import pandas as pd
import numpy as np
from typing import List, Union, Optional, Callable, Dict, Tuple
from scipy import stats


class TimeSeriesPipe:
    """
    A pipeline-style class for time series operations using the pipe pattern.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
        # Store distribution results when calculating distributions
        self.distribution_results = {}
        # Store statistical test results
        self.test_results = {}
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe TimeSeriesPipe to {type(other)}")
    
    def copy(self):
        """Create a copy with deep copy of data"""
        new_pipe = TimeSeriesPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        new_pipe.distribution_results = self.distribution_results.copy()
        new_pipe.test_results = self.test_results.copy()
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create a TimeSeriesPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        return pipe


def lead(
    columns: Union[str, List[str]],
    periods: int = 1,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    suffix: str = '_lead'
):
    """
    Create lead (future) values for specified columns.
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to create lead values for
    periods : int, default=1
        Number of periods to lead
    time_column : str, optional
        Time column to sort by before calculating lead values
    group_columns : List[str], optional
        Columns to group by before calculating lead values (for panel data)
    suffix : str, default='_lead'
        Suffix to add to the names of lead columns
        
    Returns:
    --------
    Callable
        Function that creates lead values in a TimeSeriesPipe
    """
    def _lead(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Apply lead with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for col in group_columns:
                if col not in df.columns:
                    raise ValueError(f"Group column '{col}' not found in data")
            
            # Group by and apply lead to each group
            for col in cols:
                df[f"{col}{suffix}"] = df.groupby(group_columns)[col].shift(-periods)
        else:
            # Apply lead without grouping
            for col in cols:
                df[f"{col}{suffix}"] = df[col].shift(-periods)
        
        new_pipe.data = df
        return new_pipe
    
    return _lead


def lag(
    columns: Union[str, List[str]],
    periods: int = 1,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    suffix: str = '_lag'
):
    """
    Create lag (past) values for specified columns.
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to create lag values for
    periods : int, default=1
        Number of periods to lag
    time_column : str, optional
        Time column to sort by before calculating lag values
    group_columns : List[str], optional
        Columns to group by before calculating lag values (for panel data)
    suffix : str, default='_lag'
        Suffix to add to the names of lag columns
        
    Returns:
    --------
    Callable
        Function that creates lag values in a TimeSeriesPipe
    """
    def _lag(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Apply lag with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for col in group_columns:
                if col not in df.columns:
                    raise ValueError(f"Group column '{col}' not found in data")
            
            # Group by and apply lag to each group
            for col in cols:
                df[f"{col}{suffix}"] = df.groupby(group_columns)[col].shift(periods)
        else:
            # Apply lag without grouping
            for col in cols:
                df[f"{col}{suffix}"] = df[col].shift(periods)
        
        new_pipe.data = df
        return new_pipe
    
    return _lag


def variance_analysis(
    columns: Union[str, List[str]],
    method: str = 'rolling',
    window: int = 5,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    suffix: Optional[str] = None
):
    """
    Calculate variance and standard deviation for time series data.
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze
    method : str, default='rolling'
        Method to use: 'rolling', 'expanding', or 'ewm' (exponentially weighted moving)
    window : int, default=5
        Window size for rolling calculations (used for 'rolling' and 'ewm' methods)
    time_column : str, optional
        Time column to sort by before calculations
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    suffix : str, optional
        Suffix to add to column names (defaults to '_var' and '_std')
        
    Returns:
    --------
    Callable
        Function that calculates variance in a TimeSeriesPipe
    """
    def _variance_analysis(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
                
        # Validate method
        valid_methods = ['rolling', 'expanding', 'ewm']
        if method not in valid_methods:
            raise ValueError(f"Method must be one of {valid_methods}")
        
        # Set suffixes
        if suffix is None:
            var_suffix = '_var'
            std_suffix = '_std'
        else:
            var_suffix = f"{suffix}_var"
            std_suffix = f"{suffix}_std"
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Calculate variance with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for col in group_columns:
                if col not in df.columns:
                    raise ValueError(f"Group column '{col}' not found in data")
            
            # Group by and calculate variance for each group
            for col in cols:
                if method == 'rolling':
                    # Rolling variance and standard deviation
                    df[f"{col}{var_suffix}"] = df.groupby(group_columns)[col].rolling(
                        window=window, min_periods=1
                    ).var().reset_index(level=group_columns, drop=True)
                    
                    df[f"{col}{std_suffix}"] = df.groupby(group_columns)[col].rolling(
                        window=window, min_periods=1
                    ).std().reset_index(level=group_columns, drop=True)
                
                elif method == 'expanding':
                    # Expanding variance and standard deviation
                    df[f"{col}{var_suffix}"] = df.groupby(group_columns)[col].expanding(
                        min_periods=1
                    ).var().reset_index(level=group_columns, drop=True)
                    
                    df[f"{col}{std_suffix}"] = df.groupby(group_columns)[col].expanding(
                        min_periods=1
                    ).std().reset_index(level=group_columns, drop=True)
                
                elif method == 'ewm':
                    # Exponentially weighted variance and standard deviation
                    # Common setting: alpha = 2/(window+1)
                    alpha = 2 / (window + 1)
                    
                    df[f"{col}{var_suffix}"] = df.groupby(group_columns)[col].ewm(
                        alpha=alpha, min_periods=1
                    ).var().reset_index(level=group_columns, drop=True)
                    
                    df[f"{col}{std_suffix}"] = df.groupby(group_columns)[col].ewm(
                        alpha=alpha, min_periods=1
                    ).std().reset_index(level=group_columns, drop=True)
        else:
            # Calculate variance without grouping
            for col in cols:
                if method == 'rolling':
                    # Rolling variance and standard deviation
                    df[f"{col}{var_suffix}"] = df[col].rolling(window=window, min_periods=1).var()
                    df[f"{col}{std_suffix}"] = df[col].rolling(window=window, min_periods=1).std()
                
                elif method == 'expanding':
                    # Expanding variance and standard deviation
                    df[f"{col}{var_suffix}"] = df[col].expanding(min_periods=1).var()
                    df[f"{col}{std_suffix}"] = df[col].expanding(min_periods=1).std()
                
                elif method == 'ewm':
                    # Exponentially weighted variance and standard deviation
                    alpha = 2 / (window + 1)
                    df[f"{col}{var_suffix}"] = df[col].ewm(alpha=alpha, min_periods=1).var()
                    df[f"{col}{std_suffix}"] = df[col].ewm(alpha=alpha, min_periods=1).std()
        
        new_pipe.data = df
        return new_pipe
    
    return _variance_analysis


def distribution_analysis(
    columns: Union[str, List[str]],
    bins: int = 10,
    group_columns: Optional[List[str]] = None,
    normalize: bool = False
):
    """
    Calculate distribution statistics and histograms for time series data.
    Results are stored in the pipe's distribution_results attribute.
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze
    bins : int, default=10
        Number of bins for histogram calculation
    group_columns : List[str], optional
        Columns to group by before analysis (for panel data)
    normalize : bool, default=False
        Whether to normalize histogram counts (return proportions)
        
    Returns:
    --------
    Callable
        Function that analyzes distributions in a TimeSeriesPipe
    """
    def _distribution_analysis(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Initialize distribution results dictionary
        distribution_results = {}
        
        # Calculate distributions with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for col in group_columns:
                if col not in df.columns:
                    raise ValueError(f"Group column '{col}' not found in data")
            
            # Group by and calculate distributions for each group
            for col in cols:
                distribution_results[col] = {}
                
                for name, group in df.groupby(group_columns):
                    # Make sure name is a string key
                    if isinstance(name, tuple):
                        group_key = "_".join(str(x) for x in name)
                    else:
                        group_key = str(name)
                    
                    # Calculate histogram
                    values = group[col].dropna()
                    hist, bin_edges = np.histogram(values, bins=bins)
                    
                    if normalize:
                        hist = hist / len(values) if len(values) > 0 else hist
                    
                    # Calculate summary statistics
                    stats_dict = {
                        'count': len(values),
                        'mean': values.mean() if len(values) > 0 else np.nan,
                        'std': values.std() if len(values) > 0 else np.nan,
                        'min': values.min() if len(values) > 0 else np.nan,
                        '25%': values.quantile(0.25) if len(values) > 0 else np.nan,
                        'median': values.median() if len(values) > 0 else np.nan,
                        '75%': values.quantile(0.75) if len(values) > 0 else np.nan,
                        'max': values.max() if len(values) > 0 else np.nan
                    }
                    
                    # Store results
                    distribution_results[col][group_key] = {
                        'histogram': hist,
                        'bin_edges': bin_edges,
                        'stats': stats_dict
                    }
        else:
            # Calculate distributions without grouping
            for col in cols:
                values = df[col].dropna()
                hist, bin_edges = np.histogram(values, bins=bins)
                
                if normalize:
                    hist = hist / len(values) if len(values) > 0 else hist
                
                # Calculate summary statistics
                stats_dict = {
                    'count': len(values),
                    'mean': values.mean() if len(values) > 0 else np.nan,
                    'std': values.std() if len(values) > 0 else np.nan,
                    'min': values.min() if len(values) > 0 else np.nan,
                    '25%': values.quantile(0.25) if len(values) > 0 else np.nan,
                    'median': values.median() if len(values) > 0 else np.nan,
                    '75%': values.quantile(0.75) if len(values) > 0 else np.nan,
                    'max': values.max() if len(values) > 0 else np.nan
                }
                
                # Store results
                distribution_results[col] = {
                    'histogram': hist,
                    'bin_edges': bin_edges,
                    'stats': stats_dict
                }
        
        # Store results in the pipe
        new_pipe.distribution_results = distribution_results
        
        return new_pipe
    
    return _distribution_analysis


def cumulative_distribution(
    columns: Union[str, List[str]],
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    suffix: str = '_cdf'
):
    """
    Calculate cumulative distribution (empirical CDF) for specified columns.
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze
    time_column : str, optional
        Time column to sort by before calculations
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    suffix : str, default='_cdf'
        Suffix to add to column names
        
    Returns:
    --------
    Callable
        Function that calculates cumulative distributions in a TimeSeriesPipe
    """
    def _cumulative_distribution(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Calculate cumulative distribution with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for col in group_columns:
                if col not in df.columns:
                    raise ValueError(f"Group column '{col}' not found in data")
            
            # Group by and calculate CDF for each group
            for col in cols:
                # Two approaches for CDF:
                # 1. Using rank with pct=True for empirical CDF within each group
                df[f"{col}{suffix}"] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rank(method='average', pct=True)
                )
        else:
            # Calculate cumulative distribution without grouping
            for col in cols:
                # Using rank with pct=True for empirical CDF
                df[f"{col}{suffix}"] = df[col].rank(method='average', pct=True)
        
        new_pipe.data = df
        return new_pipe
    
    return _cumulative_distribution


def get_distribution_summary():
    """
    Return a formatted summary of distribution analysis results
    
    Returns:
    --------
    Callable
        Function that returns distribution summaries from a TimeSeriesPipe
    """
    def _get_distribution_summary(pipe):
        if not pipe.distribution_results:
            raise ValueError("No distribution results found. Call distribution_analysis() first.")
        
        summaries = {}
        
        # Process each column's distribution results
        for col, dist_results in pipe.distribution_results.items():
            if isinstance(dist_results, dict) and 'stats' in dist_results:
                # Single distribution (no grouping)
                summaries[col] = pd.DataFrame(dist_results['stats'], index=[0])
            else:
                # Multiple distributions (with grouping)
                group_stats = {}
                for group, results in dist_results.items():
                    if 'stats' in results:
                        group_stats[group] = results['stats']
                
                if group_stats:
                    summaries[col] = pd.DataFrame(group_stats).T
        
        return summaries
    
    return _get_distribution_summary


def custom_calculation(func: Callable):
    """
    Apply a custom calculation function to the data
    
    Parameters:
    -----------
    func : Callable
        A function that takes a DataFrame and returns a DataFrame
        
    Returns:
    --------
    Callable
        Function that applies the custom calculation in a TimeSeriesPipe
    """
    def _custom_calculation(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Apply the custom function
        new_pipe.data = func(df)
        
        return new_pipe
    
    return _custom_calculation



def rolling_window(
    columns: Union[str, List[str]],
    window: int = 5,
    unit: str = 'daily',
    aggregation: str = 'mean',
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    suffix: Optional[str] = None
):
    """
    Apply rolling window operations to time series data.
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze
    window : int, default=5
        Window size for rolling calculations
    unit : str, default='daily'
        Time unit for window: 'daily', 'weekly', 'monthly', or 'yearly'
    aggregation : str, default='mean'
        Aggregation type: 'mean', 'sum', 'std', or 'count'
    time_column : str, optional
        Time column to sort by before calculations
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    suffix : str, optional
        Suffix to add to column names (defaults to '_rolling_{aggregation}')
        
    Returns:
    --------
    Callable
        Function that applies rolling window operations in a TimeSeriesPipe
    """
    def _rolling_window(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Validate unit and aggregation
        valid_units = ['daily', 'weekly', 'monthly', 'yearly']
        valid_aggregations = ['mean', 'sum', 'std', 'count']
        
        if unit not in valid_units:
            raise ValueError(f"Unit must be one of {valid_units}")
        if aggregation not in valid_aggregations:
            raise ValueError(f"Aggregation must be one of {valid_aggregations}")
        
        # Set suffix
        if suffix is None:
            rolling_suffix = f'_rolling_{aggregation}'
        else:
            rolling_suffix = suffix
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Calculate window size based on unit
        window_size = window
        if unit == 'weekly':
            window_size *= 7
        elif unit == 'monthly':
            window_size *= 30
        elif unit == 'yearly':
            window_size *= 365
        
        # Calculate rolling window with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for col in group_columns:
                if col not in df.columns:
                    raise ValueError(f"Group column '{col}' not found in data")
            
            # Group by and calculate rolling window for each group
            for col in cols:
                if aggregation == 'mean':
                    df[f"{col}{rolling_suffix}"] = df.groupby(group_columns)[col].rolling(window=window_size).mean()
                elif aggregation == 'sum':
                    df[f"{col}{rolling_suffix}"] = df.groupby(group_columns)[col].rolling(window=window_size).sum()
                elif aggregation == 'std':
                    df[f"{col}{rolling_suffix}"] = df.groupby(group_columns)[col].rolling(window=window_size).std()
                else:  # count
                    df[f"{col}{rolling_suffix}"] = df.groupby(group_columns)[col].rolling(window=window_size).count()
        else:
            # Calculate rolling window without grouping
            for col in cols:
                if aggregation == 'mean':
                    df[f"{col}{rolling_suffix}"] = df[col].rolling(window=window_size).mean()
                elif aggregation == 'sum':
                    df[f"{col}{rolling_suffix}"] = df[col].rolling(window=window_size).sum()
                elif aggregation == 'std':
                    df[f"{col}{rolling_suffix}"] = df[col].rolling(window=window_size).std()
                else:  # count
                    df[f"{col}{rolling_suffix}"] = df[col].rolling(window=window_size).count()
        
        new_pipe.data = df
        return new_pipe
    
    return _rolling_window
