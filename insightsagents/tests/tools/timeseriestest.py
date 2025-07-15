import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.tools.mltools.timeseriesanalysis import (
    TimeSeriesPipe,
    lead,
    lag,
    variance_analysis,
    distribution_analysis,
    cumulative_distribution,
    get_distribution_summary,
    custom_calculation,
    rolling_window
)

# Example of using the time series tool for various analyses

def main():
    """Run various time series analysis examples"""
    # Generate sample data
    df = generate_sample_data()
    print(f"Generated sample data with {len(df)} rows and {df.shape[1]} columns")
    
    # Example 1: Basic lead/lag analysis
    print("\n=== EXAMPLE 1: LEAD/LAG ANALYSIS ===")
    lag_results = basic_lag_analysis(df)
    print_lag_results(lag_results)
    
    # Example 2: Variance analysis
    print("\n=== EXAMPLE 2: VARIANCE ANALYSIS ===")
    variance_results = analyze_variance(df)
    print_variance_results(variance_results)
    
    # Example 3: Distribution analysis
    print("\n=== EXAMPLE 3: DISTRIBUTION ANALYSIS ===")
    dist_results = analyze_distribution(df)
    print_distribution_results(dist_results)
    
    # Example 4: Multi-stock analysis with grouping
    print("\n=== EXAMPLE 4: MULTI-STOCK ANALYSIS (PANEL DATA) ===")
    stocks_df = generate_stocks_data()
    panel_results = analyze_panel_data(stocks_df)
    print_panel_results(panel_results)
    
    return {
        "lag_results": lag_results,
        "variance_results": variance_results,
        "dist_results": dist_results,
        "panel_results": panel_results
    }


def generate_sample_data(n_days=100):
    """Generate sample time series data for testing"""
    # Generate dates
    dates = pd.date_range(start='2023-01-01', periods=n_days, freq='D')
    
    # Generate metrics with different patterns
    # 1. Revenue: upward trend with weekly seasonality
    revenue_base = 1000
    revenue_trend = np.linspace(0, 300, n_days)  # Upward trend
    revenue_seasonal = 100 * np.sin(np.arange(n_days) * (2 * np.pi / 7))  # Weekly pattern
    revenue_noise = np.random.normal(0, 50, n_days)  # Random noise
    revenue = revenue_base + revenue_trend + revenue_seasonal + revenue_noise
    
    # 2. Users: step function with some noise
    users_base = 500
    users_steps = np.zeros(n_days)
    step_points = [20, 50, 80]
    step_sizes = [100, 150, 200]
    
    for point, size in zip(step_points, step_sizes):
        users_steps[point:] = size
    
    users_noise = np.random.normal(0, 20, n_days)
    users = users_base + users_steps + users_noise
    
    # 3. Conversion rate: random walk with boundaries
    conversion_base = 0.05  # 5% base conversion rate
    conversion_walk = np.cumsum(np.random.normal(0, 0.002, n_days))
    # Keep conversion rate between 2% and 10%
    conversion_rate = np.clip(conversion_base + conversion_walk, 0.02, 0.1)
    
    # Create dataframe
    df = pd.DataFrame({
        'date': dates,
        'revenue': revenue,
        'users': users,
        'conversion_rate': conversion_rate
    })
    
    return df


