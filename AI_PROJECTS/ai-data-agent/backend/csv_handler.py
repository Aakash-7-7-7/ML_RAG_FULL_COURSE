import pandas as pd 

current_dataframe=None
original_dataframe=None

def load_csv_to_dataframe(file_path):

    df=pd.read_csv(file_path)
    return df 

def set_current_dataframe(df):
    global current_dataframe
    current_dataframe=df.copy()

def get_current_dataframe():
    if current_dataframe is None:
        return None
    return current_dataframe.copy()


def set_original_dataframe(df):
    global original_dataframe

    original_dataframe = df.copy()

def get_original_dataframe():
    if original_dataframe is None:
        return None

    return original_dataframe.copy()