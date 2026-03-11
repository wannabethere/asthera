"""
CSOD Workflow — Tool Integration Utilities

Extends tool_integration.py with CSOD-specific helpers:
- csod_get_tools_for_agent()     tool maps for CSOD agents
- run_async()                    safe async-in-sync runner
- csod_retrieve_mdl_schemas()    MDL schema lookup
- csod_retrieve_gold_tables()    project meta lookup for GoldStandardTables
- csod_format_scored_context()   format scored_context for LLM prompt injection
"""
import asyncio
import concurrent.futures
import json
import logging
from typing import Any, Dict, List, Optional, Set

from app.agents.state import EnhancedCompliancePipelineState
from app.agents.shared.tool_integration import (
    intelligent_retrieval,
    get_tools_for_agent,
    format_retrieved_context_for_prompt,
    create_tool_calling_agent,
    should_use_tool_calling_agent,
)
from app.agents.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


# ============================================================================
# Async helper — matches pattern used throughout nodes.py
# ============================================================================

def run_async(coro):
    """
    Run an async coroutine safely from synchronous LangGraph node code.
    
    Tries in order:
    1. nest_asyncio.apply() if a loop is already running
    2. ThreadPoolExecutor if nest_asyncio unavailable
    3. asyncio.run() as final fallback
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(coro)
            except ImportError:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ============================================================================
# CSOD-specific tool maps
# ============================================================================

# Tool lists for each CSOD agent. Keys match agent names used in csod_nodes.py.
# Placeholders for Cornerstone/Workday-specific tools (to be implemented)
CSOD_TOOL_MAP: Dict[str, List[str]] = {
    "csod_intent_classifier": [
        "tavily_search",  # General web search
    ],
    "csod_planner": [
        "tavily_search",
        # Placeholder: "cornerstone_documentation_search",
        # Placeholder: "workday_documentation_search",
    ],
    "csod_metrics_recommender": [
        # Placeholder: "cornerstone_metrics_lookup",
        # Placeholder: "workday_metrics_lookup",
        # Placeholder: "cornerstone_playbook_search",
        # Placeholder: "workday_playbook_search",
    ],
    "csod_dashboard_generator": [
        # Placeholder: "cornerstone_dashboard_patterns",
        # Placeholder: "workday_dashboard_patterns",
    ],
    "csod_compliance_test_generator": [
        # Placeholder: "cornerstone_test_runner",
        # Placeholder: "workday_test_runner",
        # Placeholder: "sql_query_executor",
    ],
    "csod_scheduler": [
        # Placeholder: "schedule_manager",
    ],
}


def csod_get_tools_for_agent(
    agent_name: str,
    state: Optional[EnhancedCompliancePipelineState] = None,
    conditional: bool = True,
) -> List[Any]:
    """
    Return instantiated LangChain tools for the given CSOD agent.
    
    Falls back to the base get_tools_for_agent() if the agent is not in
    CSOD_TOOL_MAP.
    
    Args:
        agent_name: One of the CSOD agent names (e.g., "csod_metrics_recommender")
        state:      Pipeline state used for conditional filtering
        conditional: When True, apply conditional loading logic
    Returns:
        List of instantiated tool objects
    """
    tool_names = CSOD_TOOL_MAP.get(agent_name)
    
    # Fall back to base map if not a CSOD-specific agent
    if tool_names is None:
        return get_tools_for_agent(agent_name, state=state, conditional=conditional)
    
    # Filter out placeholder tools (not yet implemented)
    available_tool_names = [name for name in tool_names if name in TOOL_REGISTRY]
    
    # Conditional filtering (can be extended later)
    if conditional and state and available_tool_names:
        available_tool_names = _csod_filter_tools_conditionally(available_tool_names, agent_name, state)
    
    tools = []
    for name in available_tool_names:
        if name in TOOL_REGISTRY:
            try:
                tools.append(TOOL_REGISTRY[name]())
            except Exception as e:
                logger.warning(f"csod_get_tools_for_agent: failed to load tool {name}: {e}")
    
    return tools


def _csod_filter_tools_conditionally(
    tool_names: List[str],
    agent_name: str,
    state: EnhancedCompliancePipelineState,
) -> List[str]:
    """Apply conditional logic for CSOD tools."""
    user_query = state.get("user_query", "").lower()
    filtered = []
    
    for name in tool_names:
        should_load = True
        
        # Add conditional logic here as tools are implemented
        # For now, all available tools are loaded
        if should_load:
            filtered.append(name)
    
    return filtered


# ============================================================================
# MDL schema lookup (reuses DT pattern)
# ============================================================================

def csod_retrieve_mdl_schemas(
    schema_names: List[str],
    fallback_query: Optional[str] = None,
    limit: int = 10,
    selected_data_sources: Optional[List[str]] = None,
    silver_gold_tables_only: bool = False,
    planner_output: Optional[Dict[str, Any]] = None,
    original_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve MDL schemas for CSOD workflow.
    
    Reuses the DT pattern but uses CSOD-specific collections (csod_db_schema, csod_table_descriptions).
    """
    # Import DT helper and reuse with CSOD workflow type
    from app.agents.mdlworkflows.dt_tool_integration import dt_retrieve_mdl_schemas
    
    return dt_retrieve_mdl_schemas(
        schema_names=schema_names,
        fallback_query=fallback_query,
        limit=limit,
        selected_data_sources=selected_data_sources,
        silver_gold_tables_only=silver_gold_tables_only,
        planner_output=planner_output,
        original_query=original_query,
        workflow_type="csod",  # Use CSOD collections
    )