def generate_stocks_data(n_days=100):
    """Generate sample multi-stock data for panel data analysis"""
    # Generate dates
    dates = pd.date_range(start='2023-01-01', periods=n_days, freq='D')
    
    # Define stocks with different characteristics
    stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
    
    # Generate data for each stock
    stock_data = []
    
    for stock in stocks:
        # Base price and volatility parameters vary by stock
        if stock == 'AAPL':
            base_price = 150
            volatility = 2.0
            trend = 0.1
        elif stock == 'MSFT':
            base_price = 250
            volatility = 2.5
            trend = 0.15
        elif stock == 'GOOGL':
            base_price = 120
            volatility = 1.8
            trend = 0.05
        else:  # AMZN
            base_price = 100
            volatility = 3.0
            trend = 0.0  # No trend
        
        # Generate price series with random walk and trend
        price_walk = np.cumsum(np.random.normal(trend, volatility, n_days))
        prices = base_price + price_walk
        
        # Generate volume with some correlation to price changes
        base_volume = 1000000
        if stock == 'AAPL':
            volume_multiplier = 2.0
        elif stock == 'MSFT':
            volume_multiplier = 1.5
        elif stock == 'GOOGL':
            volume_multiplier = 1.2
        else:  # AMZN
            volume_multiplier = 1.8
        
        # Volume increases with absolute price changes
        price_changes = np.diff(prices, prepend=prices[0])
        volume = base_volume + volume_multiplier * 100000 * np.abs(price_changes) + np.random.normal(0, 100000, n_days)
        volume = np.maximum(volume, 100000)  # Ensure minimum volume
        
        # Add to data list
        for i in range(n_days):
            stock_data.append({
                'date': dates[i],
                'stock': stock,
                'price': prices[i],
                'volume': volume[i]
            })
    
    # Create dataframe
    df = pd.DataFrame(stock_data)
    
    return df


def basic_lag_analysis(df):
    """Perform basic lead/lag analysis on time series data"""
    # Use the pipe pattern for a sequence of operations
    result = (TimeSeriesPipe.from_dataframe(df)
             # Create lagged values (previous day)
             | lag(columns=['revenue', 'users', 'conversion_rate'], periods=1, time_column='date')
             # Create led values (next day)
             | lead(columns=['revenue', 'users'], periods=1, time_column='date')
             # Create a custom calculated field
             | custom_calculation(lambda df: df.assign(
                 revenue_day_change=df['revenue'] - df['revenue_lag'],
                 revenue_day_pct_change=(df['revenue'] - df['revenue_lag']) / df['revenue_lag'] * 100
               ))
            ).data
    
    return result


def analyze_variance(df):
    """Analyze variance in time series data"""
    # Use the pipe pattern for variance analysis
    result = (TimeSeriesPipe.from_dataframe(df)
             # Calculate 7-day rolling variance and standard deviation
             | variance_analysis(
                 columns=['revenue', 'conversion_rate'],
                 method='rolling',
                 window=7,
                 time_column='date'
               )
             # Calculate expanding variance (growing window)
             | variance_analysis(
                 columns=['users'],
                 method='expanding',
                 time_column='date',
                 suffix='_expanding'
               )
             # Add custom volatility metric
             | custom_calculation(lambda df: df.assign(
                 revenue_volatility=df['revenue_std'] / df['revenue'].rolling(window=7).mean()
               ))
            ).data
    
    return result


def analyze_distribution(df):
    """Analyze distributions in time series data"""
    # Use the pipe pattern for distribution analysis
    pipe = (TimeSeriesPipe.from_dataframe(df)
           # Calculate distribution statistics
           | distribution_analysis(
               columns=['revenue', 'users', 'conversion_rate'],
               bins=20
             )
           # Calculate cumulative distribution
           | cumulative_distribution(
               columns=['revenue', 'users', 'conversion_rate'],
               time_column='date'
             )
          )
    
    # Get distribution summary
    summary = get_distribution_summary()(pipe)
    
    # Return both the data and distribution summary
    return {
        'data': pipe.data,
        'summary': summary,
        'distributions': pipe.distribution_results
    }


def analyze_panel_data(stocks_df):
    """Analyze panel data (multiple stocks)"""
    # Use the pipe pattern for panel data analysis
    result = (TimeSeriesPipe.from_dataframe(stocks_df)
             # Create lagged values by stock
             | lag(
                 columns=['price', 'volume'],
                 periods=1,
                 time_column='date',
                 group_columns=['stock']
               )
             # Calculate daily returns
             | custom_calculation(lambda df: df.assign(
                 daily_return=(df['price'] - df['price_lag']) / df['price_lag'] * 100
               ))
             # Calculate 5-day rolling variance by stock
             | variance_analysis(
                 columns=['daily_return'],
                 method='rolling',
                 window=5,
                 time_column='date',
                 group_columns=['stock']
               )
             # Calculate cumulative distribution of returns by stock
             | cumulative_distribution(
                 columns=['daily_return'],
                 time_column='date',
                 group_columns=['stock']
               )
            ).data
    
    return result

