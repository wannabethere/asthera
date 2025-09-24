"""
Example demonstrating the unified pipeline approach where each pipeline
merges its state into new columns of the original dataframe.

This allows each pipeline to run independently and produce a single
combined result with all pipeline states merged as new columns.
"""

import pandas as pd
import numpy as np
from .movingaverages import MovingAggrPipe, moving_average
from .metrics_tools import MetricsPipe, Sum, Mean, Count
from .operations_tools import OperationsPipe, PercentChange
from .cohortanalysistools import CohortPipe, form_time_cohorts, calculate_retention


def create_sample_data():
    """
    Create sample data for demonstration.
    
    Returns:
    --------
    pd.DataFrame
        Sample DataFrame with time series data
    """
    np.random.seed(42)
    
    # Create date range
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    
    # Create sample data
    data = []
    categories = ['Electronics', 'Clothing', 'Books', 'Food']
    regions = ['North', 'South', 'East', 'West']
    
    for i, date in enumerate(dates):
        for category in categories:
            for region in regions:
                # Generate some realistic data with trends and seasonality
                base_value = 100 + np.sin(2 * np.pi * i / 365) * 20
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
                    'user_id': f"user_{i}_{category}_{region}",
                    'sales': sales,
                    'revenue': revenue,
                    'profit': profit,
                    'volume': np.random.uniform(1, 10)
                })
    
    df = pd.DataFrame(data)
    return df.sort_values(['date', 'category', 'region']).reset_index(drop=True)


def demonstrate_unified_pipeline():
    """
    Demonstrate how multiple pipelines can run independently and merge their
    state into a single dataframe with new columns.
    """
    print("=== Unified Pipeline Demonstration ===\n")
    
    # Create sample data
    df = create_sample_data()
    print(f"Original data shape: {df.shape}")
    print(f"Original columns: {list(df.columns)}")
    print()
    
    # Run different pipelines independently
    print("1. Running Moving Aggregation Pipeline...")
    moving_pipe = (MovingAggrPipe.from_dataframe(df)
                   | moving_average('sales', window=7, method='simple')
                   | moving_average('revenue', window=14, method='exponential'))
    
    print("2. Running Metrics Pipeline...")
    metrics_pipe = (MetricsPipe.from_dataframe(df)
                    | Sum('revenue')
                    | Mean('sales')
                    | Count('user_id'))
    
    print("3. Running Operations Pipeline...")
    # Create a simple condition column for demonstration
    df_with_condition = df.copy()
    df_with_condition['condition'] = df_with_condition['category'].isin(['Electronics', 'Clothing'])
    df_with_condition['control'] = df_with_condition['region'].isin(['North', 'South'])
    
    operations_pipe = (OperationsPipe.from_dataframe(df_with_condition)
                       | PercentChange('condition', 'control'))
    
    print("4. Running Cohort Analysis Pipeline...")
    cohort_pipe = (CohortPipe.from_dataframe(df)
                   | form_time_cohorts('date', 'cohort', 'M')
                   | calculate_retention('cohort', 'date', 'user_id', 'M', 6))
    
    # Now demonstrate the unified approach
    print("\n=== Unified Results ===")
    
    # Each pipeline can now be converted to a unified dataframe
    print("\n1. Moving Aggregation Results:")
    moving_df = moving_pipe.to_df(include_metadata=True)
    print(f"   Shape: {moving_df.shape}")
    print(f"   New columns: {[col for col in moving_df.columns if col not in df.columns]}")
    
    print("\n2. Metrics Results:")
    metrics_df = metrics_pipe.to_df(include_metadata=True)
    print(f"   Shape: {metrics_df.shape}")
    print(f"   New columns: {[col for col in metrics_df.columns if col not in df.columns]}")
    
    print("\n3. Operations Results:")
    operations_df = operations_pipe.to_df(include_metadata=True)
    print(f"   Shape: {operations_df.shape}")
    print(f"   New columns: {[col for col in operations_df.columns if col not in df_with_condition.columns]}")
    
    print("\n4. Cohort Analysis Results:")
    cohort_df = cohort_pipe.to_df(include_metadata=True)
    print(f"   Shape: {cohort_df.shape}")
    print(f"   New columns: {[col for col in cohort_df.columns if col not in df.columns]}")
    
    # Show how all pipelines can be combined
    print("\n=== Combined Pipeline Results ===")
    
    # Start with the original data
    combined_df = df.copy()
    
    # Merge each pipeline's state
    combined_df = moving_pipe.merge_to_df(combined_df, include_metadata=True)
    combined_df = metrics_pipe.merge_to_df(combined_df, include_metadata=True)
    combined_df = operations_pipe.merge_to_df(combined_df, include_metadata=True)
    combined_df = cohort_pipe.merge_to_df(combined_df, include_metadata=True)
    
    print(f"Combined dataframe shape: {combined_df.shape}")
    print(f"Total columns: {len(combined_df.columns)}")
    print(f"Original columns: {len(df.columns)}")
    print(f"New columns added: {len(combined_df.columns) - len(df.columns)}")
    
    # Show the new columns by pipeline type
    pipeline_columns = {}
    for col in combined_df.columns:
        if col not in df.columns:
            if col.startswith('pipeline_'):
                pipeline_columns.setdefault('pipeline_info', []).append(col)
            elif col.startswith('moving_'):
                pipeline_columns.setdefault('moving_aggregation', []).append(col)
            elif col.startswith('metrics_'):
                pipeline_columns.setdefault('metrics', []).append(col)
            elif col.startswith('ops_'):
                pipeline_columns.setdefault('operations', []).append(col)
            elif col.startswith('cohort_'):
                pipeline_columns.setdefault('cohort_analysis', []).append(col)
    
    print("\nNew columns by pipeline type:")
    for pipeline_type, cols in pipeline_columns.items():
        print(f"  {pipeline_type}: {len(cols)} columns")
        if len(cols) <= 5:
            print(f"    {cols}")
        else:
            print(f"    {cols[:5]} ... and {len(cols) - 5} more")
    
    # Show sample of the combined data
    print("\n=== Sample of Combined Data ===")
    sample_cols = ['date', 'category', 'region', 'sales', 'revenue'] + list(pipeline_columns.get('pipeline_info', []))[:3]
    sample_df = combined_df[sample_cols].head(10)
    print(sample_df.to_string(index=False))
    
    return combined_df


