"""
Example Usage of Group Aggregation Functions with Moving Aggregation Pipeline

This script demonstrates how to use the standalone group aggregation functions
with the moving_apply_by_group function in the MovingAggrPipe.
"""

import pandas as pd
import numpy as np
from .movingaverages import MovingAggrPipe, moving_apply_by_group
from .group_aggregation_functions import (
    mean, sum_values, count_values, max_value, min_value,
    std_dev, variance, median, quantile, range_values,
    coefficient_of_variation, skewness, kurtosis,
    unique_count, mode, weighted_average, geometric_mean,
    harmonic_mean, interquartile_range, mad
)


def create_sample_data():
    """
    Create sample time series data with multiple groups for demonstration.
    
    Returns:
    --------
    pd.DataFrame
        Sample DataFrame with time series data grouped by category and region.
    """
    np.random.seed(42)
    
    # Create date range
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    
    # Create sample data
    data = []
    categories = ['Electronics', 'Clothing', 'Books', 'Food']
    regions = ['North', 'South', 'East', 'West']
    
    for date in dates:
        for category in categories:
            for region in regions:
                # Generate some realistic data with trends and seasonality
                base_value = 100 + np.sin(2 * np.pi * date.dayofyear / 365) * 20
                category_factor = {'Electronics': 1.5, 'Clothing': 1.0, 'Books': 0.8, 'Food': 1.2}[category]
                region_factor = {'North': 1.1, 'South': 0.9, 'East': 1.0, 'West': 1.05}[region]
                
                # Add some noise
                noise = np.random.normal(0, 10)
                
                sales = max(0, base_value * category_factor * region_factor + noise)
                revenue = sales * np.random.uniform(10, 50)
                profit = revenue * np.random.uniform(0.1, 0.3)
                
                data.append({
                    'date': date,
                    'category': category,
                    'region': region,
                    'sales': sales,
                    'revenue': revenue,
                    'profit': profit,
                    'volume': np.random.uniform(1, 10)
                })
    
    df = pd.DataFrame(data)
    return df.sort_values(['date', 'category', 'region']).reset_index(drop=True)


def demonstrate_basic_functions():
    """
    Demonstrate basic group aggregation functions.
    """
    print("=== Basic Group Aggregation Functions Demo ===\n")
    
    # Create sample data
    df = create_sample_data()
    print(f"Sample data shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Categories: {df['category'].unique()}")
    print(f"Regions: {df['region'].unique()}")
    print()
    
    # Create pipeline with basic functions
    print("1. Calculating moving mean of sales by category...")
    result1 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'category', mean, window=7))
    
    # Show results
    moving_cols = result1.get_moving_columns()
    print(f"   Created columns: {moving_cols}")
    print(f"   Sample results:")
    sample_data = result1.data[['date', 'category', 'region', 'sales'] + moving_cols].head(20)
    print(sample_data.to_string(index=False))
    print()
    
    print("2. Calculating moving sum of revenue by region...")
    result2 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('revenue', 'region', sum_values, window=14))
    
    moving_cols2 = result2.get_moving_columns()
    print(f"   Created columns: {moving_cols2}")
    print()
    
    print("3. Calculating moving count of transactions by category...")
    result3 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'category', count_values, window=7))
    
    moving_cols3 = result3.get_moving_columns()
    print(f"   Created columns: {moving_cols3}")
    print()


def demonstrate_statistical_functions():
    """
    Demonstrate statistical group aggregation functions.
    """
    print("=== Statistical Group Aggregation Functions Demo ===\n")
    
    # Create sample data
    df = create_sample_data()
    
    print("1. Calculating moving standard deviation of profit by category...")
    result1 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('profit', 'category', std_dev, window=14))
    
    moving_cols1 = result1.get_moving_columns()
    print(f"   Created columns: {moving_cols1}")
    print()
    
    print("2. Calculating moving variance of revenue by region...")
    result2 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('revenue', 'region', variance, window=21))
    
    moving_cols2 = result2.get_moving_columns()
    print(f"   Created columns: {moving_cols2}")
    print()
    
    print("3. Calculating moving median of sales by category...")
    result3 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'category', median, window=30))
    
    moving_cols3 = result3.get_moving_columns()
    print(f"   Created columns: {moving_cols3}")
    print()
    
    print("4. Calculating moving 75th percentile of profit by region...")
    result4 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('profit', 'region', 
                                     lambda g, c: quantile(g, c, 0.75), window=21))
    
    moving_cols4 = result4.get_moving_columns()
    print(f"   Created columns: {moving_cols4}")
    print()