def test_rolling_window():
    """Test rolling window calculations"""
    # Create test data
    dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
    df = pd.DataFrame({
        'date': dates,
        'revenue': [100, 120, 115, 130, 140, 150, 145, 160, 170, 180],
        'users': [1000, 1100, 1050, 1200, 1300, 1400, 1350, 1500, 1600, 1700]
    })
    
    # Test basic rolling mean
    result = (TimeSeriesPipe.from_dataframe(df)
             | rolling_window(
                 columns=['revenue', 'users'],
                 window=3,
                 aggregation='mean',
                 time_column='date'
               )
            ).data
    print(result)
    # Verify rolling mean calculations
    assert 'revenue_rolling_mean' in result.columns
    assert 'users_rolling_mean' in result.columns
    assert result['revenue_rolling_mean'].iloc[2] == (100 + 120 + 115) / 3
    assert result['users_rolling_mean'].iloc[2] == (1000 + 1100 + 1050) / 3
    
    # Test rolling sum with custom suffix
    result = (TimeSeriesPipe.from_dataframe(df)
             | rolling_window(
                 columns=['revenue'],
                 window=2,
                 aggregation='sum',
                 time_column='date',
                 suffix='_sum'
               )
            ).data
    print(result)
    assert 'revenue_sum' in result.columns
    assert result['revenue_sum'].iloc[1] == 100 + 120
    
    # Test rolling std with grouping
    df['category'] = ['A', 'A', 'B', 'B', 'A', 'A', 'B', 'B', 'A', 'A']
    result = (TimeSeriesPipe.from_dataframe(df)
             | rolling_window(
                 columns=['revenue'],
                 window=2,
                 aggregation='std',
                 time_column='date',
                 group_columns=['category']
               )
            ).data
    print(result)
    assert 'revenue_rolling_std' in result.columns
    assert result['revenue_rolling_std'].iloc[1] == np.std([100, 120])
    
    # Test different time units
    result = (TimeSeriesPipe.from_dataframe(df)
             | rolling_window(
                 columns=['revenue'],
                 window=1,
                 unit='weekly',
                 aggregation='mean',
                 time_column='date'
               )
            ).data
    print(result)
    assert result['revenue_rolling_mean'].iloc[6] == np.mean(df['revenue'].iloc[0:7])
    
    # Test invalid parameters
    

def print_lag_results(df):
    """Print lead/lag analysis results"""
    print("Sample of lead/lag analysis results:")
    print(df[['date', 'revenue', 'revenue_lag', 'revenue_lead', 'revenue_day_change', 'revenue_day_pct_change']].head(5))
    
    # Calculate and print some summary statistics
    lag_correlations = {}
    for col in ['revenue', 'users', 'conversion_rate']:
        if f'{col}_lag' in df.columns:
            lag_correlations[col] = df[col].corr(df[f'{col}_lag'])
    
    print("\nAutocorrelation with 1-day lag:")
    for col, corr in lag_correlations.items():
        print(f"  {col}: {corr:.4f}")
    
    # Find days with largest changes
    print("\nDays with largest revenue changes:")
    largest_changes = df.sort_values('revenue_day_change', ascending=False).head(3)
    for _, row in largest_changes.iterrows():
        date = row['date'].strftime('%Y-%m-%d')
        change = row['revenue_day_change']
        pct_change = row['revenue_day_pct_change']
        print(f"  {date}: {change:.2f} ({pct_change:.2f}%)")


