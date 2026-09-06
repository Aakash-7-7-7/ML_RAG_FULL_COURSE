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
    plt.close("all")

    return {
        "status": "success",
        "message": f"Successfully plotted using corrected columns: '{matched_x}' and '{matched_y}'",
        "x_column_used": matched_x,
        "y_column_used": matched_y,
    }


tools = [
    null_values,
    summarize,
    get_dataset_overview,
    scatter_plot
]