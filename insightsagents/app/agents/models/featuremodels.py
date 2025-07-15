from typing import List, Dict, Any, Optional, Union, TypedDict
from pydantic import BaseModel, Field
from enum import Enum

class OperationType(str, Enum):
    """Types of data operations"""
    EXTRACTION = "extraction"
    TRANSFORMATION = "transformation" 
    ANALYSIS = "analysis"
    REDUCTION = "reduction"

class AlgorithmMetadataDict(TypedDict):
    name: str
    description: str
    operation_type: str  # Will be OperationType value
    source: str
    version: Optional[str]
    parameters: Dict[str, Any]
    requirements: List[str]
    complexity: Optional[str]
    references: Optional[List[str]]

class FeatureStatsDict(TypedDict):
    name: str
    description: str
    feature_type: str  # Will be FeatureType value
    missing_count: int
    unique_count: int
    mean: Optional[float]
    median: Optional[float]
    std: Optional[float]
    min: Optional[float]
    max: Optional[float]
    most_common_values: Optional[List[Any]]
    skewness: Optional[float]
    kurtosis: Optional[float]
    variance: Optional[float]
    metadata: AlgorithmMetadataDict

class CorrelationInfoDict(TypedDict):
    feature1: str
    feature2: str
    description: str
    correlation_coefficient: float
    correlation_method: str
    significance: Optional[float]
    partial_correlation: Optional[float]
    controlling_variables: Optional[List[str]]
    covariance: float
    variance_feature1: float
    variance_feature2: float
    metadata: AlgorithmMetadataDict

class CovarianceAnalysisDict(TypedDict):
    covariance_matrix: Dict[str, Dict[str, float]]
    variance_vector: Dict[str, float]
    eigenvalues: Optional[List[float]]
    eigenvectors: Optional[List[List[float]]]
    condition_number: Optional[float]
    determinant: Optional[float]
    metadata: AlgorithmMetadataDict

class VarianceAnalysisDict(TypedDict):
    feature_variances: Dict[str, float]
    total_variance: float
    variance_decomposition: Optional[Dict[str, float]]
    variance_ratios: Dict[str, float]
    cumulative_variance_ratios: Dict[str, float]
    variance_threshold: float
    metadata: AlgorithmMetadataDict

class MultivariateAnalysisDict(TypedDict):
    pca_components: Optional[int]
    factor_analysis_components: Optional[int]
    cluster_analysis: bool
    cluster_method: str
    manova_features: Optional[List[str]]
    canonical_correlation: bool
    feature_interactions: List[List[str]]
    dimension_reduction: bool
    covariance_analysis: Optional[CovarianceAnalysisDict]
    variance_analysis: Optional[VarianceAnalysisDict]
    metadata: AlgorithmMetadataDict

class TemporalFeaturesDict(TypedDict):
    datetime_column: str
    extract_year: bool
    extract_month: bool
    extract_day: bool
    extract_hour: bool
    extract_dayofweek: bool
    extract_season: bool
    custom_grouping: Optional[List[str]]
    rolling_statistics: Optional[Dict[str, List[int]]]
    lag_features: Optional[Dict[str, List[int]]]
    variance_window: Optional[int]
    metadata: AlgorithmMetadataDict

class CategoricalFeaturesDict(TypedDict):
    encoding_method: str
    max_categories: int
    handle_unknown: str
    min_frequency: Optional[float]
    grouping_threshold: Optional[float]
    interaction_terms: Optional[List[List[str]]]
    weight_of_evidence: bool
    target_encoding_smoothing: Optional[float]
    variance_threshold: Optional[float]
    metadata: AlgorithmMetadataDict

class NumericalFeaturesDict(TypedDict):
    scaling_method: str
    handle_outliers: bool
    outlier_method: str
    binning: Optional[Dict[str, int]]
    polynomial_degree: Optional[int]
    interaction_features: Optional[List[List[str]]]
    box_cox_transform: bool
    yeo_johnson_transform: bool
    variance_analysis: bool
    covariance_analysis: bool
    metadata: AlgorithmMetadataDict

class FeatureExtractionConfigDict(TypedDict):
    target_column: Optional[str]
    feature_selection_method: str
    max_features: Optional[int]
    min_correlation: float
    temporal_config: Optional[TemporalFeaturesDict]
    categorical_config: Optional[CategoricalFeaturesDict]
    numerical_config: Optional[NumericalFeaturesDict]
    multivariate_config: Optional[MultivariateAnalysisDict]
    exclude_columns: List[str]
    feature_importance_method: Optional[str]
    variance_threshold: Optional[float]
    covariance_threshold: Optional[float]
    metadata: AlgorithmMetadataDict

