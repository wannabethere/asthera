# Prophet Pipeline Examples

from app.tools.mltools.models.prophet_forecast import (
    ProphetPipe,
    prepare_prophet_data,
    add_regressors,
    add_holidays,
    configure_prophet,
    add_custom_seasonality,
    fit_prophet,
    make_forecast,
    forecast_with_regressors,
    cross_validate_model,
    calculate_forecast_metrics,
    print_forecast_metrics,
    plot_forecast,
    plot_cross_validation,
    save_prophet_model,
    hyperparameter_tuning
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# Example 1: Basic Time Series Forecasting
def example_sales_forecasting():
    """
    Basic sales forecasting with Prophet
    """
    # Generate sample sales data
    np.random.seed(42)
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='D')
    
    # Create realistic sales pattern with trend, seasonality, and noise
    trend = np.linspace(1000, 1500, len(dates))
    yearly_season = 200 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    weekly_season = 100 * np.sin(2 * np.pi * np.arange(len(dates)) / 7)
    noise = np.random.normal(0, 50, len(dates))
    
    sales = trend + yearly_season + weekly_season + noise
    
    sales_data = pd.DataFrame({
        'date': dates,
        'sales': sales
    })
    
    # Basic sales forecasting pipeline
    sales_forecast = (
        ProphetPipe.from_dataframe(sales_data)
        
        # Prepare data for Prophet
        | prepare_prophet_data(
            date_column='date',
            value_column='sales'
        )
        
        # Configure Prophet model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            model_name='sales_model'
        )
        
        # Fit the model
        | fit_prophet(model_name='sales_model')
        
        # Make 90-day forecast
        | make_forecast(
            periods=90,
            freq='D',
            model_name='sales_model'
        )
        
        # Cross-validate the model
        | cross_validate_model(
            initial='730 days',  # 2 years
            period='180 days',   # 6 months
            horizon='30 days',   # 1 month forecast
            model_name='sales_model'
        )
        
        # Plot results
        | plot_forecast('sales_model_forecast', show_components=True)
        | plot_cross_validation('sales_model_cv', metric='mape')
        
        # Save model
        | save_prophet_model(model_name='sales_model')
    )
    
    return sales_forecast


# Example 2: E-commerce with Holidays and Regressors
def example_ecommerce_forecasting():
    """
    E-commerce revenue forecasting with holidays and marketing spend
    """
    # Generate e-commerce data
    np.random.seed(123)
    dates = pd.date_range(start='2021-01-01', end='2023-12-31', freq='D')
    
    # Base revenue with growth
    base_revenue = np.linspace(5000, 8000, len(dates))
    
    # Seasonal patterns
    yearly_season = 1000 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    weekly_season = 500 * (1 - 0.3 * (pd.to_datetime(dates).dayofweek >= 5))  # Weekend effect
    
    # Marketing spend (external regressor)
    marketing_spend = 1000 + 500 * np.sin(2 * np.pi * np.arange(len(dates)) / 30) + np.random.normal(0, 100, len(dates))
    marketing_effect = 0.5 * marketing_spend  # Marketing influence on revenue
    
    # Holiday effects (Black Friday, Christmas, etc.)
    holiday_effect = np.zeros(len(dates))
    for i, date in enumerate(dates):
        if date.month == 11 and date.day >= 25:  # Black Friday week
            holiday_effect[i] = 2000
        elif date.month == 12 and date.day >= 20:  # Christmas week
            holiday_effect[i] = 1500
        elif date.month == 1 and date.day <= 7:  # New Year week
            holiday_effect[i] = 800
    
    # Combine all effects
    revenue = base_revenue + yearly_season + weekly_season + marketing_effect + holiday_effect + np.random.normal(0, 200, len(dates))
    
    ecommerce_data = pd.DataFrame({
        'date': dates,
        'revenue': revenue,
        'marketing_spend': marketing_spend,
        'is_weekend': (pd.to_datetime(dates).dayofweek >= 5).astype(int)
    })
    
    # Create holiday dataframe
    holidays_df = pd.DataFrame({
        'ds': pd.to_datetime(['2021-11-26', '2022-11-25', '2023-11-24',  # Black Friday
                             '2021-12-25', '2022-12-25', '2023-12-25',  # Christmas
                             '2022-01-01', '2023-01-01', '2024-01-01']), # New Year
        'holiday': ['black_friday', 'black_friday', 'black_friday',
                   'christmas', 'christmas', 'christmas',
                   'new_year', 'new_year', 'new_year']
    })
    
    # E-commerce forecasting pipeline
    ecommerce_forecast = (
        ProphetPipe.from_dataframe(ecommerce_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='revenue'
        )
        
        # Add marketing spend as regressor
        | add_regressors(
            regressor_columns=['marketing_spend', 'is_weekend'],
            prior_scale=0.5
        )
        
        # Add holidays
        | add_holidays(
            holiday_data=holidays_df,
            holiday_name='retail_holidays',
            prior_scale=10.0,
            lower_window=-1,
            upper_window=1
        )
        
        # Configure model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
            yearly_seasonality=True,
            weekly_seasonality=True,
            model_name='ecommerce_model'
        )
        
        # Add custom monthly seasonality
        | add_custom_seasonality(
            name='monthly',
            period=30.5,
            fourier_order=5,
            model_name='ecommerce_model'
        )
        
        # Fit model
        | fit_prophet(model_name='ecommerce_model')
        
        # Forecast with future marketing spend
        | forecast_with_regressors(
            periods=60,
            regressor_future_values={
                'marketing_spend': np.random.normal(1200, 100, 60),  # Projected marketing spend
                'is_weekend': [1 if i % 7 >= 5 else 0 for i in range(60)]  # Weekend pattern
            },
            model_name='ecommerce_model'
        )
        
        # Evaluate with historical data split
        | calculate_forecast_metrics(
            'ecommerce_model_forecast_with_regressors',
            cutoff_date='2023-10-01'
        )
        
        # Print metrics
        | print_forecast_metrics('ecommerce_model_forecast_with_regressors')
        
        # Cross-validate
        | cross_validate_model(
            initial='365 days',
            period='90 days',
            horizon='30 days',
            model_name='ecommerce_model'
        )
        
        # Visualize results
        | plot_forecast('ecommerce_model_forecast_with_regressors', show_components=True)
        | plot_cross_validation('ecommerce_model_cv', metric='rmse')
    )
    
    return ecommerce_forecast


