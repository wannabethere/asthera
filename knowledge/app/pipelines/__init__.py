"""
Extraction Pipelines for Contextual Graph

Pipelines for extracting and creating contextual graph documents using LLM.
Follows the pipeline architecture pattern with async batch processing.

All pipelines now support configurable rules via ExtractionRules,
allowing them to work for different domains (compliance, finance, healthcare, etc.)
instead of being hardcoded for compliance.
"""
from app.pipelines.base import BasePipeline, ExtractionPipeline, AgentPipeline
from app.pipelines.extractions.control_extraction_pipeline import ControlExtractionPipeline
from app.pipelines.extractions.context_extraction_pipeline import ContextExtractionPipeline
from app.pipelines.extractions.requirement_extraction_pipeline import RequirementExtractionPipeline
from app.pipelines.extractions.evidence_extraction_pipeline import EvidenceExtractionPipeline
from app.pipelines.extractions.fields_extraction_pipeline import FieldsExtractionPipeline
from app.pipelines.extractions.entities_extraction_pipeline import EntitiesExtractionPipeline
from app.pipelines.extractions.pattern_recognition_pipeline import PatternRecognitionPipeline
from app.pipelines.extractions.domain_adaptation_pipeline import DomainAdaptationPipeline
from app.pipelines.extractions.metadata_generation_pipeline import MetadataGenerationPipeline
from app.pipelines.extractions.validation_pipeline import ValidationPipeline
from app.pipelines.extractions import RetrievalPipeline, RETRIEVAL_PIPELINE_AVAILABLE
from app.pipelines.contextual_graph_retrieval_pipeline import ContextualGraphRetrievalPipeline
from app.pipelines.contextual_graph_reasoning_pipeline import ContextualGraphReasoningPipeline
from app.pipelines.assembly import (
    PipelineAssembly,
    PipelineStep,
    PipelineAssemblyConfig,
    PipelineExecutionMode,
    create_contextual_reasoning_assembly
)
from app.pipelines.async_query_pipeline import AsyncQueryPipeline, AsyncDataRetrievalPipeline
from app.pipelines.pipeline_registry import (
    PipelineRegistry,
    PipelineConfig,
    PipelineCategoryConfig,
    get_pipeline_registry
)

__all__ = [
    "BasePipeline",
    "ExtractionPipeline",
    "AgentPipeline",
    "ControlExtractionPipeline",
    "ContextExtractionPipeline",
    "RequirementExtractionPipeline",
    "EvidenceExtractionPipeline",
    "FieldsExtractionPipeline",
    "EntitiesExtractionPipeline",
    "PatternRecognitionPipeline",
    "DomainAdaptationPipeline",
    "MetadataGenerationPipeline",
    "ValidationPipeline",
    "RetrievalPipeline",
    "ContextualGraphRetrievalPipeline",
    "ContextualGraphReasoningPipeline",
    # Pipeline Assembly
    "PipelineAssembly",
    "PipelineStep",
    "PipelineAssemblyConfig",
    "PipelineExecutionMode",
    "create_contextual_reasoning_assembly",
    # Async Query Pipelines
    "AsyncQueryPipeline",
    "AsyncDataRetrievalPipeline",
    # Pipeline Registry
    "PipelineRegistry",
    "PipelineConfig",
    "PipelineCategoryConfig",
    "get_pipeline_registry",
]

