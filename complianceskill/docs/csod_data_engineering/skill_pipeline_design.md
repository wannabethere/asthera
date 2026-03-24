# CSOD Skill-Based Analysis Pipeline Design Document

**Version:** 1.0
**Status:** Implemented
**Scope:** Skill pipeline enhancement layer for CSOD and DT data analysis workflows
**Related files:** `app/agents/skills/`, `app/agents/csod/workflows/csod_main_graph.py`, `app/agents/mdlworkflows/dt_workflow.py`

---

## 1. Core Principle

> Every analysis type is a **skill** — a data engineer's specialized experience.
> Skills don't replace the pipeline; they make it smarter per analysis type.

Each analysis type (gap analysis, crown jewel, anomaly detection, etc.) is treated as a self-contained skill with its own intent signals, data plan, recommender framing, and validation rules. Skills are an **enhancement layer** over the existing CSOD and DT workflows. When a skill definition exists for the classified intent and the feature flag is enabled, the pipeline gains analysis-specific intelligence. When disabled or absent, the traditional path runs unchanged.

---

## 2. Architecture Overview

### 2.1 Four-Phase Skill Pipeline

Every skill follows the same contract:

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  Phase 1             │     │  Phase 2             │     │  Phase 3             │     │  Phase 4             │
│  INTENT IDENTIFIER   │────▶│  ANALYSIS PLANNER    │────▶│  RECOMMENDER PREP    │────▶│  VALIDATOR           │
│                      │     │                      │     │                      │     │                      │
│  Confirms skill      │     │  Produces data plan  │     │  Injects skill       │     │  Filters metrics     │
│  match, extracts     │     │  (metrics, KPIs,     │     │  instructions into   │     │  using per-skill     │
│  skill-specific      │     │  transformations,    │     │  metrics recommender │     │  penalty/boost rules │
│  parameters          │     │  causal needs)       │     │  prompt              │     │  and thresholds      │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

**Key property:** Each phase is a transparent pass-through when no skill is active (`skill_context = None`). The traditional pipeline flow is never blocked.

### 2.2 Skill Definition Format

Each skill is a declarative JSON file in `app/agents/skills/definitions/`:

```json
{
  "skill_id": "gap_analysis",
  "display_name": "Gap Analysis",
  "description": "Compare current state to a target...",
  "category": "diagnostic",

  "intent_signals": {
    "keywords": ["gap", "shortfall", "target", ...],
    "question_patterns": ["how far are we from...", ...],
    "analysis_requirements": ["requires_target_value"]
  },

  "data_plan": {
    "metric_types": ["current_state"],
    "required_data_elements": ["target_value", "actual_value", "delta", "gap_pct"],
    "kpi_focus": ["completion_rate", "compliance_posture", ...],
    "transformations": [
      "compute delta = target - actual per metric",
      "rank gaps by magnitude",
      ...
    ],
    "dt_config": { ... },
    "cce_config": { ... }
  },

  "recommender_instructions": {
    "framing": "gap-to-target",
    "metric_selection_bias": "prefer metrics with clear target...",
    "output_guidance": "each metric MUST include target_value...",
    "causal_usage": "use causal edges to identify upstream drivers..."
  },

  "validator_rules": {
    "required_fields_per_metric": ["target_value", "current_value"],
    "relevance_threshold": 0.55,
    "max_metrics": 14,
    "penalty_rules": ["penalize metrics without target (-0.15)", ...],
    "boost_rules": ["boost metrics with policy/SLA thresholds (+0.10)", ...]
  },

  "workflows": ["csod", "dt"],
  "executor_compatibility": ["gap_analyzer", "metrics_recommender"]
}
```

### 2.3 Prompt Resolution — Two-Tier System

Skills get their prompts through a two-tier resolution:

| Priority | Source | When Used |
|----------|--------|-----------|
| 1 | `prompts/<skill_id>/<phase>.md` | Dedicated handcrafted prompt — returned verbatim |
| 2 | `prompts/_generic/<phase>.md` | Generic template — interpolated with skill JSON values |
| 3 | Declarative fallback | No LLM call — uses skill definition directly |

The generic templates use `{{placeholder}}` syntax. The `prompt_renderer.py` module interpolates values from the skill definition JSON:

```
{{framing}}                  → "gap-to-target"
{{penalty_rules}}            → bullet list from validator_rules
{{cce_planning_instruction}} → "Causal graph is REQUIRED — plan for csod_causal_edges..."
{{transformations_list}}     → numbered list from data_plan.transformations
```

