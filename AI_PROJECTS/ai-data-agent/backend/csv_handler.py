import pandas as pd 

current_dataframe=None

def load_csv_to_dataframe(file_path):

    df=pd.read_csv(file_path)
    return df 

def set_current_dataframe(df):
    global current_dataframe
    current_dataframe=df

def get_current_dataframe():
    return current_dataframe