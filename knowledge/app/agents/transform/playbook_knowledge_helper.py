"""
Playbook Knowledge Helper Module

Provides knowledge retrieval infrastructure for playbook-driven workflows:
- Feature definitions organized by category (from mdl_features.json, etc.)
- Enum metadata references (from enum_metadata_ref.json)
- SQL instruction examples (from sql_instructions_*.json)
- Agent category mappings (from agent_category_mapping.json)
- Deep research context generation for richer feature engineering

In production, these would be retrieved from a vector store (Chroma/Pinecone).
This module provides a structured interface to simulate that retrieval.
"""
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger("lexy-ai-service")


# ============================================================================
# LANE TYPE ENUM (shared with playbook_driven_transform_agent)
# ============================================================================

class LaneType(str, Enum):
    """Types of lanes in playbook workflows"""
    BOOTSTRAP = "bootstrap"  # Lane 0: Schema + Enum + Knowledge bootstrap
    INGESTION = "ingestion"  # Lane 1: Bronze data ingestion
    ASSETIZATION = "assetization"  # Lane 2: Canonical asset creation
    MONITORING = "monitoring"  # Lane 3: Agent/monitoring evidence
    NORMALIZATION = "normalization"  # Lane 4: Data normalization + enrichment
    SILVER_FEATURES = "silver_features"  # Lane 5: Silver feature compilation
    RISK_SCORING = "risk_scoring"  # Lane 6: Impact/Likelihood/Risk engines
    TIME_SERIES = "time_series"  # Lane 7: Time series snapshots
    COMPLIANCE = "compliance"  # Lane 8: Control evaluation
    DELIVERY = "delivery"  # Lane 9: Evidence packaging + Alerts


# ============================================================================
# AGENT CATEGORY MAPPINGS (from agent_category_mapping.json)
# ============================================================================

AGENT_CATEGORY_MAPPING = {
    "time_series_generator_agent": {
        "description": "Builds and maintains time series models from features for trend analysis and forecasting",
        "categories": [
            "raw_risk", "impact_components", "breach_method_likelihood",
            "likelihood_active", "likelihood_inherent", "effective_metrics",
            "asset_state", "lifecycle_and_maintenance", "monitoring_agent_evidence",
            "hipaa_audit_controls_and_monitoring", "hipaa_maintenance_and_integrity_proxies",
            "soc2_monitoring_coverage_and_freshness", "soc2_patch_and_change_hygiene_proxies"
        ]
    },
    "risk_agent": {
        "description": "Computes composite risk scores from impact and likelihood components",
        "categories": [
            "raw_risk", "effective_metrics", "hipaa_risk_metrics",
            "soc2_risk_metrics", "control_effectiveness_vuln_signals"
        ]
    },
    "impact_agent": {
        "description": "Computes and aggregates impact components for risk calculations",
        "categories": [
            "impact_components", "hipaa_impact_components", "soc2_impact_components",
            "tagging_and_classification", "hipaa_device_and_workstation_safeguards",
            "soc2_asset_inventory_and_classification"
        ]
    },
    "likelihood_agent": {
        "description": "Computes and aggregates likelihood components for risk calculations",
        "categories": [
            "breach_method_likelihood", "likelihood_active", "likelihood_inherent",
            "hipaa_likelihood_components", "soc2_likelihood_components",
            "security_posture_flags", "baseline_security_controls",
            "control_effectiveness_vuln_signals", "hipaa_access_control_safeguards",
            "hipaa_transmission_and_network_exposure_proxies", "hipaa_maintenance_and_integrity_proxies",
            "soc2_access_and_hardening", "soc2_patch_and_change_hygiene_proxies"
        ]
    },
    "compliance_agent": {
        "description": "Evaluates features against compliance frameworks (SOC2, HIPAA, etc.)",
        "categories": [
            "hipaa_access_control_safeguards", "hipaa_transmission_and_network_exposure_proxies",
            "hipaa_audit_controls_and_monitoring", "hipaa_device_and_workstation_safeguards",
            "hipaa_maintenance_and_integrity_proxies", "hipaa_impact_components",
            "hipaa_likelihood_components", "hipaa_risk_metrics", "soc2_access_and_hardening",
            "soc2_asset_inventory_and_classification", "soc2_monitoring_coverage_and_freshness",
            "soc2_patch_and_change_hygiene_proxies", "soc2_impact_components",
            "soc2_likelihood_components", "soc2_risk_metrics"
        ]
    },
    "control_evidence_agent": {
        "description": "Collects and validates control evidence for audit readiness",
        "categories": [
            "monitoring_agent_evidence", "baseline_security_controls",
            "control_effectiveness_vuln_signals", "hipaa_audit_controls_and_monitoring",
            "soc2_monitoring_coverage_and_freshness"
        ]
    },
    "prioritization_agent": {
        "description": "Prioritizes assets/issues based on risk and business context",
        "categories": [
            "raw_risk", "effective_metrics", "hipaa_risk_metrics",
            "soc2_risk_metrics", "tagging_and_classification", "asset_state"
        ]
    }
}

# Map lane types to agent types
LANE_TO_AGENT_MAPPING = {
    LaneType.BOOTSTRAP: "control_evidence_agent",
    LaneType.INGESTION: "control_evidence_agent",
    LaneType.ASSETIZATION: "impact_agent",
    LaneType.MONITORING: "control_evidence_agent",
    LaneType.NORMALIZATION: "likelihood_agent",
    LaneType.SILVER_FEATURES: "time_series_generator_agent",
    LaneType.RISK_SCORING: "risk_agent",
    LaneType.TIME_SERIES: "time_series_generator_agent",
    LaneType.COMPLIANCE: "compliance_agent",
    LaneType.DELIVERY: "prioritization_agent"
}


# ============================================================================
# FEATURE KNOWLEDGE BASE - CATEGORIZED FEATURES
# ============================================================================

