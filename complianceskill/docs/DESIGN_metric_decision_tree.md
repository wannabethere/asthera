# Metric Decision Tree Engine — Implementation Design

## 1. Problem Statement

The current DT workflow generates metrics/KPIs via freeform LLM prompts in `dt_detection_engineer_node` and `dt_triage_engineer_node`. This produces inconsistent, unstructured recommendations with no systematic way to align metrics to user goals, audience, or compliance use case (SOC2 audit vs. LMS learning targets).

The decision tree engine introduces structured, goal-driven metric selection that mirrors the existing template registry pattern (`registry_unified.py`) while integrating cleanly into the LangGraph DT workflow.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DT Workflow (LangGraph)                   │
│                                                             │
│  dt_intent_classifier → dt_planner                         │
│    → dt_framework_retrieval                                 │
│      → dt_metrics_retrieval                                 │
│        → dt_mdl_schema_retrieval                            │
│          → calculation_needs_assessment                      │
│            ┌──────────────────────────────────┐             │
│            │  NEW: dt_metric_decision_node     │             │
│            │  ┌─────────────────────────────┐ │             │
│            │  │ 1. Auto-resolve decisions   │ │             │
│            │  │ 2. Score all metrics        │ │             │
│            │  │ 3. Group by goal            │ │             │
│            │  │ 4. Validate coverage        │ │             │
│            │  └─────────────────────────────┘ │             │
│            └──────────────────────────────────┘             │
│              → dt_scoring_validator                          │
│                → dt_detection_engineer / dt_triage_engineer  │
│                  → ...                                       │
└─────────────────────────────────────────────────────────────┘
```

### New Modules

| Module | Purpose |
|--------|---------|
| `metric_decision_tree.py` | Decision tree structure, question definitions, auto-resolve from user query |
| `metric_scoring.py` | Weighted scoring engine that ranks metrics against resolved decisions |
| `metric_grouping.py` | Groups scored metrics into goal-aligned insight groups with KPI/metric/trend slots |
| `dt_metric_decision_nodes.py` | Two LangGraph nodes: `dt_metric_decision_node` (auto-resolve + score + group) and `dt_metric_decision_interactive_node` (conversational clarification) |

### Modified Modules

| Module | Change |
|--------|--------|
| `dt_workflow.py` | Insert `dt_metric_decision_node` after `calculation_needs_assessment`, before `dt_scoring_validator` |
| `dt_nodes.py` | Detection/triage engineers consume `dt_metric_groups` from state instead of raw `resolved_metrics` |
| `state.py` (EnhancedCompliancePipelineState) | Add `dt_metric_decisions`, `dt_scored_metrics`, `dt_metric_groups` fields |

---

## 3. Decision Tree Structure

### 3.1 Questions

Six decision axes, each mapping to metric attributes:

| # | Question Key | Question | Options | Maps To |
|---|-------------|----------|---------|---------|
| 1 | `use_case` | What is the compliance use case? | `soc2_audit`, `lms_learning_target`, `risk_posture_report`, `executive_dashboard`, `operational_monitoring` | `goal_filter`, `audience`, `aggregation_level` |
| 2 | `goal` | What is the primary measurement goal? | `compliance_posture`, `incident_triage`, `control_effectiveness`, `risk_exposure`, `training_completion`, `remediation_velocity` | `metric_categories`, `kpi_types` |
| 3 | `focus_area` | Which domain is the priority? | `access_control`, `audit_logging`, `vulnerability_management`, `incident_response`, `change_management`, `data_protection`, `training_compliance` | `control_domains`, `risk_categories` |
| 4 | `audience` | Who consumes these metrics? | `security_ops`, `compliance_team`, `executive_board`, `risk_management`, `learning_admin`, `auditor` | `aggregation_level`, `complexity`, `visualization_type` |
| 5 | `timeframe` | What time granularity? | `realtime`, `hourly`, `daily`, `weekly`, `monthly`, `quarterly` | `aggregation_window`, `medallion_layer` |
| 6 | `metric_type` | What type of insight? | `counts`, `rates`, `percentages`, `scores`, `distributions`, `comparisons`, `trends` | `metric_type` filter |

### 3.2 Option-to-Attribute Mapping

Each option carries a **tag bundle** — a set of attribute tags that the scoring engine matches against metric metadata.

```python
# Example: use_case="soc2_audit"
{
    "option_id": "soc2_audit",
    "tags": {
        "goal_filter": ["compliance_posture", "control_effectiveness"],
        "audience": ["compliance_team", "auditor", "executive_board"],
        "aggregation_level": "summary",
        "framework_hint": "soc2",
        "required_groups": ["compliance_posture", "control_effectiveness", "risk_exposure"],
    }
}
```

### 3.3 Auto-Resolve Strategy

The engine extracts decisions from three signal sources, in priority order:

1. **Explicit state fields** — `framework_id`, `intent`, `data_enrichment.suggested_focus_areas`, `data_enrichment.metrics_intent`
2. **User query keyword matching** — weighted keyword hints (identical pattern to `registry_unified.py`)
3. **Scored context signals** — presence of controls/risks/schemas implies focus areas

If auto-resolve confidence is below threshold (< 0.6 for any question), the interactive node emits a clarification request.

---

## 4. Scoring Engine

### 4.1 Metric Attribute Requirements

Each metric in `metrics_registry.json` needs these fields (some already exist, others are new):

**Existing fields (no change):**
- `id`, `name`, `description`, `category`
- `source_schemas`, `source_capabilities`
- `data_filters`, `data_groups`
- `kpis`, `trends`
- `natural_language_question`

**New fields to add:**

```json
{
  "goals": ["compliance_posture", "control_effectiveness"],
  "focus_areas": ["vulnerability_management", "patch_compliance"],
  "audience_levels": ["security_ops", "compliance_team"],
  "metric_type": "percentage",
  "aggregation_windows": ["daily", "weekly", "monthly"],
  "use_cases": ["soc2_audit", "risk_posture_report"],
  "mapped_control_domains": ["CC6", "CC7"],
  "mapped_risk_categories": ["unauthorized_access", "unpatched_systems"],
  "group_affinity": ["compliance_posture", "risk_exposure"]
}
```

### 4.2 Scoring Weights

| Dimension | Weight | Match Logic |
|-----------|--------|-------------|
| `use_case` match | 30 | metric.use_cases ∩ decisions.use_case |
| `goal` match | 25 | metric.goals ∩ decisions.goal |
| `focus_area` match | 20 | metric.focus_areas ∩ decisions.focus_area |
| `control_domain` overlap | 15 | metric.mapped_control_domains ∩ scored_context.controls[].domain |
| `risk_category` overlap | 15 | metric.mapped_risk_categories ∩ scored_context.risks[].category |
| `metric_type` match | 10 | metric.metric_type == decisions.metric_type |
| `data_source` availability | 10 | metric.source_capabilities ∩ dt_data_sources_in_scope |
| `timeframe` match | 10 | decisions.timeframe ∈ metric.aggregation_windows |
| `audience` appropriateness | 5 | decisions.audience ∈ metric.audience_levels |
| **Vector similarity boost** | 10 | Qdrant semantic score from existing `search_metrics_registry` |

**Max possible score: 150**

Normalization: `composite_score = raw_score / 150.0`

### 4.3 Threshold and Selection

| Score Range | Action |
|-------------|--------|
| ≥ 0.70 | **Include** — high confidence match |
| 0.50–0.69 | **Include with flag** — `low_confidence=True` |
| 0.35–0.49 | **Candidate pool** — included only if minimum coverage not met |
| < 0.35 | **Excluded** — recorded in `dt_dropped_metrics` |

**Minimum coverage rules:**
- At least 3 metrics per required group (from use_case.required_groups)
- At least 1 KPI-eligible metric per group
- At least 5 total metrics across all groups

If minimums aren't met, lower threshold to 0.35 for underserved groups only.

---

## 5. Metric Grouping

### 5.1 Group Definitions

Groups are defined per use_case and goal combination:

```python
METRIC_GROUPS = {
    "compliance_posture": {
        "group_id": "compliance_posture",
        "group_name": "Compliance Posture Overview",
        "goal": "Monitor overall compliance status against framework controls",
        "slots": {
            "kpis": {"min": 2, "max": 5, "prefer_types": ["percentage", "score"]},
            "metrics": {"min": 3, "max": 8, "prefer_types": ["count", "rate"]},
            "trends": {"min": 1, "max": 3, "prefer_types": ["trend"]},
        },
        "visualization_suggestions": ["gauge", "scorecard", "trend_line"],
        "audience": ["compliance_team", "executive_board", "auditor"],
        "priority": "high",
    },
    "control_effectiveness": {
        "group_id": "control_effectiveness",
        "group_name": "Control Effectiveness",
        "goal": "Measure how well individual controls mitigate their target risks",
        "slots": {
            "kpis": {"min": 2, "max": 4},
            "metrics": {"min": 3, "max": 10},
            "trends": {"min": 1, "max": 3},
        },
        "visualization_suggestions": ["heatmap", "bar_chart", "status_matrix"],
        "audience": ["security_ops", "compliance_team"],
        "priority": "high",
    },
    "risk_exposure": {
        "group_id": "risk_exposure",
        "group_name": "Risk Exposure Dashboard",
        "goal": "Quantify and track risk exposure across the environment",
        "slots": {
            "kpis": {"min": 2, "max": 4},
            "metrics": {"min": 3, "max": 8},
            "trends": {"min": 2, "max": 4},
        },
        "visualization_suggestions": ["risk_matrix", "trend_line", "gauge"],
        "audience": ["risk_management", "executive_board"],
        "priority": "high",
    },
    "operational_security": {
        "group_id": "operational_security",
        "group_name": "Operational Security Metrics",
        "goal": "Track day-to-day security operations efficiency",
        "slots": {
            "kpis": {"min": 2, "max": 5},
            "metrics": {"min": 4, "max": 12},
            "trends": {"min": 2, "max": 4},
        },
        "visualization_suggestions": ["time_series", "bar_chart", "table"],
        "audience": ["security_ops"],
        "priority": "medium",
    },
    "training_completion": {
        "group_id": "training_completion",
        "group_name": "Training & Learning Targets",
        "goal": "Track LMS training completion rates against compliance targets",
        "slots": {
            "kpis": {"min": 2, "max": 4},
            "metrics": {"min": 3, "max": 6},
            "trends": {"min": 1, "max": 2},
        },
        "visualization_suggestions": ["progress_bar", "scorecard", "table"],
        "audience": ["learning_admin", "compliance_team"],
        "priority": "medium",
    },
    "remediation_velocity": {
        "group_id": "remediation_velocity",
        "group_name": "Remediation Velocity",
        "goal": "Measure speed and completeness of vulnerability and finding remediation",
        "slots": {
            "kpis": {"min": 2, "max": 4},
            "metrics": {"min": 3, "max": 8},
            "trends": {"min": 2, "max": 3},
        },
        "visualization_suggestions": ["funnel", "trend_line", "bar_chart"],
        "audience": ["security_ops", "compliance_team"],
        "priority": "medium",
    },
}
```

### 5.2 Slot Assignment Algorithm

1. Sort scored metrics by `composite_score` descending
2. For each required group (from `use_case.required_groups`):
   a. Filter metrics whose `group_affinity` includes this group
   b. Assign to KPI slot if metric has KPI-eligible type AND slot not full
   c. Assign to metric slot if slot not full
   d. Assign to trend slot if metric has trend capability AND slot not full
3. Overflow metrics (high score but all slots full) go to an "additional_metrics" pool
4. Validate minimum slot counts; pull from candidate pool if needed

### 5.3 Output Schema

```python
{
    "decision_summary": {
        "use_case": "soc2_audit",
        "goal": "compliance_posture",
        "focus_area": "vulnerability_management",
        "audience": "compliance_team",
        "timeframe": "monthly",
        "metric_type": "percentages",
        "auto_resolve_confidence": 0.85,
        "resolved_from": ["state_fields", "keyword_hints"],
    },
    "groups": [
        {
            "group_id": "compliance_posture",
            "group_name": "Compliance Posture Overview",
            "goal": "Monitor overall compliance status",
            "priority": "high",
            "audience": ["compliance_team", "auditor"],
            "visualization_suggestions": ["gauge", "scorecard"],
            "kpis": [
                {
                    "metric_id": "vuln_count_by_severity",
                    "name": "Vulnerability Count by Severity",
                    "composite_score": 0.87,
                    "role": "kpi",
                    "mapped_controls": ["CC7.1"],
                    "mapped_risks": ["unpatched_systems"],
                    "source_schemas": ["vulnerability_instances_schema"],
                }
            ],
            "metrics": [...],
            "trends": [...],
        }
    ],
    "coverage_report": {
        "total_metrics_scored": 45,
        "total_metrics_selected": 18,
        "groups_with_full_coverage": 3,
        "groups_with_partial_coverage": 1,
        "unserved_groups": [],
        "dropped_metrics_count": 27,
    }
}
```

---

## 6. Additional Data Sources Required

### 6.1 Metric Registry Enrichment

The existing `metrics_registry.json` entries need the new fields from §4.1. This requires a one-time enrichment pass.

**Approach:** Create a migration script that:
1. Reads each metric from the registry
2. Infers `goals`, `focus_areas`, `use_cases`, `audience_levels`, `metric_type`, `aggregation_windows`, `mapped_control_domains`, `mapped_risk_categories`, `group_affinity` from existing fields (`category`, `kpis`, `data_filters`, `source_capabilities`)
3. Writes enriched metrics back to registry and re-indexes in Qdrant

**Inference rules:**

| Existing Field | Inferred New Field |
|---|---|
| `category: "vulnerabilities"` | `focus_areas: ["vulnerability_management"]`, `goals: ["risk_exposure", "compliance_posture"]` |
| `category: "access_control"` | `focus_areas: ["access_control"]`, `goals: ["compliance_posture", "control_effectiveness"]` |
| `kpis` contains "count" | `metric_type: "count"` |
| `kpis` contains "rate" or "time" | `metric_type: "rate"` |
| `trends` non-empty | `aggregation_windows: ["daily", "weekly"]` |
| `source_capabilities` contains "qualys" | `use_cases: ["soc2_audit", "risk_posture_report"]` |

### 6.2 Use Case → Group Mapping Registry

New JSON file: `metric_use_case_groups.json`

Maps each use_case to its required groups, default audience, default timeframe, and framework-specific overrides.

```json
{
  "soc2_audit": {
    "required_groups": ["compliance_posture", "control_effectiveness", "risk_exposure"],
    "optional_groups": ["operational_security", "remediation_velocity"],
    "default_audience": "auditor",
    "default_timeframe": "monthly",
    "framework_overrides": {
      "soc2": {
        "control_domain_prefix": "CC",
        "additional_required_groups": []
      }
    }
  },
  "lms_learning_target": {
    "required_groups": ["training_completion", "compliance_posture"],
    "optional_groups": ["control_effectiveness"],
    "default_audience": "learning_admin",
    "default_timeframe": "quarterly",
    "lms_specific": {
      "requires_lms_schemas": true,
      "target_schemas": ["cornerstone_learning_*", "sumtotal_*"]
    }
  }
}
```

### 6.3 Control Domain Taxonomy

New or extended mapping from framework control codes to domain categories, needed for `mapped_control_domains` scoring:

```json
{
  "soc2": {
    "CC6": {"domain": "access_control", "focus_areas": ["access_control", "authentication_mfa"]},
    "CC7": {"domain": "system_operations", "focus_areas": ["vulnerability_management", "incident_response"]},
    "CC8": {"domain": "change_management", "focus_areas": ["change_management"]},
    "CC9": {"domain": "risk_mitigation", "focus_areas": ["risk_exposure"]}
  },
  "hipaa": {
    "164.312(a)": {"domain": "access_control", "focus_areas": ["access_control"]},
    "164.312(b)": {"domain": "audit_controls", "focus_areas": ["audit_logging"]}
  }
}
```

### 6.4 LMS Schema Extensions (for learning target use case)

When `use_case == "lms_learning_target"`, the engine needs LMS-specific metrics that map to Cornerstone OnDemand or SumTotal schemas already in Qdrant. These require:

- `training_completion_rate` metric → `cornerstone_learning_assignment` schema
- `overdue_training_count` metric → `cornerstone_learning_assignment` schema
- `certification_expiry_rate` metric → `cornerstone_certification` schema
- `learning_hours_per_employee` metric → `cornerstone_learning_transcript` schema

These should be added to `metrics_registry.json` with `use_cases: ["lms_learning_target"]`.

---

## 7. Workflow Integration

### 7.1 Node Insertion Point

```
BEFORE:
  calculation_needs_assessment → (conditional) → calculation_planner → dt_scoring_validator

