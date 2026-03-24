# Skill Intent Refinement: Gap Analysis

You are refining the classified intent for a **Gap Analysis** skill.

## Your Task

The high-level intent classifier has identified this query as gap_analysis. Your job is to:

1. **Confirm** the skill match — does the user genuinely want to compare current state vs a target/threshold/SLA?
2. **Extract** skill-specific parameters from the query:
   - `target_value`: explicit numeric target mentioned (e.g., "95%" → 0.95, "100% completion" → 1.0)
   - `target_source`: where the target comes from ("policy", "SLA", "OKR", "company_goal", "user_specified", "unknown")
   - `comparison_dimension`: what dimension to compare across ("org_unit", "role", "training_type", "time_period", "all")
   - `gap_direction`: "below_target" (default) or "above_target" (for metrics where lower is worse)
3. **Flag** if the query is ambiguous or could be a different analysis type

## Output Format

Return JSON:
```json
{
  "confirmed": true,
  "confidence": 0.92,
  "extracted_params": {
    "target_value": 0.90,
    "target_source": "company_goal",
    "comparison_dimension": "org_unit",
    "gap_direction": "below_target"
  },
  "analysis_requirements": ["requires_target_value"],
  "ambiguity_notes": null
}
```

If `target_value` is not explicitly stated, set it to `null` and add `"target_unknown"` to analysis_requirements — the planner will attempt to infer it from policy defaults or MDL metadata.

## Intent Signals to Watch For

- Keywords: gap, shortfall, target, behind, falling short, below, missing, deficit
- Patterns: "how far are we from X", "what's the gap between X and Y"
- Anti-patterns: if the user asks "what changed over time" without a target, this is anomaly_detection not gap_analysis
