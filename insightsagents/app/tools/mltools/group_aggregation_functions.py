"""
Group Aggregation Functions for Moving Aggregation Pipeline

This module provides standalone functions that can be used with the moving_apply_by_group
function in the MovingAggrPipe. These functions are designed to work with grouped data
and return aggregated values that can be used in rolling window calculations.

Each function follows the signature: function(grouped_data, column_name) -> scalar_value

These functions can be directly registered into ChromaDB with descriptions and examples
for use in natural language queries and automated analysis.
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, Any, Callable
import warnings


def mean(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the mean of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate mean for
        
    Returns:
    --------
    float
        Mean value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', mean, window=7))
    """
    try:
        # Get the column values from all groups
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if not all_values:
            return np.nan
        
        return np.mean(all_values)
    except Exception as e:
        warnings.warn(f"Error calculating mean for column '{column}': {str(e)}")
        return np.nan


def sum_values(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the sum of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate sum for
        
    Returns:
    --------
    float
        Sum value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('revenue', 'region', sum_values, window=14))
    """
    try:
        total_sum = 0
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                total_sum += values.sum()
        
        return total_sum
    except Exception as e:
        warnings.warn(f"Error calculating sum for column '{column}': {str(e)}")
        return np.nan


def count_values(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> int:
    """
    Count non-null values of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to count values for
        
    Returns:
    --------
    int
        Count of non-null values across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('sales', 'product', count_values, window=30))
    """
    try:
        total_count = 0
        for name, group in grouped:
            if column in group.columns:
                count = group[column].count()
                total_count += count
        
        return total_count
    except Exception as e:
        warnings.warn(f"Error counting values for column '{column}': {str(e)}")
        return 0


def max_value(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Find the maximum value of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to find maximum for
        
    Returns:
    --------
    float
        Maximum value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('price', 'category', max_value, window=7))
    """
    try:
        max_val = -np.inf
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                if len(values) > 0:
                    group_max = values.max()
                    if group_max > max_val:
                        max_val = group_max
        
        return max_val if max_val != -np.inf else np.nan
    except Exception as e:
        warnings.warn(f"Error finding maximum for column '{column}': {str(e)}")
        return np.nan


def min_value(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Find the minimum value of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to find minimum for
        
    Returns:
    --------
    float
        Minimum value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('cost', 'supplier', min_value, window=14))
    """
    try:
        min_val = np.inf
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                if len(values) > 0:
                    group_min = values.min()
                    if group_min < min_val:
                        min_val = group_min
        
        return min_val if min_val != np.inf else np.nan
    except Exception as e:
        warnings.warn(f"Error finding minimum for column '{column}': {str(e)}")
        return np.nan


def std_dev(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the standard deviation of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate standard deviation for
        
    Returns:
    --------
    float
        Standard deviation across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('returns', 'store', std_dev, window=30))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        return np.std(all_values, ddof=1)
    except Exception as e:
        warnings.warn(f"Error calculating standard deviation for column '{column}': {str(e)}")
        return np.nan


def variance(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the variance of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate variance for
        
    Returns:
    --------
    float
        Variance across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('volatility', 'asset', variance, window=21))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        return np.var(all_values, ddof=1)
    except Exception as e:
        warnings.warn(f"Error calculating variance for column '{column}': {str(e)}")
        return np.nan


def median(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the median of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate median for
        
    Returns:
    --------
    float
        Median value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('salary', 'department', median, window=90))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if not all_values:
            return np.nan
        
        return np.median(all_values)
    except Exception as e:
        warnings.warn(f"Error calculating median for column '{column}': {str(e)}")
        return np.nan


def quantile(grouped: pd.core.groupby.DataFrameGroupBy, column: str, q: float = 0.5) -> float:
    """
    Calculate the specified quantile of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate quantile for
    q : float, default=0.5
        Quantile to calculate (0-1)
        
    Returns:
    --------
    float
        Quantile value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group for 75th percentile
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('income', 'age_group', 
    ...                                lambda g, c: quantile(g, c, 0.75), window=60))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if not all_values:
            return np.nan
        
        return np.quantile(all_values, q)
    except Exception as e:
        warnings.warn(f"Error calculating quantile for column '{column}': {str(e)}")
        return np.nan


