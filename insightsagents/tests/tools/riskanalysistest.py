import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.tools.mltools.riskanalysis import (
    RiskPipe,
    fit_distribution,
    calculate_var,
    calculate_cvar,
    calculate_portfolio_risk,
    monte_carlo_simulation,
    stress_test,
    rolling_risk_metrics,
    correlation_analysis,
    risk_attribution,
    compare_distributions
)

# Example of using the composable risk analysis tool on financial data

def main():
    # Step 1: Load data
    returns_df, portfolio_df = load_sample_data()
    print(f"Loaded {len(returns_df)} daily returns and {len(portfolio_df)} portfolio positions")
    
    # Step 2: Run various risk analyses
    
    # Example 1: Distribution fitting and VaR calculation
    print("\n=== DISTRIBUTION FITTING AND VAR ANALYSIS ===")
    var_results = analyze_var_and_distributions(returns_df)
    print_var_results(var_results)
    
    # Example 2: Portfolio risk analysis
    print("\n=== PORTFOLIO RISK ANALYSIS ===")
    portfolio_results = analyze_portfolio_risk(portfolio_df)
    print_portfolio_results(portfolio_results)
    
    # Example 3: Monte Carlo simulation
    print("\n=== MONTE CARLO SIMULATION ===")
    simulation_results = run_monte_carlo_simulation(returns_df)
    print_simulation_results(simulation_results)
    
    # Example 4: Stress testing
    print("\n=== STRESS TESTING ===")
    stress_results = run_stress_tests(returns_df)
    print_stress_results(stress_results)
    
    # Example 5: Rolling risk metrics
    print("\n=== ROLLING RISK METRICS ===")
    rolling_results = analyze_rolling_risk(returns_df)
    print_rolling_results(rolling_results)
    
    # Example 6: Correlation analysis
    print("\n=== CORRELATION ANALYSIS ===")
    correlation_results = analyze_correlations(returns_df)
    print_correlation_results(correlation_results)
    
    # Example 7: Risk attribution
    print("\n=== RISK ATTRIBUTION ===")
    attribution_results = analyze_risk_attribution(portfolio_df)
    print_attribution_results(attribution_results)
    
    return {
        'var': var_results,
        'portfolio': portfolio_results,
        'simulation': simulation_results,
        'stress': stress_results,
        'rolling': rolling_results,
        'correlation': correlation_results,
        'attribution': attribution_results
    }


def load_sample_data(n_days=1000, n_assets=5):
    """Generate synthetic financial data for risk analysis"""
    np.random.seed(42)
    
    # Generate dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Generate asset returns with different characteristics
    assets = ['SPY', 'QQQ', 'GLD', 'TLT', 'VXX']  # ETFs representing different asset classes
    
    # Define asset characteristics (mean, volatility, correlation structure)
    asset_params = {
        'SPY': {'mu': 0.0008, 'sigma': 0.015, 'sector': 'equity'},      # S&P 500
        'QQQ': {'mu': 0.0010, 'sigma': 0.020, 'sector': 'equity'},      # NASDAQ
        'GLD': {'mu': 0.0003, 'sigma': 0.012, 'sector': 'commodity'},   # Gold
        'TLT': {'mu': 0.0002, 'sigma': 0.008, 'sector': 'bond'},        # Long-term bonds
        'VXX': {'mu': -0.0020, 'sigma': 0.040, 'sector': 'volatility'}  # Volatility ETF
    }
    
    # Create correlation matrix (realistic correlations between assets)
    correlation_matrix = np.array([
        [1.00, 0.85, 0.15, -0.20, -0.60],  # SPY
        [0.85, 1.00, 0.10, -0.15, -0.65],  # QQQ
        [0.15, 0.10, 1.00, 0.05, -0.10],   # GLD
        [-0.20, -0.15, 0.05, 1.00, -0.30], # TLT
        [-0.60, -0.65, -0.10, -0.30, 1.00] # VXX
    ])
    
    # Generate correlated returns
    returns_data = {}
    
    # Start with independent normal random variables
    independent_returns = {}
    for asset in assets:
        params = asset_params[asset]
        independent_returns[asset] = np.random.normal(
            params['mu'], 
            params['sigma'], 
            len(dates)
        )
    
    # Apply correlation structure using Cholesky decomposition
    L = np.linalg.cholesky(correlation_matrix)
    
    # Generate correlated returns
    for i, asset in enumerate(assets):
        correlated_return = np.zeros(len(dates))
        for j in range(i + 1):
            correlated_return += L[i, j] * independent_returns[assets[j]]
        returns_data[asset] = correlated_return
    
    # Add some market regime changes and volatility clustering
    for asset in assets:
        # Add volatility clustering (GARCH-like effects)
        volatility = np.ones(len(dates))
        for t in range(1, len(dates)):
            volatility[t] = 0.95 * volatility[t-1] + 0.05 * returns_data[asset][t-1]**2
        
        # Apply volatility scaling
        returns_data[asset] = returns_data[asset] * np.sqrt(volatility)
        
        # Add some extreme events (market crashes)
        crash_dates = np.random.choice(len(dates), size=5, replace=False)
        for crash_date in crash_dates:
            returns_data[asset][crash_date] *= -3  # 3x larger negative return
    
    # Create returns dataframe
    returns_df = pd.DataFrame(returns_data, index=dates)
    
    # Create portfolio positions dataframe (starting with $100k in each asset)
    portfolio_df = pd.DataFrame({
        'asset': assets,
        'position': [100000] * len(assets),  # $100k in each asset
        'weight': [0.2] * len(assets),       # Equal weights
        'sector': [asset_params[asset]['sector'] for asset in assets]
    })
    
    return returns_df, portfolio_df


