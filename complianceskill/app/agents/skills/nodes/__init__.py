"""
Skill node functions — generic LangGraph nodes parameterized by loaded skills.

These nodes are **enhancement layers** that sit alongside the existing workflow
nodes.  When a skill definition exists for the detected intent and the feature
flag ``skill_pipeline_enabled`` is True, these nodes activate.  Otherwise, the
traditional (non-skill) path executes unchanged.
"""
from app.agents.skills.nodes.skill_intent_node import skill_intent_identifier_node  # noqa: F401
from app.agents.skills.nodes.skill_planner_node import skill_analysis_planner_node  # noqa: F401
from app.agents.skills.nodes.skill_recommender_node import skill_recommender_node  # noqa: F401
from app.agents.skills.nodes.skill_validator_node import skill_validator_node  # noqa: F401
