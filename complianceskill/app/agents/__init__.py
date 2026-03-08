"""
Compliance automation agents and workflows.

This package provides LangGraph-based agents for automating compliance
artifact generation, including SIEM rules, playbooks, test scripts, and more.
"""

from app.agents.state import (
    EnhancedCompliancePipelineState,
    PlanStep,
    ValidationResult,
)
from app.agents.detectiontriageworkflows.workflow import (
    build_compliance_workflow,
    create_compliance_app,
    get_compliance_app,
)
from app.agents.prompt_loader import load_prompt
from app.agents.shared.tool_integration import (
    get_tools_for_agent,
    create_tool_calling_agent,
    should_use_tool_calling_agent,
    intelligent_retrieval,
)
from app.agents.shared.gold_model_plan_generator import (
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
    GoldModelPlan,
    GoldModelSpecification,
    OutputColumn,
    SilverTableInfo,
    SourceTableColumn,
)

__all__ = [
    # State types
    "EnhancedCompliancePipelineState",
    "PlanStep",
    "ValidationResult",
    # Workflow functions
    "build_compliance_workflow",
    "create_compliance_app",
    "get_compliance_app",
    # Utilities
    "load_prompt",
    # Tool integration
    "get_tools_for_agent",
    "create_tool_calling_agent",
    "should_use_tool_calling_agent",
    "intelligent_retrieval",
    # Gold model plan generator
    "GoldModelPlanGenerator",
    "GoldModelPlanGeneratorInput",
    "GoldModelPlan",
    "GoldModelSpecification",
    "OutputColumn",
    "SilverTableInfo",
    "SourceTableColumn",
]