def analyze_var_and_distributions(returns_df):
    """Analyze VaR and fit distributions to returns"""
    # Use the pipeline pattern to analyze VaR and distributions
    result = (RiskPipe.from_dataframe(returns_df)
              # Fit normal distribution to SPY returns
              | fit_distribution(
                  columns='SPY',
                  distribution='normal',
                  method='mle',
                  output_name='spy_normal_fit'
              )
              # Compare multiple distributions for QQQ
              | compare_distributions(
                  column='QQQ',
                  distributions=['normal', 'student_t', 'skewed_normal'],
                  output_name='qqq_distribution_comparison'
              )
              # Calculate VaR using different methods
              | calculate_var(
                  columns=['SPY', 'QQQ', 'GLD'],
                  confidence_level=0.05,
                  method='historical',
                  output_name='historical_var'
              )
              | calculate_var(
                  columns=['SPY', 'QQQ', 'GLD'],
                  confidence_level=0.05,
                  method='parametric',
                  output_name='parametric_var'
              )
              # Calculate CVaR
              | calculate_cvar(
                  columns=['SPY', 'QQQ', 'GLD'],
                  confidence_level=0.05,
                  method='historical',
                  output_name='historical_cvar'
              )
    )
    
    return {
        'distributions': result.distributions,
        'var_metrics': result.risk_metrics,
        'current_metric': result.current_metric
    }


def analyze_portfolio_risk(portfolio_df):
    """Analyze portfolio-level risk metrics"""
    # Create a returns dataframe for portfolio analysis
    returns_df, _ = load_sample_data()
    
    # Use the pipeline pattern to analyze portfolio risk
    result = (RiskPipe.from_dataframe(returns_df)
              # Calculate portfolio risk with equal weights
              | calculate_portfolio_risk(
                  columns=['SPY', 'QQQ', 'GLD', 'TLT', 'VXX'],
                  weights=[0.2, 0.2, 0.2, 0.2, 0.2],
                  confidence_level=0.05,
                  method='parametric',
                  output_name='equal_weight_portfolio'
              )
              # Calculate portfolio risk with different weights
              | calculate_portfolio_risk(
                  columns=['SPY', 'QQQ', 'GLD', 'TLT', 'VXX'],
                  weights=[0.4, 0.3, 0.1, 0.15, 0.05],  # More equity heavy
                  confidence_level=0.05,
                  method='monte_carlo',
                  output_name='equity_heavy_portfolio'
              )
    )
    
    return result.risk_metrics


def run_monte_carlo_simulation(returns_df):
    """Run Monte Carlo simulations for risk assessment"""
    # Use the pipeline pattern to run Monte Carlo simulations
    result = (RiskPipe.from_dataframe(returns_df)
              # Bootstrap simulation for SPY
              | monte_carlo_simulation(
                  columns='SPY',
                  n_simulations=10000,
                  horizon=30,  # 30-day horizon
                  method='bootstrap',
                  output_name='spy_bootstrap_simulation'
              )
              # Parametric simulation for QQQ
              | monte_carlo_simulation(
                  columns='QQQ',
                  n_simulations=10000,
                  horizon=30,
                  method='parametric',
                  distribution='student_t',
                  output_name='qqq_parametric_simulation'
              )
    )
    
    return result.simulations


