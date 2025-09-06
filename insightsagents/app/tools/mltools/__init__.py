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
    calculate_statistical_trend,
    compare_periods,
    get_top_metrics    
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
    cumulative_distribution,
    custom_calculation,
    get_distribution_summary,
    
    #Todo add auto_correlation, rolling window, seasonal_decomposition, 
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
    Execute
)

from app.tools.mltools.operations_tools import (
    OperationsPipe,
    PercentChange,
    AbsoluteChange,
    MH,
    CUPED,
    PrePostChange,
    FilterConditions,
    PowerAnalysis,
    StratifiedSummary,
    BootstrapCI,
    MultiComparisonAdjustment,
    ExecuteOperations
)

from app.tools.mltools.movingaverages import (
    MovingAggrPipe,
    moving_average,
    moving_sum,
    moving_std,
    moving_variance,
    moving_apply_by_group
)

from app.tools.mltools.riskanalysis import (
    RiskPipe,
    calculate_var,
    calculate_cvar
)

from app.tools.mltools.anomalydetection import (
    AnomalyPipe,
    detect_statistical_outliers,
    detect_contextual_anomalies,
    get_anomaly_summary
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
    'cumulative_distribution', 
    'get_distribution_summary',
    'custom_calculation',

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

    # Operations Analysis
    'OperationsPipe',
    'PercentChange',
    'AbsoluteChange',
    'MH',
    'CUPED',
    'PrePostChange',
    'FilterConditions',
    'PowerAnalysis',
    'StratifiedSummary',
    'BootstrapCI',
    'MultiComparisonAdjustment',
    'ExecuteOperations',

    # Moving Averages
    'MovingAggrPipe',
    'moving_average',
    'moving_sum',
    'moving_std',
    'moving_variance',
    'moving_apply_by_group',

    # Risk Analysis
    'RiskPipe',
    'calculate_var',
    'calculate_cvar',

    # Anomaly Detection
    'AnomalyPipe',
    'detect_statistical_outliers',
    'detect_contextual_anomalies',
    'get_anomaly_summary'
]