def demonstrate_advanced_functions():
    """
    Demonstrate advanced group aggregation functions.
    """
    print("=== Advanced Group Aggregation Functions Demo ===\n")
    
    # Create sample data
    df = create_sample_data()
    
    print("1. Calculating moving coefficient of variation of sales by category...")
    result1 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'category', coefficient_of_variation, window=14))
    
    moving_cols1 = result1.get_moving_columns()
    print(f"   Created columns: {moving_cols1}")
    print()
    
    print("2. Calculating moving skewness of revenue by region...")
    result2 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('revenue', 'region', skewness, window=30))
    
    moving_cols2 = result2.get_moving_columns()
    print(f"   Created columns: {moving_cols2}")
    print()
    
    print("3. Calculating moving weighted average of price by category (using volume as weights)...")
    def weighted_avg_with_volume(grouped, column):
        return weighted_average(grouped, column, 'volume')
    
    result3 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('revenue', 'category', weighted_avg_with_volume, window=21))
    
    moving_cols3 = result3.get_moving_columns()
    print(f"   Created columns: {moving_cols3}")
    print()
    
    print("4. Calculating moving geometric mean of profit growth by region...")
    # Create profit growth column
    df['profit_growth'] = df.groupby(['category', 'region'])['profit'].pct_change() + 1
    df['profit_growth'] = df['profit_growth'].fillna(1)
    
    result4 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('profit_growth', 'region', geometric_mean, window=14))
    
    moving_cols4 = result4.get_moving_columns()
    print(f"   Created columns: {moving_cols4}")
    print()


def demonstrate_chained_operations():
    """
    Demonstrate chaining multiple group aggregation operations.
    """
    print("=== Chained Group Aggregation Operations Demo ===\n")
    
    # Create sample data
    df = create_sample_data()
    
    print("1. Chaining multiple operations on the same pipeline...")
    result = (MovingAggrPipe.from_dataframe(df)
              | moving_apply_by_group('sales', 'category', mean, window=7)
              | moving_apply_by_group('revenue', 'region', sum_values, window=14)
              | moving_apply_by_group('profit', 'category', std_dev, window=21)
              | moving_apply_by_group('sales', 'region', max_value, window=30))
    
    # Show all created columns
    moving_cols = result.get_moving_columns()
    print(f"   Total moving columns created: {len(moving_cols)}")
    print(f"   Columns: {moving_cols}")
    print()
    
    # Show summary
    summary = result.get_summary()
    print("2. Pipeline summary:")
    print(f"   Total metrics: {summary['total_metrics']}")
    print(f"   Total moving columns: {summary['total_moving_columns']}")
    print(f"   Available metrics: {summary['available_metrics']}")
    print()
    
    # Show sample results
    print("3. Sample results (first 10 rows):")
    sample_cols = ['date', 'category', 'region', 'sales', 'revenue', 'profit'] + moving_cols[:5]
    sample_data = result.data[sample_cols].head(10)
    print(sample_data.to_string(index=False))


def demonstrate_custom_functions():
    """
    Demonstrate how to create custom group aggregation functions.
    """
    print("=== Custom Group Aggregation Functions Demo ===\n")
    
    # Create sample data
    df = create_sample_data()
    
    print("1. Custom function: Moving profit margin by category...")
    def profit_margin(grouped, column):
        """Calculate profit margin (profit/revenue) across all groups."""
        try:
            total_profit = 0
            total_revenue = 0
            
            for name, group in grouped:
                if 'profit' in group.columns and 'revenue' in group.columns:
                    profit_sum = group['profit'].sum()
                    revenue_sum = group['revenue'].sum()
                    total_profit += profit_sum
                    total_revenue += revenue_sum
            
            if total_revenue == 0:
                return np.nan
            
            return total_profit / total_revenue
        except Exception as e:
            return np.nan
    
    result1 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('profit', 'category', profit_margin, window=14))
    
    moving_cols1 = result1.get_moving_columns()
    print(f"   Created columns: {moving_cols1}")
    print()
    
    print("2. Custom function: Moving sales efficiency by region...")
    def sales_efficiency(grouped, column):
        """Calculate sales efficiency (sales/volume) across all groups."""
        try:
            total_sales = 0
            total_volume = 0
            
            for name, group in grouped:
                if 'sales' in group.columns and 'volume' in group.columns:
                    sales_sum = group['sales'].sum()
                    volume_sum = group['volume'].sum()
                    total_sales += sales_sum
                    total_volume += volume_sum
            
            if total_volume == 0:
                return np.nan
            
            return total_sales / total_volume
        except Exception as e:
            return np.nan
    
    result2 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'region', sales_efficiency, window=21))
    
    moving_cols2 = result2.get_moving_columns()
    print(f"   Created columns: {moving_cols2}")
    print()


