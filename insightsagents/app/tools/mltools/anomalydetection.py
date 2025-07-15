"""
Anomaly Detection Tools for Time Series Data

This module provides a pipeline-style anomaly detection toolkit that enables
functional composition for detecting outliers and anomalies in time series data.
The module follows a similar pattern to the cohort, metrics, operations, and time series
analysis tools, providing a consistent interface for data analysis.

Key features:
- Statistical outlier detection (z-score, IQR, etc.)
- Contextual anomaly detection (based on time series patterns)
- Collective anomaly detection (using machine learning methods)
- Seasonal decomposition and residual analysis
- Change point detection
- Forecast-based anomaly detection
- Ensemble methods for combining multiple approaches

Example usage:

```python
import pandas as pd
from anomalydetection import AnomalyPipe, detect_statistical_outliers, detect_contextual_anomalies

# Load data
df = pd.read_csv('time_series_data.csv')

# Create pipeline and detect outliers
anomalies = (
    AnomalyPipe.from_dataframe(df)
    | detect_statistical_outliers(
        columns=['value'],
        method='zscore',
        threshold=3.0
    )
    | detect_contextual_anomalies(
        columns=['value'],
        time_column='timestamp',
        method='residual'
    )
)

# Get results
results = anomalies.data
```
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from scipy import stats
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import acf, pacf
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
import warnings


class AnomalyPipe:
    """
    A pipeline-style anomaly detection tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
        self.anomaly_results = {}
        self.forecasts = {}
        self.current_analysis = None
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe AnomalyPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = AnomalyPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        new_pipe.anomaly_results = self.anomaly_results.copy()
        new_pipe.forecasts = self.forecasts.copy()
        new_pipe.current_analysis = self.current_analysis
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create an AnomalyPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        return pipe


def detect_statistical_outliers(
    columns: Union[str, List[str]],
    method: str = 'zscore',
    threshold: float = 3.0,
    window: Optional[int] = None,
    time_column: Optional[str] = None,
    group_columns: Optional[List[str]] = None
):
    """
    Detect outliers using statistical methods
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze for outliers
    method : str, default='zscore'
        Method to use: 'zscore', 'modified_zscore', 'iqr', or 'percentile'
    threshold : float, default=3.0
        Threshold for determining outliers:
        - For zscore/modified_zscore: number of standard deviations
        - For iqr: multiplier of IQR (values outside Q1-threshold*IQR and Q3+threshold*IQR)
        - For percentile: values below/above percentile thresholds
    window : int, optional
        Window size for rolling outlier detection (if None, use entire series)
    time_column : str, optional
        Time column to sort by before calculations
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
        
    Returns:
    --------
    Callable
        Function that detects outliers in an AnomalyPipe
    """
    def _detect_statistical_outliers(pipe):
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
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Process each column
        for col in cols:
            # Define column names for outlier flags and scores
            outlier_flag_col = f"{col}_outlier_{method}"
            outlier_score_col = f"{col}_score_{method}"
            
            # Initialize result columns
            result_df[outlier_flag_col] = False
            result_df[outlier_score_col] = np.nan
            
            # Process with or without grouping
            if group_columns is not None:
                # Check if group columns exist
                for group_col in group_columns:
                    if group_col not in df.columns:
                        raise ValueError(f"Group column '{group_col}' not found in data")
                
                # Apply outlier detection to each group
                for name, group in df.groupby(group_columns):
                    # Convert to multi-index name if needed
                    if isinstance(name, tuple):
                        group_idx = pd.MultiIndex.from_tuples([name], names=group_columns)
                        idx_match = pd.MultiIndex.from_frame(df[group_columns])
                        group_mask = idx_match.isin(group_idx)
                    else:
                        group_mask = df[group_columns[0]] == name
                    
                    # Detect outliers in this group
                    _process_outliers(
                        result_df, 
                        group[col], 
                        group_mask, 
                        method, 
                        threshold, 
                        window,
                        outlier_flag_col,
                        outlier_score_col
                    )
            else:
                # Apply outlier detection to entire column
                _process_outliers(
                    result_df, 
                    df[col], 
                    slice(None), 
                    method, 
                    threshold, 
                    window,
                    outlier_flag_col,
                    outlier_score_col
                )
        
        # Store results
        analysis_name = f"statistical_outliers_{method}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'statistical_outliers',
            'method': method,
            'threshold': threshold,
            'window': window,
            'columns': cols
        }
        new_pipe.current_analysis = analysis_name
        
        return new_pipe
    
    def _process_outliers(result_df, series, mask, method, threshold, window, flag_col, score_col):
        """Helper function to detect outliers with various methods"""
        # Get values without NaN
        values = series.dropna()
        if len(values) == 0:
            return
        
        if window is None:
        # Apply outlier detection to entire series
            outlier_flags, outlier_scores = _calculate_outliers(values, method, threshold)
            # Map results back to the original indices
            outlier_dict = dict(zip(values.index, outlier_flags))
            score_dict = dict(zip(values.index, outlier_scores))
            
            # Update result dataframe
            for idx in series.index:
                if idx in outlier_dict:
                    # Fix: Handle the case when mask is a slice object
                    if isinstance(mask, slice) and mask.start is None and mask.stop is None:
                        # If mask is slice(None), just use the index directly
                        result_df.loc[result_df.index == idx, flag_col] = outlier_dict[idx]
                        result_df.loc[result_df.index == idx, score_col] = score_dict[idx]
                    else:
                        # Normal case with a boolean mask
                        result_df.loc[mask & (result_df.index == idx), flag_col] = outlier_dict[idx]
                        result_df.loc[mask & (result_df.index == idx), score_col] = score_dict[idx]
        else:
            # Apply rolling outlier detection
            for i in range(len(values) - window + 1):
                if i + window <= len(values):
                    window_series = values.iloc[i:i+window]
                    window_idx = window_series.index[-1]  # Current point is at the end of window
                    
                    # Calculate outliers for the window
                    _, outlier_scores = _calculate_outliers(window_series.iloc[:-1], method, threshold)
                    
                    # Check only the last point in the window
                    last_value = window_series.iloc[-1]
                    
                    if method == 'zscore':
                        window_mean = window_series.iloc[:-1].mean()
                        window_std = window_series.iloc[:-1].std()
                        if window_std == 0:
                            z_score = 0
                        else:
                            z_score = abs((last_value - window_mean) / window_std)
                        is_outlier = z_score > threshold
                        score = z_score
                    
                    elif method == 'modified_zscore':
                        # Modified Z-score uses median and MAD
                        window_median = window_series.iloc[:-1].median()
                        window_mad = np.median(np.abs(window_series.iloc[:-1] - window_median))
                        if window_mad == 0:
                            mod_z_score = 0
                        else:
                            # Constant 0.6745 makes MAD comparable to standard deviation for normal distributions
                            mod_z_score = abs(0.6745 * (last_value - window_median) / window_mad)
                        is_outlier = mod_z_score > threshold
                        score = mod_z_score
                    
                    elif method == 'iqr':
                        q1 = window_series.iloc[:-1].quantile(0.25)
                        q3 = window_series.iloc[:-1].quantile(0.75)
                        iqr = q3 - q1
                        lower_bound = q1 - threshold * iqr
                        upper_bound = q3 + threshold * iqr
                        is_outlier = (last_value < lower_bound) or (last_value > upper_bound)
                        
                        # Calculate score as how many IQRs away from the bounds
                        if last_value < lower_bound:
                            score = abs((last_value - lower_bound) / iqr) + threshold
                        elif last_value > upper_bound:
                            score = abs((last_value - upper_bound) / iqr) + threshold
                        else:
                            score = 0
                    
                    elif method == 'percentile':
                        lower_percentile = threshold / 2
                        upper_percentile = 100 - lower_percentile
                        lower_bound = window_series.iloc[:-1].quantile(lower_percentile / 100)
                        upper_bound = window_series.iloc[:-1].quantile(upper_percentile / 100)
                        is_outlier = (last_value < lower_bound) or (last_value > upper_bound)
                        
                        # Calculate score (0 to 1, where 1 is the most extreme outlier)
                        if is_outlier:
                            min_val = window_series.iloc[:-1].min()
                            max_val = window_series.iloc[:-1].max()
                            range_val = max_val - min_val
                            if range_val == 0:
                                score = 0
                            else:
                                if last_value < lower_bound:
                                    score = abs((last_value - lower_bound) / range_val)
                                else:
                                    score = abs((last_value - upper_bound) / range_val)
                        else:
                            score = 0
                    
                    # Update result dataframe
                    result_df.loc[mask & (result_df.index == window_idx), flag_col] = is_outlier
                    result_df.loc[mask & (result_df.index == window_idx), score_col] = score
    
    def _calculate_outliers(series, method, threshold):
        """Calculate outliers and scores for a series using specified method"""
        outlier_flags = np.zeros(len(series), dtype=bool)
        outlier_scores = np.zeros(len(series))
        
        if method == 'zscore':
            # Z-score method
            mean = series.mean()
            std = series.std()
            
            if std == 0:
                # If standard deviation is zero, no outliers
                return outlier_flags, outlier_scores
            
            z_scores = np.abs((series - mean) / std)
            outlier_flags = z_scores > threshold
            outlier_scores = z_scores
        
        elif method == 'modified_zscore':
            # Modified Z-score method (more robust to outliers)
            median = series.median()
            # Median Absolute Deviation
            mad = np.median(np.abs(series - median))
            
            if mad == 0:
                # If MAD is zero, no outliers
                return outlier_flags, outlier_scores
            
            # Constant 0.6745 makes MAD comparable to standard deviation for normal distributions
            mod_z_scores = 0.6745 * np.abs(series - median) / mad
            outlier_flags = mod_z_scores > threshold
            outlier_scores = mod_z_scores
        
        elif method == 'iqr':
            # Interquartile Range method
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
            
            outlier_flags = (series < lower_bound) | (series > upper_bound)
            
            # Calculate scores as how many IQRs away from the bounds
            outlier_scores = np.zeros(len(series))
            lower_outliers = series < lower_bound
            upper_outliers = series > upper_bound
            
            if iqr == 0:
                # If IQR is zero, score based on distance from median
                median = series.median()
                if np.any(lower_outliers):
                    outlier_scores[lower_outliers] = abs(series[lower_outliers] - median)
                if np.any(upper_outliers):
                    outlier_scores[upper_outliers] = abs(series[upper_outliers] - median)
            else:
                # Score based on distance from bounds in terms of IQR
                if np.any(lower_outliers):
                    outlier_scores[lower_outliers] = (abs(series[lower_outliers] - lower_bound) / iqr) + threshold
                if np.any(upper_outliers):
                    outlier_scores[upper_outliers] = (abs(series[upper_outliers] - upper_bound) / iqr) + threshold
        
        elif method == 'percentile':
            # Percentile method
            lower_percentile = threshold / 2
            upper_percentile = 100 - lower_percentile
            
            lower_bound = series.quantile(lower_percentile / 100)
            upper_bound = series.quantile(upper_percentile / 100)
            
            outlier_flags = (series < lower_bound) | (series > upper_bound)
            
            # Calculate scores (0 to 1, where 1 is the most extreme outlier)
            min_val = series.min()
            max_val = series.max()
            range_val = max_val - min_val
            
            if range_val == 0:
                # If range is zero, no outliers
                return outlier_flags, outlier_scores
            
            # For lower outliers, score based on distance from lower bound
            lower_outliers = series < lower_bound
            if np.any(lower_outliers):
                outlier_scores[lower_outliers] = abs((series[lower_outliers] - lower_bound) / range_val)
            
            # For upper outliers, score based on distance from upper bound
            upper_outliers = series > upper_bound
            if np.any(upper_outliers):
                outlier_scores[upper_outliers] = abs((series[upper_outliers] - upper_bound) / range_val)
        
        else:
            raise ValueError(f"Unknown outlier detection method: {method}")
        
        return outlier_flags, outlier_scores
    
    return _detect_statistical_outliers



