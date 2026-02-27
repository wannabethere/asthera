"""
CCE Template Registry — Learning & Development Extensions
===========================================================
6 new dashboard templates derived from Cornerstone/CSOD-style 
LMS analytics dashboards. These extend the base 17 templates
to cover the full spectrum of L&D reporting.

Templates:
  18. training-plan-tracker     — Training Plan Summary + Assign Details table
  19. team-training-analytics   — Team-level compliance & score distribution
  20. learner-profile           — Individual learner deep-dive (dark)
  21. learning-development-ops  — L&D Operations: org-level, vendor, cost analytics
  22. learning-measurement      — Enterprise measurement: ILT, courses, learner demographics
  23. lms-engagement            — Login/engagement analytics + recent activity

This module loads templates from ld_templates_registry.json for consistency
with the dashboard_registry.json format.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

# Load from JSON registry
_REGISTRY_PATH = Path(__file__).parent / "ld_templates_registry.json"

def _load_ld_registry() -> Dict[str, Any]:
    """Load L&D templates registry from JSON file."""
    try:
        with open(_REGISTRY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"L&D templates registry not found at {_REGISTRY_PATH}. "
            "Please ensure ld_templates_registry.json exists."
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {_REGISTRY_PATH}: {e}")

_registry_data = _load_ld_registry()

# Extract templates as dict keyed by id
LD_TEMPLATES: dict[str, dict] = {
    template["id"]: template
    for template in _registry_data["templates"]
}

# Extract categories
LD_CATEGORIES: dict[str, dict] = _registry_data["categories"]

# Extract decision options
LD_DECISION_OPTIONS: dict[str, List[dict]] = _registry_data["decision_options"]

# Extract auto-resolve hints
LD_AUTO_RESOLVE_HINTS: dict[str, dict] = _registry_data["auto_resolve_hints"]


def get_ld_template_embedding_text(template: dict) -> str:
    """Build embedding text for L&D templates."""
    parts = [
        template["name"],
        template["description"],
        f"Category: {template['category']}",
        f"Domains: {', '.join(template['domains'])}",
        f"Best for: {', '.join(template['best_for'])}",
        f"Complexity: {template['complexity']}",
        f"Primitives: {', '.join(template['primitives'])}",
        f"Has chat: {template['has_chat']}",
        f"Theme: {template['theme_hint']}",
    ]
    if template.get("strip_example"):
        parts.append(f"KPI examples: {', '.join(template['strip_example'])}")
    if template.get("chart_types"):
        parts.append(f"Chart types: {', '.join(template['chart_types'])}")
    if template.get("table_columns") and isinstance(template["table_columns"], list):
        parts.append(f"Table columns: {', '.join(template['table_columns'])}")
    if template.get("activity_types"):
        parts.append(f"Activity types: {', '.join(template['activity_types'])}")
    return "\n".join(parts)
