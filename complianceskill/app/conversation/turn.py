"""
Conversation Turn Engine - Core Data Structures

Defines the data structures for conversation turns, checkpoints, and questions.
All structures are JSON-serializable for API responses.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TurnOutputType(str, Enum):
    """Type of conversation turn - drives frontend widget selection."""
    CONFIRMATION = "confirmation"  # Lexy restates intent - user verifies or adjusts
    SCOPING = "scoping"  # Lexy needs more information before proceeding
    DECISION = "decision"  # Meaningful path fork - each option leads to different output
    METRIC_NARRATION = "metric_narration"  # Lexy explains what it will measure and why
    EXECUTION_PREVIEW = "execution_preview"  # Lexy summarises execution plan - user approves before execution
    CROSS_CONCEPT_CHECK = "cross_concept_check"  # Optional enrichment from related analytical domains
    INTENT_SELECTION = "intent_selection"  # Multi-intent/project selection — user picks focus area(s) before scoping


@dataclass
class TurnQuestion:
    """A single question in a conversation turn."""
    id: str  # Stable identifier for the question
    label: str  # Plain-English question shown to user
    interaction_mode: str  # 'single' for single-select chips, 'multi' for multi-select
    options: List[Dict[str, str]]  # Available chip options. Each has 'id' and 'label'
    state_key: str  # Key in scoping_answers dict that this answer populates
    required: bool = False  # If True, question is always included when filter is matched
    default_value: Optional[str] = None  # Pre-selected option id extracted from user query


@dataclass
class ConversationTurn:
    """A conversation turn sent to the frontend."""
    phase: str  # Current phase identifier (e.g., 'concept_confirm', 'scoping')
    turn_type: TurnOutputType  # Type of turn - drives frontend widget selection
    message: str  # Main message from Lexy
    questions: List[TurnQuestion] = field(default_factory=list)  # Questions for SCOPING turns
    options: List[Dict[str, Any]] = field(default_factory=list)  # Options for CONFIRMATION/DECISION turns
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata (metrics, kpis, etc.)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "phase": self.phase,
            "turn_type": self.turn_type.value,
            "message": self.message,
            "questions": [
                {
                    "id": q.id,
                    "label": q.label,
                    "interaction_mode": q.interaction_mode,
                    "options": q.options,
                    "state_key": q.state_key,
                    "required": q.required,
                    "default_value": q.default_value,
                }
                for q in self.questions
            ],
            "options": self.options,
            "metadata": self.metadata,
        }


@dataclass
class ConversationCheckpoint:
    """Checkpoint written to state when graph needs to pause for user input."""
    phase: str  # Phase identifier
    turn: ConversationTurn  # The turn to show to user
    resume_with_field: str  # State field to inject user response into
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional checkpoint metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "phase": self.phase,
            "turn": {
                "phase": self.turn.phase,
                "turn_type": self.turn.turn_type.value,
                "message": self.turn.message,
                "questions": [
                    {
                        "id": q.id,
                        "label": q.label,
                        "interaction_mode": q.interaction_mode,
                        "options": q.options,
                        "state_key": q.state_key,
                        "required": q.required,
                        "default_value": q.default_value,
                    }
                    for q in self.turn.questions
                ],
                "options": self.turn.options,
                "metadata": self.turn.metadata,
            },
            "resume_with_field": self.resume_with_field,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationCheckpoint":
        """Create from dict (for deserialization)."""
        turn_data = data["turn"]
        questions = [
            TurnQuestion(
                id=q["id"],
                label=q["label"],
                interaction_mode=q["interaction_mode"],
                options=q["options"],
                state_key=q["state_key"],
                required=q.get("required", False),
                default_value=q.get("default_value"),
            )
            for q in turn_data.get("questions", [])
        ]
        turn = ConversationTurn(
            phase=turn_data["phase"],
            turn_type=TurnOutputType(turn_data["turn_type"]),
            message=turn_data["message"],
            questions=questions,
            options=turn_data.get("options", []),
            metadata=turn_data.get("metadata", {}),
        )
        return cls(
            phase=data["phase"],
            turn=turn,
            resume_with_field=data["resume_with_field"],
            metadata=data.get("metadata", {}),
        )