**Adding a new skill** requires only 1 JSON file. Generic templates handle all 4 phases. To upgrade a skill to dedicated prompts, add 1-4 `.md` files in `prompts/<skill_id>/` — they override the generic version per-phase.

---

## 3. Integration with Existing Workflows

### 3.1 CSOD Workflow Integration

The skill nodes are inserted at three points in the CSOD graph:

```
                              ┌──────────────────────────────────────────┐
                              │         SKILL ENHANCEMENT LAYER          │
                              │  (transparent pass-through when off)     │
                              └──────────────────────────────────────────┘

  csod_followup_router
    │
    ▼
  csod_intent_classifier
    │
    ▼
  ╔══════════════════════════╗
  ║  skill_intent_identifier ║ ◄── Phase 1: refine intent, extract params
  ╠══════════════════════════╣
  ║  skill_analysis_planner  ║ ◄── Phase 2: produce data plan
  ╚══════════════════════════╝
    │
    ▼
  csod_concept_context
    │
    ▼
  csod_planner  (can read skill_data_plan for better planning)
    │
    ▼
  ┌──────────────────────────┐
  │  RETRIEVAL CHAIN          │  spine_precheck → causal_graph → cross_concept_check
  │  (unchanged)              │  → metrics_retrieval → mdl_schema_retrieval
  └──────────────────────────┘
    │
    ▼
  csod_scoring_validator
    │
    ▼
  decision_tree_resolver
    │
    ▼  (routing: _route_execution_target → "skill_recommender_prep")
  ╔══════════════════════════╗
  ║  skill_recommender_prep  ║ ◄── Phase 3: inject skill instructions
  ╚══════════════════════════╝
    │
    ▼
  csod_metrics_recommender  (reads skill_recommender_context for augmented prompting)
    │
    ▼
  ╔══════════════════════════╗
  ║  skill_validator         ║ ◄── Phase 4: filter by skill rules
  ╚══════════════════════════╝
    │
    ▼
  csod_output_format_selector
    │
    ▼
  csod_output_assembler → csod_completion_narration → END
```

**Routing changes:**

| Original Route | New Route |
|---|---|
| `csod_intent_classifier` → `csod_concept_context` | `csod_intent_classifier` → `skill_intent_identifier` → `skill_analysis_planner` → `csod_concept_context` |
| `_route_execution_target` → `csod_metrics_recommender` | `_route_execution_target` → `skill_recommender_prep` → `csod_metrics_recommender` |
| `csod_metrics_recommender` → `csod_output_format_selector` | `csod_metrics_recommender` → `skill_validator` → `csod_output_format_selector` |

**Short-circuit support:** All new routing functions respect `csod_followup_short_circuit`, routing directly to `csod_output_assembler` when the flag is set.

### 3.2 DT Workflow Integration

The DT workflow integrates Phases 1 and 2 only (Phase 3/4 are CSOD-specific since DT uses detection/triage engineers rather than a metrics recommender):

```
  dt_intent_classifier
    │
    ▼
  ╔══════════════════════════╗
  ║  skill_intent_identifier ║ ◄── Phase 1
  ╠══════════════════════════╣
  ║  skill_analysis_planner  ║ ◄── Phase 2
  ╚══════════════════════════╝
    │
    ▼
  dt_planner  (can read skill_data_plan)
    │
    ▼
  [retrieval → scoring → detection/triage chain unchanged]
```

The skill data plan enriches the DT planner's context — it knows what metrics, KPIs, and transformations the analysis requires, leading to better step selection.

### 3.3 Backward Compatibility

The skill pipeline coexists with the existing infrastructure through three mechanisms:

**1. Feature flag:** `skill_pipeline_enabled` (default `False`). When off, all skill nodes set their output state keys to `None` and return immediately.

**2. Backward-compat shim in `intent_config.py`:** The existing `get_dt_config_for_intent()`, `get_cce_enabled_for_intent()`, and `get_cce_mode_for_intent()` functions now check the `SkillRegistry` first. If a skill definition exists for the intent, its `dt_config` / `cce_config` is used. If not, the hardcoded `DT_INTENT_CONFIG` / `CCE_INTENT_CONFIG` dicts serve as fallback.

```python
def get_dt_config_for_intent(intent):
    # 1. Try SkillRegistry
    registry = _try_skill_registry()
    if registry:
        skill = registry.get(key)
        if skill:
            return skill.to_dt_intent_config()
    # 2. Fallback to hardcoded dict
    return DT_INTENT_CONFIG.get(key, {}).copy()
```

