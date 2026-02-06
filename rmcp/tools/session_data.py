"""
Session-aware data loading utilities for RMCP tools.

This module provides utilities to make RMCP tools session-aware, allowing them to
reference data stored in the R workspace instead of requiring inline data each time.

Usage:
    from .session_data import add_data_name_param, get_data_resolution_preamble

    # In tool definition, modify schema:
    schema = add_data_name_param(original_schema)

    # In tool execution, prepend R preamble:
    r_preamble = get_data_resolution_preamble()
    full_script = r_preamble + r_script
"""

import copy
from typing import Any


def add_data_name_param(schema: dict[str, Any], data_param: str = "data") -> dict[str, Any]:
    """
    Modify a tool's input schema to add a data_name parameter.

    This makes the 'data' parameter optional and adds a 'data_name' parameter
    that can reference an object in the R workspace.

    Args:
        schema: The original input schema dict
        data_param: The name of the data parameter (default: "data")

    Returns:
        Modified schema with data_name parameter added and data made optional
    """
    # Deep copy to avoid modifying the original
    new_schema = copy.deepcopy(schema)

    # Add data_name property
    if "properties" not in new_schema:
        new_schema["properties"] = {}

    new_schema["properties"]["data_name"] = {
        "type": "string",
        "description": (
            f"Name of data object in R workspace. "
            f"Use this instead of '{data_param}' to reference previously loaded data. "
            f"Either '{data_param}' or 'data_name' must be provided."
        ),
    }

    # Remove data from required if present (make it optional)
    if "required" in new_schema and data_param in new_schema["required"]:
        new_schema["required"] = [r for r in new_schema["required"] if r != data_param]
        # If required becomes empty, remove it
        if not new_schema["required"]:
            del new_schema["required"]

    return new_schema


