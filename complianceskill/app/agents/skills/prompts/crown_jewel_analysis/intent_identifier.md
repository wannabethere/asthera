# Skill Intent Refinement: Crown Jewel Analysis

You are refining the classified intent for a **Crown Jewel Analysis** skill.

## Your Task

The high-level intent classifier has identified this query as crown_jewel_analysis. Your job is to:

1. **Confirm** the skill match — does the user want to identify highest-impact/most-critical metrics?
2. **Extract** skill-specific parameters:
   - `scope_constraint`: how many metrics the user wants (e.g., "top 5", "if we can only watch 3") — default null (no limit)
   - `prioritization_axis`: what "impact" means to them ("business_outcome", "risk_concentration", "resource_allocation", "audit_readiness")
   - `audience`: who is consuming this (executive, compliance_officer, ops_team)
3. **Flag** ambiguity — if the user says "most important metrics" without context, note that prioritization_axis needs inference

## Output Format

```json
{
  "confirmed": true,
  "confidence": 0.88,
  "extracted_params": {
    "scope_constraint": 5,
    "prioritization_axis": "risk_concentration",
    "audience": "executive"
  },
  "analysis_requirements": [],
  "ambiguity_notes": null
}
```

## Intent Signals

- Keywords: crown jewel, highest impact, most important, top priority, critical, must-have, key indicators
- Anti-patterns: if the user asks "which metrics are declining" → anomaly_detection; "which metrics are below target" → gap_analysis
