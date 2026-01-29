"""
Extraction Pipelines for Contextual Graph

Pipelines for extracting and creating contextual graph documents using LLM.
Follows the pipeline architecture pattern with async batch processing.

All pipelines support configurable rules via ExtractionRules,
allowing them to work for different domains (compliance, finance, healthcare, etc.)
"""
import logging

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

# RetrievalPipeline has dependencies on langchain agents which have import issues
# in newer langchain versions. Import conditionally to avoid breaking ingestion.
logger = logging.getLogger(__name__)
try:
    from app.pipelines.extractions.retrieval_pipeline import RetrievalPipeline
    RETRIEVAL_PIPELINE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RetrievalPipeline not available due to import error: {e}")
    logger.info("This is expected if using langchain 0.2+ without langchain agents installed")
    RetrievalPipeline = None
    RETRIEVAL_PIPELINE_AVAILABLE = False

__all__ = [
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
    "RETRIEVAL_PIPELINE_AVAILABLE",
]
