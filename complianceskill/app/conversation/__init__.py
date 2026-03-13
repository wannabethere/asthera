"""
Conversation Engine - Generic Multi-Turn Conversation Framework

This package provides a generic conversation turn engine that works for any vertical.
All conversation behavior is driven by VerticalConversationConfig - no vertical-specific
logic in the engine itself.
"""
from app.conversation.config import VerticalConversationConfig, ScopingQuestionTemplate
from app.conversation.turn import (
    ConversationCheckpoint,
    ConversationTurn,
    TurnOutputType,
    TurnQuestion,
)
from app.conversation.planner_workflow import (
    build_conversation_planner_workflow,
    create_conversation_planner_app,
)

__all__ = [
    "VerticalConversationConfig",
    "ScopingQuestionTemplate",
    "ConversationCheckpoint",
    "ConversationTurn",
    "TurnOutputType",
    "TurnQuestion",
    "build_conversation_planner_workflow",
    "create_conversation_planner_app",
]