def detect_contextual_anomalies(
    columns: Union[str, List[str]],
    time_column: str,
    method: str = 'residual',
    model_type: str = 'ewm',
    threshold: float = 3.0,
    window: int = 30,
    seasonal_period: Optional[int] = None,
    group_columns: Optional[List[str]] = None,
    datetime_format: Optional[str] = None
):
    """
    Detect contextual anomalies by comparing actual values with expected values
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze for anomalies
    time_column : str
        Column containing the time/date information
    method : str, default='residual'
        Method to use: 'residual', 'prediction_interval', 'changepoint'
    model_type : str, default='ewm'
        Model to generate expected values: 'ewm', 'sarimax', 'decomposition'
    threshold : float, default=3.0
        Threshold for determining anomalies (std deviations for residuals, prediction intervals)
    window : int, default=30
        Window size for rolling model fitting
    seasonal_period : int, optional
        Number of periods in a seasonal cycle (if None, will be estimated)
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that detects contextual anomalies in an AnomalyPipe
    """
    def _detect_contextual_anomalies(pipe):
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
                
        # Validate time column
        if time_column not in df.columns:
            raise ValueError(f"Time column '{time_column}' not found in data")
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            if datetime_format:
                df[time_column] = pd.to_datetime(df[time_column], format=datetime_format)
            else:
                df[time_column] = pd.to_datetime(df[time_column])
        
        # Sort by time column
        df = df.sort_values(time_column)
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Process each column
        for col in cols:
            # Define column names for anomaly flags and scores
            anomaly_flag_col = f"{col}_anomaly_{method}"
            anomaly_score_col = f"{col}_score_{method}"
            expected_value_col = f"{col}_expected"
            
            # Initialize result columns
            result_df[anomaly_flag_col] = False
            result_df[anomaly_score_col] = np.nan
            result_df[expected_value_col] = np.nan
            
            # Process with or without grouping
            if group_columns is not None:
                # Check if group columns exist
                for group_col in group_columns:
                    if group_col not in df.columns:
                        raise ValueError(f"Group column '{group_col}' not found in data")
                
                # Apply anomaly detection to each group
                for name, group in df.groupby(group_columns):
                    # Convert to multi-index name if needed
                    if isinstance(name, tuple):
                        group_idx = pd.MultiIndex.from_tuples([name], names=group_columns)
                        idx_match = pd.MultiIndex.from_frame(df[group_columns])
                        group_mask = idx_match.isin(group_idx)
                    else:
                        group_mask = df[group_columns[0]] == name
                    
                    # Detect contextual anomalies in this group
                    _process_contextual_anomalies(
                        result_df, 
                        group[col], 
                        group[time_column],
                        group_mask, 
                        method, 
                        model_type,
                        threshold, 
                        window,
                        seasonal_period,
                        anomaly_flag_col,
                        anomaly_score_col,
                        expected_value_col
                    )
            else:
                # Apply anomaly detection to entire column
                _process_contextual_anomalies(
                    result_df, 
                    df[col], 
                    df[time_column],
                    slice(None), 
                    method, 
                    model_type,
                    threshold, 
                    window,
                    seasonal_period,
                    anomaly_flag_col,
                    anomaly_score_col,
                    expected_value_col
                )
        
        # Store results
        analysis_name = f"contextual_anomalies_{method}_{model_type}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'contextual_anomalies',
            'method': method,
            'model_type': model_type,
            'threshold': threshold,
            'window': window,
            'seasonal_period': seasonal_period,
            'columns': cols
        }
        new_pipe.current_analysis = analysis_name
        
        return new_pipe
    
    def _process_contextual_anomalies(result_df, series, time_series, mask, method, model_type,
                                      threshold, window, seasonal_period, flag_col, score_col, expected_col):
        """Helper function to detect contextual anomalies"""
        # Get values without NaN
        values = series.dropna()
        times = time_series.loc[values.index]
        
        if len(values) < window:
            warnings.warn(f"Not enough data for contextual anomaly detection. Need at least {window} points.")
            return
        
        # Determine seasonal period if not provided and needed
        if seasonal_period is None and model_type in ['sarimax', 'decomposition']:
            # Try to estimate from data
            if len(values) >= 2 * window:
                # Calculate autocorrelation
                acf_values = acf(values, nlags=min(window, len(values)//2), fft=True)
                
                # Find peaks in ACF
                potential_periods = [i for i in range(2, len(acf_values)) if acf_values[i] > acf_values[i-1] and acf_values[i] > acf_values[i+1]]
                
                if potential_periods:
                    seasonal_period = potential_periods[0]
                else:
                    # Default periods based on data frequency
                    freq = pd.infer_freq(times)
                    if freq:
                        if 'D' in freq:
                            seasonal_period = 7  # Weekly
                        elif 'H' in freq:
                            seasonal_period = 24  # Daily for hourly data
                        elif 'T' in freq or 'MIN' in freq:
                            seasonal_period = 60  # Hourly for minute data
                        elif 'M' in freq:
                            seasonal_period = 12  # Yearly for monthly data
                        else:
                            seasonal_period = 1  # No seasonality
                    else:
                        seasonal_period = 1  # No seasonality
            else:
                seasonal_period = 1  # No seasonality
        
        # For methods that use rolling windows
        if method in ['residual', 'prediction_interval']:
            for i in range(len(values) - window + 1):
                if i + window <= len(values):
                    train_idx = values.index[i:i+window-1]  # Training data
                    test_idx = values.index[i+window-1]  # Current point to test
                    
                    train_values = values.loc[train_idx]
                    test_value = values.loc[test_idx]
                    
                    # Get expected value and prediction error
                    if model_type == 'ewm':
                        # Exponentially weighted moving average
                        alpha = 2 / (window + 1)  # Common rule of thumb
                        expected = train_values.ewm(alpha=alpha, adjust=False).mean().iloc[-1]
                        
                        # Calculate prediction error standard deviation
                        residuals = train_values - train_values.ewm(alpha=alpha, adjust=False).mean()
                        pred_std = residuals.std()
                        
                    elif model_type == 'sarimax':
                        try:
                            # Fit SARIMAX model
                            if seasonal_period > 1:
                                order = (1, 0, 0)
                                seasonal_order = (1, 0, 0, seasonal_period)
                            else:
                                order = (1, 0, 0)
                                seasonal_order = (0, 0, 0, 0)
                            
                            model = SARIMAX(
                                train_values, 
                                order=order, 
                                seasonal_order=seasonal_order,
                                enforce_stationarity=False,
                                enforce_invertibility=False
                            )
                            model_fit = model.fit(disp=False)
                            
                            # Get forecast for next point
                            forecast = model_fit.forecast(steps=1)
                            expected = forecast[0]
                            
                            # Get prediction error standard deviation
                            pred_std = np.sqrt(model_fit.mse)
                            
                        except Exception as e:
                            # Fallback to exponential weighted mean
                            alpha = 2 / (window + 1)
                            expected = train_values.ewm(alpha=alpha, adjust=False).mean().iloc[-1]
                            residuals = train_values - train_values.ewm(alpha=alpha, adjust=False).mean()
                            pred_std = residuals.std()
                    
                    elif model_type == 'decomposition':
                        # Simple decomposition: trend + seasonal + residual
                        if seasonal_period > 1 and len(train_values) >= 2 * seasonal_period:
                            # Calculate trend component
                            trend = train_values.rolling(window=min(window//2, len(train_values)//2)).mean()
                            
                            # Calculate seasonal component
                            detrended = train_values - trend
                            seasonal = np.zeros(len(train_values))
                            
                            for season in range(seasonal_period):
                                season_idx = [i for i in range(len(train_values)) if i % seasonal_period == season]
                                if season_idx:
                                    season_mean = detrended.iloc[season_idx].mean()
                                    for idx in season_idx:
                                        seasonal[idx] = season_mean
                            
                            # Expected value is trend + seasonal
                            current_season = (len(train_values)) % seasonal_period
                            season_idx = [i for i in range(len(train_values)) if i % seasonal_period == current_season]
                            season_value = detrended.iloc[season_idx].mean() if season_idx else 0
                            
                            expected = trend.iloc[-1] + season_value
                            
                            # Residuals and prediction std
                            residuals = train_values - (trend + seasonal)
                            pred_std = residuals.dropna().std()
                        else:
                            # Fallback to simple moving average
                            expected = train_values.mean()
                            pred_std = train_values.std()
                    else:
                        raise ValueError(f"Unknown model type: {model_type}")
                    
                    # Handle NaN or zero std
                    if np.isnan(pred_std) or pred_std == 0:
                        pred_std = train_values.std()
                        if np.isnan(pred_std) or pred_std == 0:
                            pred_std = 1.0  # Fallback
                    
                    # Calculate residual/score
                    residual = test_value - expected
                    
                    # Flag anomalies based on method
                    if method == 'residual':
                        # Based on standardized residual
                        score = abs(residual / pred_std)
                        is_anomaly = score > threshold
                        
                    elif method == 'prediction_interval':
                        # Based on prediction interval
                        lower_bound = expected - threshold * pred_std
                        upper_bound = expected + threshold * pred_std
                        is_anomaly = (test_value < lower_bound) or (test_value > upper_bound)
                        
                        # Calculate score as how many std deviations outside the bounds
                        if test_value < lower_bound:
                            score = abs((test_value - lower_bound) / pred_std) + threshold
                        elif test_value > upper_bound:
                            score = abs((test_value - upper_bound) / pred_std) + threshold
                        else:
                            score = 0
                    
                    # Update result dataframe
                    if isinstance(mask, slice) and mask.start is None and mask.stop is None:
                        result_df.loc[(result_df.index == test_idx), flag_col] = is_anomaly
                        result_df.loc[(result_df.index == test_idx), score_col] = score
                        result_df.loc[(result_df.index == test_idx), expected_col] = expected
                    else:
                        result_df.loc[mask & (result_df.index == test_idx), flag_col] = is_anomaly
                        result_df.loc[mask & (result_df.index == test_idx), score_col] = score
                        result_df.loc[mask & (result_df.index == test_idx), expected_col] = expected
                    
        elif method == 'changepoint':
            # Detect change points in the trend
            if len(values) < 2 * window:
                warnings.warn(f"Not enough data for changepoint detection. Need at least {2*window} points.")
                return
            
            # Calculate trend using moving average
            trend = values.rolling(window=window//2, center=True).mean()
            
            # Calculate slope changes
            slopes = np.zeros(len(trend))
            for i in range(window, len(trend)):
                # Calculate slope of two adjacent windows
                prev_window = trend.iloc[i-window:i]
                next_window = trend.iloc[i:i+window]
                
                if len(prev_window) > 0 and len(next_window) > 0:
                    # Use linear regression to calculate slopes
                    x_prev = np.arange(len(prev_window))
                    x_next = np.arange(len(next_window))
                    
                    # Calculate slopes using regression
                    if len(prev_window) > 1:
                        prev_slope, _, _, _, _ = stats.linregress(x_prev, prev_window)
                    else:
                        prev_slope = 0
                        
                    if len(next_window) > 1:
                        next_slope, _, _, _, _ = stats.linregress(x_next, next_window)
                    else:
                        next_slope = 0
                    
                    # Slope change
                    slopes[i] = abs(next_slope - prev_slope)
            
            # Get distribution of slope changes
            valid_slopes = slopes[~np.isnan(slopes)]
            if len(valid_slopes) > 0:
                # Use modified Z-score to identify significant slope changes
                median_slope = np.median(valid_slopes)
                mad_slope = np.median(np.abs(valid_slopes - median_slope))
                
                if mad_slope == 0:
                    mad_slope = np.mean(valid_slopes) * 0.1  # Fallback
                
                # Calculate scores
                scores = 0.6745 * np.abs(slopes - median_slope) / mad_slope
                
                # Flag changepoints
                changepoints = scores > threshold
                
                # Update result dataframe
                for i, (idx, score, is_cp) in enumerate(zip(values.index, scores, changepoints)):
                    if not np.isnan(score):
                        result_df.loc[mask & (result_df.index == idx), flag_col] = is_cp
                        result_df.loc[mask & (result_df.index == idx), score_col] = score
                        
                        # For expected value, use the trend
                        if not np.isnan(trend.iloc[i]):
                            result_df.loc[mask & (result_df.index == idx), expected_col] = trend.iloc[i]
        else:
            raise ValueError(f"Unknown method: {method}")
    
    return _detect_contextual_anomalies


def detect_collective_anomalies(
    columns: Union[str, List[str]],
    time_column: str,
    method: str = 'isolation_forest',
    window: int = 30,
    contamination: float = 0.05,
    n_estimators: int = 100,
    group_columns: Optional[List[str]] = None,
    datetime_format: Optional[str] = None
):
    """
    Detect collective anomalies using machine learning methods on multiple features
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze for anomalies (multiple columns for multivariate analysis)
    time_column : str
        Column containing the time/date information
    method : str, default='isolation_forest'
        Method to use: 'isolation_forest', 'lof' (Local Outlier Factor)
    window : int, default=30
        Window size for rolling analysis
    contamination : float, default=0.05
        Expected proportion of anomalies in the data
    n_estimators : int, default=100
        Number of estimators (for tree-based methods)
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that detects collective anomalies in an AnomalyPipe
    """
    def _detect_collective_anomalies(pipe):
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
                
        # Validate time column
        if time_column not in df.columns:
            raise ValueError(f"Time column '{time_column}' not found in data")
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            if datetime_format:
                df[time_column] = pd.to_datetime(df[time_column], format=datetime_format)
            else:
                df[time_column] = pd.to_datetime(df[time_column])
        
        # Sort by time column
        df = df.sort_values(time_column)
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Add anomaly columns
        anomaly_flag_col = f"collective_anomaly_{method}"
        anomaly_score_col = f"collective_score_{method}"
        
        # Initialize result columns
        result_df[anomaly_flag_col] = False
        result_df[anomaly_score_col] = np.nan
        
        # Process with or without grouping
        if group_columns is not None:
            # Check if group columns exist
            for group_col in group_columns:
                if group_col not in df.columns:
                    raise ValueError(f"Group column '{group_col}' not found in data")
            
            # Apply anomaly detection to each group
            for name, group in df.groupby(group_columns):
                # Convert to multi-index name if needed
                if isinstance(name, tuple):
                    group_idx = pd.MultiIndex.from_tuples([name], names=group_columns)
                    idx_match = pd.MultiIndex.from_frame(df[group_columns])
                    group_mask = idx_match.isin(group_idx)
                else:
                    group_mask = df[group_columns[0]] == name
                
                # Detect collective anomalies in this group
                _process_collective_anomalies(
                    result_df, 
                    group[cols], 
                    group[time_column],
                    group_mask, 
                    method, 
                    window,
                    contamination,
                    n_estimators,
                    anomaly_flag_col,
                    anomaly_score_col
                )
        else:
            # Apply anomaly detection to entire dataset
            _process_collective_anomalies(
                result_df, 
                df[cols], 
                df[time_column],
                slice(None), 
                method, 
                window,
                contamination,
                n_estimators,
                anomaly_flag_col,
                anomaly_score_col
            )
        
        # Store results
        analysis_name = f"collective_anomalies_{method}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'collective_anomalies',
            'method': method,
            'window': window,
            'contamination': contamination,
            'columns': cols
        }
        new_pipe.current_analysis = analysis_name
        
        return new_pipe
    
    def _process_collective_anomalies(result_df, data, time_series, mask, method,
                                      window, contamination, n_estimators, flag_col, score_col):
        """Helper function to detect collective anomalies"""
        # Get values without NaN
        data_clean = data.dropna()
        
        if len(data_clean) < window:
            warnings.warn(f"Not enough data for collective anomaly detection. Need at least {window} points.")
            return
        
        # For rolling window analysis
        for i in range(len(data_clean) - window + 1):
            start_idx = i
            end_idx = i + window
            
            if start_idx < end_idx <= len(data_clean):
                window_data = data_clean.iloc[start_idx:end_idx]
                
                # Current point to evaluate is the last one in the window
                test_idx = window_data.index[-1]
                
                # Training data is everything except the last point
                train_data = window_data.iloc[:-1]
                test_point = window_data.iloc[-1:]
                
                # Skip if not enough training data
                if len(train_data) < 5:  # Need at least a few points
                    continue
                
                # Fill any missing values with column means
                train_data_vals = train_data.values
                test_point_vals = test_point.values
                
                # Detection method
                if method == 'isolation_forest':
                    # Fit Isolation Forest
                    clf = IsolationForest(
                        n_estimators=n_estimators,
                        contamination=contamination,
                        random_state=42
                    )
                    clf.fit(train_data_vals)
                    
                    # Predict anomaly score for test point
                    score = -clf.score_samples(test_point_vals)[0]  # Negative score: higher means more anomalous
                    pred = clf.predict(test_point_vals)[0]  # -1 for anomalies, 1 for normal
                    
                    is_anomaly = pred == -1
                    
                elif method == 'lof':
                    # Fit Local Outlier Factor
                    clf = LocalOutlierFactor(
                        n_neighbors=min(20, len(train_data) - 1),
                        contamination=contamination,
                        novelty=True
                    )
                    clf.fit(train_data_vals)
                    
                    # Predict anomaly score for test point
                    score = -clf.score_samples(test_point_vals)[0]  # Negative score: higher means more anomalous
                    pred = clf.predict(test_point_vals)[0]  # -1 for anomalies, 1 for normal
                    
                    is_anomaly = pred == -1
                
                else:
                    raise ValueError(f"Unknown method: {method}")
                
                # Update result dataframe
                result_df.loc[mask & (result_df.index == test_idx), flag_col] = is_anomaly
                result_df.loc[mask & (result_df.index == test_idx), score_col] = score
    
    return _detect_collective_anomalies


def calculate_seasonal_residuals(
    columns: Union[str, List[str]],
    mtime_column: str,
    mseasonal_period: Optional[int] = None,
    mmethod: str = 'multiplicative',
    mgroup_columns: Optional[List[str]] = None,
    mdatetime_format: Optional[str] = None
):
    """
    Calculate residuals after removing seasonal patterns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze
    time_column : str
        Column containing the time/date information
    seasonal_period : int, optional
        Number of periods in a seasonal cycle (if None, will be estimated)
    method : str, default='multiplicative'
        Decomposition method: 'multiplicative' or 'additive'
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that calculates seasonal residuals in an AnomalyPipe
    """
    def _calculate_seasonal_residuals(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        seasonal_period = mseasonal_period
        time_column = mtime_column
        method = mmethod
        group_columns = mgroup_columns
        datetime_format = mdatetime_format
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
                
        # Validate time column
        if time_column not in df.columns:
            raise ValueError(f"Time column '{time_column}' not found in data")
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            if datetime_format:
                df[time_column] = pd.to_datetime(df[time_column], format=datetime_format)
            else:
                df[time_column] = pd.to_datetime(df[time_column])
        
        # Sort by time column
        df = df.sort_values(time_column)
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Determine seasonal period if not provided
        if seasonal_period is None:
            # Try to estimate from data
            freq = pd.infer_freq(df[time_column])
            if freq:
                if 'D' in freq:
                    seasonal_period = 7  # Weekly
                elif 'H' in freq:
                    seasonal_period = 24  # Daily for hourly data
                elif 'T' in freq or 'MIN' in freq:
                    seasonal_period = 60  # Hourly for minute data
                elif 'M' in freq:
                    seasonal_period = 12  # Yearly for monthly data
                else:
                    seasonal_period = 1  # No seasonality
            else:
                # Try ACF-based estimation for the first column
                if len(df) > 50:  # Need enough data
                    acf_values = acf(df[cols[0]].dropna(), nlags=min(len(df)//2, 50), fft=True)
                    potential_periods = [i for i in range(2, len(acf_values)) if acf_values[i] > acf_values[i-1] and acf_values[i] > acf_values[i+1]]
                    if potential_periods:
                        seasonal_period = potential_periods[0]
                    else:
                        seasonal_period = 1  # No seasonality
                else:
                    seasonal_period = 1  # No seasonality
        
        # Process each column
        for col in cols:
            # Define column names for new columns
            seasonal_col = f"{col}_seasonal"
            trend_col = f"{col}_trend"
            residual_col = f"{col}_residual"
            
            # Initialize result columns
            result_df[seasonal_col] = np.nan
            result_df[trend_col] = np.nan
            result_df[residual_col] = np.nan
            
            # Process with or without grouping
            if group_columns is not None:
                # Check if group columns exist
                for group_col in group_columns:
                    if group_col not in df.columns:
                        raise ValueError(f"Group column '{group_col}' not found in data")
                
                # Apply decomposition to each group
                for name, group in df.groupby(group_columns):
                    # Convert to multi-index name if needed
                    if isinstance(name, tuple):
                        group_idx = pd.MultiIndex.from_tuples([name], names=group_columns)
                        idx_match = pd.MultiIndex.from_frame(df[group_columns])
                        group_mask = idx_match.isin(group_idx)
                    else:
                        group_mask = df[group_columns[0]] == name
                    
                    # Perform seasonal decomposition
                    _decompose_series(
                        result_df, 
                        group[col], 
                        group[time_column],
                        group_mask, 
                        seasonal_period,
                        method,
                        seasonal_col,
                        trend_col,
                        residual_col
                    )
            else:
                # Apply decomposition to entire column
                _decompose_series(
                    result_df, 
                    df[col], 
                    df[time_column],
                    slice(None), 
                    seasonal_period,
                    method,
                    seasonal_col,
                    trend_col,
                    residual_col
                )
        
        # Store results
        analysis_name = f"seasonal_residuals_{method}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'seasonal_residuals',
            'method': method,
            'seasonal_period': seasonal_period,
            'columns': cols
        }
        new_pipe.current_analysis = analysis_name
        
        return new_pipe
    
    def _decompose_series(result_df, series, time_series, mask, seasonal_period,
                          method, seasonal_col, trend_col, residual_col):
        """Helper function to perform seasonal decomposition"""
        # Get values without NaN
        values = series.dropna()
        times = time_series.loc[values.index]
        
        if len(values) < 2 * seasonal_period:
            warnings.warn(f"Not enough data for seasonal decomposition. Need at least {2 * seasonal_period} points.")
            return
        
        try:
            # Use statsmodels seasonal_decompose if available
            from statsmodels.tsa.seasonal import seasonal_decompose
            
            # Set the series index to time
            ts = pd.Series(values.values, index=times)
            
            # Perform decomposition
            decomposition = seasonal_decompose(ts, model=method, period=seasonal_period, extrapolate_trend='freq')
            
            # Extract components
            trend = pd.Series(decomposition.trend.values, index=values.index)
            seasonal = pd.Series(decomposition.seasonal.values, index=values.index)
            residual = pd.Series(decomposition.resid.values, index=values.index)
            
        except Exception as e:
            warnings.warn(f"Statsmodels decomposition failed: {str(e)}. Using simple decomposition.")
            
            # Simple manual decomposition
            # Calculate trend using centered moving average
            if seasonal_period % 2 == 0:
                # Even seasonal period requires two moving averages
                trend_ma1 = values.rolling(window=seasonal_period, center=False).mean()
                trend_ma2 = trend_ma1.rolling(window=2, center=False).mean()
                trend = trend_ma2.shift(-1)  # Center the trend
            else:
                # Odd seasonal period can use centered moving average directly
                trend = values.rolling(window=seasonal_period, center=True).mean()
            
            # Calculate seasonal components
            if method == 'multiplicative':
                # For multiplicative model, divide values by trend
                detrended = values / trend
            else:
                # For additive model, subtract trend from values
                detrended = values - trend
            
            # Calculate seasonal pattern by averaging values at the same phase
            seasonal_pattern = np.zeros(seasonal_period)
            phase_counts = np.zeros(seasonal_period)
            
            for i, val in enumerate(detrended):
                if not np.isnan(val):
                    phase = i % seasonal_period
                    seasonal_pattern[phase] += val
                    phase_counts[phase] += 1
            
            # Average each phase
            for phase in range(seasonal_period):
                if phase_counts[phase] > 0:
                    seasonal_pattern[phase] /= phase_counts[phase]
            
            # Normalize seasonal pattern for multiplicative model
            if method == 'multiplicative':
                seasonal_pattern = seasonal_pattern / np.mean(seasonal_pattern[~np.isnan(seasonal_pattern)])
            elif method == 'additive':
                seasonal_pattern = seasonal_pattern - np.mean(seasonal_pattern[~np.isnan(seasonal_pattern)])
            
            # Create the full seasonal component
            seasonal = np.zeros(len(values))
            for i in range(len(values)):
                phase = i % seasonal_period
                seasonal[i] = seasonal_pattern[phase]
            
            seasonal = pd.Series(seasonal, index=values.index)
            
            # Calculate residuals
            if method == 'multiplicative':
                residual = values / (trend * seasonal)
            else:
                residual = values - (trend + seasonal)
        if isinstance(mask, slice) and mask.start is None and mask.stop is None:
            # Update result dataframe
            result_df.loc[result_df.index.isin(values.index), trend_col] = trend
            result_df.loc[result_df.index.isin(values.index), seasonal_col] = seasonal
            result_df.loc[result_df.index.isin(values.index), residual_col] = residual
        else:    
            # Update result dataframe
            result_df.loc[mask & result_df.index.isin(values.index), trend_col] = trend
            result_df.loc[mask & result_df.index.isin(values.index), seasonal_col] = seasonal
            result_df.loc[mask & result_df.index.isin(values.index), residual_col] = residual
    
    return _calculate_seasonal_residuals


def detect_anomalies_from_residuals(
    columns: Union[str, List[str]],
    method: str = 'zscore',
    threshold: float = 3.0,
    suffix: str = '_residual',
    output_suffix: str = '_anomaly'
):
    """
    Detect anomalies from pre-calculated residuals
    
    Parameters:
    -----------
    columns : str or List[str]
        Base column(s) names (will look for {column}{suffix})
    method : str, default='zscore'
        Method to use: 'zscore', 'modified_zscore', 'iqr', or 'percentile'
    threshold : float, default=3.0
        Threshold for determining anomalies
    suffix : str, default='_residual'
        Suffix of columns containing residuals
    output_suffix : str, default='_anomaly'
        Suffix for output anomaly flag columns
        
    Returns:
    --------
    Callable
        Function that detects anomalies from residuals in an AnomalyPipe
    """
    def _detect_anomalies_from_residuals(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Get residual columns
        residual_cols = [f"{col}{suffix}" for col in cols]
        
        # Check if residual columns exist
        for col in residual_cols:
            if col not in df.columns:
                raise ValueError(f"Residual column '{col}' not found in data. Run calculate_seasonal_residuals first.")
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Process each residual column
        for i, (base_col, residual_col) in enumerate(zip(cols, residual_cols)):
            # Create output columns
            anomaly_flag_col = f"{base_col}{output_suffix}"
            anomaly_score_col = f"{base_col}_score"
            
            # Detect outliers in residuals
            residuals = df[residual_col].dropna()
            
            if method == 'zscore':
                # Z-score method
                mean = residuals.mean()
                std = residuals.std()
                
                if std == 0:
                    # If standard deviation is zero, no outliers
                    scores = np.zeros(len(residuals))
                else:
                    scores = np.abs((residuals - mean) / std)
                
                anomaly_flags = scores > threshold
                
            elif method == 'modified_zscore':
                # Modified Z-score method (more robust to outliers)
                median = residuals.median()
                # Median Absolute Deviation
                mad = np.median(np.abs(residuals - median))
                
                if mad == 0:
                    # If MAD is zero, no outliers
                    scores = np.zeros(len(residuals))
                else:
                    # Constant 0.6745 makes MAD comparable to standard deviation for normal distributions
                    scores = 0.6745 * np.abs(residuals - median) / mad
                
                anomaly_flags = scores > threshold
                
            elif method == 'iqr':
                # Interquartile Range method
                q1 = residuals.quantile(0.25)
                q3 = residuals.quantile(0.75)
                iqr = q3 - q1
                
                lower_bound = q1 - threshold * iqr
                upper_bound = q3 + threshold * iqr
                
                anomaly_flags = (residuals < lower_bound) | (residuals > upper_bound)
                
                # Calculate scores as how many IQRs away from the bounds
                scores = np.zeros(len(residuals))
                lower_outliers = residuals < lower_bound
                upper_outliers = residuals > upper_bound
                
                if iqr == 0:
                    # If IQR is zero, score based on distance from median
                    median = residuals.median()
                    scores[lower_outliers] = abs(residuals[lower_outliers] - median)
                    scores[upper_outliers] = abs(residuals[upper_outliers] - median)
                else:
                    # Score based on distance from bounds in terms of IQR
                    scores[lower_outliers] = (abs(residuals[lower_outliers] - lower_bound) / iqr) + threshold
                    scores[upper_outliers] = (abs(residuals[upper_outliers] - upper_bound) / iqr) + threshold
                
            elif method == 'percentile':
                # Percentile method
                lower_percentile = threshold / 2
                upper_percentile = 100 - lower_percentile
                
                lower_bound = residuals.quantile(lower_percentile / 100)
                upper_bound = residuals.quantile(upper_percentile / 100)
                
                anomaly_flags = (residuals < lower_bound) | (residuals > upper_bound)
                
                # Calculate scores (0 to 1, where 1 is the most extreme outlier)
                scores = np.zeros(len(residuals))
                min_val = residuals.min()
                max_val = residuals.max()
                range_val = max_val - min_val
                
                if range_val == 0:
                    # If range is zero, no outliers
                    scores = np.zeros(len(residuals))
                else:
                    # For lower outliers, score based on distance from lower bound
                    lower_outliers = residuals < lower_bound
                    if np.any(lower_outliers):
                        scores[lower_outliers] = abs((residuals[lower_outliers] - lower_bound) / range_val)
                    
                    # For upper outliers, score based on distance from upper bound
                    upper_outliers = residuals > upper_bound
                    if np.any(upper_outliers):
                        scores[upper_outliers] = abs((residuals[upper_outliers] - upper_bound) / range_val)
            
            else:
                raise ValueError(f"Unknown method: {method}")
            
            # Create DataFrames for flags and scores
            anomaly_df = pd.DataFrame({
                'flag': anomaly_flags,
                'score': scores
            }, index=residuals.index)
            
            # Add to result dataframe
            result_df[anomaly_flag_col] = False  # Initialize
            result_df[anomaly_score_col] = np.nan  # Initialize
            
            # Update values for non-NaN residuals
            result_df.loc[anomaly_df.index, anomaly_flag_col] = anomaly_df['flag']
            result_df.loc[anomaly_df.index, anomaly_score_col] = anomaly_df['score']
        
        # Store results
        analysis_name = f"residual_anomalies_{method}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'residual_anomalies',
            'method': method,
            'threshold': threshold,
            'columns': cols
        }
        new_pipe.current_analysis = analysis_name
        
        return new_pipe
    
    return _detect_anomalies_from_residuals


def get_anomaly_summary(analysis_name: Optional[str] = None):
    """
    Generate a summary of detected anomalies
    
    Parameters:
    -----------
    analysis_name : str, optional
        Name of the analysis to summarize (if None, use current analysis)
        
    Returns:
    --------
    Callable
        Function that returns a summary of anomalies
    """
    def _get_anomaly_summary(pipe):
        if not pipe.anomaly_results:
            raise ValueError("No anomaly detection results found.")
    
        # Determine which analysis to summarize
        if analysis_name is not None:
            if analysis_name not in pipe.anomaly_results:
                raise ValueError(f"Analysis '{analysis_name}' not found.")
            
            current_analysis = analysis_name
        else:
            if pipe.current_analysis is None:
                # Use the most recent analysis
                current_analysis = next(reversed(pipe.anomaly_results))
            else:
                current_analysis = pipe.current_analysis
        
        # Get analysis details
        analysis = pipe.anomaly_results[current_analysis]
        df = pipe.data
        
        # Find anomaly columns
        anomaly_columns = []
        
        for col in df.columns:
            if 'anomaly' in col.lower() and not col.startswith('_'):
                anomaly_columns.append(col)
        
        # Fix: Check if analysis contains column information
        # and use that if no anomaly columns are found
        if not anomaly_columns and 'columns' in analysis:
            # Create anomaly column names based on the analysis type and columns
            base_columns = analysis['columns']
            if not isinstance(base_columns, list):
                base_columns = [base_columns]
                
            method = analysis.get('method', '')
            for base_col in base_columns:
                # Try standard naming patterns
                possible_names = [
                    f"{base_col}_outlier_{method}",
                    f"{base_col}_anomaly_{method}",
                    f"{base_col}_anomaly"
                ]
                
                # Check if any of these columns exist
                for name in possible_names:
                    if name in df.columns:
                        anomaly_columns.append(name)
                        break
        
        if not anomaly_columns:
            raise ValueError(f"No anomaly columns found for analysis '{current_analysis}'. Please ensure the anomaly detection was successful.")
        
        # Create summary
        summary = {
            'analysis_type': analysis['type'],
            'method': analysis.get('method', analysis.get('ensemble_method', 'unknown')),
            'total_points': len(df),
            'anomalies_by_column': {},
            'total_anomalies': 0
        }
        
        # Count anomalies by column
        for col in anomaly_columns:
            anomaly_count = df[col].sum()
            anomaly_pct = (anomaly_count / len(df)) * 100
            
            # Get base column name
            base_col = col.split('_anomaly')[0]
            
            # Find corresponding score column
            score_col = None
            for c in df.columns:
                if base_col in c and 'score' in c.lower():
                    score_col = c
                    break
            
            # Get score statistics if available
            score_stats = {}
            if score_col is not None:
                anomaly_scores = df.loc[df[col], score_col]
                if not anomaly_scores.empty:
                    score_stats = {
                        'min_score': anomaly_scores.min(),
                        'max_score': anomaly_scores.max(),
                        'mean_score': anomaly_scores.mean(),
                        'median_score': anomaly_scores.median()
                    }
            
            # Store column summary
            summary['anomalies_by_column'][col] = {
                'count': int(anomaly_count),
                'percentage': float(anomaly_pct),
                'score_stats': score_stats
            }
            
            summary['total_anomalies'] += int(anomaly_count)
        
        # Calculate overall statistics
        summary['total_anomaly_percentage'] = (summary['total_anomalies'] / (len(df) * len(anomaly_columns))) * 100
        
        # Get time-based distribution if time column available
        time_columns = [col for col in df.columns if 'time' in col.lower() or 'date' in col.lower()]
        if time_columns:
            time_col = time_columns[0]
            
            # Check if time column is datetime
            if pd.api.types.is_datetime64_any_dtype(df[time_col]):
                # Group by day/month/year depending on data range
                date_range = (df[time_col].max() - df[time_col].min()).days
                
                if date_range <= 31:
                    # Group by day
                    time_format = '%Y-%m-%d'
                    df['_time_group'] = df[time_col].dt.strftime(time_format)
                elif date_range <= 366:
                    # Group by month
                    time_format = '%Y-%m'
                    df['_time_group'] = df[time_col].dt.strftime(time_format)
                else:
                    # Group by year
                    time_format = '%Y'
                    df['_time_group'] = df[time_col].dt.strftime(time_format)
                
                # Count anomalies by time period
                time_distribution = {}
                
                for col in anomaly_columns:
                    col_distribution = df.groupby('_time_group')[col].sum()
                    time_distribution[col] = col_distribution.to_dict()
                
                summary['time_distribution'] = time_distribution
        
        return summary
    
    return _get_anomaly_summary


def get_top_anomalies(
    n: int = 10,
    time_column: Optional[str] = None,
    analysis_name: Optional[str] = None
):
    """
    Get the top n anomalies by score
    
    Parameters:
    -----------
    n : int, default=10
        Number of top anomalies to return
    time_column : str, optional
        Column containing the time/date information
    analysis_name : str, optional
        Name of the analysis to use (if None, use current analysis)
        
    Returns:
    --------
    Callable
        Function that returns top anomalies
    """
    def _get_top_anomalies(pipe):
        if not pipe.anomaly_results:
            raise ValueError("No anomaly detection results found.")
        
        # Determine which analysis to use
        if analysis_name is not None:
            if analysis_name not in pipe.anomaly_results:
                raise ValueError(f"Analysis '{analysis_name}' not found.")
            
            current_analysis = analysis_name
        else:
            if pipe.current_analysis is None:
                # Use the most recent analysis
                current_analysis = next(reversed(pipe.anomaly_results))
            else:
                current_analysis = pipe.current_analysis
        
        # Get analysis details
        analysis = pipe.anomaly_results[current_analysis]
        df = pipe.data
        
        # Find anomaly and score columns
        anomaly_columns = []
        score_columns = []
        
        for col in df.columns:
            if 'anomaly' in col.lower() and not col.startswith('_'):
                anomaly_columns.append(col)
            elif 'score' in col.lower() and not col.startswith('_'):
                score_columns.append(col)
        
        if not anomaly_columns:
            raise ValueError(f"No anomaly columns found for analysis '{current_analysis}'.")
        
        if not score_columns:
            raise ValueError(f"No score columns found for analysis '{current_analysis}'.")
        
        # Create merged DataFrame with all anomalies
        anomaly_dfs = []
        
        for i, anomaly_col in enumerate(anomaly_columns):
            # Find corresponding score column
            base_col = anomaly_col.split('_anomaly')[0]
            
            score_col = None
            for sc in score_columns:
                if base_col in sc:
                    score_col = sc
                    break
            
            if score_col is None:
                continue
            
            # Get only anomalies
            anomaly_df = df[df[anomaly_col]].copy()
            if len(anomaly_df) == 0:
                continue
            
            # Add columns for identification
            anomaly_df['anomaly_type'] = anomaly_col
            anomaly_df['score'] = anomaly_df[score_col]
            anomaly_df['metric'] = base_col
            
            # Get original value
            if base_col in df.columns:
                anomaly_df['value'] = anomaly_df[base_col]
            
            # Get expected value if available
            expected_col = f"{base_col}_expected"
            if expected_col in df.columns:
                anomaly_df['expected'] = anomaly_df[expected_col]
            
            # Add to list
            anomaly_dfs.append(anomaly_df)
        
        if not anomaly_dfs:
            raise ValueError("No anomalies found.")
        
        # Merge all anomaly DataFrames
        all_anomalies = pd.concat(anomaly_dfs, ignore_index=False)
        
        # Add time information if requested
        if time_column is not None:
            if time_column in df.columns:
                # Create a time-indexed version
                if pd.api.types.is_datetime64_any_dtype(df[time_column]):
                    all_anomalies['time'] = all_anomalies[time_column]
        
        # Select columns to include in output
        output_cols = ['anomaly_type', 'metric', 'score', 'value']
        if 'expected' in all_anomalies.columns:
            output_cols.append('expected')
        if 'time' in all_anomalies.columns:
            output_cols.append('time')
        
        # Sort by score (descending) and take top n
        top_anomalies = all_anomalies.sort_values('score', ascending=False)[output_cols].head(n)
        
        return top_anomalies
    
    return _get_top_anomalies



def detect_change_points(
    columns: Union[str, List[str]],
    time_column: str,
    min_size: int = 20,
    method: str = 'binary_segmentation',
    penalty: str = 'bic',
    group_columns: Optional[List[str]] = None,
    datetime_format: Optional[str] = None
):
    """
    Detect change points in time series data
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze for change points
    time_column : str
        Column containing the time/date information
    min_size : int, default=20
        Minimum number of observations between change points
    method : str, default='binary_segmentation'
        Method: 'binary_segmentation', 'window' or 'pruned_exact'
    penalty : str, default='bic'
        Penalty for model selection: 'bic', 'aic', 'mbic'
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that detects change points in an AnomalyPipe
    """
    def _detect_change_points(pipe):
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
                
        # Validate time column
        if time_column not in df.columns:
            raise ValueError(f"Time column '{time_column}' not found in data")
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            if datetime_format:
                df[time_column] = pd.to_datetime(df[time_column], format=datetime_format)
            else:
                df[time_column] = pd.to_datetime(df[time_column])
        
        # Sort by time column
        df = df.sort_values(time_column)
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Check for ruptures package
        try:
            import ruptures as rpt
        except ImportError:
            # Fall back to manual implementation
            warnings.warn("Package 'ruptures' not found. Using manual change point detection.")
            
            # Process each column
            for col in cols:
                # Define column names for change point flags
                cp_flag_col = f"{col}_changepoint"
                cp_score_col = f"{col}_cp_score"
                
                # Initialize result columns
                result_df[cp_flag_col] = False
                result_df[cp_score_col] = 0.0
                
                # Process with or without grouping
                if group_columns is not None:
                    # Check if group columns exist
                    for group_col in group_columns:
                        if group_col not in df.columns:
                            raise ValueError(f"Group column '{group_col}' not found in data")
                    
                    # Apply change point detection to each group
                    for name, group in df.groupby(group_columns):
                        # Convert to multi-index name if needed
                        if isinstance(name, tuple):
                            group_idx = pd.MultiIndex.from_tuples([name], names=group_columns)
                            idx_match = pd.MultiIndex.from_frame(df[group_columns])
                            group_mask = idx_match.isin(group_idx)
                        else:
                            group_mask = df[group_columns[0]] == name
                        
                        # Detect change points in this group
                        _manual_detect_change_points(
                            result_df, 
                            group[col], 
                            group[time_column],
                            group_mask, 
                            min_size,
                            method,
                            penalty,
                            cp_flag_col,
                            cp_score_col
                        )
                else:
                    # Apply change point detection to entire column
                    _manual_detect_change_points(
                        result_df, 
                        df[col], 
                        df[time_column],
                        slice(None), 
                        min_size,
                        method,
                        penalty,
                        cp_flag_col,
                        cp_score_col
                    )
            
            # Store results
            analysis_name = f"changepoints_{method}"
            new_pipe.data = result_df
            new_pipe.anomaly_results[analysis_name] = {
                'type': 'changepoints',
                'method': method,
                'min_size': min_size,
                'columns': cols
            }
            new_pipe.current_analysis = analysis_name
            
            return new_pipe
        
        # Process each column using ruptures
        for col in cols:
            # Define column names for change point flags
            cp_flag_col = f"{col}_changepoint"
            cp_score_col = f"{col}_cp_score"
            
            # Initialize result columns
            result_df[cp_flag_col] = False
            result_df[cp_score_col] = 0.0
            
            # Process with or without grouping
            if group_columns is not None:
                # Check if group columns exist
                for group_col in group_columns:
                    if group_col not in df.columns:
                        raise ValueError(f"Group column '{group_col}' not found in data")
                
                # Apply change point detection to each group
                for name, group in df.groupby(group_columns):
                    # Convert to multi-index name if needed
                    if isinstance(name, tuple):
                        group_idx = pd.MultiIndex.from_tuples([name], names=group_columns)
                        idx_match = pd.MultiIndex.from_frame(df[group_columns])
                        group_mask = idx_match.isin(group_idx)
                    else:
                        group_mask = df[group_columns[0]] == name
                    
                    # Detect change points in this group
                    _detect_ruptures_change_points(
                        result_df, 
                        group[col], 
                        group[time_column],
                        group_mask, 
                        min_size,
                        method,
                        penalty,
                        cp_flag_col,
                        cp_score_col
                    )
            else:
                # Apply change point detection to entire column
                _detect_ruptures_change_points(
                    result_df, 
                    df[col], 
                    df[time_column],
                    slice(None), 
                    min_size,
                    method,
                    penalty,
                    cp_flag_col,
                    cp_score_col
                )
        
        # Store results
        analysis_name = f"changepoints_{method}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'changepoints',
            'method': method,
            'min_size': min_size,
            'columns': cols
        }
        new_pipe.current_analysis = analysis_name
        
        return new_pipe
    
    def _manual_detect_change_points(result_df, series, time_series, mask, min_size, method,
                                    penalty, flag_col, score_col):
        """Manual implementation of change point detection"""
        # Get values without NaN
        values = series.dropna()
        times = time_series.loc[values.index]
        
        if len(values) < 2 * min_size:
            warnings.warn(f"Not enough data for change point detection. Need at least {2 * min_size} points.")
            return
        
        # Calculate sliding window statistics
        if method == 'window':
            # Use sliding window to detect distributional changes
            window_size = min_size
            
            for i in range(len(values) - 2 * window_size + 1):
                if i + 2 * window_size <= len(values):
                    # Get two adjacent windows
                    window1 = values.iloc[i:i+window_size]
                    window2 = values.iloc[i+window_size:i+2*window_size]
                    
                    # Calculate statistics
                    mean1 = window1.mean()
                    std1 = window1.std()
                    mean2 = window2.mean()
                    std2 = window2.std()
                    
                    # Calculate distance score based on mean and std
                    if std1 == 0 or std2 == 0:
                        continue
                    
                    # Bhattacharyya distance for normal distributions
                    mean_diff = mean1 - mean2
                    var_avg = (std1**2 + std2**2) / 2
                    
                    score = 0.25 * (mean_diff**2) / var_avg + 0.5 * np.log(var_avg / np.sqrt(std1**2 * std2**2))
                    
                    # Threshold for change point
                    if score > 1.0:  # Adjustable threshold
                        change_point_idx = values.index[i+window_size]
                        result_df.loc[mask & (result_df.index == change_point_idx), flag_col] = True
                        result_df.loc[mask & (result_df.index == change_point_idx), score_col] = score
        
        elif method == 'binary_segmentation':
            # Binary segmentation algorithm
            def _binary_segment(start, end, min_size, depth=0, max_depth=10):
                if depth >= max_depth or end - start < 2 * min_size:
                    return
                
                # Find optimal split point
                best_score = 0
                best_split = None
                
                for split in range(start + min_size, end - min_size + 1):
                    left = values.iloc[start:split]
                    right = values.iloc[split:end]
                    
                    # Calculate score based on likelihood ratio
                    n_left = len(left)
                    n_right = len(right)
                    n_total = n_left + n_right
                    
                    left_mean = left.mean()
                    right_mean = right.mean()
                    total_mean = values.iloc[start:end].mean()
                    
                    left_var = left.var()
                    right_var = right.var()
                    total_var = values.iloc[start:end].var()
                    
                    # Handle zero variance
                    if left_var == 0 or right_var == 0 or total_var == 0:
                        continue
                    
                    # Log-likelihood ratio statistic
                    score = n_total * np.log(total_var)
                    score -= n_left * np.log(left_var) + n_right * np.log(right_var)
                    
                    # Apply penalty
                    if penalty == 'bic':
                        score -= np.log(n_total)
                    elif penalty == 'aic':
                        score -= 2
                    
                    if score > best_score:
                        best_score = score
                        best_split = split
                
                # If significant split found, record it and recurse
                if best_split is not None and best_score > 0:
                    change_point_idx = values.index[best_split]
                    result_df.loc[mask & (result_df.index == change_point_idx), flag_col] = True
                    result_df.loc[mask & (result_df.index == change_point_idx), score_col] = best_score
                    
                    # Recurse on segments
                    _binary_segment(start, best_split, min_size, depth+1, max_depth)
                    _binary_segment(best_split, end, min_size, depth+1, max_depth)
            
            # Apply binary segmentation to entire series
            _binary_segment(0, len(values), min_size)
        
        else:
            warnings.warn(f"Manual implementation for method '{method}' not available. Using binary segmentation.")
            # Fall back to binary segmentation
            _manual_detect_change_points(result_df, series, time_series, mask, min_size, 'binary_segmentation',
                                       penalty, flag_col, score_col)
    
    def _detect_ruptures_change_points(result_df, series, time_series, mask, min_size, method,
                                     penalty, flag_col, score_col):
        """Detect change points using ruptures package"""
        import ruptures as rpt
        
        # Get values without NaN
        values = series.dropna().values.reshape(-1, 1)  # Need (n, 1) shape for ruptures
        times = time_series.loc[series.dropna().index]
        
        if len(values) < 2 * min_size:
            warnings.warn(f"Not enough data for change point detection. Need at least {2 * min_size} points.")
            return
        
        # Select algorithm
        if method == 'binary_segmentation':
            algo = rpt.Binseg(model="normal").fit(values)
        elif method == 'window':
            algo = rpt.Window(width=min_size, model="normal").fit(values)
        elif method == 'pruned_exact':
            algo = rpt.Pelt(model="normal", min_size=min_size).fit(values)
        else:
            warnings.warn(f"Unknown method: {method}. Using binary segmentation.")
            algo = rpt.Binseg(model="normal").fit(values)
        
        # Map penalty to ruptures format
        if penalty == 'bic':
            pen = "bic"
        elif penalty == 'aic':
            pen = "aic"
        elif penalty == 'mbic':
            pen = "mbic"
        else:
            warnings.warn(f"Unknown penalty: {penalty}. Using BIC.")
            pen = "bic"
        
        # Detect change points
        if method == 'pruned_exact':
            # PELT algorithm uses penalty parameter
            change_points = algo.predict(pen=pen)
        else:
            # Other algorithms use n_bkps parameter (number of change points)
            # We can estimate this based on time series length and min_size
            n_bkps = max(1, len(values) // (2 * min_size))
            change_points = algo.predict(n_bkps=n_bkps)
        
        # Remove the last point (end of sequence) if present
        if change_points[-1] == len(values):
            change_points = change_points[:-1]
        
        if not change_points:
            return
        
        # Calculate scores for each change point
        scores = algo.score(change_points)
        
        # Map change points to the original index
        original_idx = series.dropna().index
        
        for i, cp in enumerate(change_points):
            if cp < len(original_idx):
                change_point_idx = original_idx[cp]
                score = scores[i] if i < len(scores) else 1.0
                
                result_df.loc[mask & (result_df.index == change_point_idx), flag_col] = True
                result_df.loc[mask & (result_df.index == change_point_idx), score_col] = score
    
    return _detect_change_points            

def forecast_and_detect_anomalies(
    columns: Union[str, List[str]],
    time_column: str,
    forecast_periods: int = 5,
    model: str = 'arima',
    threshold: float = 2.0,
    seasonal_period: Optional[int] = None,
    group_columns: Optional[List[str]] = None,
    datetime_format: Optional[str] = None
):
    """
    Forecast time series and detect anomalies based on forecast errors
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to forecast and analyze
    time_column : str
        Column containing the time/date information
    forecast_periods : int, default=5
        Number of periods to forecast ahead
    model : str, default='arima'
        Forecasting model: 'arima', 'exponential_smoothing', 'sarimax'
    threshold : float, default=2.0
        Threshold for anomaly detection (number of std deviations)
    seasonal_period : int, optional
        Number of periods in a seasonal cycle (if None, will be estimated)
    group_columns : List[str], optional
        Columns to group by before calculations (for panel data)
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that forecasts and detects anomalies in an AnomalyPipe
    """
    def _forecast_and_detect_anomalies(pipe):
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
                
        # Validate time column
        if time_column not in df.columns:
            raise ValueError(f"Time column '{time_column}' not found in data")
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            if datetime_format:
                df[time_column] = pd.to_datetime(df[time_column], format=datetime_format)
            else:
                df[time_column] = pd.to_datetime(df[time_column])
        
        # Sort by time column
        df = df.sort_values(time_column)
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Initialize forecast storage
        forecasts = {}
        
        # Process each column
        for col in cols:
            # Create output columns
            forecast_col = f"{col}_forecast"
            lower_bound_col = f"{col}_lower"
            upper_bound_col = f"{col}_upper"""
            forecast_col = f"{col}_forecast"
            lower_bound_col = f"{col}_lower"
            upper_bound_col = f"{col}_upper"
            anomaly_flag_col = f"{col}_forecast_anomaly"
            anomaly_score_col = f"{col}_forecast_score"
            
            # Initialize result columns
            result_df[forecast_col] = np.nan
            result_df[lower_bound_col] = np.nan
            result_df[upper_bound_col] = np.nan
            result_df[anomaly_flag_col] = False
            result_df[anomaly_score_col] = np.nan
            
            # Process with or without grouping
            if group_columns is not None:
                # Check if group columns exist
                for group_col in group_columns:
                    if group_col not in df.columns:
                        raise ValueError(f"Group column '{group_col}' not found in data")
                
                # Apply forecasting to each group
                group_forecasts = {}
                
                for name, group in df.groupby(group_columns):
                    # Convert to multi-index name if needed
                    if isinstance(name, tuple):
                        group_idx = pd.MultiIndex.from_tuples([name], names=group_columns)
                        idx_match = pd.MultiIndex.from_frame(df[group_columns])
                        group_mask = idx_match.isin(group_idx)
                    else:
                        group_key = str(name)
                        group_mask = df[group_columns[0]] == name
                    
                    # Generate forecast for this group
                    forecast_result = _generate_forecast(
                        group[col], 
                        group[time_column],
                        forecast_periods,
                        model,
                        threshold,
                        seasonal_period
                    )
                    
                    if forecast_result is not None:
                        # Update result dataframe with in-sample forecasts
                        for idx, row in forecast_result['in_sample'].iterrows():
                            result_df.loc[group_mask & (result_df[time_column] == idx), forecast_col] = row['forecast']
                            result_df.loc[group_mask & (result_df[time_column] == idx), lower_bound_col] = row['lower']
                            result_df.loc[group_mask & (result_df[time_column] == idx), upper_bound_col] = row['upper']
                            result_df.loc[group_mask & (result_df[time_column] == idx), anomaly_flag_col] = row['anomaly']
                            result_df.loc[group_mask & (result_df[time_column] == idx), anomaly_score_col] = row['score']
                        
                        # Store out-of-sample forecast
                        if isinstance(name, tuple):
                            group_key = "_".join(str(x) for x in name)
                        else:
                            group_key = str(name)
                        
                        group_forecasts[group_key] = forecast_result['out_sample']
                
                # Store group forecasts
                forecasts[col] = group_forecasts
            else:
                # Apply forecasting to entire column
                forecast_result = _generate_forecast(
                    df[col], 
                    df[time_column],
                    forecast_periods,
                    model,
                    threshold,
                    seasonal_period
                )
                
                if forecast_result is not None:
                    # Update result dataframe with in-sample forecasts
                    for idx, row in forecast_result['in_sample'].iterrows():
                        result_df.loc[result_df[time_column] == idx, forecast_col] = row['forecast']
                        result_df.loc[result_df[time_column] == idx, lower_bound_col] = row['lower']
                        result_df.loc[result_df[time_column] == idx, upper_bound_col] = row['upper']
                        result_df.loc[result_df[time_column] == idx, anomaly_flag_col] = row['anomaly']
                        result_df.loc[result_df[time_column] == idx, anomaly_score_col] = row['score']
                    
                    # Store out-of-sample forecast
                    forecasts[col] = forecast_result['out_sample']
        
        # Store results
        analysis_name = f"forecast_anomalies_{model}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'forecast_anomalies',
            'model': model,
            'threshold': threshold,
            'columns': cols
        }
        new_pipe.forecasts[analysis_name] = forecasts
        new_pipe.current_analysis = analysis_name
        
        return new_pipe
    
    def _generate_forecast(series, time_series, forecast_periods, model, threshold, seasonal_period):
        """Helper function to generate forecasts and detect anomalies"""
        # Get values without NaN
        values = series.dropna()
        times = time_series.loc[values.index]
        
        if len(values) < 10:  # Need at least some data
            warnings.warn(f"Not enough data for forecasting. Need at least 10 points.")
            return None
        
        # Determine seasonal period if not provided and needed
        if seasonal_period is None and model in ['sarimax']:
            # Try to estimate from data
            if len(values) >= 20:
                # Calculate autocorrelation
                acf_values = acf(values, nlags=min(len(values)//2, 20), fft=True)
                
                # Find peaks in ACF
                potential_periods = [i for i in range(2, len(acf_values)) if acf_values[i] > acf_values[i-1] and acf_values[i] > acf_values[i+1]]
                
                if potential_periods:
                    seasonal_period = potential_periods[0]
                else:
                    # Default periods based on data frequency
                    freq = pd.infer_freq(times)
                    if freq:
                        if 'D' in freq:
                            seasonal_period = 7  # Weekly
                        elif 'H' in freq:
                            seasonal_period = 24  # Daily for hourly data
                        elif 'T' in freq or 'MIN' in freq:
                            seasonal_period = 60  # Hourly for minute data
                        elif 'M' in freq:
                            seasonal_period = 12  # Yearly for monthly data
                        else:
                            seasonal_period = 1  # No seasonality
                    else:
                        seasonal_period = 1  # No seasonality
            else:
                seasonal_period = 1  # No seasonality
        
        # Set up training and test data
        train_size = max(int(len(values) * 0.8), len(values) - forecast_periods)
        train_values = values.iloc[:train_size]
        test_values = values.iloc[train_size:]
        
        # Create DataFrames for results
        in_sample_results = pd.DataFrame(index=times)
        in_sample_results['actual'] = values
        in_sample_results['forecast'] = np.nan
        in_sample_results['lower'] = np.nan
        in_sample_results['upper'] = np.nan
        in_sample_results['anomaly'] = False
        in_sample_results['score'] = np.nan
        
        # Generate forecasts
        if model == 'arima':
            try:
                from statsmodels.tsa.arima.model import ARIMA
                
                # Fit ARIMA model
                arima_model = ARIMA(train_values, order=(1, 0, 0))
                arima_fit = arima_model.fit()
                
                # In-sample predictions
                in_sample_pred = arima_fit.predict(start=0, end=len(values)-1)
                in_sample_results['forecast'] = in_sample_pred
                
                # Get prediction standard error
                pred_std = np.sqrt(arima_fit.mse)
                
                # Calculate prediction intervals
                in_sample_results['lower'] = in_sample_pred - threshold * pred_std
                in_sample_results['upper'] = in_sample_pred + threshold * pred_std
                
                # Flag anomalies
                in_sample_results['anomaly'] = (
                    (values < in_sample_results['lower']) | 
                    (values > in_sample_results['upper'])
                )
                
                # Calculate anomaly scores
                scores = np.zeros(len(values))
                lower_anomalies = values < in_sample_results['lower']
                upper_anomalies = values > in_sample_results['upper']
                
                if np.any(lower_anomalies):
                    scores[lower_anomalies] = np.abs(
                        (values[lower_anomalies] - in_sample_results.loc[lower_anomalies, 'lower']) / pred_std
                    )
                
                if np.any(upper_anomalies):
                    scores[upper_anomalies] = np.abs(
                        (values[upper_anomalies] - in_sample_results.loc[upper_anomalies, 'upper']) / pred_std
                    )
                
                in_sample_results['score'] = scores
                
                # Generate out-of-sample forecast
                future_steps = forecast_periods
                forecast = arima_fit.forecast(steps=future_steps)
                
                # Get last timestamp and frequency
                last_time = times.iloc[-1]
                freq = pd.infer_freq(times)
                
                if freq is None:
                    # Try to estimate frequency from time gaps
                    time_diffs = np.diff(times.astype(np.int64) // 10**9)  # Convert to seconds
                    if len(time_diffs) > 0:
                        avg_diff = np.median(time_diffs)
                        if avg_diff < 60*60:  # Less than an hour
                            freq = 'T'  # Minute
                        elif avg_diff < 24*60*60:  # Less than a day
                            freq = 'H'  # Hour
                        else:
                            freq = 'D'  # Day
                    else:
                        freq = 'D'  # Default to daily
                
                # Generate future timestamps
                future_times = pd.date_range(start=last_time, periods=future_steps+1, freq=freq)[1:]
                
                # Create out-of-sample forecast DataFrame
                out_sample_results = pd.DataFrame(index=future_times)
                out_sample_results['forecast'] = forecast
                out_sample_results['lower'] = forecast - threshold * pred_std
                out_sample_results['upper'] = forecast + threshold * pred_std
                
                return {
                    'in_sample': in_sample_results,
                    'out_sample': out_sample_results
                }
                
            except Exception as e:
                warnings.warn(f"ARIMA forecasting failed: {str(e)}. Falling back to simple exponential smoothing.")
                model = 'exponential_smoothing'
        
        if model == 'exponential_smoothing':
            try:
                from statsmodels.tsa.holtwinters import ExponentialSmoothing
                
                # Determine if we can use seasonal component
                use_seasonal = seasonal_period is not None and seasonal_period > 1 and len(train_values) >= 2 * seasonal_period
                
                if use_seasonal:
                    # Check if all values are positive for multiplicative model
                    if (train_values <= 0).any():
                        # Use additive model for non-positive values
                        hw_model = ExponentialSmoothing(
                            train_values,
                            trend='add',
                            seasonal='add',
                            seasonal_periods=seasonal_period
                        )
                    else:
                        # Use multiplicative model for positive values
                        hw_model = ExponentialSmoothing(
                            train_values,
                            trend='add',
                            seasonal='mul',
                            seasonal_periods=seasonal_period
                        )
                else:
                    # No seasonality
                    hw_model = ExponentialSmoothing(
                        train_values,
                        trend='add',
                        seasonal=None
                    )
                
                # Fit model
                hw_fit = hw_model.fit()
                
                # In-sample predictions
                in_sample_pred = hw_fit.fittedvalues
                in_sample_results.loc[train_values.index, 'forecast'] = in_sample_pred
                
                # Predict for test set
                if len(test_values) > 0:
                    test_pred = hw_fit.forecast(len(test_values))
                    in_sample_results.loc[test_values.index, 'forecast'] = test_pred
                
                # Get prediction standard error
                residuals = train_values - in_sample_pred
                pred_std = np.std(residuals)
                
                # Calculate prediction intervals
                in_sample_results['lower'] = in_sample_results['forecast'] - threshold * pred_std
                in_sample_results['upper'] = in_sample_results['forecast'] + threshold * pred_std
                
                # Flag anomalies
                in_sample_results['anomaly'] = (
                    (values < in_sample_results['lower']) | 
                    (values > in_sample_results['upper'])
                )
                
                # Calculate anomaly scores
                scores = np.zeros(len(values))
                lower_anomalies = values < in_sample_results['lower']
                upper_anomalies = values > in_sample_results['upper']
                
                if np.any(lower_anomalies):
                    scores[lower_anomalies] = np.abs(
                        (values[lower_anomalies] - in_sample_results.loc[lower_anomalies, 'lower']) / pred_std
                    )
                
                if np.any(upper_anomalies):
                    scores[upper_anomalies] = np.abs(
                        (values[upper_anomalies] - in_sample_results.loc[upper_anomalies, 'upper']) / pred_std
                    )
                
                in_sample_results['score'] = scores
                
                # Generate out-of-sample forecast
                future_steps = forecast_periods
                forecast = hw_fit.forecast(future_steps)
                
                # Get last timestamp and frequency
                last_time = times.iloc[-1]
                freq = pd.infer_freq(times)
                
                if freq is None:
                    # Try to estimate frequency from time gaps
                    time_diffs = np.diff(times.astype(np.int64) // 10**9)  # Convert to seconds
                    if len(time_diffs) > 0:
                        avg_diff = np.median(time_diffs)
                        if avg_diff < 60*60:  # Less than an hour
                            freq = 'T'  # Minute
                        elif avg_diff < 24*60*60:  # Less than a day
                            freq = 'H'  # Hour
                        else:
                            freq = 'D'  # Day
                    else:
                        freq = 'D'  # Default to daily
                
                # Generate future timestamps
                future_times = pd.date_range(start=last_time, periods=future_steps+1, freq=freq)[1:]
                
                # Create out-of-sample forecast DataFrame
                out_sample_results = pd.DataFrame(index=future_times)
                out_sample_results['forecast'] = forecast
                out_sample_results['lower'] = forecast - threshold * pred_std
                out_sample_results['upper'] = forecast + threshold * pred_std
                
                return {
                    'in_sample': in_sample_results,
                    'out_sample': out_sample_results
                }
                
            except Exception as e:
                warnings.warn(f"Exponential smoothing failed: {str(e)}. Using simple moving average.")
                
                # Simple moving average fallback
                window = min(len(train_values) // 4, 7)
                if window < 2:
                    window = 2
                
                # Calculate moving average
                ma = values.rolling(window=window, min_periods=1).mean()
                in_sample_results['forecast'] = ma
                
                # Get prediction standard error
                residuals = values - ma
                pred_std = np.std(residuals.dropna())
                
                # Calculate prediction intervals
                in_sample_results['lower'] = ma - threshold * pred_std
                in_sample_results['upper'] = ma + threshold * pred_std
                
                # Flag anomalies
                in_sample_results['anomaly'] = False  # Initialize with False

                # Make sure we're comparing series with the same index
                try:
                    # Align indices for comparison
                    values_aligned, lower_aligned = values.align(in_sample_results['lower'], join='inner')
                    values_aligned, upper_aligned = values.align(in_sample_results['upper'], join='inner')
                    
                    # Now perform the comparisons safely on aligned data
                    lower_violations = values_aligned < lower_aligned
                    upper_violations = values_aligned > upper_aligned
                    
                    # Get indices where violations occurred
                    anomaly_indices = lower_violations[lower_violations].index.union(
                        upper_violations[upper_violations].index
                    )
                    
                    # Update anomaly flags
                    if not anomaly_indices.empty:
                        in_sample_results.loc[anomaly_indices, 'anomaly'] = True
                        
                except Exception as e:
                    # Fallback to a more manual approach
                    for idx in values.index:
                        if idx in in_sample_results.index:
                            val = values[idx]
                            lower = in_sample_results.loc[idx, 'lower']
                            upper = in_sample_results.loc[idx, 'upper']
                            
                            if (not pd.isna(val) and not pd.isna(lower) and val < lower) or \
                            (not pd.isna(val) and not pd.isna(upper) and val > upper):
                                in_sample_results.loc[idx, 'anomaly'] = True
                                
                                # Calculate anomaly scores
                                scores = np.zeros(len(values))
                                lower_anomalies = values < in_sample_results['lower']
                                upper_anomalies = values > in_sample_results['upper']
                
                scores = np.zeros(len(values))

                # Process anomalies one by one to avoid index mismatches
                for i, (idx, is_anomaly) in enumerate(zip(values.index, in_sample_results['anomaly'])):
                    if is_anomaly and idx in in_sample_results.index:
                        val = values[idx]
                        lower = in_sample_results.loc[idx, 'lower']
                        upper = in_sample_results.loc[idx, 'upper']
                        
                        # Calculate appropriate score
                        if not pd.isna(lower) and val < lower:
                            scores[i] = np.abs((val - lower) / pred_std)
                        elif not pd.isna(upper) and val > upper:
                            scores[i] = np.abs((val - upper) / pred_std)


                in_sample_results['score'] = scores
                
                # Generate out-of-sample forecast (naive forecast - last value)
                future_steps = forecast_periods
                forecast = np.repeat(ma.iloc[-1], future_steps)
                
                # Get last timestamp and frequency
                last_time = times.iloc[-1]
                freq = pd.infer_freq(times)
                
                if freq is None:
                    # Try to estimate frequency
                    time_diffs = np.diff(times.astype(np.int64) // 10**9)  # Convert to seconds
                    if len(time_diffs) > 0:
                        avg_diff = np.median(time_diffs)
                        if avg_diff < 60*60:  # Less than an hour
                            freq = 'T'  # Minute
                        elif avg_diff < 24*60*60:  # Less than a day
                            freq = 'H'  # Hour
                        else:
                            freq = 'D'  # Day
                    else:
                        freq = 'D'  # Default to daily
                
                # Generate future timestamps
                future_times = pd.date_range(start=last_time, periods=future_steps+1, freq=freq)[1:]
                
                # Create out-of-sample forecast DataFrame
                out_sample_results = pd.DataFrame(index=future_times)
                out_sample_results['forecast'] = forecast
                out_sample_results['lower'] = forecast - threshold * pred_std
                out_sample_results['upper'] = forecast + threshold * pred_std
                
                return {
                    'in_sample': in_sample_results,
                    'out_sample': out_sample_results
                }
        
        elif model == 'sarimax':
            try:
                from statsmodels.tsa.statespace.sarimax import SARIMAX
                
                # Determine SARIMAX parameters
                if seasonal_period is not None and seasonal_period > 1:
                    # With seasonality
                    order = (1, 0, 0)
                    seasonal_order = (1, 0, 0, seasonal_period)
                else:
                    # Without seasonality
                    order = (1, 0, 0)
                    seasonal_order = (0, 0, 0, 0)
                
                # Fit SARIMAX model
                sarimax_model = SARIMAX(
                    train_values,
                    order=order,
                    seasonal_order=seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
                sarimax_fit = sarimax_model.fit(disp=False)
                
                # In-sample predictions
                in_sample_pred = sarimax_fit.get_prediction(start=0, end=len(values)-1).predicted_mean
                in_sample_results['forecast'] = in_sample_pred
                
                # Get prediction intervals
                pred_ci = sarimax_fit.get_prediction(start=0, end=len(values)-1).conf_int(alpha=1-0.95)
                
                # Calculate prediction standard error
                pred_std = (pred_ci.iloc[:, 1] - pred_ci.iloc[:, 0]) / (2 * 1.96)  # Using 95% CI to estimate std
                
                # Calculate prediction intervals
                in_sample_results['lower'] = in_sample_pred - threshold * pred_std
                in_sample_results['upper'] = in_sample_pred + threshold * pred_std
                
                # Flag anomalies
                in_sample_results['anomaly'] = (
                    (values < in_sample_results['lower']) | 
                    (values > in_sample_results['upper'])
                )
                
                # Calculate anomaly scores
                scores = np.zeros(len(values))
                lower_anomalies = values < in_sample_results['lower']
                upper_anomalies = values > in_sample_results['upper']
                
                if np.any(lower_anomalies):
                    scores[lower_anomalies] = np.abs(
                        (values[lower_anomalies] - in_sample_results.loc[lower_anomalies, 'lower']) / pred_std
                    )
                
                if np.any(upper_anomalies):
                    scores[upper_anomalies] = np.abs(
                        (values[upper_anomalies] - in_sample_results.loc[upper_anomalies, 'upper']) / pred_std
                    )
                
                in_sample_results['score'] = scores
                
                # Generate out-of-sample forecast
                future_steps = forecast_periods
                forecast = sarimax_fit.get_forecast(steps=future_steps)
                pred_mean = forecast.predicted_mean
                pred_ci = forecast.conf_int(alpha=1-0.95)
                
                # Get last timestamp and frequency
                last_time = times.iloc[-1]
                freq = pd.infer_freq(times)
                
                if freq is None:
                    # Try to estimate frequency
                    time_diffs = np.diff(times.astype(np.int64) // 10**9)  # Convert to seconds
                    if len(time_diffs) > 0:
                        avg_diff = np.median(time_diffs)
                        if avg_diff < 60*60:  # Less than an hour
                            freq = 'T'  # Minute
                        elif avg_diff < 24*60*60:  # Less than a day
                            freq = 'H'  # Hour
                        else:
                            freq = 'D'  # Day
                    else:
                        freq = 'D'  # Default to daily
                
                # Generate future timestamps
                future_times = pd.date_range(start=last_time, periods=future_steps+1, freq=freq)[1:]
                
                # Create out-of-sample forecast DataFrame
                out_sample_results = pd.DataFrame(index=future_times)
                out_sample_results['forecast'] = pred_mean.values
                out_sample_results['lower'] = pred_ci.iloc[:, 0].values
                out_sample_results['upper'] = pred_ci.iloc[:, 1].values
                
                return {
                    'in_sample': in_sample_results,
                    'out_sample': out_sample_results
                }
                
            except Exception as e:
                warnings.warn(f"SARIMAX forecasting failed: {str(e)}. Falling back to exponential smoothing.")
                # Fall back to exponential smoothing
                return _generate_forecast(series, time_series, forecast_periods, 'exponential_smoothing', threshold, seasonal_period)
        
        else:
            raise ValueError(f"Unknown forecasting model: {model}")
    
    return _forecast_and_detect_anomalies


def batch_detect_anomalies(
    columns: Union[str, List[str]],
    methods: List[Dict[str, Any]],
    ensemble_method: str = 'any',
    output_suffix: str = '_ensemble_anomaly'
):
    """
    Apply multiple anomaly detection methods and combine results
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to analyze for anomalies
    methods : List[Dict[str, Any]]
        List of method configurations, each with:
        - 'name': Method name (e.g., 'statistical_outliers', 'contextual_anomalies')
        - 'params': Parameters for the method
    ensemble_method : str, default='any'
        How to combine results: 'any' (union), 'all' (intersection), 'majority', 'weighted'
    output_suffix : str, default='_ensemble_anomaly'
        Suffix for output anomaly flag columns
        
    Returns:
    --------
    Callable
        Function that applies multiple anomaly detection methods in an AnomalyPipe
    """
    def _batch_detect_anomalies(pipe):
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
        
        # Create copy of dataframe to store results
        result_df = df.copy()
        
        # Apply each method
        method_results = {}
        
        for method_config in methods:
            method_name = method_config['name']
            method_params = method_config.get('params', {})
            
            # Apply the method
            method_func = None
            
            if method_name == 'statistical_outliers':
                method_func = detect_statistical_outliers(**method_params)
            elif method_name == 'contextual_anomalies':
                method_func = detect_contextual_anomalies(**method_params)
            elif method_name == 'collective_anomalies':
                method_func = detect_collective_anomalies(**method_params)
            elif method_name == 'seasonal_residuals':
                method_func = calculate_seasonal_residuals(**method_params)
            elif method_name == 'residual_anomalies':
                method_func = detect_anomalies_from_residuals(**method_params)
            elif method_name == 'forecast_anomalies':
                method_func = forecast_and_detect_anomalies(**method_params)
            else:
                raise ValueError(f"Unknown method: {method_name}")
            
            # Apply the method to get anomaly flags
            method_pipe = method_func(new_pipe.copy())
            
            # Store the relevant result columns
            method_results[method_name] = {}
            
            for col in cols:
                # Find anomaly flag columns for this method and column
                method_flags = {}
                method_scores = {}
                
                for result_col in method_pipe.data.columns:
                    if col in result_col and 'anomaly' in result_col.lower() and not result_col.startswith('_'):
                        method_flags[result_col] = method_pipe.data[result_col]
                    elif col in result_col and 'score' in result_col.lower() and not result_col.startswith('_'):
                        method_scores[result_col] = method_pipe.data[result_col]
                
                method_results[method_name][col] = {
                    'flags': method_flags,
                    'scores': method_scores
                }
        
        # Combine results for each column
        for col in cols:
            # Collect all anomaly flags for this column
            all_flags = {}
            all_scores = {}
            
            for method_name, method_result in method_results.items():
                if col in method_result:
                    all_flags.update(method_result[col]['flags'])
                    all_scores.update(method_result[col]['scores'])
            
            # Create ensemble anomaly flag
            ensemble_flag_col = f"{col}{output_suffix}"
            ensemble_score_col = f"{col}_ensemble_score"
            
            # Initialize result columns
            result_df[ensemble_flag_col] = False
            result_df[ensemble_score_col] = 0.0
            
            # Skip if no results
            if not all_flags:
                warnings.warn(f"No anomaly detection results found for column '{col}'")
                continue
            
            # Convert flags to DataFrame for easier processing
            flags_df = pd.DataFrame(all_flags)
            scores_df = pd.DataFrame(all_scores)
            
            # Apply ensemble method
            if ensemble_method == 'any':
                # Union of all methods - if any method flags as anomaly
                result_df[ensemble_flag_col] = flags_df.any(axis=1)
                
                # Use maximum score
                if not scores_df.empty:
                    result_df[ensemble_score_col] = scores_df.max(axis=1)
                
            elif ensemble_method == 'all':
                # Intersection of all methods - only if all methods flag as anomaly
                result_df[ensemble_flag_col] = flags_df.all(axis=1)
                
                # Use minimum score
                if not scores_df.empty:
                    result_df[ensemble_score_col] = scores_df.min(axis=1)
                
            elif ensemble_method == 'majority':
                # Majority vote - if more than half of methods flag as anomaly
                result_df[ensemble_flag_col] = (flags_df.sum(axis=1) > flags_df.shape[1] / 2)
                
                # Use average score
                if not scores_df.empty:
                    result_df[ensemble_score_col] = scores_df.mean(axis=1)
                
            elif ensemble_method == 'weighted':
                # Weighted vote - based on scores
                if not scores_df.empty:
                    # Normalize scores to 0-1 range
                    normalized_scores = scores_df.apply(lambda x: (x - x.min()) / (x.max() - x.min()) if x.max() > x.min() else x)
                    
                    # Calculate weighted sum
                    result_df[ensemble_score_col] = normalized_scores.mean(axis=1)
                    
                    # Flag as anomaly if weighted score is above threshold
                    result_df[ensemble_flag_col] = result_df[ensemble_score_col] > 0.6  # Adjustable threshold
                else:
                    # Fallback to majority vote if no scores available
                    result_df[ensemble_flag_col] = (flags_df.sum(axis=1) > flags_df.shape[1] / 2)
            
            else:
                raise ValueError(f"Unknown ensemble method: {ensemble_method}")
        
        # Store results
        analysis_name = f"ensemble_anomalies_{ensemble_method}"
        new_pipe.data = result_df
        new_pipe.anomaly_results[analysis_name] = {
            'type': 'ensemble_anomalies',
            'methods': [m['name'] for m in methods],
            'ensemble_method': ensemble_method,
            'columns': cols
        }
        new_pipe.current_analysis = analysis_name        
        return new_pipe
    
    return _batch_detect_anomalies

