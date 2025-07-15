import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Import our custom modules
from app.tools.mltools.anomalydetection import (
    AnomalyPipe, 
    detect_statistical_outliers, 
    detect_contextual_anomalies,
    calculate_seasonal_residuals,
    detect_anomalies_from_residuals,
    forecast_and_detect_anomalies,
    batch_detect_anomalies,
    get_anomaly_summary,
    get_top_anomalies
)

# Generate sample time series data with anomalies
def generate_sample_data(n_points=500):
    # Create date range
    dates = pd.date_range(start='2023-01-01', periods=n_points, freq='D')
    
    # Base signal: trend + seasonality + noise
    trend = np.linspace(100, 150, n_points)  # Upward trend
    seasonality = 15 * np.sin(2 * np.pi * np.arange(n_points) / 30)  # Monthly seasonality
    noise = np.random.normal(0, 3, n_points)  # Random noise
    
    # Create the clean signal
    signal = trend + seasonality + noise
    
    # Add anomalies
    anomaly_indices = [50, 120, 200, 320, 400, 450]
    
    # Point anomalies
    signal[anomaly_indices[0]] += 25
    signal[anomaly_indices[1]] -= 25
    
    # Contextual anomalies (seasonal pattern disruption)
    signal[anomaly_indices[2]:anomaly_indices[2]+5] += 15
    
    # Collective anomalies (level shift)
    signal[anomaly_indices[3]:anomaly_indices[3]+30] += 10
    signal[anomaly_indices[4]:anomaly_indices[4]+10] -= 20
    
    # Trend change
    for i in range(anomaly_indices[5], n_points):
        signal[i] += (i - anomaly_indices[5]) * 0.5
    
    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': dates,
        'value': signal,
        'day_of_week': dates.dayofweek,
        'month': dates.month
    })
    
    return df

# Generate data
data = generate_sample_data()

# Create an AnomalyPipe instance
anomaly_pipe = AnomalyPipe.from_dataframe(data)

# Detect statistical outliers
anomaly_pipe = anomaly_pipe | detect_statistical_outliers(
    columns='value',
    method='zscore',
    threshold=3.0
)

# Print summary of detected anomalies
print("Statistical Outliers Summary:")
outlier_summary = get_anomaly_summary()(anomaly_pipe)
print(f"Total anomalies found: {outlier_summary['total_anomalies']}")
print(f"Anomaly percentage: {outlier_summary['total_anomaly_percentage']:.2f}%")

# Apply contextual anomaly detection
anomaly_pipe = anomaly_pipe | detect_contextual_anomalies(
    columns='value',
    time_column='timestamp',
    method='residual',
    model_type='ewm',
    window=30
)

# Perform seasonal decomposition and anomaly detection on residuals
anomaly_pipe = anomaly_pipe | calculate_seasonal_residuals(
    columns='value',
    mtime_column='timestamp',
    mseasonal_period=30,  # Monthly seasonality
    mmethod='additive'
)

anomaly_pipe = anomaly_pipe | detect_anomalies_from_residuals(
    columns='value',
    method='modified_zscore',
    threshold=3.5
)

# Use forecasting for anomaly detection
anomaly_pipe = anomaly_pipe | forecast_and_detect_anomalies(
    columns='value',
    time_column='timestamp',
    forecast_periods=7,
    model='exponential_smoothing',
    threshold=2.5
)

# Apply ensemble method to combine results
anomaly_pipe = anomaly_pipe | batch_detect_anomalies(
    columns='value',
    methods=[
        {'name': 'statistical_outliers', 'params': {'columns': 'value', 'method': 'zscore'}},
        {'name': 'contextual_anomalies', 'params': {'columns': 'value', 'time_column': 'timestamp'}},
        {'name': 'residual_anomalies', 'params': {'columns': 'value'}}
    ],
    ensemble_method='majority'
)

# Get the top anomalies
top_anomalies = get_top_anomalies(
    n=10,
    time_column='timestamp'
)(anomaly_pipe)

print("\nTop 10 Anomalies:")
print(top_anomalies)



# Example of combining with other analysis tools
# For instance, with the TimeSeriesPipe for further analysis
from app.tools.mltools.timeseriesanalysis import TimeSeriesPipe, lead, variance_analysis

# Convert anomaly detection results to TimeSeriesPipe for more analysis
ts_pipe = TimeSeriesPipe(anomaly_pipe.data)

# Calculate volatility before and after anomalies
ts_pipe = ts_pipe | lead(
    columns=['value_ensemble_anomaly'],
    periods=1,
    time_column='timestamp'
) | variance_analysis(
    columns=['value'],
    method='rolling',
    window=10,
    time_column='timestamp'
)

# Display results from time series analysis
print("\nTime Series Analysis Results:")
ts_results = ts_pipe.data.head()
print(ts_results)