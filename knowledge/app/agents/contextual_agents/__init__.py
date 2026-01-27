"""
Contextual Agents Package
Generic and reusable agents for context breakdown, retrieval, and reasoning.

This package provides a generic architecture for working with different knowledge domains:
- MDL (semantic layer): tables, relations, metrics, features, examples, histories, instructions
- Compliance: frameworks, actors, controls, evidences, requirements, features, keywords, topics, patterns

Key Components:
1. Context Breakdown Agents: Analyze user queries and extract context information
2. Edge Pruning Agents: Select the most relevant edges from discovered edges
3. Context Breakdown Planner: Decides which agent(s) to use based on query type

Usage:
    from app.agents.contextual_agents import ContextBreakdownPlanner
    
    planner = ContextBreakdownPlanner()
    result = await planner.breakdown_question(
        user_question="What tables are needed for SOC2 access control?",
        product_name="Snyk",
        available_frameworks=["SOC2"]
    )
"""
from .base_context_breakdown_agent import BaseContextBreakdownAgent, ContextBreakdown
from .mdl_context_breakdown_agent import MDLContextBreakdownAgent
from .compliance_context_breakdown_agent import ComplianceContextBreakdownAgent
from .context_breakdown_planner import ContextBreakdownPlanner

from .base_edge_pruning_agent import BaseEdgePruningAgent
from .mdl_edge_pruning_agent import MDLEdgePruningAgent
from .compliance_edge_pruning_agent import ComplianceEdgePruningAgent

__all__ = [
    # Context Breakdown
    "BaseContextBreakdownAgent",
    "ContextBreakdown",
    "MDLContextBreakdownAgent",
    "ComplianceContextBreakdownAgent",
    "ContextBreakdownPlanner",
    
    # Edge Pruning
    "BaseEdgePruningAgent",
    "MDLEdgePruningAgent",
    "ComplianceEdgePruningAgent",
]