def run_stress_tests(returns_df):
    """Run stress tests with different scenarios"""
    # Define stress scenarios
    scenarios = {
        'market_crash': {
            'returns': -0.15,  # 15% decline in returns
            'volatility': 0.35  # 35% volatility
        },
        'recession': {
            'returns': -0.08,  # 8% decline in returns
            'volatility': 0.25  # 25% volatility
        },
        'volatility_spike': {
            'returns': -0.02,  # 2% decline in returns
            'volatility': 0.40  # 40% volatility
        }
    }
    
    # Use the pipeline pattern to run stress tests
    result = (RiskPipe.from_dataframe(returns_df)
              | stress_test(
                  columns=['SPY', 'QQQ', 'GLD'],
                  scenarios=scenarios,
                  output_name='market_stress_test'
              )
    )
    
    return result.stress_tests


def analyze_rolling_risk(returns_df):
    """Analyze rolling risk metrics over time"""
    # Use the pipeline pattern to calculate rolling risk metrics
    result = (RiskPipe.from_dataframe(returns_df)
              | rolling_risk_metrics(
                  columns=['SPY', 'QQQ', 'GLD'],
                  window=252,  # 1 year rolling window
                  metrics=['volatility', 'var', 'cvar', 'skewness', 'kurtosis'],
                  confidence_level=0.05,
                  output_name='rolling_risk_metrics'
              )
    )
    
    return {
        'rolling_data': result.data,
        'metrics_info': result.risk_metrics['rolling_risk_metrics']
    }


def analyze_correlations(returns_df):
    """Analyze correlations between assets"""
    # Use the pipeline pattern to analyze correlations
    result = (RiskPipe.from_dataframe(returns_df)
              | correlation_analysis(
                  columns=['SPY', 'QQQ', 'GLD', 'TLT', 'VXX'],
                  method='pearson',
                  rolling_window=60,  # 60-day rolling correlations
                  output_name='asset_correlations'
              )
    )
    
    return result.risk_metrics['asset_correlations']


def analyze_risk_attribution(portfolio_df):
    """Analyze risk attribution for portfolio components"""
    # Create a returns dataframe for attribution analysis
    returns_df, _ = load_sample_data()
    
    # Use the pipeline pattern to analyze risk attribution
    result = (RiskPipe.from_dataframe(returns_df)
              | risk_attribution(
                  columns=['SPY', 'QQQ', 'GLD', 'TLT', 'VXX'],
                  weights=[0.4, 0.3, 0.1, 0.15, 0.05],
                  confidence_level=0.05,
                  output_name='portfolio_risk_attribution'
              )
    )
    
    return result.risk_metrics['portfolio_risk_attribution']


def print_var_results(var_results):
    """Print VaR and distribution results in a readable format"""
    print("\nDistribution Fitting Results:")
    for metric_name, result in var_results['distributions'].items():
        print(f"\n{metric_name}:")
        print(f"  Distribution: {result['distribution']}")
        print(f"  Parameters: {result['parameters']}")
        if 'aic' in result:
            print(f"  AIC: {result['aic']:.2f}")
            print(f"  BIC: {result['bic']:.2f}")
            print(f"  Log-likelihood: {result['log_likelihood']:.2f}")
    
    print("\nVaR Results (5% confidence level):")
    for metric_name, result in var_results['var_metrics'].items():
        if 'var' in metric_name.lower():  # Only process VaR metrics
            print(f"\n{metric_name}:")
            for asset, asset_result in result.items():
                if isinstance(asset_result, dict) and 'var' in asset_result:
                    print(f"  {asset}: {asset_result['var']:.4f} ({asset_result['method']})")
    
    print("\nCVaR Results (5% confidence level):")
    cvar_results = var_results['var_metrics'].get('historical_cvar', {})
    for asset, asset_result in cvar_results.items():
        if isinstance(asset_result, dict) and 'cvar' in asset_result:
            print(f"  {asset}: {asset_result['cvar']:.4f} (historical)")


