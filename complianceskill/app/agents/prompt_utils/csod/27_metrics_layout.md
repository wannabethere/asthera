# Metrics layout resolver

Order DT metric groups for recommendations. Tag metrics as leading vs lagging when `csod_causal_centrality` is provided (high out_degree → leading, high in_degree → lagging).

Output **JSON only**:
```json
{
  "ordered_groups": [{"group_key": "", "metric_ids": [], "rationale": ""}],
  "leading_metric_ids": [],
  "lagging_metric_ids": [],
  "summary": ""
}
```