def print_variance_results(df):
    """Print variance analysis results"""
    print("Sample of variance analysis results:")
    print(df[['date', 'revenue', 'revenue_var', 'revenue_std', 'revenue_volatility']].head(5))
    
    # Find highest volatility periods
    highest_volatility = df.sort_values('revenue_volatility', ascending=False).head(3)
    print("\nPeriods with highest revenue volatility:")
    for _, row in highest_volatility.iterrows():
        date = row['date'].strftime('%Y-%m-%d')
        volatility = row['revenue_volatility']
        revenue = row['revenue']
        std = row['revenue_std']
        print(f"  {date}: Volatility {volatility:.4f}, Revenue {revenue:.2f}, Std Dev {std:.2f}")
    
    # Compare variance metrics
    print("\nAverage metrics over the entire period:")
    print(f"  Revenue standard deviation: {df['revenue_std'].mean():.2f}")
    print(f"  Users expanding standard deviation: {df['users_expanding_std'].mean():.2f}")
    print(f"  Revenue volatility: {df['revenue_volatility'].mean():.4f}")


def print_distribution_results(results):
    """Print distribution analysis results"""
    data = results['data']
    summary = results['summary']
    distributions = results['distributions']
    
    print("Sample of distribution analysis results:")
    print(data[['date', 'revenue', 'revenue_cdf', 'users', 'users_cdf']].head(5))
    
    # Print summary statistics
    print("\nDistribution summary statistics:")
    for col, stats in summary.items():
        print(f"\n{col} statistics:")
        print(f"  Mean: {stats['mean'].iloc[0]:.2f}")
        print(f"  Std dev: {stats['std'].iloc[0]:.2f}")
        print(f"  Min: {stats['min'].iloc[0]:.2f}")
        print(f"  25%: {stats['25%'].iloc[0]:.2f}")
        print(f"  Median: {stats['median'].iloc[0]:.2f}")
        print(f"  75%: {stats['75%'].iloc[0]:.2f}")
        print(f"  Max: {stats['max'].iloc[0]:.2f}")
    
    # Print histogram information
    print("\nHistogram information:")
    for col, dist in distributions.items():
        hist = dist['histogram']
        bins = dist['bin_edges']
        print(f"\n{col} histogram has {len(hist)} bins from {bins[0]:.2f} to {bins[-1]:.2f}")
        
        # Find the most frequent bin
        max_bin_idx = np.argmax(hist)
        max_bin_start = bins[max_bin_idx]
        max_bin_end = bins[max_bin_idx + 1]
        max_bin_count = hist[max_bin_idx]
        
        print(f"  Most frequent range: {max_bin_start:.2f} to {max_bin_end:.2f} (count: {max_bin_count})")


def print_panel_results(df):
    """Print panel data analysis results"""
    print("Sample of panel data analysis (grouped by stock):")
    # Show one sample row for each stock
    sample_rows = []
    for stock in df['stock'].unique():
        sample_rows.append(df[df['stock'] == stock].iloc[5])
    
    sample_df = pd.DataFrame(sample_rows)
    print(sample_df[['date', 'stock', 'price', 'price_lag', 'daily_return', 'daily_return_var']].head())
    
    # Calculate and print summary by stock
    print("\nSummary by stock:")
    stock_summary = df.groupby('stock').agg({
        'price': 'mean',
        'daily_return': ['mean', 'std'],
        'daily_return_var': 'mean',
        'volume': 'mean'
    })
    
    print(stock_summary)
    
    # Find days with highest returns for each stock
    print("\nDays with highest returns by stock:")
    for stock in df['stock'].unique():
        stock_data = df[df['stock'] == stock]
        best_day = stock_data.loc[stock_data['daily_return'].idxmax()]
        date = best_day['date'].strftime('%Y-%m-%d')
        return_val = best_day['daily_return']
        price = best_day['price']
        
        print(f"  {stock}: {date}, Return: {return_val:.2f}%, Price: {price:.2f}")
    
    # Compare volatility across stocks
    print("\nVolatility comparison:")
    volatility_by_stock = df.groupby('stock')['daily_return_std'].mean()
    for stock, vol in volatility_by_stock.items():
        print(f"  {stock}: {vol:.4f}")
    
    test_rolling_window()


if __name__ == "__main__":
    results = main()