AFTER:
  calculation_needs_assessment → (conditional) → calculation_planner
    → dt_metric_decision_node → dt_scoring_validator
```

### 7.2 Routing Logic

```python
def _route_after_calculation_planner(state) -> str:
    # If metrics are needed, run decision tree; else skip
    data_enrichment = state.get("data_enrichment", {})
    if data_enrichment.get("needs_metrics", False):
        return "dt_metric_decision_node"
    return "dt_scoring_validator"

def _route_after_metric_decision(state) -> str:
    # If auto-resolve confidence is low and interactive mode is on
    confidence = state.get("dt_metric_decisions", {}).get("auto_resolve_confidence", 1.0)
    interactive = state.get("dt_metric_interactive_mode", False)
    if confidence < 0.6 and interactive:
        return "dt_metric_decision_interactive_node"
    return "dt_scoring_validator"
```

### 7.3 State Extensions

Add to `EnhancedCompliancePipelineState` / `create_dt_initial_state`:

```python
# Decision tree fields
"dt_metric_decisions": {},          # Resolved decision values
"dt_scored_metrics": [],            # All metrics with composite scores
"dt_metric_groups": [],             # Grouped metric recommendations
"dt_metric_coverage_report": {},    # Coverage validation report
"dt_metric_interactive_mode": False, # Whether to ask clarifying questions
"dt_metric_dropped": [],            # Metrics below threshold
```

### 7.4 Downstream Consumer Changes

**`dt_detection_engineer_node`** (Phase 2 metrics prompt):
- Instead of passing raw `resolved_metrics` as "for reference"
- Pass `dt_metric_groups` as structured context
- The LLM uses pre-scored, pre-grouped metrics to generate KPIs with correct mappings

**`dt_triage_engineer_node`**:
- Receives `dt_metric_groups` with slot assignments
- Uses group structure to organize medallion plan entries
- Each medallion entry references the group it belongs to

**`dt_playbook_assembler_node`**:
- Includes `dt_metric_groups` in the playbook sections
- Adds coverage report to gap analysis

---

## 8. Implementation Order

| Phase | Files | Effort |
|-------|-------|--------|
| **Phase 1: Core engine** | `metric_decision_tree.py`, `metric_scoring.py`, `metric_grouping.py` | 2–3 days |
| **Phase 2: Node integration** | `dt_metric_decision_nodes.py`, `dt_workflow.py` changes, state extensions | 1–2 days |
| **Phase 3: Registry enrichment** | Migration script for `metrics_registry.json`, `metric_use_case_groups.json`, control domain taxonomy | 1–2 days |
| **Phase 4: Downstream consumers** | Modify detection/triage engineer prompts to consume groups | 1 day |
| **Phase 5: LMS extensions** | Add LMS-specific metrics, schema mappings | 1 day |

---

## 9. Key Design Decisions

1. **Auto-resolve first, ask later** — The engine always attempts full auto-resolution. Interactive clarification is optional and only triggered when confidence is low. This preserves the existing non-interactive pipeline flow.

2. **Scoring is deterministic, not LLM-based** — The scoring function uses weighted attribute matching (no LLM call). This makes it fast, reproducible, and testable. The LLM is used only downstream to generate natural-language recommendations from the scored groups.

3. **Group structure drives medallion plan** — Each metric group maps 1:1 to a medallion plan section. This gives the triage engineer structured context instead of a flat metric list.

4. **Use case is the root decision** — SOC2 audit vs. LMS learning target fundamentally changes which groups are required, which schemas are relevant, and which audience the output serves. Everything flows from this root.

5. **Backward compatible** — If `dt_metric_decisions` is empty (old workflow), the scoring validator and engineers fall back to the existing `resolved_metrics` behavior. No breaking changes.
