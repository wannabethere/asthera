"""
Skill Validator Node — Phase 4 of the skill pipeline.

Runs *after* the metrics recommender.  Applies skill-specific penalty/boost
rules and filters recommendations by the skill's relevance threshold.

If ``skill_context`` is None, this node is a pass-through — the existing
scoring from ``csod_scoring_validator`` stands as-is.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.skills import SkillRegistry
from app.agents.skills.nodes.skill_intent_node import SKILL_CONTEXT_KEY

logger = logging.getLogger(__name__)

# State keys
SKILL_VALIDATED_METRICS_KEY = "skill_validated_metrics"
SKILL_VALIDATION_REPORT_KEY = "skill_validation_report"


def skill_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 4: Validate and filter recommended metrics using skill-specific rules.

    Reads:
        - skill_context (from Phase 1)
        - csod_metric_recommendations (from metrics recommender)
        - dt_scored_metrics (fallback for DT workflow)
        - skill_recommender_context (from Phase 3)

    Writes:
        - skill_validated_metrics: filtered list of metrics that pass validation
        - skill_validation_report: {kept, dropped, warnings, summary}
        - csod_metric_recommendations: OVERWRITTEN with validated metrics
          (traditional path continues to read this key)

    The validator applies two layers:
      1. **Rule-based scoring** from skill definition's validator_rules
         (penalty_rules, boost_rules, threshold, caps)
      2. **LLM validation** (optional) if the skill has a validator.md prompt
         — for complex checks like deduplication or field completeness
    """
    skill_context = state.get(SKILL_CONTEXT_KEY)

    if not skill_context or not skill_context.get("confirmed", False):
        state[SKILL_VALIDATED_METRICS_KEY] = None
        state[SKILL_VALIDATION_REPORT_KEY] = None
        return state

    skill_id = skill_context["skill_id"]
    registry = SkillRegistry.instance()
    skill = registry.get(skill_id)

    if not skill:
        state[SKILL_VALIDATED_METRICS_KEY] = None
        state[SKILL_VALIDATION_REPORT_KEY] = None
        return state

    # Get the metrics to validate (CSOD path or DT path)
    metrics = state.get("csod_metric_recommendations") or state.get("dt_scored_metrics") or []

    if not metrics:
        state[SKILL_VALIDATED_METRICS_KEY] = []
        state[SKILL_VALIDATION_REPORT_KEY] = {"summary": {"total_candidates": 0, "passed": 0, "dropped": 0, "warnings": 0}}
        return state

    # Phase 4a: Rule-based scoring adjustments
    rules = skill.validator_rules
    validated, dropped, warnings = _apply_rules(metrics, rules, skill_context)

    # Phase 4b: Optional LLM validation
    prompt_text = skill.get_prompt("validator")
    if prompt_text and validated:
        try:
            validated, extra_dropped, extra_warnings = _invoke_validator_llm(
                prompt_text, validated, skill, skill_context, state
            )
            dropped.extend(extra_dropped)
            warnings.extend(extra_warnings)
        except Exception:
            logger.warning("Skill validator LLM failed for '%s' — using rule-based only", skill_id, exc_info=True)

    # Apply max_metrics cap
    if len(validated) > rules.max_metrics:
        # Sort by adjusted_score descending, keep top N
        validated.sort(key=lambda m: m.get("_adjusted_score", m.get("composite_score", 0)), reverse=True)
        overflow = validated[rules.max_metrics:]
        validated = validated[:rules.max_metrics]
        for m in overflow:
            dropped.append({
                "metric_id": m.get("metric_id", m.get("name", "unknown")),
                "reason": "max_metrics_cap",
                "adjusted_score": m.get("_adjusted_score", 0),
            })

    # Build report
    report = {
        "validated_metrics": [m.get("metric_id", m.get("name", "unknown")) for m in validated],
        "dropped_metrics": dropped,
        "validation_warnings": warnings,
        "summary": {
            "total_candidates": len(metrics),
            "passed": len(validated),
            "dropped": len(dropped),
            "warnings": len(warnings),
        },
    }

    # Clean internal scoring keys before writing back
    for m in validated:
        m.pop("_adjusted_score", None)
        m.pop("_penalty_log", None)
        m.pop("_boost_log", None)

    state[SKILL_VALIDATED_METRICS_KEY] = validated
    state[SKILL_VALIDATION_REPORT_KEY] = report

    # Overwrite the standard metrics key so downstream nodes (output assembler,
    # dashboard generator, etc.) consume the validated set
    if state.get("csod_metric_recommendations") is not None:
        state["csod_metric_recommendations"] = validated
    elif state.get("dt_scored_metrics") is not None:
        state["dt_scored_metrics"] = validated

    _log_skill_step(state, "skill_validator", skill_id, report)

    return state


