# Skill Metric Instructions: Anomaly Detection

These instructions are injected into the CSOD_METRICS_RECOMMENDER when the active skill is **anomaly_detection**.

## Framing: Anomaly Investigation

For every metric you recommend, frame the output as a **time-series anomaly candidate** — a metric that should be monitored for unusual deviations.

## Required Output Fields Per Metric

| Field | Type | Description |
|-------|------|-------------|
| `metric_type` | string | MUST be "trend" — reject current_state-only metrics |
| `time_window` | string | Recommended baseline window for this metric |
| `deviation_threshold` | float | Recommended z-score threshold (default 2.0) |
| `min_history_periods` | int | Minimum periods needed for baseline (default 4) |
| `upstream_drivers` | list | Causal graph upstream metrics for propagation tracing |

## CRITICAL: Trend-Only Enforcement

**ONLY recommend metrics that have time-series (trend) capability.** This is non-negotiable for anomaly detection.

- If a metric is current_state ONLY with no historical tracking → **DO NOT RECOMMEND IT**
- If a metric has both current_state and trend → recommend with metric_type="trend"
- If unsure whether a metric has trend capability → check the natural_language_question — it should query a time-based aggregation

## Metric Selection Bias

- **Prefer** metrics with rich time-series data (>= 12 historical periods)
- **Prefer** metrics with high variance (more likely to exhibit detectable anomalies)
- **Prefer** metrics connected to multiple downstream metrics in causal graph (anomaly has broader impact)
- **Deprioritize** low-variance metrics that are naturally stable (e.g., static configuration counts)
- **Reject** current_state-only metrics entirely

## Causal Context Usage

For each recommended metric, include `upstream_drivers` from causal graph:
- Walk upstream 1-2 hops through causal edges
- For each upstream driver, note the relationship type and edge weight
- This enables the anomaly detector to check "did the upstream metric also show an anomaly?" → propagated vs local

## Natural Language Question Guidance

Each metric's `natural_language_question` MUST query a time-series. Examples:
- "What is the weekly completion rate for the last 12 weeks?" (NOT "What is the current completion rate?")
- "Show monthly overdue counts by org_unit for the trailing 6 months"
