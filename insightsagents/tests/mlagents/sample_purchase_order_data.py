import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def create_sample_purchase_order_data(num_orders=1000, start_date=None, end_date=None):
    """
    Create a sample purchase order dataset for demonstration
    
    Args:
        num_orders: Number of purchase orders to generate
        start_date: Start date for the data (default: 1 year ago)
        end_date: End date for the data (default: today)
    
    Returns:
        DataFrame with purchase order data
    """
    
    # Set default date range if not provided
    if start_date is None:
        start_date = datetime.now() - timedelta(days=365)
    if end_date is None:
        end_date = datetime.now()
    
    # Define sample data for each field
    projects = [
        'Cloud Migration Initiative',
        'Data Center Expansion',
        'Security Infrastructure Upgrade',
        'Network Modernization',
        'Software Development Platform',
        'AI/ML Infrastructure',
        'Customer Portal Enhancement',
        'Mobile App Development',
        'Database Optimization',
        'DevOps Automation',
        'Business Intelligence Platform',
        'E-commerce Platform',
        'API Gateway Implementation',
        'Microservices Architecture',
        'Legacy System Replacement'
    ]
    
    regions = [
        'North America',
        'Europe',
        'Asia Pacific',
        'Latin America',
        'Middle East',
        'Africa',
        'Australia',
        'Canada',
        'United Kingdom',
        'Germany',
        'France',
        'Japan',
        'India',
        'Brazil',
        'Mexico'
    ]
    
    divisions = [
        'IT Infrastructure',
        'Software Development',
        'Data Science',
        'Cybersecurity',
        'Cloud Services',
        'Digital Transformation',
        'Enterprise Applications',
        'Network Engineering',
        'DevOps',
        'Quality Assurance',
        'Product Management',
        'Business Operations',
        'Customer Success',
        'Research & Development',
        'Platform Engineering'
    ]
    
    # Generate purchase order IDs
    po_ids = [f"PO-{str(i).zfill(6)}" for i in range(1, num_orders + 1)]
    
    # Generate random data
    np.random.seed(42)  # For reproducible results
    
    # Random selection with weights for more realistic distribution
    # Normalize probabilities to sum to exactly 1.0
    def normalize_probs(probs):
        total = sum(probs)
        return [p/total for p in probs]
    
    # Raw probabilities (will be normalized)
    project_probs_raw = [0.15, 0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.05, 0.04, 0.04, 0.03, 0.03, 0.03, 0.02, 0.02]
    region_probs_raw = [0.25, 0.20, 0.18, 0.12, 0.08, 0.06, 0.05, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01]
    division_probs_raw = [0.18, 0.15, 0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.03, 0.02, 0.02, 0.02, 0.01]
    
    # Normalize to sum to 1.0
    project_probs = normalize_probs(project_probs_raw)
    region_probs = normalize_probs(region_probs_raw)
    division_probs = normalize_probs(division_probs_raw)
    
    selected_projects = np.random.choice(projects, num_orders, p=project_probs)
    selected_regions = np.random.choice(regions, num_orders, p=region_probs)
    selected_divisions = np.random.choice(divisions, num_orders, p=division_probs)
    
    # Generate costs with realistic distribution
    # Different cost ranges for different project types
    costs = []
    for project in selected_projects:
        if 'Infrastructure' in project or 'Data Center' in project:
            # High-cost infrastructure projects
            cost = np.random.lognormal(mean=10.5, sigma=0.8) * 1000  # $50K - $500K
        elif 'Security' in project or 'Cloud' in project:
            # Medium-high cost security/cloud projects
            cost = np.random.lognormal(mean=9.8, sigma=0.7) * 1000   # $20K - $200K
        elif 'Development' in project or 'Platform' in project:
            # Medium cost development projects
            cost = np.random.lognormal(mean=9.2, sigma=0.6) * 1000   # $10K - $100K
        else:
            # Lower cost projects
            cost = np.random.lognormal(mean=8.5, sigma=0.5) * 1000   # $5K - $50K
        
        # Add some regional cost variations
        if any(region in ['North America', 'Europe'] for region in [project]):
            cost *= 1.2  # 20% higher in developed regions
        elif any(region in ['Asia Pacific', 'Latin America'] for region in [project]):
            cost *= 0.9  # 10% lower in emerging markets
        
        costs.append(round(cost, 2))
    
    # Generate order dates
    date_range = (end_date - start_date).days
    order_dates = [start_date + timedelta(days=np.random.randint(0, date_range)) for _ in range(num_orders)]
    order_dates.sort()  # Sort by date
    
    # Generate division IDs (numeric IDs for divisions)
    division_id_map = {div: i+1 for i, div in enumerate(divisions)}
    division_ids = [division_id_map[div] for div in selected_divisions]
    
    # Create the DataFrame
    df = pd.DataFrame({
        'purchase_order_id': po_ids,
        'project': selected_projects,
        'region': selected_regions,
        'division_id': division_ids,
        'division_name': selected_divisions,
        'cost': costs,
        'order_date': order_dates,
        'status': np.random.choice(['Approved', 'Pending', 'Completed', 'Cancelled'], num_orders, p=normalize_probs([0.6, 0.2, 0.15, 0.05]))
    })
    
    # Add some derived fields for analysis
    df['year'] = df['order_date'].dt.year
    df['month'] = df['order_date'].dt.month
    df['quarter'] = df['order_date'].dt.quarter
    
    # Add cost categories using a more robust approach
    def categorize_cost(cost):
        if cost < 10000:
            return 'Small (<$10K)'
        elif cost < 50000:
            return 'Medium ($10K-$50K)'
        elif cost < 100000:
            return 'Large ($50K-$100K)'
        elif cost < 500000:
            return 'Very Large ($100K-$500K)'
        else:
            return 'Enterprise (>$500K)'
    
    df['cost_category'] = df['cost'].apply(categorize_cost)
    
    return df

