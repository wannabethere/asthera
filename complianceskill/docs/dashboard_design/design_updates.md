# Design Updates — Resolve → Bind → Score → Recommend → Verify
**Integration guide for existing Layout Advisor Agent codebase**

---

## Overview

The existing system runs a single linear conversation:
`intake → decision_loop → scoring → recommendation → selection → customization → spec_generation`

The updated pipeline inserts three new structural stages (BIND, RECOMMEND with adjustment handles, VERIFY) and promotes RESOLVE from an implicit decision loop to an explicit first-class stage with two paths. The human approval gate (VERIFY) replaces the selection+customization loop as the final decision point.

---

## 1. `state.py`

### New Phases to Add to `Phase` Enum

The existing five `DECISION_*` phases remain but are now contained within the RESOLVE stage. Add:

```python
class Phase(str, Enum):
    # --- Existing (unchanged) ---
    INTAKE = "intake"
    DECISION_INTENT = "decision_intent"
    DECISION_SYSTEMS = "decision_systems"
    DECISION_AUDIENCE = "decision_audience"
    DECISION_CHAT = "decision_chat"
    DECISION_KPIS = "decision_kpis"

    # --- New stages ---
    BIND = "bind"                          # registry join, no user input
    SCORE = "score"                        # template + chart scoring, no user input
    RECOMMEND = "recommend"                # assemble options for human
    VERIFY = "verify"                      # human approval gate
    VERIFY_ADJUST = "verify_adjust"        # human applied an adjustment handle
    VERIFY_RERUN = "verify_rerun"          # partial pipeline re-run requested

    # --- Existing (unchanged) ---
    SPEC_GENERATION = "spec_generation"
    COMPLETE = "complete"
```

### New TypedDicts to Add

```python
class ResolutionPayload(TypedDict, total=False):
    """Output of BIND stage — fully joined registry context."""
    resolved_metric_groups: dict          # {required: [...], optional_included: [...]}
    control_anchors: list[dict]           # [{id, domain, focus, risk_categories}, ...]
    focus_areas: list[str]
    risk_categories: list[str]
    timeframe: str                        # "daily" | "monthly" | "quarterly"
    audience: str
    complexity: str


class ScoredCandidate(TypedDict):
    """Output of SCORE stage — one ranked template option."""
    template_id: str
    name: str
    score: int
    coverage_gaps: list[str]             # control anchor IDs not coverable
    coverage_pct: float                  # 0.0–1.0
    reasons: list[str]
    chart_candidates: dict               # {metric_group: {top, runner_up, reason}}
    adjustment_handles: list[dict]       # pre-computed handles for VERIFY


class AdjustmentHandle(TypedDict):
    """A named, pre-computed modification the human can apply at VERIFY."""
    id: str                              # e.g. "promote_control_CC5"
    label: str                           # human-readable label
    description: str                     # what it changes
    re_triggers: str                     # "none" | "chart_scoring" | "layout_rescore" | "full"
    delta: dict                          # the actual spec change


class PipelineAudit(TypedDict):
    """Immutable audit trail written when spec is committed."""
    resolve_path: str                    # "decision_tree" | "llm_advisor"
    bind_control_count: int
    score_candidates_evaluated: int
    recommend_options_presented: int
    verify_adjustments_applied: int
    verify_options_switched: int
    verify_rescore_count: int
    approved_by: str
    approved_at: str
```

### New Fields to Add to `LayoutAdvisorState`

Add these fields to the existing `LayoutAdvisorState` TypedDict:

```python
# RESOLVE output
use_case_group: str                      # from metric_use_case_groups.json
framework: list[str]                     # ["soc2"] | ["hipaa"] | ["nist_ai_rmf"]
resolution_confidence: float            # 0.0–1.0

# BIND output  
resolution_payload: ResolutionPayload

# SCORE output — replaces candidate_templates
scored_candidates: list[ScoredCandidate]  # replaces candidate_templates
# recommended_top3 already exists — keep, but now contains ScoredCandidates

# RECOMMEND output
adjustment_handles: list[AdjustmentHandle]   # pre-computed per top-3 option
recommend_rationale: list[dict]              # [{option_idx, rationale, coverage_map}]

# VERIFY state
spec_status: str                         # "pending_approval" | "approved" | "rejected"
verify_decision: str                     # "approve" | "adjust" | "switch" | "rescore" | "reject"
selected_option_idx: int                 # which of top-3 is active (0=primary)
adjustments_applied: list[str]           # handle IDs applied this session

# Post-VERIFY
compliance_context: dict                 # written to committed spec
pipeline_audit: PipelineAudit           # written to committed spec
```

