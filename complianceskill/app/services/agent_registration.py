"""
Agent Registration

Registers all available agents with the registry at startup.
This module wires up the actual agent implementations to the adapter system.
"""

import logging
from typing import Optional

from app.adapters.registry import AgentRegistry, AgentMeta, get_agent_registry
from app.adapters.langgraph_adapter import LangGraphAdapter

logger = logging.getLogger(__name__)


def register_all_agents(registry: Optional[AgentRegistry] = None):
    """
    Register all available agents with the registry.
    
    This should be called at application startup.
    
    Args:
        registry: Optional registry instance (uses global if None)
    """
    if registry is None:
        registry = get_agent_registry()
    
    logger.info("Registering agents with adapter system...")
    
    # Register CSOD Planner Workflow
    try:
        from app.agents.csod.csod_planner_workflow import get_csod_planner_app
        
        csod_planner_app = get_csod_planner_app()
        csod_planner_meta = AgentMeta(
            agent_id="csod-planner",
            display_name="CSOD Planner",
            framework="langgraph",
            capabilities=["streaming", "multi_step"],
            context_window_tokens=8000,
            system_ctx_tokens=1500,
            session_ctx_tokens=3000,
            turn_ctx_tokens=2000,
            response_reserve_tokens=1500,
            routing_tags=["csod", "planner", "cornerstone"],
        )
        csod_planner_adapter = LangGraphAdapter(csod_planner_app)
        registry.register(csod_planner_meta, csod_planner_adapter)
        logger.info("✓ Registered csod-planner")
    except Exception as e:
        logger.error(f"Failed to register csod-planner: {e}", exc_info=True)
    
    # Register CSOD Workflow
    try:
        from app.agents.csod.csod_workflow import get_csod_app
        
        csod_app = get_csod_app()
        csod_meta = AgentMeta(
            agent_id="csod-workflow",
            display_name="CSOD Metrics & KPIs Workflow",
            framework="langgraph",
            capabilities=["streaming", "tool_use", "multi_step"],
            context_window_tokens=8000,
            system_ctx_tokens=1500,
            session_ctx_tokens=3000,
            turn_ctx_tokens=2000,
            response_reserve_tokens=1500,
            routing_tags=["csod", "metrics", "kpis", "cornerstone"],
        )
        csod_adapter = LangGraphAdapter(csod_app)
        registry.register(csod_meta, csod_adapter)
        logger.info("✓ Registered csod-workflow")
    except Exception as e:
        logger.error(f"Failed to register csod-workflow: {e}", exc_info=True)
    
    # Register CSOD Metric Advisor Workflow
    try:
        from app.agents.csod.csod_metric_advisor_workflow import get_csod_metric_advisor_app
        
        csod_advisor_app = get_csod_metric_advisor_app()
        csod_advisor_meta = AgentMeta(
            agent_id="csod-metric-advisor",
            display_name="CSOD Metric Advisor",
            framework="langgraph",
            capabilities=["streaming", "tool_use", "multi_step", "causal_reasoning"],
            context_window_tokens=8000,
            system_ctx_tokens=1500,
            session_ctx_tokens=3000,
            turn_ctx_tokens=2000,
            response_reserve_tokens=1500,
            routing_tags=["csod", "metrics", "kpis", "advisor", "causal", "cornerstone"],
            use_conversation_phase0=True,  # Enable conversation Phase 0
            conversation_vertical="lms",  # Use LMS conversation config
        )
        csod_advisor_adapter = LangGraphAdapter(csod_advisor_app)
        registry.register(csod_advisor_meta, csod_advisor_adapter)
        logger.info("✓ Registered csod-metric-advisor (with conversation Phase 0)")
    except Exception as e:
        logger.error(f"Failed to register csod-metric-advisor: {e}", exc_info=True)
    
    # Register DT Workflow
    try:
        from app.agents.mdlworkflows.dt_workflow import get_detection_triage_app
        
        dt_app = get_detection_triage_app()
        dt_meta = AgentMeta(
            agent_id="dt-workflow",
            display_name="Detection & Triage Workflow",
            framework="langgraph",
            capabilities=["streaming", "tool_use", "multi_step"],
            context_window_tokens=8000,
            system_ctx_tokens=1500,
            session_ctx_tokens=3000,
            turn_ctx_tokens=2000,
            response_reserve_tokens=1500,
            routing_tags=["detection", "triage", "siem", "playbook"],
        )
        dt_adapter = LangGraphAdapter(dt_app)
        registry.register(dt_meta, dt_adapter)
        logger.info("✓ Registered dt-workflow")
    except Exception as e:
        logger.error(f"Failed to register dt-workflow: {e}", exc_info=True)
    
    # Register Compliance Workflow
    try:
        from app.agents.detectiontriageworkflows.workflow import get_compliance_app
        
        compliance_app = get_compliance_app()
        compliance_meta = AgentMeta(
            agent_id="compliance-workflow",
            display_name="Compliance Automation Workflow",
            framework="langgraph",
            capabilities=["streaming", "tool_use", "multi_step"],
            context_window_tokens=8000,
            system_ctx_tokens=1500,
            session_ctx_tokens=3000,
            turn_ctx_tokens=2000,
            response_reserve_tokens=1500,
            routing_tags=["compliance", "framework", "gap_analysis"],
        )
        compliance_adapter = LangGraphAdapter(compliance_app)
        registry.register(compliance_meta, compliance_adapter)
        logger.info("✓ Registered compliance-workflow")
    except Exception as e:
        logger.error(f"Failed to register compliance-workflow: {e}", exc_info=True)
    
    # Register Dashboard Agent
    try:
        from app.agents.dashboard_agent.llm_agent import build_llm_layout_advisor_graph
        
        dashboard_app = build_llm_layout_advisor_graph()
        dashboard_meta = AgentMeta(
            agent_id="dashboard-agent",
            display_name="Dashboard Layout Advisor",
            framework="langgraph",
            capabilities=["streaming", "tool_use", "conversational"],
            context_window_tokens=8000,
            system_ctx_tokens=1500,
            session_ctx_tokens=3000,
            turn_ctx_tokens=2000,
            response_reserve_tokens=1500,
            routing_tags=["dashboard", "layout", "template"],
        )
        dashboard_adapter = LangGraphAdapter(dashboard_app)
        registry.register(dashboard_meta, dashboard_adapter)
        logger.info("✓ Registered dashboard-agent")
    except Exception as e:
        logger.error(f"Failed to register dashboard-agent: {e}", exc_info=True)
    
    logger.info(f"Agent registration complete. Registered {len(registry.list_agents())} agents.")


def register_agent_on_startup():
    """Convenience function to call from application startup"""
    register_all_agents()
