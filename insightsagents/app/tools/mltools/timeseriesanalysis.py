import pandas as pd
import numpy as np
from typing import List, Union, Optional, Callable, Dict, Tuple, Any
from scipy import stats
from .base_pipe import BasePipe


class TimeSeriesPipe(BasePipe):
    """
    A pipeline-style class for time series operations using the pipe pattern.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for time series analysis"""
        # Store distribution results when calculating distributions
        self.distribution_results = {}
        # Store statistical test results
        self.test_results = {}
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'distribution_results'):
            self.distribution_results = source_pipe.distribution_results.copy()
        if hasattr(source_pipe, 'test_results'):
            self.test_results = source_pipe.test_results.copy()
    
    def _has_results(self) -> bool:
        """Check if the pipeline has any results to merge"""
        return len(self.distribution_results) > 0 or len(self.test_results) > 0
    
    def merge_to_df(self, base_df: pd.DataFrame, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
        """
        Merge time series analysis results into the base dataframe as new columns
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge results into
        include_metadata : bool, default=False
            Whether to include metadata columns
        **kwargs : dict
            Additional arguments
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with time series analysis results merged as new columns
        """
        if not self._has_results():
            return base_df
        
        result_df = base_df.copy()
        
        # Merge distribution results
        for dist_name, dist_data in self.distribution_results.items():
            if isinstance(dist_data, dict):
                for component, series in dist_data.items():
                    if hasattr(series, 'values') and len(series) == len(result_df):
                        result_df[f"{component}_{dist_name}"] = series.values
        
        # Merge test results
        for test_name, test_data in self.test_results.items():
            if isinstance(test_data, dict):
                for metric, value in test_data.items():
                    if include_metadata:
                        result_df[f"test_{test_name}_{metric}"] = value
        
        return result_df
    
    def to_df(self, include_metadata: bool = False, include_original: bool = True):
        """
        Convert the time series analysis results to a DataFrame
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns in the output DataFrame
        include_original : bool, default=True
            Whether to include original data columns in the output DataFrame
            
        Returns:
        --------
        pd.DataFrame
            DataFrame representation of the time series analysis results
            
        Raises:
        -------
        ValueError
            If no data is available
            
        Examples:
        --------
        >>> # Basic time series operations
        >>> pipe = (TimeSeriesPipe.from_dataframe(df)
        ...         | lag('value', 1)
        ...         | variance_analysis('value', 'rolling', 5))
        >>> results_df = pipe.to_df()
        >>> print(results_df.head())
        
        >>> # With metadata
        >>> results_df = pipe.to_df(include_metadata=True)
        >>> print(results_df.columns)
        
        >>> # Only time series columns (no original data)
        >>> ts_df = pipe.to_df(include_original=False)
        >>> print(ts_df.columns)
        """
        if self.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        # Get the result DataFrame (contains original data + time series analysis results)
        result_df = self.data.copy()
        
        # Ensure we always return a DataFrame, even if empty
        if result_df is None:
            result_df = pd.DataFrame()
        
        # Filter columns based on parameters
        columns_to_include = []
        
        if include_original:
            # Include original columns (those that don't have time series suffixes)
            original_cols = [col for col in result_df.columns 
                           if not any(suffix in col for suffix in ['_lead', '_lag', '_var', '_std', '_cdf', '_rolling_'])]
            columns_to_include.extend(original_cols)
        
        # Include time series analysis columns
        ts_cols = [col for col in result_df.columns 
                  if any(suffix in col for suffix in ['_lead', '_lag', '_var', '_std', '_cdf', '_rolling_'])]
        columns_to_include.extend(ts_cols)
        
        # Create the output DataFrame
        output_df = result_df[columns_to_include].copy()
        
        # Add metadata if requested
        if include_metadata and not output_df.empty:
            # Add information about available analyses
            if self.distribution_results:
                output_df['has_distribution_analysis'] = True
                output_df['distribution_columns'] = ', '.join(self.distribution_results.keys())
            else:
                output_df['has_distribution_analysis'] = False
                output_df['distribution_columns'] = ''
            
            if self.test_results:
                output_df['has_test_results'] = True
                output_df['test_results'] = str(list(self.test_results.keys()))
            else:
                output_df['has_test_results'] = False
                output_df['test_results'] = ''
        
        return output_df
    
    def get_timeseries_columns(self):
        """
        Get the column names that were created by the time series analysis
        
        Returns:
        --------
        List[str]
            List of column names created by the time series analysis
        """
        if self.data is None:
            return []
        
        # Get time series analysis columns
        ts_cols = [col for col in self.data.columns 
                  if any(suffix in col for suffix in ['_lead', '_lag', '_var', '_std', '_cdf', '_rolling_'])]
        
        return ts_cols
    
    def get_timeseries_summary_df(self, include_metadata: bool = False):
        """
        Get a summary DataFrame of all time series analyses
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns
            
        Returns:
        --------
        pd.DataFrame
            Summary DataFrame with time series analysis statistics
        """
        if self.data is None:
            return pd.DataFrame()
        
        summary_data = []
        
        # Analyze time series columns
        ts_cols = self.get_timeseries_columns()
        
        for col in ts_cols:
            # Determine analysis type based on suffix
            if '_lead' in col:
                analysis_type = 'lead'
                base_col = col.replace('_lead', '')
            elif '_lag' in col:
                analysis_type = 'lag'
                base_col = col.replace('_lag', '')
            elif '_var' in col:
                analysis_type = 'variance'
                base_col = col.replace('_var', '')
            elif '_std' in col:
                analysis_type = 'standard_deviation'
                base_col = col.replace('_std', '')
            elif '_cdf' in col:
                analysis_type = 'cumulative_distribution'
                base_col = col.replace('_cdf', '')
            elif '_rolling_' in col:
                analysis_type = 'rolling_window'
                base_col = col.split('_rolling_')[0]
            else:
                analysis_type = 'unknown'
                base_col = col
            
            summary_row = {
                'column': col,
                'base_column': base_col,
                'analysis_type': analysis_type
            }
            
            # Add column statistics
            if col in self.data.columns:
                col_data = self.data[col].dropna()
                summary_row['non_null_count'] = len(col_data)
                summary_row['null_count'] = self.data[col].isnull().sum()
                summary_row['null_percentage'] = (summary_row['null_count'] / len(self.data)) * 100 if len(self.data) > 0 else 0
                
                if len(col_data) > 0:
                    summary_row['mean'] = col_data.mean()
                    summary_row['std'] = col_data.std()
                    summary_row['min'] = col_data.min()
                    summary_row['max'] = col_data.max()
                else:
                    summary_row['mean'] = np.nan
                    summary_row['std'] = np.nan
                    summary_row['min'] = np.nan
                    summary_row['max'] = np.nan
            else:
                # Handle case where column doesn't exist
                summary_row['non_null_count'] = 0
                summary_row['null_count'] = 0
                summary_row['null_percentage'] = 0
                summary_row['mean'] = np.nan
                summary_row['std'] = np.nan
                summary_row['min'] = np.nan
                summary_row['max'] = np.nan
            
            # Add metadata if requested
            if include_metadata and col in self.data.columns:
                summary_row['dtype'] = str(self.data[col].dtype)
                summary_row['unique_values'] = self.data[col].nunique()
            elif include_metadata:
                summary_row['dtype'] = 'unknown'
                summary_row['unique_values'] = 0
            
            summary_data.append(summary_row)
        
        return pd.DataFrame(summary_data)
    
    def get_analysis_by_type(self, analysis_type: str):
        """
        Get all columns of a specific analysis type
        
        Parameters:
        -----------
        analysis_type : str
            Type of analysis to retrieve ('lead', 'lag', 'variance', 'standard_deviation', 'cumulative_distribution', 'rolling_window')
            
        Returns:
        --------
        List[str]
            List of column names of the specified analysis type
        """
        ts_cols = self.get_timeseries_columns()
        
        if analysis_type == 'lead':
            return [col for col in ts_cols if '_lead' in col]
        elif analysis_type == 'lag':
            return [col for col in ts_cols if '_lag' in col]
        elif analysis_type == 'variance':
            return [col for col in ts_cols if '_var' in col]
        elif analysis_type == 'standard_deviation':
            return [col for col in ts_cols if '_std' in col]
        elif analysis_type == 'cumulative_distribution':
            return [col for col in ts_cols if '_cdf' in col]
        elif analysis_type == 'rolling_window':
            return [col for col in ts_cols if '_rolling_' in col]
        else:
            return []
    
    def get_distribution_results(self):
        """
        Get the distribution analysis results
        
        Returns:
        --------
        Dict
            The distribution results dictionary, or empty dict if no distribution analysis performed
        """
        return self.distribution_results.copy() if self.distribution_results else {}
    
    def get_test_results(self):
        """
        Get the statistical test results
        
        Returns:
        --------
        Dict
            The test results dictionary, or empty dict if no tests performed
        """
        return self.test_results.copy() if self.test_results else {}
    
    def get_original_data(self):
        """
        Get the original data DataFrame
        
        Returns:
        --------
        pd.DataFrame
            The original data DataFrame, or empty DataFrame if no data was provided
        """
        return self.data.copy() if self.data is not None else pd.DataFrame()
    
    def get_distribution_summary_df(self, include_metadata: bool = False):
        """
        Get a summary DataFrame of distribution analysis results
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns
            
        Returns:
        --------
        pd.DataFrame
            Summary DataFrame with distribution analysis statistics
        """
        if not self.distribution_results:
            return pd.DataFrame()
        
        summary_data = []
        
        for col, dist_result in self.distribution_results.items():
            if isinstance(dist_result, dict) and 'stats' in dist_result:
                # Single distribution (no grouping)
                stats = dist_result['stats']
                summary_row = {
                    'column': col,
                    'group': 'overall',
                    'count': stats.get('count', np.nan),
                    'mean': stats.get('mean', np.nan),
                    'std': stats.get('std', np.nan),
                    'min': stats.get('min', np.nan),
                    'median': stats.get('median', np.nan),
                    'max': stats.get('max', np.nan)
                }
                
                if include_metadata:
                    summary_row['has_histogram'] = 'histogram' in dist_result
                    summary_row['has_bin_edges'] = 'bin_edges' in dist_result
                
                summary_data.append(summary_row)
            elif isinstance(dist_result, dict):
                # Multiple distributions (with grouping)
                for group, results in dist_result.items():
                    if isinstance(results, dict) and 'stats' in results:
                        stats = results['stats']
                        summary_row = {
                            'column': col,
                            'group': group,
                            'count': stats.get('count', np.nan),
                            'mean': stats.get('mean', np.nan),
                            'std': stats.get('std', np.nan),
                            'min': stats.get('min', np.nan),
                            'median': stats.get('median', np.nan),
                            'max': stats.get('max', np.nan)
                        }
                        
                        if include_metadata:
                            summary_row['has_histogram'] = 'histogram' in results
                            summary_row['has_bin_edges'] = 'bin_edges' in results
                        
                        summary_data.append(summary_row)
        
        return pd.DataFrame(summary_data)
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the time series analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in time series pipe)
            
        Returns:
        --------
        dict
            Summary of the time series analysis results
        """
        if not self.distribution_results and not self.test_results:
            return {"error": "No time series analysis has been performed"}
        
        # Get summary DataFrames
        ts_summary_df = self.get_timeseries_summary_df()
        dist_summary_df = self.get_distribution_summary_df()
        
        # Get time series columns
        ts_cols = self.get_timeseries_columns()
        
        # Count analyses by type
        analysis_types = {
            'distributions': len(self.distribution_results),
            'statistical_tests': len(self.test_results)
        }
        
        # Safely get distribution results info
        distribution_results_info = {}
        for col, result in self.distribution_results.items():
            if isinstance(result, dict):
                distribution_results_info[col] = {
                    "type": "distribution", 
                    "has_stats": 'stats' in result
                }
        
        # Safely get test results info
        test_results_info = {}
        for name in self.test_results.keys():
            test_results_info[name] = {"type": "statistical_test"}
        
        return {
            "total_analyses": sum(analysis_types.values()),
            "total_timeseries_columns": len(ts_cols),
            "available_distributions": list(self.distribution_results.keys()),
            "available_tests": list(self.test_results.keys()),
            "timeseries_columns": ts_cols,
            "analysis_types": analysis_types,
            "timeseries_summary_dataframe": ts_summary_df.to_dict('records') if not ts_summary_df.empty else [],
            "distribution_summary_dataframe": dist_summary_df.to_dict('records') if not dist_summary_df.empty else [],
            "distribution_results_info": distribution_results_info,
            "test_results_info": test_results_info
        }


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
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
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
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
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
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
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
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
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
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
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
            elif isinstance(dist_results, dict):
                # Multiple distributions (with grouping)
                group_stats = {}
                for group, results in dist_results.items():
                    if isinstance(results, dict) and 'stats' in results:
                        group_stats[group] = results['stats']
                
                if group_stats:
                    summaries[col] = pd.DataFrame(group_stats).T
                else:
                    # Return empty DataFrame if no valid stats found
                    summaries[col] = pd.DataFrame()
            else:
                # Return empty DataFrame for invalid results
                summaries[col] = pd.DataFrame()
        
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
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
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
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
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