### `UpstreamContext` — New Fields

```python
class UpstreamContext(TypedDict, total=False):
    # --- Existing fields unchanged ---
    use_case: str
    data_sources: list[str]
    persona: str
    metrics: list[dict]
    kpis: list[dict]
    tables: list[dict]
    visuals: list[dict]
    has_chat_requirement: bool
    kpi_count: int
    framework: str

    # --- New fields ---
    use_case_group: str                  # if upstream already resolved it
    control_ids: list[str]              # e.g. ["CC7"] for compliance-first entry
    goal_statement: str                  # freeform goal from UI
```

---

## 2. `graph.py`

### New Nodes to Register

```python
# After intake, before decision loop
workflow.add_node("bind", bind_node)
workflow.add_node("score", score_node)          # replaces scoring_node
workflow.add_node("recommend", recommend_node)  # replaces recommendation_node

# VERIFY gate (human-in-the-loop)
workflow.add_node("await_verify_input", await_verify_input)
workflow.add_node("verify", verify_node)
```

### Updated Graph Topology

The existing decision loop (decision_intent → ... → decision_kpis) becomes the **RESOLVE conversation path** — it feeds into BIND on completion rather than directly into the old `scoring` node.

```
START → intake
  ↓
intake → [auto-resolved all?]
  YES → bind (skip decision loop)
  NO  → await_decision_input → decision → [more decisions?]
            YES → await_decision_input (loop)
            NO  → bind

bind → score → recommend → await_verify_input → verify
  ↓ (from verify)
  APPROVE         → spec_generation → END
  ADJUST          → verify (re-present with diff)
  SWITCH          → recommend (rebuild from alt candidate)
  RESCORE         → bind (re-run from bind with new params)
  REJECT          → intake (full restart, save draft)
```

### New Routing Functions

```python
def route_after_decision(state: LayoutAdvisorState) -> str:
    """After last decision, route to BIND (not scoring)."""
    phase = state.get("phase")
    if phase == Phase.BIND:
        return "bind"
    return "await_decision_input"


def route_after_verify(state: LayoutAdvisorState) -> str:
    """Five-way branch from VERIFY."""
    decision = state.get("verify_decision", "")
    routes = {
        "approve":  "spec_generation",
        "adjust":   "await_verify_input",   # diff shown, re-present
        "switch":   "recommend",            # rebuild from alt
        "rescore":  "bind",                 # partial re-run
        "reject":   "intake",              # full restart
    }
    return routes.get(decision, "await_verify_input")


def await_verify_input(state: LayoutAdvisorState) -> dict:
    """Pause point — VERIFY human gate."""
    return {"needs_user_input": True, "spec_status": "pending_approval"}
```

### Interrupt Points Update

```python
interrupt_before = [
    "await_decision_input",      # existing — decision loop questions
    "await_verify_input",        # NEW — human approval gate
]
# Remove: "await_selection_input", "await_customization_input"
# These are replaced by VERIFY
```

---

## 3. `nodes.py`

### `scoring_node` → Replace with `score_node`

The existing `scoring_node` runs `score_templates_hybrid(decisions)` against all 17 templates with no control-anchor awareness. Replace entirely.

**New `score_node` responsibilities:**
- Pre-filter template pool by `domain` and `theme` from `resolution_payload` (reduces 23 → 3–6 candidates)
- Run existing `score_templates_hybrid` on pre-filtered set only
- For each candidate, compute `coverage_gaps`: control anchors from `resolution_payload.control_anchors` that the template's posture_strip_cells and panel components cannot accommodate
- Compute `coverage_pct` = (total_anchors - gap_count) / total_anchors
- Run **Pass B**: for each `resolved_metric_group`, score chart type candidates from EPS catalog against `display_type` hint and audience `complexity` tier
- Pre-compute `adjustment_handles` for each candidate (see `AdjustmentHandle` schema)
- Write `scored_candidates` list; set top-3 into `recommended_top3`
- Phase transitions to `Phase.RECOMMEND`

