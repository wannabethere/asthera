# Detection & Triage Workflow — Integration Guide

## Integration Status

| Step | Status | Notes |
|---|---|---|
| Step 1: Copy files | ✅ Complete | All DT workflow files are in place |
| Step 2: Add DT state fields | ✅ Complete | Fields added to `EnhancedCompliancePipelineState` |
| Step 3: Copy DT prompts | ✅ Complete | Prompts integrated from `prompts_mdl` directory |
| Step 4: Set `active_project_id` | ⚠️ Manual | Must be set per session/tenant |
| Step 5: Wire DT into workflow | ⚠️ Optional | Only if integrating with existing workflow |
| Step 6: Verify `search_project_meta` | ✅ Complete | Method exists in `MDLRetrievalService` |

---

## Files Delivered

| File | Drop location | Purpose |
|---|---|---|
| `dt_nodes.py` | `app/agents/dt_nodes.py` | All 11 LangGraph node functions |
| `dt_tool_integration.py` | `app/agents/dt_tool_integration.py` | MDL helpers, async runner, tool maps |
| `dt_state.py` | `app/agents/dt_state.py` | State extension (TypedDict additions) |
| `dt_workflow.py` | `app/agents/dt_workflow.py` | Graph builder + app factory |

---

## Step 1 — Copy files to your project

**Status:** ✅ **COMPLETED** - All DT workflow files are already in place.

The following files are located in `app/agents/`:
- `dt_nodes.py` - All 11 LangGraph node functions
- `dt_tool_integration.py` - MDL helpers, async runner, tool maps
- `dt_state.py` - State extension (TypedDict additions)
- `dt_workflow.py` - Graph builder + app factory

No action needed - files are already integrated.

---

## Step 2 — Add DT state fields to EnhancedCompliancePipelineState

**Status:** ✅ **COMPLETED** - DT state fields have been added to `EnhancedCompliancePipelineState` in `app/agents/state.py`.

The following fields are now available in the base state:

```python
# ========== Detection & Triage workflow fields ==========
active_project_id: Optional[str]          # ProjectId for GoldStandardTable lookup
dt_plan_summary: Optional[str]
dt_estimated_complexity: Optional[str]     # "simple" | "moderate" | "complex"
dt_playbook_template: Optional[str]       # "A" | "B" | "C"
dt_playbook_template_sections: List[str]
dt_expected_outputs: Optional[Dict[str, bool]]
dt_gap_notes: List[str]
dt_data_sources_in_scope: List[str]
dt_retrieved_controls: List[Dict[str, Any]]
dt_retrieved_risks: List[Dict[str, Any]]
dt_retrieved_scenarios: List[Dict[str, Any]]
dt_resolved_schemas: List[Dict[str, Any]]
dt_gold_standard_tables: List[Dict[str, Any]]
dt_scored_context: Optional[Dict[str, Any]]
dt_dropped_items: List[Dict[str, Any]]
dt_schema_gaps: List[Dict[str, Any]]
dt_scoring_threshold_applied: float
dt_rule_gaps: List[Dict[str, Any]]
dt_coverage_summary: Optional[Dict[str, Any]]
dt_medallion_plan: Optional[Dict[str, Any]]
dt_metric_recommendations: List[Dict[str, Any]]
dt_unmeasured_controls: List[Dict[str, Any]]
dt_siem_validation_passed: bool
dt_siem_validation_failures: List[Dict[str, Any]]
dt_metric_validation_passed: bool
dt_metric_validation_failures: List[Dict[str, Any]]
dt_metric_validation_warnings: List[Dict[str, Any]]
dt_metric_validation_rule_summary: Optional[Dict[str, str]]
dt_validation_iteration: int
dt_assembled_playbook: Optional[Dict[str, Any]]
```

> **Note:** `dt_state.py` also defines these in a separate `TypedDict` (`DetectionTriageState`) for clarity, but they are now merged into the base state for unified access.

---

## Step 3 — DT prompts are already integrated

The DT nodes load prompts from the `prompts_mdl` directory using these names:

| Node | Prompt file | Location |
|---|---|---|
| dt_intent_classifier_node | `01_intent_classifier.md` | `app/agents/prompts_mdl/` |
| dt_planner_node | `02_detection_triage_planner.md` | `app/agents/prompts_mdl/` |
| dt_detection_engineer_node | `03_detection_engineer.md` | `app/agents/prompts_mdl/` |
| dt_triage_engineer_node | `04_triage_engineer.md` | `app/agents/prompts_mdl/` |
| dt_scoring_validator_node | `05_relevance_scoring_validator.md` | `app/agents/prompts_mdl/` (for reference) |
| dt_metric_calculation_validator_node | `06_metric_calculation_validator.md` | `app/agents/prompts_mdl/` (for reference) |
| dt_playbook_assembler_node | `07_playbook_assembler.md` | Falls back to generic template if not found |

**Status:** ✅ Prompts are already integrated. The nodes automatically load from `app/agents/prompts_mdl/` directory with fallback to the base `prompts/` directory if needed.

