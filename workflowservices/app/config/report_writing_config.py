"""
Report Writing Configuration

Configuration settings for the report writing agent including:
- LLM settings
- Quality thresholds
- RAG parameters
- Writer actor configurations
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"


class QualityThresholds(BaseModel):
    """Quality thresholds for report generation"""
    minimum_overall_score: float = Field(default=0.8, description="Minimum overall quality score")
    minimum_relevance_score: float = Field(default=0.85, description="Minimum relevance score")
    minimum_clarity_score: float = Field(default=0.8, description="Minimum clarity score")
    minimum_accuracy_score: float = Field(default=0.85, description="Minimum accuracy score")
    minimum_actionability_score: float = Field(default=0.8, description="Minimum actionability score")


class RAGConfig(BaseModel):
    """Configuration for RAG system"""
    chunk_size: int = Field(default=1000, description="Text chunk size for vectorization")
    chunk_overlap: int = Field(default=200, description="Overlap between text chunks")
    retrieval_k: int = Field(default=5, description="Number of documents to retrieve")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity for retrieval")
    max_context_length: int = Field(default=4000, description="Maximum context length for generation")


class WriterActorConfig(BaseModel):
    """Configuration for different writer actor types"""
    executive: Dict[str, Any] = Field(
        default={
            "tone": "strategic",
            "complexity": "high_level",
            "focus": "business_impact",
            "max_sections": 5,
            "preferred_insights": ["strategic", "financial", "market"]
        },
        description="Executive writer configuration"
    )
    
    analyst: Dict[str, Any] = Field(
        default={
            "tone": "analytical",
            "complexity": "detailed",
            "focus": "data_insights",
            "max_sections": 8,
            "preferred_insights": ["trends", "patterns", "correlations"]
        },
        description="Analyst writer configuration"
    )
    
    technical: Dict[str, Any] = Field(
        default={
            "tone": "technical",
            "complexity": "expert",
            "focus": "technical_details",
            "max_sections": 10,
            "preferred_insights": ["technical", "performance", "architecture"]
        },
        description="Technical writer configuration"
    )
    
    business_user: Dict[str, Any] = Field(
        default={
            "tone": "user_friendly",
            "complexity": "moderate",
            "focus": "practical_applications",
            "max_sections": 6,
            "preferred_insights": ["actionable", "practical", "business_value"]
        },
        description="Business user writer configuration"
    )
    
    data_scientist: Dict[str, Any] = Field(
        default={
            "tone": "scientific",
            "complexity": "advanced",
            "focus": "statistical_insights",
            "max_sections": 12,
            "preferred_insights": ["statistical", "predictive", "causal"]
        },
        description="Data scientist writer configuration"
    )
    
    consultant: Dict[str, Any] = Field(
        default={
            "tone": "professional",
            "complexity": "balanced",
            "focus": "strategic_recommendations",
            "max_sections": 7,
            "preferred_insights": ["strategic", "competitive", "market"]
        },
        description="Consultant writer configuration"
    )


class SelfCorrectionConfig(BaseModel):
    """Configuration for self-correction system"""
    max_iterations: int = Field(default=3, description="Maximum self-correction iterations")
    quality_improvement_threshold: float = Field(default=0.1, description="Minimum quality improvement per iteration")
    enable_automatic_correction: bool = Field(default=True, description="Enable automatic self-correction")
    correction_strategies: List[str] = Field(
        default=[
            "content_restructuring",
            "tone_adjustment",
            "clarity_improvement",
            "relevance_enhancement"
        ],
        description="Available correction strategies"
    )


class ReportStructureConfig(BaseModel):
    """Configuration for report structure"""
    required_sections: List[str] = Field(
        default=[
            "executive_summary",
            "key_findings",
            "detailed_analysis",
            "recommendations",
            "appendix"
        ],
        description="Required report sections"
    )
    
    optional_sections: List[str] = Field(
        default=[
            "methodology",
            "data_sources",
            "limitations",
            "future_work",
            "glossary"
        ],
        description="Optional report sections"
    )
    
    max_section_length: int = Field(default=2000, description="Maximum characters per section")
    min_section_length: int = Field(default=200, description="Minimum characters per section")


class ReportWritingConfig(BaseModel):
    """Main configuration for report writing agent"""
    
    # LLM Configuration
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI, description="LLM provider to use")
    llm_model: str = Field(default="gpt-4", description="LLM model to use")
    llm_temperature: float = Field(default=0.1, description="LLM temperature setting")
    llm_max_tokens: int = Field(default=4000, description="Maximum tokens for LLM generation")
    
    # Quality Configuration
    quality_thresholds: QualityThresholds = Field(default=QualityThresholds(), description="Quality thresholds")
    
    # RAG Configuration
    rag_config: RAGConfig = Field(default=RAGConfig(), description="RAG system configuration")
    
    # Writer Actor Configuration
    writer_actor_config: WriterActorConfig = Field(default=WriterActorConfig(), description="Writer actor configurations")
    
    # Self-Correction Configuration
    self_correction: SelfCorrectionConfig = Field(default=SelfCorrectionConfig(), description="Self-correction settings")
    
    # Report Structure Configuration
    report_structure: ReportStructureConfig = Field(default=ReportStructureConfig(), description="Report structure settings")
    
    # Performance Configuration
    enable_caching: bool = Field(default=True, description="Enable response caching")
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    max_concurrent_generations: int = Field(default=5, description="Maximum concurrent report generations")
    
    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, description="Enable performance metrics")
    enable_logging: bool = Field(default=True, description="Enable detailed logging")
    log_level: str = Field(default="INFO", description="Logging level")


# Default configuration
DEFAULT_CONFIG = ReportWritingConfig()

# Configuration presets for different use cases
CONFIG_PRESETS = {
    "production": ReportWritingConfig(
        llm_temperature=0.05,
        quality_thresholds=QualityThresholds(
            minimum_overall_score=0.85,
            minimum_relevance_score=0.9,
            minimum_clarity_score=0.85,
            minimum_accuracy_score=0.9,
            minimum_actionability_score=0.85
        ),
        self_correction=SelfCorrectionConfig(
            max_iterations=5,
            quality_improvement_threshold=0.05
        )
    ),
    
    "development": ReportWritingConfig(
        llm_temperature=0.2,
        quality_thresholds=QualityThresholds(
            minimum_overall_score=0.7,
            minimum_relevance_score=0.75,
            minimum_clarity_score=0.7,
            minimum_accuracy_score=0.75,
            minimum_actionability_score=0.7
        ),
        self_correction=SelfCorrectionConfig(
            max_iterations=2,
            quality_improvement_threshold=0.15
        )
    ),
    
    "high_quality": ReportWritingConfig(
        llm_temperature=0.05,
        quality_thresholds=QualityThresholds(
            minimum_overall_score=0.9,
            minimum_relevance_score=0.95,
            minimum_clarity_score=0.9,
            minimum_accuracy_score=0.95,
            minimum_actionability_score=0.9
        ),
        self_correction=SelfCorrectionConfig(
            max_iterations=10,
            quality_improvement_threshold=0.02
        ),
        report_structure=ReportStructureConfig(
            max_section_length=3000,
            min_section_length=500
        )
    )
}


def get_config(preset: str = None) -> ReportWritingConfig:
    """Get configuration with optional preset"""
    if preset and preset in CONFIG_PRESETS:
        return CONFIG_PRESETS[preset]
    return DEFAULT_CONFIG


def get_writer_actor_config(actor_type: str) -> Dict[str, Any]:
    """Get configuration for a specific writer actor type"""
    config = get_config()
    return config.writer_actor_config.dict().get(actor_type, {})


def get_quality_thresholds() -> QualityThresholds:
    """Get quality thresholds configuration"""
    config = get_config()
    return config.quality_thresholds


def get_rag_config() -> RAGConfig:
    """Get RAG configuration"""
    config = get_config()
    return config.rag_config
