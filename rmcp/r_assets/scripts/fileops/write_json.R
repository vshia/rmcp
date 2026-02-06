# JSON File Writing Script for RMCP
# ==================================
#
# This script writes data to JSON files using jsonlite package with
# support for column-wise formatting and pretty printing options.

# Load required libraries
if (!require(jsonlite, quietly = TRUE)) {
  stop("Package 'jsonlite' is required but not installed. Please install it with: install.packages('jsonlite')")
}

# Helper function to convert row-oriented data to data frame
# Row-oriented: [{col1: val1, col2: val1}, {col1: val2, col2: val2}]
# Column-oriented: {col1: [val1, val2], col2: [val1, val2]}
convert_to_dataframe <- function(data) {
    if (is.data.frame(data)) {
        return(data)
    }

    if (is.matrix(data)) {
        return(as.data.frame(data))
    }

    if (is.list(data)) {
        # Check if it's row-oriented (list of named lists/vectors)
        # Row-oriented: each element is a row with named columns
        if (length(data) > 0 && is.list(data[[1]]) && !is.null(names(data[[1]]))) {
            # Row-oriented data - convert to data frame
            # bind_rows equivalent using do.call(rbind, ...)
            df <- do.call(rbind, lapply(data, function(row) {
                as.data.frame(row, stringsAsFactors = FALSE)
            }))
            return(df)
        }

        # Check if it's column-oriented (named list of vectors)
        if (!is.null(names(data)) && all(sapply(data, function(x) is.atomic(x) || is.null(x)))) {
            # Column-oriented data
            return(as.data.frame(data, stringsAsFactors = FALSE))
        }

        # Try generic conversion
        return(as.data.frame(data, stringsAsFactors = FALSE))
    }

    stop(paste0(
        "Cannot convert data to data frame. ",
        "Expected column-oriented ({col: [values]}) or row-oriented ([{col: value}]) format. ",
        "Got: ", paste(class(data), collapse = ", ")
    ))
}

# Data resolution function
resolve_session_data <- function(args, data_param = "data") {
    # Check if data was passed inline
    if (!is.null(args[[data_param]]) && length(args[[data_param]]) > 0) {
        data <- convert_to_dataframe(args[[data_param]])
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

        # Get the object and convert to data frame
        data <- get(data_name, envir = .GlobalEnv)
        return(convert_to_dataframe(data))
    }

    # Neither provided
    stop(paste0(
        "No data provided. Either pass '", data_param, "' parameter with inline data, ",
        "or provide 'data_name' to reference an object in the R workspace."
    ))
}

# Resolve data from inline or workspace reference
data <- resolve_session_data(args)

file_path <- args$file_path
pretty_print <- args$pretty %||% TRUE
auto_unbox <- args$auto_unbox %||% TRUE

# Convert data to column-wise format (consistent with other RMCP tools)
if (is.data.frame(data)) {
  data_list <- as.list(data)
} else {
  data_list <- data
}

# Write JSON file
write_json(
  data_list,
  file_path,
  pretty = pretty_print,
  auto_unbox = auto_unbox
)
# Verify file was written
if (!file.exists(file_path)) {
  stop(paste("Failed to write JSON file:", file_path))
}
file_info <- file.info(file_path)
result <- list(
  file_path = file_path,
  rows_written = if (is.data.frame(data)) nrow(data) else if (is.list(data)) length(data) else 1,
  cols_written = if (is.data.frame(data)) ncol(data) else if (is.list(data)) length(data) else 1,
  variables_written = names(data_list),
  file_size_bytes = file_info$size,
  pretty_formatted = pretty_print,
  success = TRUE,
  timestamp = as.character(Sys.time())
)