class MultivariateStatsDict(TypedDict):
    pca_explained_variance: Optional[List[float]]
    feature_loadings: Optional[Dict[str, List[float]]]
    cluster_centers: Optional[List[List[float]]]
    manova_results: Optional[Dict[str, Any]]
    canonical_correlations: Optional[List[float]]
    interaction_importance: Optional[Dict[str, float]]
    covariance_stats: Optional[CovarianceAnalysisDict]
    variance_stats: Optional[VarianceAnalysisDict]
    metadata: AlgorithmMetadataDict

class DatasetProfileDict(TypedDict):
    total_rows: int
    total_columns: int
    feature_stats: List[FeatureStatsDict]
    correlations: List[CorrelationInfoDict]
    missing_data_summary: Dict[str, float]
    data_quality_score: Optional[float]
    recommendations: List[str]
    multivariate_stats: Optional[MultivariateStatsDict]
    feature_clusters: Optional[Dict[str, List[str]]]
    covariance_matrix: Dict[str, Dict[str, float]]
    variance_analysis: VarianceAnalysisDict
    metadata: AlgorithmMetadataDict



class FeatureGraphState(TypedDict):
    """State tracking for feature graph processing"""
    current_features: List[str] 
    processed_features: Dict[str, FeatureStatsDict]
    feature_relationships: List[CorrelationInfoDict] 
    active_transformations: Dict[str, str] 
    pending_operations: List[str] 
    computation_graph: Dict[str, List[str]]
    error_log: List[Dict[str, Any]] 
    processing_metadata: Dict[str, Any] 
    validation_results: Dict[str, bool] 
    performance_metrics: Dict[str, float] 
    metadata: AlgorithmMetadataDict 

class AlgorithmMetadata(BaseModel):
    """Metadata about the algorithm/operation"""
    name: str
    description: str
    operation_type: OperationType
    source: str  # e.g. "sklearn", "custom", "scipy"
    version: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    requirements: List[str] = Field(default_factory=list)
    complexity: Optional[str] = None  # Time/Space complexity
    references: Optional[List[str]] = None

class FeatureType(str, Enum):
    """Enumeration of feature types"""
    NUMERICAL = "numerical"
    CATEGORICAL = "categorical" 
    TEMPORAL = "temporal"
    TEXT = "text"

class FeatureStats(BaseModel):
    """Basic statistics for a feature"""
    name: str
    feature_type: FeatureType
    missing_count: int = 0
    unique_count: int = 0
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    most_common_values: Optional[List[Any]] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    variance: Optional[float] = None
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="basic_statistics",
            description="Basic statistical measures of a feature",
            operation_type=OperationType.ANALYSIS,
            source="numpy"
        )
    )

class CorrelationInfo(BaseModel):
    """Correlation information between features"""
    feature1: str
    feature2: str
    description: str
    correlation_coefficient: float
    correlation_method: str = "pearson"
    significance: Optional[float] = None
    partial_correlation: Optional[float] = None
    controlling_variables: Optional[List[str]] = None
    covariance: float
    variance_feature1: float
    variance_feature2: float
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="correlation_analysis",
            description="Correlation analysis between feature pairs",
            operation_type=OperationType.ANALYSIS,
            source="scipy"
        )
    )

class CovarianceAnalysis(BaseModel):
    """Covariance analysis configuration and results"""
    covariance_matrix: Dict[str, Dict[str, float]]
    description: str
    variance_vector: Dict[str, float]
    eigenvalues: Optional[List[float]] = None
    eigenvectors: Optional[List[List[float]]] = None
    condition_number: Optional[float] = None
    determinant: Optional[float] = None
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="covariance_analysis",
            description="Analysis of feature covariance relationships",
            operation_type=OperationType.ANALYSIS,
            source="numpy"
        )
    )

class VarianceAnalysis(BaseModel):
    """Variance analysis configuration and results"""
    feature_variances: Dict[str, float]
    description: str
    total_variance: float
    variance_decomposition: Optional[Dict[str, float]] = None
    variance_ratios: Dict[str, float]
    cumulative_variance_ratios: Dict[str, float]
    variance_threshold: float = 0.01
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="variance_analysis",
            description="Analysis of feature variance distributions",
            operation_type=OperationType.ANALYSIS,
            source="sklearn"
        )
    )

class MultivariateAnalysis(BaseModel):
    """Configuration for multivariate analysis"""
    pca_components: Optional[int] = None
    description: str
    factor_analysis_components: Optional[int] = None
    cluster_analysis: bool = False
    cluster_method: str = "kmeans"
    manova_features: Optional[List[str]] = None
    canonical_correlation: bool = False
    feature_interactions: List[List[str]] = Field(default_factory=list)
    dimension_reduction: bool = False
    covariance_analysis: Optional[CovarianceAnalysis] = None
    variance_analysis: Optional[VarianceAnalysis] = None
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="multivariate_analysis",
            description="Comprehensive multivariate statistical analysis",
            operation_type=OperationType.ANALYSIS,
            source="sklearn"
        )
    )

