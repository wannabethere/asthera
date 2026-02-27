"""
CCE Template Registry — 17 Dashboard Templates
================================================
All templates from the Layout Advisor, structured for:
1. Direct lookup by ID
2. Vector store embedding (description + best_for + domains)
3. Scoring against user decisions

This module loads templates from templates_registry.json for consistency
with the dashboard_registry.json and ld_templates_registry.json formats.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

# Load from JSON registry
_REGISTRY_PATH = Path(__file__).parent / "registry_config" / "templates_registry.json"

def _load_template_registry() -> Dict[str, Any]:
    """Load base templates registry from JSON file."""
    try:
        with open(_REGISTRY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Templates registry not found at {_REGISTRY_PATH}. "
            "Please ensure templates_registry.json exists."
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {_REGISTRY_PATH}: {e}")

_registry_data = _load_template_registry()

# Extract templates as dict keyed by id
TEMPLATES: dict[str, dict] = {
    template["id"]: template
    for template in _registry_data["templates"]
}

# Extract categories
CATEGORIES: dict[str, dict] = _registry_data["categories"]

# Extract decision tree
DECISION_TREE: List[dict] = _registry_data["decision_tree"]

# Extract auto-resolve hints
AUTO_RESOLVE_HINTS: dict[str, dict] = _registry_data["auto_resolve_hints"]


def get_template_embedding_text(template: dict) -> str:
    """Build the text blob to embed for vector similarity search."""
    parts = [
        template["name"],
        template["description"],
        f"Category: {template['category']}",
        f"Domains: {', '.join(template['domains'])}",
        f"Best for: {', '.join(template['best_for'])}",
        f"Complexity: {template['complexity']}",
        f"Primitives: {', '.join(template['primitives'])}",
        f"Has chat: {template['has_chat']}",
        f"Has graph: {template.get('has_graph', False)}",
    ]
    if template.get("strip_example"):
        parts.append(f"KPI examples: {', '.join(template['strip_example'])}")
    return "\n".join(parts)
