import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.tools.mltools.trendanalysistools import (
    TrendPipe,
    aggregate_by_time,
    calculate_growth_rates,
    calculate_moving_average,
    calculate_statistical_trend,
    decompose_trend,
    forecast_metric,
    get_top_metrics,
    compare_periods
)

# Example of using the composable trend analysis tool

def main():
    # Step 1: Load data
    df = load_sample_data()
    print(f"Loaded {len(df)} data points for analysis")
    
    # Step 2: Run various trend analyses
    
    # Example 1: Analyze monthly growth rates for key metrics
    print("\n=== MONTHLY GROWTH RATE ANALYSIS ===")
    growth_results = analyze_growth_rates(df)
    print_growth_results(growth_results)
    
    # Example 2: Identify statistical trends in metrics
    print("\n=== STATISTICAL TREND ANALYSIS ===")
    trend_results = analyze_statistical_trends(df)
    print_trend_results(trend_results)
    
    # Example 3: Compare current period with previous period
    print("\n=== PERIOD-OVER-PERIOD COMPARISON ===")
    comparison_results = compare_time_periods(df)
    print_comparison_results(comparison_results)
    
    # Example 4: Forecast future values
    print("\n=== FORECAST ANALYSIS ===")
    forecast_results = forecast_metrics(df)
    print_forecast_results(forecast_results)
    
    # Example 5: Get top metrics by different criteria
    print("\n=== TOP METRICS ANALYSIS ===")
    top_results = get_top_performing_metrics(df)
    print_top_metrics(top_results)
    
    return {
        'growth': growth_results,
        'trend': trend_results,
        'comparison': comparison_results,
        'forecast': forecast_results,
        'top': top_results
    }


def load_sample_data(n_days=365):
    """Generate synthetic business metrics data"""
    np.random.seed(42)
    
    # Generate dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create dataframe
    df = pd.DataFrame({'date': dates})
    
    # Generate synthetic metrics
    
    # Revenue - has a positive trend with weekly seasonality and some noise
    base_revenue = 10000
    trend_factor = 0.001  # 0.1% daily growth
    weekly_seasonality = np.sin(np.arange(len(dates)) * (2 * np.pi / 7)) * 0.2  # 20% weekly fluctuation
    noise = np.random.normal(0, 0.05, len(dates))  # 5% random noise
    
    df['revenue'] = base_revenue * (1 + np.arange(len(dates)) * trend_factor) * (1 + weekly_seasonality) * (1 + noise)
    
    # Users - has step changes (growth spurts) and plateaus
    base_users = 1000
    step_changes = np.zeros(len(dates))
    change_points = [90, 180, 270]  # Days with step changes
    step_sizes = [0.2, 0.15, 0.25]  # Size of step changes
    
    current_level = 1.0
    for day, step in zip(change_points, step_sizes):
        if day < len(step_changes):
            step_changes[day:] = step
            current_level *= (1 + step)
    
    gradual_growth = np.arange(len(dates)) * 0.0005  # Gradual daily growth
    noise = np.random.normal(0, 0.02, len(dates))  # 2% random noise
    
    df['users'] = base_users * (1 + np.cumsum(step_changes) + gradual_growth) * (1 + noise)
    
    # Conversion rate - has a negative trend with monthly seasonality
    base_conversion = 0.05  # 5% base conversion rate
    trend_factor = -0.0001  # -0.01% daily decline
    monthly_seasonality = np.sin(np.arange(len(dates)) * (2 * np.pi / 30)) * 0.1  # 10% monthly fluctuation
    noise = np.random.normal(0, 0.03, len(dates))  # 3% random noise
    
    df['conversion_rate'] = base_conversion * (1 + np.arange(len(dates)) * trend_factor) * (1 + monthly_seasonality) * (1 + noise)
    
    # Ensure conversion rate is between 0 and 1
    df['conversion_rate'] = df['conversion_rate'].clip(0.01, 0.2)
    
    # Average order value - has a cyclical pattern
    base_aov = 75
    cyclical_pattern = np.sin(np.arange(len(dates)) * (2 * np.pi / 90)) * 0.15  # 15% quarterly cycle
    noise = np.random.normal(0, 0.04, len(dates))  # 4% random noise
    
    df['aov'] = base_aov * (1 + cyclical_pattern) * (1 + noise)
    
    # Churn rate - stable with occasional spikes
    base_churn = 0.03  # 3% base churn rate
    spikes = np.zeros(len(dates))
    spike_days = [60, 150, 240, 330]  # Days with churn spikes
    for day in spike_days:
        if day < len(spikes):
            spikes[day-2:day+3] = [0.2, 0.5, 1.0, 0.5, 0.2]  # Shape of the spike
    
    noise = np.random.normal(0, 0.1, len(dates))  # 10% random noise
    
    df['churn_rate'] = base_churn * (1 + spikes) * (1 + noise)
    
    # Ensure churn rate is between 0 and 1
    df['churn_rate'] = df['churn_rate'].clip(0.01, 0.15)
    
    return df


