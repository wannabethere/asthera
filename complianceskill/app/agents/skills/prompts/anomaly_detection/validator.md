# Skill Validator: Anomaly Detection

Validate the recommended metrics for an **anomaly detection** execution.

## Validation Rules

### Trend-Only Enforcement
Any metric with metric_type != "trend" is **automatically dropped** — this is the strictest rule.

### Relevance Scoring Adjustments

**Penalties:**
- Metric is current_state only with no trend capability: **-0.25** (effectively dropped)
- Metric has insufficient time-series history (< 4 periods): **-0.10**
- Metric has no causal graph connections for upstream tracing: **-0.05**
- Metric is naturally low-variance (configuration counts, static flags): **-0.08**

**Boosts:**
- Metric has rich time-series data (>= 12 periods): **+0.10**
- Metric connected to multiple downstream metrics in causal graph (high out_degree): **+0.08**
- Metric is in a known volatile focus area (operations, assignments): **+0.05**
- Metric has upstream drivers identified in causal graph: **+0.03**

### Threshold & Caps
- **Relevance threshold:** 0.55
- **Max metrics:** 14
- **Minimum metrics:** 3 — anomaly detection needs breadth to catch systemic patterns

### Diversity Check
Ensure at least 2 different focus_areas are represented in the final set — anomaly detection should not be limited to a single area.

## Output Format

Same as standard skill validator output (validated_metrics, dropped_metrics, validation_warnings, summary).