def create_enhanced_purchase_order_data(num_orders=2000):
    """
    Create an enhanced purchase order dataset with additional fields for comprehensive analysis
    
    Args:
        num_orders: Number of purchase orders to generate
    
    Returns:
        DataFrame with enhanced purchase order data
    """
    
    # Get base data
    df = create_sample_purchase_order_data(num_orders)
    
    # Add additional fields for more comprehensive analysis
    
    # Vendor information
    vendors = [
        'Microsoft', 'Amazon Web Services', 'Google Cloud', 'Oracle', 'IBM',
        'Cisco', 'Dell Technologies', 'HP Inc.', 'Lenovo', 'VMware',
        'Salesforce', 'Adobe', 'SAP', 'Workday', 'ServiceNow',
        'Palantir', 'Snowflake', 'Databricks', 'MongoDB', 'Elastic'
    ]
    
    # Normalize probabilities to sum to exactly 1.0
    def normalize_probs(probs):
        total = sum(probs)
        return [p/total for p in probs]
    
    # Vendor probabilities (normalized)
    vendor_probs_raw = [0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.05, 0.05, 0.04, 0.04, 0.03, 0.03, 0.03, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02]
    vendor_probs = normalize_probs(vendor_probs_raw)
    df['vendor'] = np.random.choice(vendors, num_orders, p=vendor_probs)
    
    # Contract types
    contract_types = ['One-time Purchase', 'Annual License', 'Multi-year Contract', 'Subscription', 'Professional Services']
    contract_probs_raw = [0.3, 0.25, 0.2, 0.15, 0.1]
    contract_probs = normalize_probs(contract_probs_raw)
    df['contract_type'] = np.random.choice(contract_types, num_orders, p=contract_probs)
    
    # Payment terms
    payment_terms = ['Net 30', 'Net 60', 'Net 90', 'Immediate', 'Net 45']
    payment_probs_raw = [0.4, 0.25, 0.15, 0.1, 0.1]
    payment_probs = normalize_probs(payment_probs_raw)
    df['payment_terms'] = np.random.choice(payment_terms, num_orders, p=payment_probs)
    
    # Priority levels
    priorities = ['Low', 'Medium', 'High', 'Critical']
    priority_probs_raw = [0.3, 0.4, 0.2, 0.1]
    priority_probs = normalize_probs(priority_probs_raw)
    df['priority'] = np.random.choice(priorities, num_orders, p=priority_probs)
    
    # Approval levels
    approval_levels = ['Manager', 'Director', 'VP', 'C-Level']
    approval_probs_raw = [0.4, 0.3, 0.2, 0.1]
    approval_probs = normalize_probs(approval_probs_raw)
    df['approval_level'] = np.random.choice(approval_levels, num_orders, p=approval_probs)
    
    # Add some realistic correlations using vectorized operations
    # Higher cost projects tend to have higher approval levels
    high_cost_mask = df['cost'] > 100000
    medium_cost_mask = (df['cost'] > 50000) & (df['cost'] <= 100000)
    
    if high_cost_mask.any():
        high_cost_approvals = np.random.choice(['VP', 'C-Level'], size=high_cost_mask.sum(), p=normalize_probs([0.6, 0.4]))
        df.loc[high_cost_mask, 'approval_level'] = high_cost_approvals
    
    if medium_cost_mask.any():
        medium_cost_approvals = np.random.choice(['Director', 'VP'], size=medium_cost_mask.sum(), p=normalize_probs([0.7, 0.3]))
        df.loc[medium_cost_mask, 'approval_level'] = medium_cost_approvals
    
    # Critical projects tend to have shorter payment terms
    critical_mask = df['priority'] == 'Critical'
    if critical_mask.any():
        critical_payment_terms = np.random.choice(['Immediate', 'Net 30'], size=critical_mask.sum(), p=normalize_probs([0.6, 0.4]))
        df.loc[critical_mask, 'payment_terms'] = critical_payment_terms
    
    # Add budget vs actual tracking
    df['budgeted_amount'] = df['cost'] * np.random.uniform(0.8, 1.2, num_orders)
    df['budget_variance'] = df['cost'] - df['budgeted_amount']
    df['budget_variance_pct'] = (df['budget_variance'] / df['budgeted_amount']) * 100
    
    # Add delivery dates
    df['delivery_date'] = df['order_date'] + pd.to_timedelta(np.random.randint(7, 180, num_orders), unit='D')
    
    # Add some projects that are overdue
    overdue_mask = df['delivery_date'] < datetime.now()
    df.loc[overdue_mask, 'status'] = 'Overdue'
    
    # Add forecasted columns
    # Generate forecasted values based on historical patterns and project characteristics
    np.random.seed(42)  # For reproducible results
    
    # Base forecasted value with some variation from actual cost
    df['forecasted_value'] = df['cost'] * np.random.uniform(0.85, 1.25, num_orders)
    
    # Functional forecasted value (considering functional requirements and complexity)
    # Higher for complex projects, lower for simple ones
    complexity_multiplier = np.where(
        df['project'].str.contains('Infrastructure|Security|Cloud|Platform', case=False),
        1.15,  # 15% higher for complex projects
        np.where(
            df['project'].str.contains('Development|Enhancement|Optimization', case=False),
            1.05,  # 5% higher for medium complexity
            0.95   # 5% lower for simple projects
        )
    )
    df['forecasted_functional_value'] = df['forecasted_value'] * complexity_multiplier
    
    # Forecasted PO with line item (detailed breakdown)
    line_items = [
        'Hardware Components',
        'Software Licenses',
        'Professional Services',
        'Training & Support',
        'Maintenance & Updates',
        'Custom Development',
        'Integration Services',
        'Data Migration',
        'Security Implementation',
        'Performance Optimization'
    ]
    
    # Generate line items based on project type and contract
    def generate_line_items(row):
        if 'Infrastructure' in row['project'] or 'Data Center' in row['project']:
            return 'Hardware Components, Software Licenses, Professional Services'
        elif 'Security' in row['project']:
            return 'Security Implementation, Professional Services, Training & Support'
        elif 'Development' in row['project'] or 'Platform' in row['project']:
            return 'Custom Development, Integration Services, Professional Services'
        elif 'Cloud' in row['project']:
            return 'Software Licenses, Integration Services, Data Migration'
        elif 'Optimization' in row['project']:
            return 'Performance Optimization, Professional Services'
        else:
            return 'Professional Services, Training & Support'
    
    df['forecasted_po_with_line_item'] = df.apply(generate_line_items, axis=1)
    
    # Forecasted date (when the project is expected to be completed)
    # Base on order date, delivery date, and project complexity
    base_duration = (df['delivery_date'] - df['order_date']).dt.days
    
    # Add some variation based on project complexity and priority
    complexity_days = np.where(
        df['project'].str.contains('Infrastructure|Security|Cloud|Platform', case=False),
        np.random.randint(30, 90, num_orders),  # Additional 30-90 days for complex projects
        np.where(
            df['project'].str.contains('Development|Enhancement|Optimization', case=False),
            np.random.randint(15, 45, num_orders),  # Additional 15-45 days for medium complexity
            np.random.randint(5, 20, num_orders)   # Additional 5-20 days for simple projects
        )
    )
    
    # Priority affects timeline
    priority_days = np.where(
        df['priority'] == 'Critical',
        -np.random.randint(10, 30, num_orders),  # Reduce timeline for critical projects
        np.where(
            df['priority'] == 'High',
            -np.random.randint(5, 15, num_orders),  # Slightly reduce timeline for high priority
            0  # No change for medium/low priority
        )
    )
    
    total_additional_days = complexity_days + priority_days
    df['forecasted_date'] = df['delivery_date'] + pd.to_timedelta(total_additional_days, unit='D')
    
    # Ensure forecasted dates are reasonable (not in the past for recent orders)
    min_forecast_date = datetime.now() + timedelta(days=7)  # At least 1 week from now
    df.loc[df['forecasted_date'] < min_forecast_date, 'forecasted_date'] = min_forecast_date
    
    return df

