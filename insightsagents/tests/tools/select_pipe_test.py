"""
Select Tools Usage Examples
===========================

This file demonstrates how to use the SelectPipe with various engines and data sources.
"""

import pandas as pd
import numpy as np
import asyncio
from app.tools.mltools.select_pipe import (
    SelectPipe, Select, Deselect, Rename, Reorder, AddColumns,
    everything, cols, contains, startswith, endswith, matches,
    numeric, string, temporal, categorical, nominal,
    integer, floating, has_type, where,
    select_numeric, select_strings, select_dates,
    select_by_pattern, select_by_prefix, select_by_suffix,
    preview_selection
)

# Import the engine provider for testing
from app.core.engine_provider import EngineProvider


def create_sample_data():
    """Create sample data for examples"""
    np.random.seed(42)
    
    return pd.DataFrame({
        'customer_id': range(1, 101),
        'customer_name': [f'Customer {i}' for i in range(1, 101)],
        'customer_email': [f'customer{i}@example.com' for i in range(1, 101)],
        'order_date': pd.date_range('2023-01-01', periods=100, freq='D'),
        'order_amount': np.random.uniform(10, 1000, 100),
        'order_quantity': np.random.randint(1, 10, 100),
        'product_category': np.random.choice(['Electronics', 'Clothing', 'Books', 'Home'], 100),
        'is_premium': np.random.choice([True, False], 100),
        'customer_age': np.random.randint(18, 80, 100),
        'discount_pct': np.random.uniform(0, 0.3, 100),
        'region_code': np.random.choice(['US-WEST', 'US-EAST', 'EU-NORTH', 'EU-SOUTH'], 100),
        'last_login': pd.date_range('2023-12-01', periods=100, freq='h'),
        'customer_score': np.random.uniform(0, 100, 100)
    })