# ── Rule-based scoring ────────────────────────────────────────────────────────

def _apply_rules(
    metrics: List[Dict[str, Any]],
    rules: Any,
    skill_context: Dict[str, Any],
) -> tuple:
    """
    Apply penalty/boost rules and threshold filtering.

    Returns (validated, dropped, warnings).
    """
    validated: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    for m in metrics:
        base_score = m.get("composite_score", m.get("score", 0.50))
        adjusted = float(base_score)
        penalty_log: List[str] = []
        boost_log: List[str] = []

        # Check required fields
        for field in rules.required_fields_per_metric:
            if not m.get(field):
                adjusted -= 0.15
                penalty_log.append(f"missing_required_field:{field}")
                warnings.append({
                    "metric_id": m.get("metric_id", m.get("name", "unknown")),
                    "warning": f"missing_{field}",
                    "impact": f"Required field '{field}' not present",
                })

        # Apply penalty rules (keyword-based matching)
        for rule in rules.penalty_rules:
            penalty_val = _extract_score_adjustment(rule)
            if penalty_val and _rule_matches_metric(rule, m, skill_context):
                adjusted += penalty_val  # penalty_val is negative
                penalty_log.append(rule[:60])

        # Apply boost rules
        for rule in rules.boost_rules:
            boost_val = _extract_score_adjustment(rule)
            if boost_val and _rule_matches_metric(rule, m, skill_context):
                adjusted += boost_val  # boost_val is positive
                boost_log.append(rule[:60])

        m["_adjusted_score"] = round(adjusted, 4)
        m["_penalty_log"] = penalty_log
        m["_boost_log"] = boost_log

        if adjusted >= rules.relevance_threshold:
            validated.append(m)
        else:
            dropped.append({
                "metric_id": m.get("metric_id", m.get("name", "unknown")),
                "reason": "below_threshold",
                "adjusted_score": round(adjusted, 4),
                "original_score": round(base_score, 4),
                "penalties": penalty_log,
            })

    # Minimum metrics safety net
    if len(validated) < 3 and dropped:
        # Lower threshold by 0.10 and retry
        lower_threshold = rules.relevance_threshold - 0.10
        rescued = [
            d for d in dropped
            if d.get("adjusted_score", 0) >= lower_threshold
        ]
        if rescued:
            # Find the original metrics for rescued items
            rescued_ids = {d["metric_id"] for d in rescued}
            for m in metrics:
                mid = m.get("metric_id", m.get("name", "unknown"))
                if mid in rescued_ids and m not in validated:
                    validated.append(m)
                    warnings.append({
                        "metric_id": mid,
                        "warning": "rescued_below_threshold",
                        "impact": f"Rescued with lowered threshold {lower_threshold}",
                    })
            dropped = [d for d in dropped if d["metric_id"] not in rescued_ids]

    return validated, dropped, warnings


def _extract_score_adjustment(rule_text: str) -> Optional[float]:
    """Extract a numeric adjustment from a rule string like 'penalize X (-0.15)'."""
    import re
    match = re.search(r"([+-]?\d+\.?\d*)", rule_text.split("(")[-1] if "(" in rule_text else "")
    if match:
        val = float(match.group(1))
        if "penalize" in rule_text.lower() or "penalty" in rule_text.lower():
            return -abs(val)
        return abs(val)
    return None


