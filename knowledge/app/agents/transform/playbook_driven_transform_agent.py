"""
Playbook-Driven Transform Agent with Human-in-the-Loop Architecture

This agent extends TransformSQLRAGAgent to support:
1. Playbook-driven workflows (Cornerstone, Snyk, etc.)
2. Lane-based architecture for staged transformations
3. Human-in-the-loop approval checkpoints
4. Contextual graph reasoning integration
5. Source connector abstraction for multiple data sources

Architecture follows the lane patterns from:
- cornerstone_playbook.md: People/Training compliance workflows
- snyk_silver_tables.md: Vulnerability/Asset risk workflows
"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Sequence, TypedDict, Union,
    Annotated
)

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from app.core.engine import Engine
from app.core.provider import DocumentStoreProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.agents.nodes.transform.transform_sql_rag_agent import TransformSQLRAGAgent
from app.agents.nodes.transform.domain_config import (
    DomainConfiguration,
    CYBERSECURITY_DOMAIN_CONFIG,
    HR_COMPLIANCE_DOMAIN_CONFIG,
    RISK_MANAGEMENT_DOMAIN_CONFIG,
    get_domain_config,
    ComplianceMetricLibrary,
    get_compliance_metric_library
)
from app.agents.nodes.transform.playbook_knowledge_helper import (
    LaneType,
    PlaybookKnowledgeHelper,
    KnowledgeContext,
    NLFeatureQuestion,
    NLFeatureGenerationResult,
    get_playbook_knowledge_helper,
    create_nl_feature_generation_agent,
    AGENT_CATEGORY_MAPPING,
    LANE_TO_AGENT_MAPPING,
    FEATURE_KNOWLEDGE_BASE,
    ENUM_METADATA_REFS,
    SQL_INSTRUCTION_EXAMPLES
)
from app.agents.nodes.transform.lane_feature_integration import (
    LaneFeatureExecutor,
    create_lane_feature_executor,
    get_lane_agent_config,
    playbook_to_feature_state,
    feature_to_playbook_state,
    LANE_AGENT_CONFIGS
)

logger = logging.getLogger("lexy-ai-service")


# ============================================================================
# LANE AND PLAYBOOK TYPES (LaneType imported from playbook_knowledge_helper)
# ============================================================================

# LaneType is now imported from playbook_knowledge_helper
# Re-export for backward compatibility - all lane types are available via LaneType enum


class ApprovalStatus(str, Enum):
    """Status of human-in-the-loop approvals"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class PlaybookType(str, Enum):
    """Types of supported playbooks"""
    CORNERSTONE = "cornerstone"  # HR/Training compliance
    SNYK = "snyk"  # Vulnerability management
    GENERIC = "generic"  # Generic data pipeline
    CUSTOM = "custom"  # Custom playbook


# ============================================================================
# DATA CATEGORY MAPPINGS FOR CHROMA RETRIEVAL
# ============================================================================

# Table categories for different playbook domains
# These map to how tables are organized in Chroma by category/domain

CORNERSTONE_TABLE_CATEGORIES = {
    "bronze": [
        "raw_csod_users",
        "raw_csod_transcripts", 
        "raw_csod_assigned_trainings",
        "raw_csod_tasks",
        "raw_csod_assignments"
    ],
    "silver_assets": [
        "hr_people_assets",
        "hr_training_obligations"
    ],
    "silver_instances": [
        "hr_training_instances"
    ],
    "silver_features": [
        "hr_training_features_silver"
    ],
    "enum_metadata": [
        "training_status_metadata",
        "training_obligation_metadata",
        "training_impact_class_metadata",
        "training_likelihood_class_metadata",
        "training_risk_level_metadata",
        "training_risk_driver_metadata"
    ],
    "risk_timeseries": [
        "general_training_risk_timeseries",
        "soc2_training_risk_timeseries",
        "hipaa_training_risk_timeseries"
    ],
    "compliance": [
        "hr_control_status",
        "soc2_evidence_packages",
        "hipaa_evidence_packages"
    ]
}

SNYK_TABLE_CATEGORIES = {
    "bronze": [
        "raw_snyk_orgs",
        "raw_snyk_projects",
        "raw_snyk_targets",
        "raw_snyk_issues",
        "raw_snyk_policy_ignores",
        "raw_snyk_test_runs"
    ],
    "silver_assets": [
        "dev_assets"
    ],
    "silver_agents": [
        "dev_agents",
        "asset_control_evidence_features"
    ],
    "silver_vulnerabilities": [
        "dev_vulnerability_instances",
        "dev_vulnerability_enrichment"
    ],
    "silver_features": [
        "dev_asset_features_silver"
    ],
    "enum_metadata": [
        "vuln_exploit_signal_metadata",
        "telemetry_freshness_metadata",
        "asset_exposure_metadata",
        "risk_impact_metadata",
        "likelihood_vuln_attributes_metadata",
        "risk_driver_metadata",
        "control_state_metadata"
    ],
    "risk_timeseries": [
        "asset_feature_timeseries",
        "soc2_asset_risk_timeseries",
        "hipaa_asset_risk_timeseries"
    ],
    "compliance": [
        "dev_asset_control_status",
        "soc2_evidence_packages",
        "hipaa_evidence_packages",
        "risk_alerts"
    ]
}

# Domain to table category mapping
DOMAIN_TABLE_CATEGORIES = {
    "hr_compliance": CORNERSTONE_TABLE_CATEGORIES,
    "cybersecurity": SNYK_TABLE_CATEGORIES,
}


def get_tables_for_lane(
    domain: str,
    lane_type: "LaneType",
    playbook_type: str
) -> List[str]:
    """Get relevant tables for a specific lane type and domain.
    
    Uses category mappings to determine which tables to retrieve from Chroma.
    
    Args:
        domain: Domain name (e.g., 'hr_compliance', 'cybersecurity')
        lane_type: Type of lane being executed
        playbook_type: Playbook type for additional context
        
    Returns:
        List of table names to retrieve
    """
    categories = DOMAIN_TABLE_CATEGORIES.get(domain, {})
    
    # Map lane types to relevant categories
    lane_category_mapping = {
        LaneType.BOOTSTRAP: ["enum_metadata"],
        LaneType.INGESTION: ["bronze"],
        LaneType.ASSETIZATION: ["bronze", "silver_assets"],
        LaneType.MONITORING: ["silver_assets", "silver_agents"] if "silver_agents" in categories else ["silver_assets"],
        LaneType.NORMALIZATION: ["bronze", "silver_instances"] if "silver_instances" in categories else ["bronze", "silver_vulnerabilities"],
        LaneType.SILVER_FEATURES: ["silver_assets", "silver_instances", "silver_features"] if "silver_instances" in categories else ["silver_assets", "silver_vulnerabilities", "silver_features"],
        LaneType.RISK_SCORING: ["silver_features", "enum_metadata"],
        LaneType.TIME_SERIES: ["silver_features", "risk_timeseries"],
        LaneType.COMPLIANCE: ["risk_timeseries", "compliance", "enum_metadata"],
        LaneType.DELIVERY: ["compliance"]
    }
    
    relevant_categories = lane_category_mapping.get(lane_type, [])
    tables = []
    for category in relevant_categories:
        tables.extend(categories.get(category, []))
    
    return tables


def get_all_tables_for_domain(domain: str) -> List[str]:
    """Get all tables for a domain.
    
    Args:
        domain: Domain name
        
    Returns:
        List of all table names for the domain
    """
    categories = DOMAIN_TABLE_CATEGORIES.get(domain, {})
    tables = []
    for category_tables in categories.values():
        tables.extend(category_tables)
    return tables


# ============================================================================
# PLAYBOOK STATE AND LANE DEFINITIONS
# ============================================================================

def last_value_reducer(current: Optional[str], updates: List[str]) -> str:
    """Reducer for state keys that take the last value"""
    if updates:
        return updates[-1]
    return current if current is not None else ""


def dict_merge_reducer(current: Optional[Dict], updates: List[Dict]) -> Dict:
    """Reducer that merges dictionaries"""
    result = current.copy() if current else {}
    for update in updates:
        if update:
            result.update(update)
    return result


@dataclass
class LaneDefinition:
    """Definition of a single lane in a playbook"""
    lane_id: int
    lane_type: LaneType
    name: str
    description: str
    agent_name: str  # Name of the agent responsible
    inputs: List[str]  # Required input table/entity names
    outputs: List[str]  # Output table/entity names
    requires_approval: bool = False  # Human-in-the-loop checkpoint
    approval_message: str = ""  # Message shown for approval
    timeout_seconds: int = 3600  # Default 1 hour timeout for approval
    dependencies: List[int] = field(default_factory=list)  # Lane IDs this depends on
    sql_templates: List[str] = field(default_factory=list)  # SQL templates for this lane
    validation_rules: List[str] = field(default_factory=list)  # Validation rules


@dataclass
class PlaybookDefinition:
    """Definition of a complete playbook"""
    playbook_id: str
    playbook_type: PlaybookType
    name: str
    description: str
    domain: str  # 'cybersecurity', 'hr_compliance', etc.
    lanes: List[LaneDefinition]
    compliance_frameworks: List[str] = field(default_factory=list)
    output_time_series_tables: List[str] = field(default_factory=list)
    guardrails: Dict[str, Any] = field(default_factory=dict)
    table_categories: Dict[str, List[str]] = field(default_factory=dict)  # Tables organized by category


class PlaybookExecutionState(TypedDict, total=False):
    """State for playbook execution workflow"""
    
    # Playbook context
    playbook_id: str
    playbook_type: str
    execution_id: str
    project_id: str
    domain: str  # Domain for table retrieval (e.g., 'hr_compliance', 'cybersecurity')
    compliance_frameworks: List[str]  # Applicable compliance frameworks
    
    # Lane execution state
    current_lane_id: int
    current_lane_type: str
    completed_lanes: List[int]
    failed_lanes: List[int]
    skipped_lanes: List[int]
    
    # Human-in-the-loop state
    pending_approval: bool
    approval_status: str  # ApprovalStatus value
    approval_request: Optional[Dict[str, Any]]
    approval_response: Optional[Dict[str, Any]]
    approval_deadline: Optional[str]  # ISO timestamp
    
    # Data state
    bronze_tables: Dict[str, Any]  # Raw ingested data
    silver_features: Dict[str, Any]  # Computed features
    risk_scores: Dict[str, Any]  # Risk calculations
    time_series_snapshots: Dict[str, Any]  # Time series data
    compliance_evidence: Dict[str, Any]  # Evidence packages
    
    # Natural Language Question Generation (NEW)
    nl_questions: List[Dict[str, Any]]  # Generated NL questions with metadata
    reasoning_plans: Dict[str, Any]  # Reasoning plans by lane
    lane_questions: Dict[str, List[Dict[str, Any]]]  # Questions organized by lane
    
    # SQL generation state (for future translation)
    generated_sql: List[Dict[str, Any]]  # Generated SQL statements
    executed_sql: List[Dict[str, Any]]  # Executed SQL results
    sql_errors: List[Dict[str, Any]]  # SQL execution errors
    
    # Knowledge and context
    knowledge_context: Dict[str, Any]  # Retrieved knowledge
    schema_context: List[str]  # Database schema contexts
    enum_metadata: Dict[str, Any]  # Enum metadata tables
    feature_definitions: List[Dict[str, Any]]  # Feature definitions from KB
    
    # Reasoning state
    reasoning_plan: Optional[Dict[str, Any]]
    transform_reasoning: Optional[Dict[str, Any]]
    contextual_reasoning: Optional[Dict[str, Any]]
    
    # Messages for conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Workflow state
    current_node: Annotated[str, last_value_reducer]
    next_node: Optional[str]
    status: Annotated[str, last_value_reducer]
    error: Optional[str]
    
    # Metrics and monitoring
    lane_metrics: Dict[str, Dict[str, Any]]  # Per-lane execution metrics
    total_records_processed: int
    start_time: str
    end_time: Optional[str]
    
    # Final outputs
    final_output: Optional[Dict[str, Any]]