def add_output_data_name_param(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Modify a tool's input schema to add an output_data_name parameter.

    This allows the tool to save its result (data or result_data) back
    to the R workspace under a specific name.

    Args:
        schema: The original input schema dict

    Returns:
        Modified schema with output_data_name parameter added
    """
    new_schema = copy.deepcopy(schema)

    if "properties" not in new_schema:
        new_schema["properties"] = {}

    new_schema["properties"]["output_data_name"] = {
        "type": "string",
        "description": (
            "Name to save the resulting data as in the R workspace. "
            "If provided, the processing result will be persisted "
            "and can be referenced in subsequent tool calls using 'data_name'."
        ),
    }

    return new_schema


def add_data_name_param_timeseries(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Modify a timeseries tool's input schema to add a data_name parameter.

    Timeseries tools use a different data format ({values: [], dates: []})
    so this variant handles that case.

    Args:
        schema: The original input schema dict

    Returns:
        Modified schema with data_name parameter added
    """
    new_schema = copy.deepcopy(schema)

    if "properties" not in new_schema:
        new_schema["properties"] = {}

    new_schema["properties"]["data_name"] = {
        "type": "string",
        "description": (
            "Name of time series object in R workspace. "
            "Use this instead of 'data' to reference previously loaded data. "
            "The object should be a data frame with 'values' column, "
            "or a ts/xts object. Either 'data' or 'data_name' must be provided."
        ),
    }

    # Remove data from required if present
    if "required" in new_schema and "data" in new_schema["required"]:
        new_schema["required"] = [r for r in new_schema["required"] if r != "data"]
        if not new_schema["required"]:
            del new_schema["required"]

    return new_schema


# R code preamble for data resolution from workspace
DATA_RESOLUTION_PREAMBLE = '''
# === SESSION DATA RESOLUTION ===
# Resolve data from either inline args$data or workspace reference args$data_name

resolve_session_data <- function(args, data_param = "data") {
    # Check if data was passed inline
    if (!is.null(args[[data_param]]) && length(args[[data_param]]) > 0) {
        data <- as.data.frame(args[[data_param]])
        attr(data, "source") <- "inline"
        return(data)
    }

    # Check if data_name was provided to reference workspace object
    if (!is.null(args$data_name) && nchar(args$data_name) > 0) {
        data_name <- args$data_name

        # Check if object exists in global environment
        if (!exists(data_name, envir = .GlobalEnv)) {
            stop(paste0(
                "Object '", data_name, "' not found in R workspace.\\n",
                "Available objects: ",
                paste(ls(envir = .GlobalEnv), collapse = ", ")
            ))
        }

        # Get the object
        data <- get(data_name, envir = .GlobalEnv)

        # Convert to data frame if needed
        if (!is.data.frame(data)) {
            if (is.matrix(data)) {
                data <- as.data.frame(data)
            } else if (is.list(data)) {
                data <- as.data.frame(data)
            } else {
                stop(paste0(
                    "Object '", data_name, "' is not a data frame or convertible type.\\n",
                    "Object class: ", paste(class(data), collapse = ", ")
                ))
            }
        }

        attr(data, "source") <- paste0("workspace:", data_name)
        return(data)
    }

    # Neither provided
    stop(paste0(
        "No data provided. Either pass '", data_param, "' parameter with inline data, ",
        "or provide 'data_name' to reference an object in the R workspace."
    ))
}

# Resolve timeseries data (special format with values/dates)
resolve_timeseries_data <- function(args) {
    # Check if inline data was passed
    if (!is.null(args$data) && length(args$data) > 0) {
        data <- args$data
        attr(data, "source") <- "inline"
        return(data)
    }

    # Check if data_name was provided
    if (!is.null(args$data_name) && nchar(args$data_name) > 0) {
        data_name <- args$data_name

        if (!exists(data_name, envir = .GlobalEnv)) {
            stop(paste0(
                "Object '", data_name, "' not found in R workspace.\\n",
                "Available objects: ",
                paste(ls(envir = .GlobalEnv), collapse = ", ")
            ))
        }

        obj <- get(data_name, envir = .GlobalEnv)

        # Handle different object types
        if (inherits(obj, c("ts", "xts", "zoo"))) {
            # Time series object - extract values and dates
            data <- list(
                values = as.numeric(obj),
                dates = if (inherits(obj, "xts") || inherits(obj, "zoo")) {
                    as.character(index(obj))
                } else {
                    NULL
                }
            )
        } else if (is.data.frame(obj)) {
            # Data frame - look for values column
            if ("values" %in% names(obj)) {
                data <- list(
                    values = obj$values,
                    dates = if ("dates" %in% names(obj)) obj$dates else NULL
                )
            } else {
                # Use first numeric column as values
                num_cols <- sapply(obj, is.numeric)
                if (any(num_cols)) {
                    data <- list(
                        values = obj[[which(num_cols)[1]]],
                        dates = NULL
                    )
                } else {
                    stop(paste0(
                        "Object '", data_name, "' has no numeric columns for time series."
                    ))
                }
            }
        } else if (is.numeric(obj)) {
            # Numeric vector
            data <- list(values = obj, dates = NULL)
        } else {
            stop(paste0(
                "Object '", data_name, "' cannot be converted to time series format.\\n",
                "Expected: ts, xts, zoo, data.frame with values column, or numeric vector.\\n",
                "Got: ", paste(class(obj), collapse = ", ")
            ))
        }

        attr(data, "source") <- paste0("workspace:", data_name)
        return(data)
    }

    stop(paste0(
        "No data provided. Either pass 'data' with values/dates, ",
        "or provide 'data_name' to reference an object in the R workspace."
    ))
}

# Persistence helper
persist_output_data <- function(args) {
    if (!is.null(args$output_data_name) && nchar(args$output_data_name) > 0) {
        # Determine what to persist: result_data or data or result$data
        if (exists("result_data")) {
            assign(args$output_data_name, result_data, envir = .GlobalEnv)
        } else if (exists("data")) {
            assign(args$output_data_name, data, envir = .GlobalEnv)
        } else if (exists("result") && !is.null(result$data)) {
            assign(args$output_data_name, as.data.frame(result$data), envir = .GlobalEnv)
        }
    }
}
# === END SESSION DATA RESOLUTION ===

'''


def get_data_resolution_preamble() -> str:
    """
    Get the R code preamble for resolving data from workspace.

    This preamble should be prepended to R scripts that need session-aware
    data loading.

    Returns:
        R code string with data resolution functions
    """
    return DATA_RESOLUTION_PREAMBLE


def get_timeseries_resolution_preamble() -> str:
    """
    Get the R code preamble for resolving timeseries data from workspace.

    Returns:
        R code string with timeseries data resolution functions
    """
    return DATA_RESOLUTION_PREAMBLE