# ============================================================================
# GoldStandardTable lookup (reuses DT pattern)
# ============================================================================

def csod_retrieve_gold_standard_tables(
    project_id: str,
    categories: Optional[List[str]] = None,
    intent: Optional[str] = None,
    data_sources: Optional[List[str]] = None,
    user_query: Optional[str] = None,
    focus_areas: Optional[List[str]] = None,
    use_semantic_search: bool = False,
) -> List[Dict[str, Any]]:
    """
    Retrieve GoldStandardTables for CSOD workflow.
    
    Uses CSOD project metadata to recommend categories based on intent and data sources,
    then queries across multiple project_ids matching those categories.
    
    Args:
        project_id: Primary project ID (optional if categories are provided)
        categories: Optional explicit categories (if not provided, will be recommended)
        intent: CSOD intent (used to recommend categories)
        data_sources: List of data source IDs (used to recommend categories and filter projects)
        user_query: Optional user query for semantic search
        focus_areas: Optional focus areas for category recommendation
        use_semantic_search: If True, use vector store for semantic category search
    
    Returns:
        List of gold standard table records
    """
    from app.agents.mdlworkflows.dt_tool_integration import dt_retrieve_gold_standard_tables
    from app.agents.csod.csod_project_metadata import get_csod_metadata_loader
    
    # If categories not provided, recommend them using metadata
    if not categories:
        metadata_loader = get_csod_metadata_loader()
        recommended_categories = metadata_loader.recommend_categories(
            intent=intent,
            data_sources=data_sources,
            user_query=user_query,
            focus_areas=focus_areas,
            use_semantic_search=use_semantic_search,
            limit=10,
        )
        if recommended_categories:
            categories = recommended_categories
            logger.info(f"Recommended categories from metadata: {categories}")
    
    # If project_id not provided but we have categories, find matching projects
    project_ids_to_query = [project_id] if project_id else []
    
    if categories and data_sources:
        metadata_loader = get_csod_metadata_loader()
        matching_project_ids = metadata_loader.get_project_ids_for_categories(
            categories=categories,
            data_sources=data_sources,
        )
        if matching_project_ids:
            project_ids_to_query.extend(matching_project_ids)
            # Deduplicate
            project_ids_to_query = list(dict.fromkeys(project_ids_to_query))
            logger.info(f"Found {len(project_ids_to_query)} matching projects for categories: {categories}")
    
    # If still no project_ids, use the provided one or return empty
    if not project_ids_to_query:
        if project_id:
            project_ids_to_query = [project_id]
        else:
            logger.warning("No project_id or matching projects found - cannot retrieve gold standard tables")
            return []
    
    # Query gold standard tables for each project_id
    all_gold_tables: List[Dict[str, Any]] = []
    seen_table_names: Set[str] = set()
    
    for pid in project_ids_to_query:
        try:
            project_tables = dt_retrieve_gold_standard_tables(
                project_id=pid,
                categories=categories,
                workflow_type="csod",
            )
            
            # Deduplicate by table_name across projects
            for table in project_tables:
                table_name = table.get("table_name", "")
                if table_name and table_name not in seen_table_names:
                    seen_table_names.add(table_name)
                    all_gold_tables.append(table)
            
            logger.info(f"Retrieved {len(project_tables)} gold tables from project '{pid}'")
        except Exception as e:
            logger.warning(f"Failed to retrieve gold tables from project '{pid}': {e}")
            continue
    
    logger.info(f"Total unique gold standard tables retrieved: {len(all_gold_tables)}")
    return all_gold_tables


