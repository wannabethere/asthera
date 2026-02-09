"""
LLM-powered extractors for creating contextual graph documents

Note: These extractors have been migrated to pipeline architecture.
See app/pipelines/ for the new pipeline-based implementations.

These legacy extractors are kept for backward compatibility.
For new code, use the ExtractionService and pipelines.

All extractors now support configurable rules via ExtractionRules,
allowing them to work for different domains (compliance, finance, healthcare, etc.)
instead of being hardcoded for compliance.
"""
from app.agents.extractors.control_extractor import ControlExtractor
from app.agents.extractors.requirement_extractor import RequirementExtractor
from app.agents.extractors.evidence_extractor import EvidenceExtractor
from app.agents.extractors.context_extractor import ContextExtractor
from app.agents.extractors.fields_extractor import FieldsExtractor
from app.agents.extractors.entities_extractor import EntitiesExtractor
from app.agents.extractors.extraction_rules import (
    ExtractionRules,
    FieldExtractionRule,
    get_compliance_context_rules,
    get_compliance_control_rules,
    get_compliance_evidence_rules,
    get_compliance_requirement_rules,
    get_default_fields_rules,
    get_default_entities_rules,
)
from app.agents.extractors.domain_adaptation_agent import DomainAdaptationAgent
from app.agents.extractors.metadata_generation_agent import MetadataGenerationAgent
from app.agents.extractors.pattern_recognition_agent import PatternRecognitionAgent
from app.agents.extractors.validation_agent import ValidationAgent

# Note: Pipelines are available directly from app.pipelines
# Importing them here would create a circular dependency

__all__ = [
    # Legacy extractors (for backward compatibility)
    "ControlExtractor",
    "RequirementExtractor",
    "EvidenceExtractor",
    "ContextExtractor",
    # New generic extractors
    "FieldsExtractor",
    "EntitiesExtractor",
    # Extraction rules configuration
    "ExtractionRules",
    "FieldExtractionRule",
    "get_compliance_context_rules",
    "get_compliance_control_rules",
    "get_compliance_evidence_rules",
    "get_compliance_requirement_rules",
    "get_default_fields_rules",
    "get_default_entities_rules",
    # Transfer learning / metadata generation extractors
    "DomainAdaptationAgent",
    "MetadataGenerationAgent",
    "PatternRecognitionAgent",
    "ValidationAgent",
    # Note: Pipelines should be imported from app.pipelines directly
    # to avoid circular dependencies
]

