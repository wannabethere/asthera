#!/usr/bin/env python3
"""
Simple test script to verify the to_df() functionality of CohortPipe
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.tools.mltools.cohortanalysistools import (
    CohortPipe,
    form_time_cohorts,
    form_behavioral_cohorts,
    calculate_retention,
    calculate_conversion,
    calculate_lifetime_value
)

def create_sample_data():
    """Create a small sample dataset for testing"""
    np.random.seed(42)
    
    # Create simple user data
    users = []
    for i in range(1, 21):  # 20 users
        acquisition_date = datetime.now() - timedelta(days=np.random.randint(1, 60))
        users.append({
            'user_id': f'user_{i}',
            'acquisition_date': acquisition_date,
            'acquisition_source': np.random.choice(['organic', 'paid', 'social']),
            'value_segment': np.random.choice(['high', 'medium', 'low'])
        })
    
    users_df = pd.DataFrame(users)
    
    # Create events data
    events = []
    for user in users:
        user_id = user['user_id']
        acquisition_date = user['acquisition_date']
        
        # Generate 2-5 events per user
        n_events = np.random.randint(2, 6)
        for j in range(n_events):
            event_date = acquisition_date + timedelta(days=np.random.randint(1, 30))
            event_type = np.random.choice(['view_homepage', 'search_product', 'view_product', 'add_to_cart', 'begin_checkout', 'complete_purchase'])
            
            events.append({
                'user_id': user_id,
                'event_date': event_date,
                'event': event_type,
                'acquisition_source': user['acquisition_source'],
                'value_segment': user['value_segment']
            })
    
    events_df = pd.DataFrame(events)
    
    # Create transactions data
    transactions = []
    for user in users:
        user_id = user['user_id']
        acquisition_date = user['acquisition_date']
        
        # Generate 1-3 transactions per user
        n_transactions = np.random.randint(1, 4)
        for j in range(n_transactions):
            transaction_date = acquisition_date + timedelta(days=np.random.randint(1, 30))
            amount = np.random.uniform(10, 200)
            
            transactions.append({
                'user_id': user_id,
                'transaction_date': transaction_date,
                'amount': amount,
                'acquisition_source': user['acquisition_source'],
                'value_segment': user['value_segment']
            })
    
    transactions_df = pd.DataFrame(transactions)
    
    return events_df, transactions_df

def test_to_df_functionality():
    """Test the to_df() method with different analysis types"""
    print("Creating sample data...")
    events_df, transactions_df = create_sample_data()
    print(f"Created {len(events_df)} events and {len(transactions_df)} transactions")
    
    print("\n" + "="*50)
    print("TESTING to_df() FUNCTIONALITY")
    print("="*50)
    
    # Test 1: Retention analysis
    print("\n1. Testing Retention Analysis to DataFrame:")
    try:
        retention_pipe = (CohortPipe.from_dataframe(events_df)
                          | form_time_cohorts('event_date', 'cohort', 'M')
                          | calculate_retention('cohort', 'event_date', 'user_id', 'M', 3, 'classic'))
        
        retention_df = retention_pipe.to_df()
        print(f"   ✓ Success! DataFrame shape: {retention_df.shape}")
        print(f"   Columns: {list(retention_df.columns)}")
        print(f"   Sample data:")
        print(retention_df.head(3).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Conversion analysis
    print("\n2. Testing Conversion Analysis to DataFrame:")
    try:
        conversion_pipe = (CohortPipe.from_dataframe(events_df)
                           | form_behavioral_cohorts('acquisition_source', 'acquisition_source_cohort')
                           | calculate_conversion('acquisition_source_cohort', 'event', 'user_id', 
                                                ['view_homepage', 'search_product', 'view_product', 'add_to_cart', 'begin_checkout', 'complete_purchase']))
        
        conversion_df = conversion_pipe.to_df()
        print(f"   ✓ Success! DataFrame shape: {conversion_df.shape}")
        print(f"   Columns: {list(conversion_df.columns)}")
        print(f"   Sample data:")
        print(conversion_df.head(3).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: LTV analysis
    print("\n3. Testing LTV Analysis to DataFrame:")
    try:
        ltv_pipe = (CohortPipe.from_dataframe(transactions_df)
                    | form_behavioral_cohorts('value_segment', 'value_segment_cohort')
                    | calculate_lifetime_value('value_segment_cohort', 'transaction_date', 'user_id', 'amount', 'M', 3, True))
        
        ltv_df = ltv_pipe.to_df()
        print(f"   ✓ Success! DataFrame shape: {ltv_df.shape}")
        print(f"   Columns: {list(ltv_df.columns)}")
        print(f"   Sample data:")
        print(ltv_df.head(3).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: With metadata
    print("\n4. Testing with metadata:")
    try:
        retention_df_with_meta = retention_pipe.to_df(include_metadata=True)
        print(f"   ✓ Success! DataFrame shape: {retention_df_with_meta.shape}")
        print(f"   Columns: {list(retention_df_with_meta.columns)}")
        print(f"   Sample data:")
        print(retention_df_with_meta.head(2).to_string())
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 5: Specific analysis name
    print("\n5. Testing specific analysis name:")
    try:
        retention_df_specific = retention_pipe.to_df(analysis_name='behavioral_cohorts_retention')
        print(f"   ✓ Success! DataFrame shape: {retention_df_specific.shape}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "="*50)
    print("TESTING COMPLETED")
    print("="*50)

if __name__ == "__main__":
    test_to_df_functionality() 