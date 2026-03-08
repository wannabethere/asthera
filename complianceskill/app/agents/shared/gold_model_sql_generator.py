"""
Gold Model SQL Generator — backward-compatible re-export.

All implementation lives in app.agents.shared.gold_model_generation.
Import from here or from gold_model_generation for the same behavior.
"""
from app.agents.shared.gold_model_generation import (
    GeneratedGoldModelSQL,
    GoldModelPlan,
    GoldModelSQLGenerator,
    GoldModelSQLResponse,
)

__all__ = [
    "GeneratedGoldModelSQL",
    "GoldModelPlan",
    "GoldModelSQLGenerator",
    "GoldModelSQLResponse",
]
