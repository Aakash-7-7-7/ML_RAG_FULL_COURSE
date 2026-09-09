from langchain_core.tools import tool
from difflib import get_close_matches
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from pathlib import Path
from uuid import uuid4
# Assuming these are imported correctly from your codebase
from csv_handler import get_current_dataframe, set_current_dataframe,get_original_dataframe,set_original_dataframe

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHARTS_DIR = PROJECT_ROOT / "charts"

CHARTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def save_chart() -> tuple[str, str]:
    """
    Save the current matplotlib chart as a PNG file.

    Returns:
        chart_id: Unique identifier for the chart.
        file_path: Path where the chart was saved.
    """

    chart_id = str(uuid4())

    file_path = (
        CHARTS_DIR
        / f"{chart_id}.png"
    )

    plt.tight_layout()

    plt.savefig(file_path,format="png",dpi=150,bbox_inches="tight",)

    plt.close()

    return chart_id, str(file_path)


def find_best_match(col_name: str | None, options: list) -> str | None:
    """Helper function to find exact or fuzzy matches for column names."""
    if col_name is None:
        return None
    # Check for exact match first (case-insensitive)
    for opt in options:
        if col_name.strip().lower() == opt.strip().lower():
            return opt
    # Fallback to fuzzy matching (cutoff 0.6 means 60% similarity match)
    matches = get_close_matches(col_name, options, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _drop_na_for_plot(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, int]:
    """
    Return a copy of df with rows dropped where ANY of the given columns is null,
    plus the number of rows that were excluded.

    This is applied per-plot (not to the stored dataset) so a plot is never
    skewed by missing values in the specific columns it uses, whether or not
    the user has run clean_dataset on the underlying data.
    """
    clean = df.dropna(subset=columns)
    dropped = len(df) - len(clean)
    return clean, dropped


def _fill_missing_values(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Fill missing values: median for numerical columns, mode for categorical
    columns. Returns the cleaned dataframe and a report of what was filled.
    """
    df_clean = df.copy()
    numerical_cols = df_clean.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df_clean.select_dtypes(include=["object", "string", "category"]).columns.tolist()

    report: dict[str, dict] = {}

    for col in numerical_cols:
        missing_count = int(df_clean[col].isnull().sum())
        if missing_count:
            median_val = df_clean[col].median()
            df_clean[col] = df_clean[col].fillna(median_val)
            report[col] = {
                "filled_count": missing_count,
                "method": "median",
                "fill_value": float(median_val),
            }

    for col in categorical_cols:
        missing_count = int(df_clean[col].isnull().sum())
        if missing_count:
            mode_series = df_clean[col].mode()
            mode_val = mode_series.iloc[0] if not mode_series.empty else "Unknown"
            df_clean[col] = df_clean[col].fillna(mode_val)
            report[col] = {
                "filled_count": missing_count,
                "method": "mode",
                "fill_value": str(mode_val),
            }

    return df_clean, report


@tool
def null_values():
    """Show the number of missing or null values in each column."""
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}

    nulls = df.isnull().sum().to_dict()
    return {"nulls": nulls}


@tool
def clean_dataset() -> dict:
    """
    Fill missing values in the active dataset: median for numerical columns,
    mode for categorical columns. Updates the active dataset in place so all
    subsequent tool calls (summaries, plots) use the cleaned data. Call this
    when the user asks to clean, fix, or handle missing/null values, or
    agrees to fix nulls after being told some exist.
    """
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}

    total_missing_before = int(df.isnull().sum().sum())
    if total_missing_before == 0:
        return {
            "status": "no_action_needed",
            "message": "No missing values found in the active dataset.",
        }

    df_clean, report = _fill_missing_values(df)
    set_current_dataframe(df_clean)

    return {
        "status": "success",
        "total_values_filled": total_missing_before,
        "columns_fixed": report,
        "message": (
            f"Filled {total_missing_before} missing value(s) across "
            f"{len(report)} column(s). Numerical columns were filled with "
            f"their median; categorical columns with their mode."
        ),
    }


@tool
def summarize():
    """Get summary statistics for numerical columns, including count, mean, standard deviation, minimum, maximum, and quartiles."""
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}

    info = df.describe().to_dict()
    return {"summarized_info": info}


@tool
def get_dataset_overview():
    """Get general information about the currently uploaded dataset, including whether it has missing values."""
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}

    rows, columns = df.shape
    column_names = df.columns.tolist()

    numerical_columns = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_columns = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()

    missing_summary = df.isnull().sum()
    total_missing = int(missing_summary.sum())

    result = {
        "total_rows": rows,
        "total_columns": columns,
        "column_names": column_names,
        "numerical_columns": numerical_columns,
        "categorical_columns": categorical_columns,
        "total_missing": total_missing,
    }

    if total_missing > 0:
        columns_with_missing = missing_summary[missing_summary > 0].to_dict()
        result["columns_with_missing"] = columns_with_missing
        result["recommendation"] = (
            "This dataset has missing values. Ask the user if they'd like them "
            "fixed, then call the clean_dataset tool to fill them (median for "
            "numerical columns, mode for categorical columns) before relying on "
            "plots or statistics for analysis."
        )

    return result


@tool
def scatter_plot(x_column: str, y_column: str) -> dict:
    """Generates a scatter plot between two columns. Handles minor typos in column names and excludes rows with missing values in either column."""
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}

    available_columns = list(df.columns)
    matched_x = find_best_match(x_column, available_columns)
    matched_y = find_best_match(y_column, available_columns)

    missing = []
    if not matched_x: missing.append(f"'{x_column}'")
    if not matched_y: missing.append(f"'{y_column}'")

    if missing:
        return {"error": f"Could not find a match for: {', '.join(missing)}. Available columns are: {available_columns}"}

    plot_df, dropped_rows = _drop_na_for_plot(df, [matched_x, matched_y])

    if plot_df.empty:
        return {
            "error": (
                f"No valid data to plot: every row has a missing value in "
                f"'{matched_x}' or '{matched_y}'."
            )
        }

    plt.figure(figsize=(8, 6))
    plt.scatter(plot_df[matched_x], plot_df[matched_y], alpha=0.7, edgecolors="k")
    plt.title(f"Scatter Plot: {matched_x} vs {matched_y}")
    plt.xlabel(matched_x)
    plt.ylabel(matched_y)
    plt.grid(True)
    chart_id, file_path = save_chart()

    message = f"Successfully generated scatter plot using '{matched_x}' and '{matched_y}'."
    if dropped_rows:
        message += f" Excluded {dropped_rows} row(s) with missing values in these columns."

    return {
    "status": "success",
    "chart_id": chart_id,
    "file_path": file_path,
    "chart_type": "scatter_plot",
    "message": message,
    "x_column_used": matched_x,
    "y_column_used": matched_y,
    "rows_used": len(plot_df),
    "rows_excluded_missing": dropped_rows,
    }


@tool
def histogram(column: str) -> dict:
    """Generate and display a histogram for a numerical column. Handles minor typos in column names and excludes missing values."""
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}

    available_columns = list(df.columns)
    matched_column = find_best_match(column, available_columns)

    if not matched_column:
        return {"error": f"Could not find a match for '{column}'. Available columns are: {available_columns}"}

    if not df[matched_column].dtype.kind in "biufc":
        return {"error": f"'{matched_column}' is not a numerical column. A histogram requires numerical data."}

    plot_df, dropped_rows = _drop_na_for_plot(df, [matched_column])
    data = plot_df[matched_column]

    if data.empty:
        return {"error": f"No valid data to plot: '{matched_column}' is entirely missing."}

    plt.figure(figsize=(8, 6))
    plt.hist(data, bins=15, edgecolor="black")
    plt.title(f"Distribution of {matched_column}")
    plt.xlabel(matched_column)
    plt.ylabel("Frequency")
    plt.grid(True)
    chart_id, file_path = save_chart()

    message = f"Successfully generated a histogram for '{matched_column}'."
    if dropped_rows:
        message += f" Excluded {dropped_rows} row(s) with missing values in this column."

    return {
    "status": "success",
    "chart_id": chart_id,
    "file_path": file_path,
    "chart_type": "histogram",
    "message": message,
    "column_used": matched_column,
    "total_values": len(data),
    "rows_excluded_missing": dropped_rows,
    }


@tool
def line_plot(y_column: str, x_column: str | None = None) -> dict:
    """
    Generate a line plot.
    Use a univariate line plot when only y_column is provided (uses row index as X-axis).
    Use a bivariate line plot when both x_column and y_column are provided.
    Excludes rows with missing values in the columns being plotted.
    """
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}

    available_columns = list(df.columns)
    matched_y = find_best_match(y_column, available_columns)
    matched_x = find_best_match(x_column, available_columns)

    if not matched_y:
        return {"error": f"Could not find a match for y-column: '{y_column}'. Available columns are: {available_columns}"}

    if x_column is not None and not matched_x:
        return {"error": f"Could not find a match for x-column: '{x_column}'. Available columns are: {available_columns}"}

    plot_columns = [matched_y] if not matched_x else [matched_x, matched_y]
    plot_df, dropped_rows = _drop_na_for_plot(df, plot_columns)

    if plot_df.empty:
        return {"error": "No valid data to plot after excluding rows with missing values."}

    plt.figure(figsize=(10, 5))

    if matched_x:
        # Sort values by X axis to ensure the line plot is drawn sequentially
        df_sorted = plot_df.sort_values(by=matched_x)
        plt.plot(df_sorted[matched_x], df_sorted[matched_y], marker='o', linestyle='-')
        plt.xlabel(matched_x)
        plt.title(f"Line Plot: {matched_y} vs {matched_x}")
    else:
        plt.plot(plot_df[matched_y], marker='o', linestyle='-')
        plt.xlabel("Index")
        plt.title(f"Line Plot: {matched_y} Distribution")

    plt.ylabel(matched_y)
    plt.grid(True)
    chart_id, file_path = save_chart()

    message = f"Successfully generated line plot for '{matched_y}'."
    if dropped_rows:
        message += f" Excluded {dropped_rows} row(s) with missing values in the plotted columns."

    return {
    "status": "success",
    "chart_id": chart_id,
    "file_path": file_path,
    "chart_type": "line_plot",
    "message": message,
    "x_column_used": (
        matched_x
        if matched_x
        else "Index"
    ),
    "y_column_used": matched_y,
    "rows_used": len(plot_df),
    "rows_excluded_missing": dropped_rows,
    }

@tool
def bar_chart(category_column: str, value_column: str) -> dict:
    """Generates a bar chart comparing aggregated values across categories. Excludes rows with missing values in either column."""

    df = get_current_dataframe()

    if df is None or df.empty:
        return {"error": "No active dataset found."}

    available_columns = list(df.columns)

    matched_cat = find_best_match(category_column,available_columns)

    matched_val = find_best_match(value_column,available_columns)

    if not matched_cat or not matched_val:
        return {
            "error": f"Columns not found. Options: {available_columns}"
        }

    # Prevent same column
    if matched_cat == matched_val:
        return {
            "error": (
                f"Cannot group by and aggregate the same column "
                f"('{matched_cat}'). Please provide a separate "
                f"categorical column and a numeric value column."
            )
        }

    # Make sure the VALUE column is numerical
    if not df[matched_val].dtype.kind in "biufc":
        return {
            "error": (
                f"'{matched_val}' must be a numerical column "
                "for calculating averages."
            )
        }

    # ==========================================
    # ADD THIS NEW CHECK HERE
    # ==========================================

    if df[matched_cat].dtype.kind in "biufc":

        unique_values = df[matched_cat].nunique()

        if unique_values > 10:
            return {
                    "status": "needs_alternative_visualization",

                    "reason": (
                        f"'{matched_cat}' is a numerical column with "
                        f"{unique_values} unique values."
                    ),

                    "message": (
                        "A bar chart is not the most suitable visualization "
                        "for two numerical variables with many unique values."
                    ),

                    "recommended_charts": ["scatter_plot","line_plot"],

                    "x_column": matched_cat,
                    "y_column": matched_val
                }

    # ==========================================
    # Exclude rows missing either column before aggregating, so the
    # averages aren't computed from a silently inconsistent subset.
    # ==========================================

    plot_df, dropped_rows = _drop_na_for_plot(df, [matched_cat, matched_val])

    if plot_df.empty:
        return {"error": "No valid data to plot after excluding rows with missing values."}

    summary = (plot_df.groupby(matched_cat)[matched_val].mean().reset_index(name=f"Average_{matched_val}"))

    plt.figure(figsize=(10, 8))
    plt.barh(summary[matched_cat].astype(str),summary[f"Average_{matched_val}"],edgecolor="black")
    plt.title(f"Average {matched_val} by {matched_cat}")
    plt.xlabel(f"Mean {matched_val}")
    plt.ylabel(matched_cat)
    plt.tight_layout()
    chart_id, file_path = save_chart()

    message = f"Successfully generated bar chart of average {matched_val} by {matched_cat}."
    if dropped_rows:
        message += f" Excluded {dropped_rows} row(s) with missing values in these columns."

    return {
    "status": "success",
    "chart_id": chart_id,
    "file_path": file_path,
    "chart_type": "bar_chart",
    "message": message,
    "category_column_used": matched_cat,
    "value_column_used": matched_val,
    "rows_excluded_missing": dropped_rows,
    }

@tool
def delete_columns(columns: list[str]) -> dict:
    """
    Delete one or more columns from the active dataset.

    The deleted columns can be restored later using restore_columns.
    Use this when the user asks to remove, drop, delete, or exclude
    specific columns from the dataset.
    """

    df = get_current_dataframe()

    if df is None or df.empty:
        return {
            "error": "No active dataset found. Please load a CSV first."
        }

    if not columns:
        return {
            "error": "No columns were provided for deletion."
        }

    available_columns = list(df.columns)

    matched_columns = []
    not_found = []

    for column in columns:

        matched = find_best_match(
            column,
            available_columns
        )

        if matched:
            matched_columns.append(matched)
        else:
            not_found.append(column)

    # Remove duplicates
    matched_columns = list(dict.fromkeys(matched_columns))

    if not matched_columns:
        return {
            "error": (
                f"Could not find any requested columns. "
                f"Available columns are: {available_columns}"
            ),
            "not_found": not_found,
        }

    # Prevent deleting every column
    if len(matched_columns) == len(available_columns):
        return {
            "error": (
                "Cannot delete all columns from the dataset. "
                "At least one column must remain."
            )
        }

    updated_df = df.drop(columns=matched_columns)

    set_current_dataframe(updated_df)

    return {
        "status": "success",
        "message": (
            f"Successfully deleted {len(matched_columns)} column(s). "
            "They can be restored later if needed."
        ),
        "deleted_columns": matched_columns,
        "not_found": not_found,
        "remaining_columns": updated_df.columns.tolist(),
        "remaining_column_count": len(updated_df.columns),
    }

@tool
def restore_columns(columns: list[str] | None = None) -> dict:
    """
    Restore previously deleted columns from the original dataset.

    If specific column names are provided, restores only those columns.
    If no columns are provided, restores all deleted columns.
    """

    current_df = get_current_dataframe()
    original_df = get_original_dataframe()

    if current_df is None or current_df.empty:
        return {
            "error": "No active dataset found. Please load a CSV first."
        }

    if original_df is None or original_df.empty:
        return {
            "error": (
                "Original dataset is not available, so deleted columns "
                "cannot be restored."
            )
        }

    original_columns = list(original_df.columns)
    current_columns = list(current_df.columns)

    deleted_columns = [
        col
        for col in original_columns
        if col not in current_columns
    ]

    if not deleted_columns:
        return {
            "status": "no_action_needed",
            "message": "There are no deleted columns to restore.",
            "current_columns": current_columns,
        }

    # --------------------------------
    # Restore ALL deleted columns
    # --------------------------------

    if columns is None or len(columns) == 0:

        restored_df = original_df.copy()

        set_current_dataframe(restored_df)

        return {
            "status": "success",
            "message": (
                f"Successfully restored all {len(deleted_columns)} "
                "deleted column(s)."
            ),
            "restored_columns": deleted_columns,
            "current_columns": restored_df.columns.tolist(),
        }

    # --------------------------------
    # Restore specific columns
    # --------------------------------

    matched_columns = []
    not_found = []

    for column in columns:

        matched = find_best_match(
            column,
            deleted_columns
        )

        if matched:
            matched_columns.append(matched)
        else:
            not_found.append(column)

    matched_columns = list(dict.fromkeys(matched_columns))

    if not matched_columns:
        return {
            "error": (
                "None of the requested columns are currently deleted."
            ),
            "deleted_columns_available": deleted_columns,
            "not_found": not_found,
        }

    restored_df = current_df.copy()

    for column in matched_columns:
        restored_df[column] = original_df[column]

    # Restore original column ordering
    ordered_columns = [
        col
        for col in original_columns
        if col in restored_df.columns
    ]

    restored_df = restored_df[ordered_columns]

    set_current_dataframe(restored_df)

    return {
        "status": "success",
        "message": (
            f"Successfully restored {len(matched_columns)} column(s)."
        ),
        "restored_columns": matched_columns,
        "not_found": not_found,
        "current_columns": restored_df.columns.tolist(),
    }


tools = [
    null_values,
    summarize,
    get_dataset_overview,
    clean_dataset,

    delete_columns,
    restore_columns,

    scatter_plot,
    histogram,
    line_plot,
    bar_chart
]