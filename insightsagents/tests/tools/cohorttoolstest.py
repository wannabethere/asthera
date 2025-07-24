import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.tools.mltools.cohortanalysistools import (
    CohortPipe,
    form_time_cohorts,
    form_behavioral_cohorts,
    form_acquisition_cohorts,
    calculate_retention,
    calculate_conversion,
    calculate_lifetime_value
)

# Example of using the composable cohort analysis tool on e-commerce user data

def main():
    # Step 1: Load data
    events_df, transactions_df = load_sample_data()
    print(f"Loaded {len(events_df)} events and {len(transactions_df)} transactions")
    
    # Step 2: Run various cohort analyses
    
    # Example 1: Time-based cohort retention analysis
    print("\n=== TIME-BASED COHORT RETENTION ANALYSIS ===")
    retention_results = analyze_retention(events_df)
    print("retention_results",retention_results['cohort_sizes'].to_dict().items())
    print_retention_matrix(retention_results)
    
    # Example 2: User conversion funnel by acquisition source
    print("\n=== CONVERSION FUNNEL ANALYSIS BY ACQUISITION SOURCE ===")
    funnel_results = analyze_conversion_funnel(events_df)
    print_funnel_results(funnel_results)
    
    # Example 3: Lifetime value analysis by customer segment
    print("\n=== LIFETIME VALUE ANALYSIS BY CUSTOMER SEGMENT ===")
    ltv_results = analyze_lifetime_value(events_df, transactions_df)
    print_ltv_results(ltv_results)
    
    # Test the new to_df() functionality
    print("\n=== TESTING to_df() FUNCTIONALITY ===")
    test_results = test_to_df_functionality(events_df, transactions_df)
    
    return {
        'retention': retention_results,
        'funnel': funnel_results,
        'ltv': ltv_results,
        'test_results': test_results
    }


