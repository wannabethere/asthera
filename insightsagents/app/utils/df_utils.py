import pandas as pd
import numpy as np
from dateutil.parser import parse


def read_dataset(file_path, sample_size=100, random_state=42):
    """
    Read a dataset from a file path with optional sampling.

    Parameters
    ----------
    file_path : str
        Path to the dataset file (supports .csv, .xlsx, .json)
    sample_size : int or float, optional
        If int, number of rows to sample
        If float, fraction of rows to sample (0.0 to 1.0)
        If None, return full dataset
    random_state : int, optional
        Random seed for reproducibility

    Returns
    -------
    pandas.DataFrame
        The loaded dataset (sampled if sample_size specified)

    Raises
    ------
    ValueError
        If file extension is not supported
    """
    file_ext = file_path.split('.')[-1].lower()
    
    if file_ext == 'csv':
        df = pd.read_csv(file_path)
    elif file_ext == 'xlsx':
        df = pd.read_excel(file_path)
    elif file_ext == 'json':
        df = pd.read_json(file_path)
    else:
        raise ValueError(f"Unsupported file extension: {file_ext}")
    
    if sample_size is not None:
        if isinstance(sample_size, float):
            if not 0.0 <= sample_size <= 1.0:
                raise ValueError("Sample size must be between 0.0 and 1.0 when float")
            sample_size = int(len(df) * sample_size)
        
        df = df.sample(n=sample_size, random_state=random_state)
    
    return df

def get_random_sample(df, sample_size=None, random_state=None):
    """
    Get a random sample from a pandas dataframe.

    Parameters
    ----------
    df : pandas.DataFrame
        Dataframe to sample from
    sample_size : int or float, optional
        If int, number of rows to sample
        If float, fraction of rows to sample (0.0 to 1.0)
        If None, return full dataset
    random_state : int, optional
        Random seed for reproducibility

    Returns
    -------
    pandas.DataFrame
        Sampled dataframe

    Raises
    ------
    ValueError
        If sample_size is invalid
    """
    if sample_size is None:
        return df
        
    if isinstance(sample_size, float):
        if not 0.0 <= sample_size <= 1.0:
            raise ValueError("Sample size must be between 0.0 and 1.0 when float")
        sample_size = int(len(df) * sample_size)
    
    return df.sample(n=sample_size, random_state=random_state)
def create_embeddings_from_df(df, embedding_model, columns=None, batch_size=100):
    """
    Create embeddings from a pandas dataframe to compress the size of the payload.

    Parameters
    ----------
    df : pandas.DataFrame
        Dataframe to create embeddings from
    embedding_model : Any
        OpenAI embedding model to use
    columns : list, optional
        List of columns to create embeddings from. If None, uses all columns
    batch_size : int, optional
        Number of rows to process at once, by default 100

    Returns
    -------
    numpy.ndarray
        Array of embeddings for each row in the dataframe
    """
    if columns is None:
        columns = df.columns

    # Combine selected columns into a single text for each row
    texts = df[columns].astype(str).agg(' '.join, axis=1).tolist()
    
    # Process in batches to avoid memory issues
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = embedding_model.embed_documents(batch)
        embeddings.extend(batch_embeddings)
    
    return np.array(embeddings)


def get_schema_and_top_values(df, k=5, max_str_len=100):
    """
    Get schema and top values for each column in a dataframe.

    Parameters
    ----------
    df : pandas.DataFrame
        Dataframe to analyze
    k : int, optional
        Number of top values to extract per column, by default 5
    max_str_len : int, optional
        Maximum length of string values (will be truncated), by default 100

    Returns
    -------
    tuple
        (schema_str, top_values_dict)
        schema_str: String representation of the schema
        top_values_dict: Dictionary mapping column names to their top k values
    """
    schema = get_schema(df)
    schema_str = str(schema)
    
    top_values = {}
    for col in df.columns:
        if df[col].dtype == 'object' or df[col].dtype == 'category':
            top_values[col] = _extract_top_values(df[col], k=k, max_str_len=max_str_len)
    
    return schema_str, top_values


def _extract_top_values(values, k=5, max_str_len=100):
    """
    Extracts the top k values from a pandas series

    Parameters
    ----------
    values : pandas.Series
        Series to extract top values from
    k : int, optional
        Number of top values to extract, by default 5
    max_str_len : int, optional
        Maximum length of string values (will be truncated), by default 100

    """
    top = values.value_counts().iloc[:k].index.values.tolist()
    top = [x if not isinstance(x, str) else x[:max_str_len] for x in top]
    return top


def get_schema(df):
    """
    Extracts schema from a pandas dataframe

    Parameters
    ----------
    df : pandas.DataFrame
        Dataframe to extract schema from

    Returns
    -------
    list of dict
        Schema for each column in the dataframe

    """
    schema = []

    for col in df.columns:
        info = {
            "name": col,
            "type": df[col].dtype,
            "missing_count": df[col].isna().sum(),
            "unique_count": df[col].unique().shape[0],
        }

        # If the column is numeric, extract some stats
        if np.issubdtype(df[col].dtype, np.number):
            info["min"] = df[col].min()
            info["max"] = df[col].max()
            info["mean"] = df[col].mean()
            info["std"] = df[col].std()
        # If the column is a date, extract the min and max
        elif _is_date(df[col].iloc[0]):
            info["min"] = df[col].dropna().min()
            info["max"] = df[col].dropna().max()
        # If the column is something else, extract the top values
        else:
            info["top5_unique_values"] = _extract_top_values(df[col])

        schema.append(info)

    return schema


def schema_to_str(schema) -> str:
    """Converts the list of dict to a promptable string.

    Parameters
    ----------
    schema : list of dict
        Schema for each column in the dataframe

    Returns
    -------
    str
        String representation of the schema
    """
    schema_str = ""
    for col in schema:
        schema_str += f"Column: {col['name']} ({col['type']})\n"
        for key, val in col.items():
            if key in ["name", "type"]:
                continue
            schema_str += f"  {key}: {val}\n"
    return schema_str


def _is_date(string):
    """
    Checks if a string is a date

    Parameters
    ----------
    string : str
        String to check

    Returns
    -------
    bool
        True if the string is a date, False otherwise

    """
    try:
        parse(str(string))
        return True
    except ValueError:
        return False


def schema_to_str(schema) -> str:
    """Converts the list of dict to a promptable string.

    Parameters
    ----------
    schema : list of dict
        Schema for each column in the dataframe

    Returns
    -------
    str
        String representation of the schema
    """
    schema_str = ""
    for col in schema:
        schema_str += f"Column: {col['name']} ({col['type']})\n"
        for key, val in col.items():
            if key in ["name", "type"]:
                continue
            schema_str += f"  {key}: {val}\n"
    return schema_str

