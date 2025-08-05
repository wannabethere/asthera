"""
Integrated Pipeline Example
===========================

This example demonstrates how to combine SelectPipe with MetricsPipe 
for complete data analysis workflows.
"""

import pandas as pd
import numpy as np
import asyncio
from typing import Dict, Any

# Import our custom tools
from app.tools.mltools.select_pipe import (
    SelectPipe, Select, Deselect, Rename, AddColumns,
    numeric, string, contains, startswith, cols, where
)

# Assuming MetricsPipe is available from your codebase
from app.tools.mltools.metrics_tools import (
    MetricsPipe, Sum, Mean, Count, Max, Min, Ratio, 
    StandardDeviation, Correlation, PivotTable, GroupBy
)

from app.core.engine_provider import EngineProvider


class IntegratedAnalyticsPipeline:
    """
    A comprehensive analytics pipeline that combines column selection 
    with metrics calculation using both SelectPipe and MetricsPipe.
    """
    
    def __init__(self, engine=None):
        """
        Initialize the pipeline with an optional engine.
        If no engine is provided, one will be created using EngineProvider when needed.
        """
        self.engine = engine
        self.data_cache = {}
    
    def create_sample_ecommerce_data(self) -> pd.DataFrame:
        """Create comprehensive e-commerce sample data"""
        np.random.seed(42)
        
        # Generate 1000 records
        n_records = 1000
        
        data = pd.DataFrame({
            # Customer information
            'customer_id': range(1, n_records + 1),
            'customer_name': [f'Customer_{i:04d}' for i in range(1, n_records + 1)],
            'customer_email': [f'customer{i}@example.com' for i in range(1, n_records + 1)],
            'customer_age': np.random.randint(18, 75, n_records),
            'customer_segment': np.random.choice(['Premium', 'Standard', 'Basic'], n_records, p=[0.2, 0.5, 0.3]),
            'registration_date': pd.date_range('2022-01-01', periods=n_records, freq='8h'),
            
            # Order information
            'order_id': [f'ORD_{i:06d}' for i in range(1, n_records + 1)],
            'order_date': pd.date_range('2023-01-01', periods=n_records, freq='6h'),
            'order_amount': np.random.lognormal(4, 1, n_records),  # Log-normal for realistic distribution
            'order_quantity': np.random.randint(1, 20, n_records),
            'shipping_cost': np.random.uniform(5, 50, n_records),
            'tax_amount': np.random.uniform(0, 50, n_records),
            
            # Product information
            'product_id': [f'PROD_{np.random.randint(1, 500):03d}' for _ in range(n_records)],
            'product_category': np.random.choice(
                ['Electronics', 'Clothing', 'Books', 'Home', 'Sports', 'Beauty'], 
                n_records
            ),
            'product_brand': np.random.choice(
                ['BrandA', 'BrandB', 'BrandC', 'BrandD', 'BrandE'], 
                n_records
            ),
            'product_rating': np.random.uniform(1, 5, n_records),
            
            # Financial information
            'discount_amount': np.random.uniform(0, 100, n_records),
            'coupon_used': np.random.choice([True, False], n_records, p=[0.3, 0.7]),
            'payment_method': np.random.choice(['Credit', 'Debit', 'PayPal', 'Cash'], n_records),
            'refund_amount': np.random.exponential(0.1, n_records),  # Most orders have no refund
            
            # Geographic information
            'country': np.random.choice(['US', 'UK', 'DE', 'FR', 'CA'], n_records),
            'region': np.random.choice(['North', 'South', 'East', 'West', 'Central'], n_records),
            'city_tier': np.random.choice(['Tier1', 'Tier2', 'Tier3'], n_records, p=[0.4, 0.4, 0.2]),
            
            # Behavioral data
            'website_sessions': np.random.randint(1, 50, n_records),
            'page_views': np.random.randint(5, 200, n_records),  
            'time_on_site_minutes': np.random.exponential(20, n_records),
            'cart_abandonment': np.random.choice([True, False], n_records, p=[0.4, 0.6]),
            
            # Satisfaction metrics
            'customer_satisfaction': np.random.uniform(1, 10, n_records),
            'nps_score': np.random.randint(-100, 100, n_records),
            'support_tickets': np.random.poisson(0.5, n_records),  # Most customers have 0-1 tickets
        })
        
        # Add some computed fields
        data['total_order_value'] = data['order_amount'] + data['shipping_cost'] + data['tax_amount']
        data['net_order_value'] = data['total_order_value'] - data['discount_amount']
        data['profit_margin'] = np.random.uniform(0.1, 0.4, n_records)
        data['profit_amount'] = data['net_order_value'] * data['profit_margin']
        
        return data
    
    def customer_analytics_pipeline(self) -> Dict[str, Any]:
        """
        Complete customer analytics pipeline combining selection and metrics
        """
        print("=== Customer Analytics Pipeline ===")
        
        # Step 1: Create sample data
        data = self.create_sample_ecommerce_data()
        
        # Step 2: Create engine using engine provider (consistent with select_pipe_test.py)
        engine = EngineProvider.get_test_engine(
            sample_data=data,
            table_name='orders'
        )
        
        # Step 3: Customer Demographics Analysis
        # Get the data first for consistent approach
        customer_data = engine.get_dataframe('orders', [
            'customer_id', 'customer_segment', 'customer_age', 'country', 'region', 'registration_date'
        ])
        
        customer_demographics = (
            SelectPipe.from_dataframe(customer_data)
            | Select(
                cols('customer_id', 'customer_segment', 'customer_age', 'country', 'region') |
                contains('registration')
            )
            | Rename({
                'customer_age': 'age',
                'customer_segment': 'segment'
            })
        )
        
        customer_df = customer_demographics.to_df()
        
        # Step 4: Calculate customer metrics
        customer_metrics = (
            MetricsPipe.from_dataframe(customer_df)
            | Count('customer_id', 'total_customers')
            | Mean('age', 'avg_customer_age') 
            | PivotTable('segment', 'country', 'customer_id', 'count')
        )
        
        # Step 5: Financial Analysis Pipeline
        # Get the data first for complex operations
        financial_data = engine.get_dataframe('orders', [
            'order_id', 'customer_segment', 'order_amount', 'shipping_cost', 
            'tax_amount', 'discount_amount', 'coupon_used', 'payment_method'
        ])
        
        financial_analysis = (
            SelectPipe.from_dataframe(financial_data)
            | Select(
                cols('order_id', 'customer_segment') |
                contains('amount') | contains('cost') |
                cols('discount_amount', 'coupon_used', 'payment_method')
            )
            | AddColumns(
                revenue_per_order=lambda df: df['order_amount'],
                total_cost=lambda df: df['shipping_cost'] + df['tax_amount'],
                discount_rate=lambda df: df['discount_amount'] / df['order_amount']
            )
        )
        
        financial_df = financial_analysis.to_df()
        
        # Step 6: Calculate financial metrics
        financial_metrics = (
            MetricsPipe.from_dataframe(financial_df)
            | Sum('order_amount', 'total_revenue')
            | Sum('discount_amount', 'total_discounts')
            | Mean('discount_rate', 'avg_discount_rate')
            | Count('order_id', 'total_orders')
            | PivotTable('customer_segment', values='order_amount', aggfunc='sum')
        )
        
        # Step 7: Product Performance Analysis
        # Get the data first for consistent approach
        product_data = engine.get_dataframe('orders', [
            'product_category', 'product_brand', 'product_rating', 'order_amount', 
            'order_quantity', 'customer_satisfaction'
        ])
        
        product_analysis = (
            SelectPipe.from_dataframe(product_data)
            | Select(
                startswith('product') |
                cols('order_amount', 'order_quantity', 'customer_satisfaction')
            )
            | Deselect(contains('rating'))  # Remove product_rating for this analysis
            | Rename({
                'product_category': 'category',
                'product_brand': 'brand'
            })
        )
        
        product_df = product_analysis.to_df()
        
        product_metrics = (
            MetricsPipe.from_dataframe(product_df)
            | GroupBy('category', {
                'order_amount': ['sum', 'mean', 'count'],
                'order_quantity': 'sum',
                'customer_satisfaction': 'mean'
            })
        )
        
        # Step 8: Geographic Performance
        # Get the data first for consistent approach
        geo_data = engine.get_dataframe('orders', [
            'country', 'region', 'city_tier', 'order_amount', 'net_order_value'
        ])
        
        geo_analysis = (
            SelectPipe.from_dataframe(geo_data)
            | Select(
                cols('country', 'region', 'city_tier', 'order_amount', 'net_order_value')
            )
        )
        
        geo_df = geo_analysis.to_df()
        
        geo_metrics = (
            MetricsPipe.from_dataframe(geo_df)
            | PivotTable('country', 'region', 'order_amount', 'sum')
            | PivotTable('city_tier', values='net_order_value', aggfunc='mean', 
                        output_name='avg_order_by_tier')
        )
        
        # Step 9: Customer Behavior Analysis
        # Get the data first for complex operations
        behavior_data = engine.get_dataframe('orders', [
            'customer_id', 'website_sessions', 'page_views', 'time_on_site_minutes',
            'cart_abandonment', 'customer_satisfaction', 'support_tickets'
        ])
        
        behavior_analysis = (
            SelectPipe.from_dataframe(behavior_data)
            | Select(
                cols('customer_id') |
                contains('website') | contains('page') | contains('time') |
                cols('cart_abandonment', 'customer_satisfaction', 'support_tickets')
            )
            | AddColumns(
                pages_per_session=lambda df: df['page_views'] / df['website_sessions'],
                satisfaction_category=lambda df: pd.cut(
                    df['customer_satisfaction'], 
                    bins=[0, 3, 7, 10], 
                    labels=['Low', 'Medium', 'High']
                )
            )
        )
        
        behavior_df = behavior_analysis.to_df()
        
        behavior_metrics = (
            MetricsPipe.from_dataframe(behavior_df)
            | Mean('time_on_site_minutes', 'avg_time_on_site')
            | Mean('pages_per_session', 'avg_pages_per_session')
            | Correlation('website_sessions', 'customer_satisfaction')
            | PivotTable('satisfaction_category', values='support_tickets', aggfunc='mean')
        )
        
        # Compile all results
        results = {
            'customer_demographics': {
                'data': customer_df,
                'metrics': customer_metrics.get_summary(),
                'selection_summary': customer_demographics.get_selection_summary()
            },
            'financial_analysis': {
                'data': financial_df,
                'metrics': financial_metrics.get_summary(),
                'selection_summary': financial_analysis.get_selection_summary()
            },
            'product_performance': {
                'data': product_df,
                'metrics': product_metrics.get_summary(),
                'selection_summary': product_analysis.get_selection_summary()
            },
            'geographic_analysis': {
                'data': geo_df,
                'metrics': geo_metrics.get_summary(),
                'selection_summary': geo_analysis.get_selection_summary()
            },
            'behavior_analysis': {
                'data': behavior_df,
                'metrics': behavior_metrics.get_summary(),
                'selection_summary': behavior_analysis.get_selection_summary()
            }
        }
        
        return results
    
    def advanced_segmentation_pipeline(self) -> Dict[str, Any]:
        """
        Advanced customer segmentation using both pipes
        """
        print("\n=== Advanced Customer Segmentation Pipeline ===")
        
        # Create data
        data = self.create_sample_ecommerce_data()
        
        # Use EngineProvider for consistent engine creation (consistent with select_pipe_test.py)
        engine = EngineProvider.get_test_engine(
            sample_data=data,
            table_name='customers'
        )
        
        # Step 1: Select relevant features for segmentation
        # Get the data first for complex operations
        segmentation_data = engine.get_dataframe('customers', [
            'customer_id', 'customer_age', 'customer_segment', 'website_sessions', 
            'page_views', 'time_on_site_minutes', 'net_order_value', 'profit_amount'
        ])
        
        segmentation_features = (
            SelectPipe.from_dataframe(segmentation_data)
            | Select(
                cols('customer_id', 'customer_age') |
                numeric() & ~contains('id') |
                ~contains('date') & ~contains('email') & ~contains('name')
            )
            | Deselect(
                contains('refund') | contains('support') | contains('nps')
            )
            | AddColumns(
                # RFM Analysis features
                recency_days=lambda df: np.random.randint(1, 365, len(df)),  # Varied recency for testing
                frequency=lambda df: df['website_sessions'],
                monetary=lambda df: df['net_order_value'],
                
                # Behavioral scores
                engagement_score=lambda df: (
                    df['website_sessions'] * 0.3 + 
                    df['page_views'] * 0.1 + 
                    df['time_on_site_minutes'] * 0.02
                ),
                value_score=lambda df: (
                    df['net_order_value'] * 0.4 +
                    df['profit_amount'] * 0.6
                )
            )
        )
        
        segmentation_df = segmentation_features.to_df()
        
        # Step 2: Calculate segmentation metrics
        segmentation_metrics = (
            MetricsPipe.from_dataframe(segmentation_df)
            # Overall statistics
            | Count('customer_id', 'total_customers')
            | Mean('monetary', 'avg_customer_value')
            | Mean('frequency', 'avg_session_count')
            | StandardDeviation('value_score', 'value_score_std')
            
            # Segmentation analysis
            | PivotTable('customer_segment', values=['monetary', 'frequency', 'engagement_score'], 
                        aggfunc='mean', output_name='segment_profiles')
            | GroupBy('customer_segment', {
                'monetary': ['mean', 'std', 'count'],
                'engagement_score': 'mean',
                'value_score': 'mean'
            }, output_name='detailed_segments')
        )
        
        # Step 3: Create advanced segments using quantiles
        advanced_segments = (
            SelectPipe.from_dataframe(segmentation_df)
            | AddColumns(
                # Create RFM segments
                recency_quartile=lambda df: pd.qcut(df['recency_days'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop'),
                frequency_quartile=lambda df: pd.qcut(df['frequency'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop'),
                monetary_quartile=lambda df: pd.qcut(df['monetary'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop'),
                
                # Comprehensive customer score
                customer_score=lambda df: (
                    (df['monetary'] / df['monetary'].max()) * 0.4 +
                    (df['frequency'] / df['frequency'].max()) * 0.3 +
                    (df['engagement_score'] / df['engagement_score'].max()) * 0.3
                )
            )
            | Select(
                cols('customer_id', 'customer_segment') |
                contains('quartile') | contains('score') |
                cols('monetary', 'frequency', 'engagement_score')
            )
        )
        
        advanced_df = advanced_segments.to_df()
        
        # Step 4: Analyze the advanced segments
        advanced_metrics = (
            MetricsPipe.from_dataframe(advanced_df)
            | PivotTable('frequency_quartile', 'monetary_quartile', 'customer_id', 'count',
                        output_name='rfm_matrix')
            | Mean('customer_score', 'avg_composite_score')
            | GroupBy(['customer_segment', 'monetary_quartile'], {
                'customer_score': 'mean',
                'engagement_score': 'mean'
            }, output_name='segment_quartile_analysis')
        )
        
        return {
            'segmentation_features': {
                'data': segmentation_df,
                'selection_summary': segmentation_features.get_selection_summary()
            },
            'segmentation_metrics': segmentation_metrics.get_summary(),
            'advanced_segments': {
                'data': advanced_df,
                'selection_summary': advanced_segments.get_selection_summary()
            },
            'advanced_metrics': advanced_metrics.get_summary()
        }
    
    def cohort_analysis_pipeline(self) -> Dict[str, Any]:
        """
        Cohort analysis combining selection and metrics calculation
        """
        print("\n=== Cohort Analysis Pipeline ===")
        
        # Create data with time-based patterns
        data = self.create_sample_ecommerce_data()
        
        # Add cohort information
        data['registration_month'] = data['registration_date'].dt.to_period('M')
        data['order_month'] = data['order_date'].dt.to_period('M')
        
        engine = EngineProvider.get_test_engine(
            sample_data=data,
            table_name='cohort_data'
        )
        
        # Step 1: Select cohort analysis features
        # Get the data first for complex operations
        cohort_data = engine.get_dataframe('cohort_data', [
            'customer_id', 'registration_month', 'order_month', 'net_order_value', 
            'order_quantity', 'customer_segment', 'product_category'
        ])
        
        cohort_selection = (
            SelectPipe.from_dataframe(cohort_data)
            | Select(
                cols('customer_id', 'registration_month', 'order_month', 'net_order_value', 
                     'order_quantity', 'customer_segment', 'product_category')
            )
            | AddColumns(
                # Calculate months since registration
                months_since_registration=lambda df: (
                    df['order_month'] - df['registration_month']
                ).apply(lambda x: x.n if pd.notna(x) else 0),
                
                # Create cohort labels
                cohort_label=lambda df: df['registration_month'].astype(str),
                
                # Calculate customer lifetime metrics
                lifetime_value=lambda df: df['net_order_value'],
                order_frequency=lambda df: df['order_quantity']
            )
        )
        
        cohort_df = cohort_selection.to_df()
        
        # Step 2: Calculate cohort metrics
        # Basic cohort statistics
        cohort_summary = (
            MetricsPipe.from_dataframe(cohort_df)
            | GroupBy('cohort_label', {
                'customer_id': 'nunique',
                'lifetime_value': ['mean', 'sum'],
                'order_frequency': 'mean'
            }, output_name='cohort_summary')
        )
        
        # Retention analysis
        retention_metrics = (
            MetricsPipe.from_dataframe(cohort_df)
            | PivotTable('cohort_label', 'months_since_registration', 
                        'customer_id', 'nunique', output_name='retention_matrix')
        )
        
        # Revenue cohort analysis  
        revenue_metrics = (
            MetricsPipe.from_dataframe(cohort_df)
            | PivotTable('cohort_label', 'months_since_registration',
                        'lifetime_value', 'sum', output_name='revenue_cohort_matrix')
        )
        
        # Step 3: Segment-based cohort analysis
        segment_cohort = (
            SelectPipe.from_dataframe(cohort_df)
            | Select(
                cols('customer_segment', 'cohort_label', 'months_since_registration', 
                     'lifetime_value', 'order_frequency')
            )
        )
        
        segment_cohort_df = segment_cohort.to_df()
        
        segment_metrics = (
            MetricsPipe.from_dataframe(segment_cohort_df)
            | GroupBy(['customer_segment', 'cohort_label'], {
                'lifetime_value': ['mean', 'count'],
                'order_frequency': 'mean'
            }, output_name='segment_cohort_analysis')
        )
        
        return {
            'cohort_data': {
                'data': cohort_df,
                'selection_summary': cohort_selection.get_selection_summary()
            },
            'cohort_summary': cohort_summary.get_summary(),
            'retention_metrics': retention_metrics.get_summary(),
            'revenue_metrics': revenue_metrics.get_summary(),
            'segment_cohort': {
                'data': segment_cohort_df,
                'selection_summary': segment_cohort.get_selection_summary()
            },
            'segment_metrics': segment_metrics.get_summary()
        }
    
    def print_pipeline_summary(self, results: Dict[str, Any], pipeline_name: str):
        """Print a summary of pipeline results"""
        print(f"\n=== {pipeline_name} Summary ===")
        
        for analysis_name, analysis_data in results.items():
            print(f"\n{analysis_name.replace('_', ' ').title()}:")
            
            if 'data' in analysis_data:
                df = analysis_data['data']
                print(f"  Data shape: {df.shape}")
                print(f"  Columns: {list(df.columns)[:5]}{'...' if len(df.columns) > 5 else ''}")
            
            if 'selection_summary' in analysis_data:
                selection = analysis_data['selection_summary']
                print(f"  Selection operations: {len(selection.get('selection_history', []))}")
                print(f"  Selected columns: {selection.get('selected_columns', 0)}")
            
            if 'metrics' in analysis_data:
                metrics = analysis_data['metrics']
                if isinstance(metrics, dict):
                    print(f"  Calculated metrics: {metrics.get('total_metrics', 0)}")
                    print(f"  Pivot tables: {metrics.get('total_pivot_tables', 0)}")


def main():
    """Run the integrated pipeline examples"""
    print("Starting Integrated Analytics Pipeline Examples")
    print("=" * 60)
    
    # Create pipeline instance
    pipeline = IntegratedAnalyticsPipeline()
    
    # Run customer analytics pipeline
    print("\n1. Running Customer Analytics Pipeline...")
    customer_results = pipeline.customer_analytics_pipeline()
    pipeline.print_pipeline_summary(customer_results, "Customer Analytics")
    
    # Run advanced segmentation pipeline
    print("\n2. Running Advanced Segmentation Pipeline...")
    segmentation_results = pipeline.advanced_segmentation_pipeline()
    pipeline.print_pipeline_summary(segmentation_results, "Advanced Segmentation")
    
    # Run cohort analysis pipeline
    print("\n3. Running Cohort Analysis Pipeline...")
    cohort_results = pipeline.cohort_analysis_pipeline()
    pipeline.print_pipeline_summary(cohort_results, "Cohort Analysis")
    
    print("\n" + "=" * 60)
    print("All integrated pipeline examples completed successfully!")
    
    return {
        'customer_analytics': customer_results,
        'segmentation': segmentation_results,
        'cohort_analysis': cohort_results
    }


if __name__ == "__main__":
    results = main()