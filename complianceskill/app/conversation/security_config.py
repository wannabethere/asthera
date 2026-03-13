"""
Security Agents Conversation Configuration

Configuration objects for Compliance and Detection & Triage conversation behavior.
Unlike LMS VerticalConversationConfig, security configs use static option sets
rather than vector concept lookup.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.conversation.config import ScopingQuestionTemplate


@dataclass
class SecurityConversationConfig:
    """Configuration for security agent conversation behavior."""
    agent_id: str  # Identifier for logging and route prefixes. 'compliance' | 'detection_triage'
    display_name: str  # Human-facing agent name shown in Lexy UI
    framework_options: List[Dict[str, str]]  # All selectable frameworks. Each has id, label, description
    datasource_options: List[Dict[str, str]]  # All selectable security tools. Each has id, label
    template_options: Optional[List[Dict[str, str]]] = None  # DT only. A/B/C template choices
    scoping_question_templates: Dict[str, ScopingQuestionTemplate] = field(default_factory=dict)  # Maps filter_name → question
    always_include_filters: List[str] = field(default_factory=lambda: ['severity', 'time_period'])  # Filter names always asked
    intent_options: List[Dict[str, str]] = field(default_factory=list)  # Selectable intents shown in intent_confirm_node
    requires_execution_preview: bool = True  # If True, execution_preview_node fires after scoping
    intent_to_workflow: Dict[str, str] = field(default_factory=dict)  # Maps confirmed intent → downstream workflow id
    state_key_prefix: str = ""  # Prefix for all conversation state keys. 'compliance' or 'dt'
    max_scoping_questions_per_turn: int = 3  # Cap on questions shown in a single scoping turn

    def __post_init__(self):
        """Set state_key_prefix from agent_id if not provided."""
        if not self.state_key_prefix:
            self.state_key_prefix = self.agent_id
