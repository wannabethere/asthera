"""
Consolidated Collections Registry for Compliance Skill

This module provides a single source of truth for all collections used in the compliance skill.
Collections are organized by category and usage.
"""

from enum import Enum
from typing import List, Dict, Any


class FrameworkCollections:
    """Framework Knowledge Base Collections (Qdrant)"""
    CONTROLS = "framework_controls"
    REQUIREMENTS = "framework_requirements"
    RISKS = "framework_risks"
    TEST_CASES = "framework_test_cases"
    SCENARIOS = "framework_scenarios"
    ITEMS = "framework_items"
    USER_POLICIES = "user_policies"
    
    ALL = [CONTROLS, REQUIREMENTS, RISKS, TEST_CASES, SCENARIOS, ITEMS, USER_POLICIES]
    ALL_FRAMEWORK = [CONTROLS, REQUIREMENTS, RISKS, TEST_CASES, SCENARIOS, ITEMS]


class MDLCollections:
    """MDL (Metadata Language) Collections (Qdrant/ChromaDB)"""
    # LEEN/DT workflow collections
    DB_SCHEMA = "leen_db_schema"
    TABLE_DESCRIPTION = "leen_table_description"
    PROJECT_META = "leen_project_meta"
    METRICS_REGISTRY = "leen_metrics_registry"
    
    # CSOD workflow collections
    CSOD_DB_SCHEMA = "csod_db_schema"
    CSOD_TABLE_DESCRIPTION = "csod_table_description"
    CSOD_METRICS_REGISTRY = "csod_metrics_registry"
    CSOD_L1_SOURCE_CONCEPTS = "csod_l1_source_concepts"
    CSOD_L2_RECOMMENDATION_AREAS = "csod_l2_recommendation_areas"
    CSOD_L3_MDL_TABLES = "csod_l3_mdl_tables"
    
    # Shared collections
    DASHBOARDS = "mdl_dashboards"
    DASHBOARD_TEMPLATES = "dashboard_templates"
    DASHBOARD_METRICS_REGISTRY = "dashboard_metrics_registry"
    PAST_LAYOUT_SPECS = "past_layout_specs"
    
    # All LEEN collections
    ALL_LEEN = [DB_SCHEMA, TABLE_DESCRIPTION, PROJECT_META, METRICS_REGISTRY]
    
    # All CSOD collections
    ALL_CSOD = [
        CSOD_DB_SCHEMA,
        CSOD_TABLE_DESCRIPTION,
        CSOD_METRICS_REGISTRY,
        CSOD_L1_SOURCE_CONCEPTS,
        CSOD_L2_RECOMMENDATION_AREAS,
        CSOD_L3_MDL_TABLES,
    ]
    
    # All collections (including shared)
    ALL = ALL_LEEN + ALL_CSOD + [DASHBOARDS, DASHBOARD_TEMPLATES, DASHBOARD_METRICS_REGISTRY]


class XSOARCollections:
    """XSOAR Enriched Collections (Qdrant/ChromaDB)"""
    ENRICHED = "xsoar_enriched"
    
    ALL = [ENRICHED]
    
    # Entity types within xsoar_enriched collection
    class EntityType:
        PLAYBOOK = "playbook"
        DASHBOARD = "dashboard"
        SCRIPT = "script"
        INTEGRATION = "integration"
        INDICATOR = "indicator"


class AttackCollections:
    """ATT&CK Security Intelligence Collections (Qdrant/ChromaDB)"""
    TECHNIQUES = "attack_techniques"
    TACTIC_CONTEXTS = "attack_tactic_contexts"
    # Technique + tactic → framework control (scenario / CVE pipeline mappings)
    CONTROL_MAPPINGS = "attack_control_mappings"

    ALL = [TECHNIQUES, TACTIC_CONTEXTS, CONTROL_MAPPINGS]


class ThreatIntelCollections:
    """CWE/CAPEC threat intelligence for semantic search (Qdrant/ChromaDB)"""
    CWE_CAPEC = "threat_intel_cwe_capec"  # Single collection for CWE + CAPEC search
    # CWE → CAPEC → ATT&CK derived mappings (mapper / cwe_capec_attack_vector_ingest)
    CWE_CAPEC_ATTACK_MAPPINGS = "threat_intel_cwe_capec_attack_mappings"

    ALL = [CWE_CAPEC, CWE_CAPEC_ATTACK_MAPPINGS]


