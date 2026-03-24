# Skill Metric Instructions: {{skill_display_name}}

These instructions are injected into the CSOD_METRICS_RECOMMENDER when the active skill is **{{skill_id}}**.

---

## Analysis Framing: {{framing}}

{{framing_description}}

## Metric Selection Bias

{{metric_selection_bias}}

## Output Guidance

{{output_guidance}}

## Required Data Elements Per Metric

Each recommended metric should include or map to these data elements where applicable:
{{required_data_elements_list}}

## Transformations This Analysis Expects

The downstream pipeline will apply these transformations to the recommended metrics. Ensure the metrics you recommend can support them:

{{transformations_list}}

## Causal Context Usage

{{causal_usage}}

## Grouping & Ordering

- **Group by:** `{{dt_group_by}}` (from decision tree configuration)
- **Within each group:** Order by relevance / composite_score descending
- **Highlight:** Flag top 3 metrics per group as `priority: "high"`

## Natural Language Question Guidance

Each metric's `natural_language_question` MUST be specific enough to query the right data:
- Include the metric name and any required dimensions
- Include time window or scope constraints from the user's query
- {{metric_type_specific_guidance}}

## What NOT to Recommend

- Metrics that cannot support the required transformations for this analysis
- Metrics outside the user's stated scope (wrong org_unit, training_type, etc.)
- Metrics without schema grounding in `resolved_schemas`
- Duplicate metrics that measure the same underlying data element