def load_sample_data(n_users=1000, days=180):
    """Generate synthetic e-commerce user data"""
    np.random.seed(42)
    
    # Generate user data
    users = []
    for user_id in range(1, n_users + 1):
        # Random acquisition date within the last 6 months
        acquisition_date = datetime.now() - timedelta(days=np.random.randint(1, days))
        
        # Assign random acquisition source with weighted distribution
        acquisition_sources = ['organic_search', 'paid_search', 'social_media', 'referral', 'direct', 'email']
        acquisition_weights = [0.3, 0.25, 0.2, 0.1, 0.1, 0.05]
        acquisition_source = np.random.choice(acquisition_sources, p=acquisition_weights)
        
        # Assign customer value segment based on spending patterns
        value_segments = ['high', 'medium', 'low']
        value_weights = [0.2, 0.5, 0.3]
        value_segment = np.random.choice(value_segments, p=value_weights)
        
        # Set average order value based on segment
        if value_segment == 'high':
            avg_order_value = np.random.normal(150, 30)
        elif value_segment == 'medium':
            avg_order_value = np.random.normal(75, 15)
        else:
            avg_order_value = np.random.normal(35, 10)
        
        users.append({
            'user_id': f'user_{user_id}',
            'acquisition_date': acquisition_date,
            'acquisition_source': acquisition_source,
            'value_segment': value_segment,
            'avg_order_value': max(10, avg_order_value)  # Minimum $10 order
        })
    
    users_df = pd.DataFrame(users)
    
    # Generate events data
    events = []
    conversion_funnel = [
        'view_homepage', 
        'search_product', 
        'view_product', 
        'add_to_cart', 
        'begin_checkout', 
        'complete_purchase'
    ]
    
    # Dropout rates at each step of the funnel (higher number = more dropout)
    dropout_rates = {
        'high': [0.05, 0.1, 0.15, 0.2, 0.1],     # High-value customers drop out less
        'medium': [0.1, 0.2, 0.25, 0.3, 0.15],   # Medium-value customers 
        'low': [0.2, 0.3, 0.4, 0.5, 0.3]         # Low-value customers drop out more
    }
    
    # Generate events for each user
    for user in users:
        user_id = user['user_id']
        acquisition_date = user['acquisition_date']
        value_segment = user['value_segment']
        
        # Determine how many times this user will visit the site (more for high-value)
        if value_segment == 'high':
            n_visits = np.random.poisson(8)
        elif value_segment == 'medium':
            n_visits = np.random.poisson(5)
        else:
            n_visits = np.random.poisson(3)
        
        n_visits = max(1, n_visits)  # At least 1 visit
        
        # Generate events for each visit
        for visit in range(n_visits):
            # Visit date is after acquisition, weighted toward more recent dates
            days_since_acquisition = (datetime.now() - acquisition_date).days
            days_after = np.random.exponential(scale=30)
            days_after = min(days_after, days_since_acquisition)
            visit_date = acquisition_date + timedelta(days=int(days_after))
            
            # Go through the funnel, with dropout chances at each step
            for i, event in enumerate(conversion_funnel):
                events.append({
                    'user_id': user_id,
                    'event_date': visit_date,
                    'event': event,
                    'acquisition_source': user['acquisition_source'],
                    'value_segment': value_segment
                })
                
                # Check if user drops out at this step
                if i < len(conversion_funnel) - 1:  # Not the last step
                    dropout_rate = dropout_rates[value_segment][i]
                    if np.random.random() < dropout_rate:
                        break
    
    events_df = pd.DataFrame(events)
    
    # Generate transactions data (based on completed purchases)
    purchases = events_df[events_df['event'] == 'complete_purchase']
    
    transactions = []
    for _, purchase in purchases.iterrows():
        user_id = purchase['user_id']
        user_info = users_df[users_df['user_id'] == user_id].iloc[0]
        
        # Add some random variation to the user's average order value
        order_value = user_info['avg_order_value'] * np.random.uniform(0.8, 1.2)
        
        transactions.append({
            'transaction_id': f"tx_{len(transactions) + 1}",
            'user_id': user_id,
            'transaction_date': purchase['event_date'],
            'amount': order_value,
            'acquisition_source': purchase['acquisition_source'],
            'value_segment': purchase['value_segment']
        })
    
    transactions_df = pd.DataFrame(transactions)
    
    return events_df, transactions_df


def analyze_retention(events_df):
    """Analyze user retention by month cohorts"""
    # Use the pipeline pattern to analyze retention
    result = (CohortPipe.from_dataframe(events_df)
              # Form monthly cohorts based on first event date
              | form_time_cohorts(
                  date_column='event_date',
                  cohort_column='cohort',
                  time_period='M'
              )
              # Calculate classic retention (users who return in each specific period)
              | calculate_retention(
                  cohort_column='cohort',
                  date_column='event_date',
                  user_id_column='user_id',
                  time_period='M',
                  max_periods=6,
                  retention_type='classic'
              )
    )
    
    return result.cohort_results['time_cohorts_retention']


def analyze_conversion_funnel(events_df):
    """Analyze conversion funnel by acquisition source"""
    # Define the funnel steps
    funnel_steps = [
        'view_homepage', 
        'search_product', 
        'view_product', 
        'add_to_cart', 
        'begin_checkout', 
        'complete_purchase'
    ]
    
    # Friendly step names
    step_names = [
        'Homepage View',
        'Product Search',
        'Product View',
        'Add to Cart',
        'Checkout',
        'Purchase'
    ]
    
    # Use the pipeline pattern to analyze conversion funnel
    result = (CohortPipe.from_dataframe(events_df)
              # Form cohorts based on acquisition source
              | form_behavioral_cohorts(
                  behavior_column='acquisition_source',
                  cohort_column='acquisition_source_cohort'
              )
              # Calculate conversion funnel
              | calculate_conversion(
                  cohort_column='acquisition_source_cohort',
                  event_column='event',
                  user_id_column='user_id',
                  funnel_steps=funnel_steps,
                  step_names=step_names,
                  include_rates=True,
                  cumulative=True
              )
    )
    
    return result.cohort_results['behavioral_cohorts_conversion']


