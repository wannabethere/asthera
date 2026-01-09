"""
State model for Universal Metadata Transfer Learning Pipeline
"""
from typing import Dict, List, Optional, Any, Annotated, TypedDict, Sequence
from dataclasses import dataclass
from enum import Enum
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class MetadataGenerationStatus(str, Enum):
    """Status of metadata generation process"""
    INITIALIZED = "initialized"
    PATTERN_LEARNING = "pattern_learning"
    DOMAIN_ADAPTATION = "domain_adaptation"
    METADATA_GENERATION = "metadata_generation"
    VALIDATION = "validation"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MetadataPattern:
    """Represents a learned pattern from source domain"""
    pattern_name: str
    pattern_type: str  # 'structural', 'semantic', 'scoring', 'relationship'
    source_domain: str
    pattern_structure: Dict[str, Any]
    pattern_examples: List[Dict[str, Any]]
    confidence: float
    description: Optional[str] = None


@dataclass
class DomainMapping:
    """Maps concepts between source and target domains"""
    source_domain: str
    source_code: str
    source_enum_type: str
    target_domain: str
    target_code: str
    target_enum_type: str
    mapping_type: str  # 'exact', 'similar', 'analogical'
    similarity_score: float
    mapping_rationale: str


@dataclass
class MetadataEntry:
    """Represents a single metadata entry to be generated"""
    domain_name: str
    framework_name: Optional[str]
    metadata_category: str
    enum_type: str
    code: str
    description: str
    numeric_score: float
    priority_order: int
    severity_level: Optional[int] = None
    weight: float = 1.0
    risk_score: Optional[float] = None
    occurrence_likelihood: Optional[float] = None
    consequence_severity: Optional[float] = None
    exploitability_score: Optional[float] = None
    impact_score: Optional[float] = None
    rationale: Optional[str] = None
    data_source: Optional[str] = None
    calculation_method: Optional[str] = None
    data_indicators: Optional[str] = None
    parent_code: Optional[str] = None
    equivalent_codes: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    abbreviation: Optional[str] = None


class MetadataTransferLearningState(TypedDict, total=False):
    """State for the metadata transfer learning workflow (LangGraph compatible)"""
    
    # Input parameters
    target_domain: str
    target_framework: Optional[str]
    source_domains: List[str]
    target_documents: List[str]  # Document texts
    target_document_sources: List[str]  # Document source identifiers
    
    # Pattern learning phase
    source_metadata: List[Dict[str, Any]]  # Metadata from source domains
    learned_patterns: List[Dict[str, Any]]  # Serialized MetadataPattern objects
    pattern_analysis: Dict[str, Any]
    
    # Domain adaptation phase
    domain_mappings: List[Dict[str, Any]]  # Serialized DomainMapping objects
    adaptation_strategy: Dict[str, Any]
    analogical_reasoning: List[str]
    
    # Metadata generation phase
    identified_risks: List[Dict[str, Any]]  # Risks identified from documents
    generated_metadata: List[Dict[str, Any]]  # Serialized MetadataEntry objects
    generation_notes: List[str]
    
    # Validation phase
    validation_results: Dict[str, Any]
    validation_issues: List[Dict[str, Any]]
    refined_metadata: List[Dict[str, Any]]  # Serialized MetadataEntry objects
    
    # Workflow state
    status: str  # MetadataGenerationStatus as string
    current_step: str
    messages: Annotated[Sequence[BaseMessage], add_messages]
    errors: List[str]
    warnings: List[str]
    
    # Session tracking
    session_id: Optional[str]
    created_by: str
    
    # Confidence and quality metrics
    overall_confidence: float
    quality_scores: Dict[str, float]
    
    # Database integration
    metadata_entries_created: int
    patterns_applied: List[str]

