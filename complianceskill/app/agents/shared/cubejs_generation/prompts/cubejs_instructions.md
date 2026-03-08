## Column Inference Rules
- If a column ends in `_count` or `_total` → `type: sum`
- If a column is `avg_*` or `average_*` → `type: avg`
- If a column is a boolean flag (`is_*`) → expose as a string dimension with CASE WHEN mapping, not a measure
- If a column is `*_id` or `host_id` → `type: countDistinct` for cardinality measures, string dimension for grouping
- If a column is a `TIMESTAMP WITH TIME ZONE` → `type: time` dimension

## Pre-Aggregation Rules
- Name pre-aggregations as `weeklyBy{PrimaryGrouping}` — e.g. `weeklyByHost`, `weeklyByOs`, `weeklyByLanguage`
- Always include `refreshKey: { every: '1 day' }`
- `timeDimension` must reference the cube's primary time dimension
- `granularity: 'week'` is the default; add a `monthly` variant only when the metric has `metrics_intent: "trend"` at month granularity

## Metric Meta Mapping
For each measure, inspect metric_recommendations for a matching KPI entry.
Set `meta.kpi_id` to the full metric `id` field (e.g. `vuln_by_asset_criticality:by_host_critical_vuln_count_per_host`).
Set `meta.mapped_risks` to the `mapped_risk_ids` array from that metric.
Set `meta.widget_hint` to the `widget_type` field from that metric.

## Multi-Tenant Rule
Every cube must declare `connectionId` as its first dimension.
The description must say: "Tenant isolation key — always filter by this".
