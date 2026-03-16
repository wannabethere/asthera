"""
Tool and Retrieval Integration Utilities

This module provides utilities for integrating security intelligence tools
and retrieval services into the compliance automation workflow.
"""
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from app.retrieval.service import RetrievalService
from app.agents.tools import TOOL_REGISTRY, get_tools_by_category
from app.agents.state import EnhancedCompliancePipelineState

if TYPE_CHECKING:
    from langchain.agents import AgentExecutor
    from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


def intelligent_retrieval(
    query: str,
    required_data: List[str],
    framework_id: Optional[str] = None,
    include_mdl: bool = False,
    include_xsoar: bool = False,
    retrieval_service: Optional[RetrievalService] = None
) -> Dict[str, Any]:
    """
    Intelligently route retrieval queries based on required_data hints.
    
    This function analyzes what data is needed and routes to the appropriate
    retrieval method (controls, requirements, risks, scenarios, test_cases).
    
    Args:
        query: The semantic search query
        required_data: List of data types needed (e.g., ["controls", "risks", "scenarios"])
        framework_id: Optional framework filter
        retrieval_service: Optional RetrievalService instance (creates new if None)
    
    Returns:
        Dictionary with retrieved data organized by type
    """
    if retrieval_service is None:
        retrieval_service = RetrievalService()
    
    framework_filter = [framework_id] if framework_id else None
    results = {}
    
    # Determine what to search based on required_data hints
    search_all = False
    search_controls = False
    search_requirements = False
    search_risks = False
    search_scenarios = False
    search_test_cases = False
    
    required_str = " ".join(required_data).lower()
    
    if "control" in required_str or "controls" in required_str:
        search_controls = True
    if "requirement" in required_str or "requirements" in required_str:
        search_requirements = True
    if "risk" in required_str or "risks" in required_str:
        search_risks = True
    if "scenario" in required_str or "scenarios" in required_str:
        search_scenarios = True
    if "test" in required_str or "test_case" in required_str or "test_cases" in required_str:
        search_test_cases = True
    
    # If no specific hints, search all
    if not any([search_controls, search_requirements, search_risks, search_scenarios, search_test_cases]):
        search_all = True
    
    try:
        if search_all:
            # Search everything at once
            context = retrieval_service.search_all(
                query=query,
                limit_per_collection=5,
                framework_filter=framework_filter
            )
            results = {
                "controls": [c.__dict__ for c in context.controls] if hasattr(context, 'controls') else [],
                "requirements": [r.__dict__ for r in context.requirements] if hasattr(context, 'requirements') else [],
                "risks": [r.__dict__ for r in context.risks] if hasattr(context, 'risks') else [],
                "scenarios": [s.__dict__ for s in context.scenarios] if hasattr(context, 'scenarios') else [],
                "test_cases": [tc.__dict__ for tc in context.test_cases] if hasattr(context, 'test_cases') else [],
            }
        else:
            # Search specific types
            if search_controls:
                context = retrieval_service.search_controls(
                    query=query,
                    limit=5,
                    framework_filter=framework_filter
                )
                results["controls"] = [c.__dict__ for c in context.controls] if hasattr(context, 'controls') else []
            
            if search_requirements:
                context = retrieval_service.search_requirements(
                    query=query,
                    limit=5,
                    framework_filter=framework_filter
                )
                results["requirements"] = [r.__dict__ for r in context.requirements] if hasattr(context, 'requirements') else []
            
            if search_risks:
                context = retrieval_service.search_risks(
                    query=query,
                    limit=5,
                    framework_filter=framework_filter
                )
                results["risks"] = [r.__dict__ for r in context.risks] if hasattr(context, 'risks') else []
            
            if search_scenarios:
                context = retrieval_service.search_scenarios(
                    query=query,
                    limit=5,
                    framework_filter=framework_filter
                )
                results["scenarios"] = [s.__dict__ for s in context.scenarios] if hasattr(context, 'scenarios') else []
            
            if search_test_cases:
                context = retrieval_service.search_test_cases(
                    query=query,
                    limit=5,
                    framework_filter=framework_filter
                )
                results["test_cases"] = [tc.__dict__ for tc in context.test_cases] if hasattr(context, 'test_cases') else []
    
    except Exception as e:
        logger.warning(f"Retrieval query failed for '{query}': {e}")
        results["error"] = str(e)
    
    # Add MDL retrieval if requested
    if include_mdl:
        try:
            import asyncio
            from app.retrieval.mdl_service import MDLRetrievalService
            mdl_service = MDLRetrievalService()
            # Run async function in sync context (safe for LangGraph nodes)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we're in an async context
                    # In this case, we'd need to await, but since this is called from sync code,
                    # we'll create a new loop
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            mdl_context = loop.run_until_complete(
                mdl_service.search_all_mdl(query, limit_per_collection=3)
            )
            results["mdl"] = {
                "db_schemas": [s.__dict__ for s in mdl_context.db_schemas],
                "table_descriptions": [t.__dict__ for t in mdl_context.table_descriptions],
                "project_meta": [p.__dict__ for p in mdl_context.project_meta],
                "metrics": [m.__dict__ for m in mdl_context.metrics],
            }
        except Exception as e:
            logger.warning(f"MDL retrieval failed for '{query}': {e}")
            results["mdl"] = {"error": str(e)}
    
    # Add XSOAR retrieval if requested
    if include_xsoar:
        try:
            import asyncio
            from app.retrieval.xsoar_service import XSOARRetrievalService
            xsoar_service = XSOARRetrievalService()
            # Run async function in sync context (safe for LangGraph nodes)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we're in an async context
                    # In this case, we'd need to await, but since this is called from sync code,
                    # we'll create a new loop
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            xsoar_context = loop.run_until_complete(
                xsoar_service.search_all_xsoar(query, limit_per_entity_type=3)
            )
            results["xsoar"] = {
                "playbooks": [p.__dict__ for p in xsoar_context.playbooks],
                "dashboards": [d.__dict__ for d in xsoar_context.dashboards],
                "scripts": [s.__dict__ for s in xsoar_context.scripts],
                "integrations": [i.__dict__ for i in xsoar_context.integrations],
            }
        except Exception as e:
            logger.warning(f"XSOAR retrieval failed for '{query}': {e}")
            results["xsoar"] = {"error": str(e)}
    
    return results


