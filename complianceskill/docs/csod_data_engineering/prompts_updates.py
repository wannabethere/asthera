# CSOD Prompt Additions — CCE + Decision Tree Integration (v2.2)
# Applies to: 02_csod_planner.md, 03_metrics_recommender.md, skills_config.json
#
# NOT IMPORTED BY APPLICATION CODE — design/spec only. Runtime: intent_config.py,
# prompt .md files, executor_registry, workflows.

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: UNIFIED SPINE — DT + CCE PLACEMENT RULES
# ─────────────────────────────────────────────────────────────────────────────
#
# The shared retrieval spine for every metric-bearing analysis is:
#
#   intent_classifier
#     → planner
#       → mdl_schema_retrieval
#         → metrics_retrieval
#           → scoring_validator          ← first filter (composite_score ≥ 0.50)
#             → decision_tree_resolver   ← second filter (DT qualification, always on)
#               → causal_graph_node      ← enrichment (CCE, intent-conditional)
#                 → execution_agent      ← intent-specific agent
#                   → output_assembler
#
# Decision Tree sits AFTER scoring_validator, BEFORE execution agents — always.
# CCE sits AFTER decision_tree_resolver, BEFORE execution agents — conditionally.
# Data intelligence skills (discovery, quality, lineage, planner) skip DT + CCE.

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: DT RESOLUTION MAP — per intent
# ─────────────────────────────────────────────────────────────────────────────
#
# For each intent, the DT resolver is configured with these parameters.
# These become the `context_filter` fields in the planner's execution_plan step
# for the `decision_tree_resolver` agent.