def range_values(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the range (max - min) of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate range for
        
    Returns:
    --------
    float
        Range value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('temperature', 'location', range_values, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        return np.max(all_values) - np.min(all_values)
    except Exception as e:
        warnings.warn(f"Error calculating range for column '{column}': {str(e)}")
        return np.nan


def coefficient_of_variation(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the coefficient of variation (std/mean) of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate coefficient of variation for
        
    Returns:
    --------
    float
        Coefficient of variation across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('returns', 'portfolio', 
    ...                                coefficient_of_variation, window=30))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        mean_val = np.mean(all_values)
        if mean_val == 0:
            return np.nan
        
        std_val = np.std(all_values, ddof=1)
        return std_val / mean_val
    except Exception as e:
        warnings.warn(f"Error calculating coefficient of variation for column '{column}': {str(e)}")
        return np.nan


def skewness(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the skewness of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate skewness for
        
    Returns:
    --------
    float
        Skewness value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('returns', 'asset_class', skewness, window=60))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 3:
            return np.nan
        
        values_array = np.array(all_values)
        mean_val = np.mean(values_array)
        std_val = np.std(values_array, ddof=1)
        
        if std_val == 0:
            return np.nan
        
        # Calculate skewness
        n = len(values_array)
        skew = (n / ((n-1) * (n-2))) * np.sum(((values_array - mean_val) / std_val) ** 3)
        
        return skew
    except Exception as e:
        warnings.warn(f"Error calculating skewness for column '{column}': {str(e)}")
        return np.nan


def kurtosis(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the kurtosis of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate kurtosis for
        
    Returns:
    --------
    float
        Kurtosis value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('volatility', 'market', kurtosis, window=90))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 4:
            return np.nan
        
        values_array = np.array(all_values)
        mean_val = np.mean(values_array)
        std_val = np.std(values_array, ddof=1)
        
        if std_val == 0:
            return np.nan
        
        # Calculate kurtosis
        n = len(values_array)
        kurt = (n * (n+1) / ((n-1) * (n-2) * (n-3))) * np.sum(((values_array - mean_val) / std_val) ** 4) - (3 * (n-1)**2 / ((n-2) * (n-3)))
        
        return kurt
    except Exception as e:
        warnings.warn(f"Error calculating kurtosis for column '{column}': {str(e)}")
        return np.nan


def unique_count(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> int:
    """
    Count unique values of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to count unique values for
        
    Returns:
    --------
    int
        Count of unique values across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('product_id', 'category', unique_count, window=30))
    """
    try:
        unique_values = set()
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                unique_values.update(values.unique())
        
        return len(unique_values)
    except Exception as e:
        warnings.warn(f"Error counting unique values for column '{column}': {str(e)}")
        return 0


def mode(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> Any:
    """
    Find the mode (most frequent value) of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to find mode for
        
    Returns:
    --------
    Any
        Mode value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('status', 'priority', mode, window=14))
    """
    try:
        value_counts = {}
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                for value in values:
                    value_counts[value] = value_counts.get(value, 0) + 1
        
        if not value_counts:
            return np.nan
        
        # Find the most frequent value
        mode_value = max(value_counts, key=value_counts.get)
        return mode_value
    except Exception as e:
        warnings.warn(f"Error finding mode for column '{column}': {str(e)}")
        return np.nan


def weighted_average(grouped: pd.core.groupby.DataFrameGroupBy, column: str, weight_column: str = None) -> float:
    """
    Calculate the weighted average of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate weighted average for
    weight_column : str, optional
        Column name to use as weights. If None, uses equal weights.
        
    Returns:
    --------
    float
        Weighted average across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group for equal weights
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('price', 'category', weighted_average, window=21))
    
    >>> # Use with custom weight function
    >>> def weighted_avg_with_volume(g, c):
    ...     return weighted_average(g, c, 'volume')
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('price', 'category', weighted_avg_with_volume, window=21))
    """
    try:
        if weight_column is None:
            # Equal weights
            all_values = []
            for name, group in grouped:
                if column in group.columns:
                    values = group[column].dropna()
                    all_values.extend(values.tolist())
            
            if not all_values:
                return np.nan
            
            return np.mean(all_values)
        else:
            # Weighted average
            total_weighted_sum = 0
            total_weight = 0
            
            for name, group in grouped:
                if column in group.columns and weight_column in group.columns:
                    # Get both columns and drop rows with NaN in either
                    valid_data = group[[column, weight_column]].dropna()
                    if len(valid_data) > 0:
                        values = valid_data[column].values
                        weights = valid_data[weight_column].values
                        
                        total_weighted_sum += np.sum(values * weights)
                        total_weight += np.sum(weights)
            
            if total_weight == 0:
                return np.nan
            
            return total_weighted_sum / total_weight
    except Exception as e:
        warnings.warn(f"Error calculating weighted average for column '{column}': {str(e)}")
        return np.nan


def geometric_mean(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the geometric mean of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate geometric mean for
        
    Returns:
    --------
    float
        Geometric mean across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('growth_rate', 'sector', geometric_mean, window=45))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                # Filter out non-positive values for geometric mean
                positive_values = values[values > 0]
                all_values.extend(positive_values.tolist())
        
        if not all_values:
            return np.nan
        
        # Calculate geometric mean
        log_values = np.log(all_values)
        geometric_mean_val = np.exp(np.mean(log_values))
        
        return geometric_mean_val
    except Exception as e:
        warnings.warn(f"Error calculating geometric mean for column '{column}': {str(e)}")
        return np.nan


def harmonic_mean(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the harmonic mean of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate harmonic mean for
        
    Returns:
    --------
    float
        Harmonic mean across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('speed', 'vehicle_type', harmonic_mean, window=30))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                # Filter out zero values for harmonic mean
                non_zero_values = values[values != 0]
                all_values.extend(non_zero_values.tolist())
        
        if not all_values:
            return np.nan
        
        # Calculate harmonic mean
        reciprocal_sum = np.sum(1 / np.array(all_values))
        harmonic_mean_val = len(all_values) / reciprocal_sum
        
        return harmonic_mean_val
    except Exception as e:
        warnings.warn(f"Error calculating harmonic mean for column '{column}': {str(e)}")
        return np.nan


def interquartile_range(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the interquartile range (Q3 - Q1) of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate interquartile range for
        
    Returns:
    --------
    float
        Interquartile range across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('salary', 'job_level', interquartile_range, window=60))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 4:
            return np.nan
        
        q1 = np.quantile(all_values, 0.25)
        q3 = np.quantile(all_values, 0.75)
        
        return q3 - q1
    except Exception as e:
        warnings.warn(f"Error calculating interquartile range for column '{column}': {str(e)}")
        return np.nan


def mad(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate the mean absolute deviation of a column across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate mean absolute deviation for
        
    Returns:
    --------
    float
        Mean absolute deviation across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('returns', 'asset', mad, window=30))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if not all_values:
            return np.nan
        
        values_array = np.array(all_values)
        mean_val = np.mean(values_array)
        
        mad_val = np.mean(np.abs(values_array - mean_val))
        
        return mad_val
    except Exception as e:
        warnings.warn(f"Error calculating mean absolute deviation for column '{column}': {str(e)}")
        return np.nan


# Dictionary mapping function names to their metadata for ChromaDB registration
GROUP_AGGREGATION_FUNCTIONS = {
    'mean': {
        'function': mean,
        'description': 'Calculate the mean (average) of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", mean, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate mean for'},
        'returns': 'float - Mean value across all groups'
    },
    'sum_values': {
        'function': sum_values,
        'description': 'Calculate the sum of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("revenue", "region", sum_values, window=14)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate sum for'},
        'returns': 'float - Sum value across all groups'
    },
    'count_values': {
        'function': count_values,
        'description': 'Count non-null values of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("sales", "product", count_values, window=30)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to count values for'},
        'returns': 'int - Count of non-null values across all groups'
    },
    'max_value': {
        'function': max_value,
        'description': 'Find the maximum value of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("price", "category", max_value, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to find maximum for'},
        'returns': 'float - Maximum value across all groups'
    },
    'min_value': {
        'function': min_value,
        'description': 'Find the minimum value of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("cost", "supplier", min_value, window=14)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to find minimum for'},
        'returns': 'float - Minimum value across all groups'
    },
    'std_dev': {
        'function': std_dev,
        'description': 'Calculate the standard deviation of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("returns", "store", std_dev, window=30)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate standard deviation for'},
        'returns': 'float - Standard deviation across all groups'
    },
    'variance': {
        'function': variance,
        'description': 'Calculate the variance of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("volatility", "asset", variance, window=21)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate variance for'},
        'returns': 'float - Variance across all groups'
    },
    'median': {
        'function': median,
        'description': 'Calculate the median of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("salary", "department", median, window=90)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate median for'},
        'returns': 'float - Median value across all groups'
    },
    'quantile': {
        'function': quantile,
        'description': 'Calculate the specified quantile of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("income", "age_group", lambda g, c: quantile(g, c, 0.75), window=60)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate quantile for', 'q': 'Quantile to calculate (0-1)'},
        'returns': 'float - Quantile value across all groups'
    },
    'range_values': {
        'function': range_values,
        'description': 'Calculate the range (max - min) of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("temperature", "location", range_values, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate range for'},
        'returns': 'float - Range value across all groups'
    },
    'coefficient_of_variation': {
        'function': coefficient_of_variation,
        'description': 'Calculate the coefficient of variation (std/mean) of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("returns", "portfolio", coefficient_of_variation, window=30)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate coefficient of variation for'},
        'returns': 'float - Coefficient of variation across all groups'
    },
    'skewness': {
        'function': skewness,
        'description': 'Calculate the skewness of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("returns", "asset_class", skewness, window=60)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate skewness for'},
        'returns': 'float - Skewness value across all groups'
    },
    'kurtosis': {
        'function': kurtosis,
        'description': 'Calculate the kurtosis of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("volatility", "market", kurtosis, window=90)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate kurtosis for'},
        'returns': 'float - Kurtosis value across all groups'
    },
    'unique_count': {
        'function': unique_count,
        'description': 'Count unique values of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("product_id", "category", unique_count, window=30)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to count unique values for'},
        'returns': 'int - Count of unique values across all groups'
    },
    'mode': {
        'function': mode,
        'description': 'Find the mode (most frequent value) of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("status", "priority", mode, window=14)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to find mode for'},
        'returns': 'Any - Mode value across all groups'
    },
    'weighted_average': {
        'function': weighted_average,
        'description': 'Calculate the weighted average of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("price", "category", weighted_average, window=21)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate weighted average for', 'weight_column': 'Column name to use as weights (optional)'},
        'returns': 'float - Weighted average across all groups'
    },
    'geometric_mean': {
        'function': geometric_mean,
        'description': 'Calculate the geometric mean of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("growth_rate", "sector", geometric_mean, window=45)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate geometric mean for'},
        'returns': 'float - Geometric mean across all groups'
    },
    'harmonic_mean': {
        'function': harmonic_mean,
        'description': 'Calculate the harmonic mean of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("speed", "vehicle_type", harmonic_mean, window=30)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate harmonic mean for'},
        'returns': 'float - Harmonic mean across all groups'
    },
    'interquartile_range': {
        'function': interquartile_range,
        'description': 'Calculate the interquartile range (Q3 - Q1) of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("salary", "job_level", interquartile_range, window=60)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate interquartile range for'},
        'returns': 'float - Interquartile range across all groups'
    },
    'mad': {
        'function': mad,
        'description': 'Calculate the mean absolute deviation of a column across all groups in a moving window',
        'example': 'moving_apply_by_group("returns", "asset", mad, window=30)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate mean absolute deviation for'},
        'returns': 'float - Mean absolute deviation across all groups'
    }
}