**3. State field optionality:** All 6 skill state fields are `Optional` with `total=False` on the `CSODState` TypedDict — existing nodes that don't know about skills are unaffected.

---

## 4. Skill Node Specifications

### 4.1 Phase 1: Skill Intent Identifier (`skill_intent_node.py`)

**Purpose:** After the main intent classifier, refine the classification using the matched skill's intent signals and extract analysis-specific parameters.

| | |
|---|---|
| **Reads** | `csod_intent` or `intent`, `user_query`, `compliance_profile`, `skill_pipeline_enabled` |
| **Writes** | `skill_context`: `{skill_id, confirmed, confidence, extracted_params, analysis_requirements}` |
| **LLM** | Optional — uses `intent_identifier.md` prompt if available; declarative fallback otherwise |
| **Pass-through** | When `skill_pipeline_enabled=False`, no matching skill, or skill not compatible with workflow |

**Extracted parameters** (skill-specific):
- Gap analysis: `target_value`, `target_source`, `comparison_dimension`, `gap_direction`
- Anomaly detection: `time_window`, `baseline_window`, `sensitivity`, `anomaly_type`
- Crown jewel: `scope_constraint`, `prioritization_axis`, `audience`
- Generic: `scope`, `dimension`, `time_window`, `mentioned_metrics`

### 4.2 Phase 2: Skill Analysis Planner (`skill_planner_node.py`)

**Purpose:** Produce a structured data plan that downstream nodes consume. Not code — a plan of what metrics, KPIs, transformations, and causal context are needed.

| | |
|---|---|
| **Reads** | `skill_context`, `user_query`, `data_enrichment`, `selected_data_sources`, `compliance_profile` |
| **Writes** | `skill_data_plan`: `{required_metrics, required_kpis, transformations, mdl_scope, causal_needs}` |
| **LLM** | Optional — uses `analysis_planner.md` prompt; declarative fallback from `skill.data_plan` |
| **Pass-through** | When `skill_context` is `None` or `confirmed=False` |

**Data plan structure:**

```json
{
  "required_metrics": {
    "primary": ["completion_rate", "compliance_posture"],
    "secondary": ["overdue_rate"]
  },
  "transformations": [
    {"name": "gap_delta", "formula": "target - actual", "per": "metric"}
  ],
  "mdl_scope": {
    "required_tables": ["training_completions"],
    "required_columns": ["completion_rate", "target_rate"]
  },
  "causal_needs": {
    "mode": "required",
    "usage": "upstream_driver_identification",
    "depth": 2
  }
}
```

### 4.3 Phase 3: Skill Recommender Prep (`skill_recommender_node.py`)

**Purpose:** Prepare skill-specific context for the existing metrics recommender. Does NOT replace the recommender — injects augmentation context.

| | |
|---|---|
| **Reads** | `skill_context`, `skill_data_plan` |
| **Writes** | `skill_recommender_context`: `{skill_block, metric_instructions, data_plan, framing, output_guidance}` |
| **LLM** | None — pure context preparation |
| **Pass-through** | When `skill_context` is `None` |

The existing `csod_metrics_recommender` reads `skill_recommender_context` and, if present, appends the skill context block and metric instructions to its system prompt. A utility function is provided:

```python
from app.agents.skills.nodes.skill_recommender_node import get_skill_augmented_prompt

# In csod_metrics_recommender_node:
prompt_text = get_skill_augmented_prompt(base_prompt, state)
```

### 4.4 Phase 4: Skill Validator (`skill_validator_node.py`)

**Purpose:** Post-recommendation filtering using skill-specific penalty/boost rules and relevance thresholds.

| | |
|---|---|
| **Reads** | `skill_context`, `csod_metric_recommendations` or `dt_scored_metrics` |
| **Writes** | `skill_validated_metrics`, `skill_validation_report`, overwrites `csod_metric_recommendations` |
| **LLM** | Optional — uses `validator.md` prompt for nuanced checks (dedup, field completeness) |
| **Pass-through** | When `skill_context` is `None` |

**Validation pipeline:**

```
Metrics from recommender
    │
    ▼
Phase 4a: Rule-based scoring
    ├── Apply penalty_rules (keyword match → score adjustment)
    ├── Apply boost_rules (keyword match → score adjustment)
    ├── Check required_fields_per_metric
    └── Filter by relevance_threshold
    │
    ▼
Phase 4b: LLM validation (optional)
    ├── Deduplication checks
    ├── Field completeness verification
    └── Cross-metric consistency
    │
    ▼
Phase 4c: Caps and safety nets
    ├── Apply max_metrics cap (keep top N by adjusted score)
    └── Minimum metrics safety net (lower threshold if < 3 pass)
    │
    ▼
Overwrite csod_metric_recommendations with validated set
```

