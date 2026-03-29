"""
Agent Registration

Registers all available agents with the registry at startup.
This module wires LangGraph apps to the HTTP gateway (AgentRegistry).

CSOD execution graphs registered here:
- ``csod-workflow`` → ``app.agents.csod.workflows.csod_main_graph.get_csod_app``
- ``csod-metric-advisor`` → same app as ``csod-workflow`` (deprecated id for clients)

CSOD **internal** planner routing (intent → execution_plan → executor_id) uses
`app.agents.csod.executor_registry` + `executor_registry_planned` inside
`csod_planner_node`, not this file. Describe payloads for csod-* agents attach
the same executor catalog via `agent_describe_context.build_agent_describe_context`.
"""

import logging
from typing import Any, Dict, Optional

from app.adapters.registry import AgentRegistry, AgentMeta, get_agent_registry
from app.adapters.base_langgraph_adapter import BaseLangGraphAdapter
from app.adapters.csod_langgraph_adapter import CSODLangGraphAdapter

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

    # CSOD Planner (phase-0 conversation + router): gateway entry; chains to csod-workflow
    # Internal intent → execution_plan still uses executor_registry + executor_registry_planned in csod_planner_node.
    try:
        from app.conversation.planner_workflow import create_conversation_planner_app
        from app.conversation.verticals.lms_config import LMS_CONVERSATION_CONFIG

        csod_planner_app = create_conversation_planner_app(LMS_CONVERSATION_CONFIG)
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
            planner_description="Routes CSOD/compliance queries; conversation phase then chains to csod-workflow.",
        )
        csod_planner_adapter = CSODLangGraphAdapter(csod_planner_app)
        registry.register(csod_planner_meta, csod_planner_adapter)
        logger.info("✓ Registered csod-planner")
    except Exception as e:
        logger.error(f"Failed to register csod-planner: {e}", exc_info=True)

    # Register CSOD Workflow (graph: workflows/csod_main_graph.py)
    # Uses get_csod_interactive_app() so LangGraph pauses at csod_metric_selection and
    # csod_goal_intent via interrupt_after, allowing the conversation frontend to collect
    # user selections before the workflow continues to output generation.
    try:
        from app.agents.csod.workflows.csod_main_graph import get_csod_interactive_app

        csod_app = get_csod_interactive_app()
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
            planner_description="Runs CSOD metrics and KPIs workflow; recommends metrics and produces dashboard inputs.",
        )
        csod_adapter = CSODLangGraphAdapter(csod_app)
        registry.register(csod_meta, csod_adapter)
        logger.info("✓ Registered csod-workflow")
    except Exception as e:
        logger.error(f"Failed to register csod-workflow: {e}", exc_info=True)
    
    # Deprecated agent id: same LangGraph app as csod-workflow (standalone metric-advisor graph removed from routing)
    try:
        from app.agents.csod.workflows.csod_main_graph import get_csod_interactive_app

        csod_main_for_alias = get_csod_interactive_app()
        csod_advisor_meta = AgentMeta(
            agent_id="csod-metric-advisor",
            display_name="CSOD Metric Advisor (alias)",
            framework="langgraph",
            capabilities=["streaming", "tool_use", "multi_step", "causal_reasoning"],
            context_window_tokens=8000,
            system_ctx_tokens=1500,
            session_ctx_tokens=3000,
            turn_ctx_tokens=2000,
            response_reserve_tokens=1500,
            routing_tags=["csod", "metrics", "kpis", "advisor", "causal", "cornerstone"],
            use_conversation_phase0=True,
            conversation_vertical="lms",
            planner_description="Deprecated; same graph as csod-workflow. Prefer csod-workflow.",
        )
        csod_advisor_adapter = CSODLangGraphAdapter(csod_main_for_alias)
        registry.register(csod_advisor_meta, csod_advisor_adapter)
        logger.info("✓ Registered csod-metric-advisor as alias of csod-workflow")
    except Exception as e:
        logger.error(f"Failed to register csod-metric-advisor alias: {e}", exc_info=True)
    
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
            planner_description="Detection and triage workflow; SIEM rules, playbooks, and triage pipelines.",
        )
        dt_adapter = BaseLangGraphAdapter(dt_app)
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
            planner_description="Compliance automation workflow; gap analysis and framework mapping.",
        )
        compliance_adapter = BaseLangGraphAdapter(compliance_app)
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
            planner_description="Dashboard layout and template advisor for compliance and metrics.",
        )
        dashboard_adapter = BaseLangGraphAdapter(dashboard_app)
        registry.register(dashboard_meta, dashboard_adapter)
        logger.info("✓ Registered dashboard-agent")
    except Exception as e:
        logger.error(f"Failed to register dashboard-agent: {e}", exc_info=True)

    # Register CSOD Preview Generator
    # Invoked by the frontend after Phase 1 completes to generate metric/KPI/table
    # preview cards with dummy data, Vega-Lite specs, and LLM-generated summaries.
    try:
        from app.agents.csod.workflows.csod_preview_graph import get_csod_preview_app

        preview_app = get_csod_preview_app()
        preview_meta = AgentMeta(
            agent_id="csod-preview-generator",
            display_name="CSOD Preview Generator",
            framework="langgraph",
            capabilities=["streaming", "multi_step"],
            context_window_tokens=4000,
            system_ctx_tokens=800,
            session_ctx_tokens=1500,
            turn_ctx_tokens=1000,
            response_reserve_tokens=1000,
            routing_tags=["csod", "preview", "dashboard"],
            planner_description=(
                "Generates metric/KPI preview cards from Phase 1 output. "
                "Called after metric selection is confirmed."
            ),
            use_conversation_phase0=False,
        )
        preview_adapter = BaseLangGraphAdapter(preview_app)
        registry.register(preview_meta, preview_adapter)
        logger.info("✓ Registered csod-preview-generator")
    except Exception as e:
        logger.error(f"Failed to register csod-preview-generator: {e}", exc_info=True)

    logger.info(f"Agent registration complete. Registered {len(registry.list_agents())} agents.")


def register_agent_on_startup():
    """Convenience function to call from application startup"""
    register_all_agents()


def build_csod_chain_invoke_payload_after_planner(
    planner_output: Dict[str, Any],
    *,
    thread_id: str,
    original_run_id: Optional[str] = None,
    original_step_id: str = "step_1",
) -> Dict[str, Any]:
    """
    Same invoke payload AgentInvocationService uses when chaining from csod-planner.
    Tests/scripts should merge this into POST /v1/agents/invoke (plus agent_id, claims).
    """
    from app.services.agent_invocation_service import build_planner_chain_invoke_payload

    return build_planner_chain_invoke_payload(
        planner_output,
        thread_id=thread_id,
        original_run_id=original_run_id,
        original_step_id=original_step_id,
    )