def analyze_growth_rates(df):
    """Analyze monthly growth rates for key metrics"""
    result = (TrendPipe.from_dataframe(df)
              # Aggregate to monthly level
              | aggregate_by_time(
                  date_column='date',
                  metric_columns=['revenue', 'users', 'conversion_rate', 'aov', 'churn_rate'],
                  time_period='M',
                  aggregation={
                      'revenue': 'sum',
                      'users': 'mean',
                      'conversion_rate': 'mean',
                      'aov': 'mean',
                      'churn_rate': 'mean'
                  }
              )
              # Calculate month-over-month growth rates
              | calculate_growth_rates(
                  window=1,
                  method='percentage'
              )
              # Calculate moving average to smooth out volatility
              | calculate_moving_average(
                  window=3,
                  method='simple'
              )
    )
    
    return result.trend_results


def analyze_statistical_trends(df):
    """Identify statistical trends in metrics"""
    result = (TrendPipe.from_dataframe(df)
              # Aggregate to weekly level
              | aggregate_by_time(
                  date_column='date',
                  metric_columns=['revenue', 'users', 'conversion_rate', 'aov', 'churn_rate'],
                  time_period='W',
                  aggregation={
                      'revenue': 'sum',
                      'users': 'mean',
                      'conversion_rate': 'mean',
                      'aov': 'mean',
                      'churn_rate': 'mean'
                  }
              )
              # Test for statistical trend in revenue
              | calculate_statistical_trend(
                  metric_column='revenue',
                  test_method='mann_kendall'
              )
              # Test for statistical trend in conversion rate
              | calculate_statistical_trend(
                  metric_column='conversion_rate',
                  test_method='mann_kendall'
              )
              # Decompose trend and seasonality for users
              | decompose_trend(
                  metric_column='users',
                  model='additive',
                  period=52,  # weekly data, so 52 weeks for annual seasonality
                  extrapolate_trend=12
              )
    )
    
    return {
        'trend_results': result.trend_results,
        'trend_decompositions': result.trend_decompositions
    }


def compare_time_periods(df):
    """Compare current period with previous period"""
    result = (TrendPipe.from_dataframe(df)
              # Aggregate to monthly level
              | aggregate_by_time(
                  date_column='date',
                  metric_columns=['revenue', 'users', 'conversion_rate', 'aov', 'churn_rate'],
                  time_period='M',
                  aggregation={
                      'revenue': 'sum',
                      'users': 'mean',
                      'conversion_rate': 'mean',
                      'aov': 'mean',
                      'churn_rate': 'mean'
                  }
              )
              # Compare with same month last year
              | compare_periods(
                  metric_column='revenue',
                  comparison_type='year_over_year'
              )
              # Compare with previous month
              | compare_periods(
                  metric_column='users',
                  comparison_type='month_over_month'
              )
    )
    
    return result.trend_results


def forecast_metrics(df):
    """Forecast future values of metrics"""
    result = (TrendPipe.from_dataframe(df)
              # Aggregate to monthly level
              | aggregate_by_time(
                  date_column='date',
                  metric_columns=['revenue', 'users'],
                  time_period='M',
                  aggregation={
                      'revenue': 'sum',
                      'users': 'mean'
                  }
              )
              # Forecast revenue using Holt-Winters
              | forecast_metric(
                  metric_column='revenue',
                  fperiods=6,
                  fmethod='holt_winters',
                  seasonal_periods=12
              )
              # Forecast users using exponential trend
              | forecast_metric(
                  metric_column='users',
                  fperiods=6,
                  fmethod='exponential'
              )
    )
    
    return result.forecasts


def get_top_performing_metrics(df):
    """Get top metrics by different criteria"""
    # First run all the analyses to get results for comparing
    pipe = (TrendPipe.from_dataframe(df)
            # Aggregate to monthly level
            | aggregate_by_time(
                date_column='date',
                metric_columns=['revenue', 'users', 'conversion_rate', 'aov', 'churn_rate'],
                time_period='M',
                aggregation='mean'
            )
            # Calculate growth rates
            | calculate_growth_rates(window=1)
            # Calculate statistical trends
            | calculate_statistical_trend(metric_column='revenue')
            | calculate_statistical_trend(metric_column='users')
            | calculate_statistical_trend(metric_column='conversion_rate')
            | calculate_statistical_trend(metric_column='aov')
            | calculate_statistical_trend(metric_column='churn_rate')
            # Compare current with previous period
            | compare_periods(metric_column='revenue', comparison_type='month_over_month')
            | compare_periods(metric_column='users', comparison_type='month_over_month')
            | compare_periods(metric_column='conversion_rate', comparison_type='month_over_month')
            | compare_periods(metric_column='aov', comparison_type='month_over_month')
            | compare_periods(metric_column='churn_rate', comparison_type='month_over_month')
    )
    
    # Now get top metrics by different criteria
    fastest_growing = get_top_metrics(n=3, metric_type='growth', ascending=False)(pipe)
    strongest_trends = get_top_metrics(n=3, metric_type='trend', ascending=False)(pipe)
    most_volatile = get_top_metrics(n=3, metric_type='volatility', ascending=False)(pipe)
    largest_changes = get_top_metrics(n=3, metric_type='absolute_change', ascending=False)(pipe)
    
    return {
        'fastest_growing': fastest_growing,
        'strongest_trends': strongest_trends,
        'most_volatile': most_volatile,
        'largest_changes': largest_changes
    }


