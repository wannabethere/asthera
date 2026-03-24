# Skill-Based Analysis Architecture Plan

## Concept

Treat each analysis type (gap analysis, crown jewel, anomaly detection, etc.) as a **skill** — like a data engineer's specialized experience. Each skill is self-contained with its own 4-phase pipeline:

```
Intent Identifier → Analysis Planner → Metric Recommender/Generator → Validator
```

Skills are **shared** between `csod_workflow` and `dt_workflow` — same skill definition, different data contexts.

---

## Architecture: `app/agents/skills/`

### Directory Structure

```
app/agents/skills/
├── __init__.py                    # SkillRegistry, load_skill(), get_skill()
├── base_skill.py                  # BaseAnalysisSkill abstract class
├── skill_loader.py                # JSON/YAML skill definition loader
│
├── definitions/                   # One file per skill — declarative config
│   ├── gap_analysis.json
│   ├── crown_jewel_analysis.json
│   ├── anomaly_detection.json
│   ├── coverage_analysis.json
│   ├── predictive_risk_analysis.json
│   ├── funnel_analysis.json
│   ├── cohort_analysis.json
│   ├── benchmark_analysis.json
│   ├── skill_gap_analysis.json
│   ├── behavioral_analysis.json
│   ├── training_roi_analysis.json
│   ├── compliance_test_generation.json
│   └── data_planner.json
│
├── prompts/                       # Per-skill prompt templates (4 per skill)
│   ├── gap_analysis/
│   │   ├── intent_identifier.md
│   │   ├── analysis_planner.md
│   │   ├── metric_instructions.md
│   │   └── validator.md
│   ├── crown_jewel_analysis/
│   │   ├── intent_identifier.md
│   │   ├── analysis_planner.md
│   │   ├── metric_instructions.md
│   │   └── validator.md
│   └── ...                        # same 4 files per skill
│
└── nodes/                         # Shared LangGraph node functions
    ├── skill_intent_node.py       # Uses skill's intent_identifier.md
    ├── skill_planner_node.py      # Uses skill's analysis_planner.md
    ├── skill_recommender_node.py  # Uses skill's metric_instructions.md
    └── skill_validator_node.py    # Uses skill's validator.md
```

### Skill Definition Format (e.g., `gap_analysis.json`)

Each skill is a declarative JSON that describes the skill's experience profile:

```json
{
  "skill_id": "gap_analysis",
  "display_name": "Gap Analysis",
  "description": "Compare current state to a target/SLA/policy and quantify the gap",
  "category": "diagnostic",

  "intent_signals": {
    "keywords": ["gap", "shortfall", "target", "behind", "falling short"],
    "question_patterns": ["how far are we from", "what's the gap between"],
    "analysis_requirements": ["requires_target_value"]
  },

  "data_plan": {
    "metric_types": ["current_state"],
    "required_data_elements": ["target_value", "actual_value", "delta"],
    "kpi_focus": ["completion_rate", "compliance_posture", "certification_coverage"],
    "transformations": [
      "compute delta = target - actual per metric",
      "rank gaps by magnitude",
      "group by focus_area or org_unit"
    ],
    "dt_config": {
      "use_case": "lms_learning_target",
      "goal": null,
      "metric_type": "current_state",
      "dt_group_by": "goal",
      "min_composite": 0.55,
      "requires_target_value": true
    },
    "cce_config": {
      "enabled": true,
      "mode": "required",
      "provides": "csod_causal_edges",
      "uses": "root cause decomposition via Shapley attribution"
    }
  },

  "recommender_instructions": {
    "framing": "gap-to-target",
    "metric_selection_bias": "prefer metrics with clear target/threshold definitions",
    "output_guidance": "each recommended metric must include target_value, current_value, gap_delta, gap_pct",
    "causal_usage": "use causal edges to identify upstream drivers of each gap"
  },

  "validator_rules": {
    "required_fields_per_metric": ["target_value", "current_value"],
    "relevance_threshold": 0.55,
    "max_metrics": 14,
    "penalty_rules": [
      "penalize metrics without a computable target (-0.15)",
      "penalize trend-only metrics for current_state intent (-0.10)"
    ],
    "boost_rules": [
      "boost metrics with explicit policy/SLA thresholds (+0.10)",
      "boost metrics aligned with causal terminal nodes (+0.05)"
    ]
  },

  "workflows": ["csod", "dt"],
  "executor_compatibility": ["gap_analyzer", "metrics_recommender"]
}
```

---

## The 4-Phase Skill Pipeline

### Phase 1: Skill Intent Identifier (`skill_intent_node.py`)

**When:** After the main intent classifier (csod or dt) classifies the high-level intent, the skill intent node refines it using the matched skill's `intent_identifier.md`.

**What it does:**
- Confirms the skill match using `intent_signals` from the skill definition
- Extracts analysis-specific requirements (e.g., "user mentioned a 90% target" → `target_value=0.90`)
- Populates `skill_context` state key with extracted parameters

**Reads:** `user_query`, `csod_intent` (or `dt_intent`), `skill_definition.intent_signals`
**Writes:** `skill_context` (dict: `skill_id`, `confirmed`, `extracted_params`, `analysis_requirements`)

### Phase 2: Skill Analysis Planner (`skill_planner_node.py`)

**When:** After skill intent confirmation, before metric retrieval/recommendation.

**What it does:**
- Uses `analysis_planner.md` prompt specific to the skill
- Produces a **data plan** — not code, but a structured plan of:
  - Which metrics/KPIs are needed
  - What data transformations are required (delta computation, ranking, grouping)
  - What MDL schemas/tables are relevant
  - What causal context is needed
