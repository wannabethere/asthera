"""
Helper functions for converting between state representations
"""
from typing import Dict, List, Any
from .metadata_state import (
    MetadataEntry,
    MetadataPattern,
    DomainMapping,
    MetadataTransferLearningState
)


def entry_to_dict(entry: MetadataEntry) -> Dict[str, Any]:
    """Convert MetadataEntry to dictionary"""
    return {
        "domain_name": entry.domain_name,
        "framework_name": entry.framework_name,
        "metadata_category": entry.metadata_category,
        "enum_type": entry.enum_type,
        "code": entry.code,
        "description": entry.description,
        "abbreviation": entry.abbreviation,
        "numeric_score": entry.numeric_score,
        "priority_order": entry.priority_order,
        "severity_level": entry.severity_level,
        "weight": entry.weight,
        "risk_score": entry.risk_score,
        "occurrence_likelihood": entry.occurrence_likelihood,
        "consequence_severity": entry.consequence_severity,
        "exploitability_score": entry.exploitability_score,
        "impact_score": entry.impact_score,
        "rationale": entry.rationale,
        "data_source": entry.data_source,
        "calculation_method": entry.calculation_method,
        "data_indicators": entry.data_indicators,
        "parent_code": entry.parent_code,
        "equivalent_codes": entry.equivalent_codes,
        "confidence_score": entry.confidence_score
    }


def dict_to_entry(data: Dict[str, Any]) -> MetadataEntry:
    """Convert dictionary to MetadataEntry"""
    return MetadataEntry(
        domain_name=data.get("domain_name", ""),
        framework_name=data.get("framework_name"),
        metadata_category=data.get("metadata_category", ""),
        enum_type=data.get("enum_type", ""),
        code=data.get("code", ""),
        description=data.get("description", ""),
        abbreviation=data.get("abbreviation"),
        numeric_score=float(data.get("numeric_score", 50.0)),
        priority_order=int(data.get("priority_order", 1)),
        severity_level=int(data["severity_level"]) if data.get("severity_level") else None,
        weight=float(data.get("weight", 1.0)),
        risk_score=float(data["risk_score"]) if data.get("risk_score") else None,
        occurrence_likelihood=float(data["occurrence_likelihood"]) if data.get("occurrence_likelihood") else None,
        consequence_severity=float(data["consequence_severity"]) if data.get("consequence_severity") else None,
        exploitability_score=float(data["exploitability_score"]) if data.get("exploitability_score") else None,
        impact_score=float(data["impact_score"]) if data.get("impact_score") else None,
        rationale=data.get("rationale"),
        data_source=data.get("data_source"),
        calculation_method=data.get("calculation_method"),
        data_indicators=data.get("data_indicators"),
        parent_code=data.get("parent_code"),
        equivalent_codes=data.get("equivalent_codes"),
        confidence_score=float(data["confidence_score"]) if data.get("confidence_score") else None
    )


def pattern_to_dict(pattern: MetadataPattern) -> Dict[str, Any]:
    """Convert MetadataPattern to dictionary"""
    return {
        "pattern_name": pattern.pattern_name,
        "pattern_type": pattern.pattern_type,
        "source_domain": pattern.source_domain,
        "pattern_structure": pattern.pattern_structure,
        "pattern_examples": pattern.pattern_examples,
        "confidence": pattern.confidence,
        "description": pattern.description
    }


def dict_to_pattern(data: Dict[str, Any]) -> MetadataPattern:
    """Convert dictionary to MetadataPattern"""
    return MetadataPattern(
        pattern_name=data.get("pattern_name", ""),
        pattern_type=data.get("pattern_type", ""),
        source_domain=data.get("source_domain", ""),
        pattern_structure=data.get("pattern_structure", {}),
        pattern_examples=data.get("pattern_examples", []),
        confidence=float(data.get("confidence", 0.5)),
        description=data.get("description")
    )


def mapping_to_dict(mapping: DomainMapping) -> Dict[str, Any]:
    """Convert DomainMapping to dictionary"""
    return {
        "source_domain": mapping.source_domain,
        "source_code": mapping.source_code,
        "source_enum_type": mapping.source_enum_type,
        "target_domain": mapping.target_domain,
        "target_code": mapping.target_code,
        "target_enum_type": mapping.target_enum_type,
        "mapping_type": mapping.mapping_type,
        "similarity_score": mapping.similarity_score,
        "mapping_rationale": mapping.mapping_rationale
    }


def dict_to_mapping(data: Dict[str, Any]) -> DomainMapping:
    """Convert dictionary to DomainMapping"""
    return DomainMapping(
        source_domain=data.get("source_domain", ""),
        source_code=data.get("source_code", ""),
        source_enum_type=data.get("source_enum_type", ""),
        target_domain=data.get("target_domain", ""),
        target_code=data.get("target_code", ""),
        target_enum_type=data.get("target_enum_type", ""),
        mapping_type=data.get("mapping_type", "analogical"),
        similarity_score=float(data.get("similarity_score", 0.5)),
        mapping_rationale=data.get("mapping_rationale", "")
    )


def get_entries_from_state(state: MetadataTransferLearningState) -> List[MetadataEntry]:
    """Extract MetadataEntry objects from state"""
    entries_data = state.get("refined_metadata") or state.get("generated_metadata", [])
    return [dict_to_entry(e) if isinstance(e, dict) else e for e in entries_data]


def get_patterns_from_state(state: MetadataTransferLearningState) -> List[MetadataPattern]:
    """Extract MetadataPattern objects from state"""
    patterns_data = state.get("learned_patterns", [])
    return [dict_to_pattern(p) if isinstance(p, dict) else p for p in patterns_data]


def get_mappings_from_state(state: MetadataTransferLearningState) -> List[DomainMapping]:
    """Extract DomainMapping objects from state"""
    mappings_data = state.get("domain_mappings", [])
    return [dict_to_mapping(m) if isinstance(m, dict) else m for m in mappings_data]