**Coverage gap computation logic:**
```
For each control_anchor in resolution_payload.control_anchors:
    anchor_coverable = False
    For each strip_cell in template.posture_strip_cells:
        if anchor.focus in strip_cell_focus_map[strip_cell]:
            anchor_coverable = True
    For each panel_component in template.panel_config.*:
        if anchor.focus in component_focus_map[panel_component]:
            anchor_coverable = True
    if not anchor_coverable:
        coverage_gaps.append(anchor.id)
```

**Adjustment handle pre-computation:**
```
For each coverage_gap in candidate.coverage_gaps:
    create AdjustmentHandle(
        id=f"promote_control_{gap}",
        label=f"Add {gap} to dashboard",
        description=f"Adds {gap} strip cell and creates a detail section for {anchor.domain}",
        re_triggers="chart_scoring",
        delta={"strip_cells": [...existing + gap_cell], "panel_bindings": {...}}
    )
For swap_chart options:
    For each metric_group with runner_up chart:
        create AdjustmentHandle(
            id=f"swap_chart_{metric_group}",
            label=f"Use {runner_up} instead of {top_chart} for {metric_group}",
            re_triggers="none",
            delta={"chart_specs": {metric_group: runner_up_spec}}
        )
```

### `recommendation_node` → Replace with `recommend_node`

The existing `recommendation_node` generates a simple text list. Replace with:

**New `recommend_node` responsibilities:**
- For each of the top-3 candidates, build a `RecommendOption` containing:
  - Template name, score, full rationale (LLM-generated or template-string, see Prompts file)
  - Coverage map: grid of anchor_id → covered/gap for this option
  - Proposed posture strip cells (one per control anchor, sourced from Metric Catalog)
  - Chart type selection per panel (top chart from Pass B)
  - Applicable adjustment handles (from pre-computed set on the `ScoredCandidate`)
- Write `recommend_rationale` list to state
- Write `adjustment_handles` to state (union of all handles across top-3)
- Phase transitions to `Phase.VERIFY`
- Set `spec_status = "pending_approval"`

### New `bind_node`

Insert between `intake`/decision loop and `score_node`. Calls `taxonomy_matcher.expand_use_case_group()` and `taxonomy_matcher.join_control_anchors()` (see `taxonomy_matcher.py` updates). Writes `resolution_payload` to state. No user interaction.

### New `verify_node`

Replaces `selection_node` + `customization_node` combined.

**Responsibilities:**
- Parse `user_response` to determine `verify_decision` (approve / adjust / switch / rescore / reject)
- On **approve**: write `pipeline_audit` block, set `spec_status = "approved"`, set phase to `SPEC_GENERATION`
- On **adjust**: look up `adjustment_handles` by handle ID in `user_response`, apply `delta` to pending spec, generate diff summary (see Prompts file), return to `await_verify_input` with diff shown
- On **switch**: parse option number (2 or 3), rebuild `recommended_top3[idx]` as primary, return to `await_verify_input`
- On **rescore**: extract updated parameters from `user_response` (e.g., "change timeframe to quarterly"), update state, set phase to `BIND`, re-run
- On **reject**: save draft with `spec_status = "rejected"`, write `pipeline_audit` with rejection note, route to `intake`

**Parse keywords:**
```python
APPROVE_KEYWORDS = ["approve", "looks good", "finalize", "done", "go ahead", "perfect", "ship it", "lgtm", "yes"]
REJECT_KEYWORDS  = ["reject", "start over", "restart", "wrong", "no", "cancel"]
SWITCH_KEYWORDS  = ["switch", "option 2", "option 3", "second", "third", "try #2", "try #3"]
RESCORE_KEYWORDS = ["change timeframe", "add framework", "quarterly", "weekly", "hipaa", "nist", "rescore"]
# Everything else → treat as ADJUST, match to closest adjustment handle by keyword
```

