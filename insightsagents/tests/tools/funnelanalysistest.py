import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.tools.mltools.funnelanalysis import (
    analyze_funnel,
    analyze_funnel_by_time,
    analyze_funnel_by_segment,
    analyze_user_paths,
    get_funnel_summary,
    compare_segments
)
from app.tools.mltools.cohortanalysistools import CohortPipe

# Example of using the integrated funnel analysis with the cohort framework

def main():
    # Step 1: Load data
    events_df = load_sample_data()
    print(f"Loaded {len(events_df)} events for analysis")
    
    # Define the funnel steps to analyze
    funnel_steps = [
        'view_product', 
        'add_to_cart', 
        'begin_checkout', 
        'enter_payment', 
        'complete_purchase'
    ]
    
    # Use friendly step names
    step_names = [
        'Product View',
        'Add to Cart',
        'Begin Checkout',
        'Enter Payment',
        'Purchase'
    ]
    
    # Step 2: Perform funnel analyses
    
    # Example 1: Overall funnel analysis
    print("\n=== OVERALL FUNNEL ANALYSIS ===")
    overall_funnel = analyze_overall_funnel(events_df, funnel_steps, step_names)
    print_overall_funnel(overall_funnel)
    
    # Example 2: Funnel analysis by time periods
    print("\n=== FUNNEL ANALYSIS BY TIME PERIOD ===")
    time_funnel = analyze_funnel_by_time_periods(events_df, funnel_steps, step_names)
    print_time_funnel(time_funnel)
    
    # Example 3: Funnel analysis by user segments
    print("\n=== FUNNEL ANALYSIS BY USER SEGMENT ===")
    segment_funnel = analyze_funnel_by_user_segments(events_df, funnel_steps, step_names)
    print_segment_funnel(segment_funnel)
    
    # Example 4: Analyze common user paths
    print("\n=== USER PATH ANALYSIS ===")
    path_analysis = analyze_common_paths(events_df, funnel_steps, step_names)
    print_path_analysis(path_analysis)
    
    # Example 5: Compare segments
    print("\n=== SEGMENT COMPARISON ===")
    segment_comparison = compare_funnel_segments(events_df, funnel_steps, step_names)
    print_segment_comparison(segment_comparison)
    
    return {
        'overall': overall_funnel,
        'time': time_funnel,
        'segment': segment_funnel,
        'paths': path_analysis,
        'comparison': segment_comparison
    }