# Example 3: Web Traffic with Multiple Seasonalities
def example_web_traffic_forecasting():
    """
    Web traffic forecasting with hourly data and multiple seasonalities
    """
    # Generate hourly web traffic data
    np.random.seed(456)
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='H')
    
    # Base traffic with growth
    base_traffic = np.linspace(1000, 1500, len(dates))
    
    # Multiple seasonal patterns
    daily_season = 300 * np.sin(2 * np.pi * dates.hour / 24 - np.pi/2)  # Peak in afternoon
    weekly_season = 200 * np.sin(2 * np.pi * dates.dayofweek / 7)  # Lower on weekends
    monthly_season = 150 * np.sin(2 * np.pi * dates.day / 30)
    
    # Business hours effect
    business_hours = ((dates.hour >= 9) & (dates.hour <= 17) & (dates.dayofweek < 5)).astype(int)
    business_effect = 400 * business_hours
    
    # Combine effects
    traffic = base_traffic + daily_season + weekly_season + monthly_season + business_effect + np.random.normal(0, 100, len(dates))
    
    traffic_data = pd.DataFrame({
        'timestamp': dates,
        'page_views': traffic,
        'is_business_hours': business_hours
    })
    
    # Web traffic forecasting pipeline
    traffic_forecast = (
        ProphetPipe.from_dataframe(traffic_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='timestamp',
            value_column='page_views'
        )
        
        # Add business hours regressor
        | add_regressors(
            regressor_columns=['is_business_hours'],
            prior_scale=0.1
        )
        
        # Configure with daily seasonality
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,  # Not enough data for yearly
            model_name='traffic_model'
        )
        
        # Add custom seasonalities
        | add_custom_seasonality(
            name='monthly',
            period=30.5 * 24,  # Monthly in hours
            fourier_order=3,
            model_name='traffic_model'
        )
        
        | add_custom_seasonality(
            name='quarterly',
            period=91.25 * 24,  # Quarterly in hours
            fourier_order=2,
            model_name='traffic_model'
        )
        
        # Fit model
        | fit_prophet(model_name='traffic_model')
        
        # Make 7-day hourly forecast
        | forecast_with_regressors(
            periods=7 * 24,  # 7 days * 24 hours
            regressor_future_values={
                'is_business_hours': [1 if (i % 24 >= 9 and i % 24 <= 17 and (i // 24) % 7 < 5) else 0 
                                    for i in range(7 * 24)]
            },
            freq='H',
            model_name='traffic_model'
        )
        
        # Cross-validate
        | cross_validate_model(
            initial='30 days',
            period='7 days',
            horizon='24 hours',
            model_name='traffic_model'
        )
        
        # Calculate and print metrics
        | calculate_forecast_metrics('traffic_model_forecast_with_regressors')
        | print_forecast_metrics('traffic_model_forecast_with_regressors')
        
        # Plot results
        | plot_forecast('traffic_model_forecast_with_regressors', show_components=True)
    )
    
    return traffic_forecast


# Example 4: Financial Forecasting with Logistic Growth
def example_financial_forecasting():
    """
    Financial metrics forecasting with capacity constraints (logistic growth)
    """
    # Generate financial data with capacity limit
    np.random.seed(789)
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='MS')  # Monthly
    
    # Logistic growth parameters
    capacity = 10000  # Maximum possible revenue
    k = 0.1  # Growth rate
    m = 24  # Midpoint month
    
    # Logistic growth curve
    t = np.arange(len(dates))
    base_revenue = capacity / (1 + np.exp(-k * (t - m)))
    
    # Seasonal effects
    seasonal = 500 * np.sin(2 * np.pi * t / 12)  # Annual seasonality
    
    # Economic indicators (external factors)
    economic_index = 100 + 10 * np.sin(2 * np.pi * t / 18) + np.random.normal(0, 5, len(dates))
    economic_effect = 20 * (economic_index - 100)
    
    # Market volatility
    volatility = np.random.normal(0, 200, len(dates))
    
    revenue = base_revenue + seasonal + economic_effect + volatility
    
    financial_data = pd.DataFrame({
        'date': dates,
        'revenue': revenue,
        'economic_index': economic_index,
        'cap': capacity  # Capacity for logistic growth
    })
    
    # Financial forecasting pipeline
    financial_forecast = (
        ProphetPipe.from_dataframe(financial_data)
        
        # Prepare data with capacity for logistic growth
        | prepare_prophet_data(
            date_column='date',
            value_column='revenue'
        )
        
        # Add economic indicator as regressor
        | add_regressors(
            regressor_columns=['economic_index'],
            prior_scale=0.1
        )
    )
    
    # Add capacity column for logistic growth
    financial_forecast.data['cap'] = capacity
    
    # Continue pipeline
    financial_forecast = (
        financial_forecast
        
        # Configure with logistic growth
        | configure_prophet(
            growth='logistic',  # Logistic growth instead of linear
            seasonality_mode='additive',
            changepoint_prior_scale=0.1,
            yearly_seasonality=True,
            weekly_seasonality=False,  # Monthly data doesn't need weekly
            model_name='financial_model'
        )
        
        # Fit model
        | fit_prophet(model_name='financial_model')
        
        # Forecast 12 months ahead
        | forecast_with_regressors(
            periods=12,
            regressor_future_values={
                'economic_index': 100 + np.random.normal(0, 3, 12)  # Future economic projections
            },
            freq='MS',
            model_name='financial_model'
        )
        
        # Cross-validate
        | cross_validate_model(
            initial='730 days',
            period='180 days',
            horizon='90 days',
            model_name='financial_model'
        )
        
        # Evaluate and visualize
        | calculate_forecast_metrics('financial_model_forecast_with_regressors')
        | print_forecast_metrics('financial_model_forecast_with_regressors')
        | plot_forecast('financial_model_forecast_with_regressors', show_components=True)
        | plot_cross_validation('financial_model_cv', metric='mape')
    )
    
    # Add capacity to future dataframe for logistic growth
    if 'financial_model_forecast_with_regressors' in financial_forecast.forecasts:
        forecast_data = financial_forecast.forecasts['financial_model_forecast_with_regressors']['forecast']
        forecast_data['cap'] = capacity
    
    return financial_forecast


