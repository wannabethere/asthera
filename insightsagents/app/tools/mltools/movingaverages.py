"""
Moving Aggregation Pipeline for Time Series Data

This module provides a pipeline-style moving aggregation toolkit that enables
functional composition for calculating rolling metrics and statistics on time series data.
The module follows a similar pattern to the anomaly detection, cohort, metrics, 
and operations tools, providing a consistent interface for data analysis.

Key features:
- Simple and exponentially weighted moving averages
- Moving variance and standard deviation
- Moving sums, counts, and other aggregations
- Moving percentiles and quantiles
- Moving correlation and covariance
- Window-based z-scores and normalized metrics
- Time-based and count-based windows
- Support for grouping and panel data

Example usage:

```python
import pandas as pd
from movingaggregation import MovingAggrPipe, moving_average, moving_variance

# Load data
df = pd.read_csv('time_series_data.csv')

# Create pipeline and calculate moving metrics
result = (
    MovingAggrPipe.from_dataframe(df)
    | moving_average(
        columns=['value'],
        window=7,
        method='simple'
    )
    | moving_variance(
        columns=['value'],
        window=14
    )
)

# Get results
results_df = result.data
```
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
import warnings
from .base_pipe import BasePipe


class MovingAggrPipe(BasePipe):
    """
    A pipeline-style moving aggregation tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for moving aggregation"""
        self.moving_metrics = {}
        self.current_metric = None
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'moving_metrics'):
            self.moving_metrics = source_pipe.moving_metrics.copy()
        if hasattr(source_pipe, 'current_metric'):
            self.current_metric = source_pipe.current_metric
    
    def merge_to_df(self, base_df: pd.DataFrame, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
        """
        Merge moving aggregation results into the base dataframe as new columns.
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge results into
        include_metadata : bool, default=False
            Whether to include metadata columns in the output DataFrame
        **kwargs : dict
            Additional arguments (unused for this pipeline)
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with moving aggregation results merged as new columns
        """
        result_df = base_df.copy()
        
        # Add pipeline identification
        result_df['pipeline_type'] = 'moving_aggregation'
        result_df['pipeline_has_results'] = len(self.moving_metrics) > 0
        
        # Add metadata if requested
        if include_metadata and self.moving_metrics:
            for metric_name, metric_info in self.moving_metrics.items():
                for key, value in metric_info.items():
                    if key != 'type':  # Don't duplicate the type column
                        result_df[f'moving_metadata_{metric_name}_{key}'] = str(value)
        
        return result_df
    
    def _has_results(self) -> bool:
        """
        Check if the pipeline has any moving aggregation results.
        
        Returns:
        --------
        bool
            True if the pipeline has moving aggregation results, False otherwise
        """
        return len(self.moving_metrics) > 0
    
    def get_moving_columns(self):
        """
        Get the column names that were created by the moving aggregation analysis
        
        Returns:
        --------
        List[str]
            List of column names created by the moving aggregation
        """
        if self.data is None:
            return []
        
        # Get moving aggregation columns
        moving_cols = [col for col in self.data.columns 
                      if any(suffix in col for suffix in ['_ma', '_var', '_std', '_sum', '_q', '_corr', '_zscore', '_grouped', '_ratio', '_peak', '_trough', '_reg', '_min', '_max', '_count', '_agg', '_rank', '_twa', '_cum', '_exp'])]
        
        return moving_cols
    
    def get_moving_summary_df(self, include_metadata: bool = False):
        """
        Get a summary DataFrame of all moving aggregation metrics
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns
            
        Returns:
        --------
        pd.DataFrame
            Summary DataFrame with moving aggregation statistics
        """
        if not self.moving_metrics:
            return pd.DataFrame()
        
        summary_data = []
        
        for metric_name, metric_info in self.moving_metrics.items():
            metric_type = metric_info.get('type', 'unknown')
            
            # Get columns for this metric
            if 'columns' in metric_info:
                columns = metric_info['columns']
                if isinstance(columns, list):
                    column_count = len(columns)
                    column_names = ', '.join(columns)
                else:
                    column_count = 1
                    column_names = str(columns)
            else:
                column_count = 0
                column_names = 'N/A'
            
            # Get moving columns for this metric type
            moving_cols = self.get_moving_columns()
            metric_moving_cols = [col for col in moving_cols if any(suffix in col for suffix in self._get_suffixes_for_type(metric_type))]
            
            summary_row = {
                'metric_name': metric_name,
                'type': metric_type,
                'input_columns': column_names,
                'input_column_count': column_count,
                'output_columns': ', '.join(metric_moving_cols),
                'output_column_count': len(metric_moving_cols)
            }
            
            # Add metric-specific metadata
            if include_metadata:
                for key, value in metric_info.items():
                    if key not in ['type', 'columns']:
                        summary_row[f'metadata_{key}'] = str(value)
            
            summary_data.append(summary_row)
        
        return pd.DataFrame(summary_data)
    
    def _get_suffixes_for_type(self, metric_type):
        """
        Get the suffixes associated with a specific metric type
        
        Parameters:
        -----------
        metric_type : str
            Type of moving aggregation metric
            
        Returns:
        --------
        List[str]
            List of suffixes for the given metric type
        """
        suffix_mapping = {
            'moving_average': ['_ma'],
            'moving_variance': ['_var', '_std'],
            'moving_sum': ['_sum'],
            'moving_quantile': ['_q'],
            'moving_correlation': ['_corr'],
            'moving_zscore': ['_zscore'],
            'moving_apply_by_group': ['_grouped'],
            'moving_ratio': ['_ratio'],
            'turning_points': ['_peak', '_trough'],
            'moving_regression': ['_reg', '_pred', '_resid', '_r2', '_coef', '_intercept'],
            'moving_min_max': ['_min', '_max'],
            'moving_count': ['_count'],
            'moving_aggregate': ['_agg'],
            'moving_percentile_rank': ['_rank'],
            'time_weighted_average': ['_twa'],
            'moving_cumulative': ['_cum'],
            'expanding': ['_exp']
        }
        
        return suffix_mapping.get(metric_type, [])
    
    def get_current_result(self):
        """
        Get the current moving aggregation result
        
        Returns:
        --------
        Dict
            The current moving aggregation metadata
        """
        if self.current_metric is None:
            return None
        
        return self.moving_metrics.get(self.current_metric, None)
    
    def get_metric_by_type(self, metric_type: str):
        """
        Get all metrics of a specific type
        
        Parameters:
        -----------
        metric_type : str
            Type of moving aggregation metric to retrieve
            
        Returns:
        --------
        Dict
            Dictionary of metrics of the specified type
        """
        return {name: info for name, info in self.moving_metrics.items() 
                if info.get('type') == metric_type}
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the moving aggregation results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in moving aggregation pipe)
            
        Returns:
        --------
        dict
            Summary of the moving aggregation results
        """
        if not self.moving_metrics:
            return {"error": "No moving aggregation has been performed"}
        
        # Get summary DataFrame
        summary_df = self.get_moving_summary_df()
        
        # Get moving columns
        moving_cols = self.get_moving_columns()
        
        # Count metrics by type
        metric_types = {}
        for metric_info in self.moving_metrics.values():
            metric_type = metric_info.get('type', 'unknown')
            metric_types[metric_type] = metric_types.get(metric_type, 0) + 1
        
        return {
            "total_metrics": len(self.moving_metrics),
            "total_moving_columns": len(moving_cols),
            "available_metrics": list(self.moving_metrics.keys()),
            "moving_columns": moving_cols,
            "metric_types": metric_types,
            "current_metric": self.current_metric,
            "summary_dataframe": summary_df.to_dict('records') if not summary_df.empty else [],
            "metrics_info": {name: {"type": info.get('type'), "columns": info.get('columns', [])} 
                           for name, info in self.moving_metrics.items()}
        }