def get_tools_for_agent(
    agent_name: str,
    state: Optional[EnhancedCompliancePipelineState] = None,
    conditional: bool = True
) -> List[Any]:
    """
    Get appropriate tools for a specific agent with conditional loading.
    
    Args:
        agent_name: Name of the agent (e.g., "detection_engineer", "playbook_writer")
        state: Optional state to check for conditional tool loading
        conditional: If True, only load tools when needed based on state content
    
    Returns:
        List of LangChain tools appropriate for this agent
    """
    tool_map = {
        "intent_classifier": [
            # Web search for context on frameworks/requirements
            "tavily_search",
        ],
        "planner": [
            # Web search for context
            "tavily_search",
            # Framework control search for planning
            "framework_control_search",
            # ATT&CK to control mapping for compliance coverage planning
            "attack_to_control_mapper",
        ],
        "detection_engineer": [
            # CVE and vulnerability intelligence
            "cve_intelligence",
            "epss_lookup",
            "cisa_kev_check",
            # ATT&CK framework
            "attack_technique_lookup",
            "cve_to_attack_mapper",
            "attack_to_control_mapper",
            # Exploit intelligence
            "exploit_db_search",
            "metasploit_module_search",
            "nuclei_template_search",
            # Threat intelligence
            "otx_pulse_search",
            "virustotal_lookup",
            # Analysis
            "attack_path_builder",
            "risk_calculator",
        ],
        "playbook_writer": [
            # Threat intelligence for context
            "otx_pulse_search",
            "virustotal_lookup",
            # ATT&CK for attack context
            "attack_technique_lookup",
            "attack_to_control_mapper",
            "attack_path_builder",
            # Risk analysis
            "risk_calculator",
            # CVE intelligence for vulnerability context
            "cve_intelligence",
        ],
        "test_generator": [
            # Compliance tools
            "framework_control_search",
            "cis_benchmark_lookup",
            # Gap analysis
            "gap_analysis",
            # ATT&CK to control mapping for control verification tests
            "attack_to_control_mapper",
        ],
        "framework_analyzer": [
            # Compliance tools
            "framework_control_search",
            "cis_benchmark_lookup",
            "gap_analysis",
            # Cross-framework mapping
            "attack_to_control_mapper",
        ],
        "artifact_assembler": [
            # Web search for best practices
            "tavily_search",
            # ATT&CK to control mapping for compliance artifact context
            "attack_to_control_mapper",
        ],
        "dashboard_generator": [
            # Web search for dashboard best practices
            "tavily_search",
            # Framework control search for context
            "framework_control_search",
            # ATT&CK to control mapping for risk dashboard context
            "attack_to_control_mapper",
        ],
        "gap_analysis": [
            # Compliance tools
            "framework_control_search",
            "cis_benchmark_lookup",
            "gap_analysis",
            # ATT&CK for risk context
            "attack_to_control_mapper",
            "attack_technique_lookup",
        ],
        "cross_framework_mapper": [
            # Compliance tools
            "framework_control_search",
            "cis_benchmark_lookup",
            # Cross-framework mapping
            "attack_to_control_mapper",
        ],
    }
    
    tool_names = tool_map.get(agent_name, [])
    
    # Conditional tool loading based on state content
    if conditional and state:
        tool_names = _filter_tools_conditionally(tool_names, agent_name, state)
    
    tools = []
    
    for tool_name in tool_names:
        if tool_name in TOOL_REGISTRY:
            try:
                tool = TOOL_REGISTRY[tool_name]()
                tools.append(tool)
            except Exception as e:
                logger.warning(f"Failed to load tool {tool_name} for {agent_name}: {e}")
    
    return tools