# Example 5: Hyperparameter Tuning and Model Comparison
def example_model_optimization():
    """
    Hyperparameter tuning and model comparison
    """
    # Generate sample data
    np.random.seed(999)
    dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='D')
    
    # Create complex time series
    trend = np.linspace(100, 200, len(dates))
    yearly = 20 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    weekly = 10 * np.sin(2 * np.pi * np.arange(len(dates)) / 7)
    noise = np.random.normal(0, 5, len(dates))
    changepoints = np.where(np.arange(len(dates)) > len(dates)//2, 50, 0)  # Mid-series change
    
    value = trend + yearly + weekly + changepoints + noise
    
    optimization_data = pd.DataFrame({
        'date': dates,
        'metric': value
    })
    
    # Define parameter grid for tuning
    param_grid = {
        'changepoint_prior_scale': [0.01, 0.05, 0.1, 0.2],
        'seasonality_prior_scale': [1.0, 10.0, 20.0],
        'n_changepoints': [15, 25, 35],
        'seasonality_mode': ['additive', 'multiplicative']
    }
    
    # Hyperparameter tuning pipeline
    optimized_model = (
        ProphetPipe.from_dataframe(optimization_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='metric'
        )
        
        # Perform hyperparameter tuning
        | hyperparameter_tuning(
            param_grid=param_grid,
            cv_initial='365 days',
            cv_period='90 days',
            cv_horizon='30 days',
            metric='mape',
            model_name='optimized_model'
        )
        
        # Make forecast with best model
        | make_forecast(
            periods=60,
            model_name='optimized_model_best'
        )
        
        # Evaluate best model
        | calculate_forecast_metrics('optimized_model_best_forecast')
        | print_forecast_metrics('optimized_model_best_forecast')
        
        # Plot results
        | plot_forecast('optimized_model_best_forecast', show_components=True)
        
        # Save optimized model
        | save_prophet_model(
            model_name='optimized_model_best',
            filepath='best_prophet_model.joblib'
        )
    )
    
    return optimized_model


# Example 6: Multi-step Forecasting Pipeline
def example_multi_step_forecasting():
    """
    Complete multi-step forecasting with evaluation on multiple horizons
    """
    # Generate retail sales data
    np.random.seed(111)
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='D')
    
    # Complex seasonal pattern
    base = 1000 + 0.5 * np.arange(len(dates))  # Linear trend
    yearly = 200 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    weekly = 150 * np.sin(2 * np.pi * np.arange(len(dates)) / 7)
    monthly = 100 * np.sin(2 * np.pi * np.arange(len(dates)) / 30)
    
    # Promotional effects
    promo_effect = np.random.choice([0, 0, 0, 300], len(dates))  # Random promotions
    
    # Weather impact
    weather_impact = 50 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25 + np.pi)  # Inverse seasonal
    
    sales = base + yearly + weekly + monthly + promo_effect + weather_impact + np.random.normal(0, 50, len(dates))
    
    retail_data = pd.DataFrame({
        'date': dates,
        'daily_sales': sales,
        'promotion': (promo_effect > 0).astype(int),
        'temperature': 20 + 15 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25) + np.random.normal(0, 3, len(dates))
    })
    
    # Multi-step forecasting pipeline
    multi_step_forecast = (
        ProphetPipe.from_dataframe(retail_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='daily_sales'
        )
        
        # Add external regressors
        | add_regressors(
            regressor_columns=['promotion', 'temperature'],
            prior_scale=0.1
        )
        
        # Configure base model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            changepoint_prior_scale=0.05,
            model_name='retail_model'
        )
        
        # Add custom seasonalities
        | add_custom_seasonality(
            name='monthly',
            period=30.5,
            fourier_order=5,
            model_name='retail_model'
        )
        
        # Fit model
        | fit_prophet(model_name='retail_model')
    )
    
    # Multiple forecast horizons
    horizons = [7, 14, 30, 60, 90]  # Days
    
    for horizon in horizons:
        # Make forecast for each horizon
        multi_step_forecast = multi_step_forecast | forecast_with_regressors(
            periods=horizon,
            regressor_future_values={
                'promotion': np.random.choice([0, 0, 0, 1], horizon),  # Future promotions
                'temperature': 20 + 15 * np.sin(2 * np.pi * np.arange(horizon) / 365.25) + np.random.normal(0, 2, horizon)
            },
            model_name='retail_model',
            forecast_name=f'forecast_{horizon}d'
        )
        
        # Calculate metrics for each horizon
        multi_step_forecast = (
            multi_step_forecast
            | calculate_forecast_metrics(f'forecast_{horizon}d')
            | print_forecast_metrics(f'forecast_{horizon}d')
        )
    
    # Cross-validation with multiple horizons
    for horizon in [7, 14, 30]:
        multi_step_forecast = multi_step_forecast | cross_validate_model(
            initial='365 days',
            period=f'{horizon} days',
            horizon=f'{horizon} days',
            model_name='retail_model',
            cv_name=f'cv_{horizon}d'
        )
    
    # Plot forecasts
    multi_step_forecast = multi_step_forecast | plot_forecast('forecast_30d', show_components=True)
    
    return multi_step_forecast


if __name__ == "__main__":
    print("Running Prophet Pipeline Examples...")
    
    print("\n" + "="*50)
    print("Example 1: Basic Sales Forecasting")
    print("="*50)
    sales_model = example_sales_forecasting()
    
    print("\n" + "="*50)
    print("Example 2: E-commerce with Holidays and Regressors")
    print("="*50)
    ecommerce_model = example_ecommerce_forecasting()
    
    print("\n" + "="*50)
    print("Example 3: Web Traffic with Multiple Seasonalities")
    print("="*50)
    traffic_model = example_web_traffic_forecasting()
    
    print("\n" + "="*50)
    print("Example 4: Financial Forecasting with Logistic Growth")
    print("="*50)
    financial_model = example_financial_forecasting()
    
    print("\n" + "="*50)
    print("Example 5: Hyperparameter Tuning and Optimization")
    print("="*50)
    optimized_model = example_model_optimization()
    
    print("\n" + "="*50)
    print("Example 6: Multi-step Forecasting Pipeline")
    print("="*50)
    multi_step_model = example_multi_step_forecasting()
    
    print("\nAll Prophet examples completed successfully!")