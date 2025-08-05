import pandas as pd
import numpy as np
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
import warnings
from app.tools.mltools.cohortanalysistools import form_time_cohorts,form_behavioral_cohorts


def analyze_funnel(
    event_column: str,
    user_id_column: str,
    funnel_steps: List[str],
    step_names: Optional[List[str]] = None,
    max_step_time: Optional[int] = None
):
    """
    Analyze a user funnel using the existing CohortPipe framework
    
    Parameters:
    -----------
    event_column : str
        Column containing event names/types
    user_id_column : str
        Column containing user identifiers
    funnel_steps : List[str]
        List of event names representing steps in the funnel, in order
    step_names : List[str], optional
        Friendly names for the funnel steps (if None, funnel_steps will be used)
    max_step_time : int, optional
        Maximum time (in seconds) allowed between steps (if None, no time limit)
        
    Returns:
    --------
    Callable
        Function that analyzes a funnel in a CohortPipe
    """
    def _analyze_funnel(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Validate event_column contains all funnel steps
        events_in_data = df[event_column].unique()
        missing_steps = [step for step in funnel_steps if step not in events_in_data]
        if missing_steps:
            warnings.warn(f"The following funnel steps are not in the data: {missing_steps}")
        
        # Use provided step names or funnel step values
        step_labels = step_names if step_names else funnel_steps
        if step_names and len(step_names) != len(funnel_steps):
            warnings.warn("Length of step_names doesn't match funnel_steps. Using funnel_steps as labels.")
            step_labels = funnel_steps
        
        # Calculate overall funnel metrics
        funnel_summary = []
        
        # Count unique users at each step
        step_counts = []
        user_sets = {}
        
        for i, step in enumerate(funnel_steps):
            users_at_step = set(df[df[event_column] == step][user_id_column].unique())
            user_sets[step] = users_at_step
            step_counts.append(len(users_at_step))
        
        # Calculate conversion rates
        conversion_rates = []
        cumulative_rates = []
        
        for i in range(len(step_counts)):
            if i == 0:
                conversion_rates.append(1.0)  # First step is always 100%
                cumulative_rates.append(1.0)
            else:
                # Step-to-step conversion rate
                prev_count = step_counts[i-1]
                curr_count = step_counts[i]
                conv_rate = curr_count / prev_count if prev_count > 0 else 0
                conversion_rates.append(conv_rate)
                
                # Cumulative conversion rate from first step
                first_count = step_counts[0]
                cum_rate = curr_count / first_count if first_count > 0 else 0
                cumulative_rates.append(cum_rate)
        
        # Create overall funnel summary
        overall_funnel = {
            'step': step_labels,
            'count': step_counts,
            'conversion_rate': conversion_rates,
            'cumulative_rate': cumulative_rates
        }
        
        funnel_summary = pd.DataFrame(overall_funnel)
        
        # Store funnel result
        new_pipe.conversion_funnels['overall_funnel'] = funnel_summary
        
        return new_pipe
    
    return _analyze_funnel


def analyze_funnel_by_time(
    event_column: str,
    user_id_column: str,
    date_column: str,
    funnel_steps: List[str],
    step_names: Optional[List[str]] = None,
    time_period: str = 'M',
    max_periods: int = 12,
    datetime_format: Optional[str] = None
):
    """
    Analyze funnel performance over time using the existing CohortPipe framework
    
    Parameters:
    -----------
    event_column : str
        Column containing event names/types
    user_id_column : str
        Column containing user identifiers
    date_column : str
        Column containing dates for cohort formation
    funnel_steps : List[str]
        List of event names representing steps in the funnel, in order
    step_names : List[str], optional
        Friendly names for the funnel steps (if None, funnel_steps will be used)
    time_period : str, default='M'
        Time period for cohort grouping ('D', 'W', 'M', 'Q', 'Y')
    max_periods : int, default=12
        Maximum number of periods to include
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that analyzes funnel by time periods in a CohortPipe
    """
    def _analyze_funnel_by_time(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        # First create time cohorts
        
        cohort_pipe = form_time_cohorts(
            date_column=date_column,
            cohort_column='time_cohort',
            time_period=time_period,
            format_cohorts=True,
            datetime_format=datetime_format
        )(pipe)
        
        # Use provided step names or funnel step values
        step_labels = step_names if step_names else funnel_steps
        if step_names and len(step_names) != len(funnel_steps):
            warnings.warn("Length of step_names doesn't match funnel_steps. Using funnel_steps as labels.")
            step_labels = funnel_steps
        
        df = cohort_pipe.data.copy()  # Ensure we work with a copy
        cohort_column = 'time_cohort'
        
        # Get unique cohorts (time periods)
        cohorts = df[cohort_column].unique()
        
        # Limit to most recent periods if needed
        if len(cohorts) > max_periods:
            cohorts = sorted(cohorts)[-max_periods:]
        
        # Analyze the funnel for each time period
        funnel_results = []
        
        for cohort in cohorts:
            # Filter data for this cohort
            cohort_data = df[df[cohort_column] == cohort]
            
            # Calculate funnel metrics for this cohort
            step_counts = []
            
            for step in funnel_steps:
                # Count unique users at this step
                users_at_step = set(cohort_data[cohort_data[event_column] == step][user_id_column].unique())
                step_counts.append(len(users_at_step))
            
            # Create row for this cohort
            cohort_funnel = {
                'cohort': cohort,
                'total_users': len(cohort_data[user_id_column].unique())
            }
            
            # Add count for each step
            for i, step in enumerate(step_labels):
                cohort_funnel[f"{step}_count"] = step_counts[i]
            
            # Add conversion rates
            for i in range(len(step_counts)):
                if i == 0:
                    # First step conversion (from all users)
                    if cohort_funnel['total_users'] > 0:
                        cohort_funnel[f"{step_labels[i]}_rate"] = step_counts[i] / cohort_funnel['total_users']
                    else:
                        cohort_funnel[f"{step_labels[i]}_rate"] = 0
                else:
                    # Step-to-step conversion rate
                    prev_count = step_counts[i-1]
                    curr_count = step_counts[i]
                    
                    if prev_count > 0:
                        step_rate = curr_count / prev_count
                    else:
                        step_rate = 0
                    
                    cohort_funnel[f"{step_labels[i]}_rate"] = step_rate
                    
                    # Overall conversion rate (from first step)
                    if step_counts[0] > 0:
                        cohort_funnel[f"{step_labels[i]}_overall_rate"] = curr_count / step_counts[0]
                    else:
                        cohort_funnel[f"{step_labels[i]}_overall_rate"] = 0
            
            # Add dropoff rates 
            for i in range(len(step_counts) - 1):
                curr_count = step_counts[i]
                next_count = step_counts[i+1]
                
                if curr_count > 0:
                    dropoff_rate = (curr_count - next_count) / curr_count
                else:
                    dropoff_rate = 0
                
                cohort_funnel[f"{step_labels[i]}_to_{step_labels[i+1]}_dropoff"] = dropoff_rate
            
            funnel_results.append(cohort_funnel)
        
        # Create DataFrame with all time period funnel data
        funnel_df = pd.DataFrame(funnel_results)
        
        # Store results
        cohort_pipe.conversion_funnels['time_funnel'] = funnel_df
        
        return cohort_pipe
    
    return _analyze_funnel_by_time


def analyze_funnel_by_segment(
    event_column: str,
    user_id_column: str,
    segment_column: str,
    funnel_steps: List[str],
    step_names: Optional[List[str]] = None,
    min_users: int = 10
):
    """
    Analyze funnel performance across different user segments using the existing CohortPipe framework
    
    Parameters:
    -----------
    event_column : str
        Column containing event names/types
    user_id_column : str
        Column containing user identifiers
    segment_column : str
        Column containing segment information to group by
    funnel_steps : List[str]
        List of event names representing steps in the funnel, in order
    step_names : List[str], optional
        Friendly names for the funnel steps (if None, funnel_steps will be used)
    min_users : int, default=10
        Minimum number of users required for a segment to be included
        
    Returns:
    --------
    Callable
        Function that analyzes funnel by segments in a CohortPipe
    """
    def _analyze_funnel_by_segment(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        # First create behavior cohorts
        
        cohort_pipe = form_behavioral_cohorts(
            behavior_column=segment_column,
            cohort_column='segment_cohort'
        )(pipe)
        
        # Use provided step names or funnel step values
        step_labels = step_names if step_names else funnel_steps
        if step_names and len(step_names) != len(funnel_steps):
            warnings.warn("Length of step_names doesn't match funnel_steps. Using funnel_steps as labels.")
            step_labels = funnel_steps
        
        df = cohort_pipe.data.copy()  # Ensure we work with a copy
        cohort_column = 'segment_cohort'
        
        # Get unique segments
        segments = df[cohort_column].unique()
        
        # Analyze the funnel for each segment
        funnel_results = []
        
        for segment in segments:
            # Filter data for this segment
            segment_data = df[df[cohort_column] == segment]
            
            # Skip segments with too few users
            segment_users = segment_data[user_id_column].nunique()
            if segment_users < min_users:
                continue
            
            # Calculate funnel metrics for this segment
            step_counts = []
            
            for step in funnel_steps:
                # Count unique users at this step
                users_at_step = set(segment_data[segment_data[event_column] == step][user_id_column].unique())
                step_counts.append(len(users_at_step))
            
            # Create row for this segment
            segment_funnel = {
                'segment': segment,
                'total_users': segment_users
            }
            
            # Add count for each step
            for i, step in enumerate(step_labels):
                segment_funnel[f"{step}_count"] = step_counts[i]
            
            # Add conversion rates
            for i in range(len(step_counts)):
                if i == 0:
                    # First step conversion (from all users)
                    segment_funnel[f"{step_labels[i]}_rate"] = step_counts[i] / segment_users
                else:
                    # Step-to-step conversion rate
                    prev_count = step_counts[i-1]
                    curr_count = step_counts[i]
                    
                    if prev_count > 0:
                        step_rate = curr_count / prev_count
                    else:
                        step_rate = 0
                    
                    segment_funnel[f"{step_labels[i]}_rate"] = step_rate
                    
                    # Overall conversion rate (from first step)
                    if step_counts[0] > 0:
                        segment_funnel[f"{step_labels[i]}_overall_rate"] = curr_count / step_counts[0]
                    else:
                        segment_funnel[f"{step_labels[i]}_overall_rate"] = 0
            
            # Add dropoff rates
            for i in range(len(step_counts) - 1):
                curr_count = step_counts[i]
                next_count = step_counts[i+1]
                
                if curr_count > 0:
                    dropoff_rate = (curr_count - next_count) / curr_count
                else:
                    dropoff_rate = 0
                
                segment_funnel[f"{step_labels[i]}_to_{step_labels[i+1]}_dropoff"] = dropoff_rate
            
            funnel_results.append(segment_funnel)
        
        # Create DataFrame with all segment funnel data
        funnel_df = pd.DataFrame(funnel_results)
        
        # Store results
        cohort_pipe.conversion_funnels['segment_funnel'] = funnel_df
        
        return cohort_pipe
    
    return _analyze_funnel_by_segment


def analyze_user_paths(
    event_column: str,
    user_id_column: str,
    timestamp_column: str,
    funnel_steps: List[str],
    step_names: Optional[List[str]] = None,
    max_path_length: int = 10,
    min_path_frequency: int = 5
):
    """
    Analyze actual paths users take through the funnel (not just the ideal path)
    
    Parameters:
    -----------
    event_column : str
        Column containing event names/types
    user_id_column : str
        Column containing user identifiers
    timestamp_column : str
        Column containing event timestamps
    funnel_steps : List[str]
        List of event names representing steps in the funnel, in order
    step_names : List[str], optional
        Friendly names for the funnel steps (if None, funnel_steps will be used)
    max_path_length : int, default=10
        Maximum number of steps to include in a path
    min_path_frequency : int, default=5
        Minimum number of users who must take a path for it to be included
        
    Returns:
    --------
    Callable
        Function that analyzes actual user paths in a CohortPipe
    """
    def _analyze_user_paths(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Use provided step names or funnel step values
        step_labels = step_names if step_names else funnel_steps
        if step_names and len(step_names) != len(funnel_steps):
            warnings.warn("Length of step_names doesn't match funnel_steps. Using funnel_steps as labels.")
            step_labels = funnel_steps
        
        # Create mapping between event names and step names
        step_mapping = dict(zip(funnel_steps, step_labels))
        
        # Extract user paths
        user_paths = []
        users_per_path = {}
        
        for user in df[user_id_column].unique():
            # Get events for this user, ordered by timestamp
            user_events = df[df[user_id_column] == user].sort_values(timestamp_column)
            
            # Extract the sequence of events
            event_sequence = user_events[event_column].tolist()
            
            # Map events to funnel steps (if in funnel) and filter out non-funnel events
            step_sequence = [step_mapping.get(event) for event in event_sequence if event in funnel_steps]
            
            if not step_sequence:
                continue
            
            # Remove consecutive duplicates for cleaner paths
            deduped_sequence = []
            for step in step_sequence:
                if not deduped_sequence or step != deduped_sequence[-1]:
                    deduped_sequence.append(step)
            
            # Create path representation
            path = ' > '.join(deduped_sequence[:max_path_length])
            
            # Track this path
            user_paths.append({'user_id': user, 'path': path, 'path_length': len(deduped_sequence)})
            
            # Count users per path
            if path not in users_per_path:
                users_per_path[path] = set()
            users_per_path[path].add(user)
        
        # Create DataFrame of all paths
        paths_df = pd.DataFrame(user_paths)
        
        # Count frequency of each path
        path_counts = []
        for path, users in users_per_path.items():
            user_count = len(users)
            if user_count >= min_path_frequency:
                path_counts.append({
                    'path': path,
                    'frequency': user_count,
                    'percentage': user_count / len(df[user_id_column].unique()) * 100
                })
        
        # Sort paths by frequency
        path_counts_df = pd.DataFrame(path_counts).sort_values('frequency', ascending=False)
        
        # Store results
        new_pipe.conversion_funnels['user_paths'] = {
            'user_paths': paths_df,
            'path_counts': path_counts_df
        }
        
        return new_pipe
    
    return _analyze_user_paths


def get_funnel_summary():
    """
    Return a summary of funnel analysis results
    
    Returns:
    --------
    Callable
        Function that returns funnel summary from a CohortPipe
    """
    def _get_funnel_summary(pipe):
        if not hasattr(pipe, 'conversion_funnels') or not pipe.conversion_funnels:
            raise ValueError("No funnel analyses found. Run analyze_funnel() first.")
        
        # Just return the funnel data for further analysis
        return pipe.conversion_funnels
    
    return _get_funnel_summary


def compare_segments(metric_column: str, baseline_segment: Optional[str] = None):
    """
    Compare funnel metrics across segments
    
    Parameters:
    -----------
    metric_column : str
        Column containing the metric to compare (e.g., 'Purchase_rate')
    baseline_segment : str, optional
        Segment to use as the baseline for comparison (if None, use average)
        
    Returns:
    --------
    Callable
        Function that compares segments in a CohortPipe
    """
    def _compare_segments(pipe):
        if not hasattr(pipe, 'conversion_funnels') or 'segment_funnel' not in pipe.conversion_funnels:
            raise ValueError("No segment funnel analysis found. Run analyze_funnel_by_segment() first.")
        
        funnel_data = pipe.conversion_funnels['segment_funnel']
        
        if metric_column not in funnel_data.columns:
            raise ValueError(f"Metric '{metric_column}' not found in funnel data")
        
        # Create comparison dataframe
        comparison = funnel_data[['segment', metric_column]].copy()
        
        # Calculate baseline value
        if baseline_segment is not None:
            if baseline_segment not in funnel_data['segment'].values:
                raise ValueError(f"Baseline segment '{baseline_segment}' not found")
            baseline_value = funnel_data[funnel_data['segment'] == baseline_segment][metric_column].iloc[0]
        else:
            # Use average as baseline
            baseline_value = funnel_data[metric_column].mean()
        
        # Calculate absolute and relative differences
        comparison['baseline'] = baseline_value
        comparison['abs_diff'] = comparison[metric_column] - comparison['baseline']
        comparison['rel_diff'] = (comparison[metric_column] / comparison['baseline'] - 1) * 100
        
        # Sort by the metric value
        comparison = comparison.sort_values(metric_column, ascending=False)
        
        return comparison
    
    return _compare_segments