def demonstrate_operations_functions():
    """
    Demonstrate the new operations tool functions adapted for group aggregation.
    """
    print("=== Operations Tool Functions Demo ===\n")
    
    # Create sample data
    df = create_sample_data()
    
    print("1. Moving percent change by category...")
    result1 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'category', percent_change, window=14))
    
    moving_cols1 = result1.get_moving_columns()
    print(f"   Created columns: {moving_cols1}")
    print()
    
    print("2. Moving absolute change by region...")
    result2 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('revenue', 'region', absolute_change, window=21))
    
    moving_cols2 = result2.get_moving_columns()
    print(f"   Created columns: {moving_cols2}")
    print()
    
    print("3. Moving Mantel-Haenszel estimate by category...")
    result3 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('profit', 'category', mantel_haenszel_estimate, window=30))
    
    moving_cols3 = result3.get_moving_columns()
    print(f"   Created columns: {moving_cols3}")
    print()
    
    print("4. Moving CUPED adjustment by region...")
    result4 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'region', cuped_adjustment, window=21))
    
    moving_cols4 = result4.get_moving_columns()
    print(f"   Created columns: {moving_cols1}")
    print()
    
    print("5. Moving PrePost adjustment by category...")
    # Create a pre-treatment column for demonstration
    df['sales_pre'] = df.groupby(['category', 'region'])['sales'].shift(1).fillna(df['sales'])
    
    result5 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'category', prepost_adjustment, window=14))
    
    moving_cols5 = result5.get_moving_columns()
    print(f"   Created columns: {moving_cols5}")
    print()
    
    print("6. Moving power analysis by region...")
    result6 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('revenue', 'region', power_analysis, window=30))
    
    moving_cols6 = result6.get_moving_columns()
    print(f"   Created columns: {moving_cols6}")
    print()
    
    print("7. Moving stratified summary by category...")
    result7 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('profit', 'category', stratified_summary, window=21))
    
    moving_cols7 = result7.get_moving_columns()
    print(f"   Created columns: {moving_cols7}")
    print()
    
    print("8. Moving bootstrap confidence interval by region...")
    result8 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('sales', 'region', bootstrap_confidence_interval, window=14))
    
    moving_cols8 = result8.get_moving_columns()
    print(f"   Created columns: {moving_cols8}")
    print()
    
    print("9. Moving multi-comparison adjustment by category...")
    result9 = (MovingAggrPipe.from_dataframe(df)
               | moving_apply_by_group('revenue', 'category', multi_comparison_adjustment, window=21))
    
    moving_cols9 = result9.get_moving_columns()
    print(f"   Created columns: {moving_cols9}")
    print()
    
    print("10. Moving effect size by region...")
    result10 = (MovingAggrPipe.from_dataframe(df)
                | moving_apply_by_group('profit', 'region', effect_size, window=30))
    
    moving_cols10 = result10.get_moving_columns()
    print(f"   Created columns: {moving_cols10}")
    print()
    
    print("11. Moving z-score by category...")
    result11 = (MovingAggrPipe.from_dataframe(df)
                | moving_apply_by_group('sales', 'category', z_score, window=14))
    
    moving_cols11 = result11.get_moving_columns()
    print(f"   Created columns: {moving_cols11}")
    print()
    
    print("12. Moving relative risk by region...")
    result12 = (MovingAggrPipe.from_dataframe(df)
                | moving_apply_by_group('revenue', 'region', relative_risk, window=21))
    
    moving_cols12 = result12.get_moving_columns()
    print(f"   Created columns: {moving_cols12}")
    print()
    
    print("13. Moving odds ratio by category...")
    result13 = (MovingAggrPipe.from_dataframe(df)
                | moving_apply_by_group('profit', 'category', odds_ratio, window=30))
    
    moving_cols13 = result13.get_moving_columns()
    print(f"   Created columns: {moving_cols13}")
    print()


def main():
    """
    Main function to run all demonstrations.
    """
    print("Group Aggregation Functions with Moving Aggregation Pipeline")
    print("=" * 60)
    print()
    
    try:
        # Run demonstrations
        demonstrate_basic_functions()
        print("-" * 60)
        
        demonstrate_statistical_functions()
        print("-" * 60)
        
        demonstrate_advanced_functions()
        print("-" * 60)
        
        demonstrate_chained_operations()
        print("-" * 60)
        
        demonstrate_custom_functions()
        print("-" * 60)
        
        demonstrate_operations_functions()
        print("-" * 60)
        
        print("\nAll demonstrations completed successfully!")
        
    except Exception as e:
        print(f"Error during demonstration: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