def moving_average(
    columns: Union[str, List[str]],
    window: int = 7,
    method: str = 'simple',
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_ma'
):
    """
    Calculate moving averages for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate moving averages for
    window : int, default=7
        Window size for moving calculations
    method : str, default='simple'
        Moving average method: 'simple', 'weighted', 'exponential'
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_ma'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving averages in a MovingAggrPipe
    """
    def _moving_average(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving average to each group
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                if method == 'simple':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.rolling(window=window, min_periods=min_periods, center=center).mean()
                    )
                elif method == 'weighted':
                    # Linear weights (more weight to recent values)
                    # Define a weighted mean function that creates weights based on window length
                    def weighted_mean(x):
                        if len(x) == 0:
                            return np.nan
                        weights = np.arange(1, len(x) + 1)  # Dynamic weights based on window size
                        return np.sum(weights * x) / np.sum(weights)
                    
                    # Apply to each group
                    for name, group in df.groupby(group_columns):
                        # Handle single value or tuple of values for name
                        if isinstance(name, tuple):
                            mask = True
                            for i, col_name in enumerate(group_columns):
                                mask = mask & (df[col_name] == name[i])
                        else:
                            mask = df[group_columns[0]] == name
                        
                        # Apply weighted mean to this group
                        result = group[col].rolling(window=window, min_periods=min_periods, center=center).apply(
                            weighted_mean, raw=True
                        )
                        
                        # Update values in the original dataframe
                        df.loc[mask, output_col] = result.values
                        
                elif method == 'exponential':
                    # Alpha = 2/(window+1) is a common rule of thumb
                    alpha = 2 / (window + 1)
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.ewm(alpha=alpha, min_periods=min_periods, adjust=False).mean()
                    )
                else:
                    raise ValueError(f"Unknown method: {method}")
                
        else:
            # Apply moving average to entire column
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                if method == 'simple':
                    df[output_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).mean()
                elif method == 'weighted':
                    # Linear weights (more weight to recent values)
                    def weighted_mean(x):
                        if len(x) == 0:
                            return np.nan
                        weights = np.arange(1, len(x) + 1)  # Dynamic weights based on window size
                        return np.sum(weights * x) / np.sum(weights)
                    
                    df[output_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).apply(
                        weighted_mean, raw=True
                    )
                elif method == 'exponential':
                    # Alpha = 2/(window+1) is a common rule of thumb
                    alpha = 2 / (window + 1)
                    df[output_col] = df[col].ewm(alpha=alpha, min_periods=min_periods, adjust=False).mean()
                else:
                    raise ValueError(f"Unknown method: {method}")
        
        # Store results
        metric_name = f"moving_average_{method}"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_average',
            'method': method,
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_average


def moving_variance(
    columns: Union[str, List[str]],
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    ddof: int = 1,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    var_suffix: str = '_var',
    std_suffix: str = '_std'
):
    """
    Calculate moving variance and standard deviation for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate moving variance/std for
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    ddof : int, default=1
        Delta Degrees of Freedom for variance calculation
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    var_suffix : str, default='_var'
        Suffix for variance output columns
    std_suffix : str, default='_std'
        Suffix for standard deviation output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving variance in a MovingAggrPipe
    """
    def _moving_variance(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving variance to each group
            for col in cols:
                var_col = f"{col}{var_suffix}"
                std_col = f"{col}{std_suffix}"
                
                df[var_col] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).var(ddof=ddof)
                )
                
                df[std_col] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).std(ddof=ddof)
                )
                
        else:
            # Apply moving variance to entire column
            for col in cols:
                var_col = f"{col}{var_suffix}"
                std_col = f"{col}{std_suffix}"
                
                df[var_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).var(ddof=ddof)
                df[std_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).std(ddof=ddof)
        
        # Store results
        metric_name = f"moving_variance"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_variance',
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_variance


def moving_sum(
    columns: Union[str, List[str]],
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_sum'
):
    """
    Calculate moving sums for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate moving sums for
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_sum'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving sums in a MovingAggrPipe
    """
    def _moving_sum(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving sum to each group
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                df[output_col] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).sum()
                )
                
        else:
            # Apply moving sum to entire column
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                df[output_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).sum()
        
        # Store results
        metric_name = f"moving_sum"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_sum',
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_sum


