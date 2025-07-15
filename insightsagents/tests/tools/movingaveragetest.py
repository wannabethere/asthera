"""
Example usage of the Moving Aggregation Pipeline module
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Import our custom modules
from app.tools.mltools.movingaverages import (
    MovingAggrPipe, 
    moving_average,
    moving_variance,
    moving_sum,
    moving_quantile,
    moving_correlation,
    moving_zscore,
    moving_cumulative,
    moving_min_max,
    moving_count,
    moving_aggregate,
    time_weighted_average,
    expanding_window,
    moving_ratio,
    detect_turning_points
)

# Generate sample time series data
def generate_sample_data(n_points=500):
    # Create date range
    dates = pd.date_range(start='2023-01-01', periods=n_points, freq='D')
    
    # Base signal: trend + seasonality + noise
    trend = np.linspace(100, 150, n_points)  # Upward trend
    seasonality = 15 * np.sin(2 * np.pi * np.arange(n_points) / 30)  # Monthly seasonality
    noise = np.random.normal(0, 5, n_points)  # Random noise
    
    # Create the signal
    signal = trend + seasonality + noise
    
    # Add volatility clusters
    volatility_factor = 1 + 0.5 * np.sin(2 * np.pi * np.arange(n_points) / 90)
    signal2 = trend + seasonality + noise * volatility_factor
    
    # Create a correlated series
    correlated = signal * 0.7 + trend * 0.2 + np.random.normal(0, 10, n_points)
    
    # Create a categorical variable
    categories = np.random.choice(['A', 'B', 'C'], size=n_points)
    
    # Create a binary event indicator
    events = np.zeros(n_points)
    event_indices = np.random.choice(range(n_points), size=n_points//20, replace=False)
    events[event_indices] = 1
    
    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': dates,
        'value': signal,
        'value2': signal2,
        'correlated': correlated,
        'category': categories,
        'event': events,
        'day_of_week': dates.dayofweek,
        'month': dates.month,
        'day': dates.day
    })
    
    return df

# Generate sample data
data = generate_sample_data()

# Print sample of the data
print("Sample data:")
print(data.head())

# Create a MovingAggrPipe instance
pipe = MovingAggrPipe.from_dataframe(data)

# Example 1: Calculate simple, weighted, and exponential moving averages
# Example 1: Calculate simple, weighted, and exponential moving averages
pipe = pipe | moving_average(
    columns='value',
    window=30,
    method='simple'
) | moving_average(
    columns='value',
    window=30,
    method='weighted',
    output_suffix='_ma_weighted'  # Explicitly set the suffix
) | moving_average(
    columns='value',
    window=30,
    method='exponential',
    output_suffix='_ma_exponential'  # Explicitly set the suffix
)

# Example 2: Calculate moving variance and standard deviation
pipe = pipe | moving_variance(
    columns=['value', 'value2'],
    window=30
)

# Example 3: Calculate moving quantiles (25th, 50th, 75th percentiles)
pipe = pipe | moving_quantile(
    columns='value',
    quantile=[0.25, 0.5, 0.75],
    window=30
)

# Example 4: Calculate moving correlation between time series
pipe = pipe | moving_correlation(
    column_pairs=[('value', 'correlated'), ('value', 'value2')],
    window=60
)

# Example 5: Calculate moving z-scores
pipe = pipe | moving_zscore(
    columns=['value', 'value2'],
    window=30
)

# Example 6: Calculate moving cumulative sum
pipe = pipe | moving_cumulative(
    columns='event',
    operation='sum'
)

# Example 7: Calculate min and max in a moving window
pipe = pipe | moving_min_max(
    columns='value',
    window=30
)

# Example 8: Count events in a moving window
pipe = pipe | moving_count(
    columns='event',
    window=30
)

# Example 9: Calculate time-weighted averages
pipe = pipe | time_weighted_average(
    columns='value',
    window=30,
    decay_factor=0.9
)

# Example 10: Detect turning points
pipe = pipe | detect_turning_points(
    columns='value',
    window=15,
    threshold=5.0
)

# Example 11: Calculate ratio of two metrics
pipe = pipe | moving_ratio(
    numerator_column='value',
    denominator_column='value2',
    window=30
)

# Example 12: Custom aggregate function
def custom_skewness(x):
    """Calculate skewness of a series"""
    if len(x) < 3:
        return np.nan
    n = len(x)
    mean = np.mean(x)
    std = np.std(x, ddof=1)
    if std == 0:
        return 0
    return (np.sum((x - mean) ** 3) / n) / (std ** 3)

pipe = pipe | moving_aggregate(
    columns='value',
    function=custom_skewness,
    window=30,
    output_suffix='_skew'
)

# Example 13: Expanding window calculations
pipe = pipe | expanding_window(
    columns='value',
    operation='mean'
)

# Get the results
result_df = pipe.data

# Print information about the calculated metrics
print("\nCalculated moving metrics:")
for metric_name, metric_info in pipe.moving_metrics.items():
    print(f"- {metric_name}: {metric_info['type']} (columns: {metric_info.get('columns', 'N/A')})")

# Print sample of the results
print("\nSample of calculated metrics:")
print(result_df.iloc[60:61].T)

# Plot some of the results
def plot_results():
    # Select a section of the data for clearer visualization
    plot_data = result_df.iloc[100:200].copy()
    
    # Plot 1: Original value with moving averages
    plt.figure(figsize=(12, 8))
    plt.subplot(2, 2, 1)
    plt.plot(plot_data['timestamp'], plot_data['value'], label='Original Value')
    plt.plot(plot_data['timestamp'], plot_data['value_ma'], label='Simple MA')
    plt.plot(plot_data['timestamp'], plot_data['value_ma_weighted'], label='Weighted MA')
    plt.plot(plot_data['timestamp'], plot_data['value_ma_exponential'], label='Exp MA')
    plt.title('Moving Averages')
    plt.legend()
    plt.xticks(rotation=45)
    
    # Plot 2: Z-scores
    plt.subplot(2, 2, 2)
    plt.plot(plot_data['timestamp'], plot_data['value_zscore'], label='Z-Score')
    plt.axhline(y=2, color='r', linestyle='--', label='Threshold (+2)')
    plt.axhline(y=-2, color='r', linestyle='--', label='Threshold (-2)')
    plt.title('Moving Z-Scores')
    plt.legend()
    plt.xticks(rotation=45)
    
    # Plot 3: Min-Max and Turning Points
    plt.subplot(2, 2, 3)
    plt.plot(plot_data['timestamp'], plot_data['value'], label='Value')
    plt.plot(plot_data['timestamp'], plot_data['value_min'], 'g--', label='Min')
    plt.plot(plot_data['timestamp'], plot_data['value_max'], 'r--', label='Max')
    
    # Highlight peaks and troughs
    peaks = plot_data[plot_data['value_peak']]
    troughs = plot_data[plot_data['value_trough']]
    plt.scatter(peaks['timestamp'], peaks['value'], color='red', marker='^', s=100, label='Peaks')
    plt.scatter(troughs['timestamp'], troughs['value'], color='green', marker='v', s=100, label='Troughs')
    
    plt.title('Min-Max and Turning Points')
    plt.legend()
    plt.xticks(rotation=45)
    
    # Plot 4: Correlation
    plt.subplot(2, 2, 4)
    plt.plot(plot_data['timestamp'], plot_data['value_correlated_corr'], label='Correlation')
    plt.axhline(y=0, color='k', linestyle='-')
    plt.title('Moving Correlation')
    plt.legend()
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.show()

# Run the plotting function
plot_results()

# Example of combining with other analysis tools
# For instance, with the AnomalyPipe for anomaly detection
try:
    from chatbot.tools.mltools.anomalydetection import (
        AnomalyPipe, 
        detect_statistical_outliers
    )
    
    # Add z-score based outlier detection
    anomaly_pipe = AnomalyPipe.from_dataframe(result_df)
    anomaly_pipe = anomaly_pipe | detect_statistical_outliers(
        columns='value_zscore',
        method='zscore',
        threshold=2.5
    )
    
    # Get results and print summary
    anomaly_df = anomaly_pipe.data
    anomaly_count = anomaly_df['value_zscore_outlier_zscore'].sum()
    print(f"\nDetected {anomaly_count} anomalies based on z-scores")
    
except ImportError:
    print("\nAnomalyPipe not available for demonstration")

# Demonstrate how the pipe pattern makes the code more readable and maintainable
print("\nDemonstrating pipe pattern for complex transformations:")

complex_pipe = (
    MovingAggrPipe.from_dataframe(data)
    | moving_average(columns='value', window=7, method='simple',output_suffix='_ma')
    | moving_average(columns='value', window=30, method='simple',output_suffix='_ma_2')
    | moving_ratio(
        numerator_column='value_ma',
        denominator_column='value_ma_2',
        window=1,
        output_column='short_long_ratio'
    )
    | moving_zscore(columns='short_long_ratio', window=30)
    | detect_turning_points(columns='short_long_ratio_zscore', window=7)
)

# This is equivalent to the nested function calls:
# detect_turning_points(
#     moving_zscore(
#         moving_ratio(
#             moving_average(
#                 moving_average(
#                     MovingAggrPipe.from_dataframe(data),
#                     columns='value', window=7, method='simple'
#                 ),
#                 columns='value', window=30, method='simple'
#             ),
#             numerator_column='value_ma',
#             denominator_column='value_ma_2',
#             window=1,
#             output_column='short_long_ratio'
#         ),
#         columns='short_long_ratio', window=30
#     ),
#     columns='short_long_ratio_zscore', window=7
# )
result_df = complex_pipe.data
print("Complex transformation completed successfully using pipe pattern.")
print("The pipe pattern improves code readability by avoiding deeply nested function calls.")
print(result_df.to_json(orient='records'))
print("\nDone!")