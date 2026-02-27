# Decision Tree LLM-Based Resolution

## Overview

The decision tree resolution has been refactored to use LLM-based resolution instead of hardcoded keyword matching and fallback mappings. This makes the system more flexible, maintainable, and able to handle edge cases better.

---

## Architecture

### Before (Hardcoded Logic)

```
_resolve_from_state()
  ├── Hardcoded keyword matching (AUTO_RESOLVE_HINTS)
  ├── Hardcoded fallback mappings (_INTENT_GOAL_FALLBACK_MAP, _FOCUS_AREA_FALLBACK_MAP)
  └── Complex conditional logic
```

### After (LLM-Based)

```
_resolve_from_state()
  ├── LLM call with prompt (17_resolve_decisions.md)
  │   ├── Includes all decision tree structure as examples
  │   ├── Includes all keyword hints as examples
  │   └── Includes fallback mappings as examples
  └── Fallback to simple keyword matching (if LLM fails)
```

---

## Prompt File

**Location:** `app/agents/decision_trees/prompts/17_resolve_decisions.md`

**Contents:**
- Complete decision tree structure (all 6 questions with options)
- All keyword hints from `AUTO_RESOLVE_HINTS`
- Fallback mappings (as examples, not hardcoded rules)
- Resolution rules and examples
- Input/output format specification

---

## How It Works

### 1. LLM Resolution (Primary Path)

```python
def _resolve_from_state(state: Dict[str, Any]) -> Dict[str, Tuple[str, float]]:
    # Load prompt with all decision tree examples
    prompt_template = load_prompt("17_resolve_decisions", ...)
    
    # Prepare input
    input_data = {
        "user_query": state.get("user_query", ""),
        "intent": state.get("intent", ""),
        "framework_id": state.get("framework_id"),
        "data_enrichment": state.get("data_enrichment", {}),
    }
    
    # Call LLM
    response = llm.invoke(prompt.format(input=json.dumps(input_data)))
    
    # Parse and return resolved decisions
    return parse_llm_response(response)
```

### 2. Fallback Resolution (If LLM Fails)

```python
def _resolve_from_state_fallback(state: Dict[str, Any]) -> Dict[str, Tuple[str, float]]:
    # Simple keyword matching
    # Only used if LLM call fails
    ...
```

---

## Benefits

1. **Simpler Code:** No complex keyword matching logic in Python
2. **More Flexible:** LLM can handle variations and edge cases
3. **Easier to Maintain:** All decision logic in one prompt file
4. **Better Accuracy:** LLM understands context better than keyword matching
5. **Extensible:** Easy to add new decision options or rules via prompt updates

---

## Decision Tree Structure (Included in Prompt)

The prompt includes:

1. **Q1: Use Case** — 5 options (soc2_audit, lms_learning_target, risk_posture_report, executive_dashboard, operational_monitoring)
2. **Q2: Goal** — 6 options (compliance_posture, incident_triage, control_effectiveness, risk_exposure, training_completion, remediation_velocity)
3. **Q3: Focus Area** — 7 options (access_control, audit_logging, vulnerability_management, incident_response, change_management, data_protection, training_compliance)
4. **Q4: Audience** — 6 options (security_ops, compliance_team, executive_board, risk_management, learning_admin, auditor)
5. **Q5: Timeframe** — 6 options (realtime, hourly, daily, weekly, monthly, quarterly)
6. **Q6: Metric Type** — 7 options (counts, rates, percentages, scores, distributions, comparisons, trends)

Each option includes:
- Keywords for matching
- Tags (goal_filter, audience, etc.)
- Default values

---

## Resolution Rules (In Prompt)

The LLM follows these rules:

1. **Use Case:**
   - Framework-based: `framework_id="soc2"` → `soc2_audit` (confidence: 0.9)
   - Intent-based: `intent="dashboard_generation"` + "executive" → `executive_dashboard`
   - Keyword matching: Match keywords from query/intent

2. **Goal:**
   - From `metrics_intent`: Match keywords or use fallback mappings
   - From query: Match keywords

3. **Focus Area:**
   - Direct match: If `suggested_focus_areas[0]` is valid option_id → confidence 0.9
   - Keyword match: Match keywords in the value
   - Alias mapping: Map aliases to canonical values

4. **Audience:**
   - Keyword matching from intent + query

5. **Timeframe & Metric Type:**
   - Keyword matching from query

---

## LLM Output Format

```json
{
  "resolved_decisions": {
    "use_case": {
      "option_id": "soc2_audit",
      "confidence": 0.9,
      "source": "framework"
    },
    "goal": {
      "option_id": "compliance_posture",
      "confidence": 0.75,
      "source": "fallback"
    },
    ...
  },
  "overall_confidence": 0.68,
  "reasoning": "Brief explanation..."
}
```

---

## Fallback Behavior

If the LLM call fails (timeout, error, invalid response), the system automatically falls back to `_resolve_from_state_fallback()`, which uses simple keyword matching. This ensures the system never fails completely.

---

## Testing

Tests are in `test_metric_decision_tree.py`:
- Tests for LLM-based resolution (when LLM is available)
- Tests for fallback resolution (when LLM fails)
- Tests for full `resolve_decisions()` flow

---

## Configuration

To disable LLM resolution (use fallback only), you can modify `_resolve_from_state()` to skip the LLM call. However, this is not recommended as LLM resolution provides better accuracy.

---

## Performance

- **LLM Call:** ~1-3 seconds (depending on model)
- **Fallback:** <10ms (simple keyword matching)
- **Caching:** Consider adding caching for repeated queries (future enhancement)

---

## Future Enhancements

1. **Caching:** Cache LLM responses for identical state inputs
2. **Structured Output:** Use LLM structured output mode for better parsing
3. **Confidence Thresholds:** Adjust confidence thresholds based on use case
4. **Multi-turn Refinement:** Allow LLM to ask clarifying questions if confidence is low
