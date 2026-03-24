# Skill Metric Instructions: Gap Analysis

These instructions are injected into the CSOD_METRICS_RECOMMENDER when the active skill is **gap_analysis**.

## Framing: Gap-to-Target

For every metric you recommend, frame the output as a **gap-to-target comparison**. The user needs to see:
- Where they are now (current_value)
- Where they need to be (target_value)
- How far away they are (gap_delta, gap_pct)

## Required Output Fields Per Metric

Each recommended metric MUST include these additional fields beyond the standard recommendation:

| Field | Type | Description |
|-------|------|-------------|
| `target_value` | float | The policy/SLA/company target for this metric |
| `current_value` | float | Latest observed value from data |
| `gap_delta` | float | target_value - current_value (positive = below target) |
| `gap_pct` | float | (target - current) / target * 100 |
| `target_source` | string | "policy" / "SLA" / "company_goal" / "benchmark" / "inferred" |
| `gap_severity` | string | "critical" (gap > 20%) / "warning" (5-20%) / "on_track" (< 5%) |

## Metric Selection Bias

- **Prefer** metrics with clear, computable target/threshold definitions
- **Prefer** metrics where current_value is available from the scored context
- **Deprioritize** trend-only metrics that cannot produce a point-in-time gap
- **Deprioritize** ratio metrics where the target is undefined or subjective

## Causal Context Usage

When causal edges are available:
1. For the **top 3 gaps** (by gap_pct), trace upstream through the causal graph
2. Identify **upstream drivers** — metrics that feed into the gap metric
3. For each upstream driver, note whether it is also below target
4. Include `upstream_drivers: [{metric_id, relationship, also_below_target}]` in the recommendation

## Grouping

- Group recommendations by `focus_area` or `goal` (from dt_metric_decisions)
- Within each group, order by `gap_pct` descending (largest gap first)
- Flag the top 3 overall gaps as `priority: "high"`