# ============================================================================
# USER GOAL TYPES AND INTENT
# ============================================================================

class UserGoalType(str, Enum):
    """Types of user goals that drive playbook selection and lane mapping"""
    ADD_FEATURES = "add_features"  # Add new features to tables
    COMPLIANCE_AUDIT = "compliance_audit"  # Understand/fix audit issues (Vanta, etc.)
    RISK_ANALYSIS = "risk_analysis"  # Analyze security risk
    EVIDENCE_GENERATION = "evidence_generation"  # Generate compliance evidence
    DATA_INGESTION = "data_ingestion"  # Ingest new data source
    INVESTIGATION = "investigation"  # Investigate specific issues
    CUSTOM = "custom"  # Custom user-defined goal


class ComplianceFramework(str, Enum):
    """Supported compliance frameworks"""
    SOC2 = "SOC2"
    HIPAA = "HIPAA"
    ISO_27001 = "ISO_27001"
    PCI_DSS = "PCI_DSS"
    GDPR = "GDPR"
    NIST = "NIST"
    GENERAL = "GENERAL"


class DataSourceType(str, Enum):
    """Types of data sources that map to playbooks"""
    SNYK = "snyk"  # Vulnerability scanner
    CORNERSTONE = "cornerstone"  # LMS/Training
    CROWDSTRIKE = "crowdstrike"  # EDR
    QUALYS = "qualys"  # Vulnerability scanner
    VANTA = "vanta"  # Compliance automation
    AZURE_AD = "azure_ad"  # Identity
    OKTA = "okta"  # Identity
    AWS = "aws"  # Cloud inventory
    GCP = "gcp"  # Cloud inventory
    CUSTOM = "custom"  # Custom data source


@dataclass
class UserGoal:
    """User's stated goal for the playbook execution"""
    goal_type: UserGoalType
    description: str
    target_frameworks: List[ComplianceFramework] = field(default_factory=list)
    target_features: List[str] = field(default_factory=list)
    target_tables: List[str] = field(default_factory=list)
    data_sources: List[DataSourceType] = field(default_factory=list)
    audit_context: Optional[str] = None  # e.g., "Vanta SOC2 audit finding XYZ"
    priority: str = "medium"  # low, medium, high, critical
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerOutput:
    """Output from the playbook planner"""
    selected_playbook: str  # Playbook markdown file path or ID
    playbook_content: str  # Raw markdown content
    mapped_lanes: List[Dict[str, Any]]  # Lanes relevant to the goal
    execution_plan: List[str]  # Ordered list of steps
    required_data_sources: List[DataSourceType]
    target_frameworks: List[ComplianceFramework]
    estimated_outputs: List[str]  # Expected output tables/features
    reasoning: str  # Explanation of planning decisions
    confidence: float  # Confidence in the plan (0-1)
    human_checkpoints: List[int]  # Lane IDs requiring human approval


# ============================================================================
# PLAYBOOK MARKDOWN PATHS
# ============================================================================

PLAYBOOK_MARKDOWN_PATHS = {
    "cornerstone": "genieml/data/cvedata/playbooks/cornerstone_playbook.md",
    "snyk": "genieml/data/cvedata/playbooks/snyk_silver_tables.md",
}

# Map data sources to playbooks
DATA_SOURCE_TO_PLAYBOOK = {
    DataSourceType.CORNERSTONE: "cornerstone",
    DataSourceType.SNYK: "snyk",
    DataSourceType.CROWDSTRIKE: "snyk",  # Uses similar asset risk pipeline
    DataSourceType.QUALYS: "snyk",  # Uses similar vulnerability pipeline
    DataSourceType.VANTA: "snyk",  # Compliance issues often relate to asset risk
}

# Map goal types to relevant lane types
GOAL_TO_LANE_TYPES = {
    UserGoalType.ADD_FEATURES: [LaneType.SILVER_FEATURES, LaneType.RISK_SCORING],
    UserGoalType.COMPLIANCE_AUDIT: [LaneType.COMPLIANCE, LaneType.DELIVERY, LaneType.RISK_SCORING],
    UserGoalType.RISK_ANALYSIS: [LaneType.RISK_SCORING, LaneType.SILVER_FEATURES, LaneType.TIME_SERIES],
    UserGoalType.EVIDENCE_GENERATION: [LaneType.COMPLIANCE, LaneType.DELIVERY],
    UserGoalType.DATA_INGESTION: [LaneType.INGESTION, LaneType.ASSETIZATION, LaneType.NORMALIZATION],
    UserGoalType.INVESTIGATION: [LaneType.SILVER_FEATURES, LaneType.RISK_SCORING, LaneType.COMPLIANCE],
}


# ============================================================================
# PLAYBOOK MARKDOWN PARSER
# ============================================================================

@dataclass
class ParsedLane:
    """Lane parsed from playbook markdown"""
    lane_id: int
    name: str
    description: str
    agent_name: Optional[str] = None
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    lane_type: Optional[LaneType] = None
    raw_content: str = ""


@dataclass
class ParsedPlaybook:
    """Playbook parsed from markdown"""
    title: str
    purpose: str
    lanes: List[ParsedLane]
    canonical_tables: Dict[str, List[str]]  # bronze/silver tables
    guardrails: Dict[str, Any]
    source_references: List[str]
    raw_content: str