# Feature definitions organized by category (from mdl_features.json, etc.)
FEATURE_KNOWLEDGE_BASE = {
    # Core Risk Metrics
    "raw_risk": {
        "name": "raw_risk",
        "displayName": "Raw Risk Metrics",
        "classification": "core_metric",
        "features": [
            {"name": "raw_impact", "dataType": "float", "description": "Base impact score from business value and criticality"},
            {"name": "raw_likelihood", "dataType": "float", "description": "Base likelihood of compromise from threat signals"},
            {"name": "raw_risk", "dataType": "float", "description": "Composite risk from impact × likelihood"}
        ]
    },
    # Impact Components
    "impact_components": {
        "name": "impact_components",
        "displayName": "Impact Component Features",
        "classification": "impact_component",
        "features": [
            {"name": "bastion_impact", "dataType": "float", "description": "Impact from bastion/privileged access role"},
            {"name": "propagation_impact", "dataType": "float", "description": "Lateral movement blast radius impact"},
            {"name": "category_impact", "dataType": "float", "description": "Impact from asset classification category"}
        ]
    },
    # Monitoring Agent Evidence
    "monitoring_agent_evidence": {
        "name": "monitoring_agent_evidence",
        "displayName": "Monitoring Agent Evidence",
        "classification": "core_metric",
        "features": [
            {"name": "has_agent_installed", "dataType": "boolean", "description": "True if asset has monitoring agent"},
            {"name": "agent_last_checkin_ts", "dataType": "timestamp", "description": "Most recent agent check-in"},
            {"name": "agent_health_state", "dataType": "string", "description": "Agent health: healthy/degraded/offline/unknown"},
            {"name": "agent_version_age_days", "dataType": "int", "description": "Days since agent version release"}
        ]
    },
    # Control Evidence
    "baseline_security_controls": {
        "name": "baseline_security_controls",
        "displayName": "Baseline Security Controls",
        "classification": "likelihood_component",
        "features": [
            {"name": "has_edr_installed", "dataType": "boolean", "description": "True if EDR product installed"},
            {"name": "edr_vendor", "dataType": "string", "description": "EDR vendor name"},
            {"name": "antivirus_present", "dataType": "boolean", "description": "True if AV protection present"},
            {"name": "disk_encryption_enabled_proxy", "dataType": "boolean", "description": "Proxy for disk encryption status"}
        ]
    },
    # Vulnerability Signals
    "control_effectiveness_vuln_signals": {
        "name": "control_effectiveness_vuln_signals",
        "displayName": "Vulnerability Evidence",
        "classification": "likelihood_component",
        "features": [
            {"name": "has_kev_vuln_open", "dataType": "boolean", "description": "True if KEV vulnerability is open"},
            {"name": "highest_cvss_open", "dataType": "float", "description": "Max CVSS score of open vulns"},
            {"name": "exploitable_vuln_present", "dataType": "boolean", "description": "True if exploit evidence exists"}
        ]
    },
    # SOC2 Impact
    "soc2_impact_components": {
        "name": "soc2_impact_components",
        "displayName": "SOC2 Impact Components",
        "classification": "impact_component",
        "features": [
            {"name": "soc2_impact_env_weight", "dataType": "float", "description": "Impact from environment (prod highest)"},
            {"name": "soc2_impact_bastion_multiplier", "dataType": "float", "description": "Bastion access impact multiplier"},
            {"name": "soc2_impact_internet_exposure_weight", "dataType": "float", "description": "Internet exposure impact"},
            {"name": "soc2_raw_impact", "dataType": "float", "description": "Composite SOC2 impact score"}
        ]
    },
    # SOC2 Likelihood
    "soc2_likelihood_components": {
        "name": "soc2_likelihood_components",
        "displayName": "SOC2 Likelihood Components",
        "classification": "likelihood_component",
        "features": [
            {"name": "soc2_likelihood_monitoring_gap", "dataType": "float", "description": "Likelihood from monitoring gaps"},
            {"name": "soc2_likelihood_endpoint_control_gap", "dataType": "float", "description": "Likelihood from missing controls"},
            {"name": "soc2_likelihood_misconfig", "dataType": "float", "description": "Likelihood from misconfigurations"},
            {"name": "soc2_likelihood_exploitable_vuln", "dataType": "float", "description": "Likelihood from exploit evidence"},
            {"name": "soc2_raw_likelihood", "dataType": "float", "description": "Composite SOC2 likelihood score"}
        ]
    },
    # SOC2 Risk
    "soc2_risk_metrics": {
        "name": "soc2_risk_metrics",
        "displayName": "SOC2 Risk Metrics",
        "classification": "core_metric",
        "features": [
            {"name": "soc2_raw_risk", "dataType": "float", "description": "SOC2 risk = impact × likelihood"},
            {"name": "soc2_risk_driver_primary", "dataType": "string", "description": "Primary SOC2 risk driver"}
        ]
    },
    # HIPAA Impact
    "hipaa_impact_components": {
        "name": "hipaa_impact_components",
        "displayName": "HIPAA Impact Components",
        "classification": "impact_component",
        "features": [
            {"name": "hipaa_impact_env_weight", "dataType": "float", "description": "Impact from regulated environment"},
            {"name": "hipaa_impact_encryption_gap_weight", "dataType": "float", "description": "Impact from encryption gaps"},
            {"name": "hipaa_impact_internet_exposure_weight", "dataType": "float", "description": "Internet exposure impact"},
            {"name": "hipaa_raw_impact", "dataType": "float", "description": "Composite HIPAA impact score"}
        ]
    },
    # HIPAA Likelihood
    "hipaa_likelihood_components": {
        "name": "hipaa_likelihood_components",
        "displayName": "HIPAA Likelihood Components",
        "classification": "likelihood_component",
        "features": [
            {"name": "hipaa_likelihood_monitoring_gap", "dataType": "float", "description": "Likelihood from monitoring gaps"},
            {"name": "hipaa_likelihood_endpoint_protection_gap", "dataType": "float", "description": "Likelihood from protection gaps"},
            {"name": "hipaa_likelihood_hardening_gap", "dataType": "float", "description": "Likelihood from hardening gaps"},
            {"name": "hipaa_likelihood_exploitable_vuln", "dataType": "float", "description": "Likelihood from exploit evidence"},
            {"name": "hipaa_raw_likelihood", "dataType": "float", "description": "Composite HIPAA likelihood score"}
        ]
    },
    # HIPAA Risk
    "hipaa_risk_metrics": {
        "name": "hipaa_risk_metrics",
        "displayName": "HIPAA Risk Metrics",
        "classification": "core_metric",
        "features": [
            {"name": "hipaa_raw_risk", "dataType": "float", "description": "HIPAA risk = impact × likelihood"},
            {"name": "hipaa_risk_driver_primary", "dataType": "string", "description": "Primary HIPAA risk driver"}
        ]
    },
    # Training Compliance (Cornerstone)
    "training_compliance": {
        "name": "training_compliance",
        "displayName": "Training Compliance Features",
        "classification": "core_metric",
        "features": [
            {"name": "training_status_normalized", "dataType": "string", "description": "Normalized training status"},
            {"name": "days_past_due", "dataType": "int", "description": "Days past training due date"},
            {"name": "days_to_due", "dataType": "int", "description": "Days until training due date"},
            {"name": "has_failed_attempt", "dataType": "boolean", "description": "True if training attempt failed"},
            {"name": "training_obligation", "dataType": "string", "description": "Framework-scoped obligation code"}
        ]
    },
    # Asset State
    "asset_state": {
        "name": "asset_state",
        "displayName": "Asset State & Activity Signals",
        "classification": "core_metric",
        "features": [
            {"name": "asset_last_seen_ts", "dataType": "timestamp", "description": "Most recent asset observation"},
            {"name": "asset_age_days", "dataType": "int", "description": "Days since asset creation"},
            {"name": "is_active_asset", "dataType": "boolean", "description": "True if seen recently and not retired"},
            {"name": "asset_freshness_bucket", "dataType": "string", "description": "Freshness class: <1h, 1-24h, 1-7d, >7d"}
        ]
    },
    # Effective Metrics
    "effective_metrics": {
        "name": "effective_metrics",
        "displayName": "Effective Risk Metrics",
        "classification": "effective",
        "features": [
            {"name": "effective_impact", "dataType": "float", "description": "Impact after mitigation factors"},
            {"name": "effective_likelihood", "dataType": "float", "description": "Likelihood after defensive measures"},
            {"name": "effective_risk", "dataType": "float", "description": "Final composite risk score"}
        ]
    },
    # Tagging and Classification
    "tagging_and_classification": {
        "name": "tagging_and_classification",
        "displayName": "Tagging & Classification",
        "classification": "core_metric",
        "features": [
            {"name": "is_crown_jewel_asset_proxy", "dataType": "boolean", "description": "Heuristic for crown-jewel classification"},
            {"name": "asset_environment", "dataType": "string", "description": "Derived environment: prod/stage/dev/corp"},
            {"name": "asset_location_fingerprint", "dataType": "string", "description": "Normalized geo/site fingerprint"}
        ]
    }
}


# ============================================================================
# ENUM METADATA REFERENCES (from enum_metadata_ref.json)
# ============================================================================

ENUM_METADATA_REFS = {
    "soc2_risk_driver_primary": {
        "table": "risk_driver_metadata",
        "enumType": "risk_driver_primary",
        "selector": {"framework": "SOC2"}
    },
    "hipaa_risk_driver_primary": {
        "table": "risk_driver_metadata",
        "enumType": "risk_driver_primary",
        "selector": {"framework": "HIPAA"}
    },
    "control_state": {
        "table": "control_state_metadata",
        "enumType": "control_state",
        "selector": {"control_type": "COMMON"}
    },
    "exposure_class": {
        "table": "asset_exposure_metadata",
        "enumType": "exposure_class"
    },
    "freshness_bucket": {
        "table": "telemetry_freshness_metadata",
        "enumType": "freshness_bucket"
    },
    "exploit_signal": {
        "table": "vuln_exploit_signal_metadata",
        "enumType": "exploit_signal"
    },
    "training_status": {
        "table": "training_status_metadata",
        "enumType": "training_status"
    },
    "training_obligation": {
        "table": "training_obligation_metadata",
        "enumType": "training_obligation"
    },
    "impact_class": {
        "table": "risk_impact_metadata",
        "enumType": "impact_class"
    },
    "likelihood_class": {
        "table": "likelihood_vuln_attributes_metadata",
        "enumType": "likelihood_class"
    },
    "risk_level": {
        "table": "risk_impact_metadata",
        "enumType": "risk_level"
    }
}


# ============================================================================
# SQL INSTRUCTION EXAMPLES (from sql_instructions_*.json)
# ============================================================================

SQL_INSTRUCTION_EXAMPLES = {
    "soc2_silver": [
        {
            "question": "Which Snyk-derived assets were seen in the last 24 hours?",
            "instructions": "Identify active, recently observed software assets to confirm scan coverage and freshness.",
            "categories": ["snyk_ingestion", "assets", "silver"]
        },
        {
            "question": "Which in-scope SOC2 assets have stale Snyk scanner check-ins?",
            "instructions": "Find assets where Snyk agent telemetry is stale, indicating a monitoring control evidence gap.",
            "categories": ["monitoring", "soc2", "silver"]
        },
        {
            "question": "Which assets have an open KEV vulnerability (highest urgency)?",
            "instructions": "List assets with at least one open KEV vulnerability to prioritize immediate remediation.",
            "categories": ["vulnerability_management", "soc2", "silver"]
        },
        {
            "question": "Show SOC2 per-asset risk with primary driver and risk level (last snapshot).",
            "instructions": "Return SOC2 impact/likelihood/risk and explainability fields to drive triage queues.",
            "categories": ["soc2", "risk_scoring", "silver"]
        }
    ],
    "hipaa_silver": [
        {
            "question": "Which HIPAA in-scope assets have an encryption gap?",
            "instructions": "Find assets where disk encryption proxy is missing/unknown to prioritize confidentiality safeguards.",
            "categories": ["hipaa", "encryption", "silver"]
        },
        {
            "question": "Which HIPAA assets have exploitable vulnerabilities present (KEV/public exploit)?",
            "instructions": "Identify assets where exploit evidence exists to prioritize remediation and reduce breach likelihood.",
            "categories": ["hipaa", "vulnerability_management", "silver"]
        },
        {
            "question": "Which assets fail HIPAA audit-controls evidence due to stale monitoring telemetry?",
            "instructions": "Flag assets where monitoring evidence is stale to drive audit readiness remediation.",
            "categories": ["hipaa", "controls", "silver"]
        }
    ],
    "cornerstone_silver": [
        {
            "question": "Which users have trainings past due (raw evidence view)?",
            "instructions": "List learners with past-due assigned trainings to validate ingestion and identify immediate compliance gaps.",
            "categories": ["cornerstone", "silver", "training_instances"]
        },
        {
            "question": "Show SOC2 training risk for in-scope people (latest snapshot).",
            "instructions": "Return SOC2 training risk with driver and class labels for triage queues.",
            "categories": ["cornerstone", "silver", "soc2"]
        },
        {
            "question": "Which obligations have a coverage gap (obligation exists but not assigned)?",
            "instructions": "Find people in-scope for an obligation but missing a corresponding training assignment instance.",
            "categories": ["cornerstone", "silver", "coverage"]
        }
    ],
    "enum_metadata": [
        {
            "question": "What are the SOC2 risk driver options and their meanings?",
            "instructions": "Return the list of SOC2-specific risk drivers to power UI dropdowns and validation.",
            "categories": ["enum_metadata", "governance"]
        },
        {
            "question": "What freshness buckets are available for telemetry, and what thresholds do they represent?",
            "instructions": "List freshness buckets with min/max minutes to classify last_seen and agent_checkins consistently.",
            "categories": ["enum_metadata", "telemetry"]
        },
        {
            "question": "What control_state values can SOC2/HIPAA evaluations emit?",
            "instructions": "Return allowed control_state values used by dev_asset_control_status.control_state.",
            "categories": ["enum_metadata", "controls"]
        }
    ],
    "time_series": [
        {
            "question": "Show risk trend for a specific asset over the last 30 days (SOC2 + HIPAA).",
            "instructions": "Return SOC2 and HIPAA risk scores by day for a single asset to visualize trend and verify time series integrity.",
            "categories": ["time_series", "assets", "silver"]
        },
        {
            "question": "How many assets became stale today (by freshness bucket)?",
            "instructions": "Provide a daily operational view of monitoring freshness movement. Use this for alerting thresholds later.",
            "categories": ["time_series", "monitoring", "silver"]
        }
    ]
}