def _filter_tools_conditionally(
    tool_names: List[str],
    agent_name: str,
    state: EnhancedCompliancePipelineState
) -> List[str]:
    """
    Filter tools based on state content (conditional loading).
    
    Only load tools when their data is actually present or needed.
    """
    filtered = []
    
    # Get state content for analysis
    scenarios = state.get("scenarios", [])
    controls = state.get("controls", [])
    risks = state.get("risks", [])
    user_query = state.get("user_query", "").lower()
    
    for tool_name in tool_names:
        should_load = True
        
        # CVE-related tools: only if scenarios/risks mention CVEs
        if tool_name in ["cve_intelligence", "cve_to_attack_mapper", "epss_lookup", "cisa_kev_check"]:
            has_cve_mentions = (
                "cve" in user_query or
                any("cve" in str(s).lower() for s in scenarios) or
                any("cve" in str(r).lower() for r in risks)
            )
            should_load = has_cve_mentions
        
        # Exploit tools: only if scenarios mention exploits or vulnerabilities
        elif tool_name in ["exploit_db_search", "metasploit_module_search", "nuclei_template_search"]:
            has_exploit_mentions = (
                any("exploit" in str(s).lower() or "vulnerability" in str(s).lower() for s in scenarios) or
                "exploit" in user_query or
                "vulnerability" in user_query
            )
            should_load = has_exploit_mentions
        
        # ATT&CK tools: always useful for detection/playbooks
        elif tool_name in ["attack_technique_lookup", "attack_to_control_mapper", "attack_path_builder"]:
            should_load = True  # Always useful
        
        # Threat intel: only if scenarios mention IoCs or threats
        elif tool_name in ["otx_pulse_search", "virustotal_lookup"]:
            has_threat_mentions = (
                any("ioc" in str(s).lower() or "threat" in str(s).lower() or "malware" in str(s).lower() for s in scenarios) or
                "threat" in user_query or
                "malware" in user_query
            )
            should_load = has_threat_mentions
        
        # Compliance tools: always useful
        elif tool_name in ["framework_control_search", "cis_benchmark_lookup", "gap_analysis"]:
            should_load = True
        
        # Web search: only for planning/assembly
        elif tool_name == "tavily_search":
            should_load = agent_name in ["planner", "artifact_assembler", "intent_classifier"]
        
        if should_load:
            filtered.append(tool_name)
    
    return filtered


