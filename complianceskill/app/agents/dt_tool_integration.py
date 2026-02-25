"""
Detection & Triage Workflow — Tool Integration Utilities

Extends tool_integration.py with DT-specific helpers:
- dt_get_tools_for_agent()     tool maps for DT agents
- run_async()                  safe async-in-sync runner (copied pattern from nodes.py)
- dt_retrieve_mdl_schemas()    direct schema-name lookup (not semantic search)
- dt_retrieve_gold_tables()    project meta lookup for GoldStandardTables
- dt_format_scored_context()   format scored_context for LLM prompt injection
"""
import asyncio
import concurrent.futures
import json
import logging
from typing import Any, Dict, List, Optional

from app.agents.state import EnhancedCompliancePipelineState
from app.agents.tool_integration import (  # noqa: F401 — re-export helpers used by DT nodes
    intelligent_retrieval,
    get_tools_for_agent,
    format_retrieved_context_for_prompt,
    create_tool_calling_agent,
    should_use_tool_calling_agent,
    TOOL_REGISTRY,
)

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

    This is the same pattern used in metrics_recommender_node and
    calculation_planner_node — centralised here to avoid duplication.
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
# DT-specific tool maps
# ============================================================================

# Tool lists for each DT agent.  Keys match agent names used in dt_nodes.py.
DT_TOOL_MAP: Dict[str, List[str]] = {
    "dt_intent_classifier": [
        "tavily_search",
    ],
    "dt_planner": [
        "tavily_search",
        "framework_control_search",
    ],
    "dt_detection_engineer": [
        # CVE & vulnerability intelligence
        "cve_intelligence",
        "epss_lookup",
        "cisa_kev_check",
        "cve_to_attack_mapper",
        # ATT&CK
        "attack_technique_lookup",
        "attack_to_control_mapper",
        "attack_path_builder",
        # Threat intel
        "otx_pulse_search",
        "virustotal_lookup",
        # Risk / exploit
        "exploit_db_search",
        "metasploit_module_search",
        "nuclei_template_search",
        "risk_calculator",
    ],
    "dt_triage_engineer": [
        # Framework context
        "framework_control_search",
        # Risk context
        "risk_calculator",
    ],
    "dt_playbook_assembler": [
        "tavily_search",
    ],
    "dt_dashboard_context_discoverer": [
        "framework_control_search",
    ],
    "dt_dashboard_question_generator": [
        "framework_control_search",
    ],
}


def dt_get_tools_for_agent(
    agent_name: str,
    state: Optional[EnhancedCompliancePipelineState] = None,
    conditional: bool = True,
) -> List[Any]:
    """
    Return instantiated LangChain tools for the given DT agent.

    Falls back to the base get_tools_for_agent() if the agent is not in
    DT_TOOL_MAP (so DT nodes can also access existing agent tools if needed).

    Args:
        agent_name: One of the DT agent names (e.g., "dt_detection_engineer")
        state:      Pipeline state used for conditional filtering
        conditional: When True, apply conditional loading logic
    Returns:
        List of instantiated tool objects
    """
    tool_names = DT_TOOL_MAP.get(agent_name)

    # Fall back to base map if not a DT-specific agent
    if tool_names is None:
        return get_tools_for_agent(agent_name, state=state, conditional=conditional)

    # Conditional filtering mirrors _filter_tools_conditionally logic
    if conditional and state and tool_names:
        tool_names = _dt_filter_tools_conditionally(tool_names, agent_name, state)

    tools = []
    for name in tool_names:
        if name in TOOL_REGISTRY:
            try:
                tools.append(TOOL_REGISTRY[name]())
            except Exception as e:
                logger.warning(f"dt_get_tools_for_agent: failed to load tool {name}: {e}")
    return tools