class SelectExamples:
    """Examples of using SelectPipe with different data sources"""
    
    def __init__(self):
        self.sample_data = create_sample_data()
    
    def basic_dataframe_examples(self):
        """Basic examples using DataFrame directly"""
        print("=== Basic DataFrame Examples ===")
        
        # Create pipe from DataFrame
        pipe = SelectPipe.from_dataframe(self.sample_data)
        
        # Example 1: Select all columns
        result1 = pipe | Select(everything())
        print(f"Select everything: {len(result1.get_selected_columns())} columns")
        print(f"Columns: {result1.get_selected_columns()[:5]}...")  # Show first 5
        
        # Example 2: Select specific columns by name
        result2 = pipe | Select(cols('customer_id', 'customer_name', 'order_amount'))
        print(f"\nSelect specific columns: {result2.get_selected_columns()}")
        
        # Example 3: Select columns by type
        result3 = pipe | Select(numeric())
        print(f"\nSelect numeric columns: {result3.get_selected_columns()}")
        
        # Example 4: Select columns by pattern
        result4 = pipe | Select(startswith('customer'))
        print(f"\nSelect columns starting with 'customer': {result4.get_selected_columns()}")
        
        # Example 5: Complex selection with logical operations
        result5 = pipe | Select(
            (startswith('order') | startswith('customer')) & ~contains('email')
        )
        print(f"\nComplex selection: {result5.get_selected_columns()}")
        
        # Example 6: Chain multiple operations
        result6 = (pipe 
                  | Select(numeric() | contains('name'))
                  | Deselect(contains('score'))
                  | Rename({'customer_name': 'name', 'order_amount': 'amount'}))
        print(f"\nChained operations: {result6.get_selected_columns()}")
        
        return result6
    
    def advanced_selection_examples(self):
        """Advanced selection examples"""
        print("\n=== Advanced Selection Examples ===")
        
        pipe = SelectPipe.from_dataframe(self.sample_data)
        
        # Example 1: Select using custom predicate
        def high_variance_columns(col):
            """Select columns with high variance (for numeric columns)"""
            if pd.api.types.is_numeric_dtype(col):
                return col.var() > col.mean()
            return False
        
        result1 = pipe | Select(where(high_variance_columns))
        print(f"High variance columns: {result1.get_selected_columns()}")
        
        # Example 2: Select by data type with custom logic
        result2 = pipe | Select(
            where(lambda col: col.dtype == 'object' and col.str.contains('@').any())
        )
        print(f"Email columns: {result2.get_selected_columns()}")
        
        # Example 3: Select columns with specific patterns
        result3 = pipe | Select(matches(r'.*_(id|code|pct)$'))
        print(f"ID, code, or percentage columns: {result3.get_selected_columns()}")
        
        # Example 4: Select and reorder
        result4 = (pipe 
                  | Select(contains('customer') | contains('order'))
                  | Reorder('customer_id', 'customer_name', 'order_date', 'order_amount'))
        print(f"Reordered columns: {result4.get_selected_columns()}")
        
        # Example 5: Add computed columns
        result5 = (pipe 
                  | Select(cols('order_amount', 'order_quantity', 'discount_pct'))
                  | AddColumns(
                      total_before_discount=lambda df: df['order_amount'] / (1 - df['discount_pct']),
                      avg_item_price=lambda df: df['order_amount'] / df['order_quantity'],
                      discount_amount=lambda df: df['order_amount'] * df['discount_pct'] / (1 - df['discount_pct'])
                  ))
        print(f"With computed columns: {result5.get_selected_columns()}")
        
        return result5
    
    def pandas_engine_examples(self):
        """Examples using engine provider with DataFrame data"""
        print("\n=== Engine Provider Examples ===")
        
        # Create engine using the engine provider with DataFrame data
        engine = EngineProvider.get_test_engine(
            sample_data=self.sample_data,
            table_name='customers'
        )
        
        # Create pipe from engine
        pipe = SelectPipe.from_engine(engine, 'customers')
        
        # Example 1: Select columns and fetch data
        result1 = pipe | Select(contains('customer') | contains('order'))
        df1 = result1.to_df()
        print(f"Selected {len(result1.get_selected_columns())} columns, fetched {len(df1)} rows")
        print(f"Columns: {list(df1.columns)}")
        
        # Example 2: Complex selection with engine
        result2 = (pipe 
                  | Select(numeric() | temporal())
                  | Deselect(contains('score')))
        df2 = result2.to_df()
        print(f"Numeric/temporal without score: {list(df2.columns)}")
        
        return result2
    
    async def async_engine_examples(self):
        """Examples with engine provider (simulating async)"""
        print("\n=== Engine Provider Examples (Async Simulation) ===")
        
        # Create engine using the engine provider
        engine = EngineProvider.get_test_engine(
            sample_data=self.sample_data,
            table_name='customers'
        )
        
        # Create pipe from engine
        pipe = SelectPipe.from_engine(engine, 'customers')
        
        # Select columns
        result = pipe | Select(
            startswith('customer') | 
            cols('order_date', 'order_amount', 'product_category')
        )
        
        # Use direct DataFrame access from the engine (no async needed)
        df = engine.get_dataframe('customers', result.get_selected_columns())
        print(f"Engine-based fetch: {len(df)} rows, {len(df.columns)} columns")
        print(f"Columns: {list(df.columns)}")
        
        return result
    
    def starburst_engine_examples(self):
        """Examples using engine provider (simulating Starburst)"""
        print("\n=== Engine Provider Examples (Starburst Simulation) ===")
        
        try:
            # Simulate working with data that could come from Starburst
            # In real usage, this would be data fetched from Starburst
            # For this example, we'll use the engine provider with DataFrame data
            
            # Create engine using the engine provider (simulating Starburst data)
            engine = EngineProvider.get_test_engine(
                sample_data=self.sample_data,
                table_name='sales_data'
            )
            
            # Create pipe from engine
            pipe = SelectPipe.from_engine(engine, 'sales_data')
            
            # Example: Select columns for analytics
            result = (pipe 
                     | Select(
                         cols('customer_id', 'product_category') |
                         numeric() |
                         temporal()
                     )
                     | Deselect(contains('score'))
                     | Rename({
                         'order_amount': 'revenue',
                         'order_quantity': 'quantity',
                         'customer_age': 'age'
                     }))
            
            print(f"Analytics columns: {result.get_selected_columns()}")
            print(f"Selection summary: {result.get_selection_summary()}")
            
            return result
            
        except Exception as e:
            print(f"Note: Engine provider simulation failed: {e}")
            return None
    
    def preview_examples(self):
        """Examples of previewing selections"""
        print("\n=== Preview Examples ===")
        
        # Preview without creating a pipe
        preview1 = preview_selection(
            self.sample_data,
            numeric() | contains('name')
        )
        print("Preview numeric or name columns:")
        print(f"  Total columns: {preview1['total_columns']}")
        print(f"  Selected: {preview1['selected_columns']}")
        print(f"  Selected names: {preview1['selected_column_names']}")
        
        # Preview complex selection
        preview2 = preview_selection(
            self.sample_data,
            (startswith('customer') | startswith('order')) & ~contains('email')
        )
        print("\nPreview complex selection:")
        print(f"  Selected: {preview2['selected_columns']}")
        print(f"  Unselected: {len(preview2['unselected_columns'])}")
        
        return preview1, preview2
    
    def convenience_function_examples(self):
        """Examples using convenience functions"""
        print("\n=== Convenience Function Examples ===")
        
        pipe = SelectPipe.from_dataframe(self.sample_data)
        
        # Use convenience functions
        numeric_result = pipe | select_numeric()
        print(f"select_numeric(): {len(numeric_result.get_selected_columns())} columns")
        
        string_result = pipe | select_strings()
        print(f"select_strings(): {len(string_result.get_selected_columns())} columns")
        
        date_result = pipe | select_dates()
        print(f"select_dates(): {len(date_result.get_selected_columns())} columns")
        
        pattern_result = pipe | select_by_pattern(r'.*_id$')
        print(f"select_by_pattern('.*_id$'): {pattern_result.get_selected_columns()}")
        
        prefix_result = pipe | select_by_prefix('customer')
        print(f"select_by_prefix('customer'): {prefix_result.get_selected_columns()}")
        
        suffix_result = pipe | select_by_suffix('_date')
        print(f"select_by_suffix('_date'): {suffix_result.get_selected_columns()}")
        
        return numeric_result, string_result, date_result