def demonstrate_pipeline_independence():
    """
    Demonstrate that each pipeline can run independently and be combined later.
    """
    print("\n=== Pipeline Independence Demonstration ===\n")
    
    # Create sample data
    df = create_sample_data()
    
    # Run pipelines in different orders and combinations
    print("1. Running only Moving Aggregation...")
    moving_only = (MovingAggrPipe.from_dataframe(df)
                   | moving_average('sales', window=7))
    moving_result = moving_only.to_df()
    print(f"   Result shape: {moving_result.shape}")
    print(f"   Has moving columns: {any('_ma' in col for col in moving_result.columns)}")
    
    print("\n2. Running only Metrics...")
    metrics_only = (MetricsPipe.from_dataframe(df)
                    | Sum('revenue')
                    | Mean('sales'))
    metrics_result = metrics_only.to_df()
    print(f"   Result shape: {metrics_result.shape}")
    print(f"   Has metrics columns: {any('metrics_' in col for col in metrics_result.columns)}")
    
    print("\n3. Running both together...")
    # Start with moving aggregation
    combined = moving_only.merge_to_df(df)
    # Add metrics
    combined = metrics_only.merge_to_df(combined)
    
    print(f"   Combined shape: {combined.shape}")
    print(f"   Has moving columns: {any('_ma' in col for col in combined.columns)}")
    print(f"   Has metrics columns: {any('metrics_' in col for col in combined.columns)}")
    
    print("\n4. Running in different order...")
    # Start with metrics
    combined2 = metrics_only.merge_to_df(df)
    # Add moving aggregation
    combined2 = moving_only.merge_to_df(combined2)
    
    print(f"   Combined shape: {combined2.shape}")
    print(f"   Has moving columns: {any('_ma' in col for col in combined2.columns)}")
    print(f"   Has metrics columns: {any('metrics_' in col for col in combined2.columns)}")
    
    # Verify results are the same regardless of order
    print(f"\n5. Results are identical regardless of order: {combined.equals(combined2)}")


def main():
    """
    Main function to run all demonstrations.
    """
    print("Unified Pipeline State Management")
    print("=" * 50)
    print()
    
    try:
        # Run demonstrations
        combined_df = demonstrate_unified_pipeline()
        demonstrate_pipeline_independence()
        
        print("\n" + "=" * 50)
        print("All demonstrations completed successfully!")
        print("\nKey Benefits:")
        print("1. Each pipeline runs independently")
        print("2. State is merged into new columns of original dataframe")
        print("3. Pipelines can be combined in any order")
        print("4. No state conflicts between pipelines")
        print("5. Easy to track which pipeline contributed which columns")
        
    except Exception as e:
        print(f"Error during demonstration: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
