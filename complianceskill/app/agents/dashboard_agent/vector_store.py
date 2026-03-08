"""
CCE Template Scoring Utilities
===============================
Re-exports from the service layer. All registry, scoring, and vector store
logic lives in app.services.dashboard_template_vector_store.

This module provides backward compatibility for dashboard_agent nodes and tools.
For new code, import from app.services.dashboard_template_service or
app.services.dashboard_template_vector_store directly.
"""

from __future__ import annotations

from app.services.dashboard_template_vector_store import (
    score_templates_hybrid,
    ALL_TEMPLATES as TEMPLATES,
    ALL_CATEGORIES as CATEGORIES,
    score_all_templates,
)

__all__ = [
    "score_templates_hybrid",
    "TEMPLATES",
    "CATEGORIES",
    "score_all_templates",
]
