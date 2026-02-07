# Time Series Plot Visualization Script for RMCP
# ===============================================
#
# This script creates time series plots for trend analysis with forecasting visualization.
# Supports both inline data and workspace references via data_name.

# Load required libraries
options(repos = c(CRAN = "https://cloud.r-project.org/"))
library(ggplot2)
library(rlang)

# Prepare parameters
title <- args$title %||% "Time Series Plot"
file_path <- args$file_path
return_image <- args$return_image %||% TRUE
show_trend <- args$show_trend %||% TRUE
width <- args$width %||% 1000
height <- args$height %||% 600

# Use resolve_timeseries_data for session-aware data loading
# This supports both inline data ({values, dates}) and workspace references via data_name
# The function fails fast with a clear error if no data is provided
ts_input <- resolve_timeseries_data(args)

# Convert timeseries input to data.frame for ggplot
if (is.list(ts_input) && "values" %in% names(ts_input)) {
  values <- ts_input$values
  dates <- ts_input$dates

  # Create data frame from values/dates format
  if (!is.null(dates) && length(dates) > 0) {
    data <- data.frame(
      time = tryCatch(as.Date(dates), error = function(e) seq_along(values)),
      value = values
    )
    time_var <- "time"
  } else {
    # No dates provided, use index
    data <- data.frame(
      time = seq_along(values),
      value = values
    )
    time_var <- "time"
  }
  variables <- "value"
} else if (is.data.frame(ts_input)) {
  # Already a data frame
  data <- ts_input
  time_var <- args$time_variable %||% "time"
  variables <- args$variables %||% "value"

  # Convert time variable if character
  if (time_var %in% names(data) && is.character(data[[time_var]])) {
    data[[time_var]] <- tryCatch(as.Date(data[[time_var]]), error = function(e) data[[time_var]])
  }
} else {
  stop("Unexpected data format. Expected {values, dates} or data.frame.")
}

# Reshape data for multiple variables
if (length(variables) > 1) {
  # Melt data for multiple series
  library(reshape2)
  melted_data <- melt(data, id.vars = time_var, measure.vars = variables)
  p <- ggplot(melted_data, aes(x = !!sym(time_var), y = value, color = variable)) +
    geom_line(linewidth = 1) +
    geom_point(alpha = 0.6) +
    labs(title = title, x = time_var, y = "Value", color = "Variable")
} else {
  # Single variable plot
  p <- ggplot(data, aes(x = !!sym(time_var), y = !!sym(variables[1]))) +
    geom_line(color = "steelblue", linewidth = 1) +
    geom_point(alpha = 0.6, color = "steelblue") +
    labs(title = title, x = time_var, y = variables[1])
}
p <- p + theme_minimal() +
  theme(
    plot.title = element_text(hjust = 0.5),
    axis.text.x = element_text(angle = 45, hjust = 1)
  )
# Save to file if path provided
if (!is.null(file_path)) {
  ggsave(file_path, plot = p, width = width / 100, height = height / 100, dpi = 100)
  plot_saved <- file.exists(file_path)
} else {
  plot_saved <- FALSE
}
# Calculate basic time series statistics
n_obs <- nrow(data)
has_dates <- inherits(data[[time_var]], "Date")

# Get the values column for statistics
values_col <- if ("value" %in% names(data)) data$value else if (length(variables) > 0 && variables[1] %in% names(data)) data[[variables[1]]] else NULL

# Prepare result with schema-compliant structure
result <- list(
  plot_type = "time_series_plot",
  statistics = list(
    mean = if (!is.null(values_col)) mean(values_col, na.rm = TRUE) else NA,
    sd = if (!is.null(values_col)) sd(values_col, na.rm = TRUE) else NA,
    min = if (!is.null(values_col)) min(values_col, na.rm = TRUE) else NA,
    max = if (!is.null(values_col)) max(values_col, na.rm = TRUE) else NA,
    range = if (!is.null(values_col)) diff(range(values_col, na.rm = TRUE)) else NA,
    n_obs = n_obs
  ),
  has_dates = has_dates,
  show_trend = show_trend,
  dimensions = list(width = width, height = height)
)
# Add file path if provided
if (!is.null(file_path)) {
  result$file_path <- file_path
  result$plot_saved <- plot_saved
}
# Generate base64 image if requested
if (return_image) {
  image_data <- if (exists("safe_encode_plot")) {
    safe_encode_plot(p, width, height)
  } else {
    "Plot created successfully but base64 encoding not available in standalone mode"
  }
  result$image_data <- image_data
}