def analyze_lifetime_value(events_df, transactions_df):
    """Analyze customer lifetime value by customer segment"""
    # Use the pipeline pattern to analyze LTV
    result = (CohortPipe.from_dataframe(transactions_df)
              # Form cohorts based on value segment
              | form_behavioral_cohorts(
                  behavior_column='value_segment',
                  cohort_column='value_segment_cohort'
              )
              # Calculate LTV
              | calculate_lifetime_value(
                  cohort_column='value_segment_cohort',
                  date_column='transaction_date',
                  user_id_column='user_id',
                  value_column='amount',
                  time_period='M',
                  max_periods=6,
                  cumulative=True
              )
    )
    
    return result.cohort_results['behavioral_cohorts_ltv']


def print_retention_matrix(retention_results):
    """Print retention matrix in a readable format"""
    print("\nRetention Matrix (% of users who return in each period):")
    retention_matrix = retention_results['retention_matrix']
    
    # Format as percentages
    formatted_matrix = retention_matrix.applymap(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "-")
    print(formatted_matrix)
    
    # Print cohort sizes
    print("\nCohort Sizes (unique users):")
    for cohort, size in retention_results['cohort_sizes'].to_dict().items():
        print(f"  {cohort}: {size} users")


def print_funnel_results(funnel_results):
    """Print conversion funnel results in a readable format"""
    funnel_data = funnel_results['funnel_data']
    step_names = funnel_results['step_names']
    
    print("\nConversion Funnel by Acquisition Source:")
    for _, row in funnel_data.iterrows():
        cohort = row['cohort']
        print(f"\n{cohort.replace('_', ' ').title()}:")
        
        # Print user counts at each step
        print("  User counts:")
        for step in step_names:
            count = row[f"{step}_count"]
            print(f"    {step}: {int(count)} users")
        
        # Print conversion rates
        print("  Conversion rates (from first step):")
        for i, step in enumerate(step_names):
            if i > 0:  # Skip first step
                rate = row.get(f"{step}_rate", 0)
                print(f"    {step}: {rate*100:.1f}%")


def print_ltv_results(ltv_results):
    """Print LTV results in a readable format"""
    ltv_matrix = ltv_results['ltv_matrix']
    cohort_sizes = ltv_results['cohort_sizes']
    
    print("\nCumulative Average LTV by Customer Segment:")
    
    # Format as currency
    formatted_matrix = ltv_matrix.applymap(lambda x: f"${x:.2f}" if pd.notnull(x) else "-")
    print(formatted_matrix)
    
    # Print cohort sizes
    print("\nSegment Sizes (unique users):")
    for cohort, size in zip(cohort_sizes[ltv_results['cohort_column']], cohort_sizes['cohort_size']):
        print(f"  {cohort}: {size} users")


