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


class RiskPipe:
    """
    A pipeline-style risk analysis tool that enables functional composition
    with a meterstick-like interface for maximum likelihood and risk calculations.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
        self.risk_metrics = {}
        self.distributions = {}
        self.simulations = {}
        self.stress_tests = {}
        self.current_metric = None
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe RiskPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = RiskPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        new_pipe.risk_metrics = self.risk_metrics.copy()
        new_pipe.distributions = self.distributions.copy()
        new_pipe.simulations = self.simulations.copy()
        new_pipe.stress_tests = self.stress_tests.copy()
        new_pipe.current_metric = self.current_metric
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create a RiskPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        return pipe


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
        df = new_pipe.data
        
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
        df = new_pipe.data
        
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
        df = new_pipe.data
        
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
        df = new_pipe.data
        
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
        df = new_pipe.data
        
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
        df = new_pipe.data
        
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
        df = new_pipe.data.copy()
        
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
        df = new_pipe.data
        
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
        df = new_pipe.data
        
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
        df = new_pipe.data
        
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