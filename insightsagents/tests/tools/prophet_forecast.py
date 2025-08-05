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
    hyperparameter_tuning,
    load_prophet_model,
    add_features,
    retrain_prophet_model,
    predict_forecast,
    get_prediction_results,
    update_forecast_with_new_data,
    print_prophet_summary
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

# Example 7: Model Management - Save and Load
def example_model_management():
    """
    Demonstrate model saving and loading functionality
    """
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='D')
    
    # Create time series with trend and seasonality
    trend = np.linspace(100, 200, len(dates))
    yearly_season = 20 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    weekly_season = 10 * np.sin(2 * np.pi * np.arange(len(dates)) / 7)
    noise = np.random.normal(0, 5, len(dates))
    
    value = trend + yearly_season + weekly_season + noise
    
    management_data = pd.DataFrame({
        'date': dates,
        'metric': value,
        'external_factor': np.random.normal(0, 10, len(dates))
    })
    
    # Create and save model
    print("Creating and saving model...")
    saved_model = (
        ProphetPipe.from_dataframe(management_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='metric'
        )
        
        # Add external regressor
        | add_regressors(
            regressor_columns=['external_factor'],
            prior_scale=0.1
        )
        
        # Configure model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            yearly_seasonality=True,
            weekly_seasonality=True,
            model_name='management_model'
        )
        
        # Fit model
        | fit_prophet(model_name='management_model')
        
        # Make forecast
        | make_forecast(
            periods=30,
            model_name='management_model'
        )
        
        # Save model with preprocessing
        | save_prophet_model(
            model_name='management_model',
            filepath='test_management_model.joblib',
            include_preprocessing=True
        )
    )
    
    # Load model in new pipeline
    print("\nLoading model in new pipeline...")
    loaded_model = (
        ProphetPipe.from_dataframe(management_data)
        
        # Load saved model
        | load_prophet_model(
            filepath='test_management_model.joblib',
            model_name='loaded_management_model'
        )
        
        # Make new forecast with loaded model
        | predict_forecast(
            model_name='loaded_management_model',
            periods=60,
            prediction_name='loaded_model_forecast'
        )
        
        # Get prediction results
        | get_prediction_results('loaded_model_forecast')
        
        # Print summary
        | print_prophet_summary('loaded_management_model')
    )
    
    # Compare original and loaded models
    print("\nComparing original and loaded models...")
    original_forecast = saved_model.forecasts.get('management_model_forecast', {})
    loaded_forecast = loaded_model.predictions.get('loaded_model_forecast', {})
    
    if original_forecast and loaded_forecast:
        print(f"Original forecast periods: {len(original_forecast.get('forecast', pd.DataFrame()))}")
        print(f"Loaded forecast periods: {len(loaded_forecast.get('forecast', pd.DataFrame()))}")
    
    return loaded_model