# ============================================================================
# KNOWLEDGE CONTEXT DATACLASS
# ============================================================================

@dataclass
class KnowledgeContext:
    """Container for retrieved knowledge context"""
    features: List[Dict[str, Any]] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    instructions: List[str] = field(default_factory=list)
    enum_metadata: List[Dict[str, Any]] = field(default_factory=list)
    compliance_info: Dict[str, Any] = field(default_factory=dict)
    schema_context: List[str] = field(default_factory=list)
    # Deep research enhancements
    deep_research_context: Dict[str, Any] = field(default_factory=dict)
    feature_generation_hints: List[Dict[str, Any]] = field(default_factory=list)
    quality_guidelines: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LaneResearchContext:
    """
    Enhanced context for lane execution combining knowledge and deep research.
    
    This provides richer context for feature generation including:
    - Relevant features and their dependencies
    - SQL instruction examples with detailed guidance
    - Control mappings and compliance requirements
    - Quality guidelines for generated features
    - Deep research insights for the lane
    """
    lane_type: str
    domain: str
    compliance_frameworks: List[str]
    
    # Knowledge context
    knowledge: KnowledgeContext = field(default_factory=KnowledgeContext)
    
    # Deep research context
    research_insights: Dict[str, Any] = field(default_factory=dict)
    recommended_features: List[Dict[str, Any]] = field(default_factory=list)
    control_mappings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Generation guidance
    feature_templates: List[Dict[str, Any]] = field(default_factory=list)
    calculation_patterns: List[Dict[str, Any]] = field(default_factory=list)
    quality_criteria: Dict[str, Any] = field(default_factory=dict)
    
    # Validation context
    expected_outputs: List[str] = field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# PLAYBOOK KNOWLEDGE HELPER CLASS
# ============================================================================

