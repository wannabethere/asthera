from app.tools.mltools.cohortanalysistools import (
    CohortPipe,
    form_time_cohorts,
    form_behavioral_cohorts,
    form_acquisition_cohorts,
    calculate_retention,
    calculate_conversion,
    calculate_lifetime_value    
)

from app.tools.mltools.segmentationtools import (
    SegmentationPipe,
    get_features,
    run_kmeans,
    run_dbscan,
    run_hierarchical,
    run_rule_based,
    generate_summary,
    get_segment_data,
    compare_algorithms,
    custom_calculation
)

from app.tools.mltools.trendanalysistools import (
    TrendPipe,
    aggregate_by_time,
    calculate_growth_rates,
    calculate_moving_average,
    calculate_statistical_trend,
    decompose_trend,
    forecast_metric,    
    compare_periods,
    get_top_metrics,
    _test_trend
)

from app.tools.mltools.funnelanalysis import (
    analyze_funnel,
    analyze_funnel_by_time,
    analyze_user_paths,
    analyze_funnel_by_segment,
    get_funnel_summary,
    compare_segments
)

from app.tools.mltools.timeseriesanalysis   import (
    TimeSeriesPipe,        
    lead,
    lag,
    distribution_analysis,
    cumulative_distribution,
    variance_analysis,
    custom_calculation,
    get_distribution_summary,
    rolling_window
)

from app.tools.mltools.metrics_tools import (
    MetricsPipe,
    Mean,
    Sum,
    Count,
    Max,
    Min,
    Ratio,
    Dot,
    Nth,
    Variance,
    StandardDeviation,
    CV,
    Correlation,
    Cov,
    Median,
    Percentile,
    PivotTable,
    GroupBy,
    Filter,
    CumulativeSum,
    RollingMetric,
    Execute,
    ShowPivot,
    ShowDataFrame
)

from app.tools.mltools.operations_tools import (
    OperationsPipe,
    PercentChange,
    AbsoluteChange,
    MH,
    CUPED,
    PrePostChange,
    SelectColumns,
    FilterConditions,
    PowerAnalysis,
    StratifiedSummary,
    BootstrapCI,
    MultiComparisonAdjustment,
    ExecuteOperations,
    ShowOperation,
    ShowComparison
)

from app.tools.mltools.movingaverages import (
    MovingAggrPipe,
    moving_average,
    moving_variance,
    moving_sum,
    moving_quantile,
    moving_correlation,
    moving_zscore,
    moving_apply_by_group,
    moving_ratio,
    detect_turning_points,
    moving_regression,
    moving_min_max,
    moving_count,
    moving_aggregate,
    moving_percentile_rank,
    time_weighted_average,
    moving_cumulative,
    expanding_window
)

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
    get_risk_summary,
    compare_distributions
)

from app.tools.mltools.anomalydetection import (
    AnomalyPipe,
    detect_statistical_outliers,
    detect_contextual_anomalies,
    detect_collective_anomalies,
    calculate_seasonal_residuals,
    detect_anomalies_from_residuals,
    get_anomaly_summary,
    get_top_anomalies,
    detect_change_points,
    forecast_and_detect_anomalies,
    batch_detect_anomalies
)

from app.tools.mltools.group_aggregation_functions import (
    # Basic aggregation functions
    mean,
    sum_values,
    count_values,
    max_value,
    min_value,
    std_dev,
    variance,
    median,
    quantile,
    range_values,
    coefficient_of_variation,
    skewness,
    kurtosis,
    unique_count,
    mode,
    weighted_average,
    geometric_mean,
    harmonic_mean,
    interquartile_range,
    mad,
    
    # Operations tool functions adapted for group aggregation
    percent_change,
    absolute_change,
    mantel_haenszel_estimate,
    cuped_adjustment,
    prepost_adjustment,
    power_analysis,
    stratified_summary,
    bootstrap_confidence_interval,
    multi_comparison_adjustment,
    effect_size,
    z_score,
    relative_risk,
    odds_ratio,
    
    # Utility functions
    get_function_by_name,
    get_all_function_names,
    get_function_metadata,
    get_all_functions_metadata,
    GROUP_AGGREGATION_FUNCTIONS
)


# Function Registry Components
from app.tools.mltools.registry import (
    MLFunctionRegistry,
    FunctionMetadata,
    initialize_function_registry,
    FunctionSearchInterface,
    SearchResult,
    create_search_interface,
    FunctionRetrievalService,
    create_function_retrieval_service
)


