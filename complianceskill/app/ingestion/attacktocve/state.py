"""
State schema for the ATT&CK → CIS Control enrichment LangGraph pipeline.

Flow:
  Input (technique_id or scenario_id)
    → ATT&CK Enrichment Node
    → Vector Store Retrieval Node
    → Control Mapping Node (LLM)
    → Validation Node
    → Output Node
"""

from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ATTACKTechniqueDetail(BaseModel):
    """Enriched detail from MITRE ATT&CK STIX data."""
    technique_id: str
    name: str
    description: str
    tactics: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    mitigations: list[dict[str, str]] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    detection: str = ""


class CISRiskScenario(BaseModel):
    """Parsed CIS Risk Scenario from YAML."""
    scenario_id: str
    name: str
    asset: str
    trigger: str
    loss_outcomes: list[str] = Field(default_factory=list)
    description: str = Field(default="", description="Risk scenario description (optional)")
    controls: list[str] = Field(default_factory=list)  # populated by this pipeline


class ControlMapping(BaseModel):
    """A single ATT&CK technique → CIS scenario mapping."""
    technique_id: str
    scenario_id: str
    scenario_name: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    mapped_controls: list[str] = Field(default_factory=list)
    attack_tactics: list[str] = Field(default_factory=list)
    attack_platforms: list[str] = Field(default_factory=list)
    loss_outcomes: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class ValidationResult(BaseModel):
    """Output of the validation node."""
    is_valid: bool
    issues: list[str] = Field(default_factory=list)
    corrected_mappings: list[ControlMapping] = Field(default_factory=list)
    validation_notes: str = ""


# ---------------------------------------------------------------------------
# LangGraph State
# ---------------------------------------------------------------------------

class AttackControlState(TypedDict):
    """
    Full graph state.  Every node reads from and writes to this dict.
    Use `operator.add` reducers for lists to allow parallel fan-out nodes.
    """

    # ── Inputs ──────────────────────────────────────────────────────────────
    technique_id: str                           # e.g. "T1003.001"
    scenario_filter: Optional[str]             # optional asset-domain filter
    framework_id: Optional[str]                 # e.g. "cis_controls_v8_1" (for filtering)
    framework_name: Optional[str]                # e.g. "CIS Controls v8.1"
    control_id_label: Optional[str]              # e.g. "CIS-RISK-NNN"

    # ── ATT&CK Enrichment ───────────────────────────────────────────────────
    attack_detail: Optional[ATTACKTechniqueDetail]
    enrich_error: Optional[str]

    # ── Vector Store Retrieval ──────────────────────────────────────────────
    retrieved_scenarios: list[CISRiskScenario]  # top-k from vector store
    retrieval_scores: list[float]               # cosine / MMR scores
    retrieval_source: str                       # "qdrant" | "chroma" | "yaml_fallback"

    # ── LLM Mapping ─────────────────────────────────────────────────────────
    raw_mappings: list[ControlMapping]          # before validation
    mapping_rationale: str                      # chain-of-thought from LLM

    # ── Validation ──────────────────────────────────────────────────────────
    validation_result: Optional[ValidationResult]

    # ── Final Output ────────────────────────────────────────────────────────
    final_mappings: list[ControlMapping]
    enriched_scenarios: list[CISRiskScenario]   # YAML scenarios with controls populated
    output_summary: str

    # ── Control ─────────────────────────────────────────────────────────────
    error: Optional[str]
    current_node: str
    iteration_count: int
