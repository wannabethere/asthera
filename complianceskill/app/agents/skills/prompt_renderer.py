"""
Skill Prompt Renderer — resolves generic templates with skill definition values.

Skills can have:
  1. **Dedicated prompts** in ``prompts/<skill_id>/`` — used as-is (gap_analysis, crown_jewel, anomaly_detection)
  2. **Generic templates** in ``prompts/_generic/`` — interpolated with skill definition fields

The renderer checks for a dedicated prompt first; if absent, falls back to
the generic template with ``{{placeholder}}`` substitution from the skill JSON.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.agents.skills.base_skill import AnalysisSkill

logger = logging.getLogger(__name__)

_PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"
_GENERIC_DIR = _PROMPTS_ROOT / "_generic"

# Phase → filename mapping
_PHASE_FILES = {
    "intent_identifier": "intent_identifier.md",
    "analysis_planner": "analysis_planner.md",
    "metric_instructions": "metric_instructions.md",
    "validator": "validator.md",
}


def render_skill_prompt(skill: AnalysisSkill, phase: str) -> Optional[str]:
    """
    Resolve the prompt for *skill* and *phase*.

    Resolution order:
      1. ``prompts/<skill_id>/<phase>.md`` (dedicated — returned verbatim)
      2. ``prompts/_generic/<phase>.md``   (template — interpolated from skill definition)
      3. ``None`` (no template available)
    """
    filename = _PHASE_FILES.get(phase)
    if not filename:
        logger.warning("Unknown skill prompt phase: %s", phase)
        return None

    # 1. Check for dedicated prompt
    dedicated = _PROMPTS_ROOT / skill.skill_id / filename
    if dedicated.is_file():
        return dedicated.read_text(encoding="utf-8")

    # 2. Fall back to generic template
    generic = _GENERIC_DIR / filename
    if not generic.is_file():
        return None

    template = generic.read_text(encoding="utf-8")
    return _interpolate(template, skill, phase)


def _interpolate(template: str, skill: AnalysisSkill, phase: str) -> str:
    """Replace ``{{placeholder}}`` tokens with values from the skill definition."""
    dp = skill.data_plan
    ri = skill.recommender_instructions
    vr = skill.validator_rules
    dt = dp.dt_config
    cce = dp.cce_config

    replacements: Dict[str, str] = {
        # ── Core identity ───────────────────────────────────────────
        "skill_id": skill.skill_id,
        "skill_display_name": skill.display_name,
        "skill_description": skill.description,
        "skill_category": skill.category,

        # ── Intent signals ──────────────────────────────────────────
        "intent_keywords": ", ".join(skill.intent_signals.keywords) or "none specified",
        "intent_patterns": _bullet_list(skill.intent_signals.question_patterns) or "- none specified",
        "analysis_requirements": ", ".join(skill.intent_signals.analysis_requirements) or "none",
        "analysis_requirements_list": ", ".join(
            f'"{r}"' for r in skill.intent_signals.analysis_requirements
        ) or "",

        # ── Data plan ───────────────────────────────────────────────
        "metric_types": ", ".join(dp.metric_types) or "any",
        "primary_metric_type": dp.metric_types[0] if dp.metric_types else "current_state",
        "required_data_elements": ", ".join(dp.required_data_elements) or "none specified",
        "required_data_elements_list": _bullet_list(dp.required_data_elements) or "- (none specified)",
        "kpi_focus": ", ".join(dp.kpi_focus) or "any",
        "transformations": _bullet_list(dp.transformations) or "- (none specified)",
        "transformations_list": _numbered_list(dp.transformations) or "1. (none specified)",

        # ── DT config ──────────────────────────────────────────────
        "dt_group_by": dt.dt_group_by if dt else "goal",
        "dt_min_composite": str(dt.min_composite) if dt else "0.55",

        # ── CCE config ─────────────────────────────────────────────
        "cce_mode": cce.mode if cce else "disabled",
        "cce_provides": cce.provides if cce else "none",
        "cce_uses": cce.uses if cce else "not applicable",
        "cce_usage_short": cce.uses.split("—")[0].strip() if cce and cce.uses else "general",
        "cce_planning_instruction": _cce_planning_instruction(cce),

        # ── Recommender instructions ────────────────────────────────
        "framing": ri.framing or "general",
        "framing_description": _framing_description(ri),
        "metric_selection_bias": ri.metric_selection_bias or "No specific bias — select the most relevant metrics.",
        "output_guidance": ri.output_guidance or "Standard metric recommendation output.",
        "causal_usage": ri.causal_usage or "No specific causal usage for this analysis type.",
        "metric_type_specific_guidance": _metric_type_guidance(dp.metric_types),

        # ── Validator rules ─────────────────────────────────────────
        "relevance_threshold": str(vr.relevance_threshold),
        "max_metrics": str(vr.max_metrics),
        "required_fields_check": _required_fields_check(vr),
        "penalty_rules": _bullet_list(vr.penalty_rules) or "- (no penalties defined)",
        "boost_rules": _bullet_list(vr.boost_rules) or "- (no boosts defined)",
        "transformation_compatibility": _transformation_compat(dp.transformations),
    }

    result = template
    for key, val in replacements.items():
        result = result.replace("{{" + key + "}}", val)

    return result


# ── Formatting helpers ────────────────────────────────────────────────────────

def _bullet_list(items: list) -> str:
    return "\n".join(f"- {item}" for item in items) if items else ""


def _numbered_list(items: list) -> str:
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items)) if items else ""


def _cce_planning_instruction(cce: Any) -> str:
    if not cce or not cce.enabled:
        return "Causal graph is NOT required for this analysis — skip causal context planning"
    if cce.mode == "required":
        return f"Causal graph is REQUIRED — plan for {cce.provides or 'causal edges'} to support {cce.uses or 'analysis'}"
    return f"Causal graph is OPTIONAL — include if available for enhanced {cce.uses or 'analysis'}"


def _framing_description(ri: Any) -> str:
    parts = []
    if ri.framing:
        parts.append(f"Frame every metric recommendation as a **{ri.framing}** analysis.")
    if ri.output_guidance:
        parts.append(f"\n{ri.output_guidance}")
    return "\n".join(parts) if parts else "Standard analysis framing — recommend the most relevant metrics."


def _metric_type_guidance(metric_types: list) -> str:
    if "trend" in metric_types and "current_state" not in metric_types:
        return "Queries MUST request time-series data (e.g., 'weekly X for the last 12 weeks'), NOT point-in-time snapshots."
    if "current_state" in metric_types and "trend" not in metric_types:
        return "Queries should request current/latest values, NOT historical time-series."
    return "Queries can request either current values or time-series depending on the metric."


def _required_fields_check(vr: Any) -> str:
    if not vr.required_fields_per_metric:
        return "No strict required fields for this analysis type — validation focuses on relevance scoring."
    fields = ", ".join(f"`{f}`" for f in vr.required_fields_per_metric)
    return (
        f"Every recommended metric MUST have: {fields}.\n"
        f"Metrics missing these fields receive a **-0.15** penalty per missing field.\n"
        f"Metrics missing ALL required fields are **dropped**."
    )


def _transformation_compat(transformations: list) -> str:
    if not transformations:
        return "- No specific transformations required — standard metric output is sufficient."
    return _bullet_list(
        f"Can this metric support: *{t}*?" for t in transformations[:5]
    )
