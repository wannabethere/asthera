"""
Extraction Pipelines for Contextual Graph

Pipelines for extracting and creating contextual graph documents using LLM.
Follows the pipeline architecture pattern with async batch processing.

All pipelines now support configurable rules via ExtractionRules,
allowing them to work for different domains (compliance, finance, healthcare, etc.)
instead of being hardcoded for compliance.
"""
from .base import BasePipeline, ExtractionPipeline, AgentPipeline
from .extractions.control_extraction_pipeline import ControlExtractionPipeline
from .extractions.context_extraction_pipeline import ContextExtractionPipeline
from .extractions.requirement_extraction_pipeline import RequirementExtractionPipeline
from .extractions.evidence_extraction_pipeline import EvidenceExtractionPipeline
from .extractions.fields_extraction_pipeline import FieldsExtractionPipeline
from .extractions.entities_extraction_pipeline import EntitiesExtractionPipeline
from .extractions.pattern_recognition_pipeline import PatternRecognitionPipeline
from .extractions.domain_adaptation_pipeline import DomainAdaptationPipeline
from .extractions.metadata_generation_pipeline import MetadataGenerationPipeline
from .extractions.validation_pipeline import ValidationPipeline
from .extractions.retrieval_pipeline import RetrievalPipeline
from .contextual_graph_retrieval_pipeline import ContextualGraphRetrievalPipeline
from .contextual_graph_reasoning_pipeline import ContextualGraphReasoningPipeline
from .assembly import (
    PipelineAssembly,
    PipelineStep,
    PipelineAssemblyConfig,
    PipelineExecutionMode,
    create_contextual_reasoning_assembly
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
]

