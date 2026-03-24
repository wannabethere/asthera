# Skill Validator: Gap Analysis

Validate the recommended metrics for a **gap analysis** skill execution.

## Validation Rules

### Required Fields Check
Every recommended metric MUST have:
- `target_value` — reject if missing AND target_source is not "inferred"
- `current_value` — reject if missing (cannot compute gap without it)

Metrics missing both fields are **dropped**. Metrics missing only target_value are **flagged** with `validation_warning: "target_unknown"` but kept if they score above threshold.

### Relevance Scoring Adjustments

Apply these adjustments to the metric's composite_score:

**Penalties:**
- Metric has no computable target: **-0.15**
- Metric is trend-only with no current_state capability: **-0.10**
- Metric has no delta/gap computation possible: **-0.10**
- Metric duplicates another metric's gap (same underlying measure): **-0.08**

**Boosts:**
- Metric has explicit policy/SLA threshold from MDL metadata: **+0.10**
- Metric is a causal terminal node (high in_degree): **+0.05**
- Metric's gap > 10% of target: **+0.05**
- Metric is in the user's explicitly mentioned focus area: **+0.05**

### Threshold & Caps
- **Relevance threshold:** 0.55 — drop metrics scoring below this after adjustments
- **Max metrics:** 14 — if more pass threshold, keep top 14 by adjusted score
- **Minimum metrics:** 3 — if fewer than 3 pass, lower threshold to 0.45 and retry

## Output Format

```json
{
  "validated_metrics": [...],
  "dropped_metrics": [
    {"metric_id": "...", "reason": "below_threshold", "adjusted_score": 0.42}
  ],
  "validation_warnings": [
    {"metric_id": "...", "warning": "target_unknown", "impact": "gap_delta cannot be computed"}
  ],
  "summary": {
    "total_candidates": 22,
    "passed": 14,
    "dropped": 6,
    "warnings": 2
  }
}
```