def load_sample_data(n_users=1000, days=90):
    """Generate synthetic e-commerce user event data"""
    np.random.seed(42)
    
    # Create list to store events
    events = []
    
    # Define possible user segments and their probabilities
    user_segments = {
        'new_visitor': 0.4,
        'returning_visitor': 0.3,
        'loyal_customer': 0.2,
        'high_value': 0.1
    }
    
    # Define event sequence with typical conversion rates
    funnel_steps = [
        'view_product', 
        'add_to_cart', 
        'begin_checkout', 
        'enter_payment', 
        'complete_purchase'
    ]
    
    # Define dropout probabilities at each step by segment
    # Format: {segment: [probability of dropping out at each step]}
    dropout_probs = {
        'new_visitor':      [0.60, 0.50, 0.40, 0.30],  # Higher dropout for new visitors
        'returning_visitor':[0.50, 0.40, 0.30, 0.20],  # Medium dropout for returning visitors
        'loyal_customer':   [0.30, 0.25, 0.20, 0.10],  # Lower dropout for loyal customers
        'high_value':       [0.20, 0.15, 0.10, 0.05]   # Lowest dropout for high-value customers
    }
    
    # Define possible devices and their probabilities
    devices = {
        'mobile': 0.6,
        'desktop': 0.3,
        'tablet': 0.1
    }
    
    # Generate users
    user_ids = [f"user_{i+1}" for i in range(n_users)]
    
    # Assign segments to users
    user_segment_map = {}
    user_device_map = {}
    
    for user_id in user_ids:
        # Assign segment based on probabilities
        segment = np.random.choice(
            list(user_segments.keys()), 
            p=list(user_segments.values())
        )
        user_segment_map[user_id] = segment
        
        # Assign primary device based on probabilities
        device = np.random.choice(
            list(devices.keys()), 
            p=list(devices.values())
        )
        user_device_map[user_id] = device
    
    # Generate events for each user
    for user_id in user_ids:
        segment = user_segment_map[user_id]
        device = user_device_map[user_id]
        
        # Determine number of sessions for this user (more for loyal/high-value)
        if segment in ['loyal_customer', 'high_value']:
            n_sessions = np.random.randint(3, 10)
        elif segment == 'returning_visitor':
            n_sessions = np.random.randint(2, 5)
        else:
            n_sessions = np.random.randint(1, 3)
        
        # Generate sessions for this user
        for session in range(n_sessions):
            # Generate session timestamp (more recent = more likely)
            days_ago = np.random.exponential(scale=days/3)
            days_ago = min(days_ago, days)
            session_time = datetime.now() - timedelta(days=days_ago)
            
            # Start at the first step
            current_step = 0
            
            # Generate events for each step in the funnel
            while current_step < len(funnel_steps):
                step = funnel_steps[current_step]
                
                # Generate timestamp with small increment for each step
                event_time = session_time + timedelta(minutes=current_step*5 + np.random.randint(1, 5))
                
                # Record this event
                events.append({
                    'user_id': user_id,
                    'event': step,
                    'timestamp': event_time,
                    'segment': segment,
                    'device': device,
                    'session_id': f"{user_id}_{session}"
                })
                
                # Check if user drops out at this step
                if current_step < len(funnel_steps) - 1:
                    dropout_prob = dropout_probs[segment][current_step]
                    
                    # Adjust dropout probability based on device (mobile has higher dropout)
                    if device == 'mobile':
                        dropout_prob *= 1.2
                    elif device == 'desktop':
                        dropout_prob *= 0.8
                    
                    # Ensure probability is between 0 and 1
                    dropout_prob = min(max(dropout_prob, 0), 1)
                    
                    if np.random.random() < dropout_prob:
                        break  # User drops out
                
                current_step += 1
    
    # Convert to DataFrame
    events_df = pd.DataFrame(events)
    
    return events_df


def analyze_overall_funnel(events_df, funnel_steps, step_names):
    """Analyze the overall funnel conversion"""
    result = (CohortPipe.from_dataframe(events_df)
              | analyze_funnel(
                  event_column='event',
                  user_id_column='user_id',
                  funnel_steps=funnel_steps,
                  step_names=step_names
              )
              | get_funnel_summary()
    )
    
    return result['overall_funnel']


def analyze_funnel_by_time_periods(events_df, funnel_steps, step_names):
    """Analyze funnel conversion across different time periods"""
    result = (CohortPipe.from_dataframe(events_df)
              | analyze_funnel_by_time(
                  event_column='event',
                  user_id_column='user_id',
                  date_column='timestamp',
                  funnel_steps=funnel_steps,
                  step_names=step_names,
                  time_period='M'  # Monthly periods
              )
              | get_funnel_summary()
    )
    
    return result['time_funnel']


def analyze_funnel_by_user_segments(events_df, funnel_steps, step_names):
    """Analyze funnel conversion across different user segments"""
    result = (CohortPipe.from_dataframe(events_df)
              | analyze_funnel_by_segment(
                  event_column='event',
                  user_id_column='user_id',
                  segment_column='segment',
                  funnel_steps=funnel_steps,
                  step_names=step_names
              )
              | get_funnel_summary()
    )
    
    return result['segment_funnel']


def analyze_common_paths(events_df, funnel_steps, step_names):
    """Analyze common user paths through the funnel"""
    result = (CohortPipe.from_dataframe(events_df)
              | analyze_user_paths(
                  event_column='event',
                  user_id_column='user_id',
                  timestamp_column='timestamp',
                  funnel_steps=funnel_steps,
                  step_names=step_names,
                  max_path_length=10,
                  min_path_frequency=5
              )
              | get_funnel_summary()
    )
    
    return result['user_paths']


