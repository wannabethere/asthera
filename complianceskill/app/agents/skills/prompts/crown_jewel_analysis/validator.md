# Skill Validator: Crown Jewel Analysis

Validate the recommended metrics for a **crown jewel analysis** execution.

## Validation Rules

### Required Fields Check
No strict required fields — crown jewel analysis is topology-driven, not data-element-driven.

### Relevance Scoring Adjustments

**Penalties:**
- Metric has zero causal graph connections (in_degree=0 AND out_degree=0): **-0.20**
- Metric duplicates another metric's causal role (same upstream/downstream set): **-0.10**
- Metric is only relevant to a single narrow use case: **-0.05**

**Boosts:**
- Metric is a causal hub node (in_degree >= 2 AND out_degree >= 2): **+0.10**
- Metric aligned with multiple goals from dt_metric_decisions: **+0.08**
- Metric is a leading indicator with high out_degree (>= 3): **+0.05**
- Metric has both current_state and trend capability: **+0.03**

### Threshold & Caps
- **Relevance threshold:** 0.60 (higher than default — crown jewels must be truly high-impact)
- **Max metrics:** 12
- **Minimum metrics:** 3

## Deduplication

If two metrics have the same causal role (identical upstream + downstream connections), keep only the one with the higher composite_score and drop the other with reason "causal_role_duplicate".

## Output Format

Same as standard skill validator output (validated_metrics, dropped_metrics, validation_warnings, summary).
