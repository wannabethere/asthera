"""
Unified Interface Demo for ML Tools

This script demonstrates how all the different pipe classes now share
a unified interface through the BasePipe class.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

# Import all the pipe classes
from .base_pipe import BasePipe
from .anomalydetection import AnomalyPipe
from .metrics_tools import MetricsPipe
from .cohortanalysistools import CohortPipe
from .movingaverages import MovingAggrPipe
from .operations_tools import OperationsPipe
from .riskanalysis import RiskPipe
from .segmentationtools import SegmentationPipe
from .timeseriesanalysis import TimeSeriesPipe
from .trendanalysistools import TrendPipe
from .funnelanalysis import FunnelPipe


def create_sample_data() -> pd.DataFrame:
    """Create sample data for demonstration"""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    
    data = pd.DataFrame({
        'date': dates,
        'user_id': np.random.randint(1, 1001, 100),
        'value': np.random.normal(100, 20, 100),
        'category': np.random.choice(['A', 'B', 'C'], 100),
        'region': np.random.choice(['North', 'South', 'East', 'West'], 100),
        'revenue': np.random.exponential(50, 100),
        'sales': np.random.poisson(25, 100)
    })
    
    return data


def demonstrate_unified_interface():
    """Demonstrate the unified interface across all pipe classes"""
    
    print("=== Unified Interface Demo for ML Tools ===\n")
    
    # Create sample data
    df = create_sample_data()
    print(f"Sample data shape: {df.shape}")
    print(f"Columns: {list(df.columns)}\n")
    
    # List all pipe classes
    pipe_classes = [
        AnomalyPipe,
        MetricsPipe,
        CohortPipe,
        MovingAggrPipe,
        OperationsPipe,
        RiskPipe,
        SegmentationPipe,
        TimeSeriesPipe,
        TrendPipe,
        FunnelPipe
    ]
    
    print("=== Testing Unified Interface Methods ===\n")
    
    for pipe_class in pipe_classes:
        print(f"Testing {pipe_class.__name__}:")
        
        try:
            # Test 1: Create pipe from dataframe
            pipe = pipe_class.from_dataframe(df)
            print(f"  ✓ from_dataframe() - Success")
            
            # Test 2: Check if it has data
            has_data = pipe.has_data()
            print(f"  ✓ has_data() - {has_data}")
            
            # Test 3: Get data info
            data_info = pipe.get_data_info()
            print(f"  ✓ get_data_info() - Shape: {data_info.get('shape', 'N/A')}")
            
            # Test 4: Get current data
            current_data = pipe.get_data()
            print(f"  ✓ get_data() - Type: {type(current_data).__name__}")
            
            # Test 5: Copy pipe
            copied_pipe = pipe.copy()
            print(f"  ✓ copy() - Success")
            
            # Test 6: Check if it's a BasePipe instance
            is_base_pipe = isinstance(pipe, BasePipe)
            print(f"  ✓ isinstance(BasePipe) - {is_base_pipe}")
            
            # Test 7: Try to get summary (may fail if no analysis performed)
            try:
                summary = pipe.get_summary()
                if "error" in summary:
                    print(f"  ✓ get_summary() - {summary['error']}")
                else:
                    print(f"  ✓ get_summary() - Success")
            except Exception as e:
                print(f"  ✓ get_summary() - Not implemented or error: {str(e)[:50]}...")
            
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:50]}...")
            print()
    
    print("=== Interface Consistency Check ===\n")
    
    # Check that all pipes have the required methods
    required_methods = [
        'from_dataframe',
        'has_data', 
        'get_data_info',
        'get_data',
        'set_data',
        'copy',
        'to_df',
        'get_summary'
    ]
    
    print("Required methods in BasePipe:")
    for method in required_methods:
        print(f"  - {method}")
    
    print("\nChecking method availability in each pipe class:")
    for pipe_class in pipe_classes:
        print(f"\n{pipe_class.__name__}:")
        pipe = pipe_class()
        for method in required_methods:
            has_method = hasattr(pipe, method)
            status = "✓" if has_method else "✗"
            print(f"  {status} {method}")
    
    print("\n=== Usage Example ===\n")
    
    # Demonstrate a simple pipeline with unified interface
    print("Example: Using MetricsPipe with unified interface")
    
    metrics_pipe = MetricsPipe.from_dataframe(df)
    print(f"Created pipe: {type(metrics_pipe).__name__}")
    print(f"Has data: {metrics_pipe.has_data()}")
    print(f"Data shape: {metrics_pipe.get_data_info()['shape']}")
    
    # Add some metrics
    from .metrics_tools import Sum, Mean, Count
    
    metrics_pipe = (metrics_pipe 
                   | Sum('revenue') 
                   | Mean('sales') 
                   | Count('user_id'))
    
    # Get summary
    summary = metrics_pipe.get_summary()
    print(f"Summary: {summary['total_metrics']} metrics calculated")
    print(f"Metrics: {list(summary['metrics_values'].keys())}")
    
    print("\n=== Unified Interface Benefits ===\n")
    print("1. Consistent API across all analysis types")
    print("2. Common methods: from_dataframe(), has_data(), get_data_info(), etc.")
    print("3. Type safety through BasePipe inheritance")
    print("4. Easy to extend with new pipe types")
    print("5. Unified error handling and data validation")
    print("6. Consistent documentation and usage patterns")


if __name__ == "__main__":
    demonstrate_unified_interface() 