class LLMSafetyCollections:
    """LLM Safety Collections (Qdrant) - SAFE-MCP techniques and mitigations"""
    SAFETY = "llm_safety"
    
    ALL = [SAFETY]
    
    # Entity types within llm_safety collection
    class EntityType:
        TECHNIQUE = "technique"
        MITIGATION = "mitigation"
        DETECTION_RULE = "detection_rule"  # Detection rule templates/examples


class ComprehensiveIndexingCollections:
    """
    Comprehensive Indexing Collections (Qdrant/ChromaDB)
    
    These collections are used by contextual graph reasoning and workforce assistants.
    They may have a collection_prefix (e.g., "comprehensive_index_") applied.
    Schema collections are always unprefixed.
    """
    # Domain collections
    DOMAIN_KNOWLEDGE = "domain_knowledge"
    
    # Compliance collections
    COMPLIANCE_CONTROLS = "compliance_controls"
    ENTITIES = "entities"
    EVIDENCE = "evidence"
    FIELDS = "fields"
    CONTROLS = "controls"
    
    # Additional collections
    POLICY_DOCUMENTS = "policy_documents"
    
    # Schema collections (always unprefixed)
    TABLE_DEFINITIONS = "table_definitions"
    TABLE_DESCRIPTIONS = "table_descriptions"
    COLUMN_DEFINITIONS = "column_definitions"
    SCHEMA_DESCRIPTIONS = "schema_descriptions"
    
    # Feature collections
    FEATURES = "features"
    
    # Contextual graph
    CONTEXTUAL_EDGES = "contextual_edges"
    
    # Schema collections that are always unprefixed
    UNPREFIXED_SCHEMA_COLLECTIONS = {
        TABLE_DEFINITIONS,
        TABLE_DESCRIPTIONS,
        COLUMN_DEFINITIONS,
        SCHEMA_DESCRIPTIONS,
        "db_schema",  # Legacy name
        "column_metadata"  # Legacy name
    }
    
    ALL = [
        DOMAIN_KNOWLEDGE,
        COMPLIANCE_CONTROLS,
        ENTITIES,
        EVIDENCE,
        FIELDS,
        CONTROLS,
        POLICY_DOCUMENTS,
        TABLE_DEFINITIONS,
        TABLE_DESCRIPTIONS,
        COLUMN_DEFINITIONS,
        SCHEMA_DESCRIPTIONS,
        FEATURES,
        CONTEXTUAL_EDGES,
    ]


