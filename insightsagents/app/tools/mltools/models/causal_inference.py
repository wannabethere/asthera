import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
from scipy import stats
from scipy.stats import ttest_ind, chi2_contingency, kstest
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from datetime import datetime
import itertools
from statsmodels.stats.power import ttest_power, tt_solve_power
from statsmodels.stats.multitest import multipletests


class CausalPipe:
    """
    A pipeline-style causal inference tool that enables functional composition
    with a meterstick-like interface for causal analysis and A/B testing.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
        self.original_data = None
        self.treatment_column = None
        self.outcome_column = None
        self.covariate_columns = []
        self.propensity_models = {}
        self.outcome_models = {}
        self.treatment_effects = {}
        self.matched_data = {}
        self.balance_tests = {}
        self.sensitivity_analysis = {}
        self.ab_test_results = {}
        self.power_analysis = {}
        self.current_analysis = None
        self.causal_graphs = {}
        self.instrumental_variables = {}
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe CausalPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = CausalPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        if self.original_data is not None:
            new_pipe.original_data = self.original_data.copy()
        new_pipe.treatment_column = self.treatment_column
        new_pipe.outcome_column = self.outcome_column
        new_pipe.covariate_columns = self.covariate_columns.copy()
        new_pipe.propensity_models = self.propensity_models.copy()
        new_pipe.outcome_models = self.outcome_models.copy()
        new_pipe.treatment_effects = self.treatment_effects.copy()
        new_pipe.matched_data = self.matched_data.copy()
        new_pipe.balance_tests = self.balance_tests.copy()
        new_pipe.sensitivity_analysis = self.sensitivity_analysis.copy()
        new_pipe.ab_test_results = self.ab_test_results.copy()
        new_pipe.power_analysis = self.power_analysis.copy()
        new_pipe.current_analysis = self.current_analysis
        new_pipe.causal_graphs = self.causal_graphs.copy()
        new_pipe.instrumental_variables = self.instrumental_variables.copy()
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create a CausalPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        pipe.original_data = df.copy()
        return pipe


# Data Preparation Functions
def prepare_causal_data(
    treatment_column: str,
    outcome_column: str,
    covariate_columns: List[str],
    treatment_values: Optional[Tuple] = None,
    handle_missing: str = 'drop',
    standardize_covariates: bool = True
):
    """
    Prepare data for causal inference analysis
    
    Parameters:
    -----------
    treatment_column : str
        Name of treatment/intervention column
    outcome_column : str
        Name of outcome variable column
    covariate_columns : List[str]
        List of covariate/confounding variable columns
    treatment_values : Optional[Tuple]
        Tuple of (control_value, treatment_value) for binary treatment
    handle_missing : str
        How to handle missing values ('drop', 'impute')
    standardize_covariates : bool
        Whether to standardize covariate columns
        
    Returns:
    --------
    Callable
        Function that prepares causal data from a CausalPipe
    """
    def _prepare_causal_data(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()
        
        # Validate required columns exist
        required_cols = [treatment_column, outcome_column] + covariate_columns
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing columns: {missing_cols}")
        
        # Handle missing values
        if handle_missing == 'drop':
            df = df[required_cols].dropna()
        elif handle_missing == 'impute':
            for col in covariate_columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].median())
                else:
                    df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else 'unknown')
        
        # Process treatment variable
        if treatment_values:
            control_val, treatment_val = treatment_values
            df = df[df[treatment_column].isin([control_val, treatment_val])]
            df[treatment_column] = (df[treatment_column] == treatment_val).astype(int)
        else:
            # Assume binary treatment (0/1)
            unique_treatments = df[treatment_column].unique()
            if len(unique_treatments) != 2:
                raise ValueError(f"Treatment must be binary. Found values: {unique_treatments}")
            df[treatment_column] = df[treatment_column].astype(int)
        
        # Standardize covariates if requested
        if standardize_covariates:
            scaler = StandardScaler()
            numeric_covariates = [col for col in covariate_columns 
                                if pd.api.types.is_numeric_dtype(df[col])]
            if numeric_covariates:
                df[numeric_covariates] = scaler.fit_transform(df[numeric_covariates])
        
        # Store configuration
        new_pipe.data = df
        new_pipe.treatment_column = treatment_column
        new_pipe.outcome_column = outcome_column
        new_pipe.covariate_columns = covariate_columns
        new_pipe.current_analysis = 'causal_data_preparation'
        
        return new_pipe
    
    return _prepare_causal_data


# Propensity Score Methods
def estimate_propensity_scores(
    method: str = 'logistic',
    model_params: Optional[Dict] = None,
    model_name: str = 'propensity_model'
):
    """
    Estimate propensity scores (probability of treatment assignment)
    
    Parameters:
    -----------
    method : str
        Method for propensity score estimation ('logistic', 'random_forest')
    model_params : Optional[Dict]
        Parameters for the propensity model
    model_name : str
        Name to store the model under
        
    Returns:
    --------
    Callable
        Function that estimates propensity scores from a CausalPipe
    """
    def _estimate_propensity_scores(pipe):
        if pipe.treatment_column is None or not pipe.covariate_columns:
            raise ValueError("Treatment and covariates must be defined. Run prepare_causal_data first.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        X = df[new_pipe.covariate_columns]
        y = df[new_pipe.treatment_column]
        
        # Select and configure model
        if method == 'logistic':
            model = LogisticRegression(**(model_params or {}))
        elif method == 'random_forest':
            model = RandomForestClassifier(**(model_params or {'n_estimators': 100, 'random_state': 42}))
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Fit propensity model
        model.fit(X, y)
        
        # Predict propensity scores
        propensity_scores = model.predict_proba(X)[:, 1]  # Probability of treatment
        new_pipe.data['propensity_score'] = propensity_scores
        
        # Store model
        new_pipe.propensity_models[model_name] = {
            'model': model,
            'method': method,
            'auc_score': roc_auc_score(y, propensity_scores)
        }
        
        new_pipe.current_analysis = f'propensity_estimation_{model_name}'
        
        return new_pipe
    
    return _estimate_propensity_scores


def apply_matching(
    method: str = 'nearest_neighbor',
    n_neighbors: int = 1,
    caliper: Optional[float] = None,
    replacement: bool = False,
    matching_name: str = 'matched_sample'
):
    """
    Apply matching methods for causal inference
    
    Parameters:
    -----------
    method : str
        Matching method ('nearest_neighbor', 'radius', 'stratified')
    n_neighbors : int
        Number of neighbors for nearest neighbor matching
    caliper : Optional[float]
        Maximum distance for matches
    replacement : bool
        Whether to allow matching with replacement
    matching_name : str
        Name to store matching results under
        
    Returns:
    --------
    Callable
        Function that applies matching from a CausalPipe
    """
    def _apply_matching(pipe):
        if 'propensity_score' not in pipe.data.columns:
            raise ValueError("Propensity scores not found. Run estimate_propensity_scores first.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        treated = df[df[new_pipe.treatment_column] == 1]
        control = df[df[new_pipe.treatment_column] == 0]
        
        if method == 'nearest_neighbor':
            # Nearest neighbor matching on propensity scores
            nn_model = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean')
            nn_model.fit(control[['propensity_score']].values)
            
            matched_indices = []
            matched_distances = []
            
            for idx, treated_score in treated['propensity_score'].items():
                distances, indices = nn_model.kneighbors([[treated_score]])
                
                # Apply caliper constraint if specified
                if caliper is not None:
                    valid_matches = distances[0] <= caliper
                    if not valid_matches.any():
                        continue  # Skip if no valid matches within caliper
                    indices = indices[0][valid_matches]
                    distances = distances[0][valid_matches]
                else:
                    indices = indices[0]
                    distances = distances[0]
                
                for match_idx, distance in zip(indices, distances):
                    control_idx = control.iloc[match_idx].name
                    matched_indices.append((idx, control_idx))
                    matched_distances.append(distance)
            
            # Create matched dataset
            treated_matched_idx = [pair[0] for pair in matched_indices]
            control_matched_idx = [pair[1] for pair in matched_indices]
            
            matched_df = pd.concat([
                df.loc[treated_matched_idx],
                df.loc[control_matched_idx]
            ]).reset_index(drop=True)
            
        elif method == 'stratified':
            # Stratified matching based on propensity score quintiles
            df['ps_stratum'] = pd.qcut(df['propensity_score'], q=5, labels=False, duplicates='drop')
            
            matched_dfs = []
            for stratum in df['ps_stratum'].unique():
                stratum_data = df[df['ps_stratum'] == stratum]
                treated_stratum = stratum_data[stratum_data[new_pipe.treatment_column] == 1]
                control_stratum = stratum_data[stratum_data[new_pipe.treatment_column] == 0]
                
                # Sample equal numbers from each group within stratum
                min_size = min(len(treated_stratum), len(control_stratum))
                if min_size > 0:
                    treated_sample = treated_stratum.sample(n=min_size, random_state=42)
                    control_sample = control_stratum.sample(n=min_size, random_state=42)
                    matched_dfs.append(pd.concat([treated_sample, control_sample]))
            
            matched_df = pd.concat(matched_dfs, ignore_index=True) if matched_dfs else pd.DataFrame()
            matched_distances = None
        
        else:
            raise ValueError(f"Unknown matching method: {method}")
        
        # Store matched data and results
        new_pipe.matched_data[matching_name] = {
            'data': matched_df,
            'method': method,
            'n_treated': len(matched_df[matched_df[new_pipe.treatment_column] == 1]),
            'n_control': len(matched_df[matched_df[new_pipe.treatment_column] == 0]),
            'matching_quality': matched_distances
        }
        
        new_pipe.current_analysis = f'matching_{matching_name}'
        
        return new_pipe
    
    return _apply_matching


# Treatment Effect Estimation
def estimate_treatment_effects(
    methods: List[str] = ['ate', 'att', 'doubly_robust'],
    outcome_model: str = 'linear',
    confidence_level: float = 0.95,
    analysis_name: str = 'treatment_effects'
):
    """
    Estimate various treatment effects
    
    Parameters:
    -----------
    methods : List[str]
        Treatment effect estimation methods ('ate', 'att', 'doubly_robust', 'ipw')
    outcome_model : str
        Model type for outcome regression ('linear', 'random_forest')
    confidence_level : float
        Confidence level for intervals
    analysis_name : str
        Name to store analysis under
        
    Returns:
    --------
    Callable
        Function that estimates treatment effects from a CausalPipe
    """
    def _estimate_treatment_effects(pipe):
        if pipe.treatment_column is None or pipe.outcome_column is None:
            raise ValueError("Treatment and outcome must be defined.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        results = {}
        
        # Prepare data
        X = df[new_pipe.covariate_columns] if new_pipe.covariate_columns else pd.DataFrame()
        T = df[new_pipe.treatment_column]
        Y = df[new_pipe.outcome_column]
        
        # Simple ATE (Average Treatment Effect)
        if 'ate' in methods:
            treated_outcomes = Y[T == 1]
            control_outcomes = Y[T == 0]
            
            ate_estimate = treated_outcomes.mean() - control_outcomes.mean()
            
            # Bootstrap confidence interval
            n_bootstrap = 1000
            bootstrap_ates = []
            for _ in range(n_bootstrap):
                treated_sample = treated_outcomes.sample(n=len(treated_outcomes), replace=True)
                control_sample = control_outcomes.sample(n=len(control_outcomes), replace=True)
                bootstrap_ate = treated_sample.mean() - control_sample.mean()
                bootstrap_ates.append(bootstrap_ate)
            
            alpha = 1 - confidence_level
            ci_lower = np.percentile(bootstrap_ates, 100 * alpha / 2)
            ci_upper = np.percentile(bootstrap_ates, 100 * (1 - alpha / 2))
            
            results['ate'] = {
                'estimate': ate_estimate,
                'confidence_interval': (ci_lower, ci_upper),
                'standard_error': np.std(bootstrap_ates),
                'p_value': 2 * (1 - stats.norm.cdf(abs(ate_estimate / np.std(bootstrap_ates))))
            }
        
        # ATT (Average Treatment Effect on Treated)
        if 'att' in methods and len(X.columns) > 0:
            # Regression-based ATT
            if outcome_model == 'linear':
                control_model = LinearRegression()
            else:
                control_model = RandomForestRegressor(n_estimators=100, random_state=42)
            
            # Fit model on control group
            control_data = df[T == 0]
            if len(control_data) > 0:
                control_model.fit(control_data[new_pipe.covariate_columns], control_data[new_pipe.outcome_column])
                
                # Predict counterfactual outcomes for treated group
                treated_data = df[T == 1]
                if len(treated_data) > 0:
                    counterfactual_outcomes = control_model.predict(treated_data[new_pipe.covariate_columns])
                    att_estimate = (treated_data[new_pipe.outcome_column] - counterfactual_outcomes).mean()
                    
                    results['att'] = {
                        'estimate': att_estimate,
                        'n_treated': len(treated_data)
                    }
        
        # Inverse Probability Weighting (IPW)
        if 'ipw' in methods and 'propensity_score' in df.columns:
            ps = df['propensity_score']
            
            # Compute IPW weights
            weights = T / ps + (1 - T) / (1 - ps)
            
            # Weighted outcomes
            weighted_treated = (T * weights * Y).sum() / (T * weights).sum()
            weighted_control = ((1 - T) * weights * Y).sum() / ((1 - T) * weights).sum()
            
            ipw_estimate = weighted_treated - weighted_control
            
            results['ipw'] = {
                'estimate': ipw_estimate,
                'weights': weights
            }
        
        # Doubly Robust Estimation
        if 'doubly_robust' in methods and len(X.columns) > 0 and 'propensity_score' in df.columns:
            ps = df['propensity_score']
            
            # Fit outcome models for both treatment groups
            if outcome_model == 'linear':
                treated_model = LinearRegression()
                control_model = LinearRegression()
            else:
                treated_model = RandomForestRegressor(n_estimators=100, random_state=42)
                control_model = RandomForestRegressor(n_estimators=100, random_state=43)
            
            treated_data = df[T == 1]
            control_data = df[T == 0]
            
            if len(treated_data) > 0 and len(control_data) > 0:
                treated_model.fit(treated_data[new_pipe.covariate_columns], treated_data[new_pipe.outcome_column])
                control_model.fit(control_data[new_pipe.covariate_columns], control_data[new_pipe.outcome_column])
                
                # Predict potential outcomes
                mu1 = treated_model.predict(X)  # Treated potential outcomes
                mu0 = control_model.predict(X)  # Control potential outcomes
                
                # Doubly robust estimator
                dr_component1 = T * (Y - mu1) / ps
                dr_component0 = (1 - T) * (Y - mu0) / (1 - ps)
                dr_ate = (mu1 - mu0 + dr_component1 - dr_component0).mean()
                
                results['doubly_robust'] = {
                    'estimate': dr_ate,
                    'treated_potential_outcomes': mu1,
                    'control_potential_outcomes': mu0
                }
        
        new_pipe.treatment_effects[analysis_name] = results
        new_pipe.current_analysis = f'treatment_effects_{analysis_name}'
        
        return new_pipe
    
    return _estimate_treatment_effects


# A/B Testing Functions
def design_ab_test(
    effect_size: float,
    baseline_rate: float,
    power: float = 0.8,
    alpha: float = 0.05,
    two_sided: bool = True,
    test_name: str = 'ab_test_design'
):
    """
    Design A/B test with power analysis and sample size calculation
    
    Parameters:
    -----------
    effect_size : float
        Expected effect size (difference in means or proportions)
    baseline_rate : float
        Baseline conversion rate or mean
    power : float
        Statistical power (1 - beta)
    alpha : float
        Type I error rate
    two_sided : bool
        Whether to use two-sided test
    test_name : str
        Name for the test design
        
    Returns:
    --------
    Callable
        Function that designs A/B test from a CausalPipe
    """
    def _design_ab_test(pipe):
        new_pipe = pipe.copy()
        
        # Calculate sample size needed
        effect_size_standardized = effect_size / np.sqrt(baseline_rate * (1 - baseline_rate))
        
        try:
            n_per_group = tt_solve_power(
                effect_size=effect_size_standardized,
                power=power,
                alpha=alpha,
                alternative='two-sided' if two_sided else 'one-sided'
            )
            
            total_sample_size = int(np.ceil(2 * n_per_group))
            
        except:
            # Fallback calculation
            if two_sided:
                z_alpha = stats.norm.ppf(1 - alpha/2)
            else:
                z_alpha = stats.norm.ppf(1 - alpha)
            
            z_beta = stats.norm.ppf(power)
            
            n_per_group = 2 * ((z_alpha + z_beta) / effect_size_standardized) ** 2
            total_sample_size = int(np.ceil(2 * n_per_group))
        
        # Calculate minimum detectable effect with current sample size
        if new_pipe.data is not None:
            current_n = len(new_pipe.data) // 2
            if current_n > 0:
                mde = (stats.norm.ppf(1 - alpha/2) + stats.norm.ppf(power)) * np.sqrt(2 * baseline_rate * (1 - baseline_rate) / current_n)
            else:
                mde = None
        else:
            mde = None
        
        design_results = {
            'effect_size': effect_size,
            'baseline_rate': baseline_rate,
            'power': power,
            'alpha': alpha,
            'sample_size_per_group': int(np.ceil(n_per_group)) if n_per_group > 0 else None,
            'total_sample_size': total_sample_size,
            'minimum_detectable_effect': mde,
            'test_duration_days': None,  # To be filled based on traffic
            'two_sided': two_sided
        }
        
        new_pipe.power_analysis[test_name] = design_results
        new_pipe.current_analysis = f'ab_test_design_{test_name}'
        
        return new_pipe
    
    return _design_ab_test


def analyze_ab_test(
    confidence_level: float = 0.95,
    multiple_testing_correction: Optional[str] = None,
    test_name: str = 'ab_test_analysis'
):
    """
    Analyze A/B test results with statistical inference
    
    Parameters:
    -----------
    confidence_level : float
        Confidence level for intervals
    multiple_testing_correction : Optional[str]
        Multiple testing correction method ('bonferroni', 'fdr_bh')
    test_name : str
        Name for the analysis
        
    Returns:
    --------
    Callable
        Function that analyzes A/B test from a CausalPipe
    """
    def _analyze_ab_test(pipe):
        if pipe.treatment_column is None or pipe.outcome_column is None:
            raise ValueError("Treatment and outcome must be defined for A/B test analysis.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Split into control and treatment groups
        control_group = df[df[new_pipe.treatment_column] == 0]
        treatment_group = df[df[new_pipe.treatment_column] == 1]
        
        control_outcomes = control_group[new_pipe.outcome_column]
        treatment_outcomes = treatment_group[new_pipe.outcome_column]
        
        # Basic statistics
        control_mean = control_outcomes.mean()
        treatment_mean = treatment_outcomes.mean()
        effect_size = treatment_mean - control_mean
        
        control_std = control_outcomes.std()
        treatment_std = treatment_outcomes.std()
        
        # Statistical test
        if pd.api.types.is_numeric_dtype(df[new_pipe.outcome_column]):
            # Continuous outcome - t-test
            stat, p_value = ttest_ind(treatment_outcomes, control_outcomes, equal_var=False)
            test_type = 't-test'
            
            # Effect size (Cohen's d)
            pooled_std = np.sqrt(((len(control_outcomes) - 1) * control_std**2 + 
                                (len(treatment_outcomes) - 1) * treatment_std**2) / 
                               (len(control_outcomes) + len(treatment_outcomes) - 2))
            cohens_d = effect_size / pooled_std if pooled_std > 0 else 0
            
        else:
            # Binary outcome - chi-square test
            contingency_table = pd.crosstab(df[new_pipe.treatment_column], df[new_pipe.outcome_column])
            stat, p_value, _, _ = chi2_contingency(contingency_table)
            test_type = 'chi-square'
            cohens_d = None
        
        # Confidence interval for difference
        alpha = 1 - confidence_level
        se_diff = np.sqrt(control_std**2/len(control_outcomes) + treatment_std**2/len(treatment_outcomes))
        ci_lower = effect_size - stats.norm.ppf(1 - alpha/2) * se_diff
        ci_upper = effect_size + stats.norm.ppf(1 - alpha/2) * se_diff
        
        # Multiple testing correction if specified
        if multiple_testing_correction:
            corrected_p = multipletests([p_value], method=multiple_testing_correction)[1][0]
        else:
            corrected_p = p_value
        
        # Statistical power (post-hoc)
        observed_effect_size = abs(effect_size / se_diff) if se_diff > 0 else 0
        power = ttest_power(observed_effect_size, len(control_outcomes), alpha)
        
        results = {
            'control_n': len(control_outcomes),
            'treatment_n': len(treatment_outcomes),
            'control_mean': control_mean,
            'treatment_mean': treatment_mean,
            'effect_size': effect_size,
            'relative_lift': (effect_size / control_mean * 100) if control_mean != 0 else None,
            'confidence_interval': (ci_lower, ci_upper),
            'p_value': p_value,
            'corrected_p_value': corrected_p,
            'test_statistic': stat,
            'test_type': test_type,
            'cohens_d': cohens_d,
            'statistical_power': power,
            'significant': corrected_p < (1 - confidence_level)
        }
        
        new_pipe.ab_test_results[test_name] = results
        new_pipe.current_analysis = f'ab_test_analysis_{test_name}'
        
        return new_pipe
    
    return _analyze_ab_test


# Validation and Diagnostics
def check_covariate_balance(
    matching_name: Optional[str] = None,
    balance_threshold: float = 0.1,
    test_name: str = 'balance_check'
):
    """
    Check covariate balance between treatment groups
    
    Parameters:
    -----------
    matching_name : Optional[str]
        Name of matched dataset to check (if None, uses original data)
    balance_threshold : float
        Standardized mean difference threshold for balance
    test_name : str
        Name for the balance test
        
    Returns:
    --------
    Callable
        Function that checks covariate balance from a CausalPipe
    """
    def _check_covariate_balance(pipe):
        if not pipe.covariate_columns:
            raise ValueError("No covariates defined for balance checking.")
        
        new_pipe = pipe.copy()
        
        # Select dataset to check
        if matching_name and matching_name in new_pipe.matched_data:
            df = new_pipe.matched_data[matching_name]['data']
            data_type = 'matched'
        else:
            df = new_pipe.data
            data_type = 'original'
        
        balance_results = {}
        
        for covariate in new_pipe.covariate_columns:
            if covariate in df.columns:
                treated = df[df[new_pipe.treatment_column] == 1][covariate]
                control = df[df[new_pipe.treatment_column] == 0][covariate]
                
                # Standardized mean difference
                treated_mean = treated.mean()
                control_mean = control.mean()
                pooled_std = np.sqrt((treated.var() + control.var()) / 2)
                
                smd = (treated_mean - control_mean) / pooled_std if pooled_std > 0 else 0
                
                # Statistical test
                if pd.api.types.is_numeric_dtype(df[covariate]):
                    stat, p_val = ttest_ind(treated, control, equal_var=False)
                    test_type = 't-test'
                else:
                    # Chi-square for categorical variables
                    contingency = pd.crosstab(df[new_pipe.treatment_column], df[covariate])
                    stat, p_val, _, _ = chi2_contingency(contingency)
                    test_type = 'chi-square'
                
                balance_results[covariate] = {
                    'treated_mean': treated_mean,
                    'control_mean': control_mean,
                    'standardized_mean_diff': smd,
                    'balanced': abs(smd) < balance_threshold,
                    'p_value': p_val,
                    'test_statistic': stat,
                    'test_type': test_type
                }
        
        # Overall balance assessment
        unbalanced_vars = [var for var, results in balance_results.items() 
                          if not results['balanced']]
        
        summary = {
            'data_type': data_type,
            'balance_threshold': balance_threshold,
            'n_covariates': len(balance_results),
            'n_balanced': len(balance_results) - len(unbalanced_vars),
            'n_unbalanced': len(unbalanced_vars),
            'unbalanced_variables': unbalanced_vars,
            'overall_balanced': len(unbalanced_vars) == 0,
            'covariate_results': balance_results
        }
        
        new_pipe.balance_tests[test_name] = summary
        new_pipe.current_analysis = f'balance_check_{test_name}'
        
        return new_pipe
    
    return _check_covariate_balance


def sensitivity_analysis(
    hidden_confounder_strength: List[float] = [0.1, 0.2, 0.3, 0.4, 0.5],
    analysis_name: str = 'sensitivity_analysis'
):
    """
    Perform sensitivity analysis for unmeasured confounding
    
    Parameters:
    -----------
    hidden_confounder_strength : List[float]
        Range of hidden confounder effect sizes to test
    analysis_name : str
        Name for the sensitivity analysis
        
    Returns:
    --------
    Callable
        Function that performs sensitivity analysis from a CausalPipe
    """
    def _sensitivity_analysis(pipe):
        if not pipe.treatment_effects:
            raise ValueError("Treatment effects must be estimated first.")
        
        new_pipe = pipe.copy()
        
        # Get the main treatment effect estimate
        main_analysis = list(new_pipe.treatment_effects.keys())[0]
        if 'ate' in new_pipe.treatment_effects[main_analysis]:
            baseline_effect = new_pipe.treatment_effects[main_analysis]['ate']['estimate']
        else:
            baseline_effect = list(new_pipe.treatment_effects[main_analysis].values())[0]['estimate']
        
        sensitivity_results = []
        
        for confounder_strength in hidden_confounder_strength:
            # Simulate the bias from hidden confounder
            # This is a simplified sensitivity analysis
            bias_factor = confounder_strength * np.sqrt(len(new_pipe.data))
            
            # Calculate range of possible treatment effects
            lower_bound = baseline_effect - bias_factor
            upper_bound = baseline_effect + bias_factor
            
            sensitivity_results.append({
                'confounder_strength': confounder_strength,
                'baseline_effect': baseline_effect,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'effect_robust': (lower_bound > 0 and upper_bound > 0) or (lower_bound < 0 and upper_bound < 0)
            })
        
        # Summary
        robust_effects = sum(1 for r in sensitivity_results if r['effect_robust'])
        
        summary = {
            'baseline_treatment_effect': baseline_effect,
            'sensitivity_range': sensitivity_results,
            'n_robust_scenarios': robust_effects,
            'total_scenarios': len(sensitivity_results),
            'robustness_percentage': robust_effects / len(sensitivity_results) * 100
        }
        
        new_pipe.sensitivity_analysis[analysis_name] = summary
        new_pipe.current_analysis = f'sensitivity_{analysis_name}'
        
        return new_pipe
    
    return _sensitivity_analysis


# Visualization Functions
def plot_propensity_distribution(
    model_name: str = 'propensity_model',
    figsize: Tuple[int, int] = (12, 6)
):
    """
    Plot propensity score distributions by treatment group
    
    Parameters:
    -----------
    model_name : str
        Name of propensity model
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots propensity distributions from a CausalPipe
    """
    def _plot_propensity_distribution(pipe):
        if 'propensity_score' not in pipe.data.columns:
            raise ValueError("Propensity scores not found. Run estimate_propensity_scores first.")
        
        df = pipe.data
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Histogram
        treated_ps = df[df[pipe.treatment_column] == 1]['propensity_score']
        control_ps = df[df[pipe.treatment_column] == 0]['propensity_score']
        
        ax1.hist(control_ps, alpha=0.7, label='Control', bins=30, density=True)
        ax1.hist(treated_ps, alpha=0.7, label='Treated', bins=30, density=True)
        ax1.set_xlabel('Propensity Score')
        ax1.set_ylabel('Density')
        ax1.set_title('Propensity Score Distribution')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Box plot
        ps_data = [control_ps.values, treated_ps.values]
        ax2.boxplot(ps_data, labels=['Control', 'Treated'])
        ax2.set_ylabel('Propensity Score')
        ax2.set_title('Propensity Score Box Plot')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_propensity_distribution


def plot_treatment_effects(
    analysis_name: str = 'treatment_effects',
    figsize: Tuple[int, int] = (10, 6)
):
    """
    Plot treatment effects with confidence intervals
    
    Parameters:
    -----------
    analysis_name : str
        Name of treatment effects analysis
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots treatment effects from a CausalPipe
    """
    def _plot_treatment_effects(pipe):
        if analysis_name not in pipe.treatment_effects:
            raise ValueError(f"Treatment effects '{analysis_name}' not found.")
        
        effects = pipe.treatment_effects[analysis_name]
        
        methods = []
        estimates = []
        ci_lowers = []
        ci_uppers = []
        
        for method, results in effects.items():
            methods.append(method.upper())
            estimates.append(results['estimate'])
            
            if 'confidence_interval' in results:
                ci_lower, ci_upper = results['confidence_interval']
                ci_lowers.append(ci_lower)
                ci_uppers.append(ci_upper)
            else:
                ci_lowers.append(results['estimate'])
                ci_uppers.append(results['estimate'])
        
        fig, ax = plt.subplots(figsize=figsize)
        
        y_pos = np.arange(len(methods))
        
        # Plot estimates with error bars
        errors_lower = np.array(estimates) - np.array(ci_lowers)
        errors_upper = np.array(ci_uppers) - np.array(estimates)
        
        ax.barh(y_pos, estimates, xerr=[errors_lower, errors_upper], 
               capsize=5, alpha=0.7, color='skyblue', edgecolor='black')
        
        # Add zero line
        ax.axvline(x=0, color='red', linestyle='--', alpha=0.8)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(methods)
        ax.set_xlabel('Treatment Effect')
        ax.set_title('Treatment Effect Estimates')
        ax.grid(True, alpha=0.3)
        
        # Add value labels
        for i, (estimate, ci_lower, ci_upper) in enumerate(zip(estimates, ci_lowers, ci_uppers)):
            ax.text(estimate + 0.01, i, f'{estimate:.3f}\n[{ci_lower:.3f}, {ci_upper:.3f}]',
                   va='center', fontsize=10)
        
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_treatment_effects


def plot_covariate_balance(
    test_name: str = 'balance_check',
    figsize: Tuple[int, int] = (12, 8)
):
    """
    Plot covariate balance before and after matching
    
    Parameters:
    -----------
    test_name : str
        Name of balance test
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots covariate balance from a CausalPipe
    """
    def _plot_covariate_balance(pipe):
        if test_name not in pipe.balance_tests:
            raise ValueError(f"Balance test '{test_name}' not found.")
        
        balance_results = pipe.balance_tests[test_name]['covariate_results']
        
        covariates = list(balance_results.keys())
        smd_values = [results['standardized_mean_diff'] for results in balance_results.values()]
        p_values = [results['p_value'] for results in balance_results.values()]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Standardized mean differences
        colors = ['red' if abs(smd) > 0.1 else 'green' for smd in smd_values]
        bars = ax1.barh(covariates, smd_values, color=colors, alpha=0.7)
        
        ax1.axvline(x=0.1, color='red', linestyle='--', alpha=0.8, label='Balance threshold (+0.1)')
        ax1.axvline(x=-0.1, color='red', linestyle='--', alpha=0.8, label='Balance threshold (-0.1)')
        ax1.axvline(x=0, color='black', linestyle='-', alpha=0.8)
        
        ax1.set_xlabel('Standardized Mean Difference')
        ax1.set_title('Covariate Balance')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # P-values
        log_p_values = [-np.log10(p) for p in p_values]
        colors2 = ['green' if p < 0.05 else 'red' for p in p_values]
        ax2.barh(covariates, log_p_values, color=colors2, alpha=0.7)
        
        ax2.axvline(x=-np.log10(0.05), color='red', linestyle='--', alpha=0.8, label='p = 0.05')
        ax2.set_xlabel('-log10(p-value)')
        ax2.set_title('Balance Test P-values')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_covariate_balance


# Model Management
def save_causal_model(
    model_components: List[str] = ['all'],
    filepath: Optional[str] = None
):
    """
    Save causal inference models and results
    
    Parameters:
    -----------
    model_components : List[str]
        Components to save ('propensity', 'outcome', 'effects', 'all')
    filepath : Optional[str]
        Path to save the model
        
    Returns:
    --------
    Callable
        Function that saves causal models from a CausalPipe
    """
    def _save_causal_model(pipe):
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = f"causal_model_{timestamp}.joblib"
        else:
            save_path = filepath
        
        # Package model components
        model_package = {
            'treatment_column': pipe.treatment_column,
            'outcome_column': pipe.outcome_column,
            'covariate_columns': pipe.covariate_columns
        }
        
        if 'all' in model_components or 'propensity' in model_components:
            model_package['propensity_models'] = pipe.propensity_models
        
        if 'all' in model_components or 'outcome' in model_components:
            model_package['outcome_models'] = pipe.outcome_models
        
        if 'all' in model_components or 'effects' in model_components:
            model_package['treatment_effects'] = pipe.treatment_effects
            model_package['ab_test_results'] = pipe.ab_test_results
            model_package['balance_tests'] = pipe.balance_tests
        
        import joblib
        joblib.dump(model_package, save_path)
        print(f"Causal model saved to: {save_path}")
        
        return pipe
    
    return _save_causal_model


def print_causal_summary(
    analysis_name: Optional[str] = None
):
    """
    Print comprehensive causal analysis summary
    
    Parameters:
    -----------
    analysis_name : Optional[str]
        Specific analysis to summarize (if None, summarizes all)
        
    Returns:
    --------
    Callable
        Function that prints causal summary from a CausalPipe
    """
    def _print_causal_summary(pipe):
        print(f"\n=== Causal Inference Analysis Summary ===")
        print(f"Treatment variable: {pipe.treatment_column}")
        print(f"Outcome variable: {pipe.outcome_column}")
        print(f"Number of covariates: {len(pipe.covariate_columns)}")
        print(f"Total observations: {len(pipe.data) if pipe.data is not None else 0}")
        
        if pipe.data is not None and pipe.treatment_column:
            treatment_dist = pipe.data[pipe.treatment_column].value_counts()
            print(f"Treatment distribution: {dict(treatment_dist)}")
        
        # Treatment effects summary
        if pipe.treatment_effects:
            print(f"\n=== Treatment Effects ===")
            for analysis_name, effects in pipe.treatment_effects.items():
                print(f"\nAnalysis: {analysis_name}")
                for method, results in effects.items():
                    estimate = results['estimate']
                    if 'confidence_interval' in results:
                        ci_lower, ci_upper = results['confidence_interval']
                        print(f"  {method.upper()}: {estimate:.4f} [{ci_lower:.4f}, {ci_upper:.4f}]")
                    else:
                        print(f"  {method.upper()}: {estimate:.4f}")
        
        # A/B test results
        if pipe.ab_test_results:
            print(f"\n=== A/B Test Results ===")
            for test_name, results in pipe.ab_test_results.items():
                print(f"\nTest: {test_name}")
                print(f"  Effect size: {results['effect_size']:.4f}")
                print(f"  P-value: {results['p_value']:.4f}")
                print(f"  Significant: {results['significant']}")
                if results['relative_lift']:
                    print(f"  Relative lift: {results['relative_lift']:.2f}%")
        
        # Balance tests
        if pipe.balance_tests:
            print(f"\n=== Covariate Balance ===")
            for test_name, balance in pipe.balance_tests.items():
                print(f"\nBalance test: {test_name}")
                print(f"  Balanced variables: {balance['n_balanced']}/{balance['n_covariates']}")
                if balance['unbalanced_variables']:
                    print(f"  Unbalanced: {', '.join(balance['unbalanced_variables'])}")
        
        return pipe
    
    return _print_causal_summary