def compare_funnel_segments(events_df, funnel_steps, step_names):
    """Compare funnel metrics across segments"""
    # First run the segment analysis
    pipe = (CohortPipe.from_dataframe(events_df)
            | analyze_funnel_by_segment(
                event_column='event',
                user_id_column='user_id',
                segment_column='segment',
                funnel_steps=funnel_steps,
                step_names=step_names
            )
    )
    
    # Get all available segments from the data
    available_segments = events_df['segment'].unique()
    
    # Choose a baseline segment (first segment if 'returning_visitor' doesn't exist)
    baseline_segment = 'returning_visitor'
    if baseline_segment not in available_segments and len(available_segments) > 0:
        baseline_segment = available_segments[0]
        print(f"Note: Using '{baseline_segment}' as baseline segment instead of 'returning_visitor'")
    
    # Then run the comparison on the Purchase step
    try:
        comparison = compare_segments(
            metric_column='Purchase_rate',
            baseline_segment=baseline_segment
        )(pipe)
        return comparison
    except ValueError as e:
        # Handle case where the segment isn't found or Purchase_rate column doesn't exist
        print(f"Warning: Could not compare segments: {str(e)}")
        print("Returning empty comparison dataframe instead")
        return pd.DataFrame()


def print_overall_funnel(funnel_df):
    """Print overall funnel results in a readable format"""
    print("\nOverall Funnel Conversion:")
    print("--------------------------")
    
    # Format as a table
    for _, row in funnel_df.iterrows():
        step = row['step']
        count = row['count']
        rate = row['conversion_rate']
        cum_rate = row['cumulative_rate']
        
        if rate == 1.0:  # First step
            print(f"{step}: {count:,} users (100%)")
        else:
            prev_count = funnel_df.iloc[funnel_df.index[funnel_df['step'] == step].values[0] - 1]['count']
            print(f"{step}: {count:,} users ({rate*100:.1f}% from previous step, {cum_rate*100:.1f}% from first step)")
            print(f"  Dropoff: {prev_count - count:,} users ({(1-rate)*100:.1f}%)")
    
    # Calculate overall conversion rate
    first_step = funnel_df.iloc[0]['count']
    last_step = funnel_df.iloc[-1]['count']
    overall_rate = last_step / first_step
    
    print(f"\nOverall conversion: {overall_rate*100:.2f}% ({last_step:,}/{first_step:,} users)")


def print_time_funnel(funnel_df):
    """Print time-based funnel results in a readable format"""
    print("\nFunnel Conversion by Time Period:")
    print("--------------------------------")
    
    # Show conversion rates for the last step by time period
    purchase_cols = [col for col in funnel_df.columns if 'Purchase_overall_rate' in col]
    
    if purchase_cols:
        # Get the overall purchase conversion rate column
        purchase_col = purchase_cols[0]
        
        # Sort by time period (typically will be chronological)
        sorted_df = funnel_df.sort_values('cohort')
        
        for _, row in sorted_df.iterrows():
            period = row['cohort']
            rate = row[purchase_col]
            first_step_count = row['Product View_count']
            last_step_count = row['Purchase_count']
            
            print(f"{period}: {rate*100:.2f}% overall conversion ({last_step_count:,}/{first_step_count:,} users)")
        
        # Show trend
        if len(sorted_df) > 1:
            first_period = sorted_df.iloc[0]['cohort']
            first_rate = sorted_df.iloc[0][purchase_col]
            last_period = sorted_df.iloc[-1]['cohort']
            last_rate = sorted_df.iloc[-1][purchase_col]
            
            if last_rate > first_rate:
                change = (last_rate / first_rate - 1) * 100
                print(f"\nPositive trend: Conversion increased by {change:.1f}% from {first_period} to {last_period}")
            elif last_rate < first_rate:
                change = (1 - last_rate / first_rate) * 100
                print(f"\nNegative trend: Conversion decreased by {change:.1f}% from {first_period} to {last_period}")
            else:
                print(f"\nStable conversion from {first_period} to {last_period}")


