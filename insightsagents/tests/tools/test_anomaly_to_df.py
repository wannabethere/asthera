#!/usr/bin/env python3
"""
Simple test script to verify the to_df() functionality of AnomalyPipe
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.tools.mltools.anomalydetection import (
    AnomalyPipe,
    detect_statistical_outliers,
    detect_contextual_anomalies,
    detect_collective_anomalies,
    calculate_seasonal_residuals
)

def create_sample_data():
    """Create a small sample dataset for testing"""
    np.random.seed(42)
    
    # Create time series data with some anomalies
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    n_points = len(dates)
    
    # Create normal time series
    trend = np.linspace(100, 120, n_points)
    seasonal = 10 * np.sin(2 * np.pi * np.arange(n_points) / 365.25)
    noise = np.random.normal(0, 5, n_points)
    
    # Add some anomalies
    anomalies = np.zeros(n_points)
    anomaly_indices = [50, 100, 150, 200, 250, 300]
    for idx in anomaly_indices:
        if idx < n_points:
            anomalies[idx] = np.random.choice([-30, 30])  # Large positive or negative spikes
    
    # Combine components
    values = trend + seasonal + noise + anomalies
    
    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'value': values,
        'category': np.random.choice(['A', 'B', 'C'], n_points)
    })
    
    return df

def test_to_df_functionality():
    """Test the to_df() method with different anomaly detection types"""
    print("Creating sample data...")
    df = create_sample_data()
    print(f"Created {len(df)} data points")
    
    print("\n" + "="*60)
    print("TESTING AnomalyPipe to_df() FUNCTIONALITY")
    print("="*60)
    
    # Test 1: Statistical outliers
    print("\n1. Testing Statistical Outliers to DataFrame:")
    try:
        outlier_pipe = (AnomalyPipe.from_dataframe(df)
                        | detect_statistical_outliers('value', 'zscore', 2.5))
        
        outlier_df = outlier_pipe.to_df()
        print(f"   ✓ Success! DataFrame shape: {outlier_df.shape}")
        print(f"   Columns: {list(outlier_df.columns)}")
        print(f"   Sample data:")
        print(outlier_df.head(3).to_string())
        
        # Test summary
        summary_df = outlier_pipe.get_anomaly_summary_df()
        print(f"   Summary DataFrame shape: {summary_df.shape}")
        print(f"   Summary data:")
        print(summary_df.to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Contextual anomalies
    print("\n2. Testing Contextual Anomalies to DataFrame:")
    try:
        contextual_pipe = (AnomalyPipe.from_dataframe(df)
                           | detect_contextual_anomalies('value', 'date', 'residual', 'ewm', 2.0, 30))
        
        contextual_df = contextual_pipe.to_df()
        print(f"   ✓ Success! DataFrame shape: {contextual_df.shape}")
        print(f"   Columns: {list(contextual_df.columns)}")
        print(f"   Sample data:")
        print(contextual_df.head(3).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Collective anomalies
    print("\n3. Testing Collective Anomalies to DataFrame:")
    try:
        collective_pipe = (AnomalyPipe.from_dataframe(df)
                          | detect_collective_anomalies('value', 'date', 'isolation_forest', 30, 0.1))
        
        collective_df = collective_pipe.to_df()
        print(f"   ✓ Success! DataFrame shape: {collective_df.shape}")
        print(f"   Columns: {list(collective_df.columns)}")
        print(f"   Sample data:")
        print(collective_df.head(3).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Seasonal residuals
    print("\n4. Testing Seasonal Residuals to DataFrame:")
    try:
        seasonal_pipe = (AnomalyPipe.from_dataframe(df)
                        | calculate_seasonal_residuals('value', 'date', 365, 'additive'))
        
        seasonal_df = seasonal_pipe.to_df()
        print(f"   ✓ Success! DataFrame shape: {seasonal_df.shape}")
        print(f"   Columns: {list(seasonal_df.columns)}")
        print(f"   Sample data:")
        print(seasonal_df.head(3).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 5: With metadata
    print("\n5. Testing with metadata:")
    try:
        outlier_df_with_meta = outlier_pipe.to_df(include_metadata=True)
        print(f"   ✓ Success! DataFrame shape: {outlier_df_with_meta.shape}")
        print(f"   Columns: {list(outlier_df_with_meta.columns)}")
        print(f"   Sample data:")
        print(outlier_df_with_meta.head(2).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 6: Without original data
    print("\n6. Testing without original data:")
    try:
        outlier_df_only_anomalies = outlier_pipe.to_df(include_original=False)
        print(f"   ✓ Success! DataFrame shape: {outlier_df_only_anomalies.shape}")
        print(f"   Columns: {list(outlier_df_only_anomalies.columns)}")
        print(f"   Sample data:")
        print(outlier_df_only_anomalies.head(3).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 7: Get anomaly columns
    print("\n7. Testing get_anomaly_columns():")
    try:
        anomaly_cols = outlier_pipe.get_anomaly_columns()
        print(f"   ✓ Success! Anomaly columns: {anomaly_cols}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "="*60)
    print("TESTING COMPLETED")
    print("="*60)

if __name__ == "__main__":
    test_to_df_functionality() 