def _dt_filter_tools_conditionally(
    tool_names: List[str],
    agent_name: str,
    state: EnhancedCompliancePipelineState,
) -> List[str]:
    """Apply the same conditional logic as _filter_tools_conditionally for DT tools."""
    user_query = state.get("user_query", "").lower()
    scenarios = state.get("scenarios", [])
    risks = state.get("risks", [])
    filtered = []

    for name in tool_names:
        should_load = True

        if name in ("cve_intelligence", "cve_to_attack_mapper", "epss_lookup", "cisa_kev_check"):
            should_load = (
                "cve" in user_query
                or any("cve" in str(s).lower() for s in scenarios)
                or any("cve" in str(r).lower() for r in risks)
            )
        elif name in ("exploit_db_search", "metasploit_module_search", "nuclei_template_search"):
            should_load = (
                "exploit" in user_query
                or "vulnerability" in user_query
                or any("exploit" in str(s).lower() for s in scenarios)
            )
        elif name in ("otx_pulse_search", "virustotal_lookup"):
            should_load = (
                "threat" in user_query
                or "malware" in user_query
                or any("threat" in str(s).lower() for s in scenarios)
            )
        elif name == "tavily_search":
            should_load = agent_name in ("dt_planner", "dt_playbook_assembler", "dt_intent_classifier")
        # All others (attack_technique_lookup, framework_control_search, etc.) always load

        if should_load:
            filtered.append(name)

    return filtered


# ============================================================================
# Product capabilities query helper
# ============================================================================

def _query_product_capabilities_from_qdrant(
    selected_data_sources: List[str],
) -> List[Dict[str, Any]]:
    """
    Query product capabilities from Qdrant based on selected data sources.
    Falls back to reading from JSON files if Qdrant lookup fails.
    
    Args:
        selected_data_sources: List of data source IDs (e.g., ["qualys", "okta"])
    
    Returns:
        List of product capability dicts with product_id, capability_id, etc.
    """
    capabilities = []
    
    # Try Qdrant first
    try:
        from app.core.dependencies import get_doc_store_provider
        from app.storage.qdrant_store import DocumentQdrantStore
        
        doc_store_provider = get_doc_store_provider()
        stores = doc_store_provider.stores if hasattr(doc_store_provider, "stores") else {}
        
        # Try to get product_capabilities store
        product_cap_store = stores.get("product_capabilities")
        
        if not product_cap_store:
            # Try to create it if we're using Qdrant
            try:
                from app.core.settings import get_settings
                from langchain_openai import OpenAIEmbeddings
                from app.storage.documents import DocumentQdrantStore
                
                settings = get_settings()
                qdrant_config = settings.get_vector_store_config()
                embeddings_model = OpenAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    openai_api_key=settings.OPENAI_API_KEY
                )
                
                product_cap_store = DocumentQdrantStore(
                    collection_name="product_capabilities",
                    host=qdrant_config.get("host", "localhost"),
                    port=qdrant_config.get("port", 6333),
                    embeddings_model=embeddings_model
                )
            except Exception as e:
                logger.warning(f"Could not access product_capabilities collection: {e}")
                product_cap_store = None
        
        if product_cap_store:
            # Query for each product_id
            for product_id in selected_data_sources:
                # Extract base product_id (e.g., "qualys.vulnerabilities" -> "qualys")
                base_product_id = product_id.split(".")[0].lower()
                
                try:
                    # Query Qdrant for product capabilities with product_id filter
                    where_clause = {
                        "$and": [
                            {"type": {"$eq": "PRODUCT_CAPABILITY"}},
                            {"product_id": {"$eq": base_product_id}}
                        ]
                    }
                    
                    results = product_cap_store.semantic_search(
                        query=f"product capability {base_product_id}",
                        k=20,
                        where=where_clause
                    )
                    
                    for result in results:
                        metadata = result.get("metadata", {})
                        if metadata.get("product_id") == base_product_id:
                            capabilities.append({
                                "product_id": metadata.get("product_id", ""),
                                "capability_id": metadata.get("capability_id", ""),
                                "name": metadata.get("name", ""),
                                "product_name": metadata.get("product_name", ""),
                                "description": metadata.get("description", ""),
                                "planning_notes": metadata.get("planning_notes", ""),
                                "score": result.get("score", 1.0),
                            })
                except Exception as e:
                    logger.warning(f"Failed to query product capabilities for {base_product_id}: {e}")
                    continue
    except Exception as e:
        logger.warning(f"Qdrant product capabilities lookup failed: {e}")
    
    # Fallback: Read from JSON files if Qdrant lookup returned no results
    if not capabilities:
        logger.info("Falling back to JSON file lookup for product capabilities")
        for product_id in selected_data_sources:
            base_product_id = product_id.split(".")[0].lower()
            try:
                import json
                import os
                from pathlib import Path
                
                # Try to find the product capabilities JSON file
                # Common locations: ProductKnowledge_repo/product_capabilities_enriched/{product_id}.json
                possible_paths = [
                    Path("/Users/sameerm/ComplianceSpark/byziplatform/ProductKnowledge_repo/product_capabilities_enriched") / f"{base_product_id}.json",
                    Path("ProductKnowledge_repo/product_capabilities_enriched") / f"{base_product_id}.json",
                    Path("../ProductKnowledge_repo/product_capabilities_enriched") / f"{base_product_id}.json",
                ]
                
                json_file = None
                for path in possible_paths:
                    if path.exists():
                        json_file = path
                        break
                
                if json_file:
                    with open(json_file, 'r') as f:
                        product_data = json.load(f)
                    
                    # Extract capabilities from api_categories or business_purposes
                    api_categories = product_data.get("api_categories", [])
                    for category in api_categories:
                        cap_id = category.get("id", "")
                        if cap_id:
                            capabilities.append({
                                "product_id": base_product_id,
                                "capability_id": cap_id,
                                "name": category.get("name", ""),
                                "product_name": product_data.get("product_name", ""),
                                "description": category.get("description", ""),
                                "planning_notes": category.get("planning_notes", ""),
                                "score": 1.0,
                            })
                    
                    logger.info(f"Loaded {len([c for c in capabilities if c['product_id'] == base_product_id])} capabilities from JSON for {base_product_id}")
                else:
                    logger.warning(f"Could not find product capabilities JSON file for {base_product_id}")
            except Exception as e:
                logger.warning(f"Failed to read product capabilities JSON for {base_product_id}: {e}")
                continue
    
    logger.info(f"Found {len(capabilities)} total product capabilities for {selected_data_sources}")
    return capabilities


