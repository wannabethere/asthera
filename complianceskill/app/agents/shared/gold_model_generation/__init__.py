"""
Gold Model Generation — shared for CSOD and DT workflows.

Generates gold model plans and dbt SQL from metrics and silver tables.
Structured like cubejs_generation with models, plan_generator, sql_generator, and prompts.
"""
from .models import (
    OutputColumn,
    SourceTableColumn,
    GoldModelSpecification,
    GoldModelPlan,
    SilverModelSpecification,
    SilverTableInfo,
    GoldModelPlanGeneratorInput,
    GeneratedGoldModelSQL,
    GoldModelSQLResponse,
)
from .example_loader import load_examples_for_domain, load_examples_for_model
from .plan_generator import GoldModelPlanGenerator
from .sql_generator import GoldModelSQLGenerator
from .medallion_plan_utils import create_minimal_plan_for_missing_silver

__all__ = [
    "OutputColumn",
    "SourceTableColumn",
    "GoldModelSpecification",
    "GoldModelPlan",
    "SilverModelSpecification",
    "SilverTableInfo",
    "GoldModelPlanGeneratorInput",
    "GoldModelPlanGenerator",
    "GeneratedGoldModelSQL",
    "GoldModelSQLResponse",
    "GoldModelSQLGenerator",
    "create_minimal_plan_for_missing_silver",
    "load_examples_for_domain",
    "load_examples_for_model",
]