def moving_quantile(
    columns: Union[str, List[str]],
    quantile: Union[float, List[float]],
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: Optional[str] = None
):
    """
    Calculate moving quantiles (percentiles) for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate moving quantiles for
    quantile : float or List[float]
        Quantile or quantiles to compute (values between 0 and 1)
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, optional
        Suffix for output columns (if None, uses '_qX' where X is the quantile value)
        
    Returns:
    --------
    Callable
        Function that calculates moving quantiles in a MovingAggrPipe
    """
    def _moving_quantile(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Convert quantile to list if it's a single value
        quantiles = [quantile] if isinstance(quantile, (int, float)) else quantile
        
        # Check if quantiles are valid
        for q in quantiles:
            if not 0 <= q <= 1:
                raise ValueError(f"Quantile value must be between 0 and 1, got {q}")
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving quantile to each group
            for col in cols:
                for q in quantiles:
                    # Generate column suffix
                    if output_suffix is None:
                        q_str = str(int(q * 100)) if q * 100 == int(q * 100) else str(q).replace('.', '_')
                        suffix = f"_q{q_str}"
                    else:
                        suffix = output_suffix
                    
                    output_col = f"{col}{suffix}"
                    
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.rolling(window=window, min_periods=min_periods, center=center).quantile(q)
                    )
                    
        else:
            # Apply moving quantile to entire column
            for col in cols:
                for q in quantiles:
                    # Generate column suffix
                    if output_suffix is None:
                        q_str = str(int(q * 100)) if q * 100 == int(q * 100) else str(q).replace('.', '_')
                        suffix = f"_q{q_str}"
                    else:
                        suffix = output_suffix
                    
                    output_col = f"{col}{suffix}"
                    
                    df[output_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).quantile(q)
        
        # Store results
        metric_name = f"moving_quantile"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_quantile',
            'window': window,
            'quantiles': quantiles,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_quantile


def moving_correlation(
    column_pairs: List[Tuple[str, str]],
    window: int = 30,
    min_periods: int = 2,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_corr'
):
    """
    Calculate moving correlations between pairs of columns
    
    Parameters:
    -----------
    column_pairs : List[Tuple[str, str]]
        List of tuples containing pairs of columns to calculate correlations for
    window : int, default=30
        Window size for moving calculations
    min_periods : int, default=2
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_corr'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving correlations in a MovingAggrPipe
    """
    def _moving_correlation(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Check if all columns exist
        for col1, col2 in column_pairs:
            if col1 not in df.columns:
                raise ValueError(f"Column '{col1}' not found in data")
            if col2 not in df.columns:
                raise ValueError(f"Column '{col2}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Define helper function to calculate rolling correlation
        def rolling_correlation(series1, series2, window, min_periods, center):
            s1 = series1.rolling(window=window, min_periods=min_periods, center=center)
            s2 = series2.rolling(window=window, min_periods=min_periods, center=center)
            
            # Calculate means and centered series
            means1 = s1.mean()
            means2 = s2.mean()
            
            # Calculate rolling covariance and standard deviations
            def _rolling_cov(x, y, mean_x, mean_y):
                return ((x - mean_x) * (y - mean_y)).mean()
            
            def _rolling_std(x, mean_x):
                return np.sqrt(((x - mean_x) ** 2).mean())
            
            # Apply windowed calculations
            rolling_covs = []
            rolling_stds1 = []
            rolling_stds2 = []
            
            for i in range(len(series1) - window + 1):
                if i + window <= len(series1):
                    x = series1.iloc[i:i+window]
                    y = series2.iloc[i:i+window]
                    
                    # Skip if not enough non-NA values
                    if sum(~np.isnan(x)) < min_periods or sum(~np.isnan(y)) < min_periods:
                        rolling_covs.append(np.nan)
                        rolling_stds1.append(np.nan)
                        rolling_stds2.append(np.nan)
                        continue
                    
                    # Calculate means for non-NA values
                    mean_x = np.nanmean(x)
                    mean_y = np.nanmean(y)
                    
                    # Calculate covariance and standard deviations
                    cov_xy = np.nanmean((x - mean_x) * (y - mean_y))
                    std_x = np.sqrt(np.nanmean((x - mean_x) ** 2))
                    std_y = np.sqrt(np.nanmean((y - mean_y) ** 2))
                    
                    rolling_covs.append(cov_xy)
                    rolling_stds1.append(std_x)
                    rolling_stds2.append(std_y)
            
            # Calculate correlation
            correlations = []
            for cov_xy, std_x, std_y in zip(rolling_covs, rolling_stds1, rolling_stds2):
                if np.isnan(cov_xy) or std_x == 0 or std_y == 0:
                    correlations.append(np.nan)
                else:
                    correlations.append(cov_xy / (std_x * std_y))
            
            # Create a series with the results
            result = pd.Series(np.nan, index=series1.index)
            
            # Adjust the indices based on center parameter
            if center:
                offset = window // 2
                result_indices = series1.index[offset:offset+len(correlations)]
            else:
                offset = window - 1
                result_indices = series1.index[offset:offset+len(correlations)]
            
            # Ensure we don't go out of bounds
            result_indices = result_indices[:len(correlations)]
            
            # Assign the values
            result.loc[result_indices] = correlations
            
            return result
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving correlation to each group
            for col1, col2 in column_pairs:
                output_col = f"{col1}_{col2}{output_suffix}"
                
                # Group by and apply correlation
                df[output_col] = np.nan  # Initialize with NaN
                
                for name, group in df.groupby(group_columns):
                    if len(group) >= min_periods:
                        # Calculate correlation within the group
                        group_corr = rolling_correlation(
                            group[col1], group[col2], window, min_periods, center
                        )
                        
                        # Update values in the result dataframe
                        df.loc[group.index, output_col] = group_corr
                
        else:
            # Apply moving correlation to entire columns
            for col1, col2 in column_pairs:
                output_col = f"{col1}_{col2}{output_suffix}"
                
                # Calculate correlation
                df[output_col] = rolling_correlation(
                    df[col1], df[col2], window, min_periods, center
                )
        
        # Store results
        metric_name = f"moving_correlation"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_correlation',
            'window': window,
            'column_pairs': column_pairs
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_correlation


def moving_zscore(
    columns: Union[str, List[str]],
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_zscore'
):
    """
    Calculate moving z-scores for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate moving z-scores for
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_zscore'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving z-scores in a MovingAggrPipe
    """
    def _moving_zscore(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving z-score to each group
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                # Calculate rolling mean and std for each group
                rolling_mean = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).mean()
                )
                
                rolling_std = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).std()
                )
                
                # Calculate z-score
                df[output_col] = (df[col] - rolling_mean) / rolling_std.replace(0, np.nan)
                
        else:
            # Apply moving z-score to entire column
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                # Calculate rolling mean and std
                rolling_mean = df[col].rolling(window=window, min_periods=min_periods, center=center).mean()
                rolling_std = df[col].rolling(window=window, min_periods=min_periods, center=center).std()
                
                # Calculate z-score
                df[output_col] = (df[col] - rolling_mean) / rolling_std.replace(0, np.nan)
        
        # Store results
        metric_name = f"moving_zscore"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_zscore',
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_zscore


    