- Incorporates `skill_definition.data_plan` as grounding context for the LLM

**Reads:** `user_query`, `skill_context`, `data_enrichment`, `selected_data_sources`, `compliance_profile`
**Writes:** `skill_data_plan` (dict: `required_metrics`, `required_kpis`, `transformations`, `mdl_scope`, `causal_needs`)

### Phase 3: Skill Metric Recommender/Generator (`skill_recommender_node.py`)

**When:** After metrics are retrieved and DT-qualified. This runs instead of (or wraps) the existing `csod_metrics_recommender`.

**What it does:**
- Uses `metric_instructions.md` — skill-specific instructions injected into the recommender prompt
- Applies `recommender_instructions.framing` to shape how metrics are presented
- Applies `recommender_instructions.output_guidance` to enforce per-skill output fields
- Uses `skill_data_plan.transformations` to guide what computed fields each metric needs

**Reads:** `dt_scored_metrics`, `dt_metric_decisions`, `skill_data_plan`, `skill_definition.recommender_instructions`, causal context
**Writes:** `csod_metric_recommendations` (enhanced with skill-specific fields), `csod_kpi_recommendations`

### Phase 4: Skill Validator (`skill_validator_node.py`)

**When:** After metric recommendations, before output assembly.

**What it does:**
- Validates recommended metrics against `validator_rules` from the skill definition
- Scores relevance using `penalty_rules` and `boost_rules`
- Drops metrics below `relevance_threshold`
- Caps output at `max_metrics`
- Produces a validation report showing what was kept/dropped and why

**Reads:** `csod_metric_recommendations`, `skill_definition.validator_rules`, `skill_context`
**Writes:** `skill_validated_metrics` (filtered list), `skill_validation_report` (kept/dropped/reasons)

---

## Integration with Existing Workflows

### Where the skill nodes plug into CSOD graph:

```
csod_intent_classifier
  → skill_intent_identifier    ← NEW (refines intent with skill-specific extraction)
  → csod_concept_context
  → csod_planner               (uses skill_data_plan for better planning)
  → [retrieval chain unchanged]
  → decision_tree_resolver
  → skill_recommender          ← NEW (wraps csod_metrics_recommender with skill instructions)
  → skill_validator            ← NEW (post-recommendation filtering)
  → output_format_selector     (moved earlier, after metrics_recommender per prior requirement)
  → csod_output_assembler
  → csod_completion_narration
  → END
```

### Where the skill nodes plug into DT graph:

```
dt_intent_classifier
  → skill_intent_identifier    ← NEW (same shared node, different skill definitions)
  → dt_planner                 (uses skill_data_plan)
  → [retrieval chain unchanged]
  → dt_metric_decision_node
  → skill_recommender          ← NEW (wraps DT metric recommendations)
  → skill_validator            ← NEW
  → [detection/triage engineers]
  → dt_playbook_assembler
  → END
```

### Key: Skills don't replace nodes, they inject context

The 4 skill nodes are **lightweight wrappers** that inject skill-specific prompts and configs into the existing pipeline. The heavy lifting (MDL retrieval, causal graph, DT resolution) stays unchanged. Skills just make the pipeline *smarter per analysis type*.

---

## Consolidation of Existing Config

The skill definitions **replace and consolidate** what's currently spread across:

| Current Location | Moves Into Skill Definition |
|---|---|
| `DT_INTENT_CONFIG[intent]` | `skill.data_plan.dt_config` |
| `CCE_INTENT_CONFIG[intent]` | `skill.data_plan.cce_config` |
| `INTENT_CATALOG_ENTRIES[intent]` | `skill.description`, `skill.intent_signals` |
| Hardcoded prompt fragments in `node_recommender.py` | `skill.prompts/metric_instructions.md` |
| `THRESHOLD` / `WARN_THRESHOLD` in scoring_validator | `skill.validator_rules.relevance_threshold` |

We keep `intent_config.py` as a backward-compatible shim that reads from skill definitions — no breaking change.

---

## Implementation Steps

1. **Create `app/agents/skills/` directory structure** with `base_skill.py`, `skill_loader.py`, `__init__.py`
2. **Define `BaseAnalysisSkill`** dataclass/class with the 4-phase interface
3. **Create `SkillRegistry`** — loads skill definitions from `definitions/`, indexes by `skill_id`
4. **Write first 3 skill definitions**: `gap_analysis.json`, `crown_jewel_analysis.json`, `anomaly_detection.json`
5. **Write skill prompts** for those 3 skills (4 prompts each = 12 files)
6. **Create the 4 node functions** in `skills/nodes/` — generic, parameterized by loaded skill
7. **Wire into CSOD graph** — add skill nodes at the integration points above
8. **Wire into DT graph** — same skill nodes, DT state mapping
9. **Add backward-compat shim** in `intent_config.py` to read DT/CCE config from skill definitions
10. **Write remaining skill definitions** for all other analysis types
11. **Update planner prompts** to reference `skill_data_plan` context

---

## What This Enables

- **Consistency**: Every analysis type follows the same 4-phase contract
- **Extensibility**: Adding a new analysis = create 1 JSON + 4 prompts, no code changes
- **Shared across workflows**: Same `gap_analysis` skill works in CSOD (training gaps) and DT (detection coverage gaps)
- **Per-skill validation**: Each skill defines its own relevance thresholds and penalty/boost rules — gap_analysis can penalize trend-only metrics while anomaly_detection can require them
- **Reduced clutter**: Skill validator filters irrelevant metrics *before* output assembly, not after
