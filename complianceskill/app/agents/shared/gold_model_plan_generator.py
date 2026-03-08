"""
Gold Model Plan Generator — backward-compatible re-export.

All implementation lives in app.agents.shared.gold_model_generation.
Import from here or from gold_model_generation for the same behavior.
"""
from app.agents.shared.gold_model_generation import (
    GoldModelPlan,
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
    GoldModelSpecification,
    OutputColumn,
    SilverTableInfo,
    SourceTableColumn,
)

__all__ = [
    "GoldModelPlan",
    "GoldModelPlanGenerator",
    "GoldModelPlanGeneratorInput",
    "GoldModelSpecification",
    "OutputColumn",
    "SilverTableInfo",
    "SourceTableColumn",
]