def get_purchase_order_schema_info():
    """
    Get schema information for the purchase order dataset
    
    Returns:
        Dictionary with schema, statistics, and sample values
    """
    # Create a sample dataset to extract schema info
    df = create_enhanced_purchase_order_data(1000)
    
    schema_info = {
        'schema': {
            'purchase_order_id': 'object',
            'project': 'object', 
            'region': 'object',
            'division_id': 'int64',
            'division_name': 'object',
            'cost': 'float64',
            'order_date': 'datetime64[ns]',
            'status': 'object',
            'year': 'int64',
            'month': 'int64',
            'quarter': 'int64',
            'cost_category': 'category',
            'vendor': 'object',
            'contract_type': 'object',
            'payment_terms': 'object',
            'priority': 'object',
            'approval_level': 'object',
            'budgeted_amount': 'float64',
            'budget_variance': 'float64',
            'budget_variance_pct': 'float64',
            'delivery_date': 'datetime64[ns]',
            'forecasted_value': 'float64',
            'forecasted_functional_value': 'float64',
            'forecasted_po_with_line_item': 'object',
            'forecasted_date': 'datetime64[ns]'
        },
        'stats': {
            'cost': {
                'count': len(df),
                'mean': df['cost'].mean(),
                'std': df['cost'].std(),
                'min': df['cost'].min(),
                'max': df['cost'].max(),
                'median': df['cost'].median()
            },
            'division_id': {
                'count': len(df),
                'unique': df['division_id'].nunique(),
                'min': df['division_id'].min(),
                'max': df['division_id'].max()
            },
            'year': {
                'count': len(df),
                'unique': df['year'].nunique(),
                'min': df['year'].min(),
                'max': df['year'].max()
            }
        },
        'sample_values': {
            'project': df['project'].unique()[:5].tolist(),
            'region': df['region'].unique()[:5].tolist(),
            'division_name': df['division_name'].unique()[:5].tolist(),
            'status': df['status'].unique().tolist(),
            'vendor': df['vendor'].unique()[:5].tolist(),
            'contract_type': df['contract_type'].unique().tolist(),
            'priority': df['priority'].unique().tolist()
        },
        'summary': 'Purchase order data with project, region, cost, and division information for procurement analysis'
    }
    
    return schema_info

