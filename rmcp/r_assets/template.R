# === RMCP INITIALIZED SCRIPT ===
# This script has been automatically prepared with:
# - All utility functions pre-loaded
# - Arguments parsed and validated
# - Data prepared and available

# Load required libraries
library(jsonlite)

# === RMCP UTILITIES ===
{{ UTILITIES }}

# === AUTOMATIC ARGUMENT PARSING ===
# Arguments are automatically provided by the RMCP loader system
# The 'args' variable contains validated input parameters
# The 'data' variable contains the main dataset (if provided)

# Parse arguments from command line if not already provided
if (!exists("args") || is.function(args)) {
  # Handle command line execution
  cmd_args <- commandArgs(trailingOnly = TRUE)
  if (length(cmd_args) == 0) {
    stop("No JSON arguments provided. This script should be executed through the RMCP system.")
  }
  args <- tryCatch(
    {
      fromJSON(cmd_args[1])
    },
    error = function(e) {
      stop("Failed to parse JSON arguments: ", e$message)
    }
  )
}

# Validate and prepare data
if (exists("validate_json_input") && is.function(validate_json_input)) {
  # Most scripts require data, validate generically
  # Note: data is now optional since data_name can be used instead
  required_fields <- character(0)
  args <- validate_json_input(args, required = required_fields)
}

# === SESSION-AWARE DATA RESOLUTION ===
# Resolve data from either inline args$data or workspace reference args$data_name
# Parameters:
#   args: The arguments list from the tool call
#   data_param: The name of the data parameter (default: "data")
#   required: If TRUE (default), stops with clear error when no data provided.
#             If FALSE, returns NULL for optional-data tools.
resolve_session_data <- function(args, data_param = "data", required = TRUE) {
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
        "Object '", data_name, "' not found in R workspace.\n",
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
          "Object '", data_name, "' is not a data frame or convertible type.\n",
          "Object class: ", paste(class(data), collapse = ", ")
        ))
      }
    }

    attr(data, "source") <- paste0("workspace:", data_name)
    return(data)
  }

  # Neither provided - fail fast if required, otherwise return NULL
  if (required) {
    stop(paste0(
      "No data provided. You must either:\n",
      "  1. Pass data inline via the '", data_param, "' parameter, OR\n",
      "  2. Reference a workspace object via 'data_name' parameter\n",
      "Hint: Use read_csv or read_excel with 'output_data_name' to load data first."
    ))
  }

  return(NULL)
}

# Resolve timeseries data (special format with values/dates)
# Accepts: ts, xts, zoo objects, data.frames with 'values' column, or numeric vectors
# Parameters:
#   args: The arguments list from the tool call
#   required: If TRUE (default), stops with clear error when no data provided.
#             If FALSE, returns NULL for optional-data tools.
resolve_timeseries_data <- function(args, required = TRUE) {
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
        "Object '", data_name, "' not found in R workspace.\n",
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
        "Object '", data_name, "' cannot be converted to time series format.\n",
        "Expected: ts, xts, zoo, data.frame with values column, or numeric vector.\n",
        "Got: ", paste(class(obj), collapse = ", ")
      ))
    }
    attr(data, "source") <- paste0("workspace:", data_name)
    return(data)
  }

  # Neither provided - fail fast if required, otherwise return NULL
  if (required) {
    stop(paste0(
      "No time series data provided. You must either:\n",
      "  1. Pass data inline via 'data' with {values: [...], dates: [...]} format, OR\n",
      "  2. Reference a workspace object via 'data_name' parameter\n",
      "Accepted types: ts, xts, zoo, data.frame with 'values' column, or numeric vector."
    ))
  }

  return(NULL)
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

# Prepare data variable using session-aware resolution
# This supports both inline data and workspace references via data_name
if ("data" %in% names(args) || "data_name" %in% names(args)) {
  data <- tryCatch(
    {
      resolve_session_data(args)
    },
    error = function(e) {
      # If resolution fails but data was required, stop
      # Otherwise just set data to NULL
      if ("data" %in% names(args) && !is.null(args$data)) {
        stop(e$message)
      }
      NULL
    }
  )
} else if (!exists("data")) {
  # No data provided and none exists
  data <- NULL
}

# === MAIN SCRIPT LOGIC ===
{{ MAIN_SCRIPT }}

# === SESSION PERSISTENCE ===
# If output_data_name was provided, persist the result to the workspace
if (exists("persist_output_data") && is.function(persist_output_data)) {
  persist_output_data(args)
}

# === AUTOMATIC OUTPUT HANDLING ===
# Output results in standard JSON format
if (exists("result")) {
  if (exists("format_json_output") && is.function(format_json_output)) {
    cat(safe_json(format_json_output(result)))
  } else {
    cat(jsonlite::toJSON(result, auto_unbox = TRUE))
  }
} else {
  error_msg <- list(error = "No result generated", success = FALSE)
  if (exists("safe_json") && is.function(safe_json)) {
    cat(safe_json(error_msg))
  } else {
    cat(jsonlite::toJSON(error_msg, auto_unbox = TRUE))
  }
}
