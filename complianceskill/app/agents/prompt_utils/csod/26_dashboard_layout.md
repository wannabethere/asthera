# Dashboard layout resolver

Map `dt_metric_groups` to dashboard sections and widget types for the given persona.

Output **JSON only**:
```json
{
  "sections": [
    {"section_id": "executive_kpis", "title": "...", "widget_type": "kpi_card", "metric_ids": []}
  ],
  "widget_assignments": [
    {"metric_id": "", "section_id": "", "widget_type": "kpi_card|trend_line|detail_table"}
  ],
  "persona_notes": ""
}
```

Use only metric_ids present in dt_scored_metrics. Prefer current_state → kpi_card, trend → trend_line.
