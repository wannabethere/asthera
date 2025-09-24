"""
Risk Analysis Pipeline for Maximum Likelihood and Risk Calculation

This module provides a pipeline-style risk analysis toolkit that enables
functional composition for maximum likelihood estimation, risk metrics calculation,
and portfolio risk analysis. The module follows the same pattern as the cohort,
metrics, and moving averages tools, providing a consistent interface for risk analysis.

Key features:
- Maximum likelihood estimation for various distributions
- Value at Risk (VaR) and Conditional Value at Risk (CVaR)
- Portfolio risk metrics and correlation analysis
- Monte Carlo simulations for risk assessment
- Stress testing and scenario analysis
- Risk attribution and decomposition
- Time series risk models (GARCH, etc.)

Example usage:

```python
import pandas as pd
from risk_analysis import RiskPipe, fit_distribution, calculate_var

# Load data
df = pd.read_csv('financial_data.csv')

# Create pipeline and calculate risk metrics
result = (
    RiskPipe.from_dataframe(df)
    | fit_distribution(
        columns=['returns'],
        distribution='normal'
    )
    | calculate_var(
        columns=['returns'],
        confidence_level=0.05
    )
)

# Get results
risk_metrics = result.risk_metrics
```
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
import warnings
from scipy import stats, optimize
from scipy.stats import norm, t, skewnorm, genextreme
import scipy.linalg as linalg
from .base_pipe import BasePipe


class RiskPipe(BasePipe):
    """
    A pipeline-style risk analysis tool that enables functional composition
    with a meterstick-like interface for maximum likelihood and risk calculations.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for risk analysis"""
        self.risk_metrics = {}
        self.distributions = {}
        self.simulations = {}
        self.stress_tests = {}
        self.current_metric = None
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'risk_metrics'):
            self.risk_metrics = source_pipe.risk_metrics.copy()
        if hasattr(source_pipe, 'distributions'):
            self.distributions = source_pipe.distributions.copy()
        if hasattr(source_pipe, 'simulations'):
            self.simulations = source_pipe.simulations.copy()
        if hasattr(source_pipe, 'stress_tests'):
            self.stress_tests = source_pipe.stress_tests.copy()
        if hasattr(source_pipe, 'current_metric'):
            self.current_metric = source_pipe.current_metric
    
    def _has_results(self) -> bool:
        """Check if the pipeline has any results to merge"""
        return (len(self.risk_metrics) > 0 or 
                len(self.distributions) > 0 or 
                len(self.simulations) > 0 or 
                len(self.stress_tests) > 0)
    
    def merge_to_df(self, base_df: pd.DataFrame, analysis_name: Optional[str] = None, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
        """
        Merge risk analysis results into the base dataframe as new columns
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge results into
        analysis_name : str, optional
            Specific analysis to merge (if None, merges all)
        include_metadata : bool, default=False
            Whether to include metadata columns
        **kwargs : dict
            Additional arguments
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with risk analysis results merged as new columns
        """
        if not self._has_results():
            return base_df
        
        result_df = base_df.copy()
        
        # Merge risk metrics
        for metric_name, metric_data in self.risk_metrics.items():
            if analysis_name is None or metric_name == analysis_name:
                if isinstance(metric_data, dict):
                    for key, value in metric_data.items():
                        if include_metadata:
                            result_df[f"risk_{metric_name}_{key}"] = value
        
        # Merge distributions
        for dist_name, dist_data in self.distributions.items():
            if analysis_name is None or dist_name == analysis_name:
                if isinstance(dist_data, dict):
                    for key, value in dist_data.items():
                        if include_metadata:
                            result_df[f"dist_{dist_name}_{key}"] = value
        
        # Merge simulations
        for sim_name, sim_data in self.simulations.items():
            if analysis_name is None or sim_name == analysis_name:
                if isinstance(sim_data, dict):
                    for key, value in sim_data.items():
                        if include_metadata:
                            result_df[f"sim_{sim_name}_{key}"] = value
        
        # Merge stress tests
        for stress_name, stress_data in self.stress_tests.items():
            if analysis_name is None or stress_name == analysis_name:
                if isinstance(stress_data, dict):
                    for key, value in stress_data.items():
                        if include_metadata:
                            result_df[f"stress_{stress_name}_{key}"] = value
        
        return result_df
    
    def to_df(self, analysis_name: Optional[str] = None, include_metadata: bool = False, include_original: bool = False):
        """
        Convert the risk analysis results to a DataFrame
        
        Parameters:
        -----------
        analysis_name : str, optional
            Name of the specific analysis to convert. If None, returns the current analysis
        include_metadata : bool, default=False
            Whether to include metadata columns in the output DataFrame
        include_original : bool, default=False
            Whether to include original data columns in the output DataFrame
            
        Returns:
        --------
        pd.DataFrame
            DataFrame representation of the risk analysis results
            
        Raises:
        -------
        ValueError
            If no risk analysis has been performed or analysis not found
            
        Examples:
        --------
        >>> # Basic VaR calculation
        >>> pipe = (RiskPipe.from_dataframe(df)
        ...         | calculate_var('returns', 0.05))
        >>> results_df = pipe.to_df()
        >>> print(results_df.head())
        
        >>> # Specific analysis with metadata
        >>> results_df = pipe.to_df('var_historical', include_metadata=True)
        >>> print(results_df.columns)
        
        >>> # Current analysis
        >>> current_df = pipe.to_df()  # Uses current_metric
        >>> print(current_df.head())
        """
        if not any([self.risk_metrics, self.distributions, self.simulations, self.stress_tests]):
            raise ValueError("No risk analysis has been performed. Run some analysis first.")
        
        # Determine which analysis to use
        if analysis_name is None:
            if self.current_metric is None:
                # Use the last analysis from any category
                all_analyses = {}
                all_analyses.update(self.risk_metrics)
                all_analyses.update(self.distributions)
                all_analyses.update(self.simulations)
                all_analyses.update(self.stress_tests)
                if all_analyses:
                    analysis_name = list(all_analyses.keys())[-1]
                else:
                    raise ValueError("No analyses found")
            else:
                analysis_name = self.current_metric
        
        # Find the analysis in the appropriate category
        result = None
        analysis_type = None
        
        if analysis_name in self.risk_metrics:
            result = self.risk_metrics[analysis_name]
            analysis_type = 'risk_metric'
        elif analysis_name in self.distributions:
            result = self.distributions[analysis_name]
            analysis_type = 'distribution'
        elif analysis_name in self.simulations:
            result = self.simulations[analysis_name]
            analysis_type = 'simulation'
        elif analysis_name in self.stress_tests:
            result = self.stress_tests[analysis_name]
            analysis_type = 'stress_test'
        else:
            raise ValueError(f"Analysis '{analysis_name}' not found. Available analyses: {list(self.risk_metrics.keys()) + list(self.distributions.keys()) + list(self.simulations.keys()) + list(self.stress_tests.keys())}")
        
        # Convert result to DataFrame based on type
        if analysis_type == 'risk_metric':
            return self._risk_metric_to_df(result, analysis_name, include_metadata, include_original)
        elif analysis_type == 'distribution':
            return self._distribution_to_df(result, analysis_name, include_metadata, include_original)
        elif analysis_type == 'simulation':
            return self._simulation_to_df(result, analysis_name, include_metadata, include_original)
        elif analysis_type == 'stress_test':
            return self._stress_test_to_df(result, analysis_name, include_metadata, include_original)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
    
    def _risk_metric_to_df(self, result, analysis_name, include_metadata, include_original):
        """Convert risk metric results to DataFrame"""
        if isinstance(result, dict) and any(isinstance(v, dict) for v in result.values()):
            # Multi-column results (e.g., VaR for multiple columns)
            all_data = []
            for col, col_result in result.items():
                if isinstance(col_result, dict):
                    row = {'column': col}
                    row.update(col_result)
                    all_data.append(row)
            
            result_df = pd.DataFrame(all_data)
        else:
            # Single result (e.g., portfolio risk)
            if isinstance(result, dict):
                # Flatten nested dictionaries
                flattened = self._flatten_dict(result)
                result_df = pd.DataFrame([flattened])
            else:
                result_df = pd.DataFrame([result])
        
        # Ensure we always return a DataFrame
        if result_df is None:
            result_df = pd.DataFrame()
        
        # Add metadata if requested
        if include_metadata and not result_df.empty:
            result_df['analysis_name'] = analysis_name
            result_df['analysis_type'] = 'risk_metric'
        
        # Add original data if requested
        if include_original and self.data is not None:
            # Merge with original data (this might need adjustment based on specific use case)
            if include_metadata and not result_df.empty:
                result_df['metadata_note'] = 'Original data available separately via pipe.data'
        
        return result_df
    
    def _distribution_to_df(self, result, analysis_name, include_metadata, include_original):
        """Convert distribution fit results to DataFrame"""
        if isinstance(result, dict):
            # Extract key information
            row = {
                'distribution': result.get('distribution', 'unknown'),
                'log_likelihood': result.get('log_likelihood', np.nan),
                'aic': result.get('aic', np.nan),
                'bic': result.get('bic', np.nan)
            }
            
            # Add parameters
            params = result.get('parameters', {})
            for param, value in params.items():
                row[f'param_{param}'] = value
            
            # Add confidence intervals if available
            ci = result.get('confidence_intervals', {})
            for param, (lower, upper) in ci.items():
                row[f'ci_{param}_lower'] = lower
                row[f'ci_{param}_upper'] = upper
            
            result_df = pd.DataFrame([row])
        else:
            result_df = pd.DataFrame([result])
        
        # Ensure we always return a DataFrame
        if result_df is None:
            result_df = pd.DataFrame()
        
        # Add metadata if requested
        if include_metadata and not result_df.empty:
            result_df['analysis_name'] = analysis_name
            result_df['analysis_type'] = 'distribution'
        
        return result_df
    
    def _simulation_to_df(self, result, analysis_name, include_metadata, include_original):
        """Convert simulation results to DataFrame"""
        if isinstance(result, dict):
            all_data = []
            for col, col_result in result.items():
                if isinstance(col_result, dict):
                    # Extract simulation statistics
                    path_stats = col_result.get('path_statistics', {})
                    row = {
                        'column': col,
                        'method': col_result.get('method', 'unknown'),
                        'horizon': col_result.get('horizon', np.nan),
                        'n_simulations': col_result.get('n_simulations', np.nan)
                    }
                    
                    # Add path statistics
                    for stat, values in path_stats.items():
                        if isinstance(values, np.ndarray):
                            row[f'path_{stat}_mean'] = np.mean(values)
                            row[f'path_{stat}_std'] = np.std(values)
                        else:
                            row[f'path_{stat}'] = values
                    
                    all_data.append(row)
            
            result_df = pd.DataFrame(all_data)
        else:
            result_df = pd.DataFrame([result])
        
        # Ensure we always return a DataFrame
        if result_df is None:
            result_df = pd.DataFrame()
        
        # Add metadata if requested
        if include_metadata and not result_df.empty:
            result_df['analysis_name'] = analysis_name
            result_df['analysis_type'] = 'simulation'
        
        return result_df
    
    def _stress_test_to_df(self, result, analysis_name, include_metadata, include_original):
        """Convert stress test results to DataFrame"""
        if isinstance(result, dict):
            all_data = []
            for col, col_result in result.items():
                if isinstance(col_result, dict):
                    base_case = col_result.get('base_case', {})
                    
                    # Add base case
                    row = {
                        'column': col,
                        'scenario': 'base_case',
                        'returns': base_case.get('returns', np.nan),
                        'volatility': base_case.get('volatility', np.nan)
                    }
                    all_data.append(row)
                    
                    # Add stress scenarios
                    for scenario_name, scenario_result in col_result.items():
                        if scenario_name != 'base_case' and isinstance(scenario_result, dict):
                            scenario_row = {
                                'column': col,
                                'scenario': scenario_name,
                                'returns': scenario_result.get('parameters', {}).get('returns', np.nan),
                                'volatility': scenario_result.get('parameters', {}).get('volatility', np.nan),
                                'var_95': scenario_result.get('var_95', np.nan),
                                'var_99': scenario_result.get('var_99', np.nan),
                                'cvar_95': scenario_result.get('cvar_95', np.nan),
                                'cvar_99': scenario_result.get('cvar_99', np.nan),
                                'return_impact': scenario_result.get('return_impact', np.nan),
                                'volatility_impact': scenario_result.get('volatility_impact', np.nan)
                            }
                            all_data.append(scenario_row)
            
            result_df = pd.DataFrame(all_data)
        else:
            result_df = pd.DataFrame([result])
        
        # Ensure we always return a DataFrame
        if result_df is None:
            result_df = pd.DataFrame()
        
        # Add metadata if requested
        if include_metadata and not result_df.empty:
            result_df['analysis_name'] = analysis_name
            result_df['analysis_type'] = 'stress_test'
        
        return result_df
    
    def _flatten_dict(self, d, parent_key='', sep='_'):
        """Flatten nested dictionary"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def get_risk_columns(self):
        """
        Get the column names that were created by the risk analysis
        
        Returns:
        --------
        List[str]
            List of column names created by the risk analysis
        """
        if self.data is None:
            return []
        
        # Get risk analysis columns (rolling metrics, etc.)
        risk_cols = [col for col in self.data.columns 
                    if any(suffix in col for suffix in ['_rolling_vol', '_rolling_var', '_rolling_cvar', '_rolling_skew', '_rolling_kurt'])]
        
        return risk_cols
    
    def get_risk_summary_df(self, include_metadata: bool = False):
        """
        Get a summary DataFrame of all risk analyses
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns
            
        Returns:
        --------
        pd.DataFrame
            Summary DataFrame with risk analysis statistics
        """
        summary_data = []
        
        # Risk metrics
        for metric_name, metric_result in self.risk_metrics.items():
            summary_row = {
                'analysis_name': metric_name,
                'type': 'risk_metric',
                'is_current': metric_name == self.current_metric
            }
            
            if include_metadata:
                if isinstance(metric_result, dict):
                    summary_row['keys'] = ', '.join(metric_result.keys())
                else:
                    summary_row['result_type'] = str(type(metric_result))
            
            summary_data.append(summary_row)
        
        # Distributions
        for dist_name, dist_result in self.distributions.items():
            summary_row = {
                'analysis_name': dist_name,
                'type': 'distribution',
                'is_current': dist_name == self.current_metric
            }
            
            if include_metadata and isinstance(dist_result, dict):
                summary_row['distribution'] = dist_result.get('distribution', 'unknown')
                summary_row['aic'] = dist_result.get('aic', np.nan)
            
            summary_data.append(summary_row)
        
        # Simulations
        for sim_name, sim_result in self.simulations.items():
            summary_row = {
                'analysis_name': sim_name,
                'type': 'simulation',
                'is_current': sim_name == self.current_metric
            }
            
            if include_metadata and isinstance(sim_result, dict):
                summary_row['columns'] = ', '.join(sim_result.keys())
            
            summary_data.append(summary_row)
        
        # Stress tests
        for stress_name, stress_result in self.stress_tests.items():
            summary_row = {
                'analysis_name': stress_name,
                'type': 'stress_test',
                'is_current': stress_name == self.current_metric
            }
            
            if include_metadata and isinstance(stress_result, dict):
                summary_row['columns'] = ', '.join(stress_result.keys())
            
            summary_data.append(summary_row)
        
        return pd.DataFrame(summary_data)
    
    def get_analysis_by_type(self, analysis_type: str):
        """
        Get all analyses of a specific type
        
        Parameters:
        -----------
        analysis_type : str
            Type of analysis to retrieve ('risk_metric', 'distribution', 'simulation', 'stress_test')
            
        Returns:
        --------
        Dict
            Dictionary of analyses of the specified type
        """
        type_mapping = {
            'risk_metric': self.risk_metrics,
            'distribution': self.distributions,
            'simulation': self.simulations,
            'stress_test': self.stress_tests
        }
        
        return type_mapping.get(analysis_type, {})
    
    def get_current_result(self):
        """
        Get the current risk analysis result
        
        Returns:
        --------
        Any
            The current risk analysis result, or empty dict if no current analysis
        """
        if self.current_metric is None:
            return {}
        
        # Check in all categories
        if self.current_metric in self.risk_metrics:
            return self.risk_metrics[self.current_metric]
        elif self.current_metric in self.distributions:
            return self.distributions[self.current_metric]
        elif self.current_metric in self.simulations:
            return self.simulations[self.current_metric]
        elif self.current_metric in self.stress_tests:
            return self.stress_tests[self.current_metric]
        else:
            return {}
    
    def get_original_data(self):
        """
        Get the original data DataFrame
        
        Returns:
        --------
        pd.DataFrame
            The original data DataFrame, or empty DataFrame if no data was provided
        """
        return self.data.copy() if self.data is not None else pd.DataFrame()
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the risk analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in risk analysis pipe)
            
        Returns:
        --------
        dict
            Summary of the risk analysis results
        """
        if not self.risk_metrics and not self.distributions and not self.simulations and not self.stress_tests:
            return {"error": "No risk analysis has been performed"}
        
        # Get summary DataFrame
        summary_df = self.get_risk_summary_df()
        
        # Get risk columns
        risk_cols = self.get_risk_columns()
        
        # Count analyses by type
        analysis_types = {
            'risk_metrics': len(self.risk_metrics),
            'distributions': len(self.distributions),
            'simulations': len(self.simulations),
            'stress_tests': len(self.stress_tests)
        }
        
        return {
            "total_analyses": sum(analysis_types.values()),
            "total_risk_columns": len(risk_cols),
            "available_risk_metrics": list(self.risk_metrics.keys()),
            "available_distributions": list(self.distributions.keys()),
            "available_simulations": list(self.simulations.keys()),
            "available_stress_tests": list(self.stress_tests.keys()),
            "risk_columns": risk_cols,
            "analysis_types": analysis_types,
            "current_metric": self.current_metric,
            "summary_dataframe": summary_df.to_dict('records') if not summary_df.empty else [],
            "risk_metrics_info": {name: {"type": info.get('type', 'unknown'), "columns": info.get('columns', [])} 
                                for name, info in self.risk_metrics.items()},
            "distributions_info": {name: {"distribution": info.get('distribution', 'unknown'), "parameters": list(info.get('parameters', {}).keys())} 
                                 for name, info in self.distributions.items()}
        }


def fit_distribution(
    columns: Union[str, List[str]],
    distribution: str = 'normal',
    method: str = 'mle',
    confidence_level: float = 0.95,
    output_name: Optional[str] = None
):
    """
    Fit a probability distribution to data using maximum likelihood estimation
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to fit distributions for
    distribution : str, default='normal'
        Distribution to fit: 'normal', 'student_t', 'skewed_normal', 'gev'
    method : str, default='mle'
        Estimation method: 'mle' (maximum likelihood), 'moments'
    confidence_level : float, default=0.95
        Confidence level for parameter confidence intervals
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that fits distributions in a RiskPipe
    """
    def _fit_distribution(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Fit distributions for each column
        for col in cols:
            data = df[col].dropna()
            
            if len(data) < 10:
                warnings.warn(f"Insufficient data for column '{col}' (need at least 10 observations)")
                continue
            
            # Fit the specified distribution
            if distribution == 'normal':
                if method == 'mle':
                    # Maximum likelihood estimation
                    params = stats.norm.fit(data)
                    mu, sigma = params
                    
                    # Calculate log-likelihood
                    loglik = np.sum(stats.norm.logpdf(data, mu, sigma))
                    
                    # Calculate AIC and BIC
                    k = 2  # number of parameters
                    aic = 2 * k - 2 * loglik
                    bic = k * np.log(len(data)) - 2 * loglik
                    
                    # Confidence intervals (approximate)
                    se_mu = sigma / np.sqrt(len(data))
                    se_sigma = sigma / np.sqrt(2 * len(data))
                    alpha = 1 - confidence_level
                    z_score = stats.norm.ppf(1 - alpha/2)
                    
                    result = {
                        'distribution': 'normal',
                        'parameters': {'mu': mu, 'sigma': sigma},
                        'log_likelihood': loglik,
                        'aic': aic,
                        'bic': bic,
                        'confidence_intervals': {
                            'mu': (mu - z_score * se_mu, mu + z_score * se_mu),
                            'sigma': (max(0, sigma - z_score * se_sigma), sigma + z_score * se_sigma)
                        },
                        'fitted_distribution': stats.norm(mu, sigma)
                    }
                    
                elif method == 'moments':
                    # Method of moments
                    mu = np.mean(data)
                    sigma = np.std(data, ddof=1)
                    
                    result = {
                        'distribution': 'normal',
                        'parameters': {'mu': mu, 'sigma': sigma},
                        'fitted_distribution': stats.norm(mu, sigma)
                    }
                    
            elif distribution == 'student_t':
                if method == 'mle':
                    # Fit Student's t-distribution
                    params = stats.t.fit(data)
                    df_param, loc, scale = params
                    
                    # Calculate log-likelihood
                    loglik = np.sum(stats.t.logpdf(data, df_param, loc, scale))
                    
                    # Calculate AIC and BIC
                    k = 3  # number of parameters
                    aic = 2 * k - 2 * loglik
                    bic = k * np.log(len(data)) - 2 * loglik
                    
                    result = {
                        'distribution': 'student_t',
                        'parameters': {'df': df_param, 'loc': loc, 'scale': scale},
                        'log_likelihood': loglik,
                        'aic': aic,
                        'bic': bic,
                        'fitted_distribution': stats.t(df_param, loc, scale)
                    }
                    
            elif distribution == 'skewed_normal':
                if method == 'mle':
                    # Fit skewed normal distribution
                    params = stats.skewnorm.fit(data)
                    a, loc, scale = params
                    
                    # Calculate log-likelihood
                    loglik = np.sum(stats.skewnorm.logpdf(data, a, loc, scale))
                    
                    # Calculate AIC and BIC
                    k = 3  # number of parameters
                    aic = 2 * k - 2 * loglik
                    bic = k * np.log(len(data)) - 2 * loglik
                    
                    result = {
                        'distribution': 'skewed_normal',
                        'parameters': {'skewness': a, 'location': loc, 'scale': scale},
                        'log_likelihood': loglik,
                        'aic': aic,
                        'bic': bic,
                        'fitted_distribution': stats.skewnorm(a, loc, scale)
                    }
                    
            elif distribution == 'gev':
                if method == 'mle':
                    # Fit Generalized Extreme Value distribution
                    params = stats.genextreme.fit(data)
                    c, loc, scale = params
                    
                    # Calculate log-likelihood
                    loglik = np.sum(stats.genextreme.logpdf(data, c, loc, scale))
                    
                    # Calculate AIC and BIC
                    k = 3  # number of parameters
                    aic = 2 * k - 2 * loglik
                    bic = k * np.log(len(data)) - 2 * loglik
                    
                    result = {
                        'distribution': 'gev',
                        'parameters': {'shape': c, 'location': loc, 'scale': scale},
                        'log_likelihood': loglik,
                        'aic': aic,
                        'bic': bic,
                        'fitted_distribution': stats.genextreme(c, loc, scale)
                    }
            
            else:
                raise ValueError(f"Unknown distribution: {distribution}")
            
            # Store results
            metric_name = output_name if output_name else f"{col}_distribution"
            new_pipe.distributions[metric_name] = result
            new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _fit_distribution


def calculate_var(
    columns: Union[str, List[str]],
    confidence_level: float = 0.05,
    method: str = 'historical',
    window: Optional[int] = None,
    distribution: Optional[str] = None,
    output_name: Optional[str] = None
):
    """
    Calculate Value at Risk (VaR) for specified columns
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate VaR for
    confidence_level : float, default=0.05
        Confidence level (e.g., 0.05 for 5% VaR)
    method : str, default='historical'
        Method: 'historical', 'parametric', 'monte_carlo'
    window : int, optional
        Rolling window size for historical method
    distribution : str, optional
        Distribution to use for parametric method
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that calculates VaR in a RiskPipe
    """
    def _calculate_var(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        var_results = {}
        
        for col in cols:
            data = df[col].dropna()
            
            if len(data) < 10:
                warnings.warn(f"Insufficient data for column '{col}' (need at least 10 observations)")
                continue
            
            if method == 'historical':
                # Historical simulation method
                if window is None:
                    # Use all available data
                    var_value = np.percentile(data, confidence_level * 100)
                else:
                    # Rolling window VaR
                    var_series = data.rolling(window=window).quantile(confidence_level)
                    var_value = var_series.iloc[-1]  # Latest VaR
                
                result = {
                    'method': 'historical',
                    'var': var_value,
                    'confidence_level': confidence_level
                }
                
            elif method == 'parametric':
                # Parametric method (assumes normal distribution by default)
                if distribution is None or distribution == 'normal':
                    mu = np.mean(data)
                    sigma = np.std(data, ddof=1)
                    var_value = stats.norm.ppf(confidence_level, mu, sigma)
                    
                    result = {
                        'method': 'parametric',
                        'distribution': 'normal',
                        'var': var_value,
                        'confidence_level': confidence_level,
                        'parameters': {'mu': mu, 'sigma': sigma}
                    }
                    
                elif distribution == 'student_t':
                    # Use fitted t-distribution if available
                    dist_key = f"{col}_distribution"
                    if dist_key in new_pipe.distributions:
                        fitted_dist = new_pipe.distributions[dist_key]['fitted_distribution']
                        var_value = fitted_dist.ppf(confidence_level)
                    else:
                        # Fit on the fly
                        df_param, loc, scale = stats.t.fit(data)
                        var_value = stats.t.ppf(confidence_level, df_param, loc, scale)
                    
                    result = {
                        'method': 'parametric',
                        'distribution': 'student_t',
                        'var': var_value,
                        'confidence_level': confidence_level
                    }
                    
            elif method == 'monte_carlo':
                # Monte Carlo simulation
                # Use fitted distribution if available
                dist_key = f"{col}_distribution"
                if dist_key in new_pipe.distributions:
                    fitted_dist = new_pipe.distributions[dist_key]['fitted_distribution']
                    simulated_data = fitted_dist.rvs(size=10000)
                else:
                    # Default to normal distribution
                    mu = np.mean(data)
                    sigma = np.std(data, ddof=1)
                    simulated_data = np.random.normal(mu, sigma, 10000)
                
                var_value = np.percentile(simulated_data, confidence_level * 100)
                
                result = {
                    'method': 'monte_carlo',
                    'var': var_value,
                    'confidence_level': confidence_level,
                    'simulations': 10000
                }
            
            else:
                raise ValueError(f"Unknown method: {method}")
            
            var_results[col] = result
        
        # Store results
        metric_name = output_name if output_name else f"var_{method}"
        new_pipe.risk_metrics[metric_name] = var_results
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _calculate_var


def calculate_cvar(
    columns: Union[str, List[str]],
    confidence_level: float = 0.05,
    method: str = 'historical',
    output_name: Optional[str] = None
):
    """
    Calculate Conditional Value at Risk (CVaR/Expected Shortfall)
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate CVaR for
    confidence_level : float, default=0.05
        Confidence level (e.g., 0.05 for 5% CVaR)
    method : str, default='historical'
        Method: 'historical', 'parametric'
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that calculates CVaR in a RiskPipe
    """
    def _calculate_cvar(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        cvar_results = {}
        
        for col in cols:
            data = df[col].dropna()
            
            if len(data) < 10:
                warnings.warn(f"Insufficient data for column '{col}' (need at least 10 observations)")
                continue
            
            if method == 'historical':
                # Historical simulation method
                var_threshold = np.percentile(data, confidence_level * 100)
                tail_losses = data[data <= var_threshold]
                cvar_value = np.mean(tail_losses) if len(tail_losses) > 0 else var_threshold
                
                result = {
                    'method': 'historical',
                    'cvar': cvar_value,
                    'var_threshold': var_threshold,
                    'confidence_level': confidence_level,
                    'tail_observations': len(tail_losses)
                }
                
            elif method == 'parametric':
                # Parametric method (normal distribution)
                mu = np.mean(data)
                sigma = np.std(data, ddof=1)
                
                # CVaR for normal distribution
                var_value = stats.norm.ppf(confidence_level, mu, sigma)
                phi = stats.norm.pdf(stats.norm.ppf(confidence_level))
                cvar_value = mu - sigma * phi / confidence_level
                
                result = {
                    'method': 'parametric',
                    'distribution': 'normal',
                    'cvar': cvar_value,
                    'var_threshold': var_value,
                    'confidence_level': confidence_level,
                    'parameters': {'mu': mu, 'sigma': sigma}
                }
            
            else:
                raise ValueError(f"Unknown method: {method}")
            
            cvar_results[col] = result
        
        # Store results
        metric_name = output_name if output_name else f"cvar_{method}"
        new_pipe.risk_metrics[metric_name] = cvar_results
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _calculate_cvar


def calculate_portfolio_risk(
    columns: List[str],
    weights: Optional[List[float]] = None,
    confidence_level: float = 0.05,
    method: str = 'parametric',
    output_name: Optional[str] = None
):
    """
    Calculate portfolio-level risk metrics
    
    Parameters:
    -----------
    columns : List[str]
        Columns representing portfolio components
    weights : List[float], optional
        Portfolio weights (if None, assumes equal weights)
    confidence_level : float, default=0.05
        Confidence level for risk metrics
    method : str, default='parametric'
        Method: 'parametric', 'monte_carlo'
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that calculates portfolio risk in a RiskPipe
    """
    def _calculate_portfolio_risk(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Check if columns exist
        for col in columns:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Set equal weights if not provided
        if weights is None:
            weights = [1.0 / len(columns)] * len(columns)
        
        if len(weights) != len(columns):
            raise ValueError("Number of weights must match number of columns")
        
        # Get data for portfolio components
        portfolio_data = df[columns].dropna()
        
        if len(portfolio_data) < 10:
            raise ValueError("Insufficient data for portfolio analysis")
        
        # Convert weights to numpy array
        w = np.array(weights)
        
        if method == 'parametric':
            # Calculate portfolio statistics
            returns = portfolio_data.values
            portfolio_returns = returns @ w
            
            # Portfolio mean and variance
            mu_p = np.mean(portfolio_returns)
            var_p = np.var(portfolio_returns, ddof=1)
            vol_p = np.sqrt(var_p)
            
            # Covariance matrix approach
            mu_assets = np.mean(returns, axis=0)
            cov_matrix = np.cov(returns, rowvar=False)
            
            # Portfolio moments from covariance matrix
            mu_p_cov = w @ mu_assets
            var_p_cov = w @ cov_matrix @ w
            vol_p_cov = np.sqrt(var_p_cov)
            
            # VaR and CVaR
            var_value = stats.norm.ppf(confidence_level, mu_p, vol_p)
            phi = stats.norm.pdf(stats.norm.ppf(confidence_level))
            cvar_value = mu_p - vol_p * phi / confidence_level
            
            # Component contributions to risk
            marginal_var = cov_matrix @ w
            component_var = w * marginal_var
            
            result = {
                'method': 'parametric',
                'portfolio_return': mu_p,
                'portfolio_volatility': vol_p,
                'portfolio_var': var_value,
                'portfolio_cvar': cvar_value,
                'covariance_matrix': cov_matrix,
                'component_contributions': {
                    col: contrib for col, contrib in zip(columns, component_var)
                },
                'weights': {col: w for col, w in zip(columns, weights)},
                'confidence_level': confidence_level
            }
            
        elif method == 'monte_carlo':
            # Monte Carlo simulation
            n_simulations = 10000
            
            # Estimate parameters for each asset
            mu_assets = np.mean(portfolio_data, axis=0)
            cov_matrix = np.cov(portfolio_data, rowvar=False)
            
            # Generate correlated random returns
            simulated_returns = np.random.multivariate_normal(mu_assets, cov_matrix, n_simulations)
            
            # Calculate portfolio returns
            portfolio_returns = simulated_returns @ w
            
            # Calculate risk metrics
            var_value = np.percentile(portfolio_returns, confidence_level * 100)
            tail_losses = portfolio_returns[portfolio_returns <= var_value]
            cvar_value = np.mean(tail_losses)
            
            result = {
                'method': 'monte_carlo',
                'portfolio_return': np.mean(portfolio_returns),
                'portfolio_volatility': np.std(portfolio_returns),
                'portfolio_var': var_value,
                'portfolio_cvar': cvar_value,
                'simulated_returns': portfolio_returns,
                'weights': {col: w for col, w in zip(columns, weights)},
                'confidence_level': confidence_level,
                'n_simulations': n_simulations
            }
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Store results
        metric_name = output_name if output_name else f"portfolio_risk_{method}"
        new_pipe.risk_metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _calculate_portfolio_risk


def monte_carlo_simulation(
    columns: Union[str, List[str]],
    n_simulations: int = 10000,
    horizon: int = 1,
    method: str = 'bootstrap',
    distribution: Optional[str] = None,
    output_name: Optional[str] = None
):
    """
    Perform Monte Carlo simulation for risk assessment
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to simulate
    n_simulations : int, default=10000
        Number of simulation paths
    horizon : int, default=1
        Time horizon for simulation
    method : str, default='bootstrap'
        Simulation method: 'bootstrap', 'parametric'
    distribution : str, optional
        Distribution for parametric method
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that runs Monte Carlo simulation in a RiskPipe
    """
    def _monte_carlo_simulation(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        simulation_results = {}
        
        for col in cols:
            data = df[col].dropna()
            
            if len(data) < 10:
                warnings.warn(f"Insufficient data for column '{col}' (need at least 10 observations)")
                continue
            
            if method == 'bootstrap':
                # Bootstrap resampling
                simulated_paths = []
                for _ in range(n_simulations):
                    # Sample with replacement
                    path = np.random.choice(data, size=horizon, replace=True)
                    simulated_paths.append(path)
                
                simulated_paths = np.array(simulated_paths)
                
                result = {
                    'method': 'bootstrap',
                    'simulated_paths': simulated_paths,
                    'horizon': horizon,
                    'n_simulations': n_simulations,
                    'path_statistics': {
                        'mean': np.mean(simulated_paths, axis=1),
                        'std': np.std(simulated_paths, axis=1),
                        'min': np.min(simulated_paths, axis=1),
                        'max': np.max(simulated_paths, axis=1)
                    }
                }
                
            elif method == 'parametric':
                # Parametric simulation
                if distribution is None or distribution == 'normal':
                    mu = np.mean(data)
                    sigma = np.std(data, ddof=1)
                    
                    # Generate paths
                    simulated_paths = np.random.normal(mu, sigma, (n_simulations, horizon))
                    
                    result = {
                        'method': 'parametric',
                        'distribution': 'normal',
                        'simulated_paths': simulated_paths,
                        'horizon': horizon,
                        'n_simulations': n_simulations,
                        'parameters': {'mu': mu, 'sigma': sigma}
                    }
                    
                elif distribution == 'student_t':
                    # Use fitted t-distribution
                    df_param, loc, scale = stats.t.fit(data)
                    simulated_paths = stats.t.rvs(df_param, loc, scale, size=(n_simulations, horizon))
                    
                    result = {
                        'method': 'parametric',
                        'distribution': 'student_t',
                        'simulated_paths': simulated_paths,
                        'horizon': horizon,
                        'n_simulations': n_simulations,
                        'parameters': {'df': df_param, 'loc': loc, 'scale': scale}
                    }
                    
                else:
                    raise ValueError(f"Unknown distribution: {distribution}")
            
            else:
                raise ValueError(f"Unknown method: {method}")
            
            simulation_results[col] = result
        
        # Store results
        metric_name = output_name if output_name else f"simulation_{method}"
        new_pipe.simulations[metric_name] = simulation_results
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _monte_carlo_simulation


def stress_test(
    columns: Union[str, List[str]],
    scenarios: Dict[str, Dict[str, float]],
    base_case: Optional[Dict[str, float]] = None,
    output_name: Optional[str] = None
):
    """
    Perform stress testing with specified scenarios
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to stress test
    scenarios : Dict[str, Dict[str, float]]
        Stress scenarios (e.g., {'recession': {'returns': -0.1, 'volatility': 0.25}})
    base_case : Dict[str, float], optional
        Base case parameters (if None, uses historical data)
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that performs stress testing in a RiskPipe
    """
    def _stress_test(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        stress_results = {}
        
        for col in cols:
            data = df[col].dropna()
            
            if len(data) < 10:
                warnings.warn(f"Insufficient data for column '{col}' (need at least 10 observations)")
                continue
            
            # Base case parameters
            if base_case is None:
                base_mu = np.mean(data)
                base_sigma = np.std(data, ddof=1)
                base_params = {'returns': base_mu, 'volatility': base_sigma}
            else:
                base_params = base_case
            
            column_results = {'base_case': base_params}
            
            # Apply each stress scenario
            for scenario_name, scenario_params in scenarios.items():
                # Create stressed parameters
                stressed_params = base_params.copy()
                stressed_params.update(scenario_params)
                
                # Calculate stressed risk metrics
                stressed_mu = stressed_params.get('returns', base_params['returns'])
                stressed_sigma = stressed_params.get('volatility', base_params['volatility'])
                
                # Calculate VaR and CVaR under stress
                var_95 = stats.norm.ppf(0.05, stressed_mu, stressed_sigma)
                var_99 = stats.norm.ppf(0.01, stressed_mu, stressed_sigma)
                
                phi_95 = stats.norm.pdf(stats.norm.ppf(0.05))
                phi_99 = stats.norm.pdf(stats.norm.ppf(0.01))
                
                cvar_95 = stressed_mu - stressed_sigma * phi_95 / 0.05
                cvar_99 = stressed_mu - stressed_sigma * phi_99 / 0.01
                
                scenario_result = {
                    'parameters': stressed_params,
                    'var_95': var_95,
                    'var_99': var_99,
                    'cvar_95': cvar_95,
                    'cvar_99': cvar_99,
                    'return_impact': stressed_mu - base_params['returns'],
                    'volatility_impact': stressed_sigma - base_params['volatility']
                }
                
                column_results[scenario_name] = scenario_result
            
            stress_results[col] = column_results
        
        # Store results
        metric_name = output_name if output_name else "stress_test"
        new_pipe.stress_tests[metric_name] = stress_results
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _stress_test


def rolling_risk_metrics(
    columns: Union[str, List[str]],
    window: int = 252,
    metrics: List[str] = ['volatility', 'var', 'cvar'],
    confidence_level: float = 0.05,
    output_name: Optional[str] = None
):
    """
    Calculate rolling risk metrics over time
    
    Parameters:
    -----------
    columns : str or List[str]
        Column(s) to calculate rolling metrics for
    window : int, default=252
        Rolling window size
    metrics : List[str], default=['volatility', 'var', 'cvar']
        Metrics to calculate: 'volatility', 'var', 'cvar', 'skewness', 'kurtosis'
    confidence_level : float, default=0.05
        Confidence level for VaR/CVaR calculations
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that calculates rolling risk metrics in a RiskPipe
    """
    def _rolling_risk_metrics(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Convert columns to list if it's a string
        cols = [columns] if isinstance(columns, str) else columns
        
        # Check if columns exist
        for col in cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Calculate rolling metrics for each column
        for col in cols:
            data = df[col]
            
            if 'volatility' in metrics:
                df[f'{col}_rolling_vol'] = data.rolling(window=window).std()
            
            if 'var' in metrics:
                df[f'{col}_rolling_var'] = data.rolling(window=window).quantile(confidence_level)
            
            if 'cvar' in metrics:
                def rolling_cvar(x):
                    var_threshold = x.quantile(confidence_level)
                    tail_losses = x[x <= var_threshold]
                    return tail_losses.mean() if len(tail_losses) > 0 else var_threshold
                
                df[f'{col}_rolling_cvar'] = data.rolling(window=window).apply(rolling_cvar)
            
            if 'skewness' in metrics:
                df[f'{col}_rolling_skew'] = data.rolling(window=window).skew()
            
            if 'kurtosis' in metrics:
                df[f'{col}_rolling_kurt'] = data.rolling(window=window).kurt()
        
        # Store results
        metric_name = output_name if output_name else "rolling_risk_metrics"
        new_pipe.data = df
        new_pipe.risk_metrics[metric_name] = {
            'window': window,
            'metrics': metrics,
            'confidence_level': confidence_level
        }
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _rolling_risk_metrics


def correlation_analysis(
    columns: List[str],
    method: str = 'pearson',
    rolling_window: Optional[int] = None,
    output_name: Optional[str] = None
):
    """
    Perform correlation analysis for risk assessment
    
    Parameters:
    -----------
    columns : List[str]
        Columns to analyze correlations for
    method : str, default='pearson'
        Correlation method: 'pearson', 'spearman', 'kendall'
    rolling_window : int, optional
        Window size for rolling correlations
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that performs correlation analysis in a RiskPipe
    """
    def _correlation_analysis(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Check if columns exist
        for col in columns:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        # Get data for analysis
        data = df[columns].dropna()
        
        if len(data) < 10:
            raise ValueError("Insufficient data for correlation analysis")
        
        # Calculate static correlation matrix
        corr_matrix = data.corr(method=method)
        
        # Calculate eigenvalues for stability analysis
        eigenvalues = np.linalg.eigvals(corr_matrix.values)
        condition_number = np.max(eigenvalues) / np.min(eigenvalues)
        
        result = {
            'correlation_matrix': corr_matrix,
            'eigenvalues': eigenvalues,
            'condition_number': condition_number,
            'method': method
        }
        
        # Calculate rolling correlations if requested
        if rolling_window is not None:
            rolling_corr = {}
            for i, col1 in enumerate(columns):
                for j, col2 in enumerate(columns):
                    if i < j:  # Only upper triangle
                        pair_name = f"{col1}_{col2}"
                        rolling_corr[pair_name] = data[col1].rolling(rolling_window).corr(data[col2])
            
            result['rolling_correlations'] = rolling_corr
            result['rolling_window'] = rolling_window
        
        # Store results
        metric_name = output_name if output_name else f"correlation_{method}"
        new_pipe.risk_metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _correlation_analysis


def risk_attribution(
    columns: List[str],
    weights: List[float],
    confidence_level: float = 0.05,
    output_name: Optional[str] = None
):
    """
    Perform risk attribution analysis
    
    Parameters:
    -----------
    columns : List[str]
        Portfolio components
    weights : List[float]
        Portfolio weights
    confidence_level : float, default=0.05
        Confidence level for risk calculations
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that performs risk attribution in a RiskPipe
    """
    def _risk_attribution(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        # Check if columns exist
        for col in columns:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        if len(weights) != len(columns):
            raise ValueError("Number of weights must match number of columns")
        
        # Get data
        data = df[columns].dropna()
        
        if len(data) < 10:
            raise ValueError("Insufficient data for risk attribution")
        
        # Convert weights to numpy array
        w = np.array(weights)
        
        # Calculate portfolio statistics
        returns = data.values
        mu = np.mean(returns, axis=0)
        cov_matrix = np.cov(returns, rowvar=False)
        
        # Portfolio variance
        portfolio_var = w @ cov_matrix @ w
        portfolio_vol = np.sqrt(portfolio_var)
        
        # Marginal contribution to risk
        marginal_contrib = cov_matrix @ w / portfolio_vol
        
        # Component contribution to risk
        component_contrib = w * marginal_contrib
        
        # Percentage contribution
        pct_contrib = component_contrib / portfolio_vol
        
        # Risk-adjusted returns (Sharpe-like ratio)
        risk_adj_returns = mu / np.sqrt(np.diag(cov_matrix))
        
        result = {
            'portfolio_volatility': portfolio_vol,
            'marginal_contributions': {
                col: contrib for col, contrib in zip(columns, marginal_contrib)
            },
            'component_contributions': {
                col: contrib for col, contrib in zip(columns, component_contrib)
            },
            'percentage_contributions': {
                col: contrib for col, contrib in zip(columns, pct_contrib)
            },
            'risk_adjusted_returns': {
                col: ratio for col, ratio in zip(columns, risk_adj_returns)
            },
            'weights': {col: w for col, w in zip(columns, weights)},
            'covariance_matrix': cov_matrix
        }
        
        # Store results
        metric_name = output_name if output_name else "risk_attribution"
        new_pipe.risk_metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _risk_attribution


def get_risk_summary():
    """
    Get a summary of all risk analysis results
    
    Returns:
    --------
    Callable
        Function that returns risk summary from a RiskPipe
    """
    def _get_risk_summary(pipe):
        if not any([pipe.risk_metrics, pipe.distributions, pipe.simulations, pipe.stress_tests]):
            raise ValueError("No risk analyses found. Run risk calculations first.")
        
        summary = {
            'risk_metrics': pipe.risk_metrics,
            'distributions': pipe.distributions,
            'simulations': pipe.simulations,
            'stress_tests': pipe.stress_tests
        }
        
        return summary
    
    return _get_risk_summary


def compare_distributions(
    column: str,
    distributions: List[str] = ['normal', 'student_t', 'skewed_normal'],
    output_name: Optional[str] = None
):
    """
    Compare multiple distribution fits and select the best one
    
    Parameters:
    -----------
    column : str
        Column to fit distributions for
    distributions : List[str], default=['normal', 'student_t', 'skewed_normal']
        Distributions to compare
    output_name : str, optional
        Name for the output results
        
    Returns:
    --------
    Callable
        Function that compares distributions in a RiskPipe
    """
    def _compare_distributions(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()  # Ensure we work with a copy
        
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in data")
        
        data = df[column].dropna()
        
        if len(data) < 10:
            raise ValueError("Insufficient data for distribution comparison")
        
        comparison_results = {}
        
        for dist in distributions:
            try:
                # Fit distribution
                temp_pipe = new_pipe.copy()
                temp_pipe = fit_distribution(
                    columns=column,
                    distribution=dist,
                    output_name=f"temp_{dist}"
                )(temp_pipe)
                
                # Extract results
                dist_result = temp_pipe.distributions[f"temp_{dist}"]
                
                comparison_results[dist] = {
                    'aic': dist_result.get('aic', np.inf),
                    'bic': dist_result.get('bic', np.inf),
                    'log_likelihood': dist_result.get('log_likelihood', -np.inf),
                    'parameters': dist_result['parameters']
                }
                
            except Exception as e:
                warnings.warn(f"Failed to fit {dist} distribution: {str(e)}")
                comparison_results[dist] = {
                    'aic': np.inf,
                    'bic': np.inf,
                    'log_likelihood': -np.inf,
                    'error': str(e)
                }
        
        # Select best distribution based on AIC
        best_dist = min(comparison_results.keys(), 
                       key=lambda x: comparison_results[x]['aic'])
        
        result = {
            'comparison_results': comparison_results,
            'best_distribution': best_dist,
            'selection_criterion': 'aic'
        }
        
        # Store results
        metric_name = output_name if output_name else f"{column}_distribution_comparison"
        new_pipe.risk_metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _compare_distributions