# ============================================================================
# MDL schema lookup via product capabilities + project_id
# ============================================================================

def dt_retrieve_mdl_schemas(
    schema_names: List[str],
    fallback_query: Optional[str] = None,
    limit: int = 10,
    selected_data_sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Retrieve MDL schemas using a two-step approach:
    1. Query product capabilities from Qdrant based on selected_data_sources
    2. Use project_id (e.g., "qualys_assets") to fetch MDL schemas from project data
    
    This approach ensures we get the correct tables for the selected products.

    Args:
        schema_names: List of schema names (for backward compatibility, may be empty)
        fallback_query: Fallback semantic query if product-based lookup fails
        limit: Maximum number of results
        selected_data_sources: List of selected data sources (e.g., ["qualys", "okta"])

    Returns:
        {
            "schemas": [{"table_name", "table_ddl", "column_metadata", "description", "score"}],
            "table_descriptions": [...],
            "lookup_hits": [str],    # project_ids found
            "lookup_misses": [str],  # project_ids not found
        }
    """
    from app.retrieval.mdl_service import MDLRetrievalService

    mdl_service = MDLRetrievalService()
    results: Dict[str, Any] = {
        "schemas": [],
        "table_descriptions": [],
        "lookup_hits": [],
        "lookup_misses": [],
    }

    # Step 1: Query product capabilities from Qdrant (with JSON fallback)
    product_capabilities = []
    if selected_data_sources:
        logger.info(f"Step 1: Querying product capabilities for {selected_data_sources}")
        product_capabilities = _query_product_capabilities_from_qdrant(selected_data_sources)
        logger.info(f"Found {len(product_capabilities)} product capabilities for {selected_data_sources}")
        if product_capabilities:
            logger.info(f"Product capabilities: {[(c.get('product_id'), c.get('capability_id')) for c in product_capabilities[:5]]}")
        else:
            logger.warning(f"No product capabilities found for {selected_data_sources} - will try semantic fallback (MDL enrichment)")
    else:
        logger.info("Step 1: No selected_data_sources provided - will use semantic fallback (MDL enrichment)")

    # Step 2: For each product capability, construct project_id and fetch MDL schemas
    project_ids_queried = set()
    
    if not product_capabilities:
        logger.info("Step 2: No product capabilities found - will rely on gold standard tables lookup")
    
    for cap in product_capabilities:
        product_id = cap.get("product_id", "")
        capability_id = cap.get("capability_id", "")
        
        if not product_id or not capability_id:
            continue
        
        # Construct project_id as "{product_id}_{capability_id}" (e.g., "qualys_assets")
        project_id = f"{product_id}_{capability_id}"
        
        if project_id in project_ids_queried:
            continue
        project_ids_queried.add(project_id)
        
        try:
            logger.info(f"Querying MDL schemas for project_id='{project_id}' (product={product_id}, capability={capability_id})")
            
            # Query MDL schemas using project_id parameter (MDLRetrievalService supports this)
            schema_results = run_async(
                mdl_service.search_db_schema(
                    query=f"{product_id} {capability_id} schema",
                    limit=10,
                    project_id=project_id
                )
            )
            
            logger.info(f"MDL search returned {len(schema_results)} schemas for project_id='{project_id}'")
            
            if schema_results:
                results["lookup_hits"].append(project_id)
                for r in schema_results:
                    table_name = r.table_name if hasattr(r, "table_name") else ""
                    if table_name:
                        logger.info(f"  Found schema: {table_name} (score={r.score if hasattr(r, 'score') else 'N/A'})")
                        results["schemas"].append({
                            "table_name": table_name,
                            "table_ddl": r.schema_ddl if hasattr(r, "schema_ddl") else "",
                            "column_metadata": r.columns if hasattr(r, "columns") else [],
                            "description": r.metadata.get("description", "") if (r.metadata and isinstance(r.metadata, dict)) else "",
                            "score": r.score if hasattr(r, "score") else 1.0,
                            "id": r.id if hasattr(r, "id") else "",
                            "project_id": project_id,
                            "product_id": product_id,
                            "capability_id": capability_id,
                        })
            else:
                logger.warning(f"No schemas found for project_id='{project_id}' - trying alternative project_id formats")
                results["lookup_misses"].append(project_id)
                
                # Try alternative project_id formats
                alt_project_ids = [
                    f"{product_id}_{capability_id}",  # Already tried
                    capability_id,  # Just capability
                    product_id,  # Just product
                ]
                
                for alt_project_id in alt_project_ids[1:]:  # Skip first (already tried)
                    if alt_project_id == project_id:
                        continue
                    try:
                        alt_results = run_async(
                            mdl_service.search_db_schema(
                                query=f"{product_id} {capability_id}",
                                limit=5,
                                project_id=alt_project_id
                            )
            )
                        if alt_results:
                            logger.info(f"Found {len(alt_results)} schemas with alternative project_id='{alt_project_id}'")
                            results["lookup_hits"].append(alt_project_id)
                            for r in alt_results:
                                table_name = r.table_name if hasattr(r, "table_name") else ""
                                if table_name and not any(s["table_name"] == table_name for s in results["schemas"]):
                                    results["schemas"].append({
                                        "table_name": table_name,
                                        "table_ddl": r.schema_ddl if hasattr(r, "schema_ddl") else "",
                                        "column_metadata": r.columns if hasattr(r, "columns") else [],
                                        "description": r.metadata.get("description", "") if (r.metadata and isinstance(r.metadata, dict)) else "",
                                        "score": r.score if hasattr(r, "score") else 0.8,
                                        "id": r.id if hasattr(r, "id") else "",
                                        "project_id": alt_project_id,
                                        "product_id": product_id,
                                        "capability_id": capability_id,
                                    })
                            break
                    except Exception as alt_e:
                        logger.debug(f"Alternative project_id '{alt_project_id}' also failed: {alt_e}")
                
            # Also query table_descriptions with project_id
            table_desc_results = run_async(
                mdl_service.search_table_descriptions(
                    query=f"{product_id} {capability_id} table",
                    limit=10,
                    project_id=project_id
                )
            )
            
            for r in table_desc_results:
                table_name = getattr(r, "table_name", "")
                if table_name:
                    already = any(t["table_name"] == table_name for t in results["table_descriptions"])
                    if not already:
                        results["table_descriptions"].append({
                            "table_name": table_name,
                            "description": getattr(r, "description", ""),
                            "columns": r.relationships if hasattr(r, "relationships") else [],
                            "score": r.score if hasattr(r, "score") else 0.5,
                            "id": r.id if hasattr(r, "id") else "",
                            "project_id": project_id,
                        })
                            
        except Exception as e:
            logger.warning(f"dt_retrieve_mdl_schemas: failed to fetch schemas for project_id '{project_id}': {e}")
            results["lookup_misses"].append(project_id)

    # Step 3: Direct MDL search if no schemas found via product capabilities
    # Simple fallback: search entire collection and filter by source name
    if not results["schemas"] and fallback_query:
        logger.info("=" * 80)
        logger.info("Step 3: DIRECT MDL SEARCH (fallback)")
        logger.info("=" * 80)
        logger.info(f"  Query: {fallback_query[:150]}")
        logger.info(f"  Selected data sources: {selected_data_sources}")
        logger.info(f"  Limit: {limit}")
        
        try:
            # Direct search - get more results to filter from
            search_limit = limit * 3  # Get more to filter down
            logger.info(f"  → Searching MDL collection (limit={search_limit})")
            
            fallback_schemas = run_async(
                mdl_service.search_db_schema(query=fallback_query, limit=search_limit, project_id=None)
            )
            logger.info(f"  ← Found {len(fallback_schemas)} schema results")
            
            fallback_table_descs = run_async(
                mdl_service.search_table_descriptions(query=fallback_query, limit=search_limit)
            )
            logger.info(f"  ← Found {len(fallback_table_descs)} table description results")
            
            # Log details for debugging
            if fallback_schemas:
                logger.info(f"  Schema results (first 3):")
                for i, r in enumerate(fallback_schemas[:3]):
                    table_name = getattr(r, "table_name", "") or (r.metadata.get("table_name", "") if hasattr(r, "metadata") and isinstance(r.metadata, dict) else "")
                    metadata = getattr(r, "metadata", {}) if hasattr(r, "metadata") else {}
                    project_id = metadata.get("project_id", "")
                    logger.info(f"    [{i+1}] table_name='{table_name}', project_id='{project_id}'")
            
            if fallback_table_descs:
                logger.info(f"  Table description results (first 3):")
                for i, r in enumerate(fallback_table_descs[:3]):
                    table_name = getattr(r, "table_name", "") or ""
                    metadata = getattr(r, "metadata", {}) if hasattr(r, "metadata") else {}
                    project_id = metadata.get("project_id", "")
                    logger.info(f"    [{i+1}] table_name='{table_name}', project_id='{project_id}'")
            
            # Filter by source name if provided
            if selected_data_sources:
                source_names = [ds.split(".")[0].lower() for ds in selected_data_sources]
                logger.info(f"  → Filtering by source: {source_names}")
                
                # Filter schemas
                filtered_schemas = []
                for r in fallback_schemas:
                    table_name = getattr(r, "table_name", "") or (r.metadata.get("table_name", "") if hasattr(r, "metadata") and isinstance(r.metadata, dict) else "")
                    metadata = getattr(r, "metadata", {}) if hasattr(r, "metadata") else {}
                    project_id = metadata.get("project_id", "")
                    
                    # Check if table_name or project_id contains source
                    matches = any(
                        source_name in table_name.lower() or 
                        source_name in project_id.lower()
                        for source_name in source_names
                    )
                    
                    if matches and table_name and table_name.lower() not in ("", "unknown", "null", "none"):
                        filtered_schemas.append(r)
                        logger.info(f"    ✓ Keeping schema: '{table_name}' (project_id='{project_id}')")
                
                fallback_schemas = filtered_schemas[:limit]
                logger.info(f"  ← Filtered to {len(fallback_schemas)} schemas matching sources")
                
                # Filter table descriptions
                filtered_table_descs = []
                for r in fallback_table_descs:
                    table_name = getattr(r, "table_name", "") or ""
                    metadata = getattr(r, "metadata", {}) if hasattr(r, "metadata") else {}
                    project_id = metadata.get("project_id", "")
                    
                    # Check if table_name or project_id contains source
                    matches = any(
                        source_name in table_name.lower() or 
                        source_name in project_id.lower()
                        for source_name in source_names
                    )
                    
                    if matches and table_name and table_name.lower() not in ("", "unknown", "null", "none"):
                        filtered_table_descs.append(r)
                        logger.info(f"    ✓ Keeping table description: '{table_name}' (project_id='{project_id}')")
                
                fallback_table_descs = filtered_table_descs[:limit]
                logger.info(f"  ← Filtered to {len(fallback_table_descs)} table descriptions matching sources")
            
            # Process and add valid schemas
            for r in fallback_schemas:
                table_name = getattr(r, "table_name", "") or (r.metadata.get("table_name", "") if hasattr(r, "metadata") and isinstance(r.metadata, dict) else "")
                if not table_name or table_name.lower() in ("", "unknown", "null", "none"):
                    continue
                
                if not any(s["table_name"] == table_name for s in results["schemas"]):
                    metadata = getattr(r, "metadata", {}) if hasattr(r, "metadata") else {}
                    results["schemas"].append({
                        "table_name": table_name,
                        "table_ddl": r.schema_ddl if hasattr(r, "schema_ddl") else "",
                        "column_metadata": r.columns if hasattr(r, "columns") else [],
                        "description": metadata.get("description", ""),
                        "score": r.score if hasattr(r, "score") else 0.5,
                        "id": r.id if hasattr(r, "id") else "",
                        "project_id": metadata.get("project_id", ""),
                    })
            
            # Process and add valid table descriptions
            for r in fallback_table_descs:
                table_name = getattr(r, "table_name", "") or ""
                if not table_name or table_name.lower() in ("", "unknown", "null", "none"):
                    continue
                
                if not any(t["table_name"] == table_name for t in results["table_descriptions"]):
                    results["table_descriptions"].append({
                        "table_name": table_name,
                        "description": getattr(r, "description", ""),
                        "columns": r.relationships if hasattr(r, "relationships") else [],
                        "score": r.score if hasattr(r, "score") else 0.5,
                        "id": r.id if hasattr(r, "id") else "",
                    })
                    
        except Exception as e:
            logger.error(f"  ✗ Direct MDL search failed: {e}", exc_info=True)

    # Filter out invalid schemas (empty table_name or "unknown")
    logger.info("=" * 80)
    logger.info("Step 4: FILTERING INVALID SCHEMAS")
    logger.info("=" * 80)
    logger.info(f"  Total schemas before filtering: {len(results['schemas'])}")
    
    valid_schemas = [s for s in results["schemas"] if s.get("table_name") and s.get("table_name", "").lower() not in ("", "unknown", "null", "none")]
    invalid_count = len(results["schemas"]) - len(valid_schemas)
    
    if invalid_count > 0:
        logger.warning(f"  ⚠ Filtered out {invalid_count} invalid schemas (empty or 'unknown' table_name)")
    
    results["schemas"] = valid_schemas
    logger.info(f"  ✓ Valid schemas after filtering: {len(valid_schemas)}")
    
    # Final summary
    logger.info(
        f"dt_retrieve_mdl_schemas summary: {len(results['schemas'])} valid schemas, "
        f"{len(results['table_descriptions'])} table descriptions, "
        f"{len(results['lookup_hits'])} hits, {len(results['lookup_misses'])} misses"
    )

    return results


# ============================================================================
# GoldStandardTable lookup
# ============================================================================

def dt_retrieve_gold_standard_tables(
    project_id: str,
    categories: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve GoldStandardTables available under the given project_id from
    leen_project_meta.

    Optionally filter by metric categories (e.g., ["vulnerabilities", "access_control"]).

    Returns:
        List of table records with {table_name, category, grain, description, is_gold_standard}
    """
    from app.retrieval.mdl_service import MDLRetrievalService

    mdl_service = MDLRetrievalService()
    gold_tables: List[Dict[str, Any]] = []

    if not project_id:
        return gold_tables

    query = f"gold standard tables project {project_id}"
    if categories:
        query += " " + " ".join(categories)

    try:
        project_meta_results = run_async(
            mdl_service.search_project_meta(query=query, limit=30)
        )
        for r in project_meta_results:
            metadata = r.metadata if (hasattr(r, "metadata") and isinstance(r.metadata, dict)) else {}
            # Accept records tagged as gold_standard or project_id match
            if (
                metadata.get("is_gold_standard", False)
                or metadata.get("project_id", "") == project_id
                or (hasattr(r, "project_id") and r.project_id == project_id)
            ):
                table_name = getattr(r, "table_name", "") or metadata.get("table_name", "")
                category = metadata.get("category", "")
                # Category filter
                if categories and category and category not in categories:
                    continue
                gold_tables.append({
                    "table_name": table_name,
                    "category": category,
                    "grain": metadata.get("grain", ""),
                    "description": getattr(r, "description", "") or metadata.get("description", ""),
                    "is_gold_standard": True,
                    "project_id": project_id,
                    "score": r.score if hasattr(r, "score") else 1.0,
                })
    except Exception as e:
        logger.warning(f"dt_retrieve_gold_standard_tables: failed for project_id={project_id}: {e}")

    return gold_tables


# ============================================================================
# Prompt context formatter for scored_context
# ============================================================================

def dt_format_scored_context_for_prompt(
    scored_context: Dict[str, Any],
    include_schemas: bool = True,
    include_metrics: bool = True,
    max_controls: int = 8,
    max_metrics: int = 10,
    max_schemas: int = 5,
) -> str:
    """
    Format the scored_context dict produced by dt_scoring_validator_node into
    a compact, LLM-friendly prompt string.

    Controls how much of each category is included to stay within token budgets.
    """
    import json
    parts = []

    controls = scored_context.get("controls", [])
    if controls:
        parts.append("### SCORED CONTROLS ###")
        for ctrl in controls[:max_controls]:
            score = ctrl.get("composite_score", 0)
            low_conf = " [LOW CONFIDENCE]" if ctrl.get("low_confidence") else ""
            parts.append(
                f"- [{ctrl.get('code', 'N/A')}] {ctrl.get('name', 'Unknown')} "
                f"(score={score:.2f}){low_conf}"
            )
            if ctrl.get("description"):
                parts.append(f"  {str(ctrl['description'])[:180]}")

    risks = scored_context.get("risks", [])
    if risks:
        parts.append("\n### SCORED RISKS ###")
        for risk in risks[:5]:
            score = risk.get("composite_score", 0)
            parts.append(
                f"- [{risk.get('risk_code', 'N/A')}] {risk.get('name', 'Unknown')} "
                f"(likelihood={risk.get('likelihood', '?')}, impact={risk.get('impact', '?')}, score={score:.2f})"
            )

    scenarios = scored_context.get("scenarios", [])
    if scenarios:
        parts.append("\n### SCORED SCENARIOS ###")
        for sc in scenarios[:5]:
            score = sc.get("composite_score", 0)
            parts.append(
                f"- [{sc.get('severity', '?').upper()}] {sc.get('name', 'Unknown')} (score={score:.2f})"
            )
            if sc.get("description"):
                parts.append(f"  {str(sc['description'])[:180]}")

    if include_metrics:
        metrics = scored_context.get("scored_metrics", [])
        if metrics:
            parts.append("\n### SCORED METRICS ###")
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
                if m.get("kpis"):
                    kpis_str = ", ".join(str(k) for k in m["kpis"][:4])
                    parts.append(f"  KPIs: {kpis_str}")

    if include_schemas:
        schemas = scored_context.get("resolved_schemas", [])
        if schemas:
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
