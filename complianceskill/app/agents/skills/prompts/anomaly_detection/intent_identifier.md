# Skill Intent Refinement: Anomaly Detection

You are refining the classified intent for an **Anomaly Detection** skill.

## Your Task

1. **Confirm** the skill match — does the user want to find unusual patterns, spikes, drops, or outliers?
2. **Extract** skill-specific parameters:
   - `time_window`: the period of interest ("last week", "last month", "Q4", "last 90 days")
   - `baseline_window`: how much history to use for baseline (default: "trailing_12_periods")
   - `sensitivity`: how sensitive the detection should be ("high" = 1.5σ, "medium" = 2.0σ, "low" = 3.0σ) — default "medium"
   - `focus_metrics`: specific metrics the user mentioned (e.g., "completions", "overdue") — or null for broad scan
   - `anomaly_type`: "drops" / "spikes" / "both" (default "both")
3. **Flag** if the user is actually asking about a known cause (not anomaly detection but root cause analysis)

## Output Format

```json
{
  "confirmed": true,
  "confidence": 0.90,
  "extracted_params": {
    "time_window": "last_week",
    "baseline_window": "trailing_12_periods",
    "sensitivity": "medium",
    "focus_metrics": ["course_completions"],
    "anomaly_type": "drops"
  },
  "analysis_requirements": ["enforce_trend_only"],
  "ambiguity_notes": null
}
```

## Intent Signals

- Keywords: anomaly, spike, drop, outlier, unusual, unexpected, sudden change, deviation
- Anti-patterns: "how far are we from target" → gap_analysis; "which metrics matter most" → crown_jewel