def moving_apply_by_group(
    columns: Union[str, List[str]],
    group_column: str,
    function: Callable,
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    output_suffix: str = '_grouped'
):
    """
    Apply a function by group within a moving window
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to apply the function to
    group_column : str
        Column used to define the groups within each window
    function : Callable
        Function to apply to each group in each window (must accept a DataFrame and return a scalar or Series)
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    output_suffix : str, default='_grouped'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that applies custom group-based calculations in a MovingAggrPipe
    """
    def _moving_apply_by_group(pipe):
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
        
        # Check if group column exists
        if group_column not in df.columns:
            raise ValueError(f"Group column '{group_column}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Apply function to each window by group
        for col in cols:
            output_col = f"{col}{output_suffix}"
            df[output_col] = np.nan  # Initialize with NaN
            
            # Define function to apply to each window
            def apply_by_group(window_data):
                # Skip if not enough data
                if len(window_data) < min_periods:
                    return np.nan
                
                # Group data by the group column
                grouped = window_data.groupby(group_column)
                
                # Apply function to each group
                try:
                    result = function(grouped, col)
                    return result
                except Exception as e:
                    warnings.warn(f"Error applying function to grouped data: {str(e)}")
                    return np.nan
            
            # Apply rolling window
            for i in range(len(df)):
                # Calculate window bounds
                if center:
                    start = max(0, i - window // 2)
                    end = min(len(df), i + window // 2 + 1)
                else:
                    start = max(0, i - window + 1)
                    end = i + 1
                
                # Get window data
                window_data = df.iloc[start:end]
                
                # Apply function to groups in this window
                result = apply_by_group(window_data)
                
                # Store result
                df.loc[df.index[i], output_col] = result
        
        # Store results
        metric_name = f"moving_apply_by_group"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_apply_by_group',
            'window': window,
            'group_column': group_column,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_apply_by_group


def moving_ratio(
    numerator_column: str,
    denominator_column: str,
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    fill_zeroes: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_column: Optional[str] = None
):
    """
    Calculate the ratio of sums of two columns within a moving window
    
    Parameters:
    -----------
    numerator_column : str
        Column to use as numerator
    denominator_column : str
        Column to use as denominator
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    fill_zeroes : bool, default=False
        Replace division by zero with 0 instead of NaN
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_column : str, optional
        Name for the output column (if None, uses '{numerator_column}_to_{denominator_column}_ratio')
        
    Returns:
    --------
    Callable
        Function that calculates moving ratios in a MovingAggrPipe
    """
    def _moving_ratio(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Check if columns exist
        if numerator_column not in df.columns:
            raise ValueError(f"Numerator column '{numerator_column}' not found in data")
        if denominator_column not in df.columns:
            raise ValueError(f"Denominator column '{denominator_column}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Define output column name
        if output_column is None:
            output_col = f"{numerator_column}_to_{denominator_column}_ratio"
        else:
            output_col = output_column
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Calculate the sums for each group and window
            num_sum = df.groupby(group_columns)[numerator_column].transform(
                lambda x: x.rolling(window=window, min_periods=min_periods, center=center).sum()
            )
            
            den_sum = df.groupby(group_columns)[denominator_column].transform(
                lambda x: x.rolling(window=window, min_periods=min_periods, center=center).sum()
            )
            
        else:
            # Calculate the sums for each window
            num_sum = df[numerator_column].rolling(window=window, min_periods=min_periods, center=center).sum()
            den_sum = df[denominator_column].rolling(window=window, min_periods=min_periods, center=center).sum()
        
        # Calculate the ratio
        if fill_zeroes:
            # Replace division by zero with 0
            df[output_col] = np.divide(
                num_sum, den_sum, 
                out=np.zeros_like(num_sum, dtype=float), 
                where=den_sum != 0
            )
        else:
            # Division by zero results in NaN
            df[output_col] = num_sum / den_sum
        
        # Store results
        metric_name = f"moving_ratio"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_ratio',
            'window': window,
            'numerator': numerator_column,
            'denominator': denominator_column
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_ratio


def detect_turning_points(
    columns: Union[str, List[str]],
    window: int = 7,
    threshold: float = 0.0,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    min_periods: int = 3,
    peak_suffix: str = '_peak',
    trough_suffix: str = '_trough'
):
    """
    Detect peaks and troughs (turning points) in time series data
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to detect turning points for
    window : int, default=7
        Window size for peak/trough detection (points must be highest/lowest in window)
    threshold : float, default=0.0
        Minimum absolute percentage change required to consider a point a turning point
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    min_periods : int, default=3
        Minimum number of observations in window required to consider a turning point
    peak_suffix : str, default='_peak'
        Suffix for peak indicator columns
    trough_suffix : str, default='_trough'
        Suffix for trough indicator columns
        
    Returns:
    --------
    Callable
        Function that detects turning points in a MovingAggrPipe
    """
    def _detect_turning_points(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Detect turning points for each group
            for col in cols:
                peak_col = f"{col}{peak_suffix}"
                trough_col = f"{col}{trough_suffix}"
                
                # Initialize columns
                df[peak_col] = False
                df[trough_col] = False
                
                # Process each group
                for name, group in df.groupby(group_columns):
                    if len(group) < min_periods:
                        continue
                    
                    # Get indices for this group
                    group_indices = group.index
                    
                    # Detect turning points
                    for i in range(window, len(group) - window):
                        # Current point
                        current_idx = group_indices[i]
                        current_val = group.loc[current_idx, col]
                        
                        # Window around the point
                        window_before = group.loc[group_indices[i-window:i], col]
                        window_after = group.loc[group_indices[i+1:i+window+1], col]
                        
                        # Skip if not enough data
                        if len(window_before) < min_periods or len(window_after) < min_periods:
                            continue
                        
                        # Check for peak
                        if current_val > window_before.max() and current_val > window_after.max():
                            # Calculate percentage change
                            pct_change_before = (current_val / window_before.min() - 1) * 100
                            pct_change_after = (current_val / window_after.min() - 1) * 100
                            
                            if pct_change_before >= threshold and pct_change_after >= threshold:
                                df.loc[current_idx, peak_col] = True
                        
                        # Check for trough
                        if current_val < window_before.min() and current_val < window_after.min():
                            # Calculate percentage change
                            pct_change_before = (window_before.max() / current_val - 1) * 100
                            pct_change_after = (window_after.max() / current_val - 1) * 100
                            
                            if pct_change_before >= threshold and pct_change_after >= threshold:
                                df.loc[current_idx, trough_col] = True
                
        else:
            # Detect turning points for entire dataset
            for col in cols:
                peak_col = f"{col}{peak_suffix}"
                trough_col = f"{col}{trough_suffix}"
                
                # Initialize columns
                df[peak_col] = False
                df[trough_col] = False
                
                # Process the entire series
                if len(df) < min_periods + 2 * window:
                    continue
                
                for i in range(window, len(df) - window):
                    # Current point
                    current_idx = df.index[i]
                    current_val = df.iloc[i][col]
                    
                    # Window around the point
                    window_before = df.iloc[i-window:i][col]
                    window_after = df.iloc[i+1:i+window+1][col]
                    
                    # Skip if not enough data
                    if len(window_before) < min_periods or len(window_after) < min_periods:
                        continue
                    
                    # Check for peak
                    if current_val > window_before.max() and current_val > window_after.max():
                        # Calculate percentage change
                        pct_change_before = (current_val / window_before.min() - 1) * 100
                        pct_change_after = (current_val / window_after.min() - 1) * 100
                        
                        if pct_change_before >= threshold and pct_change_after >= threshold:
                            df.loc[current_idx, peak_col] = True
                    
                    # Check for trough
                    if current_val < window_before.min() and current_val < window_after.min():
                        # Calculate percentage change
                        pct_change_before = (window_before.max() / current_val - 1) * 100
                        pct_change_after = (window_after.max() / current_val - 1) * 100
                        
                        if pct_change_before >= threshold and pct_change_after >= threshold:
                            df.loc[current_idx, trough_col] = True
        
        # Store results
        metric_name = f"turning_points"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'turning_points',
            'window': window,
            'threshold': threshold,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _detect_turning_points


def moving_regression(
    dependent_column: str,
    independent_columns: Union[str, List[str]],
    window: int = 30,
    min_periods: int = 5,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    intercept: bool = True,
    save_coefficients: bool = True,
    save_predictions: bool = True,
    save_residuals: bool = True,
    output_suffix: str = '_reg'
):
    """
    Calculate rolling regression coefficients and statistics
    
    Parameters:
    -----------
    dependent_column : str
        Column containing the dependent variable (y)
    independent_columns : str or List[str]
        Column(s) containing the independent variable(s) (X)
    window : int, default=30
        Window size for moving calculations
    min_periods : int, default=5
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    intercept : bool, default=True
        Whether to include an intercept term in the regression
    save_coefficients : bool, default=True
        Whether to save the regression coefficients
    save_predictions : bool, default=True
        Whether to save the predicted values
    save_residuals : bool, default=True
        Whether to save the residuals
    output_suffix : str, default='_reg'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving regressions in a MovingAggrPipe
    """
    def _moving_regression(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Check if columns exist
        if dependent_column not in df.columns:
            raise ValueError(f"Dependent column '{dependent_column}' not found in data")
        
        # Convert independent columns to list if it's a string
        indep_cols = [independent_columns] if isinstance(independent_columns, str) else independent_columns
        
        for col in indep_cols:
            if col not in df.columns:
                raise ValueError(f"Independent column '{col}' not found in data")
        
        # Sort by time column if provided
        if time_column is not None:
            if time_column not in df.columns:
                raise ValueError(f"Time column '{time_column}' not found in data")
            df = df.sort_values(time_column)
        
        # Define helper function to perform OLS regression
        def rolling_ols(y, X, add_intercept=True):
            # Add intercept if requested
            if add_intercept:
                X = np.column_stack([np.ones(X.shape[0]), X])
            
            # Skip if X has no variance in any column
            if np.any(np.std(X, axis=0) == 0):
                return None
            
            # Check for multicollinearity
            if X.shape[1] > 1:
                try:
                    # Try to use the normal equations (X'X)^-1 X'y
                    XtX = X.T @ X
                    XtX_inv = np.linalg.inv(XtX)
                    coef = XtX_inv @ X.T @ y
                except np.linalg.LinAlgError:
                    # Fallback to least squares if matrix is singular
                    try:
                        coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
                    except:
                        return None
            else:
                # Simple regression
                coef = np.linalg.lstsq(X, y, rcond=None)[0]
            
            # Calculate predictions and residuals
            y_pred = X @ coef
            resid = y - y_pred
            
            # Calculate R-squared
            TSS = np.sum((y - np.mean(y))**2)
            RSS = np.sum(resid**2)
            r_squared = 1 - RSS/TSS if TSS > 0 else 0
            
            return {
                'coefficients': coef,
                'predictions': y_pred,
                'residuals': resid,
                'r_squared': r_squared
            }
        
        # Create output column names
        pred_col = f"{dependent_column}_pred{output_suffix}"
        resid_col = f"{dependent_column}_resid{output_suffix}"
        r2_col = f"{dependent_column}_r2{output_suffix}"
        
        # Initialize output columns
        if save_predictions:
            df[pred_col] = np.nan
        if save_residuals:
            df[resid_col] = np.nan
        if save_coefficients:
            df[r2_col] = np.nan
            
            # Create coefficient columns
            coef_cols = []
            if intercept:
                intercept_col = f"{dependent_column}_intercept{output_suffix}"
                df[intercept_col] = np.nan
                coef_cols.append(intercept_col)
            
            for col in indep_cols:
                coef_col = f"{col}_coef{output_suffix}"
                df[coef_col] = np.nan
                coef_cols.append(coef_col)
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Process each group
            for name, group in df.groupby(group_columns):
                if len(group) < min_periods:
                    continue
                
                # Get indices for this group
                group_indices = group.index
                
                # Apply rolling regression
                for i in range(window, len(group) + 1 if center else len(group)):
                    # Calculate window bounds
                    if center:
                        window_start = max(0, i - window // 2)
                        window_end = min(len(group), i + window // 2)
                    else:
                        window_start = i - window
                        window_end = i
                    
                    # Get window data
                    window_indices = group_indices[window_start:window_end]
                    
                    if len(window_indices) < min_periods:
                        continue
                    
                    # Get dependent and independent variables
                    y = group.loc[window_indices, dependent_column].values
                    X = group.loc[window_indices, indep_cols].values
                    
                    # Skip if there are NaNs
                    if np.any(np.isnan(y)) or np.any(np.isnan(X)):
                        continue
                    
                    # Perform regression
                    result = rolling_ols(y, X, add_intercept=intercept)
                    
                    if result is None:
                        continue
                    
                    # Current index
                    if center:
                        current_idx = group_indices[i - 1] if i < len(group) else group_indices[-1]
                    else:
                        current_idx = group_indices[i - 1]
                    
                    # Save results
                    if save_coefficients:
                        # Save R-squared
                        df.loc[current_idx, r2_col] = result['r_squared']
                        
                        # Save coefficients
                        for j, coef_col in enumerate(coef_cols):
                            if j < len(result['coefficients']):
                                df.loc[current_idx, coef_col] = result['coefficients'][j]
                    
                    if save_predictions:
                        # For the prediction, use the X value at the current index
                        x_current = group.loc[current_idx, indep_cols].values
                        if intercept:
                            x_current = np.insert(x_current, 0, 1)
                        pred = np.dot(x_current, result['coefficients'])
                        df.loc[current_idx, pred_col] = pred
                    
                    if save_residuals:
                        # Residual = actual - predicted
                        actual = group.loc[current_idx, dependent_column]
                        predicted = df.loc[current_idx, pred_col] if save_predictions else np.dot(x_current, result['coefficients'])
                        df.loc[current_idx, resid_col] = actual - predicted
                
        else:
            # Process entire dataset
            # Apply rolling regression
            for i in range(window, len(df) + 1 if center else len(df)):
                # Calculate window bounds
                if center:
                    window_start = max(0, i - window // 2)
                    window_end = min(len(df), i + window // 2)
                else:
                    window_start = i - window
                    window_end = i
                
                # Get window indices
                window_indices = df.index[window_start:window_end]
                
                if len(window_indices) < min_periods:
                    continue
                
                # Get dependent and independent variables
                y = df.loc[window_indices, dependent_column].values
                X = df.loc[window_indices, indep_cols].values
                
                # Skip if there are NaNs
                if np.any(np.isnan(y)) or np.any(np.isnan(X)):
                    continue
                
                # Perform regression
                result = rolling_ols(y, X, add_intercept=intercept)
                
                if result is None:
                    continue
                
                # Current index
                if center:
                    current_idx = df.index[i - 1] if i < len(df) else df.index[-1]
                else:
                    current_idx = df.index[i - 1]
                
                # Save results
                if save_coefficients:
                    # Save R-squared
                    df.loc[current_idx, r2_col] = result['r_squared']
                    
                    # Save coefficients
                    for j, coef_col in enumerate(coef_cols):
                        if j < len(result['coefficients']):
                            df.loc[current_idx, coef_col] = result['coefficients'][j]
                
                if save_predictions:
                    # For the prediction, use the X value at the current index
                    x_current = df.loc[current_idx, indep_cols].values
                    if intercept:
                        x_current = np.insert(x_current, 0, 1)
                    pred = np.dot(x_current, result['coefficients'])
                    df.loc[current_idx, pred_col] = pred
                
                if save_residuals:
                    # Residual = actual - predicted
                    actual = df.loc[current_idx, dependent_column]
                    predicted = df.loc[current_idx, pred_col] if save_predictions else np.dot(x_current, result['coefficients'])
                    df.loc[current_idx, resid_col] = actual - predicted
        
        # Store results
        metric_name = f"moving_regression"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_regression',
            'window': window,
            'dependent': dependent_column,
            'independent': indep_cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_regression
    


def moving_min_max(
    columns: Union[str, List[str]],
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    min_suffix: str = '_min',
    max_suffix: str = '_max'
):
    """
    Calculate moving minimum and maximum values for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate moving min/max for
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    min_suffix : str, default='_min'
        Suffix for minimum value output columns
    max_suffix : str, default='_max'
        Suffix for maximum value output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving min/max in a MovingAggrPipe
    """
    def _moving_min_max(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving min and max to each group
            for col in cols:
                min_col = f"{col}{min_suffix}"
                max_col = f"{col}{max_suffix}"
                
                df[min_col] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).min()
                )
                
                df[max_col] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).max()
                )
                
        else:
            # Apply moving min and max to entire column
            for col in cols:
                min_col = f"{col}{min_suffix}"
                max_col = f"{col}{max_suffix}"
                
                df[min_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).min()
                df[max_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).max()
        
        # Store results
        metric_name = f"moving_min_max"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_min_max',
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_min_max


def moving_count(
    columns: Union[str, List[str]],
    condition: Optional[Callable] = None,
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_count'
):
    """
    Calculate moving count of observations or observations meeting a condition
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to count observations for
    condition : Callable, optional
        Function that takes a series and returns a boolean mask (if None, counts non-NaN values)
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_count'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving counts in a MovingAggrPipe
    """
    def _moving_count(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving count to each group
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                if condition is None:
                    # Count non-NaN values
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.rolling(window=window, min_periods=min_periods, center=center).count()
                    )
                else:
                    # Count values meeting the condition
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: condition(x).rolling(window=window, min_periods=min_periods, center=center).sum()
                    )
                
        else:
            # Apply moving count to entire column
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                if condition is None:
                    # Count non-NaN values
                    df[output_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).count()
                else:
                    # Count values meeting the condition
                    df[output_col] = condition(df[col]).rolling(window=window, min_periods=min_periods, center=center).sum()
        
        # Store results
        metric_name = f"moving_count"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_count',
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_count


def moving_aggregate(
    columns: Union[str, List[str]],
    function: Callable,
    window: int = 7,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_agg'
):
    """
    Apply a custom aggregation function over a moving window
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to apply the function to
    function : Callable
        Function to apply to each window (must accept a Series and return a scalar)
    window : int, default=7
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_agg'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that applies custom aggregation in a MovingAggrPipe
    """
    def _moving_aggregate(pipe):
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
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply custom function to each group
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                df[output_col] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods, center=center).apply(
                        function, raw=False
                    )
                )
                
        else:
            # Apply custom function to entire column
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                df[output_col] = df[col].rolling(window=window, min_periods=min_periods, center=center).apply(
                    function, raw=False
                )
        
        # Store results
        metric_name = f"moving_aggregate"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_aggregate',
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_aggregate


def moving_percentile_rank(
    columns: Union[str, List[str]],
    window: int = 30,
    min_periods: int = 1,
    center: bool = False,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_rank'
):
    """
    Calculate the percentile rank of each value within a moving window
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate percentile ranks for
    window : int, default=30
        Window size for moving calculations
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    center : bool, default=False
        Set the labels at the center of the window
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_rank'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates moving percentile ranks in a MovingAggrPipe
    """
    def _moving_percentile_rank(pipe):
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
        
        # Define function to calculate percentile rank
        def percentile_rank(x):
            if len(x) <= 1:
                return 0.5  # Default for single value
            
            # Get the current (last) value
            current_value = x.iloc[-1]
            
            # Get the previous values
            previous_values = x.iloc[:-1]
            
            if len(previous_values) == 0:
                return 0.5
            
            # Calculate rank
            rank = sum(previous_values < current_value) / len(previous_values)
            
            return rank
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving percentile rank to each group
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                # This is more complex with grouping, need to iterate through groups
                df[output_col] = np.nan  # Initialize with NaN
                
                for name, group in df.groupby(group_columns):
                    # Skip small groups
                    if len(group) < min_periods:
                        continue
                    
                    # Calculate rolling percentile rank
                    ranks = []
                    
                    for i in range(len(group)):
                        if i < window - 1:
                            # Not enough history, use available data
                            window_data = group[col].iloc[:i+1]
                        else:
                            # Full window
                            window_data = group[col].iloc[i-window+1:i+1]
                        
                        if len(window_data) < min_periods:
                            ranks.append(np.nan)
                        else:
                            # Calculate rank of last value
                            current_value = window_data.iloc[-1]
                            previous_values = window_data.iloc[:-1]
                            
                            if len(previous_values) == 0:
                                ranks.append(0.5)
                            else:
                                rank = sum(previous_values < current_value) / len(previous_values)
                                ranks.append(rank)
                    
                    # Update values in the result dataframe
                    df.loc[group.index, output_col] = ranks
                
        else:
            # Apply moving percentile rank to entire column
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                # Calculate rolling percentile rank
                ranks = []
                
                for i in range(len(df)):
                    if i < window - 1:
                        # Not enough history, use available data
                        window_data = df[col].iloc[:i+1]
                    else:
                        # Full window
                        window_data = df[col].iloc[i-window+1:i+1]
                    
                    if len(window_data) < min_periods:
                        ranks.append(np.nan)
                    else:
                        # Calculate rank of last value
                        current_value = window_data.iloc[-1]
                        previous_values = window_data.iloc[:-1]
                        
                        if len(previous_values) == 0:
                            ranks.append(0.5)
                        else:
                            rank = sum(previous_values < current_value) / len(previous_values)
                            ranks.append(rank)
                
                df[output_col] = ranks
        
        # Store results
        metric_name = f"moving_percentile_rank"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_percentile_rank',
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_percentile_rank


def time_weighted_average(
    columns: Union[str, List[str]],
    window: int = 7,
    decay_factor: float = 0.5,
    min_periods: int = 1,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: str = '_twa'
):
    """
    Calculate time-weighted average with exponential decay for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate time-weighted averages for
    window : int, default=7
        Window size for moving calculations
    decay_factor : float, default=0.5
        Exponential decay factor (higher values give more weight to recent observations)
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, default='_twa'
        Suffix for output columns
        
    Returns:
    --------
    Callable
        Function that calculates time-weighted averages in a MovingAggrPipe
    """
    def _time_weighted_average(pipe):
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
        
        # Validate decay factor
        if not 0 < decay_factor < 1:
            raise ValueError("Decay factor must be between 0 and 1 exclusive")
        
        # Define function to calculate time-weighted average
        def weighted_avg(x):
            if len(x) < min_periods:
                return np.nan
            
            # Create weights (newer values have higher weights)
            weights = np.array([(1 - decay_factor) ** i for i in range(len(x) - 1, -1, -1)])
            
            # Normalize weights to sum to 1
            weights = weights / weights.sum()
            
            # Calculate weighted average
            return np.sum(x * weights)
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply time-weighted average to each group
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                df[output_col] = df.groupby(group_columns)[col].transform(
                    lambda x: x.rolling(window=window, min_periods=min_periods).apply(
                        weighted_avg, raw=True
                    )
                )
                
        else:
            # Apply time-weighted average to entire column
            for col in cols:
                output_col = f"{col}{output_suffix}"
                
                df[output_col] = df[col].rolling(window=window, min_periods=min_periods).apply(
                    weighted_avg, raw=True
                )
        
        # Store results
        metric_name = f"time_weighted_average"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'time_weighted_average',
            'window': window,
            'decay_factor': decay_factor,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _time_weighted_average




def moving_cumulative(
    columns: Union[str, List[str]],
    operation: str = 'sum',
    window: int = None,
    min_periods: int = 1,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: Optional[str] = None
):
    """
    Calculate moving cumulative metrics for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate moving cumulative metrics for
    operation : str, default='sum'
        Operation to perform: 'sum', 'product', 'max', 'min'
    window : int, optional
        Window size for moving calculations. If None, cumulative over all prior data
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    time_column : str, optional
        Column containing the time/date information for time-based windows
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, optional
        Suffix for output columns. If None, defaults to '_cum{operation}'
        
    Returns:
    --------
    Callable
        Function that calculates moving cumulative metrics in a MovingAggrPipe
    """
    def _moving_cumulative(pipe):
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
        
        # Define column suffix
        if output_suffix is None:
            suffix = f"_cum{operation}"
        else:
            suffix = output_suffix
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply moving cumulative to each group
            for col in cols:
                output_col = f"{col}{suffix}"
                
                # Handle different operations
                if operation == 'sum':
                    if window is None:
                        # Cumulative sum over all prior data
                        df[output_col] = df.groupby(group_columns)[col].cumsum()
                    else:
                        # Rolling sum over window
                        df[output_col] = df.groupby(group_columns)[col].transform(
                            lambda x: x.rolling(window=window, min_periods=min_periods).sum()
                        )
                
                elif operation == 'product':
                    if window is None:
                        # Cumulative product over all prior data
                        df[output_col] = df.groupby(group_columns)[col].cumprod()
                    else:
                        # Rolling product over window
                        df[output_col] = df.groupby(group_columns)[col].transform(
                            lambda x: x.rolling(window=window, min_periods=min_periods).apply(
                                lambda x: np.prod(x), raw=True
                            )
                        )
                
                elif operation == 'max':
                    if window is None:
                        # Cumulative max over all prior data
                        df[output_col] = df.groupby(group_columns)[col].cummax()
                    else:
                        # Rolling max over window
                        df[output_col] = df.groupby(group_columns)[col].transform(
                            lambda x: x.rolling(window=window, min_periods=min_periods).max()
                        )
                
                elif operation == 'min':
                    if window is None:
                        # Cumulative min over all prior data
                        df[output_col] = df.groupby(group_columns)[col].cummin()
                    else:
                        # Rolling min over window
                        df[output_col] = df.groupby(group_columns)[col].transform(
                            lambda x: x.rolling(window=window, min_periods=min_periods).min()
                        )
                
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
        else:
            # Apply moving cumulative to entire column
            for col in cols:
                output_col = f"{col}{suffix}"
                
                # Handle different operations
                if operation == 'sum':
                    if window is None:
                        # Cumulative sum over all prior data
                        df[output_col] = df[col].cumsum()
                    else:
                        # Rolling sum over window
                        df[output_col] = df[col].rolling(window=window, min_periods=min_periods).sum()
                
                elif operation == 'product':
                    if window is None:
                        # Cumulative product over all prior data
                        df[output_col] = df[col].cumprod()
                    else:
                        # Rolling product over window
                        df[output_col] = df[col].rolling(window=window, min_periods=min_periods).apply(
                            lambda x: np.prod(x), raw=True
                        )
                
                elif operation == 'max':
                    if window is None:
                        # Cumulative max over all prior data
                        df[output_col] = df[col].cummax()
                    else:
                        # Rolling max over window
                        df[output_col] = df[col].rolling(window=window, min_periods=min_periods).max()
                
                elif operation == 'min':
                    if window is None:
                        # Cumulative min over all prior data
                        df[output_col] = df[col].cummin()
                    else:
                        # Rolling min over window
                        df[output_col] = df[col].rolling(window=window, min_periods=min_periods).min()
                
                else:
                    raise ValueError(f"Unknown operation: {operation}")
        
        # Store results
        metric_name = f"moving_cumulative_{operation}"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'moving_cumulative',
            'operation': operation,
            'window': window,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _moving_cumulative

def expanding_window(
    columns: Union[str, List[str]],
    operation: str = 'mean',
    min_periods: int = 1,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None,
    output_suffix: Optional[str] = None
):
    """
    Calculate metrics using an expanding window (all prior data)
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate expanding window metrics for
    operation : str, default='mean'
        Operation to perform: 'mean', 'sum', 'std', 'var', 'min', 'max', 'count'
    min_periods : int, default=1
        Minimum number of observations in window required to have a value
    time_column : str, optional
        Column containing the time/date information for sorting
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    output_suffix : str, optional
        Suffix for output columns. If None, defaults to '_exp{operation}'
        
    Returns:
    --------
    Callable
        Function that calculates expanding window metrics in a MovingAggrPipe
    """
    def _expanding_window(pipe):
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
        
        # Define column suffix
        if output_suffix is None:
            suffix = f"_exp{operation}"
        else:
            suffix = output_suffix
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply expanding window to each group
            for col in cols:
                output_col = f"{col}{suffix}"
                
                # Handle different operations
                if operation == 'mean':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.expanding(min_periods=min_periods).mean()
                    )
                elif operation == 'sum':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.expanding(min_periods=min_periods).sum()
                    )
                elif operation == 'std':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.expanding(min_periods=min_periods).std()
                    )
                elif operation == 'var':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.expanding(min_periods=min_periods).var()
                    )
                elif operation == 'min':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.expanding(min_periods=min_periods).min()
                    )
                elif operation == 'max':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.expanding(min_periods=min_periods).max()
                    )
                elif operation == 'count':
                    df[output_col] = df.groupby(group_columns)[col].transform(
                        lambda x: x.expanding(min_periods=min_periods).count()
                    )
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
        else:
            # Apply expanding window to entire column
            for col in cols:
                output_col = f"{col}{suffix}"
                
                # Handle different operations
                if operation == 'mean':
                    df[output_col] = df[col].expanding(min_periods=min_periods).mean()
                elif operation == 'sum':
                    df[output_col] = df[col].expanding(min_periods=min_periods).sum()
                elif operation == 'std':
                    df[output_col] = df[col].expanding(min_periods=min_periods).std()
                elif operation == 'var':
                    df[output_col] = df[col].expanding(min_periods=min_periods).var()
                elif operation == 'min':
                    df[output_col] = df[col].expanding(min_periods=min_periods).min()
                elif operation == 'max':
                    df[output_col] = df[col].expanding(min_periods=min_periods).max()
                elif operation == 'count':
                    df[output_col] = df[col].expanding(min_periods=min_periods).count()
                else:
                    raise ValueError(f"Unknown operation: {operation}")
        
        # Store results
        metric_name = f"expanding_{operation}"
        new_pipe.data = df
        new_pipe.moving_metrics[metric_name] = {
            'type': 'expanding',
            'operation': operation,
            'columns': cols
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _expanding_window