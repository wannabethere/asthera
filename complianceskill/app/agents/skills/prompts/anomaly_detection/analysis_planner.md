# Skill Analysis Planner: Anomaly Detection

You are planning the **data requirements** for detecting anomalies in compliance/learning metrics.

## Context

The user wants to find unusual patterns — spikes, drops, or outliers. This requires trend metrics with sufficient time-series history and causal graph context to trace upstream origins.

## Planning Rules

1. **Metric types:** ONLY `trend` metrics — reject current_state-only metrics at planning stage
2. **Time-series requirement:** Each metric must have >= 4 historical periods for baseline computation
3. **Baseline strategy:** Rolling window (default trailing_12_periods) for mean/stddev computation
4. **Causal context:** REQUIRED — used to trace whether anomalies originate locally or propagate from upstream
5. **Grouping:** Group by focus_area to identify systemic vs isolated anomalies
6. **Sensitivity:** Configurable z-score threshold from skill_context (default 2.0σ)

## Output Format

```json
{
  "required_metrics": {
    "primary": ["completion_rate_trend", "overdue_rate_trend", "assignment_volume_trend"],
    "secondary": ["login_frequency_trend", "certification_lapse_rate"]
  },
  "required_kpis": [],
  "target_resolution_strategy": "not_applicable",
  "transformations": [
    {"name": "rolling_baseline", "formula": "mean(last N periods)", "per": "metric", "params": {"window": 12}},
    {"name": "rolling_stddev", "formula": "stddev(last N periods)", "per": "metric", "params": {"window": 12}},
    {"name": "z_score", "formula": "(current - baseline_mean) / baseline_stddev", "per": "metric_period"},
    {"name": "anomaly_flag", "formula": "|z_score| > threshold", "per": "metric_period", "params": {"threshold": 2.0}},
    {"name": "group", "by": "focus_area"}
  ],
  "mdl_scope": {
    "required_tables": [],
    "required_columns": ["date_column", "metric_value_column"]
  },
  "causal_needs": {
    "mode": "required",
    "usage": "upstream_propagation_tracing",
    "depth": 2
  }
}
```