__all__ = [
    # Cohort Analysis
    'CohortPipe',
    'form_time_cohorts',
    'form_behavioral_cohorts',
    'form_acquisition_cohorts',
    'calculate_retention',
    'calculate_conversion',
    'calculate_lifetime_value', 

    # Segmentation
    'SegmentationPipe',
    'get_features',
    'run_kmeans',
    'run_dbscan', 
    'run_hierarchical',
    'run_rule_based',
    'generate_summary',
    'get_segment_data',
    'compare_algorithms',
    'custom_calculation',

    # Trend Analysis
    'TrendPipe',
    'aggregate_by_time',
    'calculate_growth_rates',
    'calculate_moving_average',
    'calculate_statistical_trend',
    'decompose_trend',
    'forecast_metric',
    'compare_periods',
    'get_top_metrics',
    '_test_trend',

    # Funnel Analysis
    'analyze_funnel',
    'analyze_funnel_by_time',
    'analyze_user_paths',
    'analyze_funnel_by_segment',
    'get_funnel_summary',
    'compare_segments',

    # Time Series Analysis
    'TimeSeriesPipe',
    'lead',
    'lag',
    'distribution_analysis',
    'cumulative_distribution',
    'variance_analysis',
    'get_distribution_summary',
    'custom_calculation',
    'rolling_window',

    # Metrics Analysis
    'MetricsPipe',
    'Mean',
    'Sum',
    'Count',
    'Max',
    'Min',
    'Ratio',
    'Dot',
    'Nth',
    'Variance',
    'StandardDeviation',
    'CV',
    'Correlation',
    'Cov',
    'Median',
    'Percentile',
    'PivotTable',
    'GroupBy',
    'Filter',
    'CumulativeSum',
    'RollingMetric',
    'Execute',
    'ShowPivot',
    'ShowDataFrame',

    # Operations Analysis
    'OperationsPipe',
    'PercentChange',
    'AbsoluteChange',
    'MH',
    'CUPED',
    'PrePostChange',
    'SelectColumns',
    'FilterConditions',
    'PowerAnalysis',
    'StratifiedSummary',
    'BootstrapCI',
    'MultiComparisonAdjustment',
    'ExecuteOperations',
    'ShowOperation',
    'ShowComparison',

    # Moving Averages
    'MovingAggrPipe',
    'moving_average',
    'moving_variance',
    'moving_sum',
    'moving_quantile',
    'moving_correlation',
    'moving_zscore',
    'moving_apply_by_group',
    'moving_ratio',
    'detect_turning_points',
    'moving_regression',
    'moving_min_max',
    'moving_count',
    'moving_aggregate',
    'moving_percentile_rank',
    'time_weighted_average',
    'moving_cumulative',
    'expanding_window',

    # Risk Analysis
    'RiskPipe',
    'fit_distribution',
    'calculate_var',
    'calculate_cvar',
    'calculate_portfolio_risk',
    'monte_carlo_simulation',
    'stress_test',
    'rolling_risk_metrics',
    'correlation_analysis',
    'risk_attribution',
    'get_risk_summary',
    'compare_distributions',

    # Anomaly Detection
    'AnomalyPipe',
    'detect_statistical_outliers',
    'detect_contextual_anomalies',
    'detect_collective_anomalies',
    'calculate_seasonal_residuals',
    'detect_anomalies_from_residuals',
    'get_anomaly_summary',
    'get_top_anomalies',
    'detect_change_points',
    'forecast_and_detect_anomalies',
    'batch_detect_anomalies',

    # Group Aggregation Functions - Basic
    'mean',
    'sum_values',
    'count_values',
    'max_value',
    'min_value',
    'std_dev',
    'variance',
    'median',
    'quantile',
    'range_values',
    'coefficient_of_variation',
    'skewness',
    'kurtosis',
    'unique_count',
    'mode',
    'weighted_average',
    'geometric_mean',
    'harmonic_mean',
    'interquartile_range',
    'mad',

    # Group Aggregation Functions - Operations
    'percent_change',
    'absolute_change',
    'mantel_haenszel_estimate',
    'cuped_adjustment',
    'prepost_adjustment',
    'power_analysis',
    'stratified_summary',
    'bootstrap_confidence_interval',
    'multi_comparison_adjustment',
    'effect_size',
    'z_score',
    'relative_risk',
    'odds_ratio',

    # Group Aggregation Functions - Utilities
    'get_function_by_name',
    'get_all_function_names',
    'get_function_metadata',
    'get_all_functions_metadata',
    'GROUP_AGGREGATION_FUNCTIONS'

   

    # Function Registry
    'MLFunctionRegistry',
    'FunctionMetadata',
    'initialize_function_registry',
    'FunctionSearchInterface',
    'SearchResult',
    'create_search_interface',
    'FunctionRetrievalService',
    'create_function_retrieval_service'
]