def print_portfolio_results(portfolio_results):
    """Print portfolio risk results in a readable format"""
    print("\nEqual Weight Portfolio (20% each asset):")
    equal_weight = portfolio_results.get('equal_weight_portfolio', {})
    if 'portfolio_return' in equal_weight:
        print(f"  Portfolio Return: {equal_weight['portfolio_return']:.4f}")
        print(f"  Portfolio Volatility: {equal_weight['portfolio_volatility']:.4f}")
        print(f"  Portfolio VaR (5%): {equal_weight['portfolio_var']:.4f}")
        print(f"  Portfolio CVaR (5%): {equal_weight['portfolio_cvar']:.4f}")
        
        if 'component_contributions' in equal_weight:
            print("\nComponent Contributions to Risk:")
            for asset, contrib in equal_weight['component_contributions'].items():
                print(f"  {asset}: {contrib:.4f}")
    
    print("\nEquity Heavy Portfolio (40% SPY, 30% QQQ, etc.):")
    equity_heavy = portfolio_results.get('equity_heavy_portfolio', {})
    if 'portfolio_return' in equity_heavy:
        print(f"  Portfolio Return: {equity_heavy['portfolio_return']:.4f}")
        print(f"  Portfolio Volatility: {equity_heavy['portfolio_volatility']:.4f}")
        print(f"  Portfolio VaR (5%): {equity_heavy['portfolio_var']:.4f}")
        print(f"  Portfolio CVaR (5%): {equity_heavy['portfolio_cvar']:.4f}")


def print_simulation_results(simulation_results):
    """Print Monte Carlo simulation results in a readable format"""
    print("\nSPY Bootstrap Simulation (30-day horizon):")
    spy_sim = simulation_results.get('spy_bootstrap_simulation', {}).get('SPY', {})
    if spy_sim:
        print(f"  Method: {spy_sim.get('method', 'N/A')}")
        print(f"  Simulations: {spy_sim.get('n_simulations', 'N/A')}")
        print(f"  Horizon: {spy_sim.get('horizon', 'N/A')} days")
        
        # Calculate some statistics from the simulated paths
        if 'simulated_paths' in spy_sim:
            paths = spy_sim['simulated_paths']
            cumulative_returns = np.sum(paths, axis=1)
            print(f"  Mean 30-day return: {np.mean(cumulative_returns):.4f}")
            print(f"  Std 30-day return: {np.std(cumulative_returns):.4f}")
            print(f"  Worst 30-day return: {np.min(cumulative_returns):.4f}")
            print(f"  Best 30-day return: {np.max(cumulative_returns):.4f}")
    
    print("\nQQQ Parametric Simulation (30-day horizon):")
    qqq_sim = simulation_results.get('qqq_parametric_simulation', {}).get('QQQ', {})
    if qqq_sim:
        print(f"  Method: {qqq_sim.get('method', 'N/A')}")
        print(f"  Distribution: {qqq_sim.get('distribution', 'N/A')}")
        print(f"  Parameters: {qqq_sim.get('parameters', 'N/A')}")


def print_stress_results(stress_results):
    """Print stress test results in a readable format"""
    stress_test = stress_results.get('market_stress_test', {})
    
    print("\nStress Test Results for SPY:")
    spy_results = stress_test.get('SPY', {})
    
    if 'base_case' in spy_results:
        print("\nBase Case:")
        base = spy_results['base_case']
        print(f"  Returns: {base.get('returns', 'N/A'):.4f}")
        print(f"  Volatility: {base.get('volatility', 'N/A'):.4f}")
        
        for scenario, scenario_result in spy_results.items():
            if scenario != 'base_case':
                print(f"\n{scenario.replace('_', ' ').title()}:")
                print(f"  VaR (95%): {scenario_result.get('var_95', 'N/A'):.4f}")
                print(f"  VaR (99%): {scenario_result.get('var_99', 'N/A'):.4f}")
                print(f"  CVaR (95%): {scenario_result.get('cvar_95', 'N/A'):.4f}")
                print(f"  CVaR (99%): {scenario_result.get('cvar_99', 'N/A'):.4f}")
                print(f"  Return Impact: {scenario_result.get('return_impact', 'N/A'):.4f}")
                print(f"  Volatility Impact: {scenario_result.get('volatility_impact', 'N/A'):.4f}")


def print_rolling_results(rolling_results):
    """Print rolling risk metrics results in a readable format"""
    print("\nRolling Risk Metrics (252-day window):")
    
    # Get the latest values for each metric
    data = rolling_results.get('rolling_data', pd.DataFrame())
    if not data.empty:
        latest_date = data.index[-1]
        
        print(f"\nLatest values (as of {latest_date.strftime('%Y-%m-%d')}):")
        for asset in ['SPY', 'QQQ', 'GLD']:
            print(f"\n{asset}:")
            if f'{asset}_rolling_vol' in data.columns:
                vol = data[f'{asset}_rolling_vol'].iloc[-1]
                print(f"  Volatility: {vol:.4f}")
            if f'{asset}_rolling_var' in data.columns:
                var = data[f'{asset}_rolling_var'].iloc[-1]
                print(f"  VaR (5%): {var:.4f}")
            if f'{asset}_rolling_cvar' in data.columns:
                cvar = data[f'{asset}_rolling_cvar'].iloc[-1]
                print(f"  CVaR (5%): {cvar:.4f}")