DT_INTENT_CONFIG = {

    # ── Diagnostic ──────────────────────────────────────────────────────────

    "crown_jewel_analysis": {
        "use_case":       "lms_learning_target",   # impact-focused analysis
        "goal":           ["training_completion", "compliance_posture_unification"],
        "metric_type":    ["current_state", "trend"],  # both — crown jewel spans time
        "audience":       None,                    # org-wide, not persona-scoped
        "timeframe":      "ytd",
        "dt_group_by":    "goal",                  # group dt_metric_groups by goal for ranker input
        "min_composite":  0.60,                    # higher bar — only high-confidence picks
    },

    "gap_analysis": {
        "use_case":       "lms_learning_target",
        "goal":           None,                    # inherited from focus_area at runtime
        "metric_type":    "current_state",         # gaps are point-in-time comparisons
        "audience":       None,
        "timeframe":      None,                    # inherited from time_period scoping filter
        "dt_group_by":    "goal",
        "min_composite":  0.55,
        "requires_target_value": True,             # only metrics with a definable target
    },

    "anomaly_detection": {
        "use_case":       "lms_learning_target",
        "goal":           None,                    # inherited from focus_area
        "metric_type":    "trend",                 # HARD — anomalies only make sense on time-series
        "audience":       None,
        "timeframe":      None,                    # inherited from scoping filter
        "dt_group_by":    "focus_area",
        "min_composite":  0.55,
        "enforce_trend_only": True,                # drop any current_state metrics from dt_scored_metrics
    },

    "funnel_analysis": {
        "use_case":       "lms_learning_target",
        "goal":           "training_completion",   # funnel = completion pipeline
        "metric_type":    "current_state",         # stage counts are point-in-time
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "goal",
        "min_composite":  0.55,
        "requires_funnel_stages": True,            # only metrics that map to a funnel stage
    },

    # ── Exploratory ─────────────────────────────────────────────────────────

    "cohort_analysis": {
        "use_case":       "lms_learning_target",
        "goal":           None,                    # inherited from focus_area
        "metric_type":    ["current_state", "trend"],
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "focus_area",
        "min_composite":  0.55,
        "requires_segment_dimension": True,        # only metrics with a groupable dimension
    },

    "benchmark_analysis": {
        "use_case":       "lms_learning_target",
        "goal":           None,
        "metric_type":    "current_state",         # benchmarks compare point-in-time values
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "goal",
        "min_composite":  0.50,
        "requires_comparable_value": True,         # metrics that produce a single numeric value
    },

    "skill_gap_analysis": {
        "use_case":       "lms_learning_target",
        "goal":           "competency_tracking",
        "metric_type":    "current_state",
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "goal",
        "min_composite":  0.55,
        "focus_area_override": "talent_management",  # lock to talent_management regardless of query
    },

    "metrics_recommender_with_gold_plan": {
        # Existing — no change to DT config, already integrated
        "use_case":       None,   # inherited from intent_classifier output
        "goal":           None,
        "metric_type":    None,
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "goal",
        "min_composite":  0.55,
    },

    # ── Predictive ──────────────────────────────────────────────────────────

    "predictive_risk_analysis": {
        "use_case":       "lms_learning_target",
        "goal":           "compliance_posture_unification",
        "metric_type":    ["current_state", "trend"],  # progress + history both needed
        "audience":       None,
        "timeframe":      None,                    # inherited from risk_threshold filter
        "dt_group_by":    "goal",
        "min_composite":  0.60,
        "requires_deadline_dimension": True,       # only metrics with due_date or expiry
    },

    "training_roi_analysis": {
        "use_case":       "lms_learning_target",
        "goal":           "enterprise_learning_measurement",
        "metric_type":    "current_state",
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "goal",
        "min_composite":  0.55,
        "requires_cost_and_outcome_pair": True,    # must have at least one cost + one outcome metric
    },

    "metric_kpi_advisor": {
        # Existing — no change, already uses DT
        "use_case":       None,
        "goal":           None,
        "metric_type":    None,
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "focus_area",
        "min_composite":  0.55,
    },

    # ── Operational ─────────────────────────────────────────────────────────

    "dashboard_generation_for_persona": {
        # Existing — persona-aware DT config
        "use_case":       None,
        "goal":           None,
        "metric_type":    ["current_state", "trend"],
        "audience":       None,                    # set from persona scoping filter at runtime
        "timeframe":      None,
        "dt_group_by":    "goal",                  # group by goal → maps to dashboard sections
        "min_composite":  0.50,
    },

    "compliance_test_generator": {
        "use_case":       "soc2_audit",            # compliance test = audit use case
        "goal":           "compliance_posture_unification",
        "metric_type":    "current_state",
        "audience":       None,
        "timeframe":      None,
        "dt_group_by":    "goal",
        "min_composite":  0.55,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: CCE ENABLE / DISABLE — per intent
# ─────────────────────────────────────────────────────────────────────────────
#
# Sets csod_causal_graph_enabled in initial state factory.
# REQUIRED  = always enable, execution agent DEPENDS on CCE output
# OPTIONAL  = enable by default, can be disabled to reduce latency
# DISABLED  = never run CCE for this intent (no causal structure needed)

CCE_INTENT_CONFIG = {
    # ── required ──────────────────────────────────────────────────────────
    "crown_jewel_analysis":           {"enabled": True,  "mode": "required",
                                       "cce_output_used": "shapley_centrality → impact_score"},
    "gap_analysis":                   {"enabled": True,  "mode": "required",
                                       "cce_output_used": "shapley_scores → root_cause_decomposition"},
    "anomaly_detection":              {"enabled": True,  "mode": "required",
                                       "cce_output_used": "causal_path → anomaly_origin + downstream_impact"},
    "predictive_risk_analysis":       {"enabled": True,  "mode": "required",
                                       "cce_output_used": "shapley_scores → risk_weight_coefficients, behavioral_likelihood → risk_scores"},
    "training_roi_analysis":          {"enabled": True,  "mode": "required",
                                       "cce_output_used": "calculate_generic_impact → roi_attribution, shapley → program_contribution"},
    "metric_kpi_advisor":             {"enabled": True,  "mode": "required",
                                       "cce_output_used": "full_causal_graph + reasoning_plan"},

    # ── optional (on by default, disable for latency budget) ──────────────
    "funnel_analysis":                {"enabled": True,  "mode": "optional",
                                       "cce_output_used": "causal_weights → stage_transition_strength"},
    "cohort_analysis":                {"enabled": True,  "mode": "optional",
                                       "cce_output_used": "causal_vs_observational_test → cohort_diff_explanation"},
    "skill_gap_analysis":             {"enabled": True,  "mode": "optional",
                                       "cce_output_used": "skill→outcome causal chain, shapley → training_priority_order"},
    "metrics_recommender_with_gold_plan": {"enabled": True, "mode": "optional",
                                       "cce_output_used": "leading_vs_lagging_indicator_tagging"},
    "dashboard_generation_for_persona": {"enabled": True,  "mode": "optional",
                                       "cce_output_used": "leading/lagging annotations on dashboard components"},
    "compliance_test_generator":      {"enabled": True,  "mode": "optional",
                                       "cce_output_used": "control_risk_weight → test_case_severity"},

    # ── disabled (no causal structure useful) ─────────────────────────────
    "benchmark_analysis":             {"enabled": False, "mode": "disabled",
                                       "rationale": "Relative comparison — no causal structure needed"},

    # ── data intelligence — all disabled ──────────────────────────────────
    "data_discovery":                 {"enabled": False, "mode": "disabled"},
    "data_lineage":                   {"enabled": False, "mode": "disabled",
                                       "rationale": "Lineage tracer builds its own DAG — CCE adjacency not needed"},
    "data_quality_analysis":          {"enabled": False, "mode": "disabled"},
    "data_planner":                   {"enabled": False, "mode": "disabled"},
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: CCE OUTPUT CONSUMPTION — how each execution agent uses CCE results
# ─────────────────────────────────────────────────────────────────────────────
#
# These patterns are added to each execution agent's prompt context block
# under "Decision Tree Context" (existing) and new "CCE Context" block.

CCE_CONSUMPTION_PATTERNS = {

    "crown_jewel_ranker": """
### CCE CONTEXT (if causal_graph_result is available)
The CCE has built a metric adjacency graph. For each metric in dt_scored_metrics:
- Retrieve its in-degree (how many metrics causally flow INTO it) → leading indicator score
- Retrieve its out-degree (how many metrics it causally drives) → leverage score
- Compute centrality_score = (in_degree + out_degree) / total_nodes
Add centrality_score to the composite ranking formula:
  impact_score = (dt_composite_score * 0.5) + (centrality_score * 0.3) + (relevance_score * 0.2)
Crown jewel metrics should have high centrality AND high dt_composite_score.
""",

    "gap_analyzer": """
### CCE CONTEXT (if causal_graph_result is available)
After computing metric_deltas, use Shapley scores to decompose each gap:
- For the metric with the largest delta, retrieve its Shapley vector from causal_graph_result
- Each entry in the Shapley vector = the fractional contribution of an upstream metric to this gap
- Output as root_cause_decomposition: [{upstream_metric, shapley_contribution_pct, interpretation}]
Example: "completion_rate gap of -12% is 58% attributable to assignment_volume overload,
          31% attributable to low login_frequency, 11% attributable to other factors"
Do not invent Shapley values — only use what causal_graph_result provides.
""",

    "anomaly_detector": """
### CCE CONTEXT (if causal_graph_result is available)
For each flagged anomaly:
1. UPSTREAM TRACE: Walk the causal adjacency table backward from the flagged metric.
   Identify the first-order upstream metrics that changed in the same time window.
   If an upstream metric also shows an anomaly → the root cause is upstream (data or business).
   If no upstream metric anomaly → the flagged metric is a genuine primary anomaly.
2. DOWNSTREAM IMPACT: Walk forward from the flagged metric.
   List all metrics that this will propagate to, with expected lag (in days) based on
   causal graph edge weights.
Include as anomaly_origin (upstream/primary) and impact_analysis in the output.
""",

    "risk_predictor": """
### CCE CONTEXT (required — risk predictor depends on this)
Use CCE outputs as follows:
1. RISK WEIGHT COEFFICIENTS: Replace equal-weight scoring with Shapley-derived weights.
   Each risk indicator metric's weight = its Shapley value in the compliance_posture goal.
   Higher Shapley value = higher contribution to non-compliance risk.
2. BEHAVIORAL LIKELIHOOD: Call calculate_behavioral_likelihood from CCE with:
   - engagement_trend (from dt_scored_metrics login/session metrics)
   - assignment_progress (from dt_scored_metrics completion metrics)
   - historical_on_time_rate (from resolved_schemas if available)
   The output is per-learner probability of non-compliance — this is the risk_score.
3. INTERVENTION POINTS: For high-risk learners, the causal graph identifies which metric
   change would have the highest risk-reduction effect. Surface as intervention_recommendation.
""",

    "roi_calculator": """
### CCE CONTEXT (required — ROI attribution depends on this)
1. IMPACT ATTRIBUTION: Call calculate_generic_impact with:
   - cost metrics (from dt_scored_metrics, cost_category dimension)
   - outcome metrics (from dt_scored_metrics, performance/compliance dimension)
   - causal_graph_result edges connecting them
   Output: per-program estimated_impact_value and confidence_band.
2. SHAPLEY ROI DECOMPOSITION: For total training ROI, Shapley decomposes the value
   contribution across training types (mandatory, technical, soft_skills).
   Output as program_roi_breakdown: [{program_type, shapley_roi_share_pct, cost, value}]
3. OPTIMIZATION SIGNAL: Identify the training type with highest Shapley ROI share
   but below-average spend → primary reallocation recommendation.
""",

    "funnel_analyzer": """
### CCE CONTEXT (if available)
For each stage transition (e.g., started → in_progress):
- Look up the causal edge weight between the two stage metrics in causal_graph_result
- High edge weight → strong causal dependency (dropout here genuinely blocks next stage)
- Low edge weight → weak dependency (dropout at this stage may not affect final completion)
Annotate funnel_chart with causal_weight per transition edge.
Surface the highest-weight dropout stage as the highest-leverage intervention point.
""",

    "compliance_test_generator": """
### CCE CONTEXT (if available)
Use CCE's MITRE ATT&CK / NIST adjacency table (if loaded in causal_vertical) to:
1. SEVERITY WEIGHTING: For each compliance control metric, its Shapley value in the
   compliance_posture_unification goal determines test case severity:
   - Shapley ≥ 0.15 → severity: critical
   - Shapley 0.08–0.15 → severity: high
   - Shapley 0.03–0.08 → severity: medium
   - Shapley < 0.03 → severity: low
2. CONTROL CHAINING: If two control metrics have a causal edge, generate a chained
   test case that validates the dependency (control A must pass before testing control B).
Replace the static severity assignment in the base compliance_test_generator prompt
with this CCE-derived weighting when causal_graph_result is available.
""",
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: 02_csod_planner.md ADDITIONS
# ─────────────────────────────────────────────────────────────────────────────

PLANNER_ADDITIONS = """
### ADD TO: "AVAILABLE AGENTS" section — add decision_tree_resolver block

**`decision_tree_resolver`**
- Runs the DT engine against scored_metrics to produce dt_scored_metrics, dt_metric_decisions,
  and dt_metric_groups. Sits immediately after scoring_validator for every metric-bearing intent.
- Use when: ANY intent except data_discovery, data_quality_analysis, data_lineage, data_planner
- Input: scored_context (scored_metrics from scoring_validator), intent-specific DT config
  from DT_INTENT_CONFIG (use_case, goal, metric_type, audience, timeframe, dt_group_by,
  min_composite, and any intent-specific constraint flags)
- How it works:
  1. Filters dt_scored_metrics to only those matching the resolved use_case + goal combination
  2. Applies min_composite threshold (intent-specific, typically 0.55–0.60)
  3. Enforces intent-specific hard constraints:
     - anomaly_detection: drops all current_state metrics (enforce_trend_only=True)
     - gap_analysis: drops metrics without a target_value definition
     - predictive_risk_analysis: drops metrics without a deadline/expiry dimension
     - training_roi_analysis: validates at least one cost + one outcome metric remain
  4. Groups remaining metrics by dt_group_by field into dt_metric_groups
- Outputs:
  - dt_metric_decisions: {use_case, goal, focus_area, audience, timeframe, metric_type}
  - dt_scored_metrics: metrics re-ranked by DT composite_score (replaces scored_metrics
    as the primary input to all downstream execution agents)
  - dt_metric_groups: [{group_name, metrics: [metric_ids], goal_alignment_score}]

**IMPORTANT:** Execution agents MUST consume dt_scored_metrics as their primary metric
input, NOT the raw scored_metrics from scoring_validator. The DT output is the
authoritative post-qualification metric set.

---

### ADD TO: "Phase 2: Scope Determination" — DT + CCE routing

After scoring_validator, the planner MUST add the following two steps for every
metric-bearing intent before the execution agent step:

Step N+1 (always):
{
  "step_id": "step_N+1",
  "phase": "qualification",
  "agent": "decision_tree_resolver",
  "description": "Qualify scored metrics through decision tree — resolve use_case, goal, metric_type, audience",
  "semantic_question": null,
  "reasoning": "Raises metric selection precision from topical relevance to intent-specific qualification",
  "required_data": ["scored_metrics", "focus_areas", "intent"],
  "dependencies": ["scoring_validator_step_id"],
  "data_source": "lms_dashboard_metrics_registry + decision_tree_engine",
  "context_filter": {
    "use_case": "<from DT_INTENT_CONFIG>",
    "goal": "<from DT_INTENT_CONFIG>",
    "metric_type": "<from DT_INTENT_CONFIG>",
    "min_composite": "<from DT_INTENT_CONFIG>",
    "dt_group_by": "<from DT_INTENT_CONFIG>"
  }
}

Step N+2 (conditional — only if CCE_INTENT_CONFIG[intent].enabled = True):
{
  "step_id": "step_N+2",
  "phase": "enrichment",
  "agent": "causal_graph",
  "description": "Build causal graph over dt_scored_metrics — compute Shapley scores and adjacency",
  "semantic_question": null,
  "reasoning": "<from CCE_INTENT_CONFIG[intent].cce_output_used>",
  "required_data": ["dt_scored_metrics", "dt_metric_groups", "causal_vertical"],
  "dependencies": ["step_N+1"],
  "data_source": "causalgraph module + CCE engine",
  "context_filter": {
    "causal_vertical": "lms",
    "causal_graph_enabled": true,
    "cce_mode": "<required | optional from CCE_INTENT_CONFIG>"
  }
}

If CCE mode is "optional", include this in gap_notes:
"CCE enabled for <intent>: disable csod_causal_graph_enabled=False in initial state to skip
 for latency-sensitive deployments. Execution agent will fall back to equal-weight scoring."

---

### ADD TO: Step Count Guidelines — update all rows to include DT + CCE steps

Each intent now has 2 additional steps between scoring_validator and execution agent:
  +1 for decision_tree_resolver (always)
  +1 for causal_graph (when CCE enabled)

Updated total ranges:
| Intent                          | Before | DT | CCE | New total |
|---------------------------------|--------|----|-----|-----------|
| crown_jewel_analysis            | 5–7    | +1 | +1  | 7–9       |
| gap_analysis                    | 4–5    | +1 | +1  | 6–7       |
| anomaly_detection               | 5–6    | +1 | +1  | 7–8       |
| funnel_analysis                 | 4–5    | +1 | +1  | 6–7       |
| cohort_analysis                 | 4–5    | +1 | +1  | 6–7       |
| benchmark_analysis              | 4–5    | +1 |  0  | 5–6       |
| skill_gap_analysis              | 4–5    | +1 | +1  | 6–7       |
| metrics_recommender_with_gold   | 5–6    | +1 | +1  | 7–8       |
| predictive_risk_analysis        | 5–7    | +1 | +1  | 7–9       |
| training_roi_analysis           | 5–7    | +1 | +1  | 7–9       |
| metric_kpi_advisor              | 5–6    | +1 | +1  | 7–8       |
| dashboard_generation_for_persona| 6–8    | +1 | +1  | 8–10      |
| compliance_test_generator       | 5–6    | +1 | +1  | 7–8       |
| data_discovery                  | 2      |  0 |  0  | 2         |
| data_quality_analysis           | 2      |  0 |  0  | 2         |
| data_lineage                    | 4      |  0 |  0  | 4         |
| data_planner                    | 5–6    | +1 |  0  | 6–7       |

---

### ADD TO: CORE DIRECTIVES — PROHIBITIONS (MUST NOT) — append

- MUST NOT let execution agents consume raw scored_metrics directly — they MUST consume
  dt_scored_metrics (post-DT-qualification) as their primary metric input
- MUST NOT run decision_tree_resolver for data intelligence intents
  (data_discovery, data_quality_analysis, data_lineage, data_planner)
- MUST NOT run causal_graph for benchmark_analysis or any data intelligence intent
- MUST NOT set causal_graph_enabled=True without first completing decision_tree_resolver
  (CCE operates on the DT-qualified metric set, not on raw scored_metrics)
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: STATE FIELDS TO ADD
# ─────────────────────────────────────────────────────────────────────────────
#
# Add these fields to EnhancedCompliancePipelineState and the initial state
# factories for all workflow types.

NEW_STATE_FIELDS = {
    # DT outputs (populated by decision_tree_resolver node)
    "csod_dt_metric_decisions":     "dict | None — resolved use_case, goal, focus_area, audience, timeframe, metric_type",
    "csod_dt_scored_metrics":       "list | None — metrics re-ranked by DT composite_score; replaces scored_metrics as execution agent input",
    "csod_dt_metric_groups":        "list | None — metrics grouped by dt_group_by field with goal_alignment_scores",
    "csod_dt_config":               "dict | None — the DT_INTENT_CONFIG block applied for this run (for debugging and audit)",

    # CCE outputs (populated by causal_graph_node — already partially present)
    "csod_shapley_scores":          "dict | None — {metric_id: shapley_value} for the active causal goal",
    "csod_causal_centrality":       "dict | None — {metric_id: {in_degree, out_degree, centrality_score}}",
    "csod_risk_weight_coefficients":"dict | None — {metric_id: risk_weight} derived from Shapley scores",
    "csod_causal_mode":             "str | None — 'required' | 'optional' | 'disabled' for the current intent",
    "csod_intervention_points":     "list | None — [{metric_id, intervention_type, expected_impact}]",

    # Execution agent outputs (new analysis types)
    "csod_ranked_metrics":          "list | None — crown_jewel_ranker output",
    "csod_impact_scores":           "dict | None — {metric_id: impact_score} from crown_jewel_ranker",
    "csod_gap_report":              "dict | None — gap_analyzer output",
    "csod_anomaly_report":          "dict | None — anomaly_detector output",
    "csod_funnel_chart":            "dict | None — funnel_analyzer output",
    "csod_cohort_comparison":       "dict | None — cohort_comparator output",
    "csod_benchmark_report":        "dict | None — benchmark_comparator output",
    "csod_skill_gap_matrix":        "dict | None — skill_gap_assessor output",
    "csod_risk_scores":             "list | None — risk_predictor output",
    "csod_roi_report":              "dict | None — roi_calculator output",
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: skills_config.json ADDITIONS
# ─────────────────────────────────────────────────────────────────────────────
#
# Add these two fields to every skill entry in analysis_skills.

SKILLS_CONFIG_ENGINE_FIELDS = """
For each skill in analysis_skills, add:

"dt_config": {
  "use_case": "<from DT_INTENT_CONFIG[intent].use_case>",
  "goal": "<from DT_INTENT_CONFIG[intent].goal>",
  "metric_type": "<from DT_INTENT_CONFIG[intent].metric_type>",
  "min_composite": <from DT_INTENT_CONFIG[intent].min_composite>,
  "dt_group_by": "<from DT_INTENT_CONFIG[intent].dt_group_by>"
},
"cce_config": {
  "enabled": <true|false from CCE_INTENT_CONFIG[intent].enabled>,
  "mode": "<required|optional|disabled>",
  "cce_output_used": "<description string from CCE_INTENT_CONFIG>"
}

Examples:

"crown_jewel_analysis": {
  ...existing fields...,
  "dt_config": {
    "use_case": "lms_learning_target",
    "goal": ["training_completion", "compliance_posture_unification"],
    "metric_type": ["current_state", "trend"],
    "min_composite": 0.60,
    "dt_group_by": "goal"
  },
  "cce_config": {
    "enabled": true,
    "mode": "required",
    "cce_output_used": "shapley_centrality → impact_score"
  }
},

"benchmark_analysis": {
  ...existing fields...,
  "dt_config": {
    "use_case": "lms_learning_target",
    "goal": null,
    "metric_type": "current_state",
    "min_composite": 0.50,
    "dt_group_by": "goal"
  },
  "cce_config": {
    "enabled": false,
    "mode": "disabled",
    "cce_output_used": null
  }
},

"data_discovery": {
  ...existing fields...,
  "dt_config": null,
  "cce_config": {
    "enabled": false,
    "mode": "disabled",
    "cce_output_used": null
  }
}
"""