def demonstrate_purchase_order_analysis():
    """
    Demonstrate the purchase order dataset and its analysis capabilities
    """
    print("🛒 PURCHASE ORDER DATA DEMONSTRATION")
    print("=" * 60)
    
    # Create sample data
    df = create_enhanced_purchase_order_data(1000)
    
    print(f"📊 Dataset Overview:")
    print(f"   Total Purchase Orders: {len(df):,}")
    print(f"   Date Range: {df['order_date'].min().strftime('%Y-%m-%d')} to {df['order_date'].max().strftime('%Y-%m-%d')}")
    print(f"   Total Cost: ${df['cost'].sum():,.2f}")
    print(f"   Average Cost: ${df['cost'].mean():,.2f}")
    
    print(f"\n🏢 Division Analysis:")
    division_summary = df.groupby('division_name').agg(
        order_count=('cost', 'count'),
        total_cost=('cost', 'sum'),
        avg_cost=('cost', 'mean')
    ).round(2)
    print(division_summary.head())
    
    print(f"\n🌍 Regional Analysis:")
    region_summary = df.groupby('region').agg(
        order_count=('cost', 'count'),
        total_cost=('cost', 'sum'),
        avg_cost=('cost', 'mean')
    ).round(2)
    print(region_summary.head())
    
    print(f"\n📈 Cost Category Distribution:")
    cost_cat_summary = df['cost_category'].value_counts()
    print(cost_cat_summary)
    
    print(f"\n💰 Budget Performance:")
    budget_summary = df.groupby('priority').agg(
        avg_variance_pct=('budget_variance_pct', 'mean'),
        std_variance_pct=('budget_variance_pct', 'std'),
        count=('budget_variance_pct', 'count')
    ).round(2)
    print(budget_summary)
    
    print(f"\n✅ Status Distribution:")
    status_summary = df['status'].value_counts()
    print(status_summary)
    
    print(f"\n🔮 Forecasted Values Analysis:")
    forecast_summary = df.agg({
        'forecasted_value': ['mean', 'std', 'min', 'max'],
        'forecasted_functional_value': ['mean', 'std', 'min', 'max']
    }).round(2)
    print(forecast_summary)
    
    print(f"\n📊 Forecast vs Actual Cost Comparison:")
    df['forecast_variance'] = df['forecasted_value'] - df['cost']
    df['forecast_variance_pct'] = (df['forecast_variance'] / df['cost']) * 100
    forecast_variance_summary = df.groupby('priority').agg({
        'forecast_variance_pct': ['mean', 'std', 'count']
    }).round(2)
    print(forecast_variance_summary)
    
    print(f"\n📋 Sample Line Items:")
    line_item_counts = df['forecasted_po_with_line_item'].value_counts().head(5)
    print(line_item_counts)
    
    print(f"\n📅 Forecasted Timeline Analysis:")
    df['forecast_duration_days'] = (df['forecasted_date'] - df['order_date']).dt.days
    timeline_summary = df.groupby('priority').agg({
        'forecast_duration_days': ['mean', 'std', 'min', 'max']
    }).round(0)
    print(timeline_summary)
    
    return df

if __name__ == "__main__":
    # Run the demonstration
    df = demonstrate_purchase_order_analysis()
    
    print(f"\n🎯 Sample Data Preview:")
    print(df.head(10))
    
    print(f"\n📋 Available Columns for Analysis:")
    print(df.columns.tolist()) 