def print_correlation_results(correlation_results):
    """Print correlation analysis results in a readable format"""
    print("\nAsset Correlation Matrix:")
    corr_matrix = correlation_results.get('correlation_matrix', pd.DataFrame())
    if not corr_matrix.empty:
        print(corr_matrix.round(3))
    
    print(f"\nCorrelation Analysis:")
    print(f"  Method: {correlation_results.get('method', 'N/A')}")
    print(f"  Condition Number: {correlation_results.get('condition_number', 'N/A'):.2f}")
    
    if 'rolling_correlations' in correlation_results:
        print(f"\nRolling Correlations (60-day window):")
        rolling_corr = correlation_results['rolling_correlations']
        for pair, corr_series in rolling_corr.items():
            if not corr_series.empty:
                latest_corr = corr_series.iloc[-1]
                print(f"  {pair}: {latest_corr:.3f}")


def print_attribution_results(attribution_results):
    """Print risk attribution results in a readable format"""
    print("\nRisk Attribution Analysis:")
    print(f"  Portfolio Volatility: {attribution_results.get('portfolio_volatility', 'N/A'):.4f}")
    
    if 'component_contributions' in attribution_results:
        print("\nComponent Contributions to Risk:")
        for asset, contrib in attribution_results['component_contributions'].items():
            print(f"  {asset}: {contrib:.4f}")
    
    if 'percentage_contributions' in attribution_results:
        print("\nPercentage Contributions to Risk:")
        for asset, pct in attribution_results['percentage_contributions'].items():
            print(f"  {asset}: {pct*100:.1f}%")
    
    if 'risk_adjusted_returns' in attribution_results:
        print("\nRisk-Adjusted Returns (Sharpe-like):")
        for asset, ratio in attribution_results['risk_adjusted_returns'].items():
            print(f"  {asset}: {ratio:.4f}")


if __name__ == "__main__":
    results = main()
    
    # Example of how the results could be used for risk management decisions
    print("\n=== RISK MANAGEMENT APPLICATIONS ===")
    
    # VaR insights
    var_results = results['var']['var_metrics'].get('historical_var', {})
    print("\n1. VaR Insights:")
    for asset, asset_result in var_results.items():
        if isinstance(asset_result, dict) and 'var' in asset_result:
            var_value = asset_result['var']
            print(f"   {asset}: 5% VaR = {var_value:.4f}")
            if asset == 'VXX':
                print(f"   → Action: VXX has highest risk, consider reducing position size")
    
    # Portfolio insights
    portfolio_results = results['portfolio'].get('equal_weight_portfolio', {})
    print("\n2. Portfolio Risk Insights:")
    if 'portfolio_var' in portfolio_results:
        print(f"   Equal weight portfolio VaR: {portfolio_results['portfolio_var']:.4f}")
        print(f"   → Action: Consider rebalancing to reduce concentration risk")
    
    # Stress test insights
    stress_results = results['stress'].get('market_stress_test', {}).get('SPY', {}).get('market_crash', {})
    print("\n3. Stress Test Insights:")
    if 'var_95' in stress_results:
        print(f"   Market crash scenario VaR: {stress_results['var_95']:.4f}")
        print(f"   → Action: Ensure sufficient capital buffers for extreme scenarios")
    
    # Correlation insights
    correlation_results = results['correlation'].get('correlation_matrix', pd.DataFrame())
    if not correlation_results.empty and 'SPY' in correlation_results.index and 'QQQ' in correlation_results.columns:
        spy_qqq_corr = correlation_results.loc['SPY', 'QQQ']
        print("\n4. Correlation Insights:")
        print(f"   SPY-QQQ correlation: {spy_qqq_corr:.3f}")
        print(f"   → Action: High correlation suggests limited diversification benefit")
    
    # Risk attribution insights
    attribution_results = results['attribution']
    print("\n5. Risk Attribution Insights:")
    if 'percentage_contributions' in attribution_results:
        for asset, pct in attribution_results['percentage_contributions'].items():
            if pct > 0.3:  # Assets contributing more than 30% to risk
                print(f"   {asset} contributes {pct*100:.1f}% to portfolio risk")
                print(f"   → Action: Consider reducing position in {asset}") 