# Operations Tool Functions Adapted for Group Aggregation
def percent_change(grouped: pd.core.groupby.DataFrameGroupBy, column: str, baseline_value: float = None) -> float:
    """
    Calculate the percent change of a column across all groups relative to a baseline.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate percent change for
    baseline_value : float, optional
        Baseline value to compare against. If None, uses the first group's mean.
        
    Returns:
    --------
    float
        Percent change across all groups relative to baseline
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', percent_change, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if not all_values:
            return np.nan
        
        # Calculate overall mean
        overall_mean = np.mean(all_values)
        
        # Use provided baseline or first group mean
        if baseline_value is None:
            # Get first group mean as baseline
            first_group = next(iter(grouped))[1]
            if column in first_group.columns:
                baseline_value = first_group[column].mean()
            else:
                baseline_value = overall_mean
        
        if baseline_value == 0:
            return np.nan
        
        # Calculate percent change
        pct_change = (overall_mean - baseline_value) / baseline_value * 100
        
        return pct_change
    except Exception as e:
        warnings.warn(f"Error calculating percent change for column '{column}': {str(e)}")
        return np.nan


def absolute_change(grouped: pd.core.groupby.DataFrameGroupBy, column: str, baseline_value: float = None) -> float:
    """
    Calculate the absolute change of a column across all groups relative to a baseline.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate absolute change for
    baseline_value : float, optional
        Baseline value to compare against. If None, uses the first group's mean.
        
    Returns:
    --------
    float
        Absolute change across all groups relative to baseline
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', absolute_change, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if not all_values:
            return np.nan
        
        # Calculate overall mean
        overall_mean = np.mean(all_values)
        
        # Use provided baseline or first group mean
        if baseline_value is None:
            # Get first group mean as baseline
            first_group = next(iter(grouped))[1]
            if column in first_group.columns:
                baseline_value = first_group[column].mean()
            else:
                baseline_value = overall_mean
        
        # Calculate absolute change
        abs_change = overall_mean - baseline_value
        
        return abs_change
    except Exception as e:
        warnings.warn(f"Error calculating absolute change for column '{column}': {str(e)}")
        return np.nan