class PlaybookMarkdownParser:
    """
    Parses playbook markdown files into structured format.
    
    Extracts:
    - Lane definitions (Lane 0, Lane 1, etc.)
    - Agent names
    - Input/output tables
    - Guardrails and constraints
    """
    
    def __init__(self):
        self.lane_pattern = r"#\s*Lane\s+(\d+)\s*[—–-]\s*(.+?)(?:\n|$)"
        self.agent_pattern = r"\*\*Agent:\*\*\s*`?([^`\n]+)`?"
        self.outputs_pattern = r"\*\*Output[s]?\s*(?:Table[s]?)?\*\*[:\s]*\n?((?:[-*]\s*`?[^`\n]+`?\n?)+)"
        self.inputs_pattern = r"\*\*Input[s]?\*\*[:\s]*\n?((?:[-*]\s*`?[^`\n]+`?\n?)+)"
    
    def parse(self, markdown_content: str) -> ParsedPlaybook:
        """Parse playbook markdown into structured format"""
        import re
        
        # Extract title (first # heading)
        title_match = re.search(r"^#\s+(.+?)$", markdown_content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Unknown Playbook"
        
        # Extract purpose section
        purpose_match = re.search(r"##\s*Purpose\s*\n([\s\S]*?)(?=\n##|\n#\s|$)", markdown_content)
        purpose = purpose_match.group(1).strip() if purpose_match else ""
        
        # Extract lanes
        lanes = self._extract_lanes(markdown_content)
        
        # Extract canonical tables
        canonical_tables = self._extract_tables(markdown_content)
        
        # Extract guardrails
        guardrails = self._extract_guardrails(markdown_content)
        
        # Extract source references
        source_refs = self._extract_source_references(markdown_content)
        
        return ParsedPlaybook(
            title=title,
            purpose=purpose,
            lanes=lanes,
            canonical_tables=canonical_tables,
            guardrails=guardrails,
            source_references=source_refs,
            raw_content=markdown_content
        )
    
    def _extract_lanes(self, content: str) -> List[ParsedLane]:
        """Extract lane definitions from markdown"""
        import re
        
        lanes = []
        
        # Find all lane headers
        lane_headers = list(re.finditer(self.lane_pattern, content, re.IGNORECASE))
        
        for i, match in enumerate(lane_headers):
            lane_id = int(match.group(1))
            lane_name = match.group(2).strip()
            
            # Get content until next lane or end
            start = match.end()
            end = lane_headers[i + 1].start() if i + 1 < len(lane_headers) else len(content)
            lane_content = content[start:end]
            
            # Extract agent name
            agent_match = re.search(self.agent_pattern, lane_content)
            agent_name = agent_match.group(1).strip() if agent_match else None
            
            # Extract description (first paragraph after header)
            desc_match = re.search(r"\*\*Goal:\*\*\s*(.+?)(?:\n|$)", lane_content)
            description = desc_match.group(1).strip() if desc_match else ""
            
            # Extract inputs
            inputs = self._extract_list_items(lane_content, "Input")
            
            # Extract outputs
            outputs = self._extract_list_items(lane_content, "Output")
            
            # Determine lane type from name
            lane_type = self._infer_lane_type(lane_name, lane_content)
            
            lanes.append(ParsedLane(
                lane_id=lane_id,
                name=lane_name,
                description=description,
                agent_name=agent_name,
                inputs=inputs,
                outputs=outputs,
                lane_type=lane_type,
                raw_content=lane_content
            ))
        
        return lanes
    
    def _extract_list_items(self, content: str, section_name: str) -> List[str]:
        """Extract list items from a section"""
        import re
        
        pattern = rf"\*\*{section_name}[s]?\s*(?:Table[s]?)?\*\*[:\s]*\n?((?:[-*]\s*`?[^`\n]+`?\n?)+)"
        match = re.search(pattern, content, re.IGNORECASE)
        
        if not match:
            return []
        
        items = []
        for line in match.group(1).split("\n"):
            line = line.strip()
            if line.startswith(("-", "*")):
                item = line.lstrip("-* ").strip("`").strip()
                if item:
                    items.append(item)
        
        return items
    
    def _extract_tables(self, content: str) -> Dict[str, List[str]]:
        """Extract canonical table definitions"""
        import re
        
        tables = {"bronze": [], "silver": []}
        
        # Look for Bronze/Silver sections
        bronze_match = re.search(r"\*\*Bronze[^*]*\*\*\s*\n((?:[-*]\s*`?[^`\n]+`?\n?)+)", content)
        if bronze_match:
            for line in bronze_match.group(1).split("\n"):
                line = line.strip()
                if line.startswith(("-", "*")):
                    table = line.lstrip("-* ").strip("`").strip()
                    if table:
                        tables["bronze"].append(table)
        
        silver_match = re.search(r"\*\*Silver[^*]*\*\*\s*\n((?:[-*]\s*`?[^`\n]+`?\n?)+)", content)
        if silver_match:
            for line in silver_match.group(1).split("\n"):
                line = line.strip()
                if line.startswith(("-", "*")):
                    table = line.lstrip("-* ").strip("`").strip()
                    if table:
                        tables["silver"].append(table)
        
        return tables
    
    def _extract_guardrails(self, content: str) -> Dict[str, Any]:
        """Extract guardrails/constraints section"""
        import re
        
        guardrails = {
            "silver_only": True,
            "allowed": [],
            "avoid": []
        }
        
        # Look for guardrails section
        guardrails_match = re.search(
            r"(?:Guardrails|silver-only|constraints)[:\s]*\n([\s\S]*?)(?=\n##|\n#\s|$)",
            content, re.IGNORECASE
        )
        
        if guardrails_match:
            section = guardrails_match.group(1)
            
            # Extract allowed items
            allowed_match = re.search(r"(?:✅\s*OK|allowed)[:\s]*\n((?:[-*]\s*[^\n]+\n?)+)", section, re.IGNORECASE)
            if allowed_match:
                for line in allowed_match.group(1).split("\n"):
                    line = line.strip()
                    if line.startswith(("-", "*")):
                        guardrails["allowed"].append(line.lstrip("-* ").strip())
            
            # Extract avoid items
            avoid_match = re.search(r"(?:⛔\s*Avoid|avoid)[:\s]*\n((?:[-*]\s*[^\n]+\n?)+)", section, re.IGNORECASE)
            if avoid_match:
                for line in avoid_match.group(1).split("\n"):
                    line = line.strip()
                    if line.startswith(("-", "*")):
                        guardrails["avoid"].append(line.lstrip("-* ").strip())
        
        return guardrails
    
    def _extract_source_references(self, content: str) -> List[str]:
        """Extract source references"""
        import re
        
        refs = []
        refs_match = re.search(r"(?:Source\s*references|Source)[:\s]*\n((?:[-*]\s*[^\n]+\n?)+)", content, re.IGNORECASE)
        
        if refs_match:
            for line in refs_match.group(1).split("\n"):
                line = line.strip()
                if line.startswith(("-", "*")):
                    refs.append(line.lstrip("-* ").strip())
        
        return refs
    
    def _infer_lane_type(self, lane_name: str, content: str) -> Optional[LaneType]:
        """Infer lane type from name and content"""
        name_lower = lane_name.lower()
        content_lower = content.lower()
        
        if "bootstrap" in name_lower or "schema" in name_lower:
            return LaneType.BOOTSTRAP
        elif "ingestion" in name_lower or "bronze" in name_lower:
            return LaneType.INGESTION
        elif "assetization" in name_lower or "asset" in name_lower and "identity" in content_lower:
            return LaneType.ASSETIZATION
        elif "monitoring" in name_lower or "agent" in name_lower and "evidence" in name_lower:
            return LaneType.MONITORING
        elif "normalization" in name_lower or "enrichment" in name_lower:
            return LaneType.NORMALIZATION
        elif "silver" in name_lower or "feature" in name_lower:
            return LaneType.SILVER_FEATURES
        elif "risk" in name_lower or "impact" in name_lower or "likelihood" in name_lower:
            return LaneType.RISK_SCORING
        elif "time series" in name_lower or "snapshot" in name_lower:
            return LaneType.TIME_SERIES
        elif "compliance" in name_lower or "control" in name_lower and "evaluation" in content_lower:
            return LaneType.COMPLIANCE
        elif "delivery" in name_lower or "evidence" in name_lower and "packaging" in content_lower:
            return LaneType.DELIVERY
        
        return None


# ============================================================================
# PLAYBOOK PLANNER
# ============================================================================

class PlaybookPlanner:
    """
    Plans playbook execution based on user goals.
    
    Flow:
    1. Parse user goal/intent
    2. Select appropriate playbook based on data sources
    3. Load and parse playbook markdown
    4. Map user goals to relevant lanes
    5. Generate execution plan with human checkpoints
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        playbook_base_path: str = ""
    ):
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0.1)
        self.parser = PlaybookMarkdownParser()
        self.playbook_base_path = playbook_base_path
        self._playbook_cache: Dict[str, ParsedPlaybook] = {}
    
    async def plan(
        self,
        user_goal: UserGoal,
        available_playbooks: Optional[List[str]] = None
    ) -> PlannerOutput:
        """
        Generate execution plan from user goal.
        
        Args:
            user_goal: User's stated goal
            available_playbooks: List of available playbook IDs (defaults to all)
            
        Returns:
            PlannerOutput with selected playbook and mapped lanes
        """
        # Step 1: Select playbook based on data sources
        selected_playbook = self._select_playbook(user_goal, available_playbooks)
        
        # Step 2: Load and parse playbook
        playbook_content = self._load_playbook(selected_playbook)
        parsed_playbook = self.parser.parse(playbook_content)
        
        # Step 3: Map goal to relevant lanes
        mapped_lanes = self._map_goal_to_lanes(user_goal, parsed_playbook)
        
        # Step 4: Generate execution plan
        execution_plan = self._generate_execution_plan(user_goal, mapped_lanes, parsed_playbook)
        
        # Step 5: Identify human checkpoints
        human_checkpoints = self._identify_checkpoints(user_goal, mapped_lanes)
        
        # Step 6: Estimate outputs
        estimated_outputs = self._estimate_outputs(mapped_lanes, parsed_playbook)
        
        # Step 7: Generate reasoning
        reasoning = await self._generate_reasoning(user_goal, parsed_playbook, mapped_lanes)
        
        return PlannerOutput(
            selected_playbook=selected_playbook,
            playbook_content=playbook_content,
            mapped_lanes=[self._lane_to_dict(lane) for lane in mapped_lanes],
            execution_plan=execution_plan,
            required_data_sources=user_goal.data_sources,
            target_frameworks=user_goal.target_frameworks,
            estimated_outputs=estimated_outputs,
            reasoning=reasoning,
            confidence=self._calculate_confidence(user_goal, mapped_lanes),
            human_checkpoints=human_checkpoints
        )
    
    def _select_playbook(
        self,
        user_goal: UserGoal,
        available_playbooks: Optional[List[str]] = None
    ) -> str:
        """Select appropriate playbook based on data sources and goal"""
        available = available_playbooks or list(PLAYBOOK_MARKDOWN_PATHS.keys())
        
        # Check data sources first
        for data_source in user_goal.data_sources:
            if data_source in DATA_SOURCE_TO_PLAYBOOK:
                playbook = DATA_SOURCE_TO_PLAYBOOK[data_source]
                if playbook in available:
                    return playbook
        
        # Default based on goal type
        if user_goal.goal_type == UserGoalType.ADD_FEATURES:
            # Check target tables/features to determine playbook
            target_lower = " ".join(user_goal.target_tables + user_goal.target_features).lower()
            if "training" in target_lower or "person" in target_lower or "hr" in target_lower:
                return "cornerstone"
            else:
                return "snyk"
        
        # Default based on audit context
        if user_goal.audit_context:
            audit_lower = user_goal.audit_context.lower()
            if "training" in audit_lower or "awareness" in audit_lower:
                return "cornerstone"
            else:
                return "snyk"
        
        # Default to snyk for general security/risk
        return "snyk" if "snyk" in available else available[0]
    
    def _load_playbook(self, playbook_id: str) -> str:
        """Load playbook markdown content"""
        import os
        
        if playbook_id in self._playbook_cache:
            return self._playbook_cache[playbook_id].raw_content
        
        path = PLAYBOOK_MARKDOWN_PATHS.get(playbook_id)
        if not path:
            raise ValueError(f"Unknown playbook: {playbook_id}")
        
        full_path = os.path.join(self.playbook_base_path, path) if self.playbook_base_path else path
        
        try:
            with open(full_path, "r") as f:
                content = f.read()
            return content
        except FileNotFoundError:
            logger.warning(f"Playbook file not found: {full_path}")
            # Return empty content - will be handled by caller
            return ""
    
    def _map_goal_to_lanes(
        self,
        user_goal: UserGoal,
        parsed_playbook: ParsedPlaybook
    ) -> List[ParsedLane]:
        """Map user goal to relevant lanes in the playbook"""
        relevant_lane_types = GOAL_TO_LANE_TYPES.get(user_goal.goal_type, [])
        
        # Always include bootstrap
        if LaneType.BOOTSTRAP not in relevant_lane_types:
            relevant_lane_types = [LaneType.BOOTSTRAP] + list(relevant_lane_types)
        
        # Filter lanes by type
        mapped_lanes = []
        for lane in parsed_playbook.lanes:
            if lane.lane_type in relevant_lane_types:
                mapped_lanes.append(lane)
            # Also include if lane outputs match target tables/features
            elif any(t in lane.outputs for t in user_goal.target_tables):
                mapped_lanes.append(lane)
            elif any(f in " ".join(lane.outputs).lower() for f in [f.lower() for f in user_goal.target_features]):
                mapped_lanes.append(lane)
        
        # Sort by lane_id to maintain order
        mapped_lanes.sort(key=lambda x: x.lane_id)
        
        # Include dependencies
        mapped_lanes = self._include_dependencies(mapped_lanes, parsed_playbook.lanes)
        
        return mapped_lanes
    
    def _include_dependencies(
        self,
        selected_lanes: List[ParsedLane],
        all_lanes: List[ParsedLane]
    ) -> List[ParsedLane]:
        """Include dependent lanes that are required for selected lanes"""
        selected_ids = {lane.lane_id for lane in selected_lanes}
        
        # For each selected lane, ensure all prior lanes are included
        # (simplified dependency: all lanes with lower IDs)
        min_id = min(selected_ids) if selected_ids else 0
        
        result = []
        for lane in all_lanes:
            if lane.lane_id in selected_ids or lane.lane_id < min_id:
                result.append(lane)
        
        result.sort(key=lambda x: x.lane_id)
        return result
    
    def _generate_execution_plan(
        self,
        user_goal: UserGoal,
        mapped_lanes: List[ParsedLane],
        parsed_playbook: ParsedPlaybook
    ) -> List[str]:
        """Generate ordered execution steps"""
        steps = []
        
        # Add goal context step
        steps.append(f"Goal: {user_goal.description}")
        
        if user_goal.target_frameworks:
            frameworks = ", ".join([f.value for f in user_goal.target_frameworks])
            steps.append(f"Target frameworks: {frameworks}")
        
        # Add lane execution steps
        for lane in mapped_lanes:
            step = f"Lane {lane.lane_id}: {lane.name}"
            if lane.agent_name:
                step += f" (Agent: {lane.agent_name})"
            steps.append(step)
            
            if lane.outputs:
                steps.append(f"  → Outputs: {', '.join(lane.outputs[:3])}")
        
        # Add guardrails reminder
        if parsed_playbook.guardrails.get("avoid"):
            steps.append(f"Guardrails: Avoid {', '.join(parsed_playbook.guardrails['avoid'][:2])}")
        
        return steps
    
    def _identify_checkpoints(
        self,
        user_goal: UserGoal,
        mapped_lanes: List[ParsedLane]
    ) -> List[int]:
        """Identify lanes requiring human approval"""
        checkpoints = []
        
        # High-priority goals require more checkpoints
        if user_goal.priority in ["high", "critical"]:
            # Checkpoint before risk scoring and compliance
            for lane in mapped_lanes:
                if lane.lane_type in [LaneType.RISK_SCORING, LaneType.COMPLIANCE, LaneType.DELIVERY]:
                    checkpoints.append(lane.lane_id)
        else:
            # Standard checkpoints: just before final output
            if mapped_lanes:
                checkpoints.append(mapped_lanes[-1].lane_id)
        
        return checkpoints
    
    def _estimate_outputs(
        self,
        mapped_lanes: List[ParsedLane],
        parsed_playbook: ParsedPlaybook
    ) -> List[str]:
        """Estimate expected outputs from the execution"""
        outputs = []
        
        for lane in mapped_lanes:
            outputs.extend(lane.outputs)
        
        return list(set(outputs))
    
    async def _generate_reasoning(
        self,
        user_goal: UserGoal,
        parsed_playbook: ParsedPlaybook,
        mapped_lanes: List[ParsedLane]
    ) -> str:
        """Generate reasoning for the planning decisions"""
        # Simple template-based reasoning
        reasoning_parts = []
        
        reasoning_parts.append(f"Selected playbook '{parsed_playbook.title}' based on:")
        
        if user_goal.data_sources:
            sources = ", ".join([s.value for s in user_goal.data_sources])
            reasoning_parts.append(f"  - Data sources: {sources}")
        
        if user_goal.target_frameworks:
            frameworks = ", ".join([f.value for f in user_goal.target_frameworks])
            reasoning_parts.append(f"  - Target frameworks: {frameworks}")
        
        reasoning_parts.append(f"\nMapped {len(mapped_lanes)} lanes for goal type '{user_goal.goal_type.value}':")
        
        for lane in mapped_lanes:
            reasoning_parts.append(f"  - Lane {lane.lane_id}: {lane.name} ({lane.lane_type.value if lane.lane_type else 'unknown'})")
        
        if parsed_playbook.guardrails.get("silver_only"):
            reasoning_parts.append("\nGuardrails applied: Silver-only (no gold aggregates)")
        
        return "\n".join(reasoning_parts)
    
    def _calculate_confidence(
        self,
        user_goal: UserGoal,
        mapped_lanes: List[ParsedLane]
    ) -> float:
        """Calculate confidence in the plan"""
        confidence = 0.5  # Base confidence
        
        # Higher confidence if data sources specified
        if user_goal.data_sources:
            confidence += 0.2
        
        # Higher confidence if target frameworks specified
        if user_goal.target_frameworks:
            confidence += 0.1
        
        # Higher confidence if more lanes mapped
        if len(mapped_lanes) >= 3:
            confidence += 0.1
        
        # Higher confidence if target tables/features specified
        if user_goal.target_tables or user_goal.target_features:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _lane_to_dict(self, lane: ParsedLane) -> Dict[str, Any]:
        """Convert ParsedLane to dictionary"""
        return {
            "lane_id": lane.lane_id,
            "name": lane.name,
            "description": lane.description,
            "agent_name": lane.agent_name,
            "inputs": lane.inputs,
            "outputs": lane.outputs,
            "lane_type": lane.lane_type.value if lane.lane_type else None,
        }
    
    def parse_user_input(self, user_input: str) -> UserGoal:
        """
        Parse natural language user input into a UserGoal.
        
        This is a simple heuristic parser. In production, use LLM.
        """
        input_lower = user_input.lower()
        
        # Detect goal type
        goal_type = UserGoalType.CUSTOM
        if "add feature" in input_lower or "new feature" in input_lower or "create feature" in input_lower:
            goal_type = UserGoalType.ADD_FEATURES
        elif "audit" in input_lower or "vanta" in input_lower or "finding" in input_lower:
            goal_type = UserGoalType.COMPLIANCE_AUDIT
        elif "risk" in input_lower or "vulnerability" in input_lower:
            goal_type = UserGoalType.RISK_ANALYSIS
        elif "evidence" in input_lower or "report" in input_lower:
            goal_type = UserGoalType.EVIDENCE_GENERATION
        elif "ingest" in input_lower or "import" in input_lower or "load" in input_lower:
            goal_type = UserGoalType.DATA_INGESTION
        elif "investigate" in input_lower or "why" in input_lower or "understand" in input_lower:
            goal_type = UserGoalType.INVESTIGATION
        
        # Detect frameworks
        frameworks = []
        if "soc2" in input_lower or "soc 2" in input_lower:
            frameworks.append(ComplianceFramework.SOC2)
        if "hipaa" in input_lower:
            frameworks.append(ComplianceFramework.HIPAA)
        if "iso" in input_lower or "27001" in input_lower:
            frameworks.append(ComplianceFramework.ISO_27001)
        if "pci" in input_lower:
            frameworks.append(ComplianceFramework.PCI_DSS)
        if "gdpr" in input_lower:
            frameworks.append(ComplianceFramework.GDPR)
        
        # Detect data sources
        data_sources = []
        if "snyk" in input_lower:
            data_sources.append(DataSourceType.SNYK)
        if "cornerstone" in input_lower or "training" in input_lower or "lms" in input_lower:
            data_sources.append(DataSourceType.CORNERSTONE)
        if "crowdstrike" in input_lower:
            data_sources.append(DataSourceType.CROWDSTRIKE)
        if "vanta" in input_lower:
            data_sources.append(DataSourceType.VANTA)
        
        # Detect priority
        priority = "medium"
        if "urgent" in input_lower or "critical" in input_lower or "asap" in input_lower:
            priority = "critical"
        elif "high" in input_lower or "important" in input_lower:
            priority = "high"
        elif "low" in input_lower:
            priority = "low"
        
        # Extract audit context if present
        audit_context = None
        if "vanta" in input_lower:
            audit_context = user_input  # Full input as context for audit-related goals
        
        return UserGoal(
            goal_type=goal_type,
            description=user_input,
            target_frameworks=frameworks,
            data_sources=data_sources,
            audit_context=audit_context,
            priority=priority
        )


# ============================================================================
# LEGACY PLAYBOOK REGISTRY (for backward compatibility)
# ============================================================================

# These are kept for backward compatibility but will use markdown parsing
PLAYBOOK_REGISTRY: Dict[str, str] = PLAYBOOK_MARKDOWN_PATHS.copy()

# Global planner instance
_playbook_planner: Optional[PlaybookPlanner] = None


def get_playbook_planner() -> PlaybookPlanner:
    """Get or create the global playbook planner"""
    global _playbook_planner
    if _playbook_planner is None:
        _playbook_planner = PlaybookPlanner()
    return _playbook_planner


def get_playbook_definition(playbook_type: str) -> ParsedPlaybook:
    """
    Get playbook definition by type.
    
    Returns a ParsedPlaybook from the markdown file.
    """
    if playbook_type not in PLAYBOOK_REGISTRY:
        raise ValueError(f"Unknown playbook type: {playbook_type}. Available: {list(PLAYBOOK_REGISTRY.keys())}")
    
    planner = get_playbook_planner()
    content = planner._load_playbook(playbook_type)
    return planner.parser.parse(content)


def get_playbook_path(playbook_type: str) -> str:
    """Get the markdown file path for a playbook"""
    if playbook_type not in PLAYBOOK_MARKDOWN_PATHS:
        raise ValueError(f"Unknown playbook type: {playbook_type}. Available: {list(PLAYBOOK_MARKDOWN_PATHS.keys())}")
    return PLAYBOOK_MARKDOWN_PATHS[playbook_type]


async def plan_from_user_input(
    user_input: str,
    available_playbooks: Optional[List[str]] = None
) -> PlannerOutput:
    """
    Create an execution plan from natural language user input.
    
    Examples:
        - "Add SOC2 compliance features to asset tables using Snyk data"
        - "Understand why Vanta is reporting SOC2 audit issues with training compliance"
        - "Analyze security risk for ISO 27001 using vulnerability data"
    
    Args:
        user_input: Natural language description of the goal
        available_playbooks: Optional list of playbook IDs to consider
        
    Returns:
        PlannerOutput with selected playbook, mapped lanes, and execution plan
    """
    planner = get_playbook_planner()
    user_goal = planner.parse_user_input(user_input)
    return await planner.plan(user_goal, available_playbooks)


# ============================================================================
# PLAYBOOK EXECUTION NODES
# ============================================================================

class PlaybookNodeBase:
    """Base class for playbook execution nodes"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    def _build_state_update(
        self,
        state: Dict[str, Any],
        required_fields: List[str],
        optional_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Build state update with only modified fields"""
        result = {}
        for field in required_fields:
            if field in state:
                result[field] = state[field]
        
        if optional_fields:
            for field in optional_fields:
                if field in state and state[field] is not None:
                    value = state[field]
                    if isinstance(value, (list, dict)) and len(value) == 0:
                        continue
                    result[field] = value
        
        return result


class PlaybookInitializationNode(PlaybookNodeBase):
    """Node that initializes playbook execution"""
    
    def __init__(
        self,
        transform_agent: "PlaybookDrivenTransformAgent",
        llm: Optional[ChatOpenAI] = None
    ):
        super().__init__(llm)
        self.transform_agent = transform_agent
    
    async def __call__(self, state: PlaybookExecutionState) -> PlaybookExecutionState:
        """Initialize playbook execution"""
        logger.info("PlaybookInitializationNode: Starting execution")
        
        playbook_type = state.get("playbook_type", "generic")
        project_id = state.get("project_id")
        
        try:
            # Get playbook definition
            playbook = get_playbook_definition(playbook_type)
            
            # Initialize execution state
            state["execution_id"] = str(uuid.uuid4())
            state["playbook_id"] = playbook.playbook_id
            state["domain"] = playbook.domain
            state["current_lane_id"] = 0
            state["completed_lanes"] = []
            state["failed_lanes"] = []
            state["skipped_lanes"] = []
            state["pending_approval"] = False
            state["start_time"] = datetime.utcnow().isoformat()
            state["lane_metrics"] = {}
            state["total_records_processed"] = 0
            
            # Initialize data stores
            state["bronze_tables"] = {}
            state["silver_features"] = {}
            state["risk_scores"] = {}
            state["time_series_snapshots"] = {}
            state["compliance_evidence"] = {}
            state["generated_sql"] = []
            state["executed_sql"] = []
            state["sql_errors"] = []
            
            # Get domain configuration
            domain_config = get_domain_config(playbook.domain)
            
            # Load knowledge context and initial schemas from Chroma
            if project_id and self.transform_agent.retrieval_helper:
                knowledge_context = await self._load_knowledge_context(
                    project_id=project_id,
                    domain=playbook.domain,
                    frameworks=playbook.compliance_frameworks
                )
                state["knowledge_context"] = knowledge_context
                
                # Pre-fetch available tables for this domain from Chroma
                all_domain_tables = get_all_tables_for_domain(playbook.domain)
                logger.info(f"Domain {playbook.domain} has {len(all_domain_tables)} defined tables")
            
            state["current_node"] = "initialization"
            state["next_node"] = "lane_router"
            state["status"] = "initialized"
            
            logger.info(f"Playbook initialized: {playbook.name} with {len(playbook.lanes)} lanes")
            
            # Add initialization message
            messages = list(state.get("messages", []))
            messages.append(AIMessage(content=f"Initialized playbook: {playbook.name}\n"
                                              f"Execution ID: {state['execution_id']}\n"
                                              f"Domain: {playbook.domain}\n"
                                              f"Lanes to execute: {len(playbook.lanes)}"))
            state["messages"] = messages
            
        except Exception as e:
            logger.error(f"Error initializing playbook: {e}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["next_node"] = "finalize"
        
        return state
    
    async def _load_knowledge_context(
        self,
        project_id: str,
        domain: str,
        frameworks: List[str]
    ) -> Dict[str, Any]:
        """Load knowledge context for the playbook"""
        knowledge_context = {
            "domain": domain,
            "frameworks": frameworks,
            "instructions": [],
            "sql_pairs": [],
            "playbook_knowledge": []
        }
        
        try:
            # Retrieve relevant instructions
            instructions_result = await self.transform_agent.retrieval_helper.get_instructions(
                query=f"{domain} compliance playbook",
                project_id=project_id,
                similarity_threshold=0.3,
                top_k=10
            )
            knowledge_context["instructions"] = instructions_result.get("documents", [])
            
            # Load compliance metric library
            try:
                metrics_library = get_compliance_metric_library(domain)
                knowledge_context["metrics_library"] = metrics_library.dict()
            except ValueError:
                pass
            
        except Exception as e:
            logger.warning(f"Error loading knowledge context: {e}")
        
        return knowledge_context


class LaneRouterNode(PlaybookNodeBase):
    """Node that routes to the appropriate lane or approval checkpoint"""
    
    async def __call__(self, state: PlaybookExecutionState) -> PlaybookExecutionState:
        """Route to next lane or approval checkpoint"""
        logger.info("LaneRouterNode: Determining next step")
        
        playbook_type = state.get("playbook_type", "generic")
        current_lane_id = state.get("current_lane_id", 0)
        completed_lanes = state.get("completed_lanes", [])
        pending_approval = state.get("pending_approval", False)
        
        try:
            playbook = get_playbook_definition(playbook_type)
            
            # Check if waiting for approval
            if pending_approval:
                approval_status = state.get("approval_status", ApprovalStatus.PENDING.value)
                if approval_status == ApprovalStatus.PENDING.value:
                    state["next_node"] = "human_approval"
                    return state
                elif approval_status == ApprovalStatus.REJECTED.value:
                    state["status"] = "rejected"
                    state["next_node"] = "finalize"
                    return state
                else:
                    # Approved or skipped, continue
                    state["pending_approval"] = False
            
            # Find next lane to execute
            next_lane = None
            for lane in playbook.lanes:
                if lane.lane_id in completed_lanes:
                    continue
                
                # Check dependencies
                deps_satisfied = all(dep in completed_lanes for dep in lane.dependencies)
                if deps_satisfied:
                    next_lane = lane
                    break
            
            if next_lane is None:
                # All lanes completed
                state["status"] = "completed"
                state["next_node"] = "finalize"
                logger.info("All lanes completed")
            else:
                state["current_lane_id"] = next_lane.lane_id
                state["current_lane_type"] = next_lane.lane_type.value
                
                # Check if approval is required
                if next_lane.requires_approval:
                    state["pending_approval"] = True
                    state["approval_status"] = ApprovalStatus.PENDING.value
                    state["approval_request"] = {
                        "lane_id": next_lane.lane_id,
                        "lane_name": next_lane.name,
                        "message": next_lane.approval_message,
                        "inputs": next_lane.inputs,
                        "outputs": next_lane.outputs
                    }
                    state["next_node"] = "human_approval"
                else:
                    state["next_node"] = "lane_executor"
                
                logger.info(f"Routing to lane {next_lane.lane_id}: {next_lane.name}")
            
            state["current_node"] = "lane_router"
            
        except Exception as e:
            logger.error(f"Error in lane router: {e}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["next_node"] = "finalize"
        
        return state


class HumanApprovalNode(PlaybookNodeBase):
    """Node that handles human-in-the-loop approval checkpoints"""
    
    def __init__(
        self,
        approval_callback: Optional[Callable[[Dict[str, Any]], asyncio.Future]] = None,
        auto_approve: bool = False,
        llm: Optional[ChatOpenAI] = None
    ):
        super().__init__(llm)
        self.approval_callback = approval_callback
        self.auto_approve = auto_approve
    
    async def __call__(self, state: PlaybookExecutionState) -> PlaybookExecutionState:
        """Handle human approval checkpoint"""
        logger.info("HumanApprovalNode: Waiting for approval")
        
        approval_request = state.get("approval_request", {})
        lane_name = approval_request.get("lane_name", "Unknown")
        
        try:
            if self.auto_approve:
                # Auto-approve for testing/automation
                logger.info(f"Auto-approving lane: {lane_name}")
                state["approval_status"] = ApprovalStatus.APPROVED.value
                state["approval_response"] = {
                    "approved": True,
                    "auto_approved": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
            elif self.approval_callback:
                # Use callback for approval
                try:
                    future = self.approval_callback(approval_request)
                    response = await future
                    state["approval_status"] = (
                        ApprovalStatus.APPROVED.value if response.get("approved")
                        else ApprovalStatus.REJECTED.value
                    )
                    state["approval_response"] = response
                except asyncio.TimeoutError:
                    logger.warning(f"Approval timeout for lane: {lane_name}")
                    state["approval_status"] = ApprovalStatus.TIMEOUT.value
            else:
                # Default: approve (for demo/development)
                logger.info(f"No approval callback, auto-approving: {lane_name}")
                state["approval_status"] = ApprovalStatus.APPROVED.value
                state["approval_response"] = {
                    "approved": True,
                    "reason": "No approval callback configured",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            state["pending_approval"] = False
            state["current_node"] = "human_approval"
            state["next_node"] = "lane_router"
            
            # Add approval message
            messages = list(state.get("messages", []))
            status = state["approval_status"]
            messages.append(AIMessage(content=f"Approval checkpoint for '{lane_name}': {status}"))
            state["messages"] = messages
            
        except Exception as e:
            logger.error(f"Error in approval node: {e}", exc_info=True)
            state["approval_status"] = ApprovalStatus.REJECTED.value
            state["error"] = str(e)
            state["next_node"] = "lane_router"
        
        return state


class LaneExecutorNode(PlaybookNodeBase):
    """
    Node that executes a single lane using feature engineering agents.
    
    This node leverages the sophisticated feature engineering agents from
    feature_engineering_agent.py via LaneFeatureExecutor, providing:
    1. Consistent feature generation across all lane types
    2. Built-in support for impact/likelihood/risk features
    3. Control identification and compliance features
    4. Feature dependency tracking
    
    Uses NL feature generation from playbook_knowledge_helper for
    generating natural language questions that describe features to compute.
    These questions are then used by the feature engineering agents.
    """
    
    def __init__(
        self,
        transform_agent: "PlaybookDrivenTransformAgent",
        llm: Optional[ChatOpenAI] = None
    ):
        super().__init__(llm)
        self.transform_agent = transform_agent
        self.knowledge_helper = get_playbook_knowledge_helper()
        
        # Use NLFeatureGenerationAgent from playbook_knowledge_helper for question generation
        # This provides sophisticated prompt templates for generating NL questions
        self.nl_feature_agent = create_nl_feature_generation_agent(
            llm=self.llm,
            knowledge_helper=self.knowledge_helper
        )
        
        # Initialize feature executor for lane execution
        self.feature_executor = create_lane_feature_executor(
            llm=self.llm,
            retrieval_helper=transform_agent.retrieval_helper if transform_agent else None
        )
    
    async def __call__(self, state: PlaybookExecutionState) -> PlaybookExecutionState:
        """Execute the current lane"""
        current_lane_id = state.get("current_lane_id", 0)
        playbook_type = state.get("playbook_type", "generic")
        project_id = state.get("project_id")
        domain = state.get("domain", "")
        compliance_frameworks = state.get("compliance_frameworks", [])
        
        logger.info(f"LaneExecutorNode: Executing lane {current_lane_id}")
        
        start_time = datetime.utcnow()
        
        try:
            playbook = get_playbook_definition(playbook_type)
            lane = next((l for l in playbook.lanes if l.lane_id == current_lane_id), None)
            
            if not lane:
                raise ValueError(f"Lane {current_lane_id} not found in playbook")
            
            # Update compliance frameworks if not set
            if not compliance_frameworks:
                compliance_frameworks = playbook.compliance_frameworks
                state["compliance_frameworks"] = compliance_frameworks
            
            # Get lane inputs/outputs for question generation
            lane_inputs = lane.inputs if hasattr(lane, 'inputs') else []
            lane_outputs = lane.outputs if hasattr(lane, 'outputs') else []
            lane_desc = lane.description if hasattr(lane, 'description') else ""
            
            # Step 1: Generate NL questions using NLFeatureGenerationAgent from playbook_knowledge_helper
            # This uses the sophisticated prompt templates from that module
            logger.info(f"Generating NL feature questions for lane {current_lane_id} ({lane.name})")
            nl_result: NLFeatureGenerationResult = await self.nl_feature_agent.generate_nl_questions(
                lane_type=lane.lane_type,
                domain=domain,
                compliance_frameworks=compliance_frameworks,
                user_goal=lane_desc,
                lane_inputs=lane_inputs,
                lane_outputs=lane_outputs,
                research_context=None  # Will be generated by the agent
            )
            
            # Store reasoning plan from NL generation
            reasoning_plans = state.get("reasoning_plans", {})
            reasoning_plans[str(current_lane_id)] = {
                "lane_name": lane.name,
                "lane_type": lane.lane_type.value,
                "reasoning": nl_result.generation_reasoning,
                "quality_notes": nl_result.quality_notes,
                "timestamp": datetime.utcnow().isoformat()
            }
            state["reasoning_plans"] = reasoning_plans
            
            # Store generated NL questions
            lane_questions = state.get("lane_questions", {})
            nl_questions = state.get("nl_questions", [])
            
            if nl_result.questions:
                # Convert NLFeatureQuestion objects to dicts
                questions_dicts = []
                for q in nl_result.questions:
                    if isinstance(q, NLFeatureQuestion):
                        q_dict = {
                            "question": q.question,
                            "feature_name": q.feature_name,
                            "feature_type": q.feature_type,
                            "calculation_hint": q.calculation_hint,
                            "target_columns": q.target_columns,
                            "source_tables": q.source_tables,
                            "dependencies": q.dependencies,
                            "compliance_mapping": q.compliance_mapping,
                            "enum_lookup": q.enum_lookup,
                            "validation_rules": q.validation_rules,
                            "priority": q.priority,
                            "lane_id": current_lane_id,
                            "lane_name": lane.name,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        q_dict = q if isinstance(q, dict) else {"question": str(q)}
                        q_dict["lane_id"] = current_lane_id
                        q_dict["lane_name"] = lane.name
                    
                    questions_dicts.append(q_dict)
                    nl_questions.append(q_dict)
                
                lane_questions[str(current_lane_id)] = questions_dicts
                logger.info(f"Generated {len(questions_dicts)} NL feature questions for lane {current_lane_id}")
            
            state["lane_questions"] = lane_questions
            state["nl_questions"] = nl_questions
            
            # Step 2: Execute lane (retrieves schemas, generates additional context)
            result = await self._execute_lane(
                lane=lane,
                state=state,
                project_id=project_id
            )
            
            # Update state with results
            if result.get("success"):
                completed = state.get("completed_lanes", [])
                completed.append(current_lane_id)
                state["completed_lanes"] = completed
                
                # Store lane outputs
                if lane.lane_type == LaneType.INGESTION:
                    state["bronze_tables"].update(result.get("data", {}))
                elif lane.lane_type == LaneType.SILVER_FEATURES:
                    state["silver_features"].update(result.get("data", {}))
                elif lane.lane_type == LaneType.RISK_SCORING:
                    state["risk_scores"].update(result.get("data", {}))
                elif lane.lane_type == LaneType.TIME_SERIES:
                    state["time_series_snapshots"].update(result.get("data", {}))
                elif lane.lane_type == LaneType.COMPLIANCE:
                    state["compliance_evidence"].update(result.get("data", {}))
                
                # Store generated SQL (for future translation)
                if result.get("sql"):
                    generated = state.get("generated_sql", [])
                    generated.append({
                        "lane_id": current_lane_id,
                        "sql": result["sql"],
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    state["generated_sql"] = generated
                
                # Store feature definitions from knowledge context
                if result.get("features"):
                    feature_defs = state.get("feature_definitions", [])
                    feature_defs.extend(result["features"])
                    state["feature_definitions"] = feature_defs
            else:
                failed = state.get("failed_lanes", [])
                failed.append(current_lane_id)
                state["failed_lanes"] = failed
                errors = state.get("sql_errors", [])
                errors.append({
                    "lane_id": current_lane_id,
                    "error": result.get("error"),
                    "timestamp": datetime.utcnow().isoformat()
                })
                state["sql_errors"] = errors
            
            # Record metrics
            end_time = datetime.utcnow()
            lane_metrics = state.get("lane_metrics", {})
            lane_metrics[str(current_lane_id)] = {
                "lane_name": lane.name,
                "duration_seconds": (end_time - start_time).total_seconds(),
                "success": result.get("success"),
                "records_processed": result.get("records_processed", 0),
                "questions_generated": len(lane_questions.get(str(current_lane_id), []))
            }
            state["lane_metrics"] = lane_metrics
            
            state["current_node"] = "lane_executor"
            state["next_node"] = "lane_router"
            
            # Add execution message
            messages = list(state.get("messages", []))
            status = "completed" if result.get("success") else "failed"
            questions_count = len(lane_questions.get(str(current_lane_id), []))
            messages.append(AIMessage(
                content=f"Lane {current_lane_id} ({lane.name}): {status}\n"
                        f"Generated {questions_count} natural language questions for SQL translation."
            ))
            state["messages"] = messages
            
        except Exception as e:
            logger.error(f"Error executing lane {current_lane_id}: {e}", exc_info=True)
            failed = state.get("failed_lanes", [])
            failed.append(current_lane_id)
            state["failed_lanes"] = failed
            state["error"] = str(e)
            state["next_node"] = "lane_router"
        
        return state
    
    async def _execute_lane(
        self,
        lane: LaneDefinition,
        state: PlaybookExecutionState,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Execute a lane using feature engineering agents.
        
        This method leverages the LaneFeatureExecutor to use sophisticated
        feature engineering agents from feature_engineering_agent.py, providing:
        1. Consistent feature generation across all lane types
        2. Built-in support for impact/likelihood/risk features
        3. Control identification and compliance features
        4. Feature dependency and relevance tracking
        """
        
        lane_type = lane.lane_type
        domain = state.get("domain", "")
        compliance_frameworks = state.get("compliance_frameworks", [])
        
        # Get knowledge context for this lane
        knowledge_context = self.knowledge_helper.get_knowledge_context(
            lane_type=lane_type,
            domain=domain,
            compliance_frameworks=compliance_frameworks
        )
        
        # Update state with knowledge context
        state["knowledge_context"] = {
            "features": knowledge_context.features,
            "examples": knowledge_context.examples,
            "instructions": knowledge_context.instructions,
            "compliance_info": knowledge_context.compliance_info
        }
        
        # Use feature executor for lanes that generate features
        feature_lanes = [
            LaneType.SILVER_FEATURES,
            LaneType.RISK_SCORING,
            LaneType.COMPLIANCE,
            LaneType.ASSETIZATION,
            LaneType.NORMALIZATION,
            LaneType.MONITORING
        ]
        
        if lane_type in feature_lanes:
            # Execute using feature engineering agents
            logger.info(f"Executing lane {lane.name} with feature engineering agents")
            
            result = await self.feature_executor.execute_lane(
                lane_type=lane_type,
                lane_definition=lane,
                playbook_state=dict(state),
                knowledge_context=knowledge_context
            )
            
            if result.get("success"):
                # Apply state updates from feature executor
                state_updates = result.get("state_updates", {})
                for key, value in state_updates.items():
                    if key in state:
                        if isinstance(state[key], dict) and isinstance(value, dict):
                            state[key].update(value)
                        else:
                            state[key] = value
                
                return {
                    "success": True,
                    "data": {
                        "features": result.get("features", []),
                        "calculation_plan": result.get("calculation_plan", {}),
                        "dependencies": result.get("dependencies", {}),
                    },
                    "features": result.get("features", []),
                    "reasoning": result.get("reasoning", ""),
                    "records_processed": len(result.get("features", []))
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Feature generation failed"),
                    "features": []
                }
        
        # For non-feature lanes, use simplified execution
        if lane_type == LaneType.BOOTSTRAP:
            result = await self._execute_bootstrap_lane(lane, state, project_id)
        elif lane_type == LaneType.INGESTION:
            result = await self._execute_ingestion_lane(lane, state, project_id)
        elif lane_type == LaneType.TIME_SERIES:
            result = await self._execute_time_series_lane(lane, state, project_id)
        elif lane_type == LaneType.DELIVERY:
            result = await self._execute_delivery_lane(lane, state, project_id)
        else:
            result = await self._execute_generic_lane(lane, state, project_id)
        
        # Add features from knowledge context to result
        result["features"] = knowledge_context.features
        
        return result
    
    async def _execute_bootstrap_lane(
        self,
        lane: LaneDefinition,
        state: PlaybookExecutionState,
        project_id: str
    ) -> Dict[str, Any]:
        """Execute bootstrap lane to load knowledge and schemas"""
        logger.info(f"Executing bootstrap lane: {lane.name}")
        
        try:
            # Retrieve unified context
            unified_context = await self.transform_agent._retrieve_unified_transform_context(
                query=f"Initialize {lane.name} with enum metadata and knowledge",
                project_id=project_id,
                knowledge=state.get("knowledge_context", {}).get("instructions", [])
            )
            
            state["schema_context"] = unified_context.get("schema_contexts", [])
            state["enum_metadata"] = {
                "tables": unified_context.get("table_names", []),
                "loaded": True
            }
            
            return {
                "success": True,
                "data": {
                    "schemas_loaded": len(unified_context.get("schema_contexts", [])),
                    "tables_found": unified_context.get("table_names", [])
                },
                "records_processed": len(unified_context.get("table_names", []))
            }
            
        except Exception as e:
            logger.error(f"Error in bootstrap lane: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_ingestion_lane(
        self,
        lane: LaneDefinition,
        state: PlaybookExecutionState,
        project_id: str
    ) -> Dict[str, Any]:
        """Execute data ingestion lane - retrieves bronze table schemas from Chroma"""
        logger.info(f"Executing ingestion lane: {lane.name}")
        
        try:
            domain = state.get("domain", "")
            
            # Get bronze tables for this domain from Chroma
            bronze_tables = get_tables_for_lane(domain, LaneType.INGESTION, state.get("playbook_type", ""))
            
            # Use retrieval helper to get schemas for bronze tables
            ingested_schemas = {}
            if self.transform_agent.retrieval_helper:
                # Build query to retrieve bronze table schemas
                bronze_query = f"Bronze ingestion tables for {domain}: {', '.join(lane.outputs)}"
                
                schema_result = await self.transform_agent.retrieval_helper.get_database_schemas(
                    project_id=project_id,
                    table_retrieval={
                        "table_retrieval_size": len(lane.outputs) + 5,
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": False
                    },
                    query=bronze_query,
                    tables=lane.outputs  # Request specific tables
                )
                
                # Process retrieved schemas
                for schema in schema_result.get("schemas", []):
                    if isinstance(schema, dict):
                        table_name = schema.get("table_name", "")
                        if table_name:
                            ingested_schemas[table_name] = {
                                "table_ddl": schema.get("table_ddl", ""),
                                "columns": schema.get("column_metadata", []),
                                "relationships": schema.get("relationships", [])
                            }
                
                logger.info(f"Retrieved {len(ingested_schemas)} bronze table schemas from Chroma")
            
            # Generate SQL for bronze table DDL (for reference/documentation)
            sql_statements = []
            for table_name in lane.outputs:
                if table_name in ingested_schemas:
                    ddl = ingested_schemas[table_name].get("table_ddl", "")
                    if ddl:
                        sql_statements.append(ddl)
                else:
                    # Generate placeholder DDL if table not found
                    sql_statements.append(self._generate_bronze_table_sql(table_name, {}))
            
            return {
                "success": True,
                "data": ingested_schemas,
                "sql": sql_statements,
                "records_processed": len(ingested_schemas),
                "tables_found": list(ingested_schemas.keys())
            }
            
        except Exception as e:
            logger.error(f"Error in ingestion lane: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_time_series_lane(
        self,
        lane: LaneDefinition,
        state: PlaybookExecutionState,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Execute time series snapshot lane.
        
        Generates snapshot features with timestamp, run_id, and version columns.
        This is a simpler lane that wraps silver features into time series records.
        """
        logger.info(f"Executing time series lane: {lane.name}")
        
        try:
            domain = state.get("domain", "cybersecurity")
            
            # Build time series features based on silver features
            silver_features = state.get("silver_features", {})
            ts_features = []
            
            # Generate snapshot feature definitions
            for output_table in lane.outputs:
                ts_features.append({
                    "name": f"{output_table}_snapshot",
                    "description": f"Time series snapshot of {output_table}",
                    "source_tables": lane.inputs,
                    "output_table": output_table,
                    "required_columns": ["snapshot_ts", "source_run_id", "feature_version"],
                    "feature_type": "time_series_snapshot"
                })
            
            return {
                "success": True,
                "data": {
                    "time_series_tables": lane.outputs,
                    "silver_features_count": len(silver_features),
                    "tables_used": lane.inputs + lane.outputs
                },
                "features": ts_features,
                "records_processed": len(ts_features)
            }
            
        except Exception as e:
            logger.error(f"Error in time series lane: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_delivery_lane(
        self,
        lane: LaneDefinition,
        state: PlaybookExecutionState,
        project_id: str
    ) -> Dict[str, Any]:
        """Execute evidence delivery lane"""
        logger.info(f"Executing delivery lane: {lane.name}")
        
        return {
            "success": True,
            "data": {
                "evidence_packages": lane.outputs,
                "delivery_timestamp": datetime.utcnow().isoformat()
            },
            "records_processed": 0
        }
    
    async def _execute_generic_lane(
        self,
        lane: LaneDefinition,
        state: PlaybookExecutionState,
        project_id: str
    ) -> Dict[str, Any]:
        """Execute generic lane"""
        logger.info(f"Executing generic lane: {lane.name}")
        
        try:
            generic_query = f"Execute {lane.name}: {lane.description}. "
            generic_query += f"Inputs: {', '.join(lane.inputs)}. Outputs: {', '.join(lane.outputs)}."
            
            result = await self.transform_agent.process_transform_request(
                query=generic_query,
                project_id=project_id
            )
            
            return {
                "success": result.get("success", False),
                "data": {"outputs": lane.outputs},
                "sql": result.get("data", {}).get("sql", "") if result.get("success") else "",
                "records_processed": 0
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _generate_bronze_table_sql(self, table_name: str, data: Dict[str, Any]) -> str:
        """Generate SQL for bronze table creation"""
        # This would generate actual DDL based on data structure
        return f"""
-- Bronze table: {table_name}
-- Auto-generated for playbook ingestion
CREATE TABLE IF NOT EXISTS {table_name} (
    id VARCHAR(255) PRIMARY KEY,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(100),
    source_record_id VARCHAR(255),
    raw_data JSONB
);
"""


class PlaybookFinalizeNode(PlaybookNodeBase):
    """Node that finalizes playbook execution"""
    
    async def __call__(self, state: PlaybookExecutionState) -> PlaybookExecutionState:
        """Finalize playbook execution"""
        logger.info("PlaybookFinalizeNode: Finalizing execution")
        
        state["end_time"] = datetime.utcnow().isoformat()
        
        # Build final output
        completed_lanes = state.get("completed_lanes", [])
        failed_lanes = state.get("failed_lanes", [])
        total_lanes = len(completed_lanes) + len(failed_lanes)
        
        state["final_output"] = {
            "execution_id": state.get("execution_id"),
            "playbook_id": state.get("playbook_id"),
            "status": state.get("status"),
            "summary": {
                "total_lanes": total_lanes,
                "completed_lanes": len(completed_lanes),
                "failed_lanes": len(failed_lanes),
                "success_rate": len(completed_lanes) / total_lanes if total_lanes > 0 else 0
            },
            "outputs": {
                "bronze_tables": list(state.get("bronze_tables", {}).keys()),
                "silver_features": list(state.get("silver_features", {}).keys()),
                "risk_scores": list(state.get("risk_scores", {}).keys()),
                "time_series": list(state.get("time_series_snapshots", {}).keys()),
                "compliance_evidence": list(state.get("compliance_evidence", {}).keys())
            },
            "generated_sql_count": len(state.get("generated_sql", [])),
            "lane_metrics": state.get("lane_metrics", {}),
            "duration_seconds": self._calculate_duration(
                state.get("start_time"),
                state.get("end_time")
            )
        }
        
        state["current_node"] = "finalize"
        state["next_node"] = None
        
        # Add final message
        messages = list(state.get("messages", []))
        output = state["final_output"]
        messages.append(AIMessage(
            content=f"Playbook execution completed.\n"
                    f"Status: {output['status']}\n"
                    f"Lanes: {output['summary']['completed_lanes']}/{output['summary']['total_lanes']} completed\n"
                    f"Duration: {output['duration_seconds']:.2f}s"
        ))
        state["messages"] = messages
        
        return state
    
    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """Calculate duration in seconds"""
        try:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)
            return (end - start).total_seconds()
        except:
            return 0.0


# ============================================================================
# NL QUESTION EXPORTER FOR DOWNSTREAM TRANSLATION
# ============================================================================

class NLQuestionExporter:
    """
    Exports natural language questions with metadata for downstream processing.
    
    Questions can be:
    1. Translated to SQL by SQL RAG agents
    2. Converted to dbt models
    3. Used for documentation generation
    """
    
    @staticmethod
    def export_questions_for_sql_translation(
        state: PlaybookExecutionState,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Export NL questions in format suitable for SQL translation.
        
        Args:
            state: Playbook execution state
            include_metadata: Whether to include calculation metadata
            
        Returns:
            List of questions ready for SQL translation
        """
        questions = []
        nl_questions = state.get("nl_questions", [])
        
        for q in nl_questions:
            export_q = {
                "question": q.get("question", ""),
                "intent": q.get("intent", "retrieve"),
                "source_tables": q.get("source_tables", []),
                "target_features": q.get("target_features", []),
                "compliance_framework": q.get("compliance_framework"),
                "priority": q.get("priority", 1),
                "lane_id": q.get("lane_id"),
                "lane_name": q.get("lane_name")
            }
            
            if include_metadata:
                export_q["enum_lookups"] = q.get("enum_lookups", [])
                export_q["calculation_metadata"] = q.get("calculation_metadata", {})
            
            questions.append(export_q)
        
        # Sort by priority and lane_id
        questions.sort(key=lambda x: (x.get("lane_id", 0), x.get("priority", 1)))
        
        return questions
    
    @staticmethod
    def export_questions_for_dbt(
        state: PlaybookExecutionState
    ) -> List[Dict[str, Any]]:
        """
        Export NL questions in format suitable for dbt model generation.
        
        Args:
            state: Playbook execution state
            
        Returns:
            List of questions with dbt-specific metadata
        """
        questions = []
        nl_questions = state.get("nl_questions", [])
        lane_questions = state.get("lane_questions", {})
        
        for lane_id, lane_qs in lane_questions.items():
            lane_group = {
                "lane_id": int(lane_id),
                "models": []
            }
            
            for q in lane_qs:
                model = {
                    "name": f"lane_{lane_id}_{q.get('intent', 'query')}",
                    "description": q.get("question", ""),
                    "source_tables": q.get("source_tables", []),
                    "target_features": q.get("target_features", []),
                    "compliance_framework": q.get("compliance_framework"),
                    "config": {
                        "materialized": "table" if q.get("intent") == "aggregate" else "view",
                        "tags": [q.get("compliance_framework")] if q.get("compliance_framework") else []
                    }
                }
                
                # Add calculation formula if available
                calc_meta = q.get("calculation_metadata", {})
                if calc_meta.get("formula"):
                    model["formula"] = calc_meta["formula"]
                if calc_meta.get("dependencies"):
                    model["dependencies"] = calc_meta["dependencies"]
                
                lane_group["models"].append(model)
            
            questions.append(lane_group)
        
        return questions
    
    @staticmethod
    def get_questions_summary(state: PlaybookExecutionState) -> Dict[str, Any]:
        """
        Get a summary of generated questions.
        
        Args:
            state: Playbook execution state
            
        Returns:
            Summary statistics
        """
        nl_questions = state.get("nl_questions", [])
        lane_questions = state.get("lane_questions", {})
        
        # Count by intent
        intent_counts = {}
        for q in nl_questions:
            intent = q.get("intent", "unknown")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Count by framework
        framework_counts = {}
        for q in nl_questions:
            framework = q.get("compliance_framework") or "general"
            framework_counts[framework] = framework_counts.get(framework, 0) + 1
        
        # Count by lane
        lane_counts = {
            lane_id: len(qs) for lane_id, qs in lane_questions.items()
        }
        
        return {
            "total_questions": len(nl_questions),
            "questions_by_intent": intent_counts,
            "questions_by_framework": framework_counts,
            "questions_by_lane": lane_counts,
            "lanes_with_questions": len(lane_questions),
            "frameworks_covered": list(set(
                q.get("compliance_framework") for q in nl_questions 
                if q.get("compliance_framework")
            )),
            "features_targeted": list(set(
                f for q in nl_questions for f in q.get("target_features", [])
            ))
        }
    
    @staticmethod
    def export_to_json(
        state: PlaybookExecutionState,
        include_reasoning: bool = True
    ) -> str:
        """
        Export all questions and context to JSON.
        
        Args:
            state: Playbook execution state
            include_reasoning: Whether to include reasoning plans
            
        Returns:
            JSON string with all questions and metadata
        """
        export_data = {
            "playbook_id": state.get("playbook_id"),
            "execution_id": state.get("execution_id"),
            "domain": state.get("domain"),
            "compliance_frameworks": state.get("compliance_frameworks", []),
            "questions": NLQuestionExporter.export_questions_for_sql_translation(state),
            "summary": NLQuestionExporter.get_questions_summary(state)
        }
        
        if include_reasoning:
            export_data["reasoning_plans"] = state.get("reasoning_plans", {})
        
        return json.dumps(export_data, indent=2, default=str)


# ============================================================================
# PLAYBOOK-DRIVEN TRANSFORM AGENT
# ============================================================================

class PlaybookDrivenTransformAgent(TransformSQLRAGAgent):
    """
    Enhanced Transform SQL RAG Agent with playbook-driven workflows.
    
    Supports:
    - Lane-based playbook execution (Cornerstone, Snyk, etc.)
    - Human-in-the-loop approval checkpoints
    - Contextual graph reasoning integration
    - Source connector abstraction
    """
    
    def __init__(
        self,
        llm,
        engine: Engine,
        embeddings=None,
        max_iterations: int = 5,
        document_store_provider: DocumentStoreProvider = None,
        retrieval_helper: RetrievalHelper = None,
        contextual_graph_service: Any = None,
        contextual_reasoning_pipeline: Any = None,
        approval_callback: Optional[Callable[[Dict[str, Any]], asyncio.Future]] = None,
        auto_approve: bool = False,
        **kwargs
    ):
        """Initialize Playbook-Driven Transform Agent
        
        Args:
            llm: Language model instance
            engine: Engine instance
            embeddings: Optional embeddings instance
            max_iterations: Maximum iterations for SQL generation
            document_store_provider: Optional document store provider
            retrieval_helper: Optional retrieval helper
            contextual_graph_service: Optional contextual graph service for reasoning
            contextual_reasoning_pipeline: Optional reasoning pipeline
            approval_callback: Callback for human-in-the-loop approvals
            auto_approve: Whether to auto-approve for testing
            **kwargs: Additional arguments
        """
        super().__init__(
            llm=llm,
            engine=engine,
            embeddings=embeddings,
            max_iterations=max_iterations,
            document_store_provider=document_store_provider,
            retrieval_helper=retrieval_helper,
            **kwargs
        )
        
        self.contextual_graph_service = contextual_graph_service
        self.contextual_reasoning_pipeline = contextual_reasoning_pipeline
        self.approval_callback = approval_callback
        self.auto_approve = auto_approve
        
        # Build playbook execution graph
        self._playbook_graph = self._build_playbook_graph()
    
    def _build_playbook_graph(self) -> StateGraph:
        """Build LangGraph for playbook execution"""
        workflow = StateGraph(PlaybookExecutionState)
        
        # Create nodes
        init_node = PlaybookInitializationNode(transform_agent=self, llm=self.llm)
        router_node = LaneRouterNode(llm=self.llm)
        approval_node = HumanApprovalNode(
            approval_callback=self.approval_callback,
            auto_approve=self.auto_approve,
            llm=self.llm
        )
        executor_node = LaneExecutorNode(transform_agent=self, llm=self.llm)
        finalize_node = PlaybookFinalizeNode(llm=self.llm)
        
        # Add nodes
        workflow.add_node("initialization", init_node)
        workflow.add_node("lane_router", router_node)
        workflow.add_node("human_approval", approval_node)
        workflow.add_node("lane_executor", executor_node)
        workflow.add_node("finalize", finalize_node)
        
        # Set entry point
        workflow.set_entry_point("initialization")
        
        # Add edges
        workflow.add_edge("initialization", "lane_router")
        
        # Conditional routing from lane_router
        workflow.add_conditional_edges(
            "lane_router",
            self._route_from_router,
            {
                "human_approval": "human_approval",
                "lane_executor": "lane_executor",
                "finalize": "finalize"
            }
        )
        
        # Human approval routes back to router
        workflow.add_edge("human_approval", "lane_router")
        
        # Lane executor routes back to router
        workflow.add_edge("lane_executor", "lane_router")
        
        # Finalize ends
        workflow.add_edge("finalize", END)
        
        # Compile with checkpointing
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    
    def _route_from_router(self, state: PlaybookExecutionState) -> str:
        """Determine routing from lane router"""
        next_node = state.get("next_node", "finalize")
        return next_node
    
    async def execute_playbook(
        self,
        playbook_type: str,
        project_id: str,
        thread_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a playbook workflow
        
        Args:
            playbook_type: Type of playbook ('cornerstone', 'snyk', etc.)
            project_id: Project ID for data retrieval
            thread_id: Thread ID for checkpointing (creates new if None)
            **kwargs: Additional arguments
            
        Returns:
            Final execution state and results
        """
        # Validate playbook type
        if playbook_type not in PLAYBOOK_REGISTRY:
            raise ValueError(f"Unknown playbook type: {playbook_type}. "
                           f"Available: {list(PLAYBOOK_REGISTRY.keys())}")
        
        # Determine domain from playbook type
        domain = "hr_compliance" if playbook_type == "cornerstone" else "cybersecurity"
        
        # Initialize state
        initial_state: PlaybookExecutionState = {
            "playbook_type": playbook_type,
            "project_id": project_id,
            "domain": domain,
            "messages": [],
            "status": "starting"
        }
        
        # Add any additional kwargs to state
        for key, value in kwargs.items():
            if key in PlaybookExecutionState.__annotations__:
                initial_state[key] = value
        
        # Create thread config
        config = {
            "configurable": {
                "thread_id": thread_id or str(uuid.uuid4())
            }
        }
        
        # Execute graph
        try:
            final_state = await self._playbook_graph.ainvoke(initial_state, config)
            
            return {
                "success": final_state.get("status") == "completed",
                "execution_id": final_state.get("execution_id"),
                "final_output": final_state.get("final_output"),
                "status": final_state.get("status"),
                "error": final_state.get("error"),
                "messages": [
                    msg.content if hasattr(msg, "content") else str(msg)
                    for msg in final_state.get("messages", [])
                ]
            }
            
        except Exception as e:
            logger.error(f"Error executing playbook: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }
    
    async def get_playbook_status(
        self,
        thread_id: str
    ) -> Dict[str, Any]:
        """
        Get status of a running/paused playbook execution
        
        Args:
            thread_id: Thread ID of the execution
            
        Returns:
            Current execution status
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            state = await self._playbook_graph.aget_state(config)
            
            if state and state.values:
                return {
                    "status": state.values.get("status"),
                    "current_lane": state.values.get("current_lane_id"),
                    "completed_lanes": state.values.get("completed_lanes", []),
                    "pending_approval": state.values.get("pending_approval"),
                    "approval_request": state.values.get("approval_request")
                }
            else:
                return {"status": "not_found"}
                
        except Exception as e:
            logger.error(f"Error getting playbook status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def resume_playbook(
        self,
        thread_id: str,
        approval_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resume a paused playbook execution
        
        Args:
            thread_id: Thread ID of the execution
            approval_response: Response to pending approval (if any)
            
        Returns:
            Final execution state
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            # Get current state
            state_snapshot = await self._playbook_graph.aget_state(config)
            
            if not state_snapshot or not state_snapshot.values:
                return {"success": False, "error": "Execution not found"}
            
            current_state = state_snapshot.values
            
            # Apply approval response if provided
            if approval_response and current_state.get("pending_approval"):
                current_state["approval_status"] = (
                    ApprovalStatus.APPROVED.value if approval_response.get("approved")
                    else ApprovalStatus.REJECTED.value
                )
                current_state["approval_response"] = approval_response
            
            # Resume execution
            final_state = await self._playbook_graph.ainvoke(current_state, config)
            
            return {
                "success": final_state.get("status") == "completed",
                "execution_id": final_state.get("execution_id"),
                "final_output": final_state.get("final_output"),
                "status": final_state.get("status")
            }
            
        except Exception as e:
            logger.error(f"Error resuming playbook: {e}")
            return {"success": False, "error": str(e)}
    
    def list_available_playbooks(self) -> List[Dict[str, Any]]:
        """List all available playbook definitions"""
        playbooks = []
        for playbook_id, path in PLAYBOOK_REGISTRY.items():
            try:
                parsed = get_playbook_definition(playbook_id)
                domain = "hr_compliance" if playbook_id == "cornerstone" else "cybersecurity"
                playbooks.append({
                    "playbook_id": playbook_id,
                    "name": parsed.title,
                    "description": parsed.purpose[:200] + "..." if len(parsed.purpose) > 200 else parsed.purpose,
                    "domain": domain,
                    "table_categories": list(parsed.canonical_tables.keys()) if parsed.canonical_tables else [],
                    "frameworks": ["SOC2", "HIPAA"],  # Default supported frameworks
                    "lanes_count": len(parsed.lanes)
                })
            except Exception as e:
                logger.warning(f"Could not load playbook {playbook_id}: {e}")
                playbooks.append({
                    "playbook_id": playbook_id,
                    "name": playbook_id,
                    "description": f"Playbook at {path}",
                    "domain": "unknown",
                    "table_categories": [],
                    "frameworks": [],
                    "lanes_count": 0
                })
        return playbooks
    
    def get_playbook_details(self, playbook_type: str) -> Dict[str, Any]:
        """Get detailed information about a playbook"""
        playbook = get_playbook_definition(playbook_type)
        domain = "hr_compliance" if playbook_type == "cornerstone" else "cybersecurity"
        
        # Collect all outputs from lanes
        all_outputs = []
        for lane in playbook.lanes:
            all_outputs.extend(lane.outputs)
        
        return {
            "playbook_id": playbook_type,
            "name": playbook.title,
            "description": playbook.purpose,
            "domain": domain,
            "table_categories": playbook.canonical_tables,
            "frameworks": ["SOC2", "HIPAA"],  # Default supported
            "output_tables": list(set(all_outputs)),
            "guardrails": playbook.guardrails,
            "source_references": playbook.source_references,
            "lanes": [
                {
                    "lane_id": lane.lane_id,
                    "lane_type": lane.lane_type.value if lane.lane_type else "unknown",
                    "name": lane.name,
                    "description": lane.description,
                    "agent": lane.agent_name,
                    "inputs": lane.inputs,
                    "outputs": lane.outputs,
                }
                for lane in playbook.lanes
            ]
        }
    
    # ========================================================================
    # NL QUESTION EXPORT METHODS
    # ========================================================================
    
    def get_nl_questions_for_sql(
        self,
        state: PlaybookExecutionState,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get generated NL questions ready for SQL translation.
        
        Args:
            state: Playbook execution state (from execute_playbook)
            include_metadata: Whether to include calculation metadata
            
        Returns:
            List of questions for SQL translation
        """
        return NLQuestionExporter.export_questions_for_sql_translation(
            state=state,
            include_metadata=include_metadata
        )
    
    def get_nl_questions_for_dbt(
        self,
        state: PlaybookExecutionState
    ) -> List[Dict[str, Any]]:
        """
        Get generated NL questions for dbt model generation.
        
        Args:
            state: Playbook execution state
            
        Returns:
            List of questions organized by lane for dbt
        """
        return NLQuestionExporter.export_questions_for_dbt(state=state)
    
    def get_questions_summary(
        self,
        state: PlaybookExecutionState
    ) -> Dict[str, Any]:
        """
        Get summary of generated questions.
        
        Args:
            state: Playbook execution state
            
        Returns:
            Summary statistics
        """
        return NLQuestionExporter.get_questions_summary(state=state)
    
    def export_questions_json(
        self,
        state: PlaybookExecutionState,
        include_reasoning: bool = True
    ) -> str:
        """
        Export all questions and context as JSON.
        
        Args:
            state: Playbook execution state
            include_reasoning: Whether to include reasoning plans
            
        Returns:
            JSON string
        """
        return NLQuestionExporter.export_to_json(
            state=state,
            include_reasoning=include_reasoning
        )
    
    def get_knowledge_helper(self) -> PlaybookKnowledgeHelper:
        """Get the playbook knowledge helper for direct access"""
        return get_playbook_knowledge_helper()
    
    def get_feature_definitions(
        self,
        categories: List[str] = None,
        compliance_framework: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get feature definitions from knowledge base.
        
        Args:
            categories: Specific categories to retrieve
            compliance_framework: Filter by framework
            
        Returns:
            List of feature definitions
        """
        helper = get_playbook_knowledge_helper()
        features = []
        
        if categories:
            for category in categories:
                if category in helper.feature_kb:
                    cat_features = helper.feature_kb[category].get("features", [])
                    features.extend(cat_features)
        else:
            for cat_name, cat_def in helper.feature_kb.items():
                if compliance_framework:
                    # Filter by framework
                    if compliance_framework.lower() in cat_name.lower():
                        features.extend(cat_def.get("features", []))
                else:
                    features.extend(cat_def.get("features", []))
        
        return features
    
    def get_sql_examples(
        self,
        category: str = None,
        compliance_framework: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get SQL instruction examples from knowledge base.
        
        Args:
            category: Specific category (e.g., 'soc2_silver', 'hipaa_silver')
            compliance_framework: Filter by framework
            
        Returns:
            List of SQL examples
        """
        helper = get_playbook_knowledge_helper()
        examples = []
        
        if category and category in helper.sql_examples:
            examples = helper.sql_examples[category]
        elif compliance_framework:
            framework_lower = compliance_framework.lower()
            for key, exs in helper.sql_examples.items():
                if framework_lower in key:
                    examples.extend(exs)
        else:
            for exs in helper.sql_examples.values():
                examples.extend(exs)
        
        return examples


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_playbook_driven_transform_agent(
    llm,
    engine: Engine,
    document_store_provider: DocumentStoreProvider = None,
    retrieval_helper: RetrievalHelper = None,
    contextual_graph_service: Any = None,
    contextual_reasoning_pipeline: Any = None,
    approval_callback: Optional[Callable[[Dict[str, Any]], asyncio.Future]] = None,
    auto_approve: bool = False,
    **kwargs
) -> PlaybookDrivenTransformAgent:
    """Factory function to create Playbook-Driven Transform Agent
    
    Args:
        llm: Language model instance
        engine: Engine instance
        document_store_provider: Optional document store provider
        retrieval_helper: Optional retrieval helper
        contextual_graph_service: Optional contextual graph service
        contextual_reasoning_pipeline: Optional reasoning pipeline
        approval_callback: Callback for human-in-the-loop approvals
        auto_approve: Whether to auto-approve for testing
        **kwargs: Additional arguments
        
    Returns:
        PlaybookDrivenTransformAgent instance
    """
    return PlaybookDrivenTransformAgent(
        llm=llm,
        engine=engine,
        document_store_provider=document_store_provider,
        retrieval_helper=retrieval_helper,
        contextual_graph_service=contextual_graph_service,
        contextual_reasoning_pipeline=contextual_reasoning_pipeline,
        approval_callback=approval_callback,
        auto_approve=auto_approve,
        **kwargs
    )


def register_custom_playbook(
    playbook_id: str,
    markdown_path: Optional[str] = None,
    markdown_content: Optional[str] = None
) -> str:
    """Register a custom playbook from a markdown file or content.
    
    Args:
        playbook_id: Unique playbook identifier
        markdown_path: Path to the playbook markdown file
        markdown_content: Raw markdown content (if path not provided)
        
    Returns:
        Registered playbook ID
        
    Example markdown format:
        # My Custom Playbook
        
        ## Purpose
        Description of what this playbook does.
        
        # Lane 0 — Bootstrap
        **Agent:** `MyBootstrapAgent`
        **Goal:** Initialize schemas and metadata
        
        **Outputs**
        - table_a
        - table_b
        
        # Lane 1 — Ingestion
        ...
    """
    if not markdown_path and not markdown_content:
        raise ValueError("Either markdown_path or markdown_content must be provided")
    
    if markdown_path:
        PLAYBOOK_MARKDOWN_PATHS[playbook_id] = markdown_path
    else:
        # Store content directly in a custom location marker
        PLAYBOOK_MARKDOWN_PATHS[playbook_id] = f"__content__:{playbook_id}"
        # Cache the content in the planner
        planner = get_playbook_planner()
        parsed = planner.parser.parse(markdown_content)
        planner._playbook_cache[playbook_id] = parsed
    
    # Update the registry
    PLAYBOOK_REGISTRY[playbook_id] = PLAYBOOK_MARKDOWN_PATHS[playbook_id]
    
    return playbook_id


def register_playbook_from_dict(
    playbook_id: str,
    name: str,
    description: str,
    domain: str,
    lanes: List[Dict[str, Any]],
    table_categories: Dict[str, List[str]] = None,
    compliance_frameworks: List[str] = None,
    output_time_series_tables: List[str] = None,
    guardrails: Dict[str, Any] = None
) -> str:
    """
    Register a custom playbook from a dictionary (legacy support).
    
    Converts to markdown format internally.
    
    Args:
        playbook_id: Unique playbook identifier
        name: Display name
        description: Playbook description
        domain: Domain name
        lanes: List of lane definitions
        table_categories: Dict mapping category names to lists of table names
        compliance_frameworks: Supported frameworks
        output_time_series_tables: Output tables
        guardrails: Execution guardrails
        
    Returns:
        Registered playbook ID
    """
    # Generate markdown from dict
    md_lines = [
        f"# {name}",
        "",
        "## Purpose",
        description,
        "",
    ]
    
    # Add canonical tables if provided
    if table_categories:
        md_lines.extend(["## Canonical Tables", ""])
        for category, tables in table_categories.items():
            md_lines.append(f"**{category.title()}**")
            for table in tables:
                md_lines.append(f"- `{table}`")
            md_lines.append("")
    
    # Add lanes
    for lane in lanes:
        lane_id = lane.get("lane_id", 0)
        lane_type = lane.get("lane_type", "custom")
        lane_name = lane.get("name", f"Lane {lane_id}")
        
        md_lines.extend([
            f"# Lane {lane_id} — {lane_name}",
            f"**Agent:** `{lane.get('agent_name', 'GenericAgent')}`",
            f"**Goal:** {lane.get('description', '')}",
            ""
        ])
        
        if lane.get("inputs"):
            md_lines.append("**Inputs**")
            for inp in lane["inputs"]:
                md_lines.append(f"- {inp}")
            md_lines.append("")
        
        if lane.get("outputs"):
            md_lines.append("**Outputs**")
            for out in lane["outputs"]:
                md_lines.append(f"- `{out}`")
            md_lines.append("")
    
    # Add guardrails if provided
    if guardrails:
        md_lines.extend(["## Guardrails", ""])
        if guardrails.get("allowed"):
            md_lines.append("✅ OK:")
            for item in guardrails["allowed"]:
                md_lines.append(f"- {item}")
        if guardrails.get("avoid"):
            md_lines.append("⛔ Avoid:")
            for item in guardrails["avoid"]:
                md_lines.append(f"- {item}")
    
    markdown_content = "\n".join(md_lines)
    
    return register_custom_playbook(playbook_id, markdown_content=markdown_content)