def _rule_matches_metric(
    rule_text: str,
    metric: Dict[str, Any],
    skill_context: Dict[str, Any],
) -> bool:
    """
    Simple keyword-based rule matching.

    Checks if the rule description's keywords appear in the metric's
    serialized JSON.  This is intentionally loose — the LLM validator
    (Phase 4b) handles nuanced matching.
    """
    rule_lower = rule_text.lower()
    metric_str = json.dumps(metric, default=str).lower()

    # Extract key terms from the rule (before the score adjustment)
    rule_desc = rule_text.split("(")[0].strip().lower() if "(" in rule_text else rule_lower
    # Remove common prefixes
    for prefix in ("penalize ", "boost ", "penalty: ", "boost: "):
        if rule_desc.startswith(prefix):
            rule_desc = rule_desc[len(prefix):]
            break

    # Check if key terms from rule appear in metric
    terms = [t.strip() for t in rule_desc.split() if len(t.strip()) > 3]
    if not terms:
        return False

    match_count = sum(1 for t in terms if t in metric_str)
    return match_count >= max(1, len(terms) // 2)


# ── Optional LLM validation ──────────────────────────────────────────────────

def _invoke_validator_llm(
    prompt_text: str,
    metrics: List[Dict[str, Any]],
    skill: Any,
    skill_context: Dict[str, Any],
    state: Dict[str, Any],
) -> tuple:
    """
    Run the skill's validator prompt for nuanced checks (dedup, field completeness, etc.).

    Returns (validated, extra_dropped, extra_warnings).
    """
    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text.replace("{", "{{").replace("}", "}}")),
        ("human", "{input}"),
    ])

    # Build a condensed view of metrics for the LLM
    metric_summaries = []
    for m in metrics[:20]:  # Cap at 20 to stay within token limits
        summary = {
            "metric_id": m.get("metric_id", m.get("name", "unknown")),
            "name": m.get("name", m.get("metric_id", "")),
            "composite_score": m.get("composite_score", 0),
            "adjusted_score": m.get("_adjusted_score", 0),
            "metric_type": m.get("metric_type", "unknown"),
        }
        # Add skill-relevant fields
        for f in skill.validator_rules.required_fields_per_metric:
            summary[f] = m.get(f)
        metric_summaries.append(summary)

    human_msg = (
        f"User query: {state.get('user_query', '')}\n\n"
        f"Skill: {skill.display_name}\n\n"
        f"Metrics to validate ({len(metric_summaries)}):\n"
        f"```json\n{json.dumps(metric_summaries, indent=2, default=str)}\n```"
    )

    chain = prompt | llm
    response = chain.invoke({"input": human_msg})
    content = response.content if hasattr(response, "content") else str(response)

    parsed = _parse_json(content)
    if not parsed or not isinstance(parsed, dict):
        return metrics, [], []

    # If LLM returns dropped_metrics, remove them
    llm_dropped_ids = {
        d.get("metric_id") for d in parsed.get("dropped_metrics", [])
    }
    extra_dropped = parsed.get("dropped_metrics", [])
    extra_warnings = parsed.get("validation_warnings", [])

    if llm_dropped_ids:
        metrics = [
            m for m in metrics
            if m.get("metric_id", m.get("name", "unknown")) not in llm_dropped_ids
        ]

    return metrics, extra_dropped, extra_warnings


def _parse_json(text: str) -> Any:
    import re
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _log_skill_step(state: Dict[str, Any], step_name: str, skill_id: str, report: Dict) -> None:
    from datetime import datetime
    if "execution_steps" not in state:
        state["execution_steps"] = []
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": f"skill:{skill_id}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "inputs": {"skill_id": skill_id},
        "outputs": report.get("summary", {}),
    })