class PlaybookKnowledgeHelper:
    """
    Knowledge retrieval helper for playbook-driven workflows.
    
    In production, this would query a vector store (Chroma/Pinecone) for:
    - Feature definitions by category
    - SQL examples by lane type and compliance framework
    - Instructions and metadata
    - Enum metadata references
    
    This implementation uses in-memory dictionaries to simulate retrieval.
    """
    
    def __init__(self):
        self.feature_kb = FEATURE_KNOWLEDGE_BASE
        self.agent_categories = AGENT_CATEGORY_MAPPING
        self.enum_refs = ENUM_METADATA_REFS
        self.sql_examples = SQL_INSTRUCTION_EXAMPLES
    
    def get_features_for_lane(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant features for a lane type.
        
        Args:
            lane_type: Type of lane being executed
            domain: Domain (e.g., 'hr_compliance', 'cybersecurity')
            compliance_frameworks: List of frameworks (e.g., ['SOC2', 'HIPAA'])
            
        Returns:
            List of feature definitions relevant to this lane
        """
        # Get agent type for this lane
        agent_type = LANE_TO_AGENT_MAPPING.get(lane_type, "control_evidence_agent")
        agent_config = self.agent_categories.get(agent_type, {})
        relevant_categories = agent_config.get("categories", [])
        
        # Filter by compliance framework if specified
        if compliance_frameworks:
            framework_categories = []
            for framework in compliance_frameworks:
                framework_lower = framework.lower()
                framework_categories.extend([
                    c for c in relevant_categories 
                    if framework_lower in c.lower() or "soc2" not in c.lower() and "hipaa" not in c.lower()
                ])
            relevant_categories = list(set(framework_categories)) if framework_categories else relevant_categories
        
        # Collect features from relevant categories
        features = []
        for category in relevant_categories:
            if category in self.feature_kb:
                category_def = self.feature_kb[category]
                features.extend(category_def.get("features", []))
        
        return features
    
    def get_examples_for_lane(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve SQL instruction examples for a lane type.
        
        Args:
            lane_type: Type of lane being executed
            domain: Domain name
            compliance_frameworks: Compliance frameworks
            
        Returns:
            List of example questions and instructions
        """
        examples = []
        
        # Map lane types to example categories
        lane_example_mapping = {
            LaneType.BOOTSTRAP: ["enum_metadata"],
            LaneType.INGESTION: [],
            LaneType.ASSETIZATION: ["soc2_silver", "hipaa_silver"],
            LaneType.MONITORING: ["soc2_silver", "hipaa_silver"],
            LaneType.NORMALIZATION: ["enum_metadata"],
            LaneType.SILVER_FEATURES: ["soc2_silver", "hipaa_silver", "cornerstone_silver"],
            LaneType.RISK_SCORING: ["soc2_silver", "hipaa_silver"],
            LaneType.TIME_SERIES: ["time_series"],
            LaneType.COMPLIANCE: ["soc2_silver", "hipaa_silver"],
            LaneType.DELIVERY: []
        }
        
        example_keys = lane_example_mapping.get(lane_type, [])
        
        # Filter by compliance framework
        if compliance_frameworks:
            for framework in compliance_frameworks:
                framework_lower = framework.lower()
                for key in example_keys:
                    if framework_lower in key or key in ["enum_metadata", "time_series"]:
                        examples.extend(self.sql_examples.get(key, []))
        else:
            for key in example_keys:
                examples.extend(self.sql_examples.get(key, []))
        
        # Handle Cornerstone domain
        if domain == "hr_compliance":
            examples.extend(self.sql_examples.get("cornerstone_silver", []))
        
        return examples
    
    def get_enum_metadata_for_features(
        self,
        feature_names: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get enum metadata references for specific features.
        
        Args:
            feature_names: List of feature names
            
        Returns:
            List of enum metadata table references
        """
        enum_refs = []
        for feature in feature_names:
            if feature in self.enum_refs:
                ref = self.enum_refs[feature].copy()
                ref["feature"] = feature
                enum_refs.append(ref)
        
        return enum_refs
    
    def get_compliance_context(
        self,
        frameworks: List[str],
        domain: str
    ) -> Dict[str, Any]:
        """
        Get compliance-specific context and rules.
        
        Args:
            frameworks: List of compliance frameworks
            domain: Domain name
            
        Returns:
            Dictionary with compliance context
        """
        context = {
            "frameworks": frameworks,
            "domain": domain,
            "guardrails": {
                "silver_only": True,  # No gold aggregates
                "allowed": [
                    "per-asset derived fields",
                    "per-asset max severity fields",
                    "per-asset booleans",
                    "per-person-per-obligation derived features",
                    "per-person status flags and days-to-due",
                    "per-person risk scores (raw + enum labels)"
                ],
                "avoid": [
                    "org-wide completion rate",
                    "average days past due across departments",
                    "portfolio rollups (counts across org/team)",
                    "team-level KPIs",
                    "MTTR aggregations"
                ]
            }
        }
        
        # Add framework-specific context
        if "SOC2" in frameworks:
            context["soc2"] = {
                "impact_drivers": ["environment", "bastion_access", "internet_exposure"],
                "likelihood_drivers": ["monitoring_gap", "endpoint_control_gap", "misconfig", "exploitable_vuln"],
                "risk_calculation": "soc2_raw_risk = soc2_raw_impact × soc2_raw_likelihood"
            }
        
        if "HIPAA" in frameworks:
            context["hipaa"] = {
                "impact_drivers": ["environment", "encryption_gap", "internet_exposure"],
                "likelihood_drivers": ["monitoring_gap", "endpoint_protection_gap", "hardening_gap", "exploitable_vuln"],
                "risk_calculation": "hipaa_raw_risk = hipaa_raw_impact × hipaa_raw_likelihood",
                "safeguard_types": ["Technical", "Administrative", "Physical"]
            }
        
        return context
    
    def get_knowledge_context(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str] = None,
        feature_names: List[str] = None
    ) -> KnowledgeContext:
        """
        Get complete knowledge context for a lane execution.
        
        Args:
            lane_type: Type of lane
            domain: Domain name
            compliance_frameworks: Compliance frameworks
            feature_names: Specific features to look up
            
        Returns:
            KnowledgeContext with all relevant information
        """
        frameworks = compliance_frameworks or []
        
        features = self.get_features_for_lane(lane_type, domain, frameworks)
        examples = self.get_examples_for_lane(lane_type, domain, frameworks)
        
        # Get enum metadata for known features
        feature_names_from_kb = [f["name"] for f in features]
        if feature_names:
            feature_names_from_kb.extend(feature_names)
        enum_metadata = self.get_enum_metadata_for_features(feature_names_from_kb)
        
        # Build instructions from examples
        instructions = [ex.get("instructions", "") for ex in examples if ex.get("instructions")]
        
        compliance_info = self.get_compliance_context(frameworks, domain)
        
        return KnowledgeContext(
            features=features,
            examples=examples,
            instructions=instructions,
            enum_metadata=enum_metadata,
            compliance_info=compliance_info,
            schema_context=[]  # Would be populated by RetrievalHelper
        )
    
    def get_all_categories(self) -> List[str]:
        """Get all available feature categories"""
        return list(self.feature_kb.keys())
    
    def get_category_features(self, category: str) -> List[Dict[str, Any]]:
        """Get features for a specific category"""
        if category in self.feature_kb:
            return self.feature_kb[category].get("features", [])
        return []
    
    def get_all_enum_refs(self) -> Dict[str, Dict[str, Any]]:
        """Get all enum metadata references"""
        return self.enum_refs.copy()
    
    def get_agent_categories(self, agent_type: str) -> List[str]:
        """Get feature categories for a specific agent type"""
        if agent_type in self.agent_categories:
            return self.agent_categories[agent_type].get("categories", [])
        return []
    
    def get_lane_research_context(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str] = None,
        lane_inputs: List[str] = None,
        lane_outputs: List[str] = None
    ) -> LaneResearchContext:
        """
        Get comprehensive research context for a lane execution.
        
        This combines knowledge retrieval with deep research context to provide
        everything needed for rich feature generation.
        
        Args:
            lane_type: Type of lane being executed
            domain: Domain name (e.g., 'cybersecurity', 'hr_compliance')
            compliance_frameworks: List of compliance frameworks
            lane_inputs: Input table names for the lane
            lane_outputs: Output table names for the lane
            
        Returns:
            LaneResearchContext with all relevant context
        """
        frameworks = compliance_frameworks or []
        
        # Get base knowledge context
        knowledge = self.get_knowledge_context(
            lane_type=lane_type,
            domain=domain,
            compliance_frameworks=frameworks
        )
        
        # Build feature templates based on lane type
        feature_templates = self._build_feature_templates(lane_type, domain, frameworks)
        
        # Build calculation patterns
        calculation_patterns = self._build_calculation_patterns(lane_type, frameworks)
        
        # Build quality criteria
        quality_criteria = self._build_quality_criteria(lane_type, frameworks)
        
        # Build control mappings
        control_mappings = self._build_control_mappings(lane_type, frameworks)
        
        # Build validation rules
        validation_rules = self._build_validation_rules(lane_type, lane_outputs or [])
        
        return LaneResearchContext(
            lane_type=lane_type.value,
            domain=domain,
            compliance_frameworks=frameworks,
            knowledge=knowledge,
            feature_templates=feature_templates,
            calculation_patterns=calculation_patterns,
            quality_criteria=quality_criteria,
            control_mappings=control_mappings,
            expected_outputs=lane_outputs or [],
            validation_rules=validation_rules
        )
    
    def _build_feature_templates(
        self,
        lane_type: LaneType,
        domain: str,
        frameworks: List[str]
    ) -> List[Dict[str, Any]]:
        """Build feature generation templates for a lane type"""
        templates = []
        
        # Lane-specific templates
        if lane_type == LaneType.RISK_SCORING:
            templates.extend([
                {
                    "type": "impact_feature",
                    "pattern": "{framework}_raw_impact",
                    "description": "Composite impact score for {framework}",
                    "calculation": "SUM of weighted impact components",
                    "components": ["env_weight", "bastion_multiplier", "internet_exposure_weight"],
                    "output_type": "float",
                    "range": [0.0, 1.0]
                },
                {
                    "type": "likelihood_feature",
                    "pattern": "{framework}_raw_likelihood",
                    "description": "Composite likelihood score for {framework}",
                    "calculation": "MAX of likelihood components or weighted combination",
                    "components": ["monitoring_gap", "endpoint_control_gap", "exploitable_vuln"],
                    "output_type": "float",
                    "range": [0.0, 1.0]
                },
                {
                    "type": "risk_feature",
                    "pattern": "{framework}_raw_risk",
                    "description": "Risk score = impact × likelihood for {framework}",
                    "calculation": "{framework}_raw_impact × {framework}_raw_likelihood",
                    "output_type": "float",
                    "range": [0.0, 1.0]
                },
                {
                    "type": "risk_driver",
                    "pattern": "{framework}_risk_driver_primary",
                    "description": "Primary driver of risk for {framework}",
                    "calculation": "CASE WHEN logic based on highest contributing factor",
                    "output_type": "string",
                    "enum_lookup": "risk_driver_metadata"
                }
            ])
        
        elif lane_type == LaneType.SILVER_FEATURES:
            templates.extend([
                {
                    "type": "boolean_flag",
                    "pattern": "has_{feature}_proxy",
                    "description": "Boolean proxy for {feature} presence",
                    "calculation": "COALESCE with fallback logic",
                    "output_type": "boolean"
                },
                {
                    "type": "numeric_metric",
                    "pattern": "{entity}_{metric}",
                    "description": "Numeric metric for {entity}",
                    "calculation": "Aggregation or derivation from source",
                    "output_type": "float"
                },
                {
                    "type": "classification",
                    "pattern": "{entity}_{attribute}_class",
                    "description": "Classification label for {entity} {attribute}",
                    "calculation": "CASE WHEN buckets or enum lookup",
                    "output_type": "string",
                    "enum_lookup": "appropriate_metadata_table"
                }
            ])
        
        elif lane_type == LaneType.COMPLIANCE:
            templates.extend([
                {
                    "type": "control_state",
                    "pattern": "control_state",
                    "description": "Control evaluation result",
                    "calculation": "CASE WHEN evidence → pass/fail/unknown/exception",
                    "output_type": "string",
                    "enum_lookup": "control_state_metadata",
                    "valid_values": ["pass", "fail", "unknown", "exception"]
                },
                {
                    "type": "evidence_flag",
                    "pattern": "{control}_evidence_present",
                    "description": "Evidence present for {control}",
                    "calculation": "Boolean from evidence table join",
                    "output_type": "boolean"
                }
            ])
        
        elif lane_type == LaneType.ASSETIZATION:
            templates.extend([
                {
                    "type": "asset_key",
                    "pattern": "asset_key",
                    "description": "Stable asset identity hash",
                    "calculation": "MD5/SHA hash of identifier fields",
                    "output_type": "string"
                },
                {
                    "type": "asset_attribute",
                    "pattern": "asset_{attribute}",
                    "description": "Derived asset attribute",
                    "calculation": "Inference from source fields",
                    "output_type": "string"
                }
            ])
        
        # Apply framework substitution
        expanded_templates = []
        for template in templates:
            if "{framework}" in str(template):
                for framework in frameworks:
                    expanded = {}
                    for key, value in template.items():
                        if isinstance(value, str):
                            expanded[key] = value.replace("{framework}", framework.lower())
                        else:
                            expanded[key] = value
                    expanded["framework"] = framework
                    expanded_templates.append(expanded)
            else:
                expanded_templates.append(template)
        
        return expanded_templates
    
    def _build_calculation_patterns(
        self,
        lane_type: LaneType,
        frameworks: List[str]
    ) -> List[Dict[str, Any]]:
        """Build calculation patterns for feature generation"""
        patterns = []
        
        if lane_type == LaneType.RISK_SCORING:
            patterns.extend([
                {
                    "name": "weighted_sum",
                    "description": "Sum of weighted components",
                    "sql_pattern": "({w1} * {c1}) + ({w2} * {c2}) + ({w3} * {c3})",
                    "use_case": "Impact score composition"
                },
                {
                    "name": "max_of_components",
                    "description": "Maximum of multiple components",
                    "sql_pattern": "GREATEST({c1}, {c2}, {c3})",
                    "use_case": "Likelihood from multiple threat signals"
                },
                {
                    "name": "multiplication",
                    "description": "Product of two scores",
                    "sql_pattern": "{impact} * {likelihood}",
                    "use_case": "Risk = Impact × Likelihood"
                },
                {
                    "name": "risk_driver_case",
                    "description": "Primary driver identification",
                    "sql_pattern": """CASE 
                        WHEN {driver1} >= {driver2} AND {driver1} >= {driver3} THEN '{label1}'
                        WHEN {driver2} >= {driver3} THEN '{label2}'
                        ELSE '{label3}'
                    END""",
                    "use_case": "Risk driver attribution"
                }
            ])
        
        elif lane_type == LaneType.SILVER_FEATURES:
            patterns.extend([
                {
                    "name": "coalesce_default",
                    "description": "Coalesce with default value",
                    "sql_pattern": "COALESCE({field}, {default})",
                    "use_case": "Null handling"
                },
                {
                    "name": "days_calculation",
                    "description": "Days between dates",
                    "sql_pattern": "DATEDIFF(day, {date1}, {date2})",
                    "use_case": "Age/duration calculations"
                },
                {
                    "name": "freshness_bucket",
                    "description": "Classify into time buckets",
                    "sql_pattern": """CASE 
                        WHEN DATEDIFF(minute, {ts}, CURRENT_TIMESTAMP) < 60 THEN '<1h'
                        WHEN DATEDIFF(hour, {ts}, CURRENT_TIMESTAMP) < 24 THEN '1-24h'
                        WHEN DATEDIFF(day, {ts}, CURRENT_TIMESTAMP) < 7 THEN '1-7d'
                        ELSE '>7d'
                    END""",
                    "use_case": "Telemetry freshness classification"
                }
            ])
        
        return patterns
    
    def _build_quality_criteria(
        self,
        lane_type: LaneType,
        frameworks: List[str]
    ) -> Dict[str, Any]:
        """Build quality criteria for generated features"""
        criteria = {
            "medallion_layer": "silver",
            "aggregation_level": "per_entity",
            "allowed_operations": [],
            "prohibited_operations": [],
            "naming_conventions": {},
            "data_quality_checks": []
        }
        
        if lane_type == LaneType.RISK_SCORING:
            criteria["allowed_operations"] = [
                "per-asset impact calculation",
                "per-asset likelihood calculation",
                "per-asset risk score",
                "per-asset enum lookups for labels"
            ]
            criteria["prohibited_operations"] = [
                "org-wide averages",
                "team-level rollups",
                "MTTR across populations",
                "portfolio counts"
            ]
            criteria["naming_conventions"] = {
                "impact": "{framework}_raw_impact",
                "likelihood": "{framework}_raw_likelihood",
                "risk": "{framework}_raw_risk",
                "driver": "{framework}_risk_driver_primary"
            }
            criteria["data_quality_checks"] = [
                {"check": "range_validation", "rule": "0 <= score <= 1"},
                {"check": "null_handling", "rule": "COALESCE to 0 for missing components"},
                {"check": "enum_validation", "rule": "risk_driver must be from metadata table"}
            ]
        
        elif lane_type == LaneType.SILVER_FEATURES:
            criteria["allowed_operations"] = [
                "per-entity derived fields",
                "per-entity max severity",
                "per-entity boolean flags",
                "per-entity classifications"
            ]
            criteria["prohibited_operations"] = [
                "cross-entity aggregations",
                "population statistics",
                "gold-layer rollups"
            ]
            criteria["data_quality_checks"] = [
                {"check": "not_null", "rule": "Primary key must not be null"},
                {"check": "valid_enum", "rule": "Classifications must match metadata"},
                {"check": "timestamp_valid", "rule": "Timestamps must be valid ISO format"}
            ]
        
        elif lane_type == LaneType.COMPLIANCE:
            criteria["allowed_operations"] = [
                "per-asset control evaluation",
                "per-asset evidence collection",
                "control state determination"
            ]
            criteria["prohibited_operations"] = [
                "org-wide compliance rates",
                "control effectiveness across population"
            ]
            criteria["naming_conventions"] = {
                "control_state": "control_state",
                "evidence": "{control}_evidence_present"
            }
        
        return criteria
    
    def _build_control_mappings(
        self,
        lane_type: LaneType,
        frameworks: List[str]
    ) -> List[Dict[str, Any]]:
        """Build control mappings for compliance features"""
        mappings = []
        
        if "SOC2" in frameworks:
            mappings.extend([
                {
                    "framework": "SOC2",
                    "control_id": "CC6.1",
                    "control_name": "Logical and Physical Access Controls",
                    "features": ["has_edr_installed", "antivirus_present"],
                    "evidence_tables": ["dev_agents", "asset_control_evidence_features"]
                },
                {
                    "framework": "SOC2",
                    "control_id": "CC7.2",
                    "control_name": "System Monitoring",
                    "features": ["has_agent_installed", "agent_health_state", "agent_last_checkin_ts"],
                    "evidence_tables": ["dev_agents"]
                },
                {
                    "framework": "SOC2",
                    "control_id": "CC8.1",
                    "control_name": "Change Management",
                    "features": ["agent_version_age_days"],
                    "evidence_tables": ["dev_agents"]
                }
            ])
        
        if "HIPAA" in frameworks:
            mappings.extend([
                {
                    "framework": "HIPAA",
                    "control_id": "164.312(a)(1)",
                    "control_name": "Access Control",
                    "features": ["has_edr_installed", "antivirus_present"],
                    "evidence_tables": ["dev_agents", "asset_control_evidence_features"]
                },
                {
                    "framework": "HIPAA",
                    "control_id": "164.312(e)(2)(ii)",
                    "control_name": "Encryption",
                    "features": ["disk_encryption_enabled_proxy"],
                    "evidence_tables": ["asset_control_evidence_features"]
                },
                {
                    "framework": "HIPAA",
                    "control_id": "164.312(b)",
                    "control_name": "Audit Controls",
                    "features": ["has_agent_installed", "agent_health_state"],
                    "evidence_tables": ["dev_agents"]
                }
            ])
        
        return mappings
    
    def _build_validation_rules(
        self,
        lane_type: LaneType,
        expected_outputs: List[str]
    ) -> List[Dict[str, Any]]:
        """Build validation rules for lane outputs"""
        rules = []
        
        for output in expected_outputs:
            rules.append({
                "table": output,
                "rules": [
                    {"type": "not_empty", "description": f"{output} should have records"},
                    {"type": "pk_not_null", "description": "Primary key must not be null"}
                ]
            })
        
        # Lane-specific validation
        if lane_type == LaneType.RISK_SCORING:
            rules.append({
                "scope": "all_outputs",
                "rules": [
                    {"type": "score_range", "description": "Risk scores must be 0-1", "min": 0, "max": 1},
                    {"type": "driver_valid", "description": "Risk drivers must be from enum"}
                ]
            })
        
        return rules


# ============================================================================
# NATURAL LANGUAGE FEATURE GENERATION AGENT
# ============================================================================

@dataclass
class NLFeatureQuestion:
    """A natural language question describing a feature to generate"""
    question: str
    feature_name: str
    feature_type: str  # impact, likelihood, risk, metric, boolean, classification
    calculation_hint: str
    target_columns: List[str] = field(default_factory=list)
    source_tables: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    compliance_mapping: Optional[str] = None
    enum_lookup: Optional[str] = None
    validation_rules: List[str] = field(default_factory=list)
    priority: int = 1


@dataclass
class NLFeatureGenerationResult:
    """Result of natural language feature generation"""
    questions: List[NLFeatureQuestion]
    lane_type: str
    domain: str
    frameworks: List[str]
    generation_reasoning: str
    quality_notes: List[str] = field(default_factory=list)


class NLFeatureGenerationAgent:
    """
    Agent that generates natural language questions for feature engineering.
    
    Uses the structured prompt template to generate detailed NL questions
    that describe what features to compute, their calculations, dependencies,
    and compliance mappings.
    
    Output: Natural language questions (NOT SQL)
    These questions can then be translated to SQL by downstream agents.
    """
    
    SYSTEM_PROMPT = """You are a compliance data engineer specializing in feature engineering for risk assessment.

Your task is to generate NATURAL LANGUAGE QUESTIONS that describe features to compute.
These questions will be translated to SQL by a separate agent.

CRITICAL RULES:
1. Output ONLY natural language questions - NO SQL CODE
2. Each question should describe ONE specific feature calculation
3. Include calculation logic in plain English
4. Reference source tables and dependencies clearly
5. Explain what the feature proves for compliance

QUESTION FORMAT:
Each question should follow this pattern:
"Calculate [FEATURE_NAME] by [CALCULATION_DESCRIPTION] using [SOURCE_TABLES]. 
This feature [COMPLIANCE_PURPOSE]. Dependencies: [DEPS]. Output type: [TYPE]."

Example questions:
- "Calculate soc2_raw_impact by combining environment weight (0.4 for prod), bastion access multiplier (1.5 if true), and internet exposure weight (0.3 if exposed) using dev_assets and asset_control_evidence_features. This feature measures the potential impact of a security incident for SOC2 CC6.1. Dependencies: asset_environment, is_bastion_host, is_internet_exposed. Output type: float 0-1."

- "Calculate has_agent_installed as a boolean indicating whether the asset has a monitoring agent by checking if agent_id is not null in dev_agents table. This feature provides evidence for SOC2 CC7.2 system monitoring. Dependencies: none. Output type: boolean."

QUALITY GUIDELINES:
- Be specific about calculation formulas
- Name exact columns to use
- Specify default values for nulls
- Include range constraints (e.g., 0-1 for scores)
- Map to compliance controls explicitly"""

    USER_PROMPT_TEMPLATE = """You are a compliance data engineer generating features for: {lane_type}

USER GOAL:
{user_goal}

DOMAIN CONTEXT:
Domain: {domain}
Compliance Frameworks: {frameworks}
Guardrails: {guardrails}

REQUIRED FEATURES (must generate questions for):
{required_features}

FEATURE DEPENDENCIES:
{feature_dependencies}

SQL PATTERN LIBRARY (describe these patterns in natural language):
{sql_patterns}

SIMILAR IMPLEMENTATIONS (learn from these examples):
{similar_implementations}

CALCULATION PATTERNS (use these formulas):
{calculation_patterns}

CONTROL MAPPINGS (what these features prove):
{control_mappings}

VALIDATION RULES (must satisfy):
{validation_rules}

EXPECTED OUTPUT:
Generate {num_questions} natural language questions, one per required feature.
Each question should be detailed enough for a SQL agent to implement.

FORMAT YOUR OUTPUT AS:
---
FEATURE: [feature_name]
TYPE: [impact|likelihood|risk|metric|boolean|classification]
QUESTION: [detailed natural language question]
DEPENDENCIES: [list of dependencies]
COMPLIANCE: [control mapping]
VALIDATION: [validation rules]
---

Generate the natural language questions now:"""

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        knowledge_helper: Optional["PlaybookKnowledgeHelper"] = None
    ):
        self.llm = llm
        self.knowledge_helper = knowledge_helper or PlaybookKnowledgeHelper()
    
    async def generate_nl_questions(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str],
        user_goal: str = None,
        lane_inputs: List[str] = None,
        lane_outputs: List[str] = None,
        research_context: Optional["LaneResearchContext"] = None
    ) -> NLFeatureGenerationResult:
        """
        Generate natural language questions for feature engineering.
        
        Args:
            lane_type: Type of lane
            domain: Domain name
            compliance_frameworks: Compliance frameworks
            user_goal: User's stated goal
            lane_inputs: Input table names
            lane_outputs: Output table names
            research_context: Optional research context for richer generation
            
        Returns:
            NLFeatureGenerationResult with generated questions
        """
        # Get research context if not provided
        if not research_context:
            research_context = self.knowledge_helper.get_lane_research_context(
                lane_type=lane_type,
                domain=domain,
                compliance_frameworks=compliance_frameworks,
                lane_inputs=lane_inputs,
                lane_outputs=lane_outputs
            )
        
        # Build the prompt
        prompt = self._build_prompt(
            lane_type=lane_type,
            domain=domain,
            frameworks=compliance_frameworks,
            user_goal=user_goal or f"Generate {lane_type.value} features for {', '.join(compliance_frameworks)} compliance",
            research_context=research_context
        )
        
        # Generate questions using LLM if available
        if self.llm:
            questions = await self._generate_with_llm(prompt, research_context)
        else:
            # Fallback to template-based generation
            questions = self._generate_from_templates(lane_type, research_context)
        
        return NLFeatureGenerationResult(
            questions=questions,
            lane_type=lane_type.value,
            domain=domain,
            frameworks=compliance_frameworks,
            generation_reasoning=f"Generated {len(questions)} questions for {lane_type.value}",
            quality_notes=research_context.quality_criteria.get("data_quality_checks", []) if research_context else []
        )
    
    def _build_prompt(
        self,
        lane_type: LaneType,
        domain: str,
        frameworks: List[str],
        user_goal: str,
        research_context: "LaneResearchContext"
    ) -> str:
        """Build the user prompt from research context"""
        
        # Format required features
        required_features = self._format_required_features(research_context)
        
        # Format feature dependencies
        feature_deps = self._format_feature_dependencies(research_context)
        
        # Format SQL patterns as natural language
        sql_patterns = self._format_sql_patterns(research_context)
        
        # Format similar implementations
        similar_impl = self._format_similar_implementations(research_context)
        
        # Format calculation patterns
        calc_patterns = self._format_calculation_patterns(research_context)
        
        # Format control mappings
        control_mappings = self._format_control_mappings(research_context)
        
        # Format validation rules
        validation_rules = self._format_validation_rules(research_context)
        
        # Format guardrails
        guardrails = self._format_guardrails(research_context)
        
        # Count required questions
        num_questions = len(research_context.feature_templates) if research_context.feature_templates else 5
        
        return self.USER_PROMPT_TEMPLATE.format(
            lane_type=lane_type.value,
            user_goal=user_goal,
            domain=domain,
            frameworks=", ".join(frameworks),
            guardrails=guardrails,
            required_features=required_features,
            feature_dependencies=feature_deps,
            sql_patterns=sql_patterns,
            similar_implementations=similar_impl,
            calculation_patterns=calc_patterns,
            control_mappings=control_mappings,
            validation_rules=validation_rules,
            num_questions=num_questions
        )
    
    def _format_required_features(self, context: "LaneResearchContext") -> str:
        """Format required features for the prompt"""
        if not context.feature_templates:
            return "- Generate appropriate features for this lane type"
        
        lines = []
        for i, template in enumerate(context.feature_templates, 1):
            feature_type = template.get("type", "unknown")
            pattern = template.get("pattern", "unknown")
            description = template.get("description", "")
            output_type = template.get("output_type", "unknown")
            
            lines.append(f"{i}. {pattern}")
            lines.append(f"   Type: {feature_type}")
            lines.append(f"   Description: {description}")
            lines.append(f"   Output: {output_type}")
            if template.get("enum_lookup"):
                lines.append(f"   Enum lookup: {template['enum_lookup']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_feature_dependencies(self, context: "LaneResearchContext") -> str:
        """Format feature dependencies for the prompt"""
        knowledge = context.knowledge
        
        if not knowledge.features:
            return "- No explicit dependencies specified"
        
        # Group by classification
        deps_by_type = {}
        for feature in knowledge.features[:15]:  # Limit to avoid token overflow
            classification = feature.get("classification", "other")
            if classification not in deps_by_type:
                deps_by_type[classification] = []
            deps_by_type[classification].append(feature)
        
        lines = []
        for classification, features in deps_by_type.items():
            lines.append(f"[{classification}]")
            for f in features[:5]:
                lines.append(f"  - {f.get('name', 'unknown')}: {f.get('description', 'N/A')}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_sql_patterns(self, context: "LaneResearchContext") -> str:
        """Format SQL patterns as natural language descriptions"""
        if not context.calculation_patterns:
            return "- Use standard SQL aggregations and transformations"
        
        lines = []
        for pattern in context.calculation_patterns:
            name = pattern.get("name", "unknown")
            description = pattern.get("description", "")
            use_case = pattern.get("use_case", "")
            sql = pattern.get("sql_pattern", "")
            
            lines.append(f"Pattern: {name}")
            lines.append(f"  Description: {description}")
            lines.append(f"  Use case: {use_case}")
            if sql:
                lines.append(f"  SQL hint: {sql[:100]}...")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_similar_implementations(self, context: "LaneResearchContext") -> str:
        """Format similar implementations from knowledge examples"""
        knowledge = context.knowledge
        
        if not knowledge.examples:
            return "- No similar implementations available"
        
        lines = []
        for ex in knowledge.examples[:5]:
            question = ex.get("question", "")
            instructions = ex.get("instructions", "")
            categories = ex.get("categories", [])
            
            lines.append(f"Q: {question}")
            lines.append(f"   Instructions: {instructions}")
            lines.append(f"   Categories: {', '.join(categories)}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_calculation_patterns(self, context: "LaneResearchContext") -> str:
        """Format calculation patterns"""
        if not context.calculation_patterns:
            return "- Use domain-appropriate calculations"
        
        lines = []
        for pattern in context.calculation_patterns:
            name = pattern.get("name", "")
            description = pattern.get("description", "")
            use_case = pattern.get("use_case", "")
            
            lines.append(f"- {name}: {description} (for {use_case})")
        
        return "\n".join(lines)
    
    def _format_control_mappings(self, context: "LaneResearchContext") -> str:
        """Format control mappings"""
        if not context.control_mappings:
            return "- Map features to appropriate compliance controls"
        
        lines = []
        for mapping in context.control_mappings:
            framework = mapping.get("framework", "")
            control_id = mapping.get("control_id", "")
            control_name = mapping.get("control_name", "")
            features = mapping.get("features", [])
            
            lines.append(f"{framework} {control_id}: {control_name}")
            lines.append(f"   Required features: {', '.join(features)}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_validation_rules(self, context: "LaneResearchContext") -> str:
        """Format validation rules"""
        if not context.validation_rules:
            return "- Standard data quality validations"
        
        lines = []
        for rule_set in context.validation_rules:
            scope = rule_set.get("table", rule_set.get("scope", "all"))
            rules = rule_set.get("rules", [])
            
            lines.append(f"[{scope}]")
            for rule in rules:
                rule_type = rule.get("type", "")
                description = rule.get("description", "")
                lines.append(f"  - {rule_type}: {description}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_guardrails(self, context: "LaneResearchContext") -> str:
        """Format guardrails from quality criteria"""
        criteria = context.quality_criteria
        if not criteria:
            return "Silver-layer only, per-entity features"
        
        lines = []
        if criteria.get("medallion_layer"):
            lines.append(f"Layer: {criteria['medallion_layer']}")
        if criteria.get("aggregation_level"):
            lines.append(f"Aggregation: {criteria['aggregation_level']}")
        if criteria.get("allowed_operations"):
            lines.append("Allowed:")
            for op in criteria["allowed_operations"][:5]:
                lines.append(f"  ✓ {op}")
        if criteria.get("prohibited_operations"):
            lines.append("Prohibited:")
            for op in criteria["prohibited_operations"][:3]:
                lines.append(f"  ✗ {op}")
        
        return "\n".join(lines)
    
    async def _generate_with_llm(
        self,
        prompt: str,
        context: "LaneResearchContext"
    ) -> List[NLFeatureQuestion]:
        """Generate questions using LLM"""
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse questions from response
            return self._parse_nl_questions(content, context)
            
        except Exception as e:
            logger.error(f"Error generating NL questions with LLM: {e}")
            return self._generate_from_templates(
                LaneType(context.lane_type) if isinstance(context.lane_type, str) else context.lane_type,
                context
            )
    
    def _parse_nl_questions(
        self,
        content: str,
        context: "LaneResearchContext"
    ) -> List[NLFeatureQuestion]:
        """Parse NL questions from LLM response"""
        questions = []
        
        # Split by feature blocks
        blocks = re.split(r'---+', content)
        
        for block in blocks:
            if not block.strip():
                continue
            
            # Extract fields
            feature_match = re.search(r'FEATURE:\s*(.+)', block, re.IGNORECASE)
            type_match = re.search(r'TYPE:\s*(.+)', block, re.IGNORECASE)
            question_match = re.search(r'QUESTION:\s*(.+?)(?=DEPENDENCIES:|COMPLIANCE:|VALIDATION:|$)', block, re.IGNORECASE | re.DOTALL)
            deps_match = re.search(r'DEPENDENCIES:\s*(.+?)(?=COMPLIANCE:|VALIDATION:|$)', block, re.IGNORECASE | re.DOTALL)
            compliance_match = re.search(r'COMPLIANCE:\s*(.+?)(?=VALIDATION:|$)', block, re.IGNORECASE | re.DOTALL)
            validation_match = re.search(r'VALIDATION:\s*(.+?)$', block, re.IGNORECASE | re.DOTALL)
            
            if question_match:
                feature_name = feature_match.group(1).strip() if feature_match else "unknown_feature"
                feature_type = type_match.group(1).strip() if type_match else "metric"
                question_text = question_match.group(1).strip()
                
                # Parse dependencies
                deps = []
                if deps_match:
                    deps_text = deps_match.group(1).strip()
                    deps = [d.strip() for d in re.split(r'[,\n]', deps_text) if d.strip() and d.strip() != 'none']
                
                # Parse compliance
                compliance = None
                if compliance_match:
                    compliance = compliance_match.group(1).strip()
                
                # Parse validation
                validation = []
                if validation_match:
                    val_text = validation_match.group(1).strip()
                    validation = [v.strip() for v in re.split(r'[,\n]', val_text) if v.strip()]
                
                questions.append(NLFeatureQuestion(
                    question=question_text,
                    feature_name=feature_name,
                    feature_type=feature_type,
                    calculation_hint="",  # Embedded in question
                    dependencies=deps,
                    compliance_mapping=compliance,
                    validation_rules=validation,
                    priority=1
                ))
        
        # If no questions parsed, try simpler line-by-line parsing
        if not questions:
            questions = self._parse_simple_questions(content, context)
        
        return questions
    
    def _parse_simple_questions(
        self,
        content: str,
        context: "LaneResearchContext"
    ) -> List[NLFeatureQuestion]:
        """Simple line-by-line parsing fallback"""
        questions = []
        
        # Look for "Calculate..." patterns
        calc_patterns = re.findall(
            r'(?:Calculate|Compute|Generate|Create)\s+(\w+)\s+(?:by|as|from).+?(?:\.|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        
        for i, match in enumerate(calc_patterns[:10]):
            questions.append(NLFeatureQuestion(
                question=match,
                feature_name=f"feature_{i+1}",
                feature_type="metric",
                calculation_hint="",
                priority=i + 1
            ))
        
        return questions
    
    def _generate_from_templates(
        self,
        lane_type: LaneType,
        context: "LaneResearchContext"
    ) -> List[NLFeatureQuestion]:
        """Generate questions from templates without LLM"""
        questions = []
        
        for template in context.feature_templates:
            feature_type = template.get("type", "metric")
            pattern = template.get("pattern", "unknown")
            description = template.get("description", "")
            calculation = template.get("calculation", "")
            output_type = template.get("output_type", "unknown")
            components = template.get("components", [])
            enum_lookup = template.get("enum_lookup")
            framework = template.get("framework", "")
            
            # Build natural language question from template
            question = self._template_to_question(
                feature_type=feature_type,
                pattern=pattern,
                description=description,
                calculation=calculation,
                output_type=output_type,
                components=components,
                enum_lookup=enum_lookup,
                framework=framework,
                context=context
            )
            
            questions.append(NLFeatureQuestion(
                question=question,
                feature_name=pattern,
                feature_type=feature_type,
                calculation_hint=calculation,
                dependencies=components,
                compliance_mapping=self._get_compliance_mapping(pattern, context),
                enum_lookup=enum_lookup,
                validation_rules=self._get_validation_rules(output_type),
                priority=1
            ))
        
        return questions
    
    def _template_to_question(
        self,
        feature_type: str,
        pattern: str,
        description: str,
        calculation: str,
        output_type: str,
        components: List[str],
        enum_lookup: Optional[str],
        framework: str,
        context: "LaneResearchContext"
    ) -> str:
        """Convert a feature template to a natural language question"""
        
        # Get source tables from control mappings
        source_tables = []
        for mapping in context.control_mappings:
            if pattern in mapping.get("features", []):
                source_tables.extend(mapping.get("evidence_tables", []))
        source_tables = list(set(source_tables)) or ["source_table"]
        
        # Build the question based on feature type
        if feature_type == "impact_feature":
            question = (
                f"Calculate {pattern} by {calculation} "
                f"using {', '.join(source_tables)}. "
                f"{description}. "
                f"Components: {', '.join(components) if components else 'see calculation'}. "
                f"Output type: {output_type}"
            )
            if enum_lookup:
                question += f". Use {enum_lookup} for classification labels"
            
        elif feature_type == "likelihood_feature":
            question = (
                f"Calculate {pattern} as the composite likelihood score by {calculation} "
                f"using {', '.join(source_tables)}. "
                f"{description}. "
                f"Contributing factors: {', '.join(components) if components else 'threat signals'}. "
                f"Output type: {output_type}"
            )
            
        elif feature_type == "risk_feature":
            question = (
                f"Calculate {pattern} by {calculation} "
                f"using the previously computed impact and likelihood scores. "
                f"{description}. "
                f"Output type: {output_type}"
            )
            
        elif feature_type == "risk_driver":
            question = (
                f"Determine {pattern} by identifying the primary contributing factor to the risk score "
                f"using CASE WHEN logic to compare {', '.join(components) if components else 'impact components'}. "
                f"{description}. "
                f"Output type: {output_type}"
            )
            if enum_lookup:
                question += f". Valid values from {enum_lookup}"
            
        elif feature_type == "boolean_flag":
            question = (
                f"Calculate {pattern} as a boolean indicator {description.lower()} "
                f"using COALESCE with appropriate null handling. "
                f"Output type: boolean (true/false)"
            )
            
        elif feature_type == "control_state":
            question = (
                f"Determine {pattern} by evaluating evidence to produce a control evaluation result "
                f"(pass/fail/unknown/exception) using CASE WHEN logic. "
                f"{description}. "
                f"Output type: {output_type}"
            )
            if enum_lookup:
                question += f". Valid values from {enum_lookup}"
            
        elif feature_type == "classification":
            question = (
                f"Classify {pattern} {description.lower()} "
                f"using CASE WHEN buckets or enum lookup. "
                f"Output type: {output_type}"
            )
            if enum_lookup:
                question += f". Use {enum_lookup} for valid values"
            
        else:
            # Generic feature
            question = (
                f"Calculate {pattern}: {description}. "
                f"Calculation approach: {calculation or 'appropriate derivation'}. "
                f"Output type: {output_type}"
            )
        
        # Add framework context if available
        if framework:
            question = f"[{framework}] " + question
        
        return question
    
    def _get_compliance_mapping(
        self,
        feature_name: str,
        context: "LaneResearchContext"
    ) -> Optional[str]:
        """Get compliance mapping for a feature"""
        for mapping in context.control_mappings:
            if feature_name in mapping.get("features", []):
                return f"{mapping.get('framework', '')} {mapping.get('control_id', '')}: {mapping.get('control_name', '')}"
        return None
    
    def _get_validation_rules(self, output_type: str) -> List[str]:
        """Get validation rules based on output type"""
        rules = []
        
        if output_type == "float":
            rules.append("Value must be numeric")
        if "0-1" in output_type or output_type == "float":
            rules.append("Range: 0.0 to 1.0")
        if output_type == "boolean":
            rules.append("Must be true or false")
        if output_type == "string":
            rules.append("Must not be null for required fields")
        
        return rules


# ============================================================================
# LANE DEEP RESEARCH AGENT
# ============================================================================

class LaneDeepResearchAgent:
    """
    Deep research agent that generates rich context for lane feature generation.
    
    This agent combines knowledge retrieval with LLM-powered research to:
    1. Analyze lane requirements and generate feature recommendations
    2. Provide detailed calculation guidance with SQL patterns
    3. Map features to compliance controls
    4. Generate quality criteria and validation rules
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        knowledge_helper: Optional["PlaybookKnowledgeHelper"] = None
    ):
        self.llm = llm
        self.knowledge_helper = knowledge_helper or PlaybookKnowledgeHelper()
    
    async def research_lane_context(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str],
        lane_inputs: List[str] = None,
        lane_outputs: List[str] = None,
        lane_description: str = None
    ) -> LaneResearchContext:
        """
        Perform deep research to generate rich context for a lane.
        
        Args:
            lane_type: Type of lane
            domain: Domain name
            compliance_frameworks: Compliance frameworks
            lane_inputs: Input table names
            lane_outputs: Output table names
            lane_description: Optional lane description
            
        Returns:
            LaneResearchContext with research-enhanced context
        """
        # Get base research context from knowledge helper
        context = self.knowledge_helper.get_lane_research_context(
            lane_type=lane_type,
            domain=domain,
            compliance_frameworks=compliance_frameworks,
            lane_inputs=lane_inputs,
            lane_outputs=lane_outputs
        )
        
        # If LLM is available, enhance with deep research
        if self.llm:
            research_insights = await self._generate_research_insights(
                lane_type=lane_type,
                domain=domain,
                frameworks=compliance_frameworks,
                inputs=lane_inputs or [],
                outputs=lane_outputs or [],
                description=lane_description,
                existing_context=context
            )
            context.research_insights = research_insights
            
            # Generate recommended features based on research
            recommended = await self._recommend_features(
                lane_type=lane_type,
                domain=domain,
                frameworks=compliance_frameworks,
                context=context
            )
            context.recommended_features = recommended
        
        return context
    
    async def _generate_research_insights(
        self,
        lane_type: LaneType,
        domain: str,
        frameworks: List[str],
        inputs: List[str],
        outputs: List[str],
        description: str,
        existing_context: LaneResearchContext
    ) -> Dict[str, Any]:
        """Generate research insights using LLM"""
        if not self.llm:
            return {}
        
        system_prompt = """You are a compliance data engineering expert specializing in feature engineering for risk assessment.

Analyze the lane context and provide research insights for feature generation:
1. Key features that should be generated
2. Calculation approaches and SQL patterns
3. Compliance control mappings
4. Quality considerations

Focus on SILVER-layer features (per-entity, no population aggregates).
Provide actionable, specific recommendations."""

        # Format existing context for the prompt
        features_text = "\n".join([
            f"- {f.get('name', 'unknown')}: {f.get('description', 'N/A')}"
            for f in existing_context.knowledge.features[:10]
        ])
        
        examples_text = "\n".join([
            f"- Q: {ex.get('question', '')}\n  Instructions: {ex.get('instructions', '')}"
            for ex in existing_context.knowledge.examples[:5]
        ])
        
        templates_text = "\n".join([
            f"- {t.get('type', 'unknown')}: {t.get('pattern', '')} - {t.get('description', '')}"
            for t in existing_context.feature_templates[:5]
        ])
        
        prompt = f"""
LANE CONTEXT:
- Lane Type: {lane_type.value}
- Domain: {domain}
- Frameworks: {', '.join(frameworks)}
- Inputs: {', '.join(inputs) if inputs else 'Not specified'}
- Outputs: {', '.join(outputs) if outputs else 'Not specified'}
- Description: {description or 'Not provided'}

AVAILABLE FEATURES:
{features_text}

EXAMPLE QUESTIONS:
{examples_text}

FEATURE TEMPLATES:
{templates_text}

GUARDRAILS:
- Silver-layer only (per-entity features)
- No population aggregates
- Enum lookups for classifications

Provide research insights in the following format:
1. KEY FEATURES TO GENERATE (3-5 specific features)
2. CALCULATION APPROACHES (SQL patterns to use)
3. CONTROL MAPPINGS (which compliance controls these support)
4. QUALITY CONSIDERATIONS (validation and data quality)
"""
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse insights from response
            return self._parse_research_insights(content)
            
        except Exception as e:
            logger.error(f"Error generating research insights: {e}")
            return {"error": str(e)}
    
    def _parse_research_insights(self, content: str) -> Dict[str, Any]:
        """Parse research insights from LLM response"""
        insights = {
            "key_features": [],
            "calculation_approaches": [],
            "control_mappings": [],
            "quality_considerations": [],
            "raw_content": content[:2000]  # Keep truncated raw for reference
        }
        
        # Extract key features section
        features_match = re.search(
            r"KEY FEATURES[:\s]*([\s\S]*?)(?=CALCULATION|CONTROL|QUALITY|$)",
            content, re.IGNORECASE
        )
        if features_match:
            features_text = features_match.group(1)
            features = re.findall(r"[-•*\d.]\s*([^\n]+)", features_text)
            insights["key_features"] = [f.strip() for f in features[:10]]
        
        # Extract calculation approaches
        calc_match = re.search(
            r"CALCULATION[:\s]*([\s\S]*?)(?=CONTROL|QUALITY|$)",
            content, re.IGNORECASE
        )
        if calc_match:
            calc_text = calc_match.group(1)
            calcs = re.findall(r"[-•*\d.]\s*([^\n]+)", calc_text)
            insights["calculation_approaches"] = [c.strip() for c in calcs[:10]]
        
        # Extract control mappings
        control_match = re.search(
            r"CONTROL[:\s]*([\s\S]*?)(?=QUALITY|$)",
            content, re.IGNORECASE
        )
        if control_match:
            control_text = control_match.group(1)
            controls = re.findall(r"[-•*\d.]\s*([^\n]+)", control_text)
            insights["control_mappings"] = [c.strip() for c in controls[:10]]
        
        # Extract quality considerations
        quality_match = re.search(
            r"QUALITY[:\s]*([\s\S]*?)$",
            content, re.IGNORECASE
        )
        if quality_match:
            quality_text = quality_match.group(1)
            quality = re.findall(r"[-•*\d.]\s*([^\n]+)", quality_text)
            insights["quality_considerations"] = [q.strip() for q in quality[:10]]
        
        return insights
    
    async def _recommend_features(
        self,
        lane_type: LaneType,
        domain: str,
        frameworks: List[str],
        context: LaneResearchContext
    ) -> List[Dict[str, Any]]:
        """Generate specific feature recommendations"""
        recommendations = []
        
        # Use templates and research insights to generate recommendations
        for template in context.feature_templates:
            rec = {
                "feature_type": template.get("type", "unknown"),
                "feature_pattern": template.get("pattern", ""),
                "description": template.get("description", ""),
                "calculation": template.get("calculation", ""),
                "output_type": template.get("output_type", "unknown"),
                "framework": template.get("framework"),
                "source": "template"
            }
            
            if template.get("enum_lookup"):
                rec["enum_lookup"] = template["enum_lookup"]
            
            recommendations.append(rec)
        
        # Add recommendations from research insights
        if context.research_insights.get("key_features"):
            for feature_text in context.research_insights["key_features"][:5]:
                recommendations.append({
                    "feature_type": "research_recommended",
                    "description": feature_text,
                    "source": "deep_research"
                })
        
        return recommendations