### `spec_generation_node` Updates

Add two new blocks to the generated spec that were not present before:

```python
# Write compliance_context block
spec["compliance_context"] = {
    "control_anchors": [a["id"] for a in resolution_payload.get("control_anchors", [])],
    "focus_areas": resolution_payload.get("focus_areas", []),
    "risk_categories": resolution_payload.get("risk_categories", []),
}

# Write pipeline_audit block
spec["pipeline_audit"] = {
    "resolve_path": state.get("resolution_path", "decision_tree"),
    "bind_control_count": len(resolution_payload.get("control_anchors", [])),
    "score_candidates_evaluated": len(state.get("scored_candidates", [])),
    "recommend_options_presented": len(state.get("recommended_top3", [])),
    "verify_adjustments_applied": len(state.get("adjustments_applied", [])),
    "verify_options_switched": state.get("selected_option_idx", 0),
    "approved_by": state.get("upstream_context", {}).get("persona", "user"),
    "approved_at": datetime.utcnow().isoformat(),
}

# Set spec status
spec["status"] = "approved"
```

---

## 4. `runner.py`

### `AdvisorResponse` — New Fields

```python
@dataclass
class AdvisorResponse:
    agent_message: str
    phase: str
    is_complete: bool = False
    needs_input: bool = True

    # Existing
    options: list[str] = field(default_factory=list)
    recommended: list[dict] = field(default_factory=list)
    selected_template: Optional[str] = None
    layout_spec: Optional[dict] = None
    decisions_so_far: dict = field(default_factory=dict)
    error: Optional[str] = None

    # New
    spec_status: str = "draft"                           # pending_approval | approved | rejected
    coverage_map: list[dict] = field(default_factory=list)   # per-option coverage grid
    adjustment_handles: list[dict] = field(default_factory=list)
    recommend_rationale: list[dict] = field(default_factory=list)
    compliance_context: dict = field(default_factory=dict)
    pipeline_audit: dict = field(default_factory=dict)
    resolution_payload: dict = field(default_factory=dict)
    active_option_idx: int = 0
```

### New Methods on `LayoutAdvisorSession`

```python
def approve(self) -> AdvisorResponse:
    """Shortcut: send approval to VERIFY gate."""
    return self.respond("approve")

def reject(self, reason: str = "") -> AdvisorResponse:
    """Shortcut: reject and restart."""
    return self.respond(f"reject {reason}".strip())

def apply_handle(self, handle_id: str) -> AdvisorResponse:
    """Apply a named adjustment handle at VERIFY."""
    return self.respond(handle_id)

def switch_option(self, option_number: int) -> AdvisorResponse:
    """Switch to option 2 or 3 at VERIFY."""
    return self.respond(f"switch option {option_number}")
```

### `_build_response` Updates

```python
def _build_response(self, state: dict) -> AdvisorResponse:
    # ... existing extraction logic unchanged ...

    # New fields
    spec_status = state.get("spec_status", "draft")
    coverage_map = [
        {
            "option": i + 1,
            "template_id": c.get("template_id"),
            "coverage_pct": c.get("coverage_pct", 0),
            "covered": [a for a in all_anchors if a not in c.get("coverage_gaps", [])],
            "gaps": c.get("coverage_gaps", []),
        }
        for i, c in enumerate(state.get("recommended_top3", []))
    ]
    adjustment_handles = state.get("adjustment_handles", [])
    recommend_rationale = state.get("recommend_rationale", [])
    compliance_context = state.get("compliance_context", {})
    pipeline_audit = state.get("pipeline_audit", {})

    return AdvisorResponse(
        # ... existing fields ...
        spec_status=spec_status,
        coverage_map=coverage_map,
        adjustment_handles=adjustment_handles,
        recommend_rationale=recommend_rationale,
        compliance_context=compliance_context,
        pipeline_audit=pipeline_audit,
        resolution_payload=state.get("resolution_payload", {}),
        active_option_idx=state.get("selected_option_idx", 0),
    )
```

### `_get_options_for_phase` Updates