---

## 5. State Schema Extensions

Six new fields added to `CSODState` (all `Optional`, `total=False`):

| Field | Type | Phase | Description |
|---|---|---|---|
| `skill_pipeline_enabled` | `bool` | — | Feature flag. Default `False` = all skill nodes pass-through |
| `skill_context` | `Dict` | 1 | Skill match confirmation + extracted params |
| `skill_data_plan` | `Dict` | 2 | Data plan: required metrics, KPIs, transformations, causal needs |
| `skill_recommender_context` | `Dict` | 3 | Injected recommender instructions and skill context block |
| `skill_validated_metrics` | `List[Dict]` | 4 | Post-validation filtered metric list |
| `skill_validation_report` | `Dict` | 4 | Validation report: kept/dropped/warnings/summary |

---

## 6. Skill Registry

### 6.1 Singleton Pattern

`SkillRegistry` is a singleton that loads all skill definitions from `app/agents/skills/definitions/*.json` on first access:

```python
from app.agents.skills import SkillRegistry

registry = SkillRegistry.instance()
skill = registry.get("gap_analysis")
```

### 6.2 Registry API

| Method | Returns | Description |
|---|---|---|
| `get(skill_id)` | `AnalysisSkill` or `None` | Look up skill by ID |
| `has(skill_id)` | `bool` | Check existence |
| `all_skill_ids()` | `List[str]` | All loaded skill IDs |
| `skills_for_workflow(wf)` | `Dict[str, AnalysisSkill]` | Skills available to a workflow ("csod" or "dt") |
| `resolve_skill_for_intent(intent)` | `AnalysisSkill` or `None` | Map pipeline intent to skill |
| `get_skill_context_block(intent)` | `str` or `None` | Markdown context block for prompt injection |
| `get_skill_prompt(intent, phase)` | `str` or `None` | Load phase prompt for intent's skill |
| `export_dt_intent_config()` | `Dict` | Legacy-compatible DT_INTENT_CONFIG |
| `export_cce_intent_config()` | `Dict` | Legacy-compatible CCE_INTENT_CONFIG |
| `export_catalog_entries()` | `Dict` | Legacy-compatible INTENT_CATALOG_ENTRIES |

---

## 7. Implemented Skills

### 7.1 Skills with Dedicated Prompts (Tier 1)

| Skill | Category | CCE | Workflows | Dedicated Prompts |
|---|---|---|---|---|
| `gap_analysis` | diagnostic | required | csod, dt | 4 files |
| `crown_jewel_analysis` | diagnostic | required | csod | 4 files |
| `anomaly_detection` | diagnostic | required | csod, dt | 4 files |

### 7.2 Skills Using Generic Templates (Tier 2)

| Skill | Category | CCE | Workflows |
|---|---|---|---|
| `predictive_risk_analysis` | predictive | required | csod, dt |
| `funnel_analysis` | exploratory | optional | csod |
| `cohort_analysis` | exploratory | optional | csod |
| `benchmark_analysis` | exploratory | disabled | csod |
| `skill_gap_analysis` | diagnostic | optional | csod |
| `behavioral_analysis` | diagnostic | required | csod |
| `training_roi_analysis` | diagnostic | required | csod |
| `compliance_test_generator` | operational | optional | csod |

### 7.3 Intent-to-Skill Mapping

These intents DO NOT have skills (they are output/presentation types, not analysis types):

| Intent | Reason |
|---|---|
| `metrics_dashboard_plan` | Output format — how the user sees results |
| `dashboard_generation_for_persona` | Output format |
| `metrics_recommender_with_gold_plan` | Output format |
| `metric_kpi_advisor` | Advisory mode — not a structured analysis |
| `data_discovery` | Data intelligence — skips DT, no analysis pipeline |
| `data_quality_analysis` | Data intelligence |
| `data_lineage` | Data intelligence |
| `data_planner` | Data engineering — produces pipeline specs, not analysis |

This separation reflects the core distinction: **analysis intents** (what analysis to perform) vs **output intents** (how the user sees results).

---

## 8. Configuration Consolidation

The skill definition JSON consolidates configuration that was previously spread across multiple locations:

