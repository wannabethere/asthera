"""
Conversation Engine Configuration

Generic configuration objects that drive conversation behavior.
No vertical-specific logic - pure metadata containers.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ScopingQuestionTemplate:
    """Template for a scoping question - maps filter_name to question."""
    filter_name: str  # Must match exactly one value in area.filters[]
    question_id: str  # Stable identifier for the question
    label: str  # Plain-English question shown to user
    interaction_mode: str  # 'single' for single-select chips, 'multi' for multi-select
    options: List[Dict[str, str]]  # Available chip options. Each has 'id' and 'label'
    state_key: str  # Key in scoping_answers dict that this answer populates
    required: bool = False  # If True, question is always included when filter is matched


@dataclass
class VerticalConversationConfig:
    """Configuration for a vertical's conversation behavior."""
    vertical_id: str  # Identifier used in logging, state keys, route prefixes
    display_name: str  # Human-facing vertical name shown in Lexy UI header
    l1_collection: str  # ChromaDB collection name for concept-level (L1) vector lookup
    l2_collection: str  # ChromaDB collection name for recommendation area (L2) vector lookup
    supported_datasources: List[Dict[str, str]]  # Available datasources. Each has id, display_name, description
    scoping_question_templates: Dict[str, ScopingQuestionTemplate]  # Maps filter_name -> template
    always_include_filters: List[str] = field(default_factory=list)  # Filter names always asked
    intent_to_workflow: Dict[str, str] = field(default_factory=dict)  # Maps intent -> workflow name
    default_workflow: str = "csod_workflow"  # Fallback workflow if intent doesn't match
    max_scoping_questions_per_turn: int = 3  # Cap on questions shown in a single scoping turn
    # Pre-planner: goal_intent checkpoint + LLM goal_output_intent (shared routing → dbt/cube flags)
    enable_goal_intent_phases: bool = True