# ============================================================================
# ENHANCED KNOWLEDGE RETRIEVER
# ============================================================================

class EnhancedKnowledgeRetriever:
    """
    Combines PlaybookKnowledgeHelper with LaneDeepResearchAgent for
    comprehensive knowledge retrieval with deep research capabilities.
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None
    ):
        self.knowledge_helper = PlaybookKnowledgeHelper()
        self.research_agent = LaneDeepResearchAgent(
            llm=llm,
            knowledge_helper=self.knowledge_helper
        )
    
    def get_knowledge_context(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str] = None
    ) -> KnowledgeContext:
        """Get basic knowledge context (synchronous)"""
        return self.knowledge_helper.get_knowledge_context(
            lane_type=lane_type,
            domain=domain,
            compliance_frameworks=compliance_frameworks
        )
    
    async def get_rich_context(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str] = None,
        lane_inputs: List[str] = None,
        lane_outputs: List[str] = None,
        lane_description: str = None
    ) -> LaneResearchContext:
        """
        Get rich context with deep research (asynchronous).
        
        This is the recommended method for feature generation as it
        provides comprehensive context including research insights.
        """
        return await self.research_agent.research_lane_context(
            lane_type=lane_type,
            domain=domain,
            compliance_frameworks=compliance_frameworks or [],
            lane_inputs=lane_inputs,
            lane_outputs=lane_outputs,
            lane_description=lane_description
        )
    
    def get_feature_templates(
        self,
        lane_type: LaneType,
        frameworks: List[str]
    ) -> List[Dict[str, Any]]:
        """Get feature templates for a lane type"""
        return self.knowledge_helper._build_feature_templates(
            lane_type=lane_type,
            domain="",
            frameworks=frameworks
        )
    
    def get_calculation_patterns(
        self,
        lane_type: LaneType,
        frameworks: List[str]
    ) -> List[Dict[str, Any]]:
        """Get calculation patterns for a lane type"""
        return self.knowledge_helper._build_calculation_patterns(
            lane_type=lane_type,
            frameworks=frameworks
        )


# ============================================================================
# GLOBAL INSTANCE AND FACTORY
# ============================================================================

_playbook_knowledge_helper: Optional[PlaybookKnowledgeHelper] = None
_enhanced_knowledge_retriever: Optional[EnhancedKnowledgeRetriever] = None


def get_playbook_knowledge_helper() -> PlaybookKnowledgeHelper:
    """Get or create the global playbook knowledge helper"""
    global _playbook_knowledge_helper
    if _playbook_knowledge_helper is None:
        _playbook_knowledge_helper = PlaybookKnowledgeHelper()
    return _playbook_knowledge_helper


def get_enhanced_knowledge_retriever(
    llm: Optional[BaseChatModel] = None
) -> EnhancedKnowledgeRetriever:
    """
    Get or create the global enhanced knowledge retriever.
    
    Args:
        llm: Optional LLM for deep research capabilities
        
    Returns:
        EnhancedKnowledgeRetriever instance
    """
    global _enhanced_knowledge_retriever
    if _enhanced_knowledge_retriever is None:
        _enhanced_knowledge_retriever = EnhancedKnowledgeRetriever(llm=llm)
    return _enhanced_knowledge_retriever


def create_lane_deep_research_agent(
    llm: Optional[BaseChatModel] = None,
    knowledge_helper: Optional[PlaybookKnowledgeHelper] = None
) -> LaneDeepResearchAgent:
    """
    Factory function to create a LaneDeepResearchAgent.
    
    Args:
        llm: Optional LLM for research capabilities
        knowledge_helper: Optional knowledge helper (uses global if not provided)
        
    Returns:
        LaneDeepResearchAgent instance
    """
    helper = knowledge_helper or get_playbook_knowledge_helper()
    return LaneDeepResearchAgent(llm=llm, knowledge_helper=helper)


def create_nl_feature_generation_agent(
    llm: Optional[BaseChatModel] = None,
    knowledge_helper: Optional[PlaybookKnowledgeHelper] = None
) -> NLFeatureGenerationAgent:
    """
    Factory function to create a NLFeatureGenerationAgent.
    
    This agent generates natural language questions for feature engineering
    that can be translated to SQL by downstream agents.
    
    Args:
        llm: Optional LLM for generation (if None, uses template-based generation)
        knowledge_helper: Optional knowledge helper (uses global if not provided)
        
    Returns:
        NLFeatureGenerationAgent instance
        
    Example usage:
        agent = create_nl_feature_generation_agent(llm=llm)
        result = await agent.generate_nl_questions(
            lane_type=LaneType.RISK_SCORING,
            domain="cybersecurity",
            compliance_frameworks=["SOC2", "HIPAA"],
            user_goal="Generate risk scores for assets"
        )
        for q in result.questions:
            print(f"{q.feature_name}: {q.question}")
    """
    helper = knowledge_helper or get_playbook_knowledge_helper()
    return NLFeatureGenerationAgent(llm=llm, knowledge_helper=helper)


def reset_playbook_knowledge_helper() -> None:
    """Reset the global playbook knowledge helper (useful for testing)"""
    global _playbook_knowledge_helper, _enhanced_knowledge_retriever
    _playbook_knowledge_helper = None
    _enhanced_knowledge_retriever = None
