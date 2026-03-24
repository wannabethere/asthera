# Skill Validator: {{skill_display_name}}

Validate the recommended metrics for a **{{skill_display_name}}** execution.

---

## Validation Context

**Skill:** {{skill_id}}
**Category:** {{skill_category}}
**Analysis framing:** {{framing}}

## Required Fields Check

{{required_fields_check}}

## Relevance Scoring Adjustments

### Penalties
{{penalty_rules}}

### Boosts
{{boost_rules}}

## Threshold & Caps

- **Relevance threshold:** {{relevance_threshold}} — drop metrics scoring below this after adjustments
- **Max metrics:** {{max_metrics}} — if more pass threshold, keep top {{max_metrics}} by adjusted score
- **Minimum metrics:** 3 — if fewer than 3 pass, lower threshold by 0.10 and retry

## Deduplication

If two metrics measure the same underlying data element (same table + column + aggregation), keep only the one with the higher adjusted score. Drop the other with reason `"duplicate_measure"`.

## Transformation Compatibility Check

Verify each metric can support the required transformations for this analysis:
{{transformation_compatibility}}

Metrics that cannot support required transformations receive a **-0.10** penalty.

## Output Format

```json
{
  "validated_metrics": [...],
  "dropped_metrics": [
    {"metric_id": "...", "reason": "below_threshold | duplicate_measure | missing_required_field | incompatible_transform", "adjusted_score": 0.42}
  ],
  "validation_warnings": [
    {"metric_id": "...", "warning": "description", "impact": "what this means for the analysis"}
  ],
  "summary": {
    "total_candidates": 22,
    "passed": 14,
    "dropped": 6,
    "warnings": 2,
    "skill_id": "{{skill_id}}",
    "threshold_applied": {{relevance_threshold}}
  }
}
```

## Critical: Preserve Analysis Coverage

- Ensure at least 2 different focus_areas or goals are represented in the final set
- If the analysis requires paired metrics (e.g., cost + outcome for ROI), ensure pairs survive together — do not drop one half of a pair
- If a metric is the only representative of a required transformation, lower its threshold by 0.05 before dropping