# Example 8: Feature Management and Addition
def example_feature_management():
    """
    Demonstrate adding new features to Prophet models
    """
    # Generate sample data with multiple features
    np.random.seed(123)
    dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='D')
    
    # Base metric
    base_metric = 100 + 0.5 * np.arange(len(dates))
    
    # Create various features
    feature1 = np.random.normal(0, 10, len(dates))  # Random feature
    feature2 = 20 * np.sin(2 * np.pi * np.arange(len(dates)) / 30)  # Monthly pattern
    feature3 = np.random.choice([0, 1], len(dates), p=[0.8, 0.2])  # Binary feature
    feature4 = np.cumsum(np.random.normal(0, 1, len(dates)))  # Cumulative feature
    
    # Combine into target
    target = base_metric + 0.3 * feature1 + 0.5 * feature2 + 10 * feature3 + 0.1 * feature4 + np.random.normal(0, 5, len(dates))
    
    feature_data = pd.DataFrame({
        'date': dates,
        'target': target,
        'feature1': feature1,
        'feature2': feature2,
        'feature3': feature3,
        'feature4': feature4,
        'derived_feature': feature1 * feature2,  # Interaction
        'external_metric': np.random.normal(50, 15, len(dates))
    })
    
    # Feature management pipeline
    print("Creating model with initial features...")
    feature_model = (
        ProphetPipe.from_dataframe(feature_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='target'
        )
        
        # Add initial regressors
        | add_regressors(
            regressor_columns=['feature1', 'feature2'],
            prior_scale=0.1
        )
        
        # Configure and fit initial model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            model_name='feature_model'
        )
        | fit_prophet(model_name='feature_model')
        | make_forecast(
            periods=30,
            model_name='feature_model'
        )
    )
    
    print("\nAdding new features...")
    # Add new features
    feature_model = (
        feature_model
        
        # Add new regressor features
        | add_features(
            feature_columns=['feature3', 'feature4'],
            feature_type='regressor',
            feature_name='additional_regressors'
        )
        
        # Add external features
        | add_features(
            feature_columns=['external_metric'],
            feature_type='external',
            feature_name='external_data'
        )
        
        # Add derived features
        | add_features(
            feature_columns=['derived_feature'],
            feature_type='derived',
            feature_name='interaction_features'
        )
    )
    
    print("\nRetraining model with new features...")
    # Retrain with new features
    feature_model = (
        feature_model
        
        # Configure new model with all features
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            model_name='enhanced_feature_model'
        )
        
        # Add all regressors
        | add_regressors(
            regressor_columns=['feature1', 'feature2', 'feature3', 'feature4'],
            prior_scale=0.1
        )
        
        # Fit enhanced model
        | fit_prophet(model_name='enhanced_feature_model')
        
        # Make forecast with future regressor values
        | predict_forecast(
            model_name='enhanced_feature_model',
            periods=30,
            regressor_future_values={
                'feature1': np.random.normal(0, 10, 30),
                'feature2': 20 * np.sin(2 * np.pi * np.arange(30) / 30),
                'feature3': np.random.choice([0, 1], 30, p=[0.8, 0.2]),
                'feature4': np.cumsum(np.random.normal(0, 1, 30))
            },
            prediction_name='enhanced_forecast'
        )
        
        # Print summary
        | print_prophet_summary()
    )
    
    return feature_model


# Example 9: Model Retraining and Updates
def example_model_retraining():
    """
    Demonstrate model retraining with new data and updated configurations
    """
    # Generate initial training data
    np.random.seed(456)
    initial_dates = pd.date_range(start='2022-01-01', end='2023-06-30', freq='D')
    
    # Initial pattern
    initial_trend = np.linspace(100, 150, len(initial_dates))
    initial_season = 20 * np.sin(2 * np.pi * np.arange(len(initial_dates)) / 365.25)
    initial_noise = np.random.normal(0, 5, len(initial_dates))
    
    initial_value = initial_trend + initial_season + initial_noise
    
    initial_data = pd.DataFrame({
        'date': initial_dates,
        'metric': initial_value,
        'regressor': np.random.normal(0, 10, len(initial_dates))
    })
    
    # Create initial model
    print("Creating initial model...")
    retrain_model = (
        ProphetPipe.from_dataframe(initial_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='metric'
        )
        
        # Add regressor
        | add_regressors(
            regressor_columns=['regressor'],
            prior_scale=0.1
        )
        
        # Configure initial model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            changepoint_prior_scale=0.05,
            model_name='initial_model'
        )
        
        # Fit initial model
        | fit_prophet(model_name='initial_model')
        
        # Make initial forecast
        | make_forecast(
            periods=30,
            model_name='initial_model'
        )
    )
    
    # Generate new data with different pattern
    print("\nGenerating new data with updated pattern...")
    new_dates = pd.date_range(start='2023-07-01', end='2023-12-31', freq='D')
    
    # New pattern with higher trend and different seasonality
    new_trend = np.linspace(150, 250, len(new_dates))  # Higher trend
    new_season = 30 * np.sin(2 * np.pi * np.arange(len(new_dates)) / 365.25 + np.pi/4)  # Phase shift
    new_noise = np.random.normal(0, 8, len(new_dates))  # Higher noise
    
    new_value = new_trend + new_season + new_noise
    
    new_data = pd.DataFrame({
        'date': new_dates,
        'metric': new_value,
        'regressor': np.random.normal(5, 15, len(new_dates))  # Different regressor pattern
    })
    
    # Retrain with new data
    print("\nRetraining model with new data...")
    retrain_model = (
        retrain_model
        
        # Retrain with new data
        | retrain_prophet_model(
            model_name='initial_model',
            new_data=new_data,
            retrain_name='retrained_model'
        )
        
        # Make forecast with retrained model
        | predict_forecast(
            model_name='retrained_model',
            periods=60,
            prediction_name='retrained_forecast'
        )
    )
    
    # Retrain with updated configuration
    print("\nRetraining with updated configuration...")
    retrain_model = (
        retrain_model
        
        # Retrain with updated parameters
        | retrain_prophet_model(
            model_name='retrained_model',
            update_config={
                'changepoint_prior_scale': 0.1,  # More flexible changepoints
                'seasonality_prior_scale': 20.0,  # Stronger seasonality
                'n_changepoints': 35  # More changepoints
            },
            retrain_name='optimized_model'
        )
        
        # Make forecast with optimized model
        | predict_forecast(
            model_name='optimized_model',
            periods=90,
            prediction_name='optimized_forecast'
        )
        
        # Compare models
        | print_prophet_summary()
    )
    
    return retrain_model


