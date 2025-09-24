import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
import warnings
from .base_pipe import BasePipe

"""
def _period_diff(period_delta, time_period):
    #Helper function to calculate difference between time periods
    if time_period == 'D':
        return period_delta.days
    elif time_period == 'W':
        return period_delta.days // 7
    elif time_period == 'M':
        # For months, we need years * 12 + additional months
        return (period_delta.years * 12) + period_delta.months
    elif time_period == 'Q':
        # For quarters, convert months to quarters (divide by 3)
        total_months = (period_delta.years * 12) + period_delta.months
        return total_months // 3
    elif time_period == 'Y':
        return period_delta.years
    else:
        return 0
"""

def _period_diff(period_delta, time_period):
    """Helper function to calculate difference between time periods"""
    if isinstance(period_delta, pd.Timedelta):
        # For Timedelta objects (most common in pandas)
        if time_period == 'D':
            return period_delta.days
        elif time_period == 'W':
            return period_delta.days // 7
        elif time_period == 'M':
            # Approximate months as days / 30
            return period_delta.days // 30
        elif time_period == 'Q':
            # Approximate quarters as days / 90
            return period_delta.days // 90
        elif time_period == 'Y':
            # Approximate years as days / 365
            return period_delta.days // 365
        else:
            return 0
    else:
        # For Period objects or other types
        try:
            if time_period == 'D':
                return period_delta.n
            elif time_period == 'W':
                return period_delta.n
            elif time_period == 'M':
                return period_delta.n
            elif time_period == 'Q':
                return period_delta.n
            elif time_period == 'Y':
                return period_delta.n
            else:
                return 0
        except AttributeError:
            # Fall back to approximation if attributes not available
            total_seconds = getattr(period_delta, 'total_seconds', lambda: 0)()
            if time_period == 'D':
                return int(total_seconds / (24 * 3600))
            elif time_period == 'W':
                return int(total_seconds / (7 * 24 * 3600))
            elif time_period == 'M':
                return int(total_seconds / (30 * 24 * 3600))
            elif time_period == 'Q':
                return int(total_seconds / (90 * 24 * 3600))
            elif time_period == 'Y':
                return int(total_seconds / (365 * 24 * 3600))
            else:
                return 0

