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
from ..base_pipe import BasePipe


class ProphetPipe(BasePipe):
    """
    A pipeline-style Prophet time series forecasting tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for Prophet forecasting analysis"""
        self.models = {}
        self.forecasts = {}
        self.metrics = {}
        self.cross_validation_results = {}
        self.holidays = {}
        self.regressors = {}
        self.current_analysis = None
        self.model_configs = {}
        self.original_data = None
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'models'):
            self.models = source_pipe.models.copy()
        if hasattr(source_pipe, 'forecasts'):
            self.forecasts = source_pipe.forecasts.copy()
        if hasattr(source_pipe, 'metrics'):
            self.metrics = source_pipe.metrics.copy()
        if hasattr(source_pipe, 'cross_validation_results'):
            self.cross_validation_results = source_pipe.cross_validation_results.copy()
        if hasattr(source_pipe, 'holidays'):
            self.holidays = source_pipe.holidays.copy()
        if hasattr(source_pipe, 'regressors'):
            self.regressors = source_pipe.regressors.copy()
        if hasattr(source_pipe, 'current_analysis'):
            self.current_analysis = source_pipe.current_analysis
        if hasattr(source_pipe, 'model_configs'):
            self.model_configs = source_pipe.model_configs.copy()
        if hasattr(source_pipe, 'original_data'):
            self.original_data = source_pipe.original_data.copy() if source_pipe.original_data is not None else None
    
    def _has_results(self) -> bool:
        """Check if the pipeline has any results to merge"""
        return (len(self.models) > 0 or 
                len(self.forecasts) > 0 or 
                len(self.metrics) > 0 or 
                len(self.cross_validation_results) > 0)
    
    def merge_to_df(self, base_df: pd.DataFrame, analysis_name: Optional[str] = None, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
        """
        Merge Prophet forecasting results into the base dataframe as new columns
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge results into
        analysis_name : str, optional
            Specific analysis to merge (if None, merges all)
        include_metadata : bool, default=False
            Whether to include metadata columns
        **kwargs : dict
            Additional arguments
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with Prophet forecasting results merged as new columns
        """
        if not self._has_results():
            return base_df
        
        result_df = base_df.copy()
        
        # Merge forecasts
        for forecast_name, forecast_data in self.forecasts.items():
            if analysis_name is None or forecast_name == analysis_name:
                if isinstance(forecast_data, pd.DataFrame):
                    for col in forecast_data.columns:
                        if col not in result_df.columns:
                            result_df[f"forecast_{forecast_name}_{col}"] = None
                    
                    # Try to align forecasts with base data by index if possible
                    if len(forecast_data) == len(result_df):
                        for col in forecast_data.columns:
                            result_df[f"forecast_{forecast_name}_{col}"] = forecast_data[col].values
        
        # Merge metrics
        for metric_name, metric_data in self.metrics.items():
            if analysis_name is None or metric_name == analysis_name:
                if isinstance(metric_data, dict):
                    for key, value in metric_data.items():
                        if include_metadata:
                            result_df[f"metric_{metric_name}_{key}"] = value
        
        # Merge cross-validation results
        for cv_name, cv_data in self.cross_validation_results.items():
            if analysis_name is None or cv_name == analysis_name:
                if isinstance(cv_data, dict):
                    for key, value in cv_data.items():
                        if include_metadata:
                            result_df[f"cv_{cv_name}_{key}"] = value
        
        return result_df
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the Prophet forecasting analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in Prophet forecasting pipe)
            
        Returns:
        --------
        dict
            Summary of the Prophet forecasting analysis results
        """
        if not any([self.models, self.forecasts, self.metrics, self.cross_validation_results]):
            return {"error": "No Prophet forecasting analysis has been performed"}
        
        # Count analyses by type
        analysis_types = {
            'models': len(self.models),
            'forecasts': len(self.forecasts),
            'metrics': len(self.metrics),
            'cross_validation_results': len(self.cross_validation_results),
            'holidays': len(self.holidays),
            'regressors': len(self.regressors),
            'model_configs': len(self.model_configs)
        }
        
        # Get model information
        models_info = {}
        for name, model in self.models.items():
            models_info[name] = {
                "type": "Prophet",
                "growth": model.get('growth', 'unknown'),
                "seasonality_mode": model.get('seasonality_mode', 'unknown'),
                "n_changepoints": model.get('n_changepoints', 'unknown')
            }
        
        # Get forecast information
        forecasts_info = {}
        for name, forecast in self.forecasts.items():
            forecasts_info[name] = {
                "periods": len(forecast.get('forecast', pd.DataFrame())),
                "include_history": forecast.get('include_history', False),
                "model_name": forecast.get('model_name', 'unknown')
            }
        
        # Get metrics summary
        metrics_summary = {}
        for name, metric_data in self.metrics.items():
            if isinstance(metric_data, dict):
                metrics_summary[name] = {
                    "mape": metric_data.get('mape', None),
                    "mae": metric_data.get('mae', None),
                    "rmse": metric_data.get('rmse', None),
                    "mdape": metric_data.get('mdape', None)
                }
        
        return {
            "total_analyses": sum(analysis_types.values()),
            "analysis_types": analysis_types,
            "current_analysis": self.current_analysis,
            "available_models": list(self.models.keys()),
            "available_forecasts": list(self.forecasts.keys()),
            "available_metrics": list(self.metrics.keys()),
            "available_cross_validation_results": list(self.cross_validation_results.keys()),
            "available_holidays": list(self.holidays.keys()),
            "available_regressors": list(self.regressors.keys()),
            "available_model_configs": list(self.model_configs.keys()),
            "models_info": models_info,
            "forecasts_info": forecasts_info,
            "metrics_summary": metrics_summary,
            "cross_validation_info": {name: {"n_folds": len(cv.get('performance_metrics', []))} 
                                    for name, cv in self.cross_validation_results.items()},
            "holidays_info": {name: {"n_holidays": len(holiday.get('holidays', []))} 
                            for name, holiday in self.holidays.items()},
            "regressors_info": {name: {"n_regressors": len(regressor.get('regressors', []))} 
                              for name, regressor in self.regressors.items()}
        }
    
    def to_df(self, **kwargs) -> pd.DataFrame:
        """
        Convert the Prophet forecasting analysis results to a DataFrame.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments:
            - include_forecasts: bool, whether to include forecast data (default: True)
            - include_metrics: bool, whether to include evaluation metrics (default: False)
            - include_history: bool, whether to include historical data (default: True)
            - forecast_name: str, specific forecast to include (default: None, includes all)
            
        Returns:
        --------
        pd.DataFrame
            DataFrame representation of the Prophet analysis results
            
        Raises:
        -------
        ValueError
            If no data is available
        """
        if self.data is None:
            raise ValueError("No data available. Run analysis first.")
        
        # Get parameters
        include_forecasts = kwargs.get('include_forecasts', True)
        include_metrics = kwargs.get('include_metrics', False)
        include_history = kwargs.get('include_history', True)
        forecast_name = kwargs.get('forecast_name', None)
        
        # Start with the original data
        result_df = self.data.copy()
        
        # Add forecast data if requested
        if include_forecasts and self.forecasts:
            if forecast_name:
                if forecast_name in self.forecasts:
                    forecast_data = self.forecasts[forecast_name]['forecast']
                    # Merge forecast with original data
                    result_df = pd.merge(result_df, forecast_data, on='ds', how='outer', suffixes=('', f'_{forecast_name}'))
            else:
                # Add all forecasts
                for name, forecast_info in self.forecasts.items():
                    forecast_data = forecast_info['forecast']
                    # Merge forecast with original data
                    result_df = pd.merge(result_df, forecast_data, on='ds', how='outer', suffixes=('', f'_{name}'))
        
        # Add metrics if requested
        if include_metrics and self.metrics:
            metrics_data = {}
            if forecast_name:
                if forecast_name in self.metrics:
                    metrics = self.metrics[forecast_name]
                    for metric_name, value in metrics.items():
                        if isinstance(value, (int, float)):
                            metrics_data[f'{forecast_name}_{metric_name}'] = [value] * len(result_df)
            else:
                # Add all metrics
                for name, metrics in self.metrics.items():
                    for metric_name, value in metrics.items():
                        if isinstance(value, (int, float)):
                            metrics_data[f'{name}_{metric_name}'] = [value] * len(result_df)
            
            # Add metrics as columns
            for col_name, values in metrics_data.items():
                result_df[col_name] = values
        
        # Filter historical data if requested
        if not include_history:
            # Keep only forecast periods (where y is NaN but yhat is not)
            if 'yhat' in result_df.columns:
                result_df = result_df[result_df['y'].isna() & result_df['yhat'].notna()]
        
        return result_df


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
        
        # Add capacity column for logistic growth if needed
        if model.growth == 'logistic':
            if 'cap' in new_pipe.data.columns:
                # Use the same capacity value for all future periods
                cap_value = new_pipe.data['cap'].iloc[-1]  # Use last historical capacity value
                future['cap'] = cap_value
            else:
                raise ValueError("Logistic growth requires 'cap' column in data")
        
        # Add regressor values for future periods if needed
        if new_pipe.regressors:
            warnings.warn("Future regressor values needed for forecasting with regressors. "
                         "Ensure regressor data extends to forecast period.")
        
        # Generate forecast
        forecast = model.predict(future)
        
        # Store forecast
        final_forecast_name = forecast_name if forecast_name is not None else f'{model_name}_forecast'
        
        new_pipe.forecasts[final_forecast_name] = {
            'forecast': forecast,
            'model_name': model_name,
            'periods': periods,
            'freq': freq,
            'include_history': include_history
        }
        
        new_pipe.current_analysis = f'forecast_{final_forecast_name}'
        
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
        
        # Add capacity column for logistic growth if needed
        if model.growth == 'logistic':
            if 'cap' in new_pipe.data.columns:
                # Use the same capacity value for all future periods
                cap_value = new_pipe.data['cap'].iloc[-1]  # Use last historical capacity value
                future['cap'] = cap_value
            else:
                raise ValueError("Logistic growth requires 'cap' column in data")
        
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
        final_forecast_name = forecast_name if forecast_name is not None else f'{model_name}_forecast_with_regressors'
        
        new_pipe.forecasts[final_forecast_name] = {
            'forecast': forecast,
            'model_name': model_name,
            'periods': periods,
            'freq': freq,
            'include_history': include_history,
            'regressor_future_values': regressor_future_values
        }
        
        new_pipe.current_analysis = f'forecast_{final_forecast_name}'
        
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
        final_cv_name = cv_name if cv_name is not None else f'{model_name}_cv'
        
        new_pipe.cross_validation_results[final_cv_name] = {
            'cv_results': df_cv,
            'performance_metrics': df_p,
            'initial': initial,
            'period': period,
            'horizon': horizon
        }
        
        new_pipe.current_analysis = f'cross_validate_{final_cv_name}'
        
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
            actual_data = new_pipe.data[new_pipe.data['ds'] > cutoff]
        else:
            actual_data = new_pipe.data
        
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
        
        # Plot forecast with error handling
        try:
            fig1 = model.plot(forecast_df, figsize=figsize)
            plt.title(f'Forecast: {forecast_name}')
            plt.tight_layout()
            plt.show()
        except Exception as e:
            print(f"Warning: Prophet plotting failed with error: {e}")
            print("Creating custom forecast plot...")
            
            # Create custom plot
            plt.figure(figsize=figsize)
            
            # Plot historical data
            if 'y' in forecast_df.columns:
                historical_mask = ~forecast_df['y'].isna()
                plt.plot(forecast_df.loc[historical_mask, 'ds'], 
                        forecast_df.loc[historical_mask, 'y'], 
                        'ko', markersize=3, label='Historical')
            
            # Plot forecast
            plt.plot(forecast_df['ds'], forecast_df['yhat'], 'b-', label='Forecast')
            
            # Plot confidence intervals
            if 'yhat_lower' in forecast_df.columns and 'yhat_upper' in forecast_df.columns:
                plt.fill_between(forecast_df['ds'], 
                               forecast_df['yhat_lower'], 
                               forecast_df['yhat_upper'], 
                               alpha=0.3, color='blue', label='Confidence Interval')
            
            plt.title(f'Forecast: {forecast_name}')
            plt.xlabel('Date')
            plt.ylabel('Value')
            plt.legend()
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.show()
        
        # Plot components if requested
        if show_components:
            try:
                fig2 = model.plot_components(forecast_df, figsize=(12, 8))
                plt.suptitle(f'Forecast Components: {forecast_name}')
                plt.tight_layout()
                plt.show()
            except Exception as e:
                print(f"Warning: Prophet component plotting failed with error: {e}")
                print("Skipping component plot...")
        
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
        
        # Plot cross-validation metric with error handling
        try:
            fig = plot_cross_validation_metric(cv_data['cv_results'], metric=metric, figsize=figsize)
            plt.title(f'Cross-Validation {metric.upper()}: {cv_name}')
            plt.tight_layout()
            plt.show()
        except Exception as e:
            print(f"Warning: Prophet cross-validation plotting failed with error: {e}")
            print("Creating custom cross-validation plot...")
            
            # Create custom plot
            plt.figure(figsize=figsize)
            
            # Plot metric over time
            cv_results = cv_data['cv_results']
            if metric in cv_results.columns:
                plt.plot(cv_results['ds'], cv_results[metric], 'b-', marker='o', markersize=3)
                plt.title(f'Cross-Validation {metric.upper()}: {cv_name}')
                plt.xlabel('Date')
                plt.ylabel(metric.upper())
                plt.xticks(rotation=45)
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                plt.show()
            else:
                print(f"Metric '{metric}' not found in cross-validation results.")
                print(f"Available metrics: {list(cv_results.columns)}")
        
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


def load_prophet_model(
    filepath: str,
    model_name: str = 'loaded_model'
):
    """
    Load a previously saved Prophet forecasting model
    
    Parameters:
    -----------
    filepath : str
        Path to the saved model file
    model_name : str
        Name for the loaded model
        
    Returns:
    --------
    Callable
        Function that loads Prophet models into a ProphetPipe
    """
    def _load_prophet_model(pipe):
        try:
            model_package = joblib.load(filepath)
            
            new_pipe = pipe.copy()
            
            # Restore model
            new_pipe.models[model_name] = model_package['model']
            
            # Restore configuration
            if 'config' in model_package:
                new_pipe.model_configs[model_name] = model_package['config']
            
            # Restore regressors
            if 'regressors' in model_package:
                new_pipe.regressors = model_package['regressors']
            
            # Restore holidays
            if 'holidays' in model_package:
                new_pipe.holidays = model_package['holidays']
            
            new_pipe.current_analysis = f'loaded_model_{model_name}'
            
            print(f"Successfully loaded Prophet model from: {filepath}")
            print(f"Model name: {model_name}")
            if 'config' in model_package:
                config = model_package['config']
                print(f"Growth: {config.get('growth', 'unknown')}")
                print(f"Seasonality mode: {config.get('seasonality_mode', 'unknown')}")
                print(f"Number of changepoints: {config.get('n_changepoints', 'unknown')}")
            print(f"Number of regressors: {len(model_package.get('regressors', {}))}")
            print(f"Number of holiday groups: {len(model_package.get('holidays', {}))}")
            
            return new_pipe
            
        except Exception as e:
            raise ValueError(f"Failed to load model from {filepath}: {str(e)}")
    
    return _load_prophet_model


def add_features(
    feature_columns: List[str],
    feature_type: str = 'regressor',
    feature_name: str = 'additional_features'
):
    """
    Add new features to the Prophet forecasting pipeline
    
    Parameters:
    -----------
    feature_columns : List[str]
        List of new feature column names to add
    feature_type : str
        Type of features ('regressor', 'external', 'derived')
    feature_name : str
        Name for the feature addition operation
        
    Returns:
    --------
    Callable
        Function that adds features to a ProphetPipe
    """
    def _add_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided before adding features.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate that new features exist in the data
        missing_features = [col for col in feature_columns if col not in df.columns]
        if missing_features:
            raise ValueError(f"Missing features in data: {missing_features}")
        
        # Add features based on type
        if feature_type == 'regressor':
            # Add as regressors for Prophet models
            for col in feature_columns:
                new_pipe.regressors[col] = {
                    'prior_scale': 10.0,
                    'standardize': 'auto'
                }
            print(f"Added {len(feature_columns)} regressor features: {feature_columns}")
            
        elif feature_type == 'external':
            # Store external features (not used directly by Prophet but available for analysis)
            if not hasattr(new_pipe, 'external_features'):
                new_pipe.external_features = {}
            new_pipe.external_features[feature_name] = {
                'columns': feature_columns,
                'type': 'external'
            }
            print(f"Added {len(feature_columns)} external features: {feature_columns}")
            
        elif feature_type == 'derived':
            # Store derived features (computed from existing features)
            if not hasattr(new_pipe, 'derived_features'):
                new_pipe.derived_features = {}
            new_pipe.derived_features[feature_name] = {
                'columns': feature_columns,
                'type': 'derived'
            }
            print(f"Added {len(feature_columns)} derived features: {feature_columns}")
        
        else:
            raise ValueError(f"Unknown feature type: {feature_type}")
        
        new_pipe.current_analysis = f'add_features_{feature_name}'
        
        return new_pipe
    
    return _add_features


def retrain_prophet_model(
    model_name: str,
    new_data: Optional[pd.DataFrame] = None,
    update_config: Optional[Dict] = None,
    retrain_name: str = 'retrained_model'
):
    """
    Retrain a Prophet model with new data or updated configuration
    
    Parameters:
    -----------
    model_name : str
        Name of the existing model to retrain
    new_data : Optional[pd.DataFrame]
        New data to use for retraining (if None, uses existing data)
    update_config : Optional[Dict]
        Updated configuration parameters for the model
    retrain_name : str
        Name for the retrained model
        
    Returns:
    --------
    Callable
        Function that retrains Prophet models from a ProphetPipe
    """
    def _retrain_prophet_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for retraining.")
        
        new_pipe = pipe.copy()
        
        # Get the original model configuration
        original_config = new_pipe.model_configs.get(model_name, {}).copy()
        
        # Update configuration if provided
        if update_config:
            original_config.update(update_config)
        
        # Determine data to use for retraining
        if new_data is not None:
            retrain_data = new_data.copy()
            
            # Ensure data has required columns (ds, y)
            if 'ds' not in retrain_data.columns or 'y' not in retrain_data.columns:
                raise ValueError("New data must have 'ds' and 'y' columns for Prophet")
            
            # Convert ds to datetime if needed
            if not pd.api.types.is_datetime64_any_dtype(retrain_data['ds']):
                retrain_data['ds'] = pd.to_datetime(retrain_data['ds'])
            
            # Sort by date
            retrain_data = retrain_data.sort_values('ds').reset_index(drop=True)
        else:
            retrain_data = new_pipe.data
            if retrain_data is None:
                raise ValueError("No data available for retraining.")
        
        # Create new model with updated configuration
        retrained_model = Prophet(
            growth=original_config.get('growth', 'linear'),
            seasonality_mode=original_config.get('seasonality_mode', 'additive'),
            changepoint_prior_scale=original_config.get('changepoint_prior_scale', 0.05),
            seasonality_prior_scale=original_config.get('seasonality_prior_scale', 10.0),
            holidays_prior_scale=original_config.get('holidays_prior_scale', 10.0),
            n_changepoints=original_config.get('n_changepoints', 25),
            changepoint_range=original_config.get('changepoint_range', 0.8),
            yearly_seasonality=original_config.get('yearly_seasonality', 'auto'),
            weekly_seasonality=original_config.get('weekly_seasonality', 'auto'),
            daily_seasonality=original_config.get('daily_seasonality', 'auto')
        )
        
        # Add holidays if any
        for holiday_key, holiday_config in new_pipe.holidays.items():
            retrained_model.holidays = holiday_config['holidays_df']
        
        # Add regressors if any
        for regressor, config in new_pipe.regressors.items():
            if regressor in retrain_data.columns:
                retrained_model.add_regressor(
                    regressor,
                    prior_scale=config['prior_scale'],
                    standardize=config['standardize']
                )
        
        # Fit the retrained model
        retrained_model.fit(retrain_data)
        
        # Store the retrained model
        new_pipe.models[retrain_name] = retrained_model
        new_pipe.model_configs[retrain_name] = original_config
        
        # Update data if using new data
        if new_data is not None:
            new_pipe.data = retrain_data
        
        new_pipe.current_analysis = f'retrain_{retrain_name}'
        
        print(f"Successfully retrained model '{model_name}' as '{retrain_name}'")
        print(f"Growth: {original_config.get('growth', 'linear')}")
        print(f"Seasonality mode: {original_config.get('seasonality_mode', 'additive')}")
        print(f"Number of changepoints: {original_config.get('n_changepoints', 25)}")
        print(f"Data points: {len(retrain_data)}")
        print(f"Date range: {retrain_data['ds'].min()} to {retrain_data['ds'].max()}")
        
        return new_pipe
    
    return _retrain_prophet_model


def predict_forecast(
    model_name: str,
    periods: int,
    freq: str = 'D',
    include_history: bool = True,
    regressor_future_values: Optional[Dict[str, Union[List, pd.Series, np.ndarray]]] = None,
    prediction_name: str = 'forecast_prediction'
):
    """
    Generate forecasts using a trained Prophet model
    
    Parameters:
    -----------
    model_name : str
        Name of the trained model to use for prediction
    periods : int
        Number of periods to forecast
    freq : str
        Frequency of forecasts
    include_history : bool
        Whether to include historical period in forecast
    regressor_future_values : Optional[Dict[str, Union[List, pd.Series, np.ndarray]]]
        Future values for regressors if the model uses them
    prediction_name : str
        Name for the prediction results
        
    Returns:
    --------
    Callable
        Function that generates forecasts from a ProphetPipe
    """
    def _predict_forecast(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for prediction.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=periods, freq=freq, include_history=include_history)
        
        # Add capacity column for logistic growth if needed
        if model.growth == 'logistic':
            if new_pipe.data is not None and 'cap' in new_pipe.data.columns:
                # Use the same capacity value for all future periods
                cap_value = new_pipe.data['cap'].iloc[-1]  # Use last historical capacity value
                future['cap'] = cap_value
            else:
                raise ValueError("Logistic growth requires 'cap' column in data")
        
        # Add regressor values for future periods if needed
        if regressor_future_values:
            if include_history:
                # Get historical regressor values
                historical_length = len(new_pipe.data) if new_pipe.data is not None else 0
                
                for regressor, future_values in regressor_future_values.items():
                    if regressor not in new_pipe.regressors:
                        warnings.warn(f"Regressor '{regressor}' not in model. Skipping.")
                        continue
                    
                    # Historical values
                    historical_values = new_pipe.data[regressor].values if new_pipe.data is not None and regressor in new_pipe.data.columns else [0] * historical_length
                    
                    # Combine historical and future
                    all_values = list(historical_values) + list(future_values)
                    future[regressor] = all_values[:len(future)]
            else:
                # Only future values
                for regressor, future_values in regressor_future_values.items():
                    future[regressor] = future_values
        elif new_pipe.regressors:
            warnings.warn("Model has regressors but no future values provided. "
                         "Forecast may be incomplete.")
        
        # Generate forecast
        forecast = model.predict(future)
        
        # Store prediction results
        if not hasattr(new_pipe, 'predictions'):
            new_pipe.predictions = {}
        
        new_pipe.predictions[prediction_name] = {
            'forecast': forecast,
            'model_name': model_name,
            'periods': periods,
            'freq': freq,
            'include_history': include_history,
            'regressor_future_values': regressor_future_values
        }
        
        new_pipe.current_analysis = f'prediction_{prediction_name}'
        
        print(f"Successfully generated forecast for {periods} periods")
        print(f"Model used: {model_name}")
        print(f"Frequency: {freq}")
        print(f"Include history: {include_history}")
        if regressor_future_values:
            print(f"Regressors used: {list(regressor_future_values.keys())}")
        
        return new_pipe
    
    return _predict_forecast


def get_prediction_results(
    prediction_name: Optional[str] = None
):
    """
    Get prediction results from the pipeline
    
    Parameters:
    -----------
    prediction_name : Optional[str]
        Specific prediction to retrieve (if None, returns all)
        
    Returns:
    --------
    Callable
        Function that retrieves prediction results from a ProphetPipe
    """
    def _get_prediction_results(pipe):
        if not hasattr(pipe, 'predictions') or not pipe.predictions:
            return {"error": "No prediction results found. Run predict_forecast first."}
        
        if prediction_name:
            if prediction_name in pipe.predictions:
                return pipe.predictions[prediction_name]
            else:
                return {"error": f"Prediction '{prediction_name}' not found"}
        
        return pipe.predictions
    
    return _get_prediction_results


def update_forecast_with_new_data(
    model_name: str,
    new_data: pd.DataFrame,
    periods: int,
    freq: str = 'D',
    include_history: bool = True,
    update_name: str = 'updated_forecast'
):
    """
    Update a forecast with new data by retraining and generating new predictions
    
    Parameters:
    -----------
    model_name : str
        Name of the existing model to update
    new_data : pd.DataFrame
        New data to incorporate
    periods : int
        Number of periods to forecast
    freq : str
        Frequency of forecasts
    include_history : bool
        Whether to include historical period in forecast
    update_name : str
        Name for the updated forecast
        
    Returns:
    --------
    Callable
        Function that updates forecasts with new data from a ProphetPipe
    """
    def _update_forecast_with_new_data(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for updating.")
        
        new_pipe = pipe.copy()
        
        # Retrain model with new data
        new_pipe = new_pipe | retrain_prophet_model(
            model_name=model_name,
            new_data=new_data,
            retrain_name=f"{model_name}_updated"
        )
        
        # Generate new forecast
        new_pipe = new_pipe | predict_forecast(
            model_name=f"{model_name}_updated",
            periods=periods,
            freq=freq,
            include_history=include_history,
            prediction_name=update_name
        )
        
        new_pipe.current_analysis = f'update_forecast_{update_name}'
        
        print(f"Successfully updated forecast with new data")
        print(f"Original model: {model_name}")
        print(f"Updated model: {model_name}_updated")
        print(f"New forecast: {update_name}")
        
        return new_pipe
    
    return _update_forecast_with_new_data


def print_prophet_summary(
    model_name: Optional[str] = None
):
    """
    Print comprehensive Prophet analysis summary
    
    Parameters:
    -----------
    model_name : Optional[str]
        Specific model to summarize (if None, summarizes all)
        
    Returns:
    --------
    Callable
        Function that prints Prophet summary from a ProphetPipe
    """
    def _print_prophet_summary(pipe):
        print(f"\n=== Prophet Forecasting Analysis Summary ===")
        
        if pipe.data is not None:
            print(f"Data points: {len(pipe.data)}")
            print(f"Date range: {pipe.data['ds'].min()} to {pipe.data['ds'].max()}")
        
        # Model information
        if pipe.models:
            print(f"\n=== Models ===")
            for name, model in pipe.models.items():
                if model_name is None or name == model_name:
                    print(f"\nModel: {name}")
                    if name in pipe.model_configs:
                        config = pipe.model_configs[name]
                        print(f"  Growth: {config.get('growth', 'unknown')}")
                        print(f"  Seasonality mode: {config.get('seasonality_mode', 'unknown')}")
                        print(f"  Changepoints: {config.get('n_changepoints', 'unknown')}")
                        print(f"  Changepoint prior scale: {config.get('changepoint_prior_scale', 'unknown')}")
        
        # Forecasts information
        if pipe.forecasts:
            print(f"\n=== Forecasts ===")
            for name, forecast in pipe.forecasts.items():
                print(f"\nForecast: {name}")
                print(f"  Model: {forecast.get('model_name', 'unknown')}")
                print(f"  Periods: {forecast.get('periods', 'unknown')}")
                print(f"  Frequency: {forecast.get('freq', 'unknown')}")
                print(f"  Include history: {forecast.get('include_history', 'unknown')}")
        
        # Metrics information
        if pipe.metrics:
            print(f"\n=== Metrics ===")
            for name, metrics in pipe.metrics.items():
                if isinstance(metrics, dict):
                    print(f"\nMetrics: {name}")
                    if 'mae' in metrics:
                        print(f"  MAE: {metrics['mae']:.4f}")
                    if 'rmse' in metrics:
                        print(f"  RMSE: {metrics['rmse']:.4f}")
                    if 'mape' in metrics:
                        print(f"  MAPE: {metrics['mape']:.2f}%")
                    if 'coverage' in metrics:
                        print(f"  Coverage: {metrics['coverage']:.1f}%")
        
        # Regressors information
        if pipe.regressors:
            print(f"\n=== Regressors ===")
            for name, config in pipe.regressors.items():
                print(f"  {name}: prior_scale={config.get('prior_scale', 'unknown')}")
        
        # Holidays information
        if pipe.holidays:
            print(f"\n=== Holidays ===")
            for name, config in pipe.holidays.items():
                n_holidays = len(config.get('holidays_df', []))
                print(f"  {name}: {n_holidays} holidays")
        
        return pipe
    
    return _print_prophet_summary