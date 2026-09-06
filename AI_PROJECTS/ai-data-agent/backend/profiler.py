from csv_handler import load_csv_to_dataframe



def null_values(df):

    nulls=df.isnull().sum()

    return nulls


def summarize(df):
    return df.describe()

def get_shape(df):

    return df.shape

def list_columns(df):
    categorical_column= df.select_dtypes(include=['object','string']).columns.tolist()
    numerical_column=df.select_dtypes(include=['number']).columns.tolist()


    return f"Total Categorical_column are: {categorical_column} , \nTotal Numerical_column are:{numerical_column}"


def get_data_types(df):

    return df.dtypes