def format_retrieved_context_for_prompt(
    context: Dict[str, Any],
    include_mdl: bool = False,
    include_xsoar: bool = False
) -> str:
    """
    Format retrieved context data for inclusion in LLM prompts.
    
    Args:
        context: Dictionary with retrieved data (controls, risks, scenarios, etc.)
        include_mdl: Whether to format MDL data if present
        include_xsoar: Whether to format XSOAR data if present
    
    Returns:
        Formatted string suitable for prompt inclusion
    """
    parts = []
    
    if context.get("controls"):
        parts.append("### CONTROLS ###")
        for ctrl in context["controls"][:5]:  # Limit to top 5
            parts.append(f"- {ctrl.get('name', 'Unknown')} ({ctrl.get('id', 'N/A')})")
            if ctrl.get('description'):
                parts.append(f"  {ctrl['description'][:200]}...")
    
    if context.get("requirements"):
        parts.append("\n### REQUIREMENTS ###")
        for req in context["requirements"][:5]:
            parts.append(f"- {req.get('name', 'Unknown')} ({req.get('requirement_code', 'N/A')})")
            if req.get('description'):
                parts.append(f"  {req['description'][:200]}...")
    
    if context.get("risks"):
        parts.append("\n### RISKS ###")
        for risk in context["risks"][:5]:
            parts.append(f"- {risk.get('name', 'Unknown')} (Likelihood: {risk.get('likelihood', 'N/A')}, Impact: {risk.get('impact', 'N/A')})")
    
    if context.get("scenarios"):
        parts.append("\n### SCENARIOS ###")
        for scenario in context["scenarios"][:5]:
            parts.append(f"- {scenario.get('name', 'Unknown')} (Severity: {scenario.get('severity', 'N/A')})")
    
    if context.get("test_cases"):
        parts.append("\n### TEST CASES ###")
        for tc in context["test_cases"][:5]:
            parts.append(f"- {tc.get('name', 'Unknown')} ({tc.get('id', 'N/A')})")
    
    # Format MDL data if requested and present
    if include_mdl and context.get("mdl"):
        mdl = context["mdl"]
        if not isinstance(mdl, dict) or "error" in mdl:
            parts.append("\n### MDL DATA ###")
            parts.append("(MDL retrieval unavailable)")
        else:
            if mdl.get("db_schemas"):
                parts.append("\n### DATABASE SCHEMAS (MDL) ###")
                for schema in mdl["db_schemas"][:3]:
                    parts.append(f"- Table: {schema.get('table_name', 'Unknown')}")
                    if schema.get('schema_ddl'):
                        parts.append(f"  DDL: {schema['schema_ddl'][:150]}...")
            
            if mdl.get("table_descriptions"):
                parts.append("\n### TABLE DESCRIPTIONS (MDL) ###")
                for desc in mdl["table_descriptions"][:3]:
                    parts.append(f"- {desc.get('table_name', 'Unknown')}: {desc.get('description', '')[:150]}...")
            
            if mdl.get("metrics"):
                parts.append("\n### METRICS REGISTRY (MDL) ###")
                for metric in mdl["metrics"][:3]:
                    parts.append(f"- {metric.get('metric_name', 'Unknown')}: {metric.get('metric_definition', '')[:150]}...")
    
    # Format XSOAR data if requested and present
    if include_xsoar and context.get("xsoar"):
        xsoar = context["xsoar"]
        if not isinstance(xsoar, dict) or "error" in xsoar:
            parts.append("\n### XSOAR DATA ###")
            parts.append("(XSOAR retrieval unavailable)")
        else:
            if xsoar.get("playbooks"):
                parts.append("\n### XSOAR PLAYBOOKS ###")
                for pb in xsoar["playbooks"][:3]:
                    parts.append(f"- {pb.get('playbook_name', 'Unknown')} ({pb.get('playbook_id', 'N/A')})")
            
            if xsoar.get("dashboards"):
                parts.append("\n### XSOAR DASHBOARDS ###")
                for dash in xsoar["dashboards"][:3]:
                    parts.append(f"- {dash.get('dashboard_name', 'Unknown')} ({dash.get('dashboard_id', 'N/A')})")
            
            if xsoar.get("scripts"):
                parts.append("\n### XSOAR SCRIPTS ###")
                for script in xsoar["scripts"][:3]:
                    parts.append(f"- {script.get('script_name', 'Unknown')} ({script.get('script_id', 'N/A')})")
    
    if not parts:
        return "No relevant context found."
    
    return "\n".join(parts)