def print_growth_results(growth_results):
    """Print growth rate analysis results"""
    for name, result in growth_results.items():
        if result['type'] == 'growth':
            df = result['data']
            print(f"\nMonthly growth rates:")
            latest = df.iloc[-1]
            growth_cols = [col for col in df.columns if '_growth' in col]
            
            for col in growth_cols:
                metric = col.replace('_growth', '')
                latest_growth = latest[col]
                print(f"  {metric}: {latest_growth*100:.2f}% month-over-month")


def print_trend_results(results):
    """Print trend analysis results"""
    # Statistical trends
    trend_results = results['trend_results']
    for name, result in trend_results.items():
        if result['type'] == 'statistical_trend':
            metric = result['metric']
            trend = result['trend']
            significant = result['significant']
            p_value = result['p_value']
            
            print(f"\n{metric}:")
            if significant:
                print(f"  Significant {trend} trend (p-value: {p_value})")
                if 'slope' in result:
                    print(f"  Slope: {result['slope']} per period")
            else:
                print(f"  No significant trend detected (p-value: {p_value})")
    
    # Trend decompositions
    decompositions = results['trend_decompositions']
    for name, decomp in decompositions.items():
        metric = decomp['metric']
        decomp_type = decomp['type']
        
        print(f"\n{metric} decomposition ({decomp_type}):")
        if decomp_type == 'seasonal':
            print(f"  Periodicity: {decomp['period']} periods")
        elif decomp_type == 'linear':
            print(f"  Trend slope: {decomp['slope']:.4f} per period")


def print_comparison_results(comparison_results):
    """Print period comparison results"""
    for name, result in comparison_results.items():
        if result['type'] == 'period_comparison':
            metric = result['metric']
            comparison_type = result['comparison_type']
            df = result['data']
            
            # Get latest comparison
            latest = df.iloc[-1]
            current = latest['current']
            previous = latest['previous']
            abs_diff = latest['abs_diff']
            rel_diff = latest['rel_diff']
            
            print(f"\n{metric} ({comparison_type}):")
            print(f"  Current: {current:.2f}")
            print(f"  Previous: {previous:.2f}")
            print(f"  Absolute change: {abs_diff:.2f}")
            print(f"  Relative change: {rel_diff:.2f}%")


def print_forecast_results(forecast_results):
    """Print forecast results"""
    for name, forecast in forecast_results.items():
        if isinstance(forecast, dict) and forecast['type'] == 'forecast':
            metric = forecast['metric']
            method = forecast['method']
            df = forecast['data']
            
            print(f"\n{metric} forecast ({method}):")
            print(f"  Forecast periods: {len(df)}")
            
            # Print forecast for first and last period
            first_period = df.index[0].strftime('%Y-%m')
            last_period = df.index[-1].strftime('%Y-%m')
            first_forecast = df['forecast'].iloc[0]
            last_forecast = df['forecast'].iloc[-1]
            
            print(f"  {first_period}: {first_forecast:.2f}")
            print(f"  {last_period}: {last_forecast:.2f}")
            
            # Calculate growth from first to last period
            growth = (last_forecast / first_forecast - 1) * 100
            print(f"  Forecast growth: {growth:.2f}%")


def print_top_metrics(top_results):
    """Print top metrics analysis results"""
    # Fastest growing
    print("\nFastest growing metrics:")
    if not top_results['fastest_growing'].empty:
        for _, row in top_results['fastest_growing'].iterrows():
            print(f"  {row['metric']}: {row['value']*100:.2f}% growth")
    
    # Strongest trends
    print("\nStrongest trend metrics:")
    if not top_results['strongest_trends'].empty:
        for _, row in top_results['strongest_trends'].iterrows():
            direction = "increasing" if row['value'] > 0 else "decreasing"
            print(f"  {row['metric']}: {direction} trend (slope: {row['value']:.4f})")
    
    # Most volatile
    print("\nMost volatile metrics:")
    if not top_results['most_volatile'].empty:
        for _, row in top_results['most_volatile'].iterrows():
            print(f"  {row['metric']}: {row['value']:.2f} coefficient of variation")
    
    # Largest changes
    print("\nLargest absolute changes:")
    if not top_results['largest_changes'].empty:
        for _, row in top_results['largest_changes'].iterrows():
            print(f"  {row['metric']}: {row['value']:.2f} absolute change ({row['rel_diff']:.2f}% relative)")


if __name__ == "__main__":
    results = main()