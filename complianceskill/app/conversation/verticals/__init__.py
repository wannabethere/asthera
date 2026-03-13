"""
Vertical-Specific Conversation Configurations

Each vertical has its own config file that defines:
- Scoping question templates
- Supported datasources
- Intent-to-workflow mappings
- Collection names
"""
from app.conversation.verticals.lms_config import (
    LMS_CONVERSATION_CONFIG,
    LMS_SCOPING_TEMPLATES,
)

__all__ = [
    "LMS_CONVERSATION_CONFIG",
    "LMS_SCOPING_TEMPLATES",
]