# Example 10: Advanced Prediction and Inference
def example_advanced_prediction():
    """
    Demonstrate advanced prediction capabilities with different scenarios
    """
    # Generate comprehensive dataset
    np.random.seed(789)
    dates = pd.date_range(start='2021-01-01', end='2023-12-31', freq='D')
    
    # Complex pattern with multiple components
    trend = np.linspace(100, 300, len(dates))
    yearly_season = 50 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    weekly_season = 20 * np.sin(2 * np.pi * np.arange(len(dates)) / 7)
    monthly_season = 15 * np.sin(2 * np.pi * np.arange(len(dates)) / 30)
    
    # External factors
    marketing_spend = 1000 + 200 * np.sin(2 * np.pi * np.arange(len(dates)) / 30) + np.random.normal(0, 50, len(dates))
    weather_effect = 10 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25 + np.pi) + np.random.normal(0, 3, len(dates))
    promotion_days = np.random.choice([0, 1], len(dates), p=[0.9, 0.1])
    
    # Combine all effects
    target = trend + yearly_season + weekly_season + monthly_season + 0.1 * marketing_spend + weather_effect + 50 * promotion_days + np.random.normal(0, 10, len(dates))
    
    prediction_data = pd.DataFrame({
        'date': dates,
        'target': target,
        'marketing_spend': marketing_spend,
        'weather': weather_effect,
        'promotion': promotion_days,
        'day_of_week': pd.to_datetime(dates).dayofweek,
        'month': pd.to_datetime(dates).month
    })
    
    # Create comprehensive model
    print("Creating comprehensive prediction model...")
    prediction_model = (
        ProphetPipe.from_dataframe(prediction_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='target'
        )
        
        # Add multiple regressors
        | add_regressors(
            regressor_columns=['marketing_spend', 'weather', 'promotion'],
            prior_scale=0.1
        )
        
        # Configure model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            model_name='prediction_model'
        )
        
        # Add custom seasonality
        | add_custom_seasonality(
            name='monthly',
            period=30.5,
            fourier_order=5,
            model_name='prediction_model'
        )
        
        # Fit model
        | fit_prophet(model_name='prediction_model')
    )
    
    # Scenario 1: Basic prediction
    print("\nScenario 1: Basic prediction...")
    prediction_model = (
        prediction_model
        
        | predict_forecast(
            model_name='prediction_model',
            periods=30,
            prediction_name='basic_prediction'
        )
    )
    
    # Scenario 2: Prediction with future regressor values
    print("\nScenario 2: Prediction with future regressor values...")
    prediction_model = (
        prediction_model
        
        | predict_forecast(
            model_name='prediction_model',
            periods=60,
            regressor_future_values={
                'marketing_spend': np.random.normal(1200, 100, 60),  # Increased marketing
                'weather': np.random.normal(0, 5, 60),  # Weather forecast
                'promotion': np.random.choice([0, 1], 60, p=[0.85, 0.15])  # Planned promotions
            },
            prediction_name='regressor_prediction'
        )
    )
    
    # Scenario 3: Prediction without history
    print("\nScenario 3: Prediction without historical data...")
    prediction_model = (
        prediction_model
        
        | predict_forecast(
            model_name='prediction_model',
            periods=90,
            include_history=False,
            regressor_future_values={
                'marketing_spend': np.random.normal(1500, 150, 90),  # Aggressive marketing
                'weather': np.random.normal(5, 8, 90),  # Seasonal weather
                'promotion': np.random.choice([0, 1], 90, p=[0.8, 0.2])  # More promotions
            },
            prediction_name='future_only_prediction'
        )
    )
    
    # Get and analyze prediction results
    print("\nAnalyzing prediction results...")
    basic_results = prediction_model | get_prediction_results('basic_prediction')
    regressor_results = prediction_model | get_prediction_results('regressor_prediction')
    future_results = prediction_model | get_prediction_results('future_only_prediction')
    
    # Print comprehensive summary
    prediction_model = prediction_model | print_prophet_summary()
    
    return prediction_model