def run_all_examples():
    """Run all examples"""
    examples = SelectExamples()
    
    # Run synchronous examples
    print("Running select tool examples...\n")
    
    examples.basic_dataframe_examples()
    examples.advanced_selection_examples()
    examples.pandas_engine_examples()
    examples.preview_examples()
    examples.convenience_function_examples()
    examples.starburst_engine_examples()
    
    # Run async example
    async def run_async():
        await examples.async_engine_examples()
    
    asyncio.run(run_async())
    
    print("\n=== All examples completed! ===")


def integration_example():
    """
    Complete integration example showing real-world usage
    """
    print("\n=== Integration Example: Customer Analytics Pipeline ===")
    
    # Create sample data
    data = create_sample_data()
    
    # Step 1: Create engine using engine provider
    engine = EngineProvider.get_test_engine(
        sample_data=data,
        table_name='customers'
    )
    
    # Step 2: Create analytical pipeline using direct DataFrame approach
    # This avoids the engine data loading issues for complex operations
    analytics_pipe = (
        SelectPipe.from_dataframe(data)
        | Select(
            # Customer identifiers
            cols('customer_id', 'customer_name') |
            # Order information
            startswith('order') |
            # Customer demographics
            cols('customer_age', 'region_code') |
            # Business metrics
            contains('discount') | contains('score')
        )
        | Deselect(
            # Remove email for privacy
            contains('email')
        )
        | Rename({
            'order_amount': 'revenue',
            'order_quantity': 'units_sold',
            'customer_age': 'age',
            'discount_pct': 'discount_rate'
        })
        | Reorder(
            'customer_id', 'customer_name', 'age', 'region_code',
            'order_date', 'revenue', 'units_sold', 'discount_rate'
        )
        | AddColumns(
            revenue_per_unit=lambda df: df['revenue'] / df['units_sold'],
            customer_segment=lambda df: pd.cut(
                df['customer_score'], 
                bins=[0, 33, 66, 100], 
                labels=['Low', 'Medium', 'High']
            )
        )
    )
    
    # Step 3: Get results
    result_df = analytics_pipe.to_df()
    summary = analytics_pipe.get_selection_summary()
    
    print(f"Final dataset: {len(result_df)} rows × {len(result_df.columns)} columns")
    print(f"Columns: {list(result_df.columns)}")
    print(f"Selection history: {len(summary['selection_history'])} operations")
    
    # Step 4: Show sample data
    print("\nSample data:")
    print(result_df.head())
    
    return analytics_pipe, result_df


if __name__ == "__main__":
    # Run all examples
    run_all_examples()
    
    # Run integration example
    integration_example()