"""Load CSOD skills_config.json and map skills/workflows to agent IDs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SKILLS_CONFIG_PATH = Path(__file__).resolve().parent / "skills_config.json"


def load_skills_config() -> Dict[str, Any]:
    """Load skills configuration from JSON file."""
    try:
        if SKILLS_CONFIG_PATH.exists():
            with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning(
            "Skills config not found at %s, using defaults", SKILLS_CONFIG_PATH
        )
        return _get_default_skills_config()
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Error loading skills config: %s", e, exc_info=True)
        return _get_default_skills_config()


def _get_default_skills_config() -> Dict[str, Any]:
    """Default skills configuration fallback."""
    return {
        "skills": {
            "metrics_recommendations": {
                "display_name": "Metrics Recommendations",
                "agents": ["csod_workflow"],
            },
            "causal_analysis": {
                "display_name": "Causal Analysis",
                "agents": ["csod_workflow"],
            },
        },
        "agent_mapping": {
            "csod_workflow": {
                "agent_id": "csod-workflow",
            },
            "csod_metric_advisor_workflow": {
                "agent_id": "csod-workflow",
            },
        },
        "default_agent": "csod_workflow",
    }


def get_agent_for_skill(
    skill_id: str, skills_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Get the agent workflow key for a given skill (first agent in skill.agents).
    """
    if skills_config is None:
        skills_config = load_skills_config()

    skill_info = skills_config.get("skills", {}).get(skill_id, {})
    agents = skill_info.get("agents", [])

    if agents:
        return agents[0]

    return skills_config.get("default_agent", "csod_workflow")


def get_agent_id_from_workflow(
    workflow_name: str, skills_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Resolve LangGraph agent_id from workflow name using skills config agent_mapping.
    """
    if skills_config is None:
        skills_config = load_skills_config()

    agent_mapping = skills_config.get("agent_mapping", {})
    workflow_info = agent_mapping.get(workflow_name, {})
    agent_id = workflow_info.get("agent_id")

    if agent_id:
        return agent_id

    if workflow_name == "csod_metric_advisor_workflow":
        return "csod-workflow"
    if workflow_name == "csod_workflow":
        return "csod-workflow"
    return "csod-workflow"