```python
# Remove PHASE_TO_DECISION lookup for SELECTION phase (no longer exists)
# Replace with VERIFY phase options

if phase == Phase.VERIFY:
    handles = state.get("adjustment_handles", [])
    base_options = ["✅ Approve", "❌ Reject / Start Over"]
    if len(state.get("recommended_top3", [])) > 1:
        base_options.insert(1, "↔ Switch to Option 2")
    if len(state.get("recommended_top3", [])) > 2:
        base_options.insert(2, "↔ Switch to Option 3")
    handle_options = [f"🔧 {h['label']}" for h in handles[:5]]
    return base_options + handle_options
```

---

## 5. `tools.py`

### New Tool: `bind_metric_groups`

```python
@tool
def bind_metric_groups(use_case_group: str, complexity: str) -> str:
    """
    Expand a use_case_group into required/optional metric groups.
    Loads from metric_use_case_groups.json and applies complexity gating.
    
    Args:
        use_case_group: e.g. "soc2_audit", "lms_learning_target"
        complexity: "low" | "medium" | "high"
    
    Returns:
        JSON with required_groups, optional_included, timeframe, audience.
    """
```

### New Tool: `bind_control_anchors`

```python
@tool
def bind_control_anchors(focus_areas: list[str], framework: str) -> str:
    """
    Join focus_areas against control_domain_taxonomy for a given framework.
    Returns the matched control anchors with their risk_categories.
    
    Args:
        focus_areas: e.g. ["training_compliance", "access_control"]
        framework: "soc2" | "hipaa" | "nist_ai_rmf"
    
    Returns:
        JSON array of matched control_anchor dicts.
    """
```

### New Tool: `compute_coverage_gaps`

```python
@tool
def compute_coverage_gaps(template_id: str, control_anchors: list[dict]) -> str:
    """
    Check which control anchors a given template cannot surface.
    Checks posture_strip_cells and panel_components against anchor focus_areas.
    
    Args:
        template_id: e.g. "hybrid-compliance"
        control_anchors: list of anchor dicts from resolution_payload
    
    Returns:
        JSON with covered_anchors[], gap_anchors[], coverage_pct.
    """
```

### New Tool: `apply_adjustment_handle`

```python
@tool
def apply_adjustment_handle(
    current_spec: dict,
    handle: dict,
    resolution_payload: dict,
) -> str:
    """
    Apply a pre-computed adjustment handle to a pending spec.
    Returns the updated spec AND a human-readable diff summary.
    
    Args:
        current_spec: The current pending spec dict
        handle: AdjustmentHandle dict (id, delta, re_triggers)
        resolution_payload: For context when re-triggers != "none"
    
    Returns:
        JSON with {updated_spec, diff_summary, re_triggers}.
    """
```

### Updated `score_templates` Tool

The existing tool calls `score_templates_hybrid(decisions)` on all templates. Update to:
1. Accept `resolution_payload` as a parameter (not just `decisions`)
2. Pre-filter by domain+theme before scoring
3. Compute `coverage_gaps` per candidate
4. Return `coverage_pct` and `adjustment_handles` per candidate alongside existing score/reasons

### Remove Tool: ~~`apply_customization`~~

This is replaced by `apply_adjustment_handle`. Remove from `LAYOUT_TOOLS`.

### Updated `LAYOUT_TOOLS` List

```python
LAYOUT_TOOLS = [
    search_templates,
    score_templates,           # updated signature
    get_template_detail,
    generate_layout_spec,
    bind_metric_groups,        # new
    bind_control_anchors,      # new
    compute_coverage_gaps,     # new
    apply_adjustment_handle,   # new (replaces apply_customization)
    list_templates,
    match_domain_from_metrics_tool,
]
```

---

## 6. `taxonomy_matcher.py`

### New Function: `match_use_case_group`

```python
def match_use_case_group(
    goal_text: str,
    data_sources: Optional[list[str]] = None,
    framework: Optional[str] = None,
) -> tuple[str, float]:
    """
    Rule-based keyword match of freeform goal text to a use_case_group.
    Returns (use_case_group_id, confidence_score).
    Falls back to "operational_monitoring" with low confidence if no match.
    
    Keyword map (extend from metric_use_case_groups.json keys):
        audit, compliance evidence, control testing → soc2_audit
        training, learning, LMS, completion → lms_learning_target
        risk report, risk posture, risk summary → risk_posture_report
        executive, board, leadership, KPI summary → executive_dashboard
        monitoring, alerts, operations, SOC → operational_monitoring
    """
```

