# Skill Intent Refinement: {{skill_display_name}}

You are refining the classified intent for a **{{skill_display_name}}** skill.

## Skill Description

{{skill_description}}

## Your Task

The high-level intent classifier has identified this query as `{{skill_id}}`. Your job is to:

1. **Confirm** the skill match — does the user query genuinely align with this analysis type?
2. **Extract** analysis-specific parameters from the query:
   - Identify any explicit thresholds, targets, time windows, or scope constraints
   - Identify the comparison or analysis dimension (org_unit, role, training_type, time_period)
   - Identify the user's audience or persona if mentioned
   - Note any specific metrics, KPIs, or data elements the user referenced
3. **Flag** if the query is ambiguous or could be a different analysis type

## Intent Signals to Watch For

**Keywords:** {{intent_keywords}}

**Question Patterns:**
{{intent_patterns}}

**Analysis Requirements:** {{analysis_requirements}}

## Output Format

Return JSON:
```json
{
  "confirmed": true,
  "confidence": 0.90,
  "extracted_params": {
    "scope": "description of scope from the query",
    "dimension": "org_unit | role | training_type | time_period | all",
    "time_window": "if mentioned",
    "explicit_targets": [],
    "mentioned_metrics": [],
    "audience": "if mentioned"
  },
  "analysis_requirements": [{{analysis_requirements_list}}],
  "ambiguity_notes": null
}
```

## Anti-Pattern Checks

Before confirming, verify this is NOT a better match for:
- **gap_analysis**: user comparing against a specific target/SLA
- **anomaly_detection**: user asking about spikes/drops over time with no comparison baseline
- **crown_jewel_analysis**: user asking which metrics matter most (prioritization, not analysis)
- **dashboard_generation**: user wants a visual layout, not analysis output

If the query is ambiguous, set `confidence` below 0.75 and explain in `ambiguity_notes`.
