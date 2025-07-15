import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
import warnings
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from scipy import stats


class TrendPipe:
    """
    A pipeline-style trend analysis tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
        self.time_aggregations = {}
        self.trend_results = {}
        self.trend_decompositions = {}
        self.forecasts = {}
        self.current_analysis = None
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe TrendPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = TrendPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        new_pipe.time_aggregations = self.time_aggregations.copy()
        new_pipe.trend_results = self.trend_results.copy()
        new_pipe.trend_decompositions = self.trend_decompositions.copy()
        new_pipe.forecasts = self.forecasts.copy()
        new_pipe.current_analysis = self.current_analysis
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create a TrendPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        return pipe


def aggregate_by_time(
    date_column: str,
    metric_columns: List[str],
    time_period: str = 'D',
    aggregation: Union[str, Dict[str, str]] = 'mean',
    fill_missing: bool = True,
    include_current_period: bool = False,
    time_name: str = 'time',
    datetime_format: Optional[str] = None
):
    """
    Aggregate data by time periods
    
    Parameters:
    -----------
    date_column : str
        Column containing the date to aggregate by
    metric_columns : List[str]
        Columns containing metrics to analyze
    time_period : str, default='D'
        Time period for aggregation ('D' for daily, 'W' for weekly, 'M' for monthly, 'Q' for quarterly, 'Y' for yearly)
    aggregation : str or Dict[str, str], default='mean'
        Aggregation method (mean, sum, count, min, max) or dict mapping columns to methods
    fill_missing : bool, default=True
        Whether to fill in missing time periods with NaN
    include_current_period : bool, default=False
        Whether to include the current (potentially incomplete) time period
    time_name : str, default='time'
        Name to use for the time column in the result
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that aggregates data by time periods
    """
    def _aggregate_by_time(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            if datetime_format:
                df[date_column] = pd.to_datetime(df[date_column], format=datetime_format)
            else:
                df[date_column] = pd.to_datetime(df[date_column])
        
        # Get all metrics to aggregate
        all_metrics = metric_columns.copy()
        
        # Create time period column for grouping
        df['_time_period'] = df[date_column].dt.to_period(time_period)
        
        # Get current time period for filtering if needed
        now = pd.Timestamp.now()
        current_period = now.to_period(time_period)
        
        # Filter out current (incomplete) period if requested
        if not include_current_period:
            df = df[df['_time_period'] < current_period]
        
        # Determine aggregation methods for each column
        if isinstance(aggregation, str):
            # Use the same method for all columns
            agg_methods = {col: aggregation for col in all_metrics}
        else:
            # Use the specified method for each column, with a default
            agg_methods = {col: aggregation.get(col, 'mean') for col in all_metrics}
        
        # Aggregate by time period
        grouped = df.groupby('_time_period')[all_metrics].agg(agg_methods)
        
        # Fill in missing time periods if requested
        if fill_missing:
            # Create a complete time range
            min_period = grouped.index.min()
            max_period = grouped.index.max()
            
            if min_period is not None and max_period is not None:
                full_range = pd.period_range(start=min_period, end=max_period, freq=time_period)
                grouped = grouped.reindex(full_range)
        
        # Convert PeriodIndex to DatetimeIndex for easier plotting
        grouped.index = grouped.index.to_timestamp()
        
        # Rename the index
        grouped.index.name = time_name
        
        # Store the result
        new_pipe.time_aggregations[time_name] = {
            'time_period': time_period,
            'aggregation': aggregation,
            'data': grouped
        }
        
        new_pipe.current_analysis = time_name
        
        return new_pipe
    
    return _aggregate_by_time


def calculate_growth_rates(
    window: Optional[int] = None,
    annualize: bool = False,
    method: str = 'percentage'
):
    """
    Calculate growth rates for aggregated metrics
    
    Parameters:
    -----------
    window : int, optional
        Window size for growth rate calculation (if None, compare to previous period)
    annualize : bool, default=False
        Whether to annualize growth rates (useful for comparing different time periods)
    method : str, default='percentage'
        Method for calculating growth ('percentage', 'log', or 'cagr')
        
    Returns:
    --------
    Callable
        Function that calculates growth rates
    """
    def _calculate_growth_rates(pipe):
        if pipe.current_analysis is None or pipe.current_analysis not in pipe.time_aggregations:
            raise ValueError("No time aggregation found. Call aggregate_by_time() first.")
        
        new_pipe = pipe.copy()
        agg_data = new_pipe.time_aggregations[new_pipe.current_analysis]
        df = agg_data['data']
        time_period = agg_data['time_period']
        
        # Create a new dataframe for growth rates
        growth_df = pd.DataFrame(index=df.index)
        
        # Calculate periods per year for annualization
        if annualize:
            if time_period == 'D':
                periods_per_year = 365.25
            elif time_period == 'W':
                periods_per_year = 52.143
            elif time_period == 'M':
                periods_per_year = 12
            elif time_period == 'Q':
                periods_per_year = 4
            elif time_period == 'Y':
                periods_per_year = 1
            else:
                periods_per_year = 1
                warnings.warn(f"Unknown time period '{time_period}'. Using 1 period per year for annualization.")
        
        # Calculate growth rates for each column
        for col in df.columns:
            if window is None:
                # Compare to previous period
                prev_values = df[col].shift(1)
                
                if method == 'percentage':
                    growth = (df[col] / prev_values) - 1
                elif method == 'log':
                    growth = np.log(df[col] / prev_values)
                elif method == 'cagr':
                    # CAGR doesn't make sense for period-to-period
                    growth = (df[col] / prev_values) - 1
                else:
                    raise ValueError(f"Unknown growth method: {method}")
            else:
                # Compare to value 'window' periods ago
                prev_values = df[col].shift(window)
                
                if method == 'percentage':
                    growth = (df[col] / prev_values) - 1
                    if annualize:
                        growth = (1 + growth) ** (periods_per_year / window) - 1
                elif method == 'log':
                    growth = np.log(df[col] / prev_values)
                    if annualize:
                        growth = growth * (periods_per_year / window)
                elif method == 'cagr':
                    # CAGR is already "annualized" in a sense
                    growth = (df[col] / prev_values) ** (1 / window) - 1
                    if annualize:
                        growth = (1 + growth) ** periods_per_year - 1
                else:
                    raise ValueError(f"Unknown growth method: {method}")
            
            growth_df[f"{col}_growth"] = growth
        
        # Store the result
        analysis_name = f"{new_pipe.current_analysis}_growth"
        new_pipe.trend_results[analysis_name] = {
            'type': 'growth',
            'window': window,
            'annualize': annualize,
            'method': method,
            'data': growth_df
        }
        
        return new_pipe
    
    return _calculate_growth_rates


def calculate_moving_average(
    window: int = 7,
    method: str = 'simple',
    center: bool = False
):
    """
    Calculate moving averages for aggregated metrics
    
    Parameters:
    -----------
    window : int, default=7
        Window size for moving average
    method : str, default='simple'
        Method for calculating moving average ('simple', 'weighted', or 'exponential')
    center : bool, default=False
        Whether to center the window (for simple and weighted)
        
    Returns:
    --------
    Callable
        Function that calculates moving averages
    """
    def _calculate_moving_average(pipe):
        if pipe.current_analysis is None or pipe.current_analysis not in pipe.time_aggregations:
            raise ValueError("No time aggregation found. Call aggregate_by_time() first.")
        
        new_pipe = pipe.copy()
        agg_data = new_pipe.time_aggregations[new_pipe.current_analysis]
        df = agg_data['data']
        
        # Create a new dataframe for moving averages
        ma_df = pd.DataFrame(index=df.index)
        
        # Calculate moving averages for each column
        for col in df.columns:
            if method == 'simple':
                ma_df[f"{col}_ma"] = df[col].rolling(window=window, center=center).mean()
            elif method == 'weighted':
                # Linear weights (more weight to recent values)
                weights = np.arange(1, window + 1)
                ma_df[f"{col}_ma"] = df[col].rolling(window=window, center=center).apply(
                    lambda x: np.sum(weights * x) / np.sum(weights), raw=True
                )
            elif method == 'exponential':
                # Alpha = 2/(window+1) is a common rule of thumb
                alpha = 2 / (window + 1)
                ma_df[f"{col}_ma"] = df[col].ewm(alpha=alpha, adjust=False).mean()
            else:
                raise ValueError(f"Unknown moving average method: {method}")
        
        # Store the result
        analysis_name = f"{new_pipe.current_analysis}_ma"
        new_pipe.trend_results[analysis_name] = {
            'type': 'moving_average',
            'window': window,
            'method': method,
            'center': center,
            'data': ma_df
        }
        
        return new_pipe
    
    return _calculate_moving_average


def decompose_trend(
    metric_column: str,
    model: str = 'additive',
    period: Optional[int] = None,
    extrapolate_trend: Optional[int] = None
):
    """
    Decompose time series into trend, seasonal, and residual components
    
    Parameters:
    -----------
    metric_column : str
        Column to decompose
    model : str, default='additive'
        Type of seasonal component ('additive' or 'multiplicative')
    period : int, optional
        Number of periods in a seasonal cycle (if None, will be estimated)
    extrapolate_trend : int, optional
        Number of periods to extrapolate the trend into the future
        
    Returns:
    --------
    Callable
        Function that decomposes time series
    """
    def _decompose_trend(pipe):
        if pipe.current_analysis is None or pipe.current_analysis not in pipe.time_aggregations:
            raise ValueError("No time aggregation found. Call aggregate_by_time() first.")
        
        new_pipe = pipe.copy()
        agg_data = new_pipe.time_aggregations[new_pipe.current_analysis]
        df = agg_data['data']
        time_period = agg_data['time_period']
        
        # Check if the metric column exists
        if metric_column not in df.columns:
            raise ValueError(f"Metric column '{metric_column}' not found in aggregated data")
        
        # Fill any missing values for decomposition
        series = df[metric_column].copy()
        if series.isnull().any():
            series = series.interpolate(method='linear')
        
        # Determine period if not provided
        decomp_period = period  # Use local variable to avoid UnboundLocalError
        if decomp_period is None:
            # Estimate based on time period
            if time_period == 'D':
                est_period = 7  # Weekly
            elif time_period == 'W':
                est_period = 52  # Yearly
            elif time_period == 'M':
                est_period = 12  # Yearly
            elif time_period == 'Q':
                est_period = 4  # Yearly
            else:
                est_period = 1  # No seasonality
            
            # Check if we have enough data
            if len(series) >= 2 * est_period:
                decomp_period = est_period
            else:
                # Not enough data for seasonal decomposition
                warnings.warn(
                    f"Not enough data for seasonal decomposition with estimated period {est_period}. "
                    "Using simple trend estimation instead."
                )
                
                # Just fit a line instead
                x = np.arange(len(series))
                mask = ~np.isnan(series)
                slope, intercept, _, _, _ = stats.linregress(x[mask], series[mask])
                trend = pd.Series(intercept + slope * x, index=series.index)
                
                # Store the result
                analysis_name = f"{new_pipe.current_analysis}_{metric_column}_decomp"
                new_pipe.trend_decompositions[analysis_name] = {
                    'type': 'linear',
                    'metric': metric_column,
                    'trend': trend,
                    'seasonal': pd.Series(0, index=series.index),
                    'residual': series - trend,
                    'model': 'additive',
                    'slope': slope,
                    'intercept': intercept
                }
                
                # Extrapolate if requested
                if extrapolate_trend is not None and extrapolate_trend > 0:
                    # Create future dates
                    last_date = series.index[-1]
                    if time_period == 'D':
                        future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=extrapolate_trend, freq='D')
                    elif time_period == 'W':
                        future_dates = pd.date_range(start=last_date + timedelta(days=7), periods=extrapolate_trend, freq='W')
                    elif time_period == 'M':
                        future_dates = pd.date_range(start=last_date + timedelta(days=31), periods=extrapolate_trend, freq='M')
                    elif time_period == 'Q':
                        future_dates = pd.date_range(start=last_date + timedelta(days=92), periods=extrapolate_trend, freq='Q')
                    elif time_period == 'Y':
                        future_dates = pd.date_range(start=last_date + timedelta(days=366), periods=extrapolate_trend, freq='Y')
                    
                    # Calculate future trend values
                    future_x = np.arange(len(series), len(series) + extrapolate_trend)
                    future_trend = intercept + slope * future_x
                    
                    # Create forecast dataframe
                    forecast_df = pd.DataFrame({
                        'forecast': future_trend,
                        'trend': future_trend,
                        'seasonal': np.zeros(len(future_dates)),
                    }, index=future_dates)
                    
                    # Store the forecast
                    new_pipe.forecasts[analysis_name] = forecast_df
                
                return new_pipe
        
        # Perform seasonal decomposition
        try:
            decomposition = seasonal_decompose(
                series, 
                model=model, 
                period=decomp_period,
                extrapolate_trend='freq'
            )
            
            # Store the result
            analysis_name = f"{new_pipe.current_analysis}_{metric_column}_decomp"
            new_pipe.trend_decompositions[analysis_name] = {
                'type': 'seasonal',
                'metric': metric_column,
                'trend': decomposition.trend,
                'seasonal': decomposition.seasonal,
                'residual': decomposition.resid,
                'model': model,
                'period': decomp_period
            }
            
            # Extrapolate if requested
            if extrapolate_trend is not None and extrapolate_trend > 0:
                # Get the last trend value and seasonal pattern
                last_trend = decomposition.trend.iloc[-1]
                
                # Calculate trend slope (average of last 5 periods)
                trend_series = decomposition.trend.dropna()
                if len(trend_series) >= 6:
                    recent_trend = trend_series.iloc[-6:]
                    x = np.arange(len(recent_trend))
                    slope, _, _, _, _ = stats.linregress(x, recent_trend)
                else:
                    # Use the overall trend
                    x = np.arange(len(trend_series))
                    slope, _, _, _, _ = stats.linregress(x, trend_series)
                
                # Create future dates
                last_date = series.index[-1]
                if time_period == 'D':
                    future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=extrapolate_trend, freq='D')
                elif time_period == 'W':
                    future_dates = pd.date_range(start=last_date + timedelta(days=7), periods=extrapolate_trend, freq='W')
                elif time_period == 'M':
                    future_dates = pd.date_range(start=last_date + timedelta(days=31), periods=extrapolate_trend, freq='M')
                elif time_period == 'Q':
                    future_dates = pd.date_range(start=last_date + timedelta(days=92), periods=extrapolate_trend, freq='Q')
                elif time_period == 'Y':
                    future_dates = pd.date_range(start=last_date + timedelta(days=366), periods=extrapolate_trend, freq='Y')
                
                # Calculate future trend values
                future_trend = [last_trend + slope * (i + 1) for i in range(extrapolate_trend)]
                
                # Calculate future seasonal values
                if len(decomposition.seasonal) >= decomp_period:
                    # Extract seasonal pattern
                    last_cycle = decomposition.seasonal.iloc[-decomp_period:].values
                    # Repeat the pattern for the forecast period
                    future_seasonal = np.tile(last_cycle, extrapolate_trend // decomp_period + 1)[:extrapolate_trend]
                else:
                    # Not enough data for seasonal pattern
                    future_seasonal = np.zeros(extrapolate_trend)
                
                # Calculate forecast
                if model == 'additive':
                    forecast = [t + s for t, s in zip(future_trend, future_seasonal)]
                else:  # multiplicative
                    forecast = [t * s for t, s in zip(future_trend, future_seasonal)]
                
                # Create forecast dataframe
                forecast_df = pd.DataFrame({
                    'forecast': forecast,
                    'trend': future_trend,
                    'seasonal': future_seasonal,
                }, index=future_dates)
                
                # Store the forecast
                new_pipe.forecasts[analysis_name] = forecast_df
            
        except Exception as e:
            warnings.warn(f"Error in seasonal decomposition: {str(e)}. Using simple trend estimation instead.")
            
            # Just fit a line instead
            x = np.arange(len(series))
            mask = ~np.isnan(series)
            slope, intercept, _, _, _ = stats.linregress(x[mask], series[mask])
            trend = pd.Series(intercept + slope * x, index=series.index)
            
            # Store the result
            analysis_name = f"{new_pipe.current_analysis}_{metric_column}_decomp"
            new_pipe.trend_decompositions[analysis_name] = {
                'type': 'linear',
                'metric': metric_column,
                'trend': trend,
                'seasonal': pd.Series(0, index=series.index),
                'residual': series - trend,
                'model': 'additive',
                'slope': slope,
                'intercept': intercept
            }
            
            # Extrapolate if requested
            if extrapolate_trend is not None and extrapolate_trend > 0:
                # Create future dates
                last_date = series.index[-1]
                if time_period == 'D':
                    future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=extrapolate_trend, freq='D')
                elif time_period == 'W':
                    future_dates = pd.date_range(start=last_date + timedelta(days=7), periods=extrapolate_trend, freq='W')
                elif time_period == 'M':
                    future_dates = pd.date_range(start=last_date + timedelta(days=31), periods=extrapolate_trend, freq='M')
                elif time_period == 'Q':
                    future_dates = pd.date_range(start=last_date + timedelta(days=92), periods=extrapolate_trend, freq='Q')
                elif time_period == 'Y':
                    future_dates = pd.date_range(start=last_date + timedelta(days=366), periods=extrapolate_trend, freq='Y')
                
                # Calculate future trend values
                future_x = np.arange(len(series), len(series) + extrapolate_trend)
                future_trend = intercept + slope * future_x
                
                # Create forecast dataframe
                forecast_df = pd.DataFrame({
                    'forecast': future_trend,
                    'trend': future_trend,
                    'seasonal': np.zeros(len(future_dates)),
                }, index=future_dates)
                
                # Store the forecast
                new_pipe.forecasts[analysis_name] = forecast_df
        
        return new_pipe
    
    return _decompose_trend


def forecast_metric(
    metric_column: str,
    fperiods: int = 12,
    fmethod: str = 'holt_winters',
    seasonal_periods: Optional[int] = None,
    confidence_interval: float = 0.95
):
    """
    Forecast future values of a metric
    
    Parameters:
    -----------
    metric_column : str
        Column to forecast
    periods : int, default=12
        Number of periods to forecast
    method : str, default='holt_winters'
        Forecasting method ('holt_winters', 'linear', 'exponential')
    seasonal_periods : int, optional
        Number of periods in a seasonal cycle (if None, will be estimated)
    confidence_interval : float, default=0.95
        Confidence level for prediction intervals
        
    Returns:
    --------
    Callable
        Function that forecasts future values
    """
    def _forecast_metric(pipe):
        if pipe.current_analysis is None or pipe.current_analysis not in pipe.time_aggregations:
            raise ValueError("No time aggregation found. Call aggregate_by_time() first.")
        
        periods = fperiods
        method = fmethod
        new_pipe = pipe.copy()
        agg_data = new_pipe.time_aggregations[new_pipe.current_analysis]
        df = agg_data['data']
        time_period = agg_data['time_period']
        
        # Check if the metric column exists
        if metric_column not in df.columns:
            raise ValueError(f"Metric column '{metric_column}' not found in aggregated data")
        
        # Fill any missing values for forecasting
        series = df[metric_column].copy()
        if series.isnull().any():
            series = series.interpolate(method='linear')
        
        # Determine seasonal periods if not provided
        forecast_seasonal_period = seasonal_periods  # Use local variable to avoid UnboundLocalError
        if forecast_seasonal_period is None and method == 'holt_winters':
            # Estimate based on time period
            if time_period == 'D':
                forecast_seasonal_period = 7  # Weekly
            elif time_period == 'W':
                forecast_seasonal_period = 52  # Yearly
            elif time_period == 'M':
                forecast_seasonal_period = 12  # Yearly
            elif time_period == 'Q':
                forecast_seasonal_period = 4  # Yearly
            else:
                forecast_seasonal_period = 1  # No seasonality
        
        # Generate forecast
        if method == 'holt_winters':
            try:
                # Need at least 2 full seasons of data
                if len(series) >= 2 * forecast_seasonal_period:
                    # Check if all values are positive for multiplicative model
                    if (series <= 0).any():
                        # Use additive model for negative values
                        model = ExponentialSmoothing(
                            series,
                            trend='add',
                            seasonal='add',
                            seasonal_periods=forecast_seasonal_period
                        )
                    else:
                        # Use multiplicative model for strictly positive values
                        model = ExponentialSmoothing(
                            series,
                            trend='add',
                            seasonal='mul',
                            seasonal_periods=forecast_seasonal_period
                        )
                else:
                    # Not enough data for seasonal model
                    model = ExponentialSmoothing(series, trend='add', seasonal=None)
                
                # Fit and forecast
                fit_model = model.fit()
                forecast = fit_model.forecast(periods)
                
                # Get prediction intervals
                z = stats.norm.ppf((1 + confidence_interval) / 2)
                pred_intervals = fit_model.get_prediction(pd.date_range(
                    start=series.index[-1] + pd.Timedelta(days=1),
                    periods=periods,
                    freq=time_period
                ))
                
                if hasattr(pred_intervals, 'conf_int'):
                    # statsmodels 0.13+
                    lower = pred_intervals.conf_int()[:, 0]
                    upper = pred_intervals.conf_int()[:, 1]
                else:
                    # Manual calculation
                    sigma = np.sqrt(fit_model.sse / (len(series) - len(fit_model.params)))
                    lower = forecast - z * sigma
                    upper = forecast + z * sigma
            except Exception as e:
                warnings.warn(f"Error in Holt-Winters forecasting: {str(e)}. Using linear trend instead.")
                method = 'linear'
        
        if method == 'linear':
            # Fit a linear trend
            x = np.arange(len(series))
            mask = ~np.isnan(series)
            slope, intercept, _, _, _ = stats.linregress(x[mask], series[mask])
            
            # Generate forecast
            future_x = np.arange(len(series), len(series) + periods)
            forecast = pd.Series(intercept + slope * future_x)
            
            # Calculate prediction intervals
            y_hat = intercept + slope * x[mask]
            n = len(x[mask])
            
            # Standard error of the regression
            se = np.sqrt(np.sum((series[mask] - y_hat) ** 2) / (n - 2))
            
            # Standard error of the prediction
            x_mean = np.mean(x[mask])
            x_var = np.sum((x[mask] - x_mean) ** 2)
            
            lower = []
            upper = []
            z = stats.t.ppf((1 + confidence_interval) / 2, n - 2)
            
            for x_i in future_x:
                se_pred = se * np.sqrt(1 + 1/n + (x_i - x_mean)**2 / x_var)
                lower.append(intercept + slope * x_i - z * se_pred)
                upper.append(intercept + slope * x_i + z * se_pred)
        
        elif method == 'exponential':
            # Check if all values are positive
            if (series <= 0).any():
                warnings.warn("Exponential forecasting requires positive values. Using linear trend instead.")
                method = 'linear'
                
                # Fit a linear trend
                x = np.arange(len(series))
                mask = ~np.isnan(series)
                slope, intercept, _, _, _ = stats.linregress(x[mask], series[mask])
                
                # Generate forecast
                future_x = np.arange(len(series), len(series) + periods)
                forecast = pd.Series(intercept + slope * future_x)
                
                # Calculate prediction intervals
                y_hat = intercept + slope * x[mask]
                n = len(x[mask])
                
                # Standard error of the regression
                se = np.sqrt(np.sum((series[mask] - y_hat) ** 2) / (n - 2))
                
                # Standard error of the prediction
                x_mean = np.mean(x[mask])
                x_var = np.sum((x[mask] - x_mean) ** 2)
                
                lower = []
                upper = []
                z = stats.t.ppf((1 + confidence_interval) / 2, n - 2)
                
                for x_i in future_x:
                    se_pred = se * np.sqrt(1 + 1/n + (x_i - x_mean)**2 / x_var)
                    lower.append(intercept + slope * x_i - z * se_pred)
                    upper.append(intercept + slope * x_i + z * se_pred)
            else:
                # Fit an exponential trend (linear in log space)
                log_series = np.log(series)
                x = np.arange(len(log_series))
                mask = ~np.isnan(log_series)
                slope, intercept, _, _, _ = stats.linregress(x[mask], log_series[mask])
                
                # Generate forecast in log space
                future_x = np.arange(len(log_series), len(log_series) + periods)
                log_forecast = intercept + slope * future_x
                
                # Convert back to original scale
                forecast = pd.Series(np.exp(log_forecast))
                
                # Calculate prediction intervals in log space
                y_hat = intercept + slope * x[mask]
                n = len(x[mask])
                
                # Standard error of the regression
                se = np.sqrt(np.sum((log_series[mask] - y_hat) ** 2) / (n - 2))
                
                # Standard error of the prediction
                x_mean = np.mean(x[mask])
                x_var = np.sum((x[mask] - x_mean) ** 2)
                
                lower = []
                upper = []
                z = stats.t.ppf((1 + confidence_interval) / 2, n - 2)
                
                for x_i in future_x:
                    se_pred = se * np.sqrt(1 + 1/n + (x_i - x_mean)**2 / x_var)
                    log_lower = intercept + slope * x_i - z * se_pred
                    log_upper = intercept + slope * x_i + z * se_pred
                    lower.append(np.exp(log_lower))
                    upper.append(np.exp(log_upper))
        
        # Create future dates
        last_date = series.index[-1]
        if time_period == 'D':
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=periods, freq='D')
        elif time_period == 'W':
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=7), periods=periods, freq='W')
        elif time_period == 'M':
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=31), periods=periods, freq='MS')
        elif time_period == 'Q':
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=92), periods=periods, freq='QS')
        elif time_period == 'Y':
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=366), periods=periods, freq='YS')
        else:
            # Default to daily if unknown
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=periods, freq='D')
        
        # Create forecast dataframe
        forecast_df = pd.DataFrame({
            'forecast': forecast.values,
            'lower': lower,
            'upper': upper
        }, index=future_dates)
        
        # Store the result
        analysis_name = f"{new_pipe.current_analysis}_{metric_column}_forecast"
        new_pipe.forecasts[analysis_name] = {
            'type': 'forecast',
            'method': method,
            'metric': metric_column,
            'data': forecast_df,
            'confidence_interval': confidence_interval
        }
        
        return new_pipe
    
    return _forecast_metric

def calculate_statistical_trend(
    metric_column: str,
    test_method: str = 'mann_kendall',
    alpha: float = 0.05,
    window: Optional[int] = None
):
    """
    Calculate statistical significance of trends
    
    Parameters:
    -----------
    metric_column : str
        Column to test for trend
    test_method : str, default='mann_kendall'
        Statistical test method ('mann_kendall', 't_test', 'spearman')
    alpha : float, default=0.05
        Significance level
    window : int, optional
        Window size for rolling trend analysis (if None, test the entire series)
        
    Returns:
    --------
    Callable
        Function that tests for statistical trends
    """
    def _calculate_statistical_trend(pipe):
        if pipe.current_analysis is None or pipe.current_analysis not in pipe.time_aggregations:
            raise ValueError("No time aggregation found. Call aggregate_by_time() first.")
        
        new_pipe = pipe.copy()
        agg_data = new_pipe.time_aggregations[new_pipe.current_analysis]
        df = agg_data['data']
        
        # Check if the metric column exists
        if metric_column not in df.columns:
            raise ValueError(f"Metric column '{metric_column}' not found in aggregated data")
        
        # Fill any missing values for trend testing
        series = df[metric_column].copy()
        if series.isnull().any():
            series = series.interpolate(method='linear')
        
        if window is None:
            # Test the entire series
            result = _test_trend(series, test_method, alpha)
            
            # Store the result
            analysis_name = f"{new_pipe.current_analysis}_{metric_column}_trend"
            new_pipe.trend_results[analysis_name] = {
                'type': 'statistical_trend',
                'method': test_method,
                'metric': metric_column,
                'trend': result['trend'],
                'p_value': result['p_value'],
                'significant': result['significant'],
                'slope': result.get('slope', None),
                'alpha': alpha
            }
        else:
            # Calculate rolling trend
            rolling_results = []
            for i in range(len(series) - window + 1):
                if i + window <= len(series):
                    window_series = series.iloc[i:i+window]
                    window_time = series.index[i+window-1]  # End of window
                    result = _test_trend(window_series, test_method, alpha)
                    rolling_results.append({
                        'time': window_time,
                        'trend': result['trend'],
                        'p_value': result['p_value'],
                        'significant': result['significant'],
                        'slope': result.get('slope', None)
                    })
            
            # Create rolling trend dataframe
            rolling_df = pd.DataFrame(rolling_results)
            
            # Store the result
            analysis_name = f"{new_pipe.current_analysis}_{metric_column}_rolling_trend"
            new_pipe.trend_results[analysis_name] = {
                'type': 'rolling_trend',
                'method': test_method,
                'metric': metric_column,
                'window': window,
                'data': rolling_df,
                'alpha': alpha
            }
        
        return new_pipe
    
    return _calculate_statistical_trend


def _test_trend(series, method, alpha):
    """Helper function to test for trend using various methods"""
    if method == 'mann_kendall':
        try:
            from scipy.stats import kendalltau
            tau, p_value = kendalltau(np.arange(len(series)), series.values)
            significant = p_value < alpha
            trend = 'increasing' if tau > 0 else 'decreasing' if tau < 0 else 'no trend'
            return {
                'trend': trend,
                'p_value': p_value,
                'significant': significant,
                'tau': tau
            }
        except:
            warnings.warn("Mann-Kendall test failed. Falling back to t-test.")
            method = 't_test'
    
    if method == 't_test':
        x = np.arange(len(series))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, series.values)
        significant = p_value < alpha
        trend = 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'no trend'
        return {
            'trend': trend,
            'p_value': p_value,
            'significant': significant,
            'slope': slope,
            'intercept': intercept,
            'r_value': r_value
        }
    
    if method == 'spearman':
        rho, p_value = stats.spearmanr(np.arange(len(series)), series.values)
        significant = p_value < alpha
        trend = 'increasing' if rho > 0 else 'decreasing' if rho < 0 else 'no trend'
        return {
            'trend': trend,
            'p_value': p_value,
            'significant': significant,
            'rho': rho
        }
    
    raise ValueError(f"Unknown test method: {method}")


def compare_periods(
    metric_column: str,
    comparison_type: str = 'year_over_year',
    n_periods: int = 1,
    aggregation: str = 'mean'
):
    """
    Compare metrics between different time periods (e.g., year-over-year, month-over-month)
    
    Parameters:
    -----------
    metric_column : str
        Column to compare
    comparison_type : str, default='year_over_year'
        Type of comparison ('year_over_year', 'month_over_month', 'week_over_week', 'period_over_period')
    n_periods : int, default=1
        Number of periods to go back for comparison
    aggregation : str, default='mean'
        Method to aggregate values within periods ('mean', 'sum', 'median', 'min', 'max')
        
    Returns:
    --------
    Callable
        Function that compares metrics between periods
    """
    def _compare_periods(pipe):
        if pipe.current_analysis is None or pipe.current_analysis not in pipe.time_aggregations:
            raise ValueError("No time aggregation found. Call aggregate_by_time() first.")
        
        new_pipe = pipe.copy()
        agg_data = new_pipe.time_aggregations[new_pipe.current_analysis]
        df = agg_data['data']
        time_period = agg_data['time_period']
        
        # Check if the metric column exists
        if metric_column not in df.columns:
            raise ValueError(f"Metric column '{metric_column}' not found in aggregated data")
        
        # Get time index
        time_index = df.index
        
        # Determine period offset based on comparison type and current time period
        period_offset = None
        
        if comparison_type == 'year_over_year':
            if time_period in ['D', 'W', 'M', 'Q']:
                period_offset = pd.DateOffset(years=n_periods)
            else:
                period_offset = pd.DateOffset(years=n_periods)
        
        elif comparison_type == 'month_over_month':
            if time_period in ['D', 'W']:
                period_offset = pd.DateOffset(months=n_periods)
            else:
                period_offset = pd.DateOffset(months=n_periods)
        
        elif comparison_type == 'week_over_week':
            if time_period == 'D':
                period_offset = pd.DateOffset(weeks=n_periods)
            else:
                period_offset = pd.DateOffset(weeks=n_periods)
        
        elif comparison_type == 'period_over_period':
            if time_period == 'D':
                period_offset = pd.DateOffset(days=n_periods)
            elif time_period == 'W':
                period_offset = pd.DateOffset(weeks=n_periods)
            elif time_period == 'M':
                period_offset = pd.DateOffset(months=n_periods)
            elif time_period == 'Q':
                period_offset = pd.DateOffset(months=3*n_periods)
            elif time_period == 'Y':
                period_offset = pd.DateOffset(years=n_periods)
            else:
                period_offset = pd.DateOffset(days=n_periods)
        
        else:
            raise ValueError(f"Unknown comparison type: {comparison_type}")
        
        # Create comparison dataframe
        comparison_df = pd.DataFrame(index=time_index)
        comparison_df['current'] = df[metric_column]
        
        # Get previous period values (shifted by offset)
        previous_index = time_index - period_offset
        previous_values = []
        
        for t in time_index:
            prev_t = t - period_offset
            if prev_t in df.index:
                previous_values.append(df.loc[prev_t, metric_column])
            else:
                previous_values.append(np.nan)
        
        comparison_df['previous'] = previous_values
        
        # Calculate absolute and relative differences
        comparison_df['abs_diff'] = comparison_df['current'] - comparison_df['previous']
        comparison_df['rel_diff'] = (comparison_df['current'] / comparison_df['previous'] - 1) * 100
        
        # Store the result
        analysis_name = f"{new_pipe.current_analysis}_{metric_column}_comparison"
        new_pipe.trend_results[analysis_name] = {
            'type': 'period_comparison',
            'metric': metric_column,
            'comparison_type': comparison_type,
            'n_periods': n_periods,
            'data': comparison_df
        }
        
        return new_pipe
    
    return _compare_periods


def get_top_metrics(n: int = 5, metric_type: str = 'growth', ascending: bool = False):
    """
    Get top metrics based on growth, trend, or other criteria
    
    Parameters:
    -----------
    n : int, default=5
        Number of top metrics to return
    metric_type : str, default='growth'
        Type of metric to rank by ('growth', 'trend', 'volatility', 'absolute_change')
    ascending : bool, default=False
        Whether to sort in ascending order (False = highest values first)
        
    Returns:
    --------
    Callable
        Function that gets top metrics
    """
    def _get_top_metrics(pipe):
        metrics = []
        
        if metric_type == 'growth':
            # Get growth rate analyses
            growth_analyses = {k: v for k, v in pipe.trend_results.items() if v['type'] == 'growth'}
            if not growth_analyses:
                raise ValueError("No growth analyses found. Call calculate_growth_rates() first.")
            
            # Extract latest growth rates for all metrics
            for name, analysis in growth_analyses.items():
                growth_df = analysis['data']
                for col in growth_df.columns:
                    if col.endswith('_growth'):
                        metric_name = col[:-7]  # Remove '_growth' suffix
                        latest_growth = growth_df[col].dropna().iloc[-1] if not growth_df[col].dropna().empty else None
                        if latest_growth is not None:
                            metrics.append({
                                'metric': metric_name,
                                'value': latest_growth,
                                'analysis': name,
                                'type': 'growth'
                            })
        
        elif metric_type == 'trend':
            # Get trend analyses
            trend_analyses = {k: v for k, v in pipe.trend_results.items() if v['type'] == 'statistical_trend'}
            if not trend_analyses:
                raise ValueError("No trend analyses found. Call calculate_statistical_trend() first.")
            
            # Extract trend significance for all metrics
            for name, analysis in trend_analyses.items():
                metric_name = analysis['metric']
                if analysis['significant']:
                    # Use slope if available, otherwise just use 1/-1 for increasing/decreasing
                    if 'slope' in analysis and analysis['slope'] is not None:
                        value = analysis['slope']
                    else:
                        value = 1 if analysis['trend'] == 'increasing' else -1
                else:
                    value = 0
                
                metrics.append({
                    'metric': metric_name,
                    'value': value,
                    'analysis': name,
                    'trend': analysis['trend'],
                    'significant': analysis['significant'],
                    'p_value': analysis['p_value'],
                    'type': 'trend'
                })
        
        elif metric_type == 'volatility':
            # Calculate volatility for all metrics in time aggregations
            for agg_name, agg_data in pipe.time_aggregations.items():
                df = agg_data['data']
                for col in df.columns:
                    # Calculate coefficient of variation (CV) as a measure of volatility
                    # CV = standard deviation / mean
                    mean = df[col].mean()
                    if mean != 0:
                        cv = df[col].std() / abs(mean)
                        metrics.append({
                            'metric': col,
                            'value': cv,
                            'analysis': agg_name,
                            'std': df[col].std(),
                            'mean': mean,
                            'type': 'volatility'
                        })
        
        elif metric_type == 'absolute_change':
            # Get period comparison analyses
            comparison_analyses = {k: v for k, v in pipe.trend_results.items() if v['type'] == 'period_comparison'}
            if not comparison_analyses:
                raise ValueError("No period comparison analyses found. Call compare_periods() first.")
            
            # Extract absolute changes for all metrics
            for name, analysis in comparison_analyses.items():
                metric_name = analysis['metric']
                comparison_df = analysis['data']
                latest_abs_diff = comparison_df['abs_diff'].dropna().iloc[-1] if not comparison_df['abs_diff'].dropna().empty else None
                latest_rel_diff = comparison_df['rel_diff'].dropna().iloc[-1] if not comparison_df['rel_diff'].dropna().empty else None
                
                if latest_abs_diff is not None:
                    metrics.append({
                        'metric': metric_name,
                        'value': latest_abs_diff,
                        'rel_diff': latest_rel_diff,
                        'analysis': name,
                        'comparison_type': analysis['comparison_type'],
                        'n_periods': analysis['n_periods'],
                        'type': 'absolute_change'
                    })
        
        else:
            raise ValueError(f"Unknown metric type: {metric_type}")
        
        # Sort and get top metrics
        if metrics:
            metrics_df = pd.DataFrame(metrics)
            top_metrics = metrics_df.sort_values('value', ascending=ascending).head(n)
            return top_metrics
        else:
            return pd.DataFrame()
    
    return _get_top_metrics