class TemporalFeatures(BaseModel):
    """Temporal feature extraction configuration"""
    datetime_column: str
    description: str
    extract_year: bool = True
    extract_month: bool = True
    extract_day: bool = True
    extract_hour: bool = False
    extract_dayofweek: bool = True
    extract_season: bool = False
    custom_grouping: Optional[List[str]] = None
    rolling_statistics: Optional[Dict[str, List[int]]] = None
    lag_features: Optional[Dict[str, List[int]]] = None
    variance_window: Optional[int] = None
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="temporal_feature_extraction",
            description="Extraction of time-based features",
            operation_type=OperationType.EXTRACTION,
            source="pandas"
        )
    )

class CategoricalFeatures(BaseModel):
    """Categorical feature processing configuration"""
    encoding_method: str = "one_hot"
    description: str
    max_categories: int = 20
    handle_unknown: str = "ignore"
    min_frequency: Optional[float] = None
    grouping_threshold: Optional[float] = None
    interaction_terms: Optional[List[List[str]]] = None
    weight_of_evidence: bool = False
    target_encoding_smoothing: Optional[float] = None
    variance_threshold: Optional[float] = None
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="categorical_processing",
            description="Processing and encoding of categorical features",
            operation_type=OperationType.TRANSFORMATION,
            source="category_encoders"
        )
    )

class NumericalFeatures(BaseModel):
    """Numerical feature processing configuration"""
    scaling_method: str = "standard"
    description: str
    handle_outliers: bool = False
    outlier_method: str = "iqr"
    binning: Optional[Dict[str, int]] = None
    polynomial_degree: Optional[int] = None
    interaction_features: Optional[List[List[str]]] = None
    box_cox_transform: bool = False
    yeo_johnson_transform: bool = False
    variance_analysis: bool = True
    covariance_analysis: bool = True
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="numerical_processing",
            description="Processing and transformation of numerical features",
            operation_type=OperationType.TRANSFORMATION,
            source="sklearn"
        )
    )

class FeatureExtractionConfig(BaseModel):
    """Main configuration for feature extraction"""
    target_column: Optional[str] = None
    description: str
    feature_selection_method: str = "correlation"
    max_features: Optional[int] = None
    min_correlation: float = 0.1
    temporal_config: Optional[TemporalFeatures] = None
    categorical_config: Optional[CategoricalFeatures] = None
    numerical_config: Optional[NumericalFeatures] = None
    multivariate_config: Optional[MultivariateAnalysis] = None
    exclude_columns: List[str] = Field(default_factory=list)
    feature_importance_method: Optional[str] = None
    variance_threshold: Optional[float] = None
    covariance_threshold: Optional[float] = None
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="feature_extraction",
            description="Complete feature extraction pipeline",
            operation_type=OperationType.EXTRACTION,
            source="custom"
        )
    )

class MultivariateStats(BaseModel):
    """Statistics from multivariate analysis"""
    pca_explained_variance: Optional[List[float]] = None
    description: str
    feature_loadings: Optional[Dict[str, List[float]]] = None
    cluster_centers: Optional[List[List[float]]] = None
    manova_results: Optional[Dict[str, Any]] = None
    canonical_correlations: Optional[List[float]] = None
    interaction_importance: Optional[Dict[str, float]] = None
    covariance_stats: Optional[CovarianceAnalysis] = None
    variance_stats: Optional[VarianceAnalysis] = None
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="multivariate_statistics",
            description="Comprehensive multivariate statistical results",
            operation_type=OperationType.ANALYSIS,
            source="sklearn"
        )
    )

class DatasetProfile(BaseModel):
    """Profile of the dataset including feature statistics"""
    total_rows: int
    total_columns: int
    summary: str
    key_insights: str
    feature_stats: List[FeatureStats]
    correlations: List[CorrelationInfo]
    missing_data_summary: Dict[str, float]
    data_quality_score: Optional[float] = None
    recommendations: List[str] = Field(default_factory=list)
    multivariate_stats: Optional[MultivariateStats] = None
    feature_clusters: Optional[Dict[str, List[str]]] = None
    covariance_matrix: Dict[str, Dict[str, float]]
    variance_analysis: VarianceAnalysis
    metadata: AlgorithmMetadata = Field(
        default_factory=lambda: AlgorithmMetadata(
            name="dataset_profiling",
            description="Complete statistical profile of the dataset",
            operation_type=OperationType.ANALYSIS,
            source="custom"
        )
    )



