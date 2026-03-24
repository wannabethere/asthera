# Skill Analysis Planner: Crown Jewel Analysis

You are planning the **data requirements** for identifying the highest-impact metrics in a compliance/learning program.

## Context

The user wants to know which metrics matter most — the "crown jewels" that deserve the most attention when resources are constrained. This requires causal graph topology to determine which metrics have the most influence.

## Planning Rules

1. **Metric types:** Both `current_state` AND `trend` — crown jewels can be either
2. **Causal context:** REQUIRED — centrality scoring is the primary ranking mechanism
3. **Scope:** Cast wide initially (all qualified metrics), then rank and cut to scope_constraint
4. **Grouping:** Group by goal to ensure coverage across compliance objectives
5. **Leading vs lagging:** Must classify each metric using graph topology (out_degree → leading, in_degree → lagging)

## Output Format

```json
{
  "required_metrics": {
    "primary": ["compliance_completion_rate", "compliance_posture", "certification_coverage", "training_completion_rate"],
    "secondary": ["assignment_volume", "login_frequency", "overdue_rate", "manager_engagement"]
  },
  "required_kpis": [],
  "target_resolution_strategy": "not_applicable",
  "transformations": [
    {"name": "centrality_score", "formula": "in_degree + out_degree", "per": "metric"},
    {"name": "impact_rank", "formula": "rank by centrality_score desc", "per": "all"},
    {"name": "classify_leading_lagging", "formula": "out_degree > in_degree → leading; else → lagging", "per": "metric"},
    {"name": "group", "by": "goal"}
  ],
  "mdl_scope": {
    "required_tables": [],
    "required_columns": []
  },
  "causal_needs": {
    "mode": "required",
    "usage": "centrality_ranking_and_classification",
    "depth": "full_graph"
  }
}
```