**Note:** The scoring and metric calculation validators are algorithmic (no LLM calls), so their prompts serve as documentation of the validation rules implemented in code.

---

## Step 4 — Set `active_project_id` in your tenant/session context

`dt_mdl_schema_retrieval_node` looks up GoldStandardTables using:

```python
project_id = (
    state.get("active_project_id")
    or (state.get("compliance_profile") or {}).get("project_id", "")
)
```

**Action:** Populate `active_project_id` when building the initial state for a session.
The project ID maps to the tenant's project in `leen_project_meta`.

```python
# Example API endpoint that invokes the DT workflow
from app.agents.dt_workflow import create_dt_initial_state, get_detection_triage_app

initial_state = create_dt_initial_state(
    user_query=request.query,
    session_id=str(uuid.uuid4()),
    framework_id="hipaa",
    selected_data_sources=tenant_profile.data_sources,   # ← from your tenant API
    active_project_id=tenant_profile.project_id,         # ← from your tenant config
)

app = get_detection_triage_app()
result = app.invoke(initial_state, config={"configurable": {"thread_id": session_id}})
```

---

## Step 5 — Wire DT into the existing compliance workflow (optional)

If you want one unified graph rather than two separate apps, use the integration helper:

```python
# In workflow.py, after build_compliance_workflow() creates the workflow graph:

from app.agents.dt_workflow import add_dt_workflow_to_existing

def build_compliance_workflow() -> StateGraph:
    workflow = StateGraph(EnhancedCompliancePipelineState)
    # ... existing nodes and edges ...

    # Attach DT subgraph
    add_dt_workflow_to_existing(workflow)

    # Add routing from profile_resolver to dt_intent_classifier
    def route_from_profile_resolver(state) -> str:
        intent = state.get("intent", "")
        data_enrichment = state.get("data_enrichment", {})
        
        # Route detection/triage intents to DT workflow
        if intent in ("detection_engineering", "triage_engineering", "full_pipeline"):
            return "dt_intent_classifier"
        
        # ... existing routing ...
        if data_enrichment.get("needs_metrics", False):
            return "metrics_recommender"
        ...

    workflow.add_conditional_edges(
        "profile_resolver",
        route_from_profile_resolver,
        {
            "dt_intent_classifier": "dt_intent_classifier",  # ← add this
            "metrics_recommender": "metrics_recommender",
            "planner": "planner",
            ...
        }
    )

    return workflow
```

When using the integrated approach, `dt_playbook_assembler` routes to the existing
`artifact_assembler` automatically (see `add_dt_workflow_to_existing()`), so the
final output packaging is unified.

---

## Step 6 — Verify `MDLRetrievalService` has `search_project_meta`

**Status:** ✅ **VERIFIED** - `MDLRetrievalService` already has the `search_project_meta` method.

The method is implemented in `app/retrieval/mdl_service.py`:

```python
async def search_project_meta(
    self,
    query: str,
    limit: int = 5,
    project_id: Optional[str] = None
) -> List[MDLProjectMetaResult]:
    """Search leen_project_meta collection for project metadata."""
```

The `dt_retrieve_gold_standard_tables()` function in `dt_tool_integration.py` uses this method and will gracefully return `[]` if there are any errors (caught by `try/except`), so the workflow won't crash.

---

## Architecture modifications vs original design

| Original design | Implemented as |
|---|---|
| `scoring_validator` as separate LLM node | Pure Python scoring (4 dimensions) — no LLM call. Faster, deterministic, no prompt needed. |
| `metrics_lookup` as a dedicated plan step | `dt_metrics_retrieval_node` — reuses `MDLRetrievalService.search_metrics_registry()` exactly as `metrics_recommender_node` does. |
| `playbook_template_hint` drives template selection | Set in planner; used by `dt_scoring_validator_node` routing and `dt_triage_engineer_node` for context injection. |
| Max 3 validation iterations | `MAX_REFINEMENT_ITERATIONS = 3` constant in `dt_workflow.py`. |
| Template C routes detection then triage sequentially | `dt_siem_rule_validator` routes to `dt_triage_engineer` when template is B or C, so both always run. |

---

## Quick test invocation

```python
from app.agents.dt_workflow import get_detection_triage_app, create_dt_initial_state

app = get_detection_triage_app()

state = create_dt_initial_state(
    user_query="Build HIPAA breach detection for credential theft on patient portal",
    session_id="test-001",
    framework_id="hipaa",
    selected_data_sources=["qualys", "okta", "splunk"],
    active_project_id="proj_hipaa_001",
)

result = app.invoke(state, config={"configurable": {"thread_id": "test-001"}})

print(f"SIEM rules: {len(result.get('siem_rules', []))}")
print(f"Metric recommendations: {len(result.get('dt_metric_recommendations', []))}")
print(f"Quality score: {result.get('quality_score', 0):.1f}/100")
print(f"Gap notes: {result.get('dt_gap_notes', [])}")
```