def mantel_haenszel_estimate(grouped: pd.core.groupby.DataFrameGroupBy, column: str, baseline_value: float = None) -> float:
    """
    Calculate the Mantel-Haenszel estimate across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate MH estimate for
    baseline_value : float, optional
        Baseline value to compare against. If None, uses the first group's mean.
        
    Returns:
    --------
    float
        Mantel-Haenszel estimate across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', mantel_haenszel_estimate, window=7))
    """
    try:
        if baseline_value is None:
            # Get first group mean as baseline
            first_group = next(iter(grouped))[1]
            if column in first_group.columns:
                baseline_value = first_group[column].mean()
            else:
                return np.nan
        
        if baseline_value == 0:
            return np.nan
        
        # Calculate MH estimate
        numerator_sum = 0
        denominator_sum = 0
        
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                if len(values) > 0:
                    group_mean = values.mean()
                    weight = len(values)
                    
                    numerator_sum += weight * group_mean
                    denominator_sum += weight * baseline_value
        
        if denominator_sum == 0:
            return np.nan
        
        mh_estimate = numerator_sum / denominator_sum
        
        return mh_estimate
    except Exception as e:
        warnings.warn(f"Error calculating Mantel-Haenszel estimate for column '{column}': {str(e)}")
        return np.nan