class ComplianceSkillCollections:
    """
    All collections used in Compliance Skill.
    
    This class provides a consolidated view of all collections.
    """
    
    # Collections actively used in compliance skill workflow
    ACTIVE_COLLECTIONS = {
        # Framework KB (via RetrievalService)
        **{name: name for name in FrameworkCollections.ALL},
        
        # MDL (via MDLRetrievalService)
        **{name: name for name in MDLCollections.ALL},
        
        # XSOAR (via XSOARRetrievalService)
        **{name: name for name in XSOARCollections.ALL},
        
        # ATT&CK (via attack ingestion / semantic search)
        **{name: name for name in AttackCollections.ALL},
        # CWE/CAPEC threat intel (via cwe_csv_ingest, capec_csv_ingest, cwe_enrich)
        **{name: name for name in ThreatIntelCollections.ALL},
        
        # LLM Safety (via LLMSafetyRetrievalService)
        **{name: name for name in LLMSafetyCollections.ALL},
    }
    
    @staticmethod
    def get_all_active_collections() -> List[str]:
        """Get all collections actively used in compliance skill."""
        return list(ComplianceSkillCollections.ACTIVE_COLLECTIONS.values())
    
    @staticmethod
    def get_framework_collections() -> List[str]:
        """Get framework KB collections."""
        return FrameworkCollections.ALL
    
    @staticmethod
    def get_mdl_collections() -> List[str]:
        """Get MDL collections."""
        return MDLCollections.ALL
    
    @staticmethod
    def get_xsoar_collections() -> List[str]:
        """Get XSOAR collections."""
        return XSOARCollections.ALL
    
    @staticmethod
    def get_llm_safety_collections() -> List[str]:
        """Get LLM Safety collections."""
        return LLMSafetyCollections.ALL
    
    @staticmethod
    def get_comprehensive_indexing_collections() -> List[str]:
        """Get comprehensive indexing collections (used by workforce assistants)."""
        return ComprehensiveIndexingCollections.ALL
    
    @staticmethod
    def is_collection_active(collection_name: str) -> bool:
        """Check if a collection is actively used in compliance skill."""
        return collection_name in ComplianceSkillCollections.ACTIVE_COLLECTIONS.values()
    
    @staticmethod
    def get_collection_info() -> Dict[str, Any]:
        """Get information about all collections organized by category."""
        return {
            "framework_kb": {
                "collections": FrameworkCollections.ALL,
                "description": "Framework Knowledge Base collections (Qdrant)",
                "accessed_via": "RetrievalService",
                "count": len(FrameworkCollections.ALL)
            },
            "mdl": {
                "collections": MDLCollections.ALL,
                "description": "MDL (Metadata Language) collections (Qdrant/ChromaDB)",
                "accessed_via": "MDLRetrievalService",
                "count": len(MDLCollections.ALL)
            },
            "xsoar": {
                "collections": XSOARCollections.ALL,
                "description": "XSOAR enriched collections (Qdrant/ChromaDB)",
                "accessed_via": "XSOARRetrievalService",
                "count": len(XSOARCollections.ALL)
            },
            "llm_safety": {
                "collections": LLMSafetyCollections.ALL,
                "description": "LLM Safety collections (Qdrant) - SAFE-MCP techniques and mitigations",
                "accessed_via": "LLMSafetyRetrievalService",
                "count": len(LLMSafetyCollections.ALL)
            },
            "comprehensive_indexing": {
                "collections": ComprehensiveIndexingCollections.ALL,
                "description": "Comprehensive indexing collections (used by workforce assistants)",
                "accessed_via": "CollectionFactory",
                "count": len(ComprehensiveIndexingCollections.ALL),
                "note": "May have collection_prefix applied (schema collections are unprefixed)"
            },
            "attack_mapping": {
                "collections": AttackCollections.ALL,
                "description": (
                    "ATT&CK techniques, tactic contexts, and technique→control mapping vectors "
                    "for semantic search"
                ),
                "accessed_via": "TacticContextualiserTool, FrameworkItemRetrievalTool, scenario ingest",
                "count": len(AttackCollections.ALL)
            },
            "threat_intel": {
                "collections": ThreatIntelCollections.ALL,
                "description": (
                    "CWE/CAPEC threat intelligence and CWE→CAPEC→ATT&CK mapping vectors for semantic search"
                ),
                "accessed_via": (
                    "cwe_csv_ingest, capec_csv_ingest, cwe_enrich --vector-store, "
                    "indexing_cli.cwe_capec_attack_vector_ingest"
                ),
                "count": len(ThreatIntelCollections.ALL)
            },
            "summary": {
                "total_active": len(ComplianceSkillCollections.get_all_active_collections()),
                "total_comprehensive": len(ComprehensiveIndexingCollections.ALL),
                "total_all": (
                    len(FrameworkCollections.ALL) +
                    len(MDLCollections.ALL) +
                    len(XSOARCollections.ALL) +
                    len(LLMSafetyCollections.ALL) +
                    len(ThreatIntelCollections.ALL) +
                    len(ComprehensiveIndexingCollections.ALL)
                )
            }
        }


# Backward compatibility: Export Collections from qdrant_framework_store
# This maintains compatibility with existing code that imports Collections from qdrant_framework_store
from app.storage.qdrant_framework_store import Collections as _LegacyCollections

# Re-export for backward compatibility
__all__ = [
    "FrameworkCollections",
    "MDLCollections",
    "XSOARCollections",
    "AttackCollections",
    "ThreatIntelCollections",
    "LLMSafetyCollections",
    "ComprehensiveIndexingCollections",
    "ComplianceSkillCollections",
    "Collections",  # Backward compatibility alias
]

# Alias for backward compatibility
Collections = _LegacyCollections