# Example 11: Complete Model Lifecycle
def example_complete_lifecycle():
    """
    Demonstrate complete model lifecycle from creation to deployment
    """
    # Generate comprehensive dataset
    np.random.seed(999)
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='D')
    
    # Business metric with complex patterns
    base_trend = np.linspace(1000, 2000, len(dates))
    yearly_pattern = 200 * np.sin(2 * np.pi * np.arange(len(dates)) / 365.25)
    weekly_pattern = 100 * np.sin(2 * np.pi * np.arange(len(dates)) / 7)
    
    # Business factors
    advertising_budget = 500 + 100 * np.sin(2 * np.pi * np.arange(len(dates)) / 30) + np.random.normal(0, 20, len(dates))
    competitor_activity = np.random.choice([0, 1], len(dates), p=[0.7, 0.3])
    seasonal_events = np.where((pd.to_datetime(dates).month == 12) | (pd.to_datetime(dates).month == 1), 1, 0)
    
    # Combine effects
    business_metric = base_trend + yearly_pattern + weekly_pattern + 0.5 * advertising_budget - 100 * competitor_activity + 300 * seasonal_events + np.random.normal(0, 50, len(dates))
    
    lifecycle_data = pd.DataFrame({
        'date': dates,
        'business_metric': business_metric,
        'advertising_budget': advertising_budget,
        'competitor_activity': competitor_activity,
        'seasonal_events': seasonal_events,
        'day_of_week': pd.to_datetime(dates).dayofweek
    })
    
    print("=== Complete Model Lifecycle Demo ===")
    
    # Step 1: Initial Model Development
    print("\nStep 1: Initial Model Development")
    lifecycle_model = (
        ProphetPipe.from_dataframe(lifecycle_data)
        
        # Prepare data
        | prepare_prophet_data(
            date_column='date',
            value_column='business_metric'
        )
        
        # Add initial regressors
        | add_regressors(
            regressor_columns=['advertising_budget'],
            prior_scale=0.1
        )
        
        # Configure initial model
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            yearly_seasonality=True,
            weekly_seasonality=True,
            model_name='lifecycle_model'
        )
        
        # Fit model
        | fit_prophet(model_name='lifecycle_model')
        
        # Initial forecast
        | make_forecast(
            periods=30,
            model_name='lifecycle_model'
        )
        
        # Evaluate initial model
        | cross_validate_model(
            initial='730 days',
            period='180 days',
            horizon='30 days',
            model_name='lifecycle_model'
        )
    )
    
    # Step 2: Model Enhancement
    print("\nStep 2: Model Enhancement")
    lifecycle_model = (
        lifecycle_model
        
        # Add more features
        | add_features(
            feature_columns=['competitor_activity', 'seasonal_events'],
            feature_type='regressor',
            feature_name='business_factors'
        )
        
        # Retrain with enhanced features
        | retrain_prophet_model(
            model_name='lifecycle_model',
            update_config={
                'changepoint_prior_scale': 0.1,
                'seasonality_prior_scale': 15.0
            },
            retrain_name='enhanced_lifecycle_model'
        )
        
        # Enhanced forecast
        | predict_forecast(
            model_name='enhanced_lifecycle_model',
            periods=60,
            regressor_future_values={
                'advertising_budget': np.random.normal(600, 50, 60),
                'competitor_activity': np.random.choice([0, 1], 60, p=[0.6, 0.4]),
                'seasonal_events': [1 if i < 30 else 0 for i in range(60)]  # Holiday season
            },
            prediction_name='enhanced_forecast'
        )
    )
    
    # Step 3: Model Optimization
    print("\nStep 3: Model Optimization")
    param_grid = {
        'changepoint_prior_scale': [0.05, 0.1, 0.2],
        'seasonality_prior_scale': [10.0, 15.0, 20.0],
        'n_changepoints': [20, 25, 30]
    }
    
    lifecycle_model = (
        lifecycle_model
        
        # Hyperparameter tuning
        | hyperparameter_tuning(
            param_grid=param_grid,
            cv_initial='365 days',
            cv_period='90 days',
            cv_horizon='30 days',
            metric='mape',
            model_name='optimized_lifecycle_model'
        )
        
        # Forecast with optimized model
        | predict_forecast(
            model_name='optimized_lifecycle_model_best',
            periods=90,
            regressor_future_values={
                'advertising_budget': np.random.normal(700, 60, 90),
                'competitor_activity': np.random.choice([0, 1], 90, p=[0.5, 0.5]),
                'seasonal_events': [1 if i < 45 else 0 for i in range(90)]
            },
            prediction_name='optimized_forecast'
        )
    )
    
    # Step 4: Model Deployment
    print("\nStep 4: Model Deployment")
    lifecycle_model = (
        lifecycle_model
        
        # Save optimized model
        | save_prophet_model(
            model_name='optimized_lifecycle_model_best',
            filepath='deployed_lifecycle_model.joblib'
        )
    )
    
    # Step 5: Model Monitoring and Updates
    print("\nStep 5: Model Monitoring and Updates")
    
    # Simulate new data arrival
    new_dates = pd.date_range(start='2024-01-01', end='2024-03-31', freq='D')
    new_advertising = np.random.normal(800, 80, len(new_dates))  # Increased budget
    new_competitor = np.random.choice([0, 1], len(new_dates), p=[0.4, 0.6])  # More competition
    new_seasonal = np.zeros(len(new_dates))
    
    new_business_metric = (
        2000 + 0.8 * np.arange(len(new_dates)) +  # Higher trend
        200 * np.sin(2 * np.pi * np.arange(len(new_dates)) / 365.25) +  # Seasonality
        0.5 * new_advertising - 150 * new_competitor +  # Business factors
        np.random.normal(0, 60, len(new_dates))  # Noise
    )
    
    new_data = pd.DataFrame({
        'date': new_dates,
        'business_metric': new_business_metric,
        'advertising_budget': new_advertising,
        'competitor_activity': new_competitor,
        'seasonal_events': new_seasonal,
        'day_of_week': pd.to_datetime(new_dates).dayofweek
    })
    
    # Update model with new data
    lifecycle_model = (
        lifecycle_model
        
        # Update forecast with new data
        | update_forecast_with_new_data(
            model_name='optimized_lifecycle_model_best',
            new_data=new_data,
            periods=120,
            update_name='updated_forecast'
        )
        
        # Final evaluation
        | calculate_forecast_metrics('updated_forecast')
        | print_forecast_metrics('updated_forecast')
        
        # Comprehensive summary
        | print_prophet_summary()
    )
    
    print("\n=== Model Lifecycle Completed Successfully ===")
    
    return lifecycle_model

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
    
    print("\n" + "="*50)
    print("Example 7: Model Management - Save and Load")
    print("="*50)
    model_management_example = example_model_management()
    
    print("\n" + "="*50)
    print("Example 8: Feature Management and Addition")
    print("="*50)
    feature_management_example = example_feature_management()
    
    print("\n" + "="*50)
    print("Example 9: Model Retraining and Updates")
    print("="*50)
    retraining_example = example_model_retraining()
    
    print("\n" + "="*50)
    print("Example 10: Advanced Prediction and Inference")
    print("="*50)
    prediction_example = example_advanced_prediction()
    
    print("\n" + "="*50)
    print("Example 11: Complete Model Lifecycle")
    print("="*50)
    lifecycle_example = example_complete_lifecycle()
    
    print("\nAll Prophet examples completed successfully!")