| Previously In | Now Also In Skill Definition |
|---|---|
| `DT_INTENT_CONFIG[intent]` | `skill.data_plan.dt_config` |
| `CCE_INTENT_CONFIG[intent]` | `skill.data_plan.cce_config` |
| `INTENT_CATALOG_ENTRIES[intent]` | `skill.description` + `skill.intent_signals` |
| Hardcoded `THRESHOLD` in `scoring_validator` | `skill.validator_rules.relevance_threshold` |
| Prompt fragments in `node_recommender.py` | `skill.prompts/metric_instructions.md` |

The existing `intent_config.py` dicts are preserved as fallbacks. When a skill definition exists, it takes precedence via the backward-compat shim.

---

## 9. Directory Structure

```
app/agents/skills/
├── __init__.py                      # SkillRegistry singleton + exports
├── base_skill.py                    # AnalysisSkill dataclass + nested configs
├── skill_loader.py                  # Discovers and loads definitions from disk
├── prompt_renderer.py               # Interpolates generic templates with skill values
│
├── definitions/                     # One JSON per skill (11 files)
│   ├── gap_analysis.json
│   ├── crown_jewel_analysis.json
│   ├── anomaly_detection.json
│   ├── predictive_risk_analysis.json
│   ├── funnel_analysis.json
│   ├── cohort_analysis.json
│   ├── benchmark_analysis.json
│   ├── skill_gap_analysis.json
│   ├── behavioral_analysis.json
│   ├── training_roi_analysis.json
│   └── compliance_test_generation.json
│
├── prompts/
│   ├── _generic/                    # Generic templates (4 files)
│   │   ├── intent_identifier.md
│   │   ├── analysis_planner.md
│   │   ├── metric_instructions.md
│   │   └── validator.md
│   ├── gap_analysis/                # Dedicated prompts (4 files each)
│   │   ├── intent_identifier.md
│   │   ├── analysis_planner.md
│   │   ├── metric_instructions.md
│   │   └── validator.md
│   ├── crown_jewel_analysis/        # Dedicated prompts
│   │   └── ...
│   └── anomaly_detection/           # Dedicated prompts
│       └── ...
│
└── nodes/                           # Generic LangGraph node functions
    ├── __init__.py
    ├── skill_intent_node.py         # Phase 1
    ├── skill_planner_node.py        # Phase 2
    ├── skill_recommender_node.py    # Phase 3
    └── skill_validator_node.py      # Phase 4
```

---

## 10. Extensibility

### Adding a New Analysis Skill

**Minimum (1 file):** Create `definitions/<skill_id>.json` with the skill definition. The generic templates handle all 4 phases. The SkillRegistry picks it up automatically on next load.

**Enhanced (1 JSON + 1-4 prompts):** Add dedicated prompts in `prompts/<skill_id>/` for any phase that needs handcrafted instructions. Dedicated prompts override the generic template for that phase only.

**No code changes required.** No modifications to `intent_config.py`, node files, workflow graphs, or routing logic.

### Upgrading a Generic Skill to Dedicated

1. Create `prompts/<skill_id>/` directory
2. Add `.md` files for any phase that needs custom instructions
3. The `get_prompt()` resolution automatically prefers the dedicated file

### Using Skills in a New Workflow

1. Add the workflow name to the skill's `"workflows"` array
2. Wire `skill_intent_identifier_node` and `skill_analysis_planner_node` into the new workflow graph
3. Optionally wire `skill_recommender_node` and `skill_validator_node` if the workflow has a metrics recommender

---

## 11. Activation

To enable the skill pipeline for a workflow invocation, set `skill_pipeline_enabled=True` in the initial state:

```python
initial_state = {
    "user_query": "Where are we falling short on compliance training targets?",
    "skill_pipeline_enabled": True,
    # ... other state fields
}
```

When the flag is `False` (default), all skill nodes execute as no-ops:
- `skill_context` → `None`
- `skill_data_plan` → `None`
- `skill_recommender_context` → `None`
- `skill_validated_metrics` → `None`

The traditional CSOD/DT pipeline runs exactly as before.

---

## 12. Observability

All skill nodes append step records to `state["execution_steps"]` with `agent_name` prefixed by `"skill:"`:

```json
{
  "step_name": "skill_intent_identifier",
  "agent_name": "skill:gap_analysis",
  "timestamp": "2026-03-23T...",
  "status": "completed",
  "inputs": {"skill_id": "gap_analysis"},
  "outputs": {"confirmed": true}
}
```

The `skill_validation_report` provides detailed filtering visibility:

```json
{
  "summary": {
    "total_candidates": 22,
    "passed": 14,
    "dropped": 6,
    "warnings": 2
  },
  "dropped_metrics": [
    {"metric_id": "...", "reason": "below_threshold", "adjusted_score": 0.42}
  ]
}
```