# ============================================================================
# Prompt context formatter for scored_context
# ============================================================================

def csod_format_scored_context_for_prompt(
    scored_context: Dict[str, Any],
    include_schemas: bool = True,
    include_metrics: bool = True,
    include_kpis: bool = True,
    max_metrics: int = 10,
    max_kpis: int = 10,
    max_schemas: int = 5,
    silver_gold_tables_only: bool = False,
) -> str:
    """
    Format the scored_context dict for CSOD workflow into a compact,
    LLM-friendly prompt string.
    """
    parts = []
    
    if include_metrics:
        metrics = scored_context.get("scored_metrics", []) or scored_context.get("metrics", [])
        if metrics:
            parts.append("### SCORED METRICS ###")
            for m in metrics[:max_metrics]:
                score = m.get("composite_score", 0)
                parts.append(
                    f"- [{m.get('metric_id', 'N/A')}] {m.get('name', 'Unknown')} "
                    f"(category={m.get('category', '?')}, score={score:.2f})"
                )
                if m.get("natural_language_question"):
                    parts.append(f"  Q: {m['natural_language_question'][:180]}")
                if m.get("source_schemas"):
                    parts.append(f"  schemas: {m['source_schemas']}")
    
    if include_kpis:
        kpis = scored_context.get("scored_kpis", []) or scored_context.get("kpis", [])
        if kpis:
            parts.append("\n### SCORED KPIs ###")
            for k in kpis[:max_kpis]:
                score = k.get("composite_score", 0)
                parts.append(
                    f"- [{k.get('kpi_id', 'N/A')}] {k.get('name', 'Unknown')} "
                    f"(score={score:.2f})"
                )
                if k.get("description"):
                    parts.append(f"  {str(k['description'])[:180]}")
    
    if include_schemas:
        schemas = scored_context.get("resolved_schemas", [])
        if schemas:
            if silver_gold_tables_only:
                parts.append("\n### RESOLVED MDL SCHEMAS (SILVER TABLES — use as source for calculation) ###")
            else:
                parts.append("\n### RESOLVED MDL SCHEMAS ###")
            for s in schemas[:max_schemas]:
                parts.append(f"- Table: {s.get('table_name', 'Unknown')}")
                if s.get("table_ddl"):
                    parts.append(f"  DDL: {str(s['table_ddl'])[:250]}")
                elif s.get("description"):
                    parts.append(f"  Desc: {str(s['description'])[:200]}")
                if s.get("column_metadata"):
                    cols = s["column_metadata"][:6]
                    col_str = ", ".join(
                        c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in cols
                    )
                    parts.append(f"  Columns (sample): {col_str}")
        
        gold_tables = scored_context.get("gold_standard_tables", [])
        if gold_tables:
            parts.append("\n### GOLD STANDARD TABLES ###")
            for gt in gold_tables[:max_schemas]:
                parts.append(
                    f"- {gt.get('table_name', 'Unknown')} "
                    f"(category={gt.get('category', '?')}, grain={gt.get('grain', '?')})"
                )
    
    if not parts:
        return "No relevant scored context available."
    
    return "\n".join(parts)