### New Function: `expand_use_case_group`

```python
def expand_use_case_group(
    use_case_group: str,
    complexity: str,
) -> dict:
    """
    Load metric_use_case_groups.json and return expanded group with
    complexity-gated optional groups.
    
    Returns:
        {required_groups, optional_included, default_audience, default_timeframe,
         framework_overrides}
    """
```

### New Function: `join_control_anchors`

```python
def join_control_anchors(
    focus_areas: list[str],
    framework: str,
) -> list[dict]:
    """
    Join focus_areas against control_domain_taxonomy.json for the given framework.
    
    For each control in the framework:
        if any(fa in control.focus_areas for fa in focus_areas):
            include control as anchor
    
    Returns list of anchor dicts: [{id, domain, display_name, focus, risk_categories}]
    """
```

### New Function: `reverse_map_control_to_use_case`

```python
def reverse_map_control_to_use_case(
    control_id: str,
    framework: str,
) -> tuple[str, list[str]]:
    """
    Compliance-first entry point.
    Given a control ID (e.g. "CC7", "164.312(b)"), find the best
    use_case_group and resolve focus_areas.
    
    Returns (use_case_group_id, focus_areas_list)
    
    Logic:
        1. Look up control in taxonomy → get focus_areas, risk_categories
        2. Match focus_areas against metric_use_case_groups required_groups
        3. Find use_case_group with highest overlap
    """
```

### Update to `match_domain_from_metrics`

Add `use_case_group` as an optional parameter. When provided, use it to bias domain scoring (the domain tied to the use_case_group in `dashboard_domain_taxonomy.json` gets a +25pt boost).

---

## 7. `llm_agent.py`

The LLM agent is the **fallback path within RESOLVE** when freeform goal input cannot be resolved by the decision tree. It does not change structurally — but its system prompt is updated to reflect its new scope.

**Scope change:** The LLM agent now operates only within RESOLVE. It runs the decision conversation, then hands off a structured `Dashboard Intent Object` to BIND. It does not participate in BIND, SCORE, RECOMMEND, or VERIFY directly.

**System prompt update:** See `prompts.md` → Prompt 1 (Goal Classification) and Prompt 2 (Decision Conversation).

**Output contract change:** The agent must produce a structured JSON block at conversation completion with the Dashboard Intent Object fields that BIND consumes:

```python
# At end of LLM conversation, extract structured output:
INTENT_EXTRACTION_SCHEMA = {
    "use_case_group": str,      # matched to metric_use_case_groups keys
    "domain": str,              # matched to dashboard_domain_taxonomy keys
    "framework": list[str],     # ["soc2"] | ["hipaa"] | []
    "audience": str,
    "complexity": str,
    "theme": str,
    "timeframe": str,
    "resolution_confidence": float,
}
```

Add a `_extract_intent_object(messages: list) -> dict` helper that calls a structured extraction prompt after the conversation completes, using the `INTENT_EXTRACTION_SCHEMA`.

---

## Migration Checklist

| File | Status | Notes |
|---|---|---|
| `state.py` | Additive | New phases, TypedDicts, fields on `LayoutAdvisorState` and `UpstreamContext` |
| `graph.py` | Additive + route changes | New nodes, updated routing functions, updated interrupt list |
| `nodes.py` | Replace `scoring_node`, `recommendation_node`; Add `bind_node`, `verify_node`; Update `spec_generation_node` | Old `selection_node` + `customization_node` removed |
| `runner.py` | Additive | New fields on `AdvisorResponse`, new shortcut methods, updated `_build_response` and `_get_options_for_phase` |
| `tools.py` | Additive + one removal | 4 new tools, `score_templates` updated, `apply_customization` removed |
| `taxonomy_matcher.py` | Additive | 4 new functions, minor update to `match_domain_from_metrics` |
| `llm_agent.py` | Prompt update + output contract | System prompt update, add intent extraction schema |
