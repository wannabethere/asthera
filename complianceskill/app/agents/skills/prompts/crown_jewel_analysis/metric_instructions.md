# Skill Metric Instructions: Crown Jewel Analysis

These instructions are injected into the CSOD_METRICS_RECOMMENDER when the active skill is **crown_jewel_analysis**.

## Framing: Impact Prioritization

For every metric you recommend, frame the output as an **impact ranking**. The user needs to see which metrics matter most and why, based on causal topology.

## Required Output Fields Per Metric

| Field | Type | Description |
|-------|------|-------------|
| `impact_rank` | int | 1..N ranking by centrality_score |
| `centrality_score` | float | in_degree + out_degree from causal graph |
| `in_degree` | int | Number of incoming causal edges (lagging signal) |
| `out_degree` | int | Number of outgoing causal edges (leading signal) |
| `leading_or_lagging` | string | "leading" (high out_degree) / "lagging" (high in_degree) / "hub" (both high) |
| `business_justification` | string | 1-sentence explanation of why this is a crown jewel |
| `must_watch` | bool | true for top 5 metrics |

## Metric Selection Bias

- **Prefer** metrics with high causal centrality (combined degree >= 3)
- **Prefer** metrics that connect multiple goals (hub nodes)
- **Deprioritize** isolated metrics with zero causal connections
- **Deprioritize** metrics that are redundant (same causal role as a higher-ranked metric)

## Causal Context Usage

- Use `csod_causal_centrality` as the PRIMARY ranking input
- Classify: out_degree > in_degree → "leading"; in_degree > out_degree → "lagging"; both >= 2 → "hub"
- Identify confounders (nodes that create spurious correlations) and flag them separately
- Crown jewels should include a mix of leading AND lagging indicators for balanced monitoring

## Scope Constraint

If `scope_constraint` is set in skill_context (e.g., "top 5"), output exactly that many metrics. If not set, output up to max_metrics (12) but clearly mark the top 5 as must_watch.
