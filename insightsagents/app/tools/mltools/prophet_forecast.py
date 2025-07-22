import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from prophet.plot import plot_cross_validation_metric
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import warnings
from datetime import datetime, timedelta
import itertools


class ProphetPipe:
    """
    A pipeline-style Prophet time series forecasting tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
        self.models = {}
        self.forecasts = {}
        self.metrics = {}
        self.cross_validation_results = {}
        self.holidays = {}
        self.regressors = {}
        self.current_analysis = None
        self.model_configs = {}
        self.original_data = None
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe ProphetPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = ProphetPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        if self.original_data is not None:
            new_pipe.original_data = self.original_data.copy()
        new_pipe.models = self.models.copy()
        new_pipe.forecasts = self.forecasts.copy()
        new_pipe.metrics = self.metrics.copy()
        new_pipe.cross_validation_results = self.cross_validation_results.copy()
        new_pipe.holidays = self.holidays.copy()
        new_pipe.regressors = self.regressors.copy()
        new_pipe.current_analysis = self.current_analysis
        new_pipe.model_configs = self.model_configs.copy()
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create a ProphetPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        pipe.original_data = df.copy()
        return pipe


# Data Preparation Functions
def prepare_prophet_data(
    date_column: str,
    value_column: str,
    date_format: Optional[str] = None,
    freq: Optional[str] = None
):
    """
    Prepare data for Prophet by creating ds/y format
    
    Parameters:
    -----------
    date_column : str
        Column containing dates
    value_column : str
        Column containing values to forecast
    date_format : Optional[str]
        Format for parsing dates if not datetime
    freq : Optional[str]
        Expected frequency of the time series
        
    Returns:
    --------
    Callable
        Function that prepares Prophet data from a ProphetPipe
    """
    def _prepare_prophet_data(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Convert date column to datetime
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            if date_format:
                df[date_column] = pd.to_datetime(df[date_column], format=date_format)
            else:
                df[date_column] = pd.to_datetime(df[date_column])
        
        # Create Prophet format dataframe
        prophet_df = df[[date_column, value_column]].copy()
        prophet_df.columns = ['ds', 'y']
        
        # Sort by date
        prophet_df = prophet_df.sort_values('ds').reset_index(drop=True)
        
        # Check for missing values
        if prophet_df['y'].isnull().any():
            warnings.warn("Found missing values in target variable. Consider handling them before training.")
        
        # Validate frequency if provided
        if freq:
            expected_freq = pd.infer_freq(prophet_df['ds'])
            if expected_freq != freq:
                warnings.warn(f"Inferred frequency ({expected_freq}) differs from expected ({freq})")
        
        new_pipe.data = prophet_df
        new_pipe.current_analysis = 'data_preparation'
        
        return new_pipe
    
    return _prepare_prophet_data


def add_regressors(
    regressor_columns: List[str],
    regressor_data: Optional[pd.DataFrame] = None,
    prior_scale: float = 10.0,
    standardize: Union[bool, str] = 'auto'
):
    """
    Add external regressors to the model
    
    Parameters:
    -----------
    regressor_columns : List[str]
        Columns to use as regressors
    regressor_data : Optional[pd.DataFrame]
        DataFrame containing regressor data (if different from main data)
    prior_scale : float
        Prior scale for the regressor coefficients
    standardize : Union[bool, str]
        Whether to standardize regressors
        
    Returns:
    --------
    Callable
        Function that adds regressors to a ProphetPipe
    """
    def _add_regressors(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Prepare data first.")
        
        new_pipe = pipe.copy()
        
        if regressor_data is not None:
            # Merge regressor data with main data
            regressor_df = regressor_data.copy()
            if 'ds' not in regressor_df.columns:
                raise ValueError("Regressor data must have a 'ds' column with dates")
            
            # Merge on ds column
            new_pipe.data = pd.merge(new_pipe.data, regressor_df, on='ds', how='left')
        
        # Store regressor configuration
        for col in regressor_columns:
            if col not in new_pipe.data.columns:
                warnings.warn(f"Regressor column '{col}' not found in data. Skipping.")
                continue
            
            new_pipe.regressors[col] = {
                'prior_scale': prior_scale,
                'standardize': standardize
            }
        
        new_pipe.current_analysis = 'add_regressors'
        
        return new_pipe
    
    return _add_regressors


def add_holidays(
    holiday_data: Union[pd.DataFrame, str, List[str]],
    holiday_name: Optional[str] = None,
    prior_scale: float = 10.0,
    lower_window: int = 0,
    upper_window: int = 0
):
    """
    Add holiday effects to the model
    
    Parameters:
    -----------
    holiday_data : Union[pd.DataFrame, str, List[str]]
        Holiday data or country code for built-in holidays
    holiday_name : Optional[str]
        Name for the holiday group
    prior_scale : float
        Prior scale for holiday effects
    lower_window : int
        Days before holiday to include
    upper_window : int
        Days after holiday to include
        
    Returns:
    --------
    Callable
        Function that adds holidays to a ProphetPipe
    """
    def _add_holidays(pipe):
        new_pipe = pipe.copy()
        
        if isinstance(holiday_data, pd.DataFrame):
            # Custom holiday dataframe
            holidays_df = holiday_data.copy()
            if 'ds' not in holidays_df.columns or 'holiday' not in holidays_df.columns:
                raise ValueError("Holiday DataFrame must have 'ds' and 'holiday' columns")
            
            holiday_key = holiday_name or 'custom_holidays'
            
        elif isinstance(holiday_data, str):
            # Country code for built-in holidays
            try:
                from prophet.make_holidays import make_holidays_df
                year_start = new_pipe.data['ds'].dt.year.min()
                year_end = new_pipe.data['ds'].dt.year.max() + 1
                years = list(range(year_start, year_end + 1))
                holidays_df = make_holidays_df(year_list=years, country=holiday_data)
                holiday_key = f'{holiday_data}_holidays'
            except ImportError:
                warnings.warn("Could not import make_holidays_df. Install holidays package.")
                return new_pipe
            except Exception as e:
                warnings.warn(f"Could not create holidays for {holiday_data}: {e}")
                return new_pipe
                
        elif isinstance(holiday_data, list):
            # List of holiday names - create simple holiday dataframe
            if not new_pipe.data is not None:
                raise ValueError("Data must be prepared before adding holidays from list")
            
            date_range = pd.date_range(
                start=new_pipe.data['ds'].min(),
                end=new_pipe.data['ds'].max(),
                freq='D'
            )
            
            holidays_df = pd.DataFrame({
                'ds': date_range,
                'holiday': None
            })
            
            # This is a simplified approach - in practice, you'd need specific dates
            warnings.warn("Holiday list approach requires specific implementation for your use case")
            return new_pipe
        
        else:
            raise ValueError("holiday_data must be DataFrame, country code string, or list of holidays")
        
        # Add window columns if specified
        if lower_window != 0:
            holidays_df['lower_window'] = lower_window
        if upper_window != 0:
            holidays_df['upper_window'] = upper_window
        
        new_pipe.holidays[holiday_key] = {
            'holidays_df': holidays_df,
            'prior_scale': prior_scale
        }
        
        new_pipe.current_analysis = 'add_holidays'
        
        return new_pipe
    
    return _add_holidays


# Model Configuration Functions
def configure_prophet(
    growth: str = 'linear',
    seasonality_mode: str = 'additive',
    changepoint_prior_scale: float = 0.05,
    seasonality_prior_scale: float = 10.0,
    holidays_prior_scale: float = 10.0,
    n_changepoints: int = 25,
    changepoint_range: float = 0.8,
    yearly_seasonality: Union[bool, str] = 'auto',
    weekly_seasonality: Union[bool, str] = 'auto',
    daily_seasonality: Union[bool, str] = 'auto',
    model_name: str = 'prophet_model'
):
    """
    Configure Prophet model parameters
    
    Parameters:
    -----------
    growth : str
        'linear' or 'logistic' growth
    seasonality_mode : str
        'additive' or 'multiplicative'
    changepoint_prior_scale : float
        Prior scale for changepoint flexibility
    seasonality_prior_scale : float
        Prior scale for seasonality
    holidays_prior_scale : float
        Prior scale for holidays
    n_changepoints : int
        Number of potential changepoints
    changepoint_range : float
        Proportion of history for changepoints
    yearly_seasonality : Union[bool, str]
        Yearly seasonality setting
    weekly_seasonality : Union[bool, str]
        Weekly seasonality setting
    daily_seasonality : Union[bool, str]
        Daily seasonality setting
    model_name : str
        Name for the model
        
    Returns:
    --------
    Callable
        Function that configures Prophet model in a ProphetPipe
    """
    def _configure_prophet(pipe):
        new_pipe = pipe.copy()
        
        # Create Prophet model with configuration
        model = Prophet(
            growth=growth,
            seasonality_mode=seasonality_mode,
            changepoint_prior_scale=changepoint_prior_scale,
            seasonality_prior_scale=seasonality_prior_scale,
            holidays_prior_scale=holidays_prior_scale,
            n_changepoints=n_changepoints,
            changepoint_range=changepoint_range,
            yearly_seasonality=yearly_seasonality,
            weekly_seasonality=weekly_seasonality,
            daily_seasonality=daily_seasonality
        )
        
        # Add holidays if any
        for holiday_key, holiday_config in new_pipe.holidays.items():
            model.holidays = holiday_config['holidays_df']
        
        # Add regressors if any
        for regressor, config in new_pipe.regressors.items():
            model.add_regressor(
                regressor,
                prior_scale=config['prior_scale'],
                standardize=config['standardize']
            )
        
        new_pipe.models[model_name] = model
        new_pipe.model_configs[model_name] = {
            'growth': growth,
            'seasonality_mode': seasonality_mode,
            'changepoint_prior_scale': changepoint_prior_scale,
            'seasonality_prior_scale': seasonality_prior_scale,
            'holidays_prior_scale': holidays_prior_scale,
            'n_changepoints': n_changepoints,
            'changepoint_range': changepoint_range,
            'yearly_seasonality': yearly_seasonality,
            'weekly_seasonality': weekly_seasonality,
            'daily_seasonality': daily_seasonality
        }
        
        new_pipe.current_analysis = f'configure_{model_name}'
        
        return new_pipe
    
    return _configure_prophet


def add_custom_seasonality(
    name: str,
    period: float,
    fourier_order: int,
    prior_scale: float = 10.0,
    model_name: str = 'prophet_model'
):
    """
    Add custom seasonality to the model
    
    Parameters:
    -----------
    name : str
        Name of the seasonality
    period : float
        Period of the seasonality in days
    fourier_order : int
        Number of Fourier terms
    prior_scale : float
        Prior scale for seasonality
    model_name : str
        Name of the model to add seasonality to
        
    Returns:
    --------
    Callable
        Function that adds custom seasonality to a ProphetPipe
    """
    def _add_custom_seasonality(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found. Configure model first.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        model.add_seasonality(
            name=name,
            period=period,
            fourier_order=fourier_order,
            prior_scale=prior_scale
        )
        
        new_pipe.current_analysis = f'add_seasonality_{name}'
        
        return new_pipe
    
    return _add_custom_seasonality


# Training Functions
def fit_prophet(
    model_name: str = 'prophet_model'
):
    """
    Fit the Prophet model to the data
    
    Parameters:
    -----------
    model_name : str
        Name of the model to fit
        
    Returns:
    --------
    Callable
        Function that fits Prophet model in a ProphetPipe
    """
    def _fit_prophet(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Prepare data first.")
        
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found. Configure model first.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        # Fit the model
        model.fit(new_pipe.data)
        
        new_pipe.current_analysis = f'fit_{model_name}'
        
        return new_pipe
    
    return _fit_prophet


# Forecasting Functions
def make_forecast(
    periods: int,
    freq: str = 'D',
    include_history: bool = True,
    model_name: str = 'prophet_model',
    forecast_name: Optional[str] = None
):
    """
    Generate forecasts using the fitted model
    
    Parameters:
    -----------
    periods : int
        Number of periods to forecast
    freq : str
        Frequency of forecasts
    include_history : bool
        Whether to include historical period in forecast
    model_name : str
        Name of the fitted model
    forecast_name : Optional[str]
        Name for the forecast results
        
    Returns:
    --------
    Callable
        Function that generates forecasts from a ProphetPipe
    """
    def _make_forecast(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=periods, freq=freq, include_history=include_history)
        
        # Add regressor values for future periods if needed
        if new_pipe.regressors:
            warnings.warn("Future regressor values needed for forecasting with regressors. "
                         "Ensure regressor data extends to forecast period.")
        
        # Generate forecast
        forecast = model.predict(future)
        
        # Store forecast
        if forecast_name is None:
            forecast_name = f'{model_name}_forecast'
        
        new_pipe.forecasts[forecast_name] = {
            'forecast': forecast,
            'model_name': model_name,
            'periods': periods,
            'freq': freq,
            'include_history': include_history
        }
        
        new_pipe.current_analysis = f'forecast_{forecast_name}'
        
        return new_pipe
    
    return _make_forecast


def forecast_with_regressors(
    periods: int,
    regressor_future_values: Dict[str, Union[List, pd.Series, np.ndarray]],
    freq: str = 'D',
    include_history: bool = True,
    model_name: str = 'prophet_model',
    forecast_name: Optional[str] = None
):
    """
    Generate forecasts with future regressor values
    
    Parameters:
    -----------
    periods : int
        Number of periods to forecast
    regressor_future_values : Dict[str, Union[List, pd.Series, np.ndarray]]
        Future values for each regressor
    freq : str
        Frequency of forecasts
    include_history : bool
        Whether to include historical period
    model_name : str
        Name of the fitted model
    forecast_name : Optional[str]
        Name for the forecast results
        
    Returns:
    --------
    Callable
        Function that generates forecasts with regressors from a ProphetPipe
    """
    def _forecast_with_regressors(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=periods, freq=freq, include_history=include_history)
        
        # Add future regressor values
        if include_history:
            # Get historical regressor values
            historical_length = len(new_pipe.data)
            
            for regressor, future_values in regressor_future_values.items():
                if regressor not in new_pipe.regressors:
                    warnings.warn(f"Regressor '{regressor}' not in model. Skipping.")
                    continue
                
                # Historical values
                historical_values = new_pipe.data[regressor].values if regressor in new_pipe.data.columns else [0] * historical_length
                
                # Combine historical and future
                all_values = list(historical_values) + list(future_values)
                future[regressor] = all_values[:len(future)]
        else:
            # Only future values
            for regressor, future_values in regressor_future_values.items():
                future[regressor] = future_values
        
        # Generate forecast
        forecast = model.predict(future)
        
        # Store forecast
        if forecast_name is None:
            forecast_name = f'{model_name}_forecast_with_regressors'
        
        new_pipe.forecasts[forecast_name] = {
            'forecast': forecast,
            'model_name': model_name,
            'periods': periods,
            'freq': freq,
            'include_history': include_history,
            'regressor_future_values': regressor_future_values
        }
        
        new_pipe.current_analysis = f'forecast_{forecast_name}'
        
        return new_pipe
    
    return _forecast_with_regressors


# Evaluation Functions
def cross_validate_model(
    initial: str,
    period: str,
    horizon: str,
    parallel: str = None,
    model_name: str = 'prophet_model',
    cv_name: Optional[str] = None
):
    """
    Perform cross-validation on the model
    
    Parameters:
    -----------
    initial : str
        Size of initial training period
    period : str
        Spacing between cutoff dates
    horizon : str
        Size of forecast horizon
    parallel : str
        Parallelization method
    model_name : str
        Name of the model to cross-validate
    cv_name : Optional[str]
        Name for CV results
        
    Returns:
    --------
    Callable
        Function that performs cross-validation on a ProphetPipe
    """
    def _cross_validate_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if pipe.data is None:
            raise ValueError("No data found.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        # Perform cross-validation
        df_cv = cross_validation(
            model,
            initial=initial,
            period=period,
            horizon=horizon,
            parallel=parallel
        )
        
        # Calculate performance metrics
        df_p = performance_metrics(df_cv)
        
        # Store results
        if cv_name is None:
            cv_name = f'{model_name}_cv'
        
        new_pipe.cross_validation_results[cv_name] = {
            'cv_results': df_cv,
            'performance_metrics': df_p,
            'initial': initial,
            'period': period,
            'horizon': horizon
        }
        
        new_pipe.current_analysis = f'cross_validate_{cv_name}'
        
        return new_pipe
    
    return _cross_validate_model


def calculate_forecast_metrics(
    forecast_name: str,
    actual_column: str = 'y',
    cutoff_date: Optional[str] = None
):
    """
    Calculate forecast accuracy metrics
    
    Parameters:
    -----------
    forecast_name : str
        Name of the forecast to evaluate
    actual_column : str
        Column name with actual values
    cutoff_date : Optional[str]
        Date to split actual vs forecast period
        
    Returns:
    --------
    Callable
        Function that calculates forecast metrics from a ProphetPipe
    """
    def _calculate_forecast_metrics(pipe):
        if forecast_name not in pipe.forecasts:
            raise ValueError(f"Forecast '{forecast_name}' not found.")
        
        new_pipe = pipe.copy()
        forecast_data = new_pipe.forecasts[forecast_name]
        forecast_df = forecast_data['forecast']
        
        # Get actual data
        if cutoff_date:
            cutoff = pd.to_datetime(cutoff_date)
            actual_data = new_pipe.original_data[new_pipe.original_data['ds'] > cutoff]
        else:
            actual_data = new_pipe.original_data
        
        # Merge forecast with actual
        merged = pd.merge(
            forecast_df[['ds', 'yhat', 'yhat_lower', 'yhat_upper']],
            actual_data[['ds', actual_column]],
            on='ds',
            how='inner'
        )
        
        if len(merged) == 0:
            warnings.warn("No overlapping dates found between forecast and actual data.")
            return new_pipe
        
        # Calculate metrics
        y_true = merged[actual_column]
        y_pred = merged['yhat']
        
        mae = np.mean(np.abs(y_true - y_pred))
        mse = np.mean((y_true - y_pred) ** 2)
        rmse = np.sqrt(mse)
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        
        # Coverage (percentage of actual values within prediction interval)
        coverage = np.mean(
            (merged[actual_column] >= merged['yhat_lower']) & 
            (merged[actual_column] <= merged['yhat_upper'])
        ) * 100
        
        metrics = {
            'mae': mae,
            'mse': mse,
            'rmse': rmse,
            'mape': mape,
            'coverage': coverage,
            'n_observations': len(merged)
        }
        
        new_pipe.metrics[forecast_name] = metrics
        new_pipe.current_analysis = f'metrics_{forecast_name}'
        
        return new_pipe
    
    return _calculate_forecast_metrics


def print_forecast_metrics(
    forecast_name: str
):
    """
    Print forecast metrics in a formatted way
    
    Parameters:
    -----------
    forecast_name : str
        Name of forecast to print metrics for
        
    Returns:
    --------
    Callable
        Function that prints forecast metrics from a ProphetPipe
    """
    def _print_forecast_metrics(pipe):
        if forecast_name not in pipe.metrics:
            raise ValueError(f"Metrics for forecast '{forecast_name}' not found.")
        
        metrics = pipe.metrics[forecast_name]
        
        print(f"\n=== Forecast Metrics for {forecast_name} ===")
        print(f"MAE (Mean Absolute Error):     {metrics['mae']:.4f}")
        print(f"MSE (Mean Squared Error):      {metrics['mse']:.4f}")
        print(f"RMSE (Root Mean Squared Error): {metrics['rmse']:.4f}")
        print(f"MAPE (Mean Absolute Percentage Error): {metrics['mape']:.2f}%")
        print(f"Coverage (Prediction Interval): {metrics['coverage']:.1f}%")
        print(f"Number of observations: {metrics['n_observations']}")
        
        return pipe
    
    return _print_forecast_metrics


# Visualization Functions
def plot_forecast(
    forecast_name: str,
    figsize: Tuple[int, int] = (12, 6),
    show_components: bool = False
):
    """
    Plot forecast results
    
    Parameters:
    -----------
    forecast_name : str
        Name of forecast to plot
    figsize : Tuple[int, int]
        Figure size
    show_components : bool
        Whether to show component plots
        
    Returns:
    --------
    Callable
        Function that plots forecast from a ProphetPipe
    """
    def _plot_forecast(pipe):
        if forecast_name not in pipe.forecasts:
            raise ValueError(f"Forecast '{forecast_name}' not found.")
        
        forecast_data = pipe.forecasts[forecast_name]
        model_name = forecast_data['model_name']
        forecast_df = forecast_data['forecast']
        
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for plotting.")
        
        model = pipe.models[model_name]
        
        # Plot forecast
        fig1 = model.plot(forecast_df, figsize=figsize)
        plt.title(f'Forecast: {forecast_name}')
        plt.tight_layout()
        plt.show()
        
        # Plot components if requested
        if show_components:
            fig2 = model.plot_components(forecast_df, figsize=(12, 8))
            plt.suptitle(f'Forecast Components: {forecast_name}')
            plt.tight_layout()
            plt.show()
        
        return pipe
    
    return _plot_forecast


def plot_cross_validation(
    cv_name: str,
    metric: str = 'mape',
    figsize: Tuple[int, int] = (12, 6)
):
    """
    Plot cross-validation results
    
    Parameters:
    -----------
    cv_name : str
        Name of cross-validation results
    metric : str
        Metric to plot
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots cross-validation from a ProphetPipe
    """
    def _plot_cross_validation(pipe):
        if cv_name not in pipe.cross_validation_results:
            raise ValueError(f"Cross-validation '{cv_name}' not found.")
        
        cv_data = pipe.cross_validation_results[cv_name]
        df_p = cv_data['performance_metrics']
        
        # Plot cross-validation metric
        fig = plot_cross_validation_metric(cv_data['cv_results'], metric=metric, figsize=figsize)
        plt.title(f'Cross-Validation {metric.upper()}: {cv_name}')
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_cross_validation


# Model Management Functions
def save_prophet_model(
    model_name: str = 'prophet_model',
    filepath: Optional[str] = None
):
    """
    Save a trained Prophet model to disk
    
    Parameters:
    -----------
    model_name : str
        Name of the model to save
    filepath : Optional[str]
        Path to save the model
        
    Returns:
    --------
    Callable
        Function that saves a Prophet model from a ProphetPipe
    """
    def _save_prophet_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        new_pipe = pipe.copy()
        
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = f"{model_name}_{timestamp}.joblib"
        else:
            save_path = filepath
        
        # Save model and configuration
        model_package = {
            'model': pipe.models[model_name],
            'config': pipe.model_configs.get(model_name, {}),
            'regressors': pipe.regressors,
            'holidays': pipe.holidays
        }
        
        joblib.dump(model_package, save_path)
        print(f"Prophet model saved to: {save_path}")
        
        return new_pipe
    
    return _save_prophet_model


def hyperparameter_tuning(
    param_grid: Dict[str, List],
    cv_initial: str,
    cv_period: str,
    cv_horizon: str,
    metric: str = 'mape',
    model_name: str = 'prophet_model'
):
    """
    Perform hyperparameter tuning using cross-validation
    
    Parameters:
    -----------
    param_grid : Dict[str, List]
        Grid of parameters to search
    cv_initial : str
        Initial period for CV
    cv_period : str
        Period between CV folds
    cv_horizon : str
        Forecast horizon for CV
    metric : str
        Metric to optimize
    model_name : str
        Base name for models
        
    Returns:
    --------
    Callable
        Function that performs hyperparameter tuning on a ProphetPipe
    """
    def _hyperparameter_tuning(pipe):
        if pipe.data is None:
            raise ValueError("No data found.")
        
        new_pipe = pipe.copy()
        
        # Generate all parameter combinations
        param_combinations = [dict(zip(param_grid.keys(), v)) 
                            for v in itertools.product(*param_grid.values())]
        
        results = []
        
        for i, params in enumerate(param_combinations):
            print(f"Testing parameter combination {i+1}/{len(param_combinations)}: {params}")
            
            # Create model with current parameters
            temp_model_name = f"{model_name}_temp_{i}"
            
            # Configure and fit model
            temp_pipe = (
                new_pipe.copy()
                | configure_prophet(**params, model_name=temp_model_name)
                | fit_prophet(model_name=temp_model_name)
            )
            
            # Perform cross-validation
            temp_pipe = temp_pipe | cross_validate_model(
                initial=cv_initial,
                period=cv_period,
                horizon=cv_horizon,
                model_name=temp_model_name,
                cv_name=f"cv_{i}"
            )
            
            # Get metric value
            cv_results = temp_pipe.cross_validation_results[f"cv_{i}"]
            metric_value = cv_results['performance_metrics'][metric].mean()
            
            results.append({
                'params': params,
                'metric_value': metric_value,
                'model_name': temp_model_name
            })
        
        # Find best parameters
        best_result = min(results, key=lambda x: x['metric_value'])
        
        print(f"\nBest parameters: {best_result['params']}")
        print(f"Best {metric}: {best_result['metric_value']:.4f}")
        
        # Store tuning results
        new_pipe.metrics[f'{model_name}_tuning'] = {
            'best_params': best_result['params'],
            'best_metric': best_result['metric_value'],
            'all_results': results,
            'metric_optimized': metric
        }
        
        # Configure final model with best parameters
        new_pipe = (
            new_pipe
            | configure_prophet(**best_result['params'], model_name=f"{model_name}_best")
            | fit_prophet(model_name=f"{model_name}_best")
        )
        
        new_pipe.current_analysis = f'tuning_{model_name}'
        
        return new_pipe
    
    return _hyperparameter_tuning