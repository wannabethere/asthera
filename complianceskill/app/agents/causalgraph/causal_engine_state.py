"""
Causal Engine State Definitions

Defines the state schema and data models for the causal graph creator pipeline.
Based on causal_dashboard_design_doc.md Section 9 (State Contract).
"""
from typing import TypedDict, List, Dict, Optional, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================================
# Core Data Models
# ============================================================================

@dataclass
class CausalNode:
    """Causal node definition with type classification."""
    node_id: str
    metric_ref: str
    category: str
    node_type: Literal["root", "mediator", "confounder", "collider", "terminal"]
    observable: bool
    latent_proxy: Optional[str] = None
    temporal_grain: str = "monthly"  # daily|weekly|monthly|quarterly
    description: str = ""
    parent_count: int = 0
    child_count: int = 0
    collider_warning: bool = False
    is_outcome: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state storage."""
        return {
            "node_id": self.node_id,
            "metric_ref": self.metric_ref,
            "category": self.category,
            "node_type": self.node_type,
            "observable": self.observable,
            "latent_proxy": self.latent_proxy,
            "temporal_grain": self.temporal_grain,
            "description": self.description,
            "parent_count": self.parent_count,
            "child_count": self.child_count,
            "collider_warning": self.collider_warning,
            "is_outcome": self.is_outcome,
        }


@dataclass
class CausalEdge:
    """Causal edge definition with mechanism and confidence."""
    edge_id: str
    source_node: str
    target_node: str
    lag_window_days: int = 14
    lag_confidence: float = 0.75
    direction: Literal["positive", "negative", "nonlinear", "unknown"] = "positive"
    mechanism: str = ""
    confounders: List[str] = field(default_factory=list)
    confidence_score: float = 0.65
    corpus_validated: bool = False
    corpus_match_type: Literal["confirmed", "contradicted", "analogous", "novel", "untested"] = "novel"
    flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state storage."""
        return {
            "edge_id": self.edge_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "lag_window_days": self.lag_window_days,
            "lag_confidence": self.lag_confidence,
            "direction": self.direction,
            "mechanism": self.mechanism,
            "confounders": self.confounders,
            "confidence_score": self.confidence_score,
            "corpus_validated": self.corpus_validated,
            "corpus_match_type": self.corpus_match_type,
            "flags": self.flags,
        }


@dataclass
class ValidationResult:
    """Edge validation result from causal validation layer."""
    edge_id: str
    status: Literal["pass", "flag", "reject"]
    reason: str
    suggested_revision: Optional[str] = None
    corpus_references: List[str] = field(default_factory=list)


@dataclass
class GraphHydrationStatus:
    """Node observability status from graph hydrator."""
    node_id: str
    data_source: Optional[str] = None
    silver_table: Optional[str] = None
    observable: bool = False
    missing_reason: Optional[str] = None


@dataclass
class GraphMetadata:
    """Causal graph metadata summary."""
    vertical: str
    node_count: int
    edge_count: int
    observable_node_ratio: float
    mean_edge_confidence: float
    low_confidence_edges: List[str] = field(default_factory=list)
    unobservable_nodes: List[str] = field(default_factory=list)
    rejected_edge_count: int = 0
    revision_iterations_used: int = 0
    graph_coverage_flags: List[str] = field(default_factory=list)


# ============================================================================
# State Schema
# ============================================================================

class CSODCausalPipelineState(TypedDict, total=False):
    """
    State schema for CSOD causal graph pipeline.
    
    Extends EnhancedCompliancePipelineState with causal graph fields.
    """
    # ── Vertical configuration ─────────────────────────────────────────────
    vertical: str
    metric_registry: Dict[str, Any]
    schema_definitions: Dict[str, Any]
    corpus: List[Dict[str, Any]]
    available_data_sources: List[str]
    vertical_config: Dict[str, Any]
    
    # ── Causal engine — working state ──────────────────────────────────────
    decomposed_metric_groups: List[Dict[str, Any]]
    proposed_nodes: List[Dict[str, Any]]  # CausalNode dicts
    proposed_edges: List[Dict[str, Any]]  # CausalEdge dicts
    validation_results: List[Dict[str, Any]]  # ValidationResult dicts
    flagged_edges: List[str]
    rejected_edges: List[str]
    revision_queue: List[Dict[str, Any]]
    revision_iterations: int
    max_revisions: int
    
    # ── Causal engine — outputs ────────────────────────────────────────────
    hydration_status: List[Dict[str, Any]]  # GraphHydrationStatus dicts
    unobservable_nodes: List[str]
    causal_graph: Dict[str, Any]  # NetworkX node_link_data
    graph_metadata: Dict[str, Any]  # GraphMetadata dict
    
    # ── Bridge layer outputs ───────────────────────────────────────────────
    causal_signals: Dict[str, Any]  # derived decision signals
    causal_graph_boost_focus_areas: List[str]
    causal_graph_panel_data: Optional[Dict[str, Any]]
    causal_node_index: Dict[str, Dict[str, Any]]  # metric_ref → node metadata
    
    # ── CSOD integration fields ────────────────────────────────────────────
    user_query: str
    csod_intent: Optional[str]
    csod_metric_recommendations: List[Dict[str, Any]]
    csod_causal_graph_enabled: bool
    
    # ── Pipeline metadata ───────────────────────────────────────────────────
    current_phase: str
    iteration_count: int
    execution_steps: List[Dict[str, Any]]
    messages: List  # Annotated[..., add_messages]
    error: Optional[str]