def test_to_df_functionality(events_df, transactions_df):
    """Test the new to_df() method functionality"""
    print("\nTesting to_df() method for different analysis types:")
    
    # Test 1: Retention analysis to DataFrame
    print("\n1. Retention Analysis to DataFrame:")
    retention_pipe = (CohortPipe.from_dataframe(events_df)
                      | form_time_cohorts('event_date', 'cohort', 'M')
                      | calculate_retention('cohort', 'event_date', 'user_id', 'M', 6, 'classic'))
    
    retention_df = retention_pipe.to_df()
    print(f"   Retention DataFrame shape: {retention_df.shape}")
    print(f"   Columns: {list(retention_df.columns)}")
    print(f"   Sample data:")
    print(retention_df.head(3))
    
    # Test 2: Conversion analysis to DataFrame
    print("\n2. Conversion Analysis to DataFrame:")
    conversion_pipe = (CohortPipe.from_dataframe(events_df)
                       | form_behavioral_cohorts('acquisition_source', 'acquisition_source_cohort')
                       | calculate_conversion('acquisition_source_cohort', 'event', 'user_id', 
                                            ['view_homepage', 'search_product', 'view_product', 'add_to_cart', 'begin_checkout', 'complete_purchase'],
                                            ['Homepage View', 'Product Search', 'Product View', 'Add to Cart', 'Checkout', 'Purchase']))
    
    conversion_df = conversion_pipe.to_df()
    print(f"   Conversion DataFrame shape: {conversion_df.shape}")
    print(f"   Columns: {list(conversion_df.columns)}")
    print(f"   Sample data:")
    print(conversion_df.head(3))
    
    # Test 3: LTV analysis to DataFrame
    print("\n3. LTV Analysis to DataFrame:")
    ltv_pipe = (CohortPipe.from_dataframe(transactions_df)
                | form_behavioral_cohorts('value_segment', 'value_segment_cohort')
                | calculate_lifetime_value('value_segment_cohort', 'transaction_date', 'user_id', 'amount', 'M', 6, True))
    
    ltv_df = ltv_pipe.to_df()
    print(f"   LTV DataFrame shape: {ltv_df.shape}")
    print(f"   Columns: {list(ltv_df.columns)}")
    print(f"   Sample data:")
    print(ltv_df.head(3))
    
    # Test 4: With metadata
    print("\n4. Retention Analysis to DataFrame with metadata:")
    retention_df_with_meta = retention_pipe.to_df(include_metadata=True)
    print(f"   Retention DataFrame with metadata shape: {retention_df_with_meta.shape}")
    print(f"   Columns: {list(retention_df_with_meta.columns)}")
    print(f"   Sample data:")
    print(retention_df_with_meta.head(2))
    
    # Test 5: Specific analysis name
    print("\n5. Specific analysis name:")
    retention_df_specific = retention_pipe.to_df(analysis_name='time_cohorts_retention')
    print(f"   Specific analysis DataFrame shape: {retention_df_specific.shape}")
    
    return {
        'retention_df': retention_df,
        'conversion_df': conversion_df,
        'ltv_df': ltv_df,
        'retention_df_with_meta': retention_df_with_meta
    }

if __name__ == "__main__":
    results = main()
    
    # Example of how the results could be used for business decisions
    print("\n=== BUSINESS APPLICATIONS OF COHORT ANALYSIS ===")
    
    # Retention insights
    retention_matrix = results['retention']['retention_matrix']
    print("\n1. Retention Insights:")
    latest_cohort = retention_matrix.index[-1]
    first_month_retention = retention_matrix.loc[latest_cohort, 'Period 1']
    print(f"   Latest cohort ({latest_cohort}) has {first_month_retention*100:.1f}% month 1 retention")
    print("   → Action: Focus on improving onboarding for new users to increase retention")
    
    # Funnel insights
    funnel_data = results['funnel']['funnel_data']
    print("\n2. Conversion Funnel Insights:")
    for source in funnel_data['cohort'].unique():
        source_data = funnel_data[funnel_data['cohort'] == source]
        cart_to_purchase = source_data['Purchase_rate'].values[0] / source_data['Add to Cart_rate'].values[0]
        print(f"   {source.title()}: {cart_to_purchase*100:.1f}% of users who add to cart complete purchase")
    print("   → Action: Improve checkout process for users from social_media")
    
    # LTV insights
    ltv_matrix = results['ltv']['ltv_matrix']
    print("\n3. Lifetime Value Insights:")
    for segment in ltv_matrix.index:
        six_month_ltv = ltv_matrix.loc[segment, 'Period 6'] if 'Period 6' in ltv_matrix.columns else ltv_matrix.iloc[0, -1]
        print(f"   {segment.title()} segment 6-month LTV: ${six_month_ltv:.2f}")
    print("   → Action: Increase marketing spend on acquiring high-value customers")