def create_tool_calling_agent(
    llm: Any,
    tools: List[Any],
    prompt: Optional["ChatPromptTemplate"] = None,
    use_react_agent: bool = True,
    executor_kwargs: Optional[Dict[str, Any]] = None
) -> Optional["AgentExecutor"]:
    """
    Create a tool-calling agent with AgentExecutor.
    
    This function creates an agent that can actively use tools during execution.
    
    Args:
        llm: Language model instance
        tools: List of tools for the agent
        prompt: Optional custom prompt (only used with create_tool_calling_agent)
        use_react_agent: If True, prefer create_react_agent; if False, use create_tool_calling_agent
        executor_kwargs: Additional kwargs to pass to AgentExecutor
    
    Returns:
        AgentExecutor instance, or None if agent creation fails
    """
    if not tools:
        logger.warning("No tools available for agent initialization")
        return None
    
    executor_kwargs = executor_kwargs or {}
    default_kwargs = {
        "verbose": False,  # Set to False by default to reduce noise
        "handle_parsing_errors": True,
        "max_iterations": 5,
        "early_stopping_method": "generate"
    }
    default_kwargs.update(executor_kwargs)
    
    # Try multiple import paths for LangChain agent components
    AgentExecutor = None
    create_react_agent = None
    create_tool_calling_agent_func = None
    hub = None
    
    # Try langchain_classic first (newer LangChain versions)
    try:
        from langchain_classic.agents import AgentExecutor, create_react_agent, create_tool_calling_agent as create_tool_calling_agent_func
        from langchain_classic import hub
        logger.debug("Using langchain_classic for agent components")
    except ImportError:
        # Try standard langchain.agents
        try:
            from langchain.agents import AgentExecutor, create_react_agent, create_tool_calling_agent as create_tool_calling_agent_func
            from langchain import hub
            logger.debug("Using langchain.agents for agent components")
        except ImportError:
            # Try langchain_core.agents
            try:
                from langchain_core.agents import AgentExecutor
                from langchain.agents import create_react_agent, create_tool_calling_agent as create_tool_calling_agent_func
                from langchain import hub
                logger.debug("Using langchain_core.agents for AgentExecutor")
            except ImportError:
                logger.error("Could not import LangChain agent components. Tool-calling agents will not work.")
                return None
    
    if not all([AgentExecutor, create_react_agent, create_tool_calling_agent_func, hub]):
        logger.error("Missing required LangChain agent components")
        return None
    
    # Prefer create_react_agent (modern pattern)
    if use_react_agent:
        try:
            react_prompt = hub.pull("hwchase17/react")
            
            # Create a wrapper LLM that strips stop sequences from invocations
            # Some models (like newer OpenAI models) don't support the 'stop' parameter
            class StopSequenceStripper:
                """Wrapper to remove stop sequences from LLM calls."""
                def __init__(self, llm):
                    self.llm = llm
                    # Preserve all attributes from original LLM
                    for attr in dir(llm):
                        if not attr.startswith('_') and attr not in ['invoke', 'stream', 'batch', 'abatch']:
                            try:
                                setattr(self, attr, getattr(llm, attr))
                            except:
                                pass
                
                def invoke(self, input, config=None, **kwargs):
                    # Remove stop from kwargs and config if present
                    kwargs.pop('stop', None)
                    if config:
                        if hasattr(config, 'configurable') and config.configurable:
                            config.configurable.pop('stop', None)
                        if hasattr(config, 'run_name'):
                            # Create a new config without stop
                            from langchain_core.runnables.config import RunnableConfig
                            new_config = RunnableConfig(
                                configurable=config.configurable.copy() if hasattr(config, 'configurable') else {},
                                tags=config.tags if hasattr(config, 'tags') else None,
                                metadata=config.metadata if hasattr(config, 'metadata') else None,
                                run_name=config.run_name if hasattr(config, 'run_name') else None,
                            )
                            config = new_config
                    return self.llm.invoke(input, config=config, **kwargs)
                
                def stream(self, input, config=None, **kwargs):
                    kwargs.pop('stop', None)
                    if config and hasattr(config, 'configurable') and config.configurable:
                        config.configurable.pop('stop', None)
                    return self.llm.stream(input, config=config, **kwargs)
            
            wrapped_llm = StopSequenceStripper(llm)
            
            agent = create_react_agent(wrapped_llm, tools, react_prompt)
            logger.info("Created tool-calling agent using create_react_agent (with stop sequence stripping)")
            return AgentExecutor(agent=agent, tools=tools, **default_kwargs)
        except Exception as e:
            logger.warning(f"Failed to create react agent: {e}. Trying tool calling agent.")
    
    # Fallback to create_tool_calling_agent
    if prompt:
        try:
            agent = create_tool_calling_agent_func(llm=llm, tools=tools, prompt=prompt)
            logger.info("Created tool-calling agent using create_tool_calling_agent")
            return AgentExecutor(agent=agent, tools=tools, **default_kwargs)
        except Exception as e:
            logger.error(f"Failed to create tool calling agent: {e}")
            return None
    else:
        logger.error("Cannot create agent: no prompt provided and react_agent failed")
        return None


def should_use_tool_calling_agent(
    agent_name: str,
    state: Optional[EnhancedCompliancePipelineState] = None
) -> bool:
    """
    Determine if an agent should use tool-calling (vs simple LLM chain).
    
    Args:
        agent_name: Name of the agent
        state: Optional state to check
    
    Returns:
        True if tool-calling agent should be used
    """
    # Agents that should always use tool-calling if tools are available
    tool_calling_agents = [
        "detection_engineer",
        "playbook_writer",
        "framework_analyzer",
        "planner",
    ]
    
    if agent_name in tool_calling_agents:
        # Check if tools are available
        tools = get_tools_for_agent(agent_name, state=state, conditional=True)
        return len(tools) > 0
    
    # Other agents can use tool-calling if tools are available
    tools = get_tools_for_agent(agent_name, state=state, conditional=True)
    return len(tools) > 0
