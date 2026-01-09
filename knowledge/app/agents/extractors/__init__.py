"""
LLM-powered extractors for creating contextual graph documents

Note: These extractors have been migrated to pipeline architecture.
See app/agents/pipelines/ for the new pipeline-based implementations.

These legacy extractors are kept for backward compatibility.
For new code, use the ExtractionService and pipelines.

All extractors now support configurable rules via ExtractionRules,
allowing them to work for different domains (compliance, finance, healthcare, etc.)
instead of being hardcoded for compliance.
"""
from .control_extractor import ControlExtractor
from .requirement_extractor import RequirementExtractor
from .evidence_extractor import EvidenceExtractor
from .context_extractor import ContextExtractor
from .fields_extractor import FieldsExtractor
from .entities_extractor import EntitiesExtractor
from .extraction_rules import (
    ExtractionRules,
    FieldExtractionRule,
    get_compliance_context_rules,
    get_compliance_control_rules,
    get_compliance_evidence_rules,
    get_compliance_requirement_rules,
    get_default_fields_rules,
    get_default_entities_rules,
)

# Note: Pipelines are available directly from app.agents.pipelines
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
    # Note: Pipelines should be imported from app.agents.pipelines directly
    # to avoid circular dependencies
]

