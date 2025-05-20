from chatbot.tools.mltools.cohortanalysistools import (
    CohortPipe,
    form_time_cohorts,
    form_behavioral_cohorts,
    form_acquisition_cohorts,
    calculate_retention,
    calculate_conversion,
    calculate_lifetime_value    
)

from chatbot.tools.mltools.segmentationtools import (
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

from chatbot.tools.mltools.trendanalysistools import (
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

from chatbot.tools.mltools.funnelanalysis import (
    analyze_funnel,
    analyze_funnel_by_time,
    analyze_user_paths,
    analyze_funnel_by_segment,
    get_funnel_summary,
    compare_segments
)

from chatbot.tools.mltools.timeseriesanalysis   import (
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
    'custom_calculation'
]