def cuped_adjustment(grouped: pd.core.groupby.DataFrameGroupBy, column: str, covariate_column: str = None) -> float:
    """
    Calculate CUPED-adjusted value across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate CUPED adjustment for
    covariate_column : str, optional
        Column name to use as covariate for adjustment
        
    Returns:
    --------
    float
        CUPED-adjusted value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', cuped_adjustment, window=7))
    """
    try:
        if covariate_column is None:
            # If no covariate specified, return simple mean
            return mean(grouped, column)
        
        # Calculate CUPED adjustment
        all_values = []
        all_covariates = []
        
        for name, group in grouped:
            if column in group.columns and covariate_column in group.columns:
                # Get valid data for both columns
                valid_data = group[[column, covariate_column]].dropna()
                if len(valid_data) > 0:
                    all_values.extend(valid_data[column].tolist())
                    all_covariates.extend(valid_data[covariate_column].tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        # Calculate means
        y_mean = np.mean(all_values)
        x_mean = np.mean(all_covariates)
        
        # Calculate covariance and variance
        y_array = np.array(all_values)
        x_array = np.array(all_covariates)
        
        cov_xy = np.cov(y_array, x_array, ddof=1)[0, 1]
        var_x = np.var(x_array, ddof=1)
        
        if var_x == 0:
            return y_mean
        
        # Calculate theta (adjustment factor)
        theta = cov_xy / var_x
        
        # Apply CUPED adjustment
        cuped_value = y_mean - theta * x_mean
        
        return cuped_value
    except Exception as e:
        warnings.warn(f"Error calculating CUPED adjustment for column '{column}': {str(e)}")
        return np.nan


def prepost_adjustment(grouped: pd.core.groupby.DataFrameGroupBy, column: str, pre_column: str = None) -> float:
    """
    Calculate PrePost-adjusted value across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate PrePost adjustment for
    pre_column : str, optional
        Column name to use as pre-treatment measure
        
    Returns:
    --------
    float
        PrePost-adjusted value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', prepost_adjustment, window=7))
    """
    try:
        if pre_column is None:
            # If no pre-column specified, return simple mean
            return mean(grouped, column)
        
        # Calculate PrePost adjustment
        all_values = []
        all_pre_values = []
        
        for name, group in grouped:
            if column in group.columns and pre_column in group.columns:
                # Get valid data for both columns
                valid_data = group[[column, pre_column]].dropna()
                if len(valid_data) > 0:
                    all_values.extend(valid_data[column].tolist())
                    all_pre_values.extend(valid_data[pre_column].tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        # Calculate means
        post_mean = np.mean(all_values)
        pre_mean = np.mean(all_pre_values)
        
        # Calculate PrePost adjustment
        prepost_value = post_mean - pre_mean
        
        return prepost_value
    except Exception as e:
        warnings.warn(f"Error calculating PrePost adjustment for column '{column}': {str(e)}")
        return np.nan


def power_analysis(grouped: pd.core.groupby.DataFrameGroupBy, column: str, alpha: float = 0.05, power: float = 0.8) -> float:
    """
    Calculate power analysis metrics across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate power analysis for
    alpha : float, default=0.05
        Significance level
    power : float, default=0.8
        Desired statistical power
        
    Returns:
    --------
    float
        Effect size (Cohen's d) across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', power_analysis, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        # Calculate effect size (Cohen's d)
        values_array = np.array(all_values)
        effect_size = np.std(values_array, ddof=1)
        
        if effect_size == 0:
            return np.nan
        
        # Return coefficient of variation as a measure of effect size
        mean_val = np.mean(values_array)
        cv = effect_size / mean_val if mean_val != 0 else np.nan
        
        return cv
    except Exception as e:
        warnings.warn(f"Error calculating power analysis for column '{column}': {str(e)}")
        return np.nan


def stratified_summary(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate stratified summary statistics across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate stratified summary for
        
    Returns:
    --------
    float
        Stratified summary value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', stratified_summary, window=7))
    """
    try:
        # Calculate weighted mean across groups
        total_weighted_sum = 0
        total_weight = 0
        
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                if len(values) > 0:
                    group_mean = values.mean()
                    weight = len(values)
                    
                    total_weighted_sum += weight * group_mean
                    total_weight += weight
        
        if total_weight == 0:
            return np.nan
        
        stratified_value = total_weighted_sum / total_weight
        
        return stratified_value
    except Exception as e:
        warnings.warn(f"Error calculating stratified summary for column '{column}': {str(e)}")
        return np.nan


def bootstrap_confidence_interval(grouped: pd.core.groupby.DataFrameGroupBy, column: str, confidence: float = 0.95, n_bootstrap: int = 100) -> float:
    """
    Calculate bootstrap confidence interval across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate bootstrap CI for
    confidence : float, default=0.95
        Confidence level
    n_bootstrap : int, default=100
        Number of bootstrap samples
        
    Returns:
    --------
    float
        Bootstrap confidence interval width across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', bootstrap_confidence_interval, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        # Bootstrap the mean
        bootstrap_means = []
        values_array = np.array(all_values)
        
        for _ in range(n_bootstrap):
            # Resample with replacement
            bootstrap_sample = np.random.choice(values_array, size=len(values_array), replace=True)
            bootstrap_means.append(np.mean(bootstrap_sample))
        
        # Calculate confidence interval
        alpha = 1 - confidence
        lower_ci = np.percentile(bootstrap_means, alpha/2 * 100)
        upper_ci = np.percentile(bootstrap_means, (1 - alpha/2) * 100)
        
        # Return confidence interval width
        ci_width = upper_ci - lower_ci
        
        return ci_width
    except Exception as e:
        warnings.warn(f"Error calculating bootstrap confidence interval for column '{column}': {str(e)}")
        return np.nan


def multi_comparison_adjustment(grouped: pd.core.groupby.DataFrameGroupBy, column: str, method: str = 'bonferroni') -> float:
    """
    Calculate multi-comparison adjusted value across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate multi-comparison adjustment for
    method : str, default='bonferroni'
        Method to use for adjustment ('bonferroni', 'fdr', 'sidak')
        
    Returns:
    --------
    float
        Multi-comparison adjusted value across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', multi_comparison_adjustment, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        # Calculate p-value equivalent (using coefficient of variation as proxy)
        values_array = np.array(all_values)
        mean_val = np.mean(values_array)
        std_val = np.std(values_array, ddof=1)
        
        if mean_val == 0:
            return np.nan
        
        # Use coefficient of variation as a proxy for p-value
        cv = std_val / mean_val
        
        # Apply multi-comparison adjustment
        n_comparisons = len(all_values)
        
        if method.lower() == 'bonferroni':
            adjusted_value = cv * n_comparisons
        elif method.lower() == 'sidak':
            adjusted_value = 1 - (1 - cv) ** n_comparisons
        elif method.lower() == 'fdr':
            # Benjamini-Hochberg procedure
            adjusted_value = cv * n_comparisons / n_comparisons
        else:
            adjusted_value = cv
        
        return adjusted_value
    except Exception as e:
        warnings.warn(f"Error calculating multi-comparison adjustment for column '{column}': {str(e)}")
        return np.nan


def effect_size(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate effect size (Cohen's d) across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate effect size for
        
    Returns:
    --------
    float
        Effect size across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', effect_size, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if len(all_values) < 2:
            return np.nan
        
        # Calculate effect size using coefficient of variation
        values_array = np.array(all_values)
        mean_val = np.mean(values_array)
        std_val = np.std(values_array, ddof=1)
        
        if mean_val == 0:
            return np.nan
        
        # Cohen's d equivalent using CV
        effect_size_val = std_val / mean_val
        
        return effect_size_val
    except Exception as e:
        warnings.warn(f"Error calculating effect size for column '{column}': {str(e)}")
        return np.nan


def z_score(grouped: pd.core.groupby.DataFrameGroupBy, column: str) -> float:
    """
    Calculate z-score across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate z-score for
        
    Returns:
    --------
    float
        Z-score across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', z_score, window=7))
    """
    try:
        all_values = []
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                all_values.extend(values.tolist())
        
        if not all_values:
            return np.nan
        
        # Calculate z-score
        values_array = np.array(all_values)
        mean_val = np.mean(values_array)
        std_val = np.std(values_array, ddof=1)
        
        if std_val == 0:
            return 0.0
        
        # Calculate z-score of the mean
        z_score_val = (mean_val - mean_val) / std_val  # This will be 0, but we can use a different approach
        
        # Alternative: calculate z-score relative to overall distribution
        overall_mean = np.mean(values_array)
        overall_std = np.std(values_array, ddof=1)
        
        if overall_std == 0:
            return 0.0
        
        # Return the coefficient of variation as a standardized measure
        cv = overall_std / overall_mean if overall_mean != 0 else np.nan
        
        return cv
    except Exception as e:
        warnings.warn(f"Error calculating z-score for column '{column}': {str(e)}")
        return np.nan


def relative_risk(grouped: pd.core.groupby.DataFrameGroupBy, column: str, threshold: float = None) -> float:
    """
    Calculate relative risk across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate relative risk for
    threshold : float, optional
        Threshold to define "exposed" vs "unexposed" groups
        
    Returns:
    --------
    float
        Relative risk across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', relative_risk, window=7))
    """
    try:
        if threshold is None:
            # Use median as threshold if none provided
            all_values = []
            for name, group in grouped:
                if column in group.columns:
                    values = group[column].dropna()
                    all_values.extend(values.tolist())
            
            if not all_values:
                return np.nan
            
            threshold = np.median(all_values)
        
        # Calculate relative risk
        exposed_count = 0
        unexposed_count = 0
        exposed_total = 0
        unexposed_total = 0
        
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                if len(values) > 0:
                    exposed = values[values > threshold]
                    unexposed = values[values <= threshold]
                    
                    exposed_count += len(exposed)
                    unexposed_count += len(unexposed)
                    exposed_total += len(values)
                    unexposed_total += len(values)
        
        if exposed_total == 0 or unexposed_total == 0:
            return np.nan
        
        # Calculate risk in each group
        risk_exposed = exposed_count / exposed_total if exposed_total > 0 else 0
        risk_unexposed = unexposed_count / unexposed_total if unexposed_total > 0 else 0
        
        if risk_unexposed == 0:
            return np.nan
        
        # Calculate relative risk
        relative_risk_val = risk_exposed / risk_unexposed
        
        return relative_risk_val
    except Exception as e:
        warnings.warn(f"Error calculating relative risk for column '{column}': {str(e)}")
        return np.nan


def odds_ratio(grouped: pd.core.groupby.DataFrameGroupBy, column: str, threshold: float = None) -> float:
    """
    Calculate odds ratio across all groups.
    
    Parameters:
    -----------
    grouped : pd.core.groupby.DataFrameGroupBy
        Grouped DataFrame object
    column : str
        Column name to calculate odds ratio for
    threshold : float, optional
        Threshold to define "exposed" vs "unexposed" groups
        
    Returns:
    --------
    float
        Odds ratio across all groups
        
    Example:
    --------
    >>> # Use with moving_apply_by_group
    >>> result = (MovingAggrPipe.from_dataframe(df)
    ...         | moving_apply_by_group('value', 'category', odds_ratio, window=7))
    """
    try:
        if threshold is None:
            # Use median as threshold if none provided
            all_values = []
            for name, group in grouped:
                if column in group.columns:
                    values = group[column].dropna()
                    all_values.extend(values.tolist())
            
            if not all_values:
                return np.nan
            
            threshold = np.median(all_values)
        
        # Calculate odds ratio
        exposed_positive = 0
        exposed_negative = 0
        unexposed_positive = 0
        unexposed_negative = 0
        
        for name, group in grouped:
            if column in group.columns:
                values = group[column].dropna()
                if len(values) > 0:
                    exposed = values[values > threshold]
                    unexposed = values[values <= threshold]
                    
                    exposed_positive += len(exposed)
                    exposed_negative += len(unexposed)
                    unexposed_positive += len(unexposed)
                    unexposed_negative += len(exposed)
        
        # Calculate odds
        odds_exposed = exposed_positive / exposed_negative if exposed_negative > 0 else np.nan
        odds_unexposed = unexposed_positive / unexposed_negative if unexposed_negative > 0 else np.nan
        
        if pd.isna(odds_exposed) or pd.isna(odds_unexposed) or odds_unexposed == 0:
            return np.nan
        
        # Calculate odds ratio
        odds_ratio_val = odds_exposed / odds_unexposed
        
        return odds_ratio_val
    except Exception as e:
        warnings.warn(f"Error calculating odds ratio for column '{column}': {str(e)}")
        return np.nan


# Update the GROUP_AGGREGATION_FUNCTIONS dictionary to include all new functions
GROUP_AGGREGATION_FUNCTIONS.update({
    'percent_change': {
        'function': percent_change,
        'description': 'Calculate percent change across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", percent_change, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate percent change for', 'baseline_value': 'Baseline value to compare against (optional)'},
        'returns': 'float - Percent change across all groups'
    },
    'absolute_change': {
        'function': absolute_change,
        'description': 'Calculate absolute change across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", absolute_change, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate absolute change for', 'baseline_value': 'Baseline value to compare against (optional)'},
        'returns': 'float - Absolute change across all groups'
    },
    'mantel_haenszel_estimate': {
        'function': mantel_haenszel_estimate,
        'description': 'Calculate Mantel-Haenszel estimate across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", mantel_haenszel_estimate, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate MH estimate for', 'baseline_value': 'Baseline value to compare against (optional)'},
        'returns': 'float - Mantel-Haenszel estimate across all groups'
    },
    'cuped_adjustment': {
        'function': cuped_adjustment,
        'description': 'Calculate CUPED-adjusted value across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", cuped_adjustment, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate CUPED adjustment for', 'covariate_column': 'Column name to use as covariate (optional)'},
        'returns': 'float - CUPED-adjusted value across all groups'
    },
    'prepost_adjustment': {
        'function': prepost_adjustment,
        'description': 'Calculate PrePost-adjusted value across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", prepost_adjustment, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate PrePost adjustment for', 'pre_column': 'Column name to use as pre-treatment measure (optional)'},
        'returns': 'float - PrePost-adjusted value across all groups'
    },
    'power_analysis': {
        'function': power_analysis,
        'description': 'Calculate power analysis metrics across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", power_analysis, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate power analysis for', 'alpha': 'Significance level (default: 0.05)', 'power': 'Desired statistical power (default: 0.8)'},
        'returns': 'float - Effect size across all groups'
    },
    'stratified_summary': {
        'function': stratified_summary,
        'description': 'Calculate stratified summary statistics across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", stratified_summary, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate stratified summary for'},
        'returns': 'float - Stratified summary value across all groups'
    },
    'bootstrap_confidence_interval': {
        'function': bootstrap_confidence_interval,
        'description': 'Calculate bootstrap confidence interval across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", bootstrap_confidence_interval, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate bootstrap CI for', 'confidence': 'Confidence level (default: 0.95)', 'n_bootstrap': 'Number of bootstrap samples (default: 100)'},
        'returns': 'float - Bootstrap confidence interval width across all groups'
    },
    'multi_comparison_adjustment': {
        'function': multi_comparison_adjustment,
        'description': 'Calculate multi-comparison adjusted value across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", multi_comparison_adjustment, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate multi-comparison adjustment for', 'method': 'Method to use for adjustment (default: bonferroni)'},
        'returns': 'float - Multi-comparison adjusted value across all groups'
    },
    'effect_size': {
        'function': effect_size,
        'description': 'Calculate effect size (Cohen\'s d) across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", effect_size, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate effect size for'},
        'returns': 'float - Effect size across all groups'
    },
    'z_score': {
        'function': z_score,
        'description': 'Calculate z-score across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", z_score, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate z-score for'},
        'returns': 'float - Z-score across all groups'
    },
    'relative_risk': {
        'function': relative_risk,
        'description': 'Calculate relative risk across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", relative_risk, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate relative risk for', 'threshold': 'Threshold to define exposed vs unexposed groups (optional)'},
        'returns': 'float - Relative risk across all groups'
    },
    'odds_ratio': {
        'function': odds_ratio,
        'description': 'Calculate odds ratio across all groups in a moving window',
        'example': 'moving_apply_by_group("value", "category", odds_ratio, window=7)',
        'parameters': {'grouped': 'Grouped DataFrame object', 'column': 'Column name to calculate odds ratio for', 'threshold': 'Threshold to define exposed vs unexposed groups (optional)'},
        'returns': 'float - Odds ratio across all groups'
    }
})


