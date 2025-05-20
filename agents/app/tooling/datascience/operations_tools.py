import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
import warnings
import numpy as np

class OperationsPipe:
    """
    A pipeline-style operations analysis tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
        self.operations = {}
        self.comparisons = {}
        self.current_operation = None
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe OperationsPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = OperationsPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        new_pipe.operations = self.operations.copy()
        new_pipe.comparisons = self.comparisons.copy()
        new_pipe.current_operation = self.current_operation
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create an OperationsPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        return pipe


# Basic Operations Functions
def PercentChange(condition_column: str, baseline: str, output_name: Optional[str] = None):
    """
    Compute the percent change (other - baseline) / baseline
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    baseline : str
        The baseline value to compare against
    output_name : str, optional
        Name for the output operation, defaults to 'pct_change_{condition_column}_vs_{baseline}'
        
    Returns:
    --------
    Callable
        Function that calculates percent change from an OperationsPipe
    """
    def _percent_change(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column and baseline
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        if baseline not in df[condition_column].unique():
            raise ValueError(f"Baseline '{baseline}' not found in the condition column '{condition_column}'.")
        
        # Calculate the percent change
        baseline_rows = df[df[condition_column] == baseline]
        other_rows = df[df[condition_column] != baseline]
        
        # Group by any columns except the condition column
        group_cols = [col for col in df.columns if col != condition_column]
        
        # Initialize result dataframe
        result_df = pd.DataFrame()
        
        # Process each metric column (assuming numeric columns are metrics)
        metric_cols = df.select_dtypes(include=['number']).columns
        
        for metric in metric_cols:
            # Calculate baseline values
            baseline_values = baseline_rows.groupby(group_cols)[metric].mean().reset_index()
            baseline_values.rename(columns={metric: 'baseline_value'}, inplace=True)
            
            # Calculate other values
            other_values = other_rows.groupby(group_cols + [condition_column])[metric].mean().reset_index()
            
            # Merge baseline and other values
            merged = pd.merge(other_values, baseline_values, on=group_cols)
            
            # Calculate percent change
            merged[f'pct_change_{metric}'] = (merged[metric] - merged['baseline_value']) / merged['baseline_value']
            
            # Add to result
            if result_df.empty:
                result_df = merged[[*group_cols, condition_column, f'pct_change_{metric}']]
            else:
                result_df = pd.merge(result_df, merged[[*group_cols, condition_column, f'pct_change_{metric}']], 
                                   on=group_cols + [condition_column])
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"pct_change_{condition_column}_vs_{baseline}"
        
        # Store the operation
        new_pipe.operations[op_name] = result_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    return _percent_change


def AbsoluteChange(condition_column: str, baseline: str, output_name: Optional[str] = None):
    """
    Compute the absolute change (other - baseline)
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    baseline : str
        The baseline value to compare against
    output_name : str, optional
        Name for the output operation, defaults to 'abs_change_{condition_column}_vs_{baseline}'
        
    Returns:
    --------
    Callable
        Function that calculates absolute change from an OperationsPipe
    """
    def _absolute_change(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column and baseline
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        if baseline not in df[condition_column].unique():
            raise ValueError(f"Baseline '{baseline}' not found in the condition column '{condition_column}'.")
        
        # Calculate the absolute change
        baseline_rows = df[df[condition_column] == baseline]
        other_rows = df[df[condition_column] != baseline]
        
        # Group by any columns except the condition column
        group_cols = [col for col in df.columns if col != condition_column]
        
        # Initialize result dataframe
        result_df = pd.DataFrame()
        
        # Process each metric column (assuming numeric columns are metrics)
        metric_cols = df.select_dtypes(include=['number']).columns
        
        for metric in metric_cols:
            # Calculate baseline values
            baseline_values = baseline_rows.groupby(group_cols)[metric].mean().reset_index()
            baseline_values.rename(columns={metric: 'baseline_value'}, inplace=True)
            
            # Calculate other values
            other_values = other_rows.groupby(group_cols + [condition_column])[metric].mean().reset_index()
            
            # Merge baseline and other values
            merged = pd.merge(other_values, baseline_values, on=group_cols)
            
            # Calculate absolute change
            merged[f'abs_change_{metric}'] = merged[metric] - merged['baseline_value']
            
            # Add to result
            if result_df.empty:
                result_df = merged[[*group_cols, condition_column, f'abs_change_{metric}']]
            else:
                result_df = pd.merge(result_df, merged[[*group_cols, condition_column, f'abs_change_{metric}']], 
                                   on=group_cols + [condition_column])
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"abs_change_{condition_column}_vs_{baseline}"
        
        # Store the operation
        new_pipe.operations[op_name] = result_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    return _absolute_change


def MH(condition_column: str, baseline: str, stratified_by: Union[str, List[str]], output_name: Optional[str] = None):
    """
    Compute the Mantel-Haenszel estimator
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    baseline : str
        The baseline value to compare against
    stratified_by : str or List[str]
        Column(s) to stratify by when computing the MH estimator
    output_name : str, optional
        Name for the output operation, defaults to 'mh_{condition_column}_vs_{baseline}'
        
    Returns:
    --------
    Callable
        Function that calculates Mantel-Haenszel estimate from an OperationsPipe
    """
    def _mantel_haenszel(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column and baseline
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        if baseline not in df[condition_column].unique():
            raise ValueError(f"Baseline '{baseline}' not found in the condition column '{condition_column}'.")
        
        # Ensure stratified_by is a list
        strata_cols = [stratified_by] if isinstance(stratified_by, str) else stratified_by
        
        # Validate strata columns
        for col in strata_cols:
            if col not in df.columns:
                raise ValueError(f"Stratification column '{col}' not found in the data.")
        
        # Initialize result dataframe
        result_df = pd.DataFrame()
        
        # Process each metric column (assuming numeric columns are metrics)
        metric_cols = df.select_dtypes(include=['number']).columns
        
        for metric in metric_cols:
            # Calculate MH estimator
            numerator_sum = 0
            denominator_sum = 0
            
            # Calculate for each stratum
            for stratum, stratum_df in df.groupby(strata_cols):
                # Get the baseline and other rows for this stratum
                baseline_rows = stratum_df[stratum_df[condition_column] == baseline]
                other_rows = stratum_df[stratum_df[condition_column] != baseline]
                
                # Skip strata without both baseline and other condition
                if baseline_rows.empty or other_rows.empty:
                    continue
                
                # For each non-baseline condition in this stratum
                for condition, condition_df in other_rows.groupby(condition_column):
                    # Calculate weights
                    baseline_mean = baseline_rows[metric].mean()
                    condition_mean = condition_df[metric].mean()
                    
                    # Skip if baseline mean is 0 (to avoid division by zero)
                    if baseline_mean == 0:
                        continue
                    
                    weight = len(baseline_rows) * len(condition_df) / len(stratum_df)
                    
                    # Add to sums
                    numerator_sum += weight * condition_mean
                    denominator_sum += weight * baseline_mean
            
            # Calculate MH estimate
            if denominator_sum == 0:
                mh_estimate = float('nan')
            else:
                mh_estimate = numerator_sum / denominator_sum
            
            # Create result row
            result_row = pd.DataFrame({
                'metric': [metric],
                'mh_estimate': [mh_estimate],
                'percent_change': [(mh_estimate - 1) * 100 if not pd.isna(mh_estimate) else float('nan')]
            })
            
            # Add to result
            result_df = pd.concat([result_df, result_row])
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"mh_{condition_column}_vs_{baseline}"
        
        # Store the operation
        new_pipe.operations[op_name] = result_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    return _mantel_haenszel


def CUPED(condition_column: str, baseline: str, covariates: Union[str, List[str]], 
         stratified_by: Optional[Union[str, List[str]]] = None, output_name: Optional[str] = None):
    """
    Compute the absolute change adjusted using the CUPED approach
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    baseline : str
        The baseline value to compare against
    covariates : str or List[str]
        Column(s) to use as covariates for adjustment
    stratified_by : str or List[str], optional
        Column(s) to stratify by when computing the adjustment
    output_name : str, optional
        Name for the output operation, defaults to 'cuped_{condition_column}_vs_{baseline}'
        
    Returns:
    --------
    Callable
        Function that calculates CUPED adjustment from an OperationsPipe
    """
    def _cuped(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column and baseline
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        if baseline not in df[condition_column].unique():
            raise ValueError(f"Baseline '{baseline}' not found in the condition column '{condition_column}'.")
        
        # Ensure covariates is a list
        covariate_cols = [covariates] if isinstance(covariates, str) else covariates
        
        # Validate covariate columns
        for col in covariate_cols:
            if col not in df.columns:
                raise ValueError(f"Covariate column '{col}' not found in the data.")
        
        # Initialize strata columns if provided
        strata_cols = []
        if stratified_by:
            strata_cols = [stratified_by] if isinstance(stratified_by, str) else stratified_by
            
            # Validate strata columns
            for col in strata_cols:
                if col not in df.columns:
                    raise ValueError(f"Stratification column '{col}' not found in the data.")
        
        # Initialize result dataframe
        result_df = pd.DataFrame()
        
        # Process each metric column (assuming numeric columns are metrics)
        metric_cols = df.select_dtypes(include=['number']).columns
        metric_cols = [col for col in metric_cols if col not in covariate_cols]  # Exclude covariates
        
        # If stratified, apply CUPED within each stratum
        if strata_cols:
            for stratum, stratum_df in df.groupby(strata_cols):
                stratum_result = _apply_cuped(stratum_df, condition_column, baseline, covariate_cols, metric_cols)
                
                # Add stratum information
                for i, col in enumerate(strata_cols):
                    stratum_result[col] = stratum[i] if isinstance(stratum, tuple) else stratum
                
                # Add to result
                result_df = pd.concat([result_df, stratum_result])
        else:
            # Apply CUPED to the entire dataset
            result_df = _apply_cuped(df, condition_column, baseline, covariate_cols, metric_cols)
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"cuped_{condition_column}_vs_{baseline}"
        
        # Store the operation
        new_pipe.operations[op_name] = result_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    def _apply_cuped(df, condition_column, baseline, covariate_cols, metric_cols):
        """Helper function to apply CUPED within a dataframe"""
        # Get baseline and treatment data
        baseline_df = df[df[condition_column] == baseline]
        treatment_groups = df[df[condition_column] != baseline][condition_column].unique()
        
        cuped_results = []
        
        for treatment in treatment_groups:
            treatment_df = df[df[condition_column] == treatment]
            
            for metric in metric_cols:
                # Skip if either baseline or treatment is empty
                if baseline_df.empty or treatment_df.empty:
                    continue
                
                # Calculate baseline and treatment means
                baseline_mean = baseline_df[metric].mean()
                treatment_mean = treatment_df[metric].mean()
                
                # Calculate covariance and theta for each covariate
                adjusted_treatment_mean = treatment_mean
                
                for covariate in covariate_cols:
                    # Skip if covariate is the same as the metric
                    if covariate == metric:
                        continue
                    
                    # Calculate means for the covariate
                    baseline_cov_mean = baseline_df[covariate].mean()
                    treatment_cov_mean = treatment_df[covariate].mean()
                    
                    # Calculate variance and covariance in baseline
                    var_cov = np.var(baseline_df[covariate], ddof=1)
                    cov_metric_cov = np.cov(
                        baseline_df[metric], 
                        baseline_df[covariate], 
                        ddof=1
                    )[0, 1]
                    
                    # Calculate theta (adjustment factor)
                    if var_cov == 0:
                        theta = 0  # Avoid division by zero
                    else:
                        theta = cov_metric_cov / var_cov
                    
                    # Adjust the treatment mean
                    adjustment = theta * (treatment_cov_mean - baseline_cov_mean)
                    adjusted_treatment_mean -= adjustment
                
                # Calculate absolute and percent change
                abs_change = adjusted_treatment_mean - baseline_mean
                pct_change = abs_change / baseline_mean if baseline_mean != 0 else float('nan')
                
                # Add result
                cuped_results.append({
                    condition_column: treatment,
                    'metric': metric,
                    'baseline_mean': baseline_mean,
                    'treatment_mean': treatment_mean,
                    'adjusted_treatment_mean': adjusted_treatment_mean,
                    'absolute_change': abs_change,
                    'percent_change': pct_change * 100  # Convert to percentage
                })
        
        return pd.DataFrame(cuped_results)
    
    return _cuped


def PrePostChange(condition_column: str, baseline: str, covariates: Union[str, List[str]],
                stratified_by: Optional[Union[str, List[str]]] = None, output_name: Optional[str] = None):
    """
    Compute the percent change adjusted using the PrePost approach
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    baseline : str
        The baseline value to compare against
    covariates : str or List[str]
        Column(s) to use as pre-treatment covariates
    stratified_by : str or List[str], optional
        Column(s) to stratify by when computing the adjustment
    output_name : str, optional
        Name for the output operation, defaults to 'prepost_{condition_column}_vs_{baseline}'
        
    Returns:
    --------
    Callable
        Function that calculates PrePost adjustment from an OperationsPipe
    """
    def _prepost_change(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column and baseline
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        if baseline not in df[condition_column].unique():
            raise ValueError(f"Baseline '{baseline}' not found in the condition column '{condition_column}'.")
        
        # Ensure covariates is a list
        covariate_cols = [covariates] if isinstance(covariates, str) else covariates
        
        # Validate covariate columns
        for col in covariate_cols:
            if col not in df.columns:
                raise ValueError(f"Covariate column '{col}' not found in the data.")
        
        # Initialize strata columns if provided
        strata_cols = []
        if stratified_by:
            strata_cols = [stratified_by] if isinstance(stratified_by, str) else stratified_by
            
            # Validate strata columns
            for col in strata_cols:
                if col not in df.columns:
                    raise ValueError(f"Stratification column '{col}' not found in the data.")
        
        # Initialize result dataframe
        result_df = pd.DataFrame()
        
        # Process each metric column (assuming numeric columns are metrics)
        metric_cols = df.select_dtypes(include=['number']).columns
        metric_cols = [col for col in metric_cols if col not in covariate_cols]  # Exclude covariates
        
        # If stratified, apply PrePost within each stratum
        if strata_cols:
            for stratum, stratum_df in df.groupby(strata_cols):
                stratum_result = _apply_prepost(stratum_df, condition_column, baseline, covariate_cols, metric_cols)
                
                # Add stratum information
                for i, col in enumerate(strata_cols):
                    stratum_result[col] = stratum[i] if isinstance(stratum, tuple) else stratum
                
                # Add to result
                result_df = pd.concat([result_df, stratum_result])
        else:
            # Apply PrePost to the entire dataset
            result_df = _apply_prepost(df, condition_column, baseline, covariate_cols, metric_cols)
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"prepost_{condition_column}_vs_{baseline}"
        
        # Store the operation
        new_pipe.operations[op_name] = result_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    def _apply_prepost(df, condition_column, baseline, covariate_cols, metric_cols):
        """Helper function to apply PrePost within a dataframe"""
        # Get baseline and treatment data
        baseline_df = df[df[condition_column] == baseline]
        treatment_groups = df[df[condition_column] != baseline][condition_column].unique()
        
        prepost_results = []
        
        for treatment in treatment_groups:
            treatment_df = df[df[condition_column] == treatment]
            
            for metric in metric_cols:
                # Skip if either baseline or treatment is empty
                if baseline_df.empty or treatment_df.empty:
                    continue
                
                # Calculate baseline and treatment means
                baseline_mean = baseline_df[metric].mean()
                treatment_mean = treatment_df[metric].mean()
                
                # Calculate PrePost adjustment for each pre-treatment covariate
                adjusted_pct_change = (treatment_mean - baseline_mean) / baseline_mean if baseline_mean != 0 else float('nan')
                
                for covariate in covariate_cols:
                    # Skip if covariate is the same as the metric
                    if covariate == metric:
                        continue
                    
                    # Calculate pre-treatment means for both groups
                    baseline_pre = baseline_df[covariate].mean()
                    treatment_pre = treatment_df[covariate].mean()
                    
                    # Skip if pre-treatment means are identical
                    if baseline_pre == treatment_pre:
                        continue
                    
                    # Calculate pre-treatment difference percentage
                    pre_diff_pct = (treatment_pre - baseline_pre) / baseline_pre if baseline_pre != 0 else float('nan')
                    
                    # Adjust the percent change if pre differences exist
                    if not pd.isna(pre_diff_pct) and not pd.isna(adjusted_pct_change):
                        adjusted_pct_change -= pre_diff_pct
                
                # Convert to percentage
                adjusted_pct_change = adjusted_pct_change * 100 if not pd.isna(adjusted_pct_change) else float('nan')
                
                # Calculate raw percent change
                raw_pct_change = ((treatment_mean - baseline_mean) / baseline_mean) * 100 if baseline_mean != 0 else float('nan')
                
                # Add result
                prepost_results.append({
                    condition_column: treatment,
                    'metric': metric,
                    'baseline_mean': baseline_mean,
                    'treatment_mean': treatment_mean,
                    'raw_percent_change': raw_pct_change,
                    'adjusted_percent_change': adjusted_pct_change
                })
        
        return pd.DataFrame(prepost_results)
    
    return _prepost_change


# Additional helper functions
def FilterConditions(conditions: List[str], output_name: Optional[str] = None):
    """
    Filter the data to include only specified conditions
    
    Parameters:
    -----------
    conditions : List[str]
        List of condition values to keep
    output_name : str, optional
        Name for the output operation, defaults to 'filtered_conditions'
        
    Returns:
    --------
    Callable
        Function that filters conditions from an OperationsPipe
    """
    def _filter_conditions(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Find condition column by examining the data
        # This assumes condition column is the one with categorical/string values that match conditions
        condition_cols = []
        for col in df.columns:
            if df[col].dtype == 'object' or pd.api.types.is_categorical_dtype(df[col]):
                matches = sum(df[col].isin(conditions))
                if matches > 0:
                    condition_cols.append((col, matches))
        
        if not condition_cols:
            raise ValueError(f"No columns found with values matching the specified conditions: {conditions}")
        
        # Use the column with the most matches
        condition_cols.sort(key=lambda x: x[1], reverse=True)
        condition_column = condition_cols[0][0]
        
        # Filter the data
        filtered_df = df[df[condition_column].isin(conditions)]
        
        if filtered_df.empty:
            warnings.warn(f"No data remains after filtering for conditions: {conditions}")
        
        # Generate output name if not provided
        op_name = output_name if output_name else "filtered_conditions"
        
        # Update the data
        new_pipe.data = filtered_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    return _filter_conditions


def PowerAnalysis(condition_column: str, baseline: str, metric_column: str, 
                 alpha: float = 0.05, power: float = 0.8, output_name: Optional[str] = None):
    """
    Perform power analysis to determine sample size requirements
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    baseline : str
        The baseline value to compare against
    metric_column : str
        The metric to analyze
    alpha : float, default=0.05
        Significance level
    power : float, default=0.8
        Desired statistical power
    output_name : str, optional
        Name for the output operation, defaults to 'power_analysis_{metric_column}'
        
    Returns:
    --------
    Callable
        Function that performs power analysis from an OperationsPipe
    """
    def _power_analysis(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column and baseline
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        if baseline not in df[condition_column].unique():
            raise ValueError(f"Baseline '{baseline}' not found in the condition column '{condition_column}'.")
        
        if metric_column not in df.columns:
            raise ValueError(f"Metric column '{metric_column}' not found in the data.")
        
        # Get baseline data
        baseline_data = df[df[condition_column] == baseline][metric_column]
        
        if baseline_data.empty:
            raise ValueError(f"No data found for baseline '{baseline}'.")
        
        # Calculate baseline statistics
        baseline_mean = baseline_data.mean()
        baseline_std = baseline_data.std()
        
        # Get treatment groups
        treatment_groups = df[df[condition_column] != baseline][condition_column].unique()
        
        power_results = []
        
        from scipy import stats
        
        for treatment in treatment_groups:
            treatment_data = df[df[condition_column] == treatment][metric_column]
            
            if treatment_data.empty:
                continue
            
            # Calculate treatment statistics
            treatment_mean = treatment_data.mean()
            treatment_std = treatment_data.std()
            
            # Calculate effect size (Cohen's d)
            pooled_std = np.sqrt((baseline_std**2 + treatment_std**2) / 2)
            effect_size = abs(treatment_mean - baseline_mean) / pooled_std
            
            # Calculate required sample size
            # Using the formula for two-sample t-test
            z_alpha = stats.norm.ppf(1 - alpha/2)
            z_power = stats.norm.ppf(power)
            
            required_n = 2 * ((z_alpha + z_power) / effect_size)**2
            
            # Round up to the nearest integer
            required_n = int(np.ceil(required_n))
            
            # Calculate actual power with current sample sizes
            n1 = len(baseline_data)
            n2 = len(treatment_data)
            
            # Calculate non-centrality parameter
            ncp = effect_size * np.sqrt((n1 * n2) / (n1 + n2))
            
            # Calculate critical value
            df_total = n1 + n2 - 2
            t_crit = stats.t.ppf(1 - alpha/2, df_total)
            
            # Calculate actual power
            actual_power = 1 - stats.nct.cdf(t_crit, df_total, ncp)
            
            # Add to results
            power_results.append({
                'treatment': treatment,
                'baseline_mean': baseline_mean,
                'treatment_mean': treatment_mean,
                'effect_size': effect_size,
                'current_baseline_n': n1,
                'current_treatment_n': n2,
                'required_n_per_group': required_n,
                'actual_power': actual_power
            })
        
        # Convert to dataframe
        power_df = pd.DataFrame(power_results)
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"power_analysis_{metric_column}"
        
        # Store the operation
        new_pipe.operations[op_name] = power_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    return _power_analysis


def StratifiedSummary(condition_column: str, stratified_by: Union[str, List[str]], 
                     metrics: Optional[List[str]] = None, output_name: Optional[str] = None):
    """
    Create a summary of metrics stratified by specified columns
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    stratified_by : str or List[str]
        Column(s) to stratify by
    metrics : List[str], optional
        List of metric columns to include (if None, all numeric columns are used)
    output_name : str, optional
        Name for the output operation, defaults to 'stratified_summary'
        
    Returns:
    --------
    Callable
        Function that creates a stratified summary from an OperationsPipe
    """
    def _stratified_summary(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        # Ensure stratified_by is a list
        strata_cols = [stratified_by] if isinstance(stratified_by, str) else stratified_by
        
        # Validate strata columns
        for col in strata_cols:
            if col not in df.columns:
                raise ValueError(f"Stratification column '{col}' not found in the data.")
        
        # Determine metrics to include
        if metrics is None:
            # Use all numeric columns except the condition and strata columns
            metric_cols = df.select_dtypes(include=['number']).columns.tolist()
            metric_cols = [col for col in metric_cols if col not in [condition_column] + strata_cols]
        else:
            # Use specified metrics
            metric_cols = metrics
            # Validate metric columns
            for col in metric_cols:
                if col not in df.columns:
                    raise ValueError(f"Metric column '{col}' not found in the data.")
        
        # Create summary dataframe
        summary_data = []
        
        # For each stratum
        for stratum_values, stratum_df in df.groupby(strata_cols):
            # Convert to tuple if single value
            if not isinstance(stratum_values, tuple):
                stratum_values = (stratum_values,)
            
            # For each condition
            for condition, condition_df in stratum_df.groupby(condition_column):
                # For each metric
                for metric in metric_cols:
                    # Calculate summary statistics
                    values = condition_df[metric]
                    summary = {
                        'count': len(values),
                        'mean': values.mean(),
                        'std': values.std(),
                        'min': values.min(),
                        'q25': values.quantile(0.25),
                        'median': values.median(),
                        'q75': values.quantile(0.75),
                        'max': values.max()
                    }
                    
                    # Create row
                    row = {
                        condition_column: condition,
                        'metric': metric
                    }
                    
                    # Add stratum values
                    for i, col in enumerate(strata_cols):
                        row[col] = stratum_values[i]
                    
                    # Add summary statistics
                    for stat, value in summary.items():
                        row[stat] = value
                    
                    summary_data.append(row)
        
        # Convert to dataframe
        summary_df = pd.DataFrame(summary_data)
        
        # Generate output name if not provided
        op_name = output_name if output_name else "stratified_summary"
        
        # Store the operation
        new_pipe.operations[op_name] = summary_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    return _stratified_summary


def BootstrapCI(condition_column: str, baseline: str, metric_column: str, 
               confidence: float = 0.95, n_bootstraps: int = 1000, 
               stratified_by: Optional[Union[str, List[str]]] = None,
               output_name: Optional[str] = None):
    """
    Calculate bootstrap confidence intervals for the difference in means
    
    Parameters:
    -----------
    condition_column : str
        Column containing the condition values
    baseline : str
        The baseline value to compare against
    metric_column : str
        The metric to analyze
    confidence : float, default=0.95
        Confidence level for the intervals
    n_bootstraps : int, default=1000
        Number of bootstrap samples to generate
    stratified_by : str or List[str], optional
        Column(s) to stratify by when computing the intervals
    output_name : str, optional
        Name for the output operation, defaults to 'bootstrap_ci_{metric_column}'
        
    Returns:
    --------
    Callable
        Function that calculates bootstrap CIs from an OperationsPipe
    """
    def _bootstrap_ci(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the condition column and baseline
        if condition_column not in df.columns:
            raise ValueError(f"Condition column '{condition_column}' not found in the data.")
        
        if baseline not in df[condition_column].unique():
            raise ValueError(f"Baseline '{baseline}' not found in the condition column '{condition_column}'.")
        
        if metric_column not in df.columns:
            raise ValueError(f"Metric column '{metric_column}' not found in the data.")
        
        # Initialize strata columns if provided
        strata_cols = []
        if stratified_by:
            strata_cols = [stratified_by] if isinstance(stratified_by, str) else stratified_by
            
            # Validate strata columns
            for col in strata_cols:
                if col not in df.columns:
                    raise ValueError(f"Stratification column '{col}' not found in the data.")
        
        # Initialize result dataframe
        result_df = pd.DataFrame()
        
        # If stratified, apply bootstrap within each stratum
        if strata_cols:
            for stratum, stratum_df in df.groupby(strata_cols):
                stratum_result = _apply_bootstrap(
                    stratum_df, condition_column, baseline, metric_column, 
                    confidence, n_bootstraps
                )
                
                # Add stratum information
                if isinstance(stratum, tuple):
                    for i, col in enumerate(strata_cols):
                        stratum_result[col] = stratum[i]
                else:
                    stratum_result[strata_cols[0]] = stratum
                
                # Add to result
                result_df = pd.concat([result_df, stratum_result])
        else:
            # Apply bootstrap to the entire dataset
            result_df = _apply_bootstrap(
                df, condition_column, baseline, metric_column, 
                confidence, n_bootstraps
            )
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"bootstrap_ci_{metric_column}"
        
        # Store the operation
        new_pipe.operations[op_name] = result_df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    def _apply_bootstrap(df, condition_column, baseline, metric_column, confidence, n_bootstraps):
        """Helper function to apply bootstrap within a dataframe"""
        
        
        # Get baseline data
        baseline_data = df[df[condition_column] == baseline][metric_column].dropna().values
        
        if len(baseline_data) == 0:
            warnings.warn(f"No data found for baseline '{baseline}'.")
            return pd.DataFrame()
        
        # Get treatment groups
        treatment_groups = df[df[condition_column] != baseline][condition_column].unique()
        
        bootstrap_results = []
        
        for treatment in treatment_groups:
            treatment_data = df[df[condition_column] == treatment][metric_column].dropna().values
            
            if len(treatment_data) == 0:
                warnings.warn(f"No data found for treatment '{treatment}'.")
                continue
            
            # Calculate observed difference
            observed_diff = np.mean(treatment_data) - np.mean(baseline_data)
            
            # Bootstrap the difference
            bootstrap_diffs = []
            for _ in range(n_bootstraps):
                # Resample with replacement
                bs_baseline = np.random.choice(baseline_data, size=len(baseline_data), replace=True)
                bs_treatment = np.random.choice(treatment_data, size=len(treatment_data), replace=True)
                
                # Calculate difference
                bs_diff = np.mean(bs_treatment) - np.mean(bs_baseline)
                bootstrap_diffs.append(bs_diff)
            
            # Calculate confidence interval
            alpha = 1 - confidence
            lower_ci = np.percentile(bootstrap_diffs, alpha/2 * 100)
            upper_ci = np.percentile(bootstrap_diffs, (1 - alpha/2) * 100)
            
            # Calculate p-value (two-sided)
            if observed_diff > 0:
                p_value = 2 * sum(bs_diff <= 0 for bs_diff in bootstrap_diffs) / n_bootstraps
            else:
                p_value = 2 * sum(bs_diff >= 0 for bs_diff in bootstrap_diffs) / n_bootstraps
            
            # Add to results
            bootstrap_results.append({
                condition_column: treatment,
                'baseline_mean': np.mean(baseline_data),
                'treatment_mean': np.mean(treatment_data),
                'observed_diff': observed_diff,
                'lower_ci': lower_ci,
                'upper_ci': upper_ci,
                'p_value': p_value,
                'significant': p_value < (1 - confidence),
                'baseline_n': len(baseline_data),
                'treatment_n': len(treatment_data)
            })
        
        return pd.DataFrame(bootstrap_results)
    
    return _bootstrap_ci


def MultiComparisonAdjustment(p_value_column: str, method: str = 'bonferroni', 
                             output_name: Optional[str] = None):
    """
    Apply multiple comparison adjustment to p-values
    
    Parameters:
    -----------
    p_value_column : str
        Column containing the p-values to adjust
    method : str, default='bonferroni'
        Method to use for adjustment ('bonferroni', 'fdr', 'sidak')
    output_name : str, optional
        Name for the output operation, defaults to 'adjusted_{method}'
        
    Returns:
    --------
    Callable
        Function that adjusts p-values from an OperationsPipe
    """
    def _multi_comparison_adjustment(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate the p-value column
        if p_value_column not in df.columns:
            raise ValueError(f"P-value column '{p_value_column}' not found in the data.")
        
        # Validate method
        valid_methods = ['bonferroni', 'fdr', 'sidak', 'holm']
        if method.lower() not in valid_methods:
            raise ValueError(f"Invalid method: {method}. Use one of {valid_methods}")
        
        # Get p-values
        p_values = df[p_value_column].values
        
        # Apply adjustment
        if method.lower() == 'bonferroni':
            adjusted_p = np.minimum(p_values * len(p_values), 1.0)
        elif method.lower() == 'sidak':
            adjusted_p = 1.0 - (1.0 - p_values) ** len(p_values)
        elif method.lower() == 'fdr':
            # Benjamini-Hochberg procedure
            n = len(p_values)
            sorted_idx = np.argsort(p_values)
            sorted_p = p_values[sorted_idx]
            
            # Calculate adjusted p-values
            adjusted_sorted_p = np.zeros_like(sorted_p)
            for i in range(n-1, -1, -1):
                if i == n-1:
                    adjusted_sorted_p[i] = sorted_p[i]
                else:
                    adjusted_sorted_p[i] = min(sorted_p[i] * n / (i + 1), adjusted_sorted_p[i+1])
            
            # Restore original order
            inverse_idx = np.argsort(sorted_idx)
            adjusted_p = adjusted_sorted_p[inverse_idx]
        elif method.lower() == 'holm':
            # Holm-Bonferroni method
            n = len(p_values)
            sorted_idx = np.argsort(p_values)
            sorted_p = p_values[sorted_idx]
            
            # Calculate adjusted p-values
            adjusted_sorted_p = np.zeros_like(sorted_p)
            for i in range(n):
                adjusted_sorted_p[i] = min(sorted_p[i] * (n - i), 1.0)
                
            # Make sure p-values are monotonically increasing
            for i in range(1, n):
                adjusted_sorted_p[i] = max(adjusted_sorted_p[i], adjusted_sorted_p[i-1])
            
            # Restore original order
            inverse_idx = np.argsort(sorted_idx)
            adjusted_p = adjusted_sorted_p[inverse_idx]
        
        # Add adjusted p-values to the dataframe
        adjusted_col = f"adjusted_p_{method.lower()}"
        df[adjusted_col] = adjusted_p
        
        # Add significance indicator
        df[f"significant_{method.lower()}"] = df[adjusted_col] < 0.05
        
        # Generate output name if not provided
        op_name = output_name if output_name else f"adjusted_{method.lower()}"
        
        # Update the data
        new_pipe.data = df
        new_pipe.current_operation = op_name
        
        return new_pipe
    
    return _multi_comparison_adjustment





# Output and display functions
def ExecuteOperations():
    """
    Execute the operations pipeline and return all calculated operations
    
    Returns:
    --------
    Callable
        Function that returns all operations from an OperationsPipe
    """
    def _execute_operations(pipe):
        # Simply return the operations
        return pipe.operations
    
    return _execute_operations


def ShowOperation(operation_name: Optional[str] = None):
    """
    Show a specific operation or the last created one
    
    Parameters:
    -----------
    operation_name : str, optional
        Name of the operation to show
        
    Returns:
    --------
    Callable
        Function that returns an operation from an OperationsPipe
    """
    def _show_operation(pipe):
        if not pipe.operations:
            raise ValueError("No operations found in the pipeline.")
        
        # Determine which operation to show
        if operation_name:
            if operation_name not in pipe.operations:
                raise ValueError(f"Operation '{operation_name}' not found.")
            return pipe.operations[operation_name]
        else:
            # Show the most recent operation
            return pipe.operations[pipe.current_operation]
    
    return _show_operation


def ShowComparison(comparison_name: Optional[str] = None):
    """
    Show a specific comparison or the last created one
    
    Parameters:
    -----------
    comparison_name : str, optional
        Name of the comparison to show
        
    Returns:
    --------
    Callable
        Function that returns a comparison from an OperationsPipe
    """
    def _show_comparison(pipe):
        if not pipe.comparisons:
            raise ValueError("No comparisons found in the pipeline.")
        
        # Determine which comparison to show
        if comparison_name:
            if comparison_name not in pipe.comparisons:
                raise ValueError(f"Comparison '{comparison_name}' not found.")
            return pipe.comparisons[comparison_name]
        else:
            # Show the most recent comparison
            return pipe.comparisons[next(reversed(pipe.comparisons))]
    
    return _show_comparison


