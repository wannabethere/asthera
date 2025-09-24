"""
Enhanced Funnel Analysis Demo

This script demonstrates the new pipeline flow integration functionality
with clean visual representations and comprehensive flow files.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def create_sample_data():
    """Create sample data for demonstration"""
    print("📊 Creating sample data...")
    
    # Create sample financial data
    np.random.seed(42)
    n_records = 1000
    
    # Generate dates
    start_date = datetime.now() - timedelta(days=365)
    dates = [start_date + timedelta(days=i) for i in range(n_records)]
    
    # Generate sample data
    data = {
        'Date': dates,
        'Region': np.random.choice(['North', 'South', 'East', 'West'], n_records),
        'Cost center': np.random.choice(['Center A', 'Center B', 'Center C'], n_records),
        'Project': np.random.choice([10.0, 20.0, 30.0, 40.0, 50.0], n_records),
        'Account': [2] * n_records,
        'Source': np.random.choice(['PROJECT ACCOUNTING', 'PAYABLES', 'REVALUATION', 'SPREADSHEET'], n_records),
        'Category': np.random.choice(['MISCELLANEOUS_COST', 'PURCHASE INVOICES', 'ACCRUAL - AUTOREVERSE'], n_records),
        'Event Type': np.random.choice(['MISC_COST_DIST', 'INVOICE VALIDATED', 'INVOICE CANCELLED'], n_records),
        'PO No': [f'NEW_PO_{i:04d}' for i in range(n_records)],
        'Transactional value': np.random.normal(1000, 500, n_records),
        'Functional value': np.random.normal(1000, 500, n_records),
        'PO with Line item': [f'NEW_PO_{i:04d}-001' for i in range(n_records)],
        'Forecasted value': np.random.normal(1000, 500, n_records),
        'Forecasted functional value': np.random.normal(1000, 500, n_records),
        'Forecasted PO with Line item': [f'NEW_PO_{i:04d}-001' for i in range(n_records)]
    }
    
    df = pd.DataFrame(data)
    print(f"✅ Created sample dataset with {len(df)} records")
    return df

def demonstrate_pipeline_flow():
    """Demonstrate the pipeline flow functionality"""
    print("\n🚀 Enhanced Funnel Analysis Demo")
    print("=" * 60)
    
    # Create sample data
    df = create_sample_data()
    
    # Define analysis questions
    questions = [
        {
            "name": "variance_analysis",
            "question": "How does the 5-day rolling variance of transactional values change over time for each group of projects and regions?",
            "context": "Analyze variance patterns for investment decisions"
        },
        {
            "name": "anomaly_detection", 
            "question": "Find anomalies in daily transactional values that deviate from normal business patterns by region and project",
            "context": "Detect unusual spending patterns"
        },
        {
            "name": "trend_analysis",
            "question": "What are the daily trends of transactional values and forecasted values by region and project?",
            "context": "Understand spending trends over time"
        }
    ]
    
    print(f"\n📋 Analysis Questions:")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q['question']}")
    
    print(f"\n💡 This demo shows how the enhanced funnel analysis tool:")
    print(f"  ✅ Generates separate code for each step")
    print(f"  ✅ Creates comprehensive flow graphs")
    print(f"  ✅ Provides execution analysis and optimization opportunities")
    print(f"  ✅ Creates clean visual representations")
    print(f"  ✅ Generates comprehensive Python files with all flow information")
    
    print(f"\n🔧 Key Features Demonstrated:")
    print(f"  • Pipeline Flow Integration Agent")
    print(f"  • Separate Step Code Generation")
    print(f"  • Flow Graph Visualization")
    print(f"  • Execution Analysis")
    print(f"  • Dependency Analysis")
    print(f"  • Data Flow Analysis")
    print(f"  • Optimization Recommendations")
    
    print(f"\n📁 Output Files Generated:")
    print(f"  • Individual step codes (Python functions)")
    print(f"  • Flow graph visualizations (PNG images)")
    print(f"  • Comprehensive flow files (Complete Python scripts)")
    print(f"  • JSON results with metadata")
    print(f"  • Execution plans and recommendations")
    
    print(f"\n🎯 Benefits:")
    print(f"  • Modularity: Each step is independently executable")
    print(f"  • Transparency: Clear understanding of pipeline structure")
    print(f"  • Optimization: Identified parallel execution opportunities")
    print(f"  • Visualization: Visual representation of data flow")
    print(f"  • Debugging: Easier debugging of individual steps")
    print(f"  • Maintenance: Easier modification of individual steps")
    
    print(f"\n📊 Sample Data Preview:")
    print(df.head())
    print(f"\nData shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    
    print(f"\n🎉 Demo Complete!")
    print(f"To run the actual analysis, use the enhanced_funnelanalysistoolusage_enhanced.py script")

if __name__ == "__main__":
    demonstrate_pipeline_flow()