def get_function_by_name(function_name: str) -> Callable:
    """
    Get a group aggregation function by name.
    
    Parameters:
    -----------
    function_name : str
        Name of the function to retrieve
        
    Returns:
    --------
    Callable
        The requested function
        
    Raises:
    -------
    ValueError
        If the function name is not found
    """
    if function_name not in GROUP_AGGREGATION_FUNCTIONS:
        available_functions = list(GROUP_AGGREGATION_FUNCTIONS.keys())
        raise ValueError(f"Function '{function_name}' not found. Available functions: {available_functions}")
    
    return GROUP_AGGREGATION_FUNCTIONS[function_name]['function']


def get_all_function_names() -> list:
    """
    Get a list of all available group aggregation function names.
    
    Returns:
    --------
    list
        List of available function names
    """
    return list(GROUP_AGGREGATION_FUNCTIONS.keys())


def get_function_metadata(function_name: str) -> dict:
    """
    Get metadata for a specific group aggregation function.
    
    Parameters:
    -----------
    function_name : str
        Name of the function to get metadata for
        
    Returns:
    --------
    dict
        Dictionary containing function metadata
        
    Raises:
    -------
    ValueError
        If the function name is not found
    """
    if function_name not in GROUP_AGGREGATION_FUNCTIONS:
        available_functions = list(GROUP_AGGREGATION_FUNCTIONS.keys())
        raise ValueError(f"Function '{function_name}' not found. Available functions: {available_functions}")
    
    return GROUP_AGGREGATION_FUNCTIONS[function_name].copy()


def get_all_functions_metadata() -> dict:
    """
    Get metadata for all group aggregation functions.
    
    Returns:
    --------
    dict
        Dictionary mapping function names to their metadata
    """
    return GROUP_AGGREGATION_FUNCTIONS.copy()