def print_segment_funnel(funnel_df):
    """Print segment-based funnel results in a readable format"""
    print("\nFunnel Conversion by User Segment:")
    print("---------------------------------")
    
    # Get overall conversion rate for each segment (first step to last step)
    if 'Purchase_overall_rate' in funnel_df.columns:
        # Sort segments by conversion rate
        sorted_df = funnel_df.sort_values('Purchase_overall_rate', ascending=False)
        
        for _, row in sorted_df.iterrows():
            segment = row['segment']
            rate = row['Purchase_overall_rate']
            first_step_count = row['Product View_count']
            last_step_count = row['Purchase_count']
            
            print(f"{segment}: {rate*100:.2f}% overall conversion ({last_step_count:,}/{first_step_count:,} users)")
        
        # Identify best and worst performing segments
        best_segment = sorted_df.iloc[0]['segment']
        worst_segment = sorted_df.iloc[-1]['segment']
        
        print(f"\nBest performing segment: {best_segment}")
        print(f"Worst performing segment: {worst_segment}")
        
        # Show conversion rates by step for the best segment
        best_row = sorted_df[sorted_df['segment'] == best_segment].iloc[0]
        print(f"\nConversion steps for {best_segment}:")
        
        # Get the step names from the column headers
        # Extract step names from column headers like "Step_count" or "Step_rate"
        step_cols = [col for col in best_row.index if '_count' in col]
        steps = [col.split('_count')[0] for col in step_cols]
        
        # Show rates for each step (except the first)
        for i, step in enumerate(steps[1:], 1):
            rate_col = f"{step}_rate"
            if rate_col in best_row:
                print(f"  {step}: {best_row[rate_col]*100:.1f}% conversion from previous step")


def print_path_analysis(path_results):
    """Print path analysis results in a readable format"""
    path_counts = path_results['path_counts']
    
    print("\nMost Common User Paths:")
    print("---------------------")
    
    # Show top 5 most common paths
    for i, (_, row) in enumerate(path_counts.head(5).iterrows(), 1):
        path = row['path']
        freq = row['frequency']
        pct = row['percentage']
        
        print(f"{i}. {path}")
        print(f"   Frequency: {freq:,} users ({pct:.1f}%)")
    
   # Check if there are any complete paths (containing all possible steps)
    # We can't use step_names here since it's not defined in this scope,
    # so we'll just check if there are paths that skip steps in general
    all_paths = path_counts['path'].tolist()
    
    # Consider a "complete" path one with the most steps
    max_steps = max(path.count('>') + 1 for path in all_paths)
    complete_paths = [p for p in all_paths if p.count('>') + 1 == max_steps]
    
    # Paths that have fewer steps are considered to be skipping steps
    skipped_paths = [p for p in all_paths if p.count('>') + 1 < max_steps]
    
    if skipped_paths:
        print("\nPaths that skip steps:")
        for i, path in enumerate(skipped_paths[:3], 1):  # Show the first 3
            path_row = path_counts[path_counts['path'] == path].iloc[0]
            freq = path_row['frequency']
            print(f"{i}. {path} - {freq:,} users")



def print_segment_comparison(comparison_df):
    """Print segment comparison results in a readable format"""
    print("\nSegment Comparison for Purchase Rate:")
    print("----------------------------------")
    
    # Format as a table
    for _, row in comparison_df.iterrows():
        segment = row['segment']
        rate = row['Purchase_rate']
        rel_diff = row['rel_diff']
        
        # Format the relative difference
        if rel_diff > 0:
            diff_str = f"+{rel_diff:.1f}%"
        elif rel_diff < 0:
            diff_str = f"{rel_diff:.1f}%"
        else:
            diff_str = "baseline"
        
        print(f"{segment:20s}: {rate*100:.2f}% ({diff_str})")
    
    # Identify biggest opportunity
    if len(comparison_df) > 1:
        max_negative_diff = comparison_df[comparison_df['rel_diff'] < 0].sort_values('rel_diff').iloc[0]
        if not max_negative_diff.empty:
            print(f"\nBiggest improvement opportunity: {max_negative_diff['segment']}")
            print(f"Current: {max_negative_diff['Purchase_rate']*100:.2f}%, Potential uplift: {abs(max_negative_diff['rel_diff']):.1f}%")


if __name__ == "__main__":
    results = main()
    
    # Example of how the results could be used for business decisions
    print("\n=== BUSINESS APPLICATIONS OF FUNNEL ANALYSIS ===")
    
    # Overall funnel insights
    print("\n1. Overall Funnel Insights:")