class CohortPipe(BasePipe):
    """
    A pipeline-style cohort analysis tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for cohort analysis"""
        self.cohorts = {}
        self.cohort_results = {}
        self.retention_matrices = {}
        self.conversion_funnels = {}
        self.lifecycle_stages = {}
        self.current_analysis = None
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'cohorts'):
            self.cohorts = source_pipe.cohorts.copy()
        if hasattr(source_pipe, 'cohort_results'):
            self.cohort_results = source_pipe.cohort_results.copy()
        if hasattr(source_pipe, 'retention_matrices'):
            self.retention_matrices = source_pipe.retention_matrices.copy()
        if hasattr(source_pipe, 'conversion_funnels'):
            self.conversion_funnels = source_pipe.conversion_funnels.copy()
        if hasattr(source_pipe, 'lifecycle_stages'):
            self.lifecycle_stages = source_pipe.lifecycle_stages.copy()
        if hasattr(source_pipe, 'current_analysis'):
            self.current_analysis = source_pipe.current_analysis
    
    def to_df(self, analysis_name: Optional[str] = None, include_metadata: bool = False):
        """
        Convert the last analysis output to a DataFrame
        
        Parameters:
        -----------
        analysis_name : str, optional
            Name of the specific analysis to convert. If None, uses the current_analysis
        include_metadata : bool, default=False
            Whether to include metadata columns in the output DataFrame
            
        Returns:
        --------
        pd.DataFrame
            DataFrame representation of the analysis results
            
        Raises:
        -------
        ValueError
            If no analysis has been performed or the specified analysis doesn't exist
            
        Examples:
        --------
        >>> # Retention analysis
        >>> pipe = (CohortPipe.from_dataframe(df)
        ...         | form_time_cohorts('date', 'cohort', 'M')
        ...         | calculate_retention('cohort', 'date', 'user_id', 'M', 6))
        >>> retention_df = pipe.to_df()
        >>> print(retention_df.head())
        
        >>> # Conversion analysis with metadata
        >>> pipe = (CohortPipe.from_dataframe(df)
        ...         | form_behavioral_cohorts('source', 'cohort')
        ...         | calculate_conversion('cohort', 'event', 'user_id', ['step1', 'step2']))
        >>> conversion_df = pipe.to_df(include_metadata=True)
        >>> print(conversion_df.columns)
        """
        if not self.cohort_results:
            raise ValueError("No analysis has been performed. Run an analysis first.")
        
        # Determine which analysis to use
        if analysis_name is None:
            if self.current_analysis is None:
                # Use the last analysis in cohort_results
                if not self.cohort_results:
                    raise ValueError("No cohort results available to convert to DataFrame.")
                analysis_name = list(self.cohort_results.keys())[-1]
            else:
                # Find the analysis that matches current_analysis
                matching_analyses = [name for name in self.cohort_results.keys() 
                                   if name.startswith(self.current_analysis)]
                if not matching_analyses:
                    raise ValueError(f"No analysis found for current_analysis: {self.current_analysis}")
                analysis_name = matching_analyses[0]
        
        if analysis_name not in self.cohort_results:
            raise ValueError(f"Analysis '{analysis_name}' not found. Available analyses: {list(self.cohort_results.keys())}")
        
        result = self.cohort_results[analysis_name]
        analysis_type = result['type']
        
        if analysis_type == 'retention':
            return self._retention_to_df(result, include_metadata)
        elif analysis_type == 'conversion':
            return self._conversion_to_df(result, include_metadata)
        elif analysis_type == 'ltv':
            return self._ltv_to_df(result, include_metadata)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
    
    def merge_to_df(self, base_df: pd.DataFrame, analysis_name: Optional[str] = None, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
        """
        Merge cohort analysis results into the base dataframe as new columns.
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge results into
        analysis_name : str, optional
            Name of the specific analysis to merge. If None, uses the current_analysis
        include_metadata : bool, default=False
            Whether to include metadata columns in the output DataFrame
        **kwargs : dict
            Additional arguments (unused for this pipeline)
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with cohort analysis results merged as new columns
        """
        result_df = base_df.copy()
        
        # Add pipeline identification
        result_df['pipeline_type'] = 'cohort_analysis'
        result_df['pipeline_has_results'] = len(self.cohort_results) > 0
        
        if not self.cohort_results:
            return result_df
        
        # Determine which analysis to use
        if analysis_name is None:
            if self.current_analysis is None:
                # Use the last analysis in cohort_results
                analysis_name = list(self.cohort_results.keys())[-1]
            else:
                # Find the analysis that matches current_analysis
                matching_analyses = [name for name in self.cohort_results.keys() 
                                   if name.startswith(self.current_analysis)]
                if matching_analyses:
                    analysis_name = matching_analyses[0]
                else:
                    analysis_name = list(self.cohort_results.keys())[-1]
        
        if analysis_name not in self.cohort_results:
            return result_df
        
        # Get the analysis result
        analysis_result = self.cohort_results[analysis_name]
        analysis_type = analysis_result['type']
        
        # Add analysis summary information
        result_df[f'cohort_analysis_{analysis_name}_has_data'] = True
        result_df[f'cohort_analysis_{analysis_name}_type'] = analysis_type
        
        # Add metadata if requested
        if include_metadata:
            result_df['cohort_analysis_name'] = analysis_name
            result_df['cohort_analysis_type'] = 'cohort_analysis'
            result_df['cohort_total_analyses'] = len(self.cohort_results)
            result_df['cohort_available_analyses'] = ', '.join(self.cohort_results.keys())
            result_df['cohort_current_analysis'] = self.current_analysis or 'none'
        
        return result_df
    
    def _has_results(self) -> bool:
        """
        Check if the pipeline has any cohort analysis results.
        
        Returns:
        --------
        bool
            True if the pipeline has cohort analysis results, False otherwise
        """
        return len(self.cohort_results) > 0
    
    def _retention_to_df(self, result: Dict, include_metadata: bool = False) -> pd.DataFrame:
        """Convert retention analysis results to DataFrame"""
        retention_matrix = result['retention_matrix']
        retention_counts = result['retention_counts']
        cohort_sizes = result['cohort_sizes']
        
        # Create a long-format DataFrame
        df_list = []
        
        for cohort in retention_matrix.index:
            cohort_size = cohort_sizes.loc[cohort, 'cohort_size'] if cohort in cohort_sizes.index else 0
            
            for period_col in retention_matrix.columns:
                period_num = period_col.replace('Period ', '')
                retention_rate = retention_matrix.loc[cohort, period_col]
                user_count = retention_counts.loc[cohort, period_col]
                
                row = {
                    'cohort': cohort,
                    'period': int(period_num),
                    'retention_rate': retention_rate,
                    'user_count': user_count,
                    'cohort_size': cohort_size
                }
                
                if include_metadata:
                    row.update({
                        'analysis_type': 'retention',
                        'retention_type': result.get('retention_type', 'unknown'),
                        'time_period': result.get('time_period', 'unknown'),
                        'cohort_column': result.get('cohort_column', 'unknown')
                    })
                
                df_list.append(row)
        
        result_df = pd.DataFrame(df_list)
        
        # Ensure we always return a DataFrame
        if result_df is None:
            result_df = pd.DataFrame()
        
        return result_df
    
    def _conversion_to_df(self, result: Dict, include_metadata: bool = False) -> pd.DataFrame:
        """Convert conversion analysis results to DataFrame"""
        # The funnel_data is already a DataFrame, just add metadata if requested
        df = result['funnel_data'].copy()
        
        # Ensure we always return a DataFrame
        if df is None:
            df = pd.DataFrame()
        
        if include_metadata and not df.empty:
            df['analysis_type'] = 'conversion'
            df['event_column'] = result.get('event_column', 'unknown')
            df['funnel_steps'] = str(result.get('funnel_steps', []))
            df['include_rates'] = result.get('include_rates', False)
            df['cumulative'] = result.get('cumulative', False)
        
        return df
    
    def _ltv_to_df(self, result: Dict, include_metadata: bool = False) -> pd.DataFrame:
        """Convert LTV analysis results to DataFrame"""
        ltv_matrix = result['ltv_matrix']
        ltv_matrix_total = result['ltv_matrix_total']
        cohort_sizes = result['cohort_sizes']
        
        # Create a long-format DataFrame
        df_list = []
        
        for cohort in ltv_matrix.index:
            cohort_size = cohort_sizes[cohort_sizes[result['cohort_column']] == cohort]['cohort_size'].iloc[0]
            
            for period_col in ltv_matrix.columns:
                period_num = period_col.replace('Period ', '')
                avg_value = ltv_matrix.loc[cohort, period_col]
                total_value = ltv_matrix_total.loc[cohort, period_col]
                
                row = {
                    'cohort': cohort,
                    'period': int(period_num),
                    'avg_value': avg_value,
                    'total_value': total_value,
                    'cohort_size': cohort_size
                }
                
                if include_metadata:
                    row.update({
                        'analysis_type': 'ltv',
                        'value_column': result.get('value_column', 'unknown'),
                        'time_period': result.get('time_period', 'unknown'),
                        'cumulative': result.get('cumulative', False),
                        'cohort_column': result.get('cohort_column', 'unknown')
                    })
                
                df_list.append(row)
        
        result_df = pd.DataFrame(df_list)
        
        # Ensure we always return a DataFrame
        if result_df is None:
            result_df = pd.DataFrame()
        
        return result_df
    
    def get_summary(self, analysis_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a summary of the cohort analysis results.
        
        Parameters:
        -----------
        analysis_name : str, optional
            Name of the specific analysis. If None, uses the current_analysis
            
        Returns:
        --------
        dict
            Summary of the cohort analysis results
        """
        if not self.cohort_results:
            return {"error": "No analysis has been performed"}
        
        # Determine which analysis to use
        if analysis_name is None:
            if self.current_analysis is None:
                analysis_name = list(self.cohort_results.keys())[-1]
            else:
                matching_analyses = [name for name in self.cohort_results.keys() 
                                   if name.startswith(self.current_analysis)]
                if not matching_analyses:
                    return {"error": f"No analysis found for current_analysis: {self.current_analysis}"}
                analysis_name = matching_analyses[0]
        
        if analysis_name not in self.cohort_results:
            return {"error": f"Analysis '{analysis_name}' not found"}
        
        result = self.cohort_results[analysis_name]
        
        return {
            "analysis_name": analysis_name,
            "analysis_type": result.get('type', 'unknown'),
            "total_analyses": len(self.cohort_results),
            "available_analyses": list(self.cohort_results.keys()),
            "total_cohorts": len(self.cohorts),
            "cohort_types": list(self.cohorts.keys()),
            "retention_matrices": list(self.retention_matrices.keys()),
            "conversion_funnels": list(self.conversion_funnels.keys()),
            "lifecycle_stages": list(self.lifecycle_stages.keys()),
            "current_analysis": self.current_analysis
        }


# Cohort formation functions
def form_time_cohorts(
    date_column: str,
    cohort_column: str = 'cohort',
    time_period: str = 'M',
    format_cohorts: bool = True,
    datetime_format: Optional[str] = None
):
    """
    Form cohorts based on time periods
    
    Parameters:
    -----------
    date_column : str
        Column containing the date to use for cohort formation
    cohort_column : str, default='cohort'
        Name of the column to store cohort information
    time_period : str, default='M'
        Time period for cohort grouping ('D' for daily, 'W' for weekly, 'M' for monthly, 'Q' for quarterly, 'Y' for yearly)
    format_cohorts : bool, default=True
        Whether to format cohorts as strings (e.g., 'Jan 2023' instead of timestamp)
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that forms time-based cohorts from a CohortPipe
    """
    def _form_time_cohorts(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            if datetime_format:
                df[date_column] = pd.to_datetime(df[date_column], format=datetime_format)
            else:
                df[date_column] = pd.to_datetime(df[date_column])
        
        # Create cohort column based on time period
        if time_period == 'D':
            df[cohort_column] = df[date_column].dt.date
        elif time_period == 'W':
            df[cohort_column] = df[date_column].dt.to_period('W').dt.start_time
        elif time_period == 'M':
            df[cohort_column] = df[date_column].dt.to_period('M').dt.start_time
        elif time_period == 'Q':
            df[cohort_column] = df[date_column].dt.to_period('Q').dt.start_time
        elif time_period == 'Y':
            df[cohort_column] = df[date_column].dt.to_period('Y').dt.start_time
        else:
            raise ValueError(f"Invalid time period: {time_period}. Use 'D', 'W', 'M', 'Q', or 'Y'.")
        
        # Format cohorts if requested
        if format_cohorts:
            if time_period == 'D':
                df[cohort_column] = df[cohort_column].apply(lambda x: x.strftime('%d %b %Y'))
            elif time_period == 'W':
                df[cohort_column] = df[cohort_column].apply(lambda x: x.strftime('Week of %d %b %Y'))
            elif time_period == 'M':
                df[cohort_column] = df[cohort_column].apply(lambda x: x.strftime('%b %Y'))
            elif time_period == 'Q':
                df[cohort_column] = df[cohort_column].apply(lambda x: f"Q{x.quarter} {x.year}")
            elif time_period == 'Y':
                df[cohort_column] = df[cohort_column].apply(lambda x: str(x.year))
        
        # Store cohort info
        new_pipe.cohorts['time_cohorts'] = {
            'type': 'time',
            'date_column': date_column,
            'cohort_column': cohort_column,
            'time_period': time_period
        }
        
        new_pipe.data = df
        new_pipe.current_analysis = 'time_cohorts'
        
        return new_pipe
    
    return _form_time_cohorts


def form_behavioral_cohorts(
    behavior_column: str,
    cohort_column: str = 'cohort',
    conditions: Dict[str, Any] = None,
    custom_cohorts: Dict[str, Callable[[pd.DataFrame], pd.Series]] = None
):
    """
    Form cohorts based on user behavior
    
    Parameters:
    -----------
    behavior_column : str
        Column containing the behavior to use for cohort formation
    cohort_column : str, default='cohort'
        Name of the column to store cohort information
    conditions : Dict[str, Any], optional
        Dictionary mapping cohort names to conditions (e.g., {'high_value': ('>',100)})
    custom_cohorts : Dict[str, Callable], optional
        Dictionary mapping cohort names to functions that take a dataframe and return a boolean mask
        
    Returns:
    --------
    Callable
        Function that forms behavior-based cohorts from a CohortPipe
    """
    def _form_behavioral_cohorts(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Create default cohort column with 'Other'
        df[cohort_column] = 'Other'
        
        # Apply conditions if provided
        if conditions:
            for cohort_name, condition in conditions.items():
                if isinstance(condition, tuple):
                    operator, value = condition[0], condition[1]
                    
                    if operator == '>':
                        mask = df[behavior_column] > value
                    elif operator == '>=':
                        mask = df[behavior_column] >= value
                    elif operator == '<':
                        mask = df[behavior_column] < value
                    elif operator == '<=':
                        mask = df[behavior_column] <= value
                    elif operator == '==':
                        mask = df[behavior_column] == value
                    elif operator == '!=':
                        mask = df[behavior_column] != value
                    elif operator == 'in':
                        mask = df[behavior_column].isin(value)
                    elif operator == 'not in':
                        mask = ~df[behavior_column].isin(value)
                    elif operator == 'between':
                        if len(condition) != 3:
                            raise ValueError("'between' operator requires lower and upper bounds.")
                        lower, upper = condition[1], condition[2]
                        mask = (df[behavior_column] >= lower) & (df[behavior_column] <= upper)
                    elif operator == 'contains':
                        mask = df[behavior_column].astype(str).str.contains(value)
                    else:
                        raise ValueError(f"Unknown operator: {operator}")
                    
                    df.loc[mask, cohort_column] = cohort_name
                else:
                    warnings.warn(f"Invalid condition for cohort '{cohort_name}'. Skipping.")
        
        # Apply custom cohort functions if provided
        if custom_cohorts:
            for cohort_name, cohort_func in custom_cohorts.items():
                mask = cohort_func(df)
                df.loc[mask, cohort_column] = cohort_name
        
        # Store cohort info
        new_pipe.cohorts['behavioral_cohorts'] = {
            'type': 'behavioral',
            'behavior_column': behavior_column,
            'cohort_column': cohort_column
        }
        
        new_pipe.data = df
        new_pipe.current_analysis = 'behavioral_cohorts'
        
        return new_pipe
    
    return _form_behavioral_cohorts


def form_acquisition_cohorts(
    acquisition_date_column: str,
    acquisition_source_column: str,
    cohort_column: str = 'cohort',
    time_period: str = 'M',
    combine_source: bool = True,
    format_cohorts: bool = True,
    datetime_format: Optional[str] = None
):
    """
    Form cohorts based on acquisition time and source
    
    Parameters:
    -----------
    acquisition_date_column : str
        Column containing the date of user acquisition
    acquisition_source_column : str
        Column containing the acquisition source (e.g., 'organic', 'paid', etc.)
    cohort_column : str, default='cohort'
        Name of the column to store cohort information
    time_period : str, default='M'
        Time period for cohort grouping ('D', 'W', 'M', 'Q', 'Y')
    combine_source : bool, default=True
        Whether to combine time period with acquisition source
    format_cohorts : bool, default=True
        Whether to format cohorts as strings
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that forms acquisition-based cohorts from a CohortPipe
    """
    def _form_acquisition_cohorts(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[acquisition_date_column]):
            if datetime_format:
                df[acquisition_date_column] = pd.to_datetime(df[acquisition_date_column], format=datetime_format)
            else:
                df[acquisition_date_column] = pd.to_datetime(df[acquisition_date_column])
        
        # Create time-based cohort
        time_cohort = acquisition_date_column + '_period'
        if time_period == 'D':
            df[time_cohort] = df[acquisition_date_column].dt.date
        elif time_period == 'W':
            df[time_cohort] = df[acquisition_date_column].dt.to_period('W').dt.start_time
        elif time_period == 'M':
            df[time_cohort] = df[acquisition_date_column].dt.to_period('M').dt.start_time
        elif time_period == 'Q':
            df[time_cohort] = df[acquisition_date_column].dt.to_period('Q').dt.start_time
        elif time_period == 'Y':
            df[time_cohort] = df[acquisition_date_column].dt.to_period('Y').dt.start_time
        else:
            raise ValueError(f"Invalid time period: {time_period}. Use 'D', 'W', 'M', 'Q', or 'Y'.")
        
        # Format time cohort if requested
        if format_cohorts:
            if time_period == 'D':
                df[time_cohort] = df[time_cohort].apply(lambda x: x.strftime('%d %b %Y'))
            elif time_period == 'W':
                df[time_cohort] = df[time_cohort].apply(lambda x: x.strftime('Week of %d %b %Y'))
            elif time_period == 'M':
                df[time_cohort] = df[time_cohort].apply(lambda x: x.strftime('%b %Y'))
            elif time_period == 'Q':
                df[time_cohort] = df[time_cohort].apply(lambda x: f"Q{x.quarter} {x.year}")
            elif time_period == 'Y':
                df[time_cohort] = df[time_cohort].apply(lambda x: str(x.year))
        
        # Combine with source if requested
        if combine_source:
            df[cohort_column] = df[acquisition_source_column] + ' - ' + df[time_cohort].astype(str)
        else:
            df[cohort_column] = df[time_cohort]
        
        # Clean up temporary column
        df.drop(columns=[time_cohort], inplace=True)
        
        # Store cohort info
        new_pipe.cohorts['acquisition_cohorts'] = {
            'type': 'acquisition',
            'acquisition_date_column': acquisition_date_column,
            'acquisition_source_column': acquisition_source_column,
            'cohort_column': cohort_column,
            'time_period': time_period
        }
        
        new_pipe.data = df
        new_pipe.current_analysis = 'acquisition_cohorts'
        
        return new_pipe
    
    return _form_acquisition_cohorts


# Cohort analysis functions
def calculate_retention(
    cohort_column: str,
    date_column: str,
    user_id_column: str,
    time_period: str = 'M',
    max_periods: int = 12,
    retention_type: str = 'classic',
    datetime_format: Optional[str] = None
):
    """
    Calculate retention metrics for cohorts
    
    Parameters:
    -----------
    cohort_column : str
        Column containing cohort information
    date_column : str
        Column containing the date of activity
    user_id_column : str
        Column containing user identifiers
    time_period : str, default='M'
        Time period for retention calculation ('D', 'W', 'M', 'Q', 'Y')
    max_periods : int, default=12
        Maximum number of periods to calculate retention for
    retention_type : str, default='classic'
        Type of retention to calculate:
        - 'classic': Users who return in a specific period
        - 'rolling': Users who return in this period or any later period
        - 'unbounded': Users who were active at least N times
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that calculates retention from a CohortPipe
    """
    def _calculate_retention(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            if datetime_format:
                df[date_column] = pd.to_datetime(df[date_column], format=datetime_format)
            else:
                df[date_column] = pd.to_datetime(df[date_column])
        
        # Add period column
        print(f"time_period: {time_period}")
        if time_period == 'D':
            df['period'] = df[date_column].dt.date
        elif time_period == 'W':
            df['period'] = df[date_column].dt.to_period('W').dt.start_time
        elif time_period == 'M':
            df['period'] = df[date_column].dt.to_period('M').dt.start_time
        elif time_period == 'Q':
            df['period'] = df[date_column].dt.to_period('Q').dt.start_time
        elif time_period == 'Y':
            df['period'] = df[date_column].dt.to_period('Y').dt.start_time
        else:
            raise ValueError(f"Invalid time period: {time_period}. Use 'D', 'W', 'M', 'Q', or 'Y'.")
        
        # Group by user and find their first period (for calculating periods since first activity)
        user_first_period = df.groupby(user_id_column)['period'].min().reset_index()
        user_first_period.columns = [user_id_column, 'first_period']
        
        # Merge first period back to the original dataframe
        df = pd.merge(df, user_first_period, on=user_id_column, how='left')
        
        # Calculate periods since first activity
        df['periods_since_first'] = (df['period'] - df['first_period']).apply(lambda x: _period_diff(x, time_period))
        
        # Filter to relevant periods
        df = df[df['periods_since_first'] <= max_periods]
        
        # Count unique users per cohort and period
        if retention_type == 'classic':
            # For each cohort and period, count unique users
            cohort_counts = df.groupby([cohort_column, 'periods_since_first'])[user_id_column].nunique().reset_index()
            cohort_counts.columns = [cohort_column, 'period', 'users']
            
            # Calculate total users in each cohort (period 0)
            cohort_sizes = cohort_counts[cohort_counts['period'] == 0].copy()
            cohort_sizes.columns = [cohort_column, 'period', 'cohort_size']
            
            # Merge cohort sizes back to get retention rates
            retention = pd.merge(cohort_counts, cohort_sizes[[cohort_column, 'cohort_size']], on=cohort_column, how='left')
            retention['retention_rate'] = retention['users'] / retention['cohort_size']
            
            # Pivot to create retention matrix
            retention_matrix = retention.pivot(index=cohort_column, columns='period', values='retention_rate')
            retention_counts = retention.pivot(index=cohort_column, columns='period', values='users')
            cohort_sizes = retention[retention['period'] == 0][['cohort_size']]
            
        elif retention_type == 'rolling':
            # For rolling retention, count users who return in this or any future period
            rolling_counts = []
            
            for cohort in df[cohort_column].unique():
                cohort_users = df[df[cohort_column] == cohort][user_id_column].unique()
                cohort_size = len(cohort_users)
                
                for period in range(max_periods + 1):
                    # Find users who were active in this period or later
                    active_users = df[(df[cohort_column] == cohort) & 
                                    (df['periods_since_first'] >= period)][user_id_column].unique()
                    active_count = len(active_users)
                    
                    rolling_counts.append({
                        cohort_column: cohort,
                        'period': period,
                        'users': active_count,
                        'cohort_size': cohort_size,
                        'retention_rate': active_count / cohort_size if cohort_size > 0 else 0
                    })
            
            rolling_df = pd.DataFrame(rolling_counts)
            
            # Pivot to create retention matrix
            retention_matrix = rolling_df.pivot(index=cohort_column, columns='period', values='retention_rate')
            retention_counts = rolling_df.pivot(index=cohort_column, columns='period', values='users')
            cohort_sizes = rolling_df[rolling_df['period'] == 0][['cohort_size']]
            
        elif retention_type == 'unbounded':
            # For unbounded retention, count users who were active at least N times
            unbounded_counts = []
            
            for cohort in df[cohort_column].unique():
                # Get users in this cohort
                cohort_data = df[df[cohort_column] == cohort]
                cohort_users = cohort_data[user_id_column].unique()
                cohort_size = len(cohort_users)
                
                # Count activity frequency per user
                user_activity_count = cohort_data.groupby(user_id_column).size().reset_index()
                user_activity_count.columns = [user_id_column, 'activity_count']
                
                for period in range(max_periods + 1):
                    # Period in unbounded retention represents "users active at least N times"
                    active_users = user_activity_count[user_activity_count['activity_count'] > period][user_id_column].unique()
                    active_count = len(active_users)
                    
                    unbounded_counts.append({
                        cohort_column: cohort,
                        'period': period,
                        'users': active_count,
                        'cohort_size': cohort_size,
                        'retention_rate': active_count / cohort_size if cohort_size > 0 else 0
                    })
            
            unbounded_df = pd.DataFrame(unbounded_counts)
            
            # Pivot to create retention matrix
            retention_matrix = unbounded_df.pivot(index=cohort_column, columns='period', values='retention_rate')
            retention_counts = unbounded_df.pivot(index=cohort_column, columns='period', values='users')
            cohort_sizes = unbounded_df[unbounded_df['period'] == 0][['cohort_size']]
        
        else:
            raise ValueError(f"Invalid retention type: {retention_type}. Use 'classic', 'rolling', or 'unbounded'.")
        
        # Format columns
        retention_matrix.columns = [f'Period {col}' for col in retention_matrix.columns]
        retention_counts.columns = [f'Period {col}' for col in retention_counts.columns]
        
        # Store results
        analysis_name = f'{new_pipe.current_analysis}_retention'
        new_pipe.cohort_results[analysis_name] = {
            'type': 'retention',
            'retention_type': retention_type,
            'cohort_column': cohort_column,
            'time_period': time_period,
            'retention_matrix': retention_matrix,
            'retention_counts': retention_counts,
            'cohort_sizes': cohort_sizes
        }
        
        new_pipe.retention_matrices[analysis_name] = retention_matrix
        
        return new_pipe
    
    return _calculate_retention


def calculate_conversion(
    cohort_column: str,
    event_column: str,
    user_id_column: str,
    funnel_steps: List[str],
    step_names: Optional[List[str]] = None,
    include_rates: bool = True,
    cumulative: bool = True
):
    """
    Calculate conversion funnel metrics for cohorts
    
    Parameters:
    -----------
    cohort_column : str
        Column containing cohort information
    event_column : str
        Column containing event names/types
    user_id_column : str
        Column containing user identifiers
    funnel_steps : List[str]
        List of event names representing steps in the funnel, in order
    step_names : List[str], optional
        Friendly names for the funnel steps (if None, funnel_steps will be used)
    include_rates : bool, default=True
        Whether to include conversion rates between steps
    cumulative : bool, default=True
        Whether to show cumulative conversion from first step
        
    Returns:
    --------
    Callable
        Function that calculates conversion funnels from a CohortPipe
    """
    def _calculate_conversion(pipe):
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
        
        # Calculate conversion metrics for each cohort
        cohorts = df[cohort_column].unique()
        all_funnel_data = []
        
        for cohort in cohorts:
            cohort_data = df[df[cohort_column] == cohort]
            
            # Count unique users at each step
            step_counts = []
            user_sets = {}
            
            for i, step in enumerate(funnel_steps):
                users_at_step = set(cohort_data[cohort_data[event_column] == step][user_id_column].unique())
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
            
            # Create row for this cohort
            cohort_funnel = {
                'cohort': cohort,
                'total_users': len(cohort_data[user_id_column].unique())
            }
            
            # Add count for each step
            for i, step in enumerate(step_labels):
                cohort_funnel[f"{step}_count"] = step_counts[i]
            
            # Add conversion rates if requested
            if include_rates:
                if cumulative:
                    # Cumulative rates from first step
                    for i, step in enumerate(step_labels):
                        if i > 0:  # Skip first step
                            cohort_funnel[f"{step}_rate"] = cumulative_rates[i]
                else:
                    # Step-to-step rates
                    for i, step in enumerate(step_labels):
                        if i > 0:  # Skip first step
                            prev_step = step_labels[i-1]
                            cohort_funnel[f"{prev_step}_to_{step}_rate"] = conversion_rates[i]
            
            all_funnel_data.append(cohort_funnel)
        
        # Create DataFrame with all cohort funnel data
        funnel_df = pd.DataFrame(all_funnel_data)
        
        # Store results
        analysis_name = f'{new_pipe.current_analysis}_conversion'
        new_pipe.cohort_results[analysis_name] = {
            'type': 'conversion',
            'cohort_column': cohort_column,
            'event_column': event_column,
            'funnel_steps': funnel_steps,
            'step_names': step_labels,
            'include_rates': include_rates,
            'cumulative': cumulative,
            'funnel_data': funnel_df
        }
        
        new_pipe.conversion_funnels[analysis_name] = funnel_df
        
        return new_pipe
    
    return _calculate_conversion


def calculate_lifetime_value(
    cohort_column: str,
    date_column: str,
    user_id_column: str,
    value_column: str,
    time_period: str = 'M',
    max_periods: int = 12,
    cumulative: bool = True,
    datetime_format: Optional[str] = None
):
    """
    Calculate lifetime value metrics for cohorts
    
    Parameters:
    -----------
    cohort_column : str
        Column containing cohort information
    date_column : str
        Column containing the date of activity
    user_id_column : str
        Column containing user identifiers
    value_column : str
        Column containing the value (revenue, etc.)
    time_period : str, default='M'
        Time period for LTV calculation ('D', 'W', 'M', 'Q', 'Y')
    max_periods : int, default=12
        Maximum number of periods to calculate LTV for
    cumulative : bool, default=True
        Whether to show cumulative LTV over time
    datetime_format : str, optional
        Format string for parsing dates if they are not already datetime objects
        
    Returns:
    --------
    Callable
        Function that calculates LTV from a CohortPipe
    """
    def _calculate_lifetime_value(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            if datetime_format:
                df[date_column] = pd.to_datetime(df[date_column], format=datetime_format)
            else:
                df[date_column] = pd.to_datetime(df[date_column])
        
        # Add period column
        if time_period == 'D':
            df['period'] = df[date_column].dt.date
        elif time_period == 'W':
            df['period'] = df[date_column].dt.to_period('W').dt.start_time
        elif time_period == 'M':
            df['period'] = df[date_column].dt.to_period('M').dt.start_time
        elif time_period == 'Q':
            df['period'] = df[date_column].dt.to_period('Q').dt.start_time
        elif time_period == 'Y':
            df['period'] = df[date_column].dt.to_period('Y').dt.start_time
        else:
            raise ValueError(f"Invalid time period: {time_period}. Use 'D', 'W', 'M', 'Q', or 'Y'.")
        
        # Group by user and find their first period (for calculating periods since first activity)
        user_first_period = df.groupby(user_id_column)['period'].min().reset_index()
        user_first_period.columns = [user_id_column, 'first_period']
        
        # Merge first period back to the original dataframe
        df = pd.merge(df, user_first_period, on=user_id_column, how='left')
        
        # Calculate periods since first activity
        df['periods_since_first'] = (df['period'] - df['first_period']).apply(lambda x: _period_diff(x, time_period))
        
        # Filter to relevant periods
        df = df[df['periods_since_first'] <= max_periods]
        
        # Calculate cohort sizes (unique users in each cohort)
        cohort_sizes = df.groupby(cohort_column)[user_id_column].nunique().reset_index()
        cohort_sizes.columns = [cohort_column, 'cohort_size']
        
        # Sum value by cohort and period
        value_by_period = df.groupby([cohort_column, 'periods_since_first'])[value_column].sum().reset_index()
        value_by_period.columns = [cohort_column, 'period', 'total_value']
        
        # Merge with cohort sizes to calculate average value per user
        ltv_data = pd.merge(value_by_period, cohort_sizes, on=cohort_column, how='left')
        ltv_data['avg_value'] = ltv_data['total_value'] / ltv_data['cohort_size']
        
        # Create LTV matrix
        if cumulative:
            # Calculate cumulative value over time
            ltv_cum = []
            
            for cohort in ltv_data[cohort_column].unique():
                cohort_ltv = ltv_data[ltv_data[cohort_column] == cohort].sort_values('period')
                cohort_ltv['cumulative_value'] = cohort_ltv['total_value'].cumsum()
                cohort_ltv['cumulative_avg_value'] = cohort_ltv['cumulative_value'] / cohort_ltv['cohort_size']
                ltv_cum.append(cohort_ltv)
                
            ltv_data_cum = pd.concat(ltv_cum)
            ltv_matrix = ltv_data_cum.pivot(index=cohort_column, columns='period', values='cumulative_avg_value')
            ltv_matrix_total = ltv_data_cum.pivot(index=cohort_column, columns='period', values='cumulative_value')
        else:
            # Non-cumulative - just the value in each period
            ltv_matrix = ltv_data.pivot(index=cohort_column, columns='period', values='avg_value')
            ltv_matrix_total = ltv_data.pivot(index=cohort_column, columns='period', values='total_value')
        
        # Format columns
        ltv_matrix.columns = [f'Period {col}' for col in ltv_matrix.columns]
        ltv_matrix_total.columns = [f'Period {col}' for col in ltv_matrix_total.columns]
        
        # Store results
        analysis_name = f'{new_pipe.current_analysis}_ltv'
        new_pipe.cohort_results[analysis_name] = {
            'type': 'ltv',
            'cohort_column': cohort_column,
            'value_column': value_column,
            'time_period': time_period,
            'cumulative': cumulative,
            'ltv_matrix': ltv_matrix,
            'ltv_matrix_total': ltv_matrix_total,
            'ltv_data': ltv_data,
            'cohort_sizes': cohort_sizes
        }
        
        return new_pipe
    
    return _calculate_lifetime_value