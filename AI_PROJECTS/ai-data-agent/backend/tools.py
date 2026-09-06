from langchain_core.tools import tool
from difflib import get_close_matches

from csv_handler import get_current_dataframe
import matplotlib.pyplot as plt 


@tool
def null_values():
    """Show the number of missing or null values in each column."""

    df = get_current_dataframe()

    nulls = df.isnull().sum().to_dict()

    return {
        "nulls": nulls
    }


@tool
def summarize():
    """Get summary statistics for numerical columns, including count, mean, standard deviation, minimum, maximum, and quartiles."""

    df = get_current_dataframe()

    info = df.describe().to_dict()

    return {
        "summarized_info": info
    }


@tool
def get_dataset_overview():
    """Get general information about the currently uploaded dataset."""

    df = get_current_dataframe()

    rows = df.shape[0]
    columns = df.shape[1]

    column_names = df.columns.tolist()

    numerical_columns = df.select_dtypes(
        include=["number"]
    ).columns.tolist()

    categorical_columns = df.select_dtypes(
        include=["object", "string"]
    ).columns.tolist()

    return {
        "total_rows": rows,
        "total_columns": columns,
        "column_names": column_names,
        "numerical_columns": numerical_columns,
        "categorical_columns": categorical_columns
    }

@tool
def scatter_plot(x_column: str, y_column: str) -> dict:
    """Generates a scatter plot between two columns. Handles minor typos in column names."""
    
    # 1. Fetch the active dataframe
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}
        
    available_columns = list(df.columns)

    # 2. Fuzzy matching helper function
    def find_best_match(col_name: str, options: list) -> str:
        # Check for exact match first (case-insensitive)
        for opt in options:
            if col_name.strip().lower() == opt.strip().lower():
                return opt
        # Fallback to fuzzy matching (cutoff 0.6 means 60% similarity match)
        matches = get_close_matches(col_name, options, n=1, cutoff=0.6)
        return matches[0] if matches else None

    # Find the closest matching columns in the dataset
    matched_x = find_best_match(x_column, available_columns)
    matched_y = find_best_match(y_column, available_columns)

    # 3. Validation
    missing = []
    if not matched_x: missing.append(f"'{x_column}'")
    if not matched_y: missing.append(f"'{y_column}'")
    
    if missing:
        return {
            "error": f"Could not find a match for: {', '.join(missing)}. Available columns are: {available_columns}"
        }

    # 4. Plotting using the corrected column names
    plt.figure(figsize=(8, 6))
    plt.scatter(df[matched_x], df[matched_y], alpha=0.7, edgecolors="k")
    plt.title(f"Scatter Plot: {matched_x} vs {matched_y}")
    plt.xlabel(matched_x)
    plt.ylabel(matched_y)
    plt.grid(True)
    plt.show()
    plt.close()

    return {
        "status": "success",
        "message": f"Successfully plotted using corrected columns: '{matched_x}' and '{matched_y}'",
        "x_column_used": matched_x,
        "y_column_used": matched_y,
    }

@tool
def histogram(column: str) -> dict:
    """Generate and display a histogram for a numerical column.
    Handles minor typos in column names.
    """

    df = get_current_dataframe()

    if df is None or df.empty:
        return {
            "error": "No active dataset found. Please load a CSV first."
        }

    available_columns = list(df.columns)

    def find_best_match(col_name: str,options: list) -> str | None:

        # First try exact case-insensitive match
        for opt in options:
            if col_name.strip().lower() == opt.strip().lower():
                return opt

        # Then try fuzzy matching
        matches = get_close_matches(col_name,options,n=1,cutoff=0.6)

        return matches[0] if matches else None


    matched_column = find_best_match(column,available_columns)


    if not matched_column:
        return {
            "error": (
                f"Could not find a match for '{column}'. "
                f"Available columns are: {available_columns}"
            )
        }


    # Check if column is numeric
    if not df[matched_column].dtype.kind in "biufc":
        return {
            "error": (
                f"'{matched_column}' is not a numerical column. "
                "A histogram requires numerical data."
            )
        }


    # Remove null values
    data = df[matched_column].dropna()


    plt.figure(figsize=(8, 6))
    plt.hist(data,bins=5,edgecolor="black")
    plt.title(f"Distribution of {matched_column}")
    plt.xlabel(matched_column)
    plt.ylabel("Frequency")
    plt.grid(True)
    plt.show()
    plt.close()


    return {
        "status": "success",
        "chart_type": "histogram",
        "message": (
            f"Successfully generated a histogram for "
            f"'{matched_column}'."
        ),
        "column_used": matched_column,
        "total_values": len(data)
    }


@tool
def line_plot(y_column: str, x_column: str | None = None) -> dict:
    """
    Generate a line plot.

    Use a univariate line plot when only y_column is provided.
    The dataset row index will be used as the x-axis.

    Use a bivariate line plot when both x_column and y_column
    are provided.

    The x_column and y_column should be different for a
    bivariate line plot.
    """

    
    df = get_current_dataframe()
    if df is None or df.empty:
        return {"error": "No active dataset found. Please load a CSV first."}
    
    available_columns = list(df.columns)

    def find_best_match(col_name: str | None, options: list) -> str | None:
        if col_name is None:
            return None
        for opt in options:
            if col_name.strip().lower() == opt.strip().lower():
                return opt 
        matches = get_close_matches(col_name, options, n=1, cutoff=0.6)
        return matches[0] if matches else None

    matched_y = find_best_match(y_column, available_columns)
    matched_x = find_best_match(x_column, available_columns)

    # Validate y_column (always required)
    if not matched_y:
        return {
            "error": f"Could not find a match for y-column: '{y_column}'. Available columns are: {available_columns}"
        }

    # Validate x_column only if explicitly passed
    if x_column is not None and not matched_x:
        return {
            "error": f"Could not find a match for x-column: '{x_column}'. Available columns are: {available_columns}"
        }

    plt.figure(figsize=(8, 6))

    if matched_x is None:
        plt.plot(df[matched_y], marker="o", linestyle="dotted")
        plt.xlabel("Row Index")
        plt.ylabel(matched_y)
        plt.title(f"Line Plot of {matched_y}")
    else:
        plt.plot(df[matched_x], df[matched_y], marker="o", linestyle="dotted")
        plt.xlabel(matched_x)
        plt.ylabel(matched_y)
        plt.title(f"{matched_y} vs {matched_x}")

    plt.grid(True)
    plt.show()
    plt.close()

    return {
        "status": "success",
        "chart_type": "line",
        "message": "Line plot generated successfully.",
        "x_column_used": matched_x if matched_x else "Row Index",
        "y_column_used": matched_y
    }





tools = [
    null_values,
    summarize,
    get_dataset_overview,
    scatter_plot,
    histogram,
    line_plot
]