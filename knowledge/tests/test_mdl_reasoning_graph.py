"""
CLI script to test MDL Reasoning and Planning Graph

Usage:
    # Test retrieval only (without running full graph)
    python -m tests.test_mdl_reasoning_graph \
        --test-retrieval-only \
        --question "what are asset related tables?" \
        --project-id Snyk
    
    # Single query (interactive) - defaults to Snyk
    python -m tests.test_mdl_reasoning_graph \
        --question "What tables are related to AccessRequest in Snyk?"
    
    # Single query with explicit product (defaults to Snyk if not specified)
    python -m tests.test_mdl_reasoning_graph \
        --question "What tables are related to AccessRequest?" \
        --product-name Snyk
    
    # Single query with actor (summary will be written for the actor)
    python -m tests.test_mdl_reasoning_graph \
        --question "What tables are related to user access request and their soc2 compliance controls?" \
        --product-name Snyk \
        --actor "Data Engineer"
    
    # Single query with actor and project-id (for metrics retrieval)
    python -m tests.test_mdl_reasoning_graph \
        --question "What tables are related to user access request and their soc2 compliance controls?" \
        --product-name Snyk \
        --actor "Compliance Officer" \
        --project-id Snyk
    
    # Batch testing (runs predefined test queries, all use Snyk)
    python -m tests.test_mdl_reasoning_graph --batch
"""
import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from langchain_openai import ChatOpenAI

from app.core.settings import get_settings, clear_settings_cache
from app.core.dependencies import (
    get_chromadb_client,
    get_embeddings_model,
    get_llm
)
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory
from app.agents.mdl_reasoning_nodes import create_mdl_reasoning_graph

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_retrieval_only(
    user_question: str,
    project_id: str = "Snyk",
    top_k: int = 10
):
    """Test retrieval only without running the full graph"""
    logger.info("=" * 80)
    logger.info("Retrieval-Only Test")
    logger.info("=" * 80)
    logger.info(f"Question: {user_question}")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Top K: {top_k}")
    logger.info("")
    
    # Clear settings cache
    clear_settings_cache()
    
    # Get RetrievalHelper
    try:
        from app.agents.data.retrieval_helper import RetrievalHelper
        retrieval_helper = RetrievalHelper()
        logger.info("RetrievalHelper initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RetrievalHelper: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return
    
    # Test retrieval
    try:
        logger.info("Testing retrieval with get_database_schemas...")
        table_retrieval = {
            "table_retrieval_size": top_k,
            "table_column_retrieval_size": 100,
            "allow_using_db_schemas_without_pruning": True  # Skip column pruning - return full DDL for markdown
        }
        
        result = await retrieval_helper.get_database_schemas(
            project_id=project_id,
            table_retrieval=table_retrieval,
            query=user_question,
            histories=None,
            tables=None
        )
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("Retrieval Results")
        logger.info("=" * 80)
        
        if result and "schemas" in result:
            schemas = result.get("schemas", [])
            logger.info(f"Total schemas retrieved: {len(schemas)}")
            logger.info("")
            
            for i, schema in enumerate(schemas, 1):
                table_name = schema.get("table_name", "Unknown")
                table_ddl = schema.get("table_ddl", "")
                column_metadata = schema.get("column_metadata", [])
                
                logger.info(f"{i}. Table: {table_name}")
                logger.info(f"   Columns: {len(column_metadata)}")
                if table_ddl:
                    # Show first 200 chars of DDL
                    ddl_preview = table_ddl[:200].replace('\n', ' ')
                    logger.info(f"   DDL preview: {ddl_preview}...")
                logger.info("")
            
            # Log metadata
            logger.info("Result metadata:")
            for key, value in result.items():
                if key != "schemas":
                    if isinstance(value, dict):
                        logger.info(f"   {key}: dict with {len(value)} items")
                    else:
                        logger.info(f"   {key}: {value}")
        else:
            logger.warning("No schemas returned from retrieval")
            logger.info(f"Result: {result}")
            
    except Exception as e:
        logger.error(f"Error during retrieval test: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def test_graph(
    user_question: str,
    product_name: str = "Snyk",
    model_name: str = "gpt-4o-mini",
    actor: Optional[str] = None,
    project_id: Optional[str] = None
):
    """Test MDL reasoning graph with a question"""
    logger.info("=" * 80)
    logger.info("MDL Reasoning and Planning Graph Test")
    logger.info("=" * 80)
    logger.info(f"Question: {user_question}")
    logger.info(f"Product: {product_name}")
    if actor:
        logger.info(f"Actor: {actor}")
    if project_id:
        logger.info(f"Project ID: {project_id}")
    logger.info("")
    
    # Clear settings cache
    clear_settings_cache()
    
    # Get dependencies - use existing stores
    logger.info("Initializing dependencies from existing stores...")
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    # Use get_llm with model parameter (not model_name)
    llm = get_llm(temperature=0.2, model=model_name)
    
    # Initialize collection factory using settings (leverages existing stores)
    from app.storage.vector_store import ChromaVectorStoreClient
    from app.core.settings import get_settings
    
    settings = get_settings()
    # Use settings to get proper vector store configuration
    vector_store_config = settings.get_vector_store_config()
    
    # Create vector store client with proper config (uses existing ChromaDB)
    vector_store_client = ChromaVectorStoreClient(
        config=vector_store_config,
        embeddings_model=embeddings
    )
    # Use the cached persistent client from dependencies (existing store)
    vector_store_client._client = persistent_client
    
    # Initialize collection factory (uses existing collections)
    collection_factory = CollectionFactory(
        vector_store_client=vector_store_client,
        embeddings_model=embeddings,
        collection_prefix=""  # No prefix - use existing collections
    )
    
    # Initialize contextual graph storage (uses existing stores, no new data creation)
    contextual_graph_storage = ContextualGraphStorage(
        vector_store_client=vector_store_client,
        embeddings_model=embeddings,
        collection_prefix="",  # No prefix - use existing collections
        collection_factory=collection_factory
    )
    
    logger.info("Creating graph...")
    
    # Create retrieval_helper with the vector_store_client (required for table retrieval via MDL queries)
    retrieval_helper = None
    try:
        from app.agents.data.retrieval_helper import RetrievalHelper
        retrieval_helper = RetrievalHelper(vector_store_client=vector_store_client)
        logger.info("RetrievalHelper created successfully - table retrieval via MDL queries enabled")
    except (ImportError, Exception) as e:
        logger.error(f"Failed to create RetrievalHelper: {e}. Table retrieval will not work properly.")
        retrieval_helper = None
    
    # Create graph
    graph = create_mdl_reasoning_graph(
        contextual_graph_storage=contextual_graph_storage,
        collection_factory=collection_factory,
        llm=llm,
        model_name=model_name,
        use_checkpointing=False,
        retrieval_helper=retrieval_helper
    )
    
    # Initial state - use Snyk as default project/product
    initial_state = {
        "user_question": user_question,
        "product_name": product_name or "Snyk",  # Default to Snyk for all purposes
        "project_id": project_id or product_name or "Snyk",  # Use provided project_id or default to product_name
        "actor": actor,  # Actor making the request (optional)
        "identified_entities": [],
        "search_questions": [],
        "tables_found": [],
        "entities_found": [],
        "entity_questions": [],
        "contexts_retrieved": [],
        "edges_discovered": [],
        "related_entities": [],
        "natural_language_questions": [],
        "reasoning_plan": None,
        "plan_components": {},  # Initialize as empty dict, not None
        "current_step": "start",
        "status": "processing",
        "messages": []
    }
    
    try:
        # Run graph
        logger.info("Running graph...")
        logger.info("")
        result = await graph.ainvoke(initial_state)
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("Results")
        logger.info("=" * 80)
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Current Step: {result.get('current_step')}")
        
        if result.get("error"):
            logger.error(f"Error: {result.get('error')}")
            return
        
        # Note: State normalization is now handled at the source in each node.
        # This ensures data is in the correct format when set in state, not just when output.
        
        # Log full state after each step for debugging
        logger.info("")
        logger.info("=" * 80)
        logger.info("FULL STATE AFTER GRAPH EXECUTION (NO TRUNCATION)")
        logger.info("=" * 80)
        import json as json_module
        state_json = json_module.dumps(result, indent=2, default=str)
        logger.info(f"Full State JSON ({len(state_json)} chars):\n{state_json}")
        logger.info("=" * 80)
        
        # Generic Breakdown
        generic_breakdown = result.get("generic_breakdown", {})
        if generic_breakdown:
            logger.info("")
            logger.info("1. Generic Breakdown (First Step):")
            logger.info(f"   Query Type: {generic_breakdown.get('query_type', 'unknown')}")
            logger.info(f"   Identified Entities: {len(generic_breakdown.get('identified_entities', []))}")
            for entity in generic_breakdown.get('identified_entities', [])[:10]:
                logger.info(f"     - {entity}")
        
        # MDL Table Curation
        context_breakdown = result.get("context_breakdown", {})
        relevant_tables = result.get("relevant_tables", [])
        mdl_queries = result.get("mdl_queries", [])
        mdl_queries_planning = result.get("mdl_queries_planning", [])
        curated_tables_info = result.get("tables_found", [])
        if context_breakdown:
            logger.info("")
            logger.info("2. MDL Table Curation (if query_type is mdl):")
            if mdl_queries_planning:
                logger.info(f"   MDL Queries Processed (in parallel): {len(mdl_queries_planning)}")
                for i, query_obj in enumerate(mdl_queries_planning, 1):
                    if isinstance(query_obj, dict):
                        query_text = query_obj.get("query", "")
                        query_type = query_obj.get("type", "")
                        logger.info(f"     {i}. {query_text} (type: {query_type})")
                    else:
                        logger.info(f"     {i}. {query_obj}")
            elif mdl_queries:
                logger.info(f"   MDL Queries Processed (in parallel): {len(mdl_queries)}")
                for i, mdl_query in enumerate(mdl_queries, 1):
                    logger.info(f"     {i}. {mdl_query}")
            if curated_tables_info:
                logger.info(f"   Curated Tables (scored and pruned): {len(curated_tables_info)}")
                for table_info in curated_tables_info[:15]:
                    # Handle case where table_info might be a string or other type
                    if isinstance(table_info, dict):
                        table_name = table_info.get('table_name', 'Unknown')
                        score = table_info.get('relevance_score', 0.0)
                        logger.info(f"     - {table_name} (score: {score:.2f})")
                    elif isinstance(table_info, str):
                        logger.warning(f"     - table_info is a string (should be dict): '{table_info[:50]}...'")
                    else:
                        logger.warning(f"     - table_info is unexpected type {type(table_info)}: {str(table_info)[:50]}")
            mdl_results = context_breakdown.get('mdl_results', [])
            if mdl_results:
                logger.info(f"   Curation Results per MDL Query:")
                for i, mdl_result in enumerate(mdl_results, 1):
                    curated = mdl_result.get('curated_tables', [])
                    considered = mdl_result.get('total_tables_considered', 0)
                    pruned = mdl_result.get('tables_pruned', 0)
                    logger.info(f"     Query {i}: {len(curated)} curated (considered {considered}, pruned {pruned})")
        
        # Contextual Planning
        contextual_plan = result.get("contextual_plan", {})
        if contextual_plan:
            logger.info("")
            logger.info("3. Contextual Planning (identifies relevant edges for curated tables):")
            table_edges_raw = contextual_plan.get('table_edges', [])
            
            # Normalize table_edges - filter to ensure all entries are dicts
            table_edges = []
            for item in table_edges_raw:
                if isinstance(item, dict):
                    table_edges.append(item)
                elif isinstance(item, str):
                    logger.warning(f"   Skipping string edge: '{item[:50]}...'")
                else:
                    logger.warning(f"   Skipping non-dict edge: {type(item)}")
            
            if table_edges:
                logger.info(f"   Identified Edges: {len(table_edges)}")
                # Group by table
                edges_by_table = {}
                for edge in table_edges:
                    if isinstance(edge, dict):
                        table_name = edge.get('table_name', 'Unknown')
                        if table_name not in edges_by_table:
                            edges_by_table[table_name] = []
                        edges_by_table[table_name].append(edge)
                
                for table_name, edges in list(edges_by_table.items())[:10]:
                    logger.info(f"     {table_name}: {len(edges)} edges")
                    for edge in edges[:3]:  # Show first 3 edges per table
                        if isinstance(edge, dict):
                            edge_type = edge.get('edge_type', 'Unknown')
                            target = edge.get('target_entity_type', 'Unknown')
                            score = edge.get('relevance_score', 0.0)
                            logger.info(f"       - {edge_type} -> {target} (score: {score:.2f})")
                        else:
                            logger.warning(f"       - Non-dict edge: {type(edge)}")
            reasoning = contextual_plan.get('reasoning', '')
            if reasoning:
                logger.info(f"   Reasoning: {reasoning[:300]}...")
        
        # Edge-Based Retrieval
        contexts_retrieved = result.get("contexts_retrieved", [])
        edges_discovered_raw = result.get("edges_discovered", [])
        
        # Normalize edges_discovered - filter to ensure all entries are dicts
        edges_discovered = []
        for item in edges_discovered_raw:
            if isinstance(item, dict):
                edges_discovered.append(item)
            elif isinstance(item, str):
                logger.warning(f"   Skipping string edge in edges_discovered: '{item[:50]}...'")
            else:
                logger.warning(f"   Skipping non-dict edge in edges_discovered: {type(item)}")
        
        logger.info("")
        logger.info("4. Edge-Based Retrieval (retrieves data based on identified edges):")
        logger.info(f"   Contexts Retrieved: {len(contexts_retrieved)}")
        if contexts_retrieved:
            # Group by entity type
            contexts_by_type = {}
            for context in contexts_retrieved:
                if isinstance(context, dict):
                    entity_type = context.get('entity_type', 'unknown')
                    if entity_type not in contexts_by_type:
                        contexts_by_type[entity_type] = 0
                    contexts_by_type[entity_type] += 1
            logger.info(f"   Contexts by Type: {contexts_by_type}")
            for context in contexts_retrieved[:5]:
                if isinstance(context, dict):
                    entity_type = context.get('entity_type', 'Unknown')
                    source = context.get('source', 'N/A')
                    related_table = context.get('related_table', 'N/A')
                    logger.info(f"     - {entity_type} from {source} (table: {related_table})")
        
        logger.info(f"   Edges Discovered: {len(edges_discovered)}")
        for edge in edges_discovered[:5]:
            if isinstance(edge, dict):
                edge_type = edge.get('edge_type', 'Unknown')
                source = edge.get('source_entity_id', 'N/A')
                target = edge.get('target_entity_id', 'N/A')
                logger.info(f"     - {edge_type}: {source} -> {target}")
            else:
                logger.warning(f"     - Non-dict edge: {type(edge)}")
        
        # Summary
        summary = result.get("summary", {})
        logger.info("")
        logger.info("5. Summary:")
        if summary:
            answer = summary.get('answer', '')
            key_tables = summary.get('key_tables', [])
            relationships = summary.get('relationships', '')
            contexts = summary.get('contexts', '')
            metrics = summary.get('metrics', [])
            insights = summary.get('insights', '')
            logger.info(f"   Answer: {answer[:200]}..." if answer else "   Answer: Not provided")
            logger.info(f"   Key Tables: {len(key_tables)}")
            for table in key_tables[:5]:
                if isinstance(table, dict):
                    table_name = table.get('table_name', 'Unknown')
                    logger.info(f"     - {table_name}")
            # Format relationships, contexts, metrics, and insights with proper string conversion
            relationships_str = str(relationships)[:200] + "..." if relationships else "Not provided"
            contexts_str = str(contexts)[:200] + "..." if contexts else "Not provided"
            metrics_str = f"{len(metrics)} metrics" if isinstance(metrics, list) and metrics else (str(metrics)[:200] + "..." if metrics else "Not provided")
            insights_str = str(insights)[:200] + "..." if insights else "Not provided"
            
            logger.info(f"   Relationships: {relationships_str}")
            logger.info(f"   Contexts: {contexts_str}")
            logger.info(f"   Metrics: {metrics_str}")
            if isinstance(metrics, list) and metrics:
                for metric in metrics[:3]:
                    if isinstance(metric, dict):
                        metric_name = metric.get('metric_name', 'Unknown')
                        logger.info(f"     - {metric_name}")
            logger.info(f"   Insights: {insights_str}")
        else:
            logger.info("   Summary: Not generated")
        
        # Metrics Retrieved
        metrics_retrieved = result.get("final_result", {}).get("metrics_retrieved", [])
        if metrics_retrieved:
            logger.info("")
            logger.info("6. Metrics Retrieved:")
            logger.info(f"   Total Metrics: {len(metrics_retrieved)}")
            for metric in metrics_retrieved[:5]:
                if isinstance(metric, dict):
                    metric_name = metric.get('metric_name') or metric.get('name', 'Unknown')
                    source = metric.get('source', 'N/A')
                    logger.info(f"     - {metric_name} (source: {source})")
        
        # Final Result Summary
        final_result = result.get("final_result", {})
        if final_result:
            logger.info("")
            logger.info("=" * 80)
            logger.info("Final Result Summary")
            logger.info("=" * 80)
            curated_tables_final = final_result.get('tables_found', [])
            # Normalize curated tables
            curated_tables_final_normalized = [t for t in curated_tables_final if isinstance(t, dict)]
            logger.info(f"Curated Tables: {len(curated_tables_final_normalized)}")
            logger.info(f"Contexts Retrieved: {len(final_result.get('contexts_retrieved', []))}")
            logger.info(f"Edges Discovered: {len(final_result.get('edges_discovered', []))}")
            logger.info(f"Summary: {'Generated' if final_result.get('summary') else 'Not generated'}")
        
        # MDL Reasoning Graph Test Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("MDL Reasoning Graph Test Summary")
        logger.info("=" * 80)
        logger.info(f"✓ Generic Breakdown: Query type '{generic_breakdown.get('query_type', 'unknown')}', {len(generic_breakdown.get('identified_entities', []))} entities identified")
        
        # Normalize curated_tables_info for summary
        curated_tables_info_normalized = [t for t in curated_tables_info if isinstance(t, dict)]
        if curated_tables_info_normalized:
            logger.info(f"✓ MDL Table Curation: {len(curated_tables_info_normalized)} curated tables (scored and pruned)")
        
        contextual_plan = result.get("contextual_plan", {})
        if contextual_plan:
            table_edges = contextual_plan.get('table_edges', [])
            # Normalize table_edges
            table_edges_normalized = [e for e in table_edges if isinstance(e, dict)]
            logger.info(f"✓ Contextual Planning: {len(table_edges_normalized)} relevant edges identified for curated tables")
        
        logger.info(f"✓ Edge-Based Retrieval: {len(contexts_retrieved)} contexts, {len(edges_discovered)} edges retrieved")
        
        if summary:
            logger.info(f"✓ Summary: Generated with answer and insights")
        
        # Note about LLM response logging
        logger.info("")
        logger.info("=" * 80)
        logger.info("LLM Response Logging")
        logger.info("=" * 80)
        logger.info("Full LLM responses (NO TRUNCATION) are logged at each step:")
        logger.info("  - GenericContextBreakdownNode: Full LLM Prompt and Response")
        logger.info("  - MDLTableCurationNode: Full LLM Prompt and Response (fetches table schemas, scores/prunes tables)")
        logger.info("  - MDLContextualPlannerNode: Full LLM Prompt and Response (identifies relevant edges for curated tables)")
        logger.info("  - MDLSummaryNode: Full LLM Prompt and Response (generates final summary)")
        logger.info("Check the logs above for complete LLM interactions at each step.")
        logger.info("=" * 80)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ Test completed successfully")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
        raise


async def run_batch_tests(model_name: str = "gpt-4o-mini"):
    """Run batch tests with predefined queries (same as tests/test_mdl_reasoning_graph.py)"""
    logger.info("=" * 80)
    logger.info("Running Batch Tests for MDL Reasoning and Planning Graph")
    logger.info("=" * 80)
    
    # Predefined test queries - all use Snyk as project/product
    test_queries = [
        {
            "user_question": "What tables are related to user access request and their soc2 compliance controls in Snyk?",
            "product_name": "Snyk"  # Default project/product for all purposes
        }
    ]
    
    """
    ,
        {
            "user_question": "What compliance controls are relevant to the AccessRequest table?",
            "product_name": "Snyk"  # Default project/product for all purposes
        }
    """
    for i, test_query in enumerate(test_queries, 1):
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"Batch Test {i}/{len(test_queries)}: {test_query['user_question']}")
        logger.info("=" * 80)
        
        await test_graph(
            user_question=test_query["user_question"],
            product_name=test_query.get("product_name"),
            model_name=model_name,
            actor=test_query.get("actor"),
            project_id=test_query.get("project_id")
        )
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("All batch tests completed")
    logger.info("=" * 80)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Test MDL Reasoning and Planning Graph",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--question",
        type=str,
        default=None,
        help="User question to test (required unless --batch is specified)"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch tests with predefined queries (ignores --question and --product-name)"
    )
    
    parser.add_argument(
        "--product-name",
        type=str,
        default="Snyk",
        help="Product name (default: Snyk)"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="LLM model name (default: gpt-4o-mini)"
    )
    
    parser.add_argument(
        "--actor",
        type=str,
        default=None,
        help="Actor making the request (e.g., 'Data Engineer', 'Compliance Officer') - summary will be written for this actor"
    )
    
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="Project ID for metrics retrieval (defaults to product_name if not specified)"
    )
    
    parser.add_argument(
        "--test-retrieval-only",
        action="store_true",
        help="Test retrieval only without running the full graph"
    )
    
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results to retrieve (default: 10, only used with --test-retrieval-only)"
    )
    
    args = parser.parse_args()
    
    # Check for required settings using get_settings()
    from app.core.settings import get_settings
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set in settings. Please set it in .env file or environment variables.")
        return 1
    
    # Run test
    if args.test_retrieval_only:
        # Test retrieval only
        if not args.question:
            parser.error("--question is required with --test-retrieval-only")
        project_id = args.project_id or args.product_name or "Snyk"
        asyncio.run(test_retrieval_only(
            user_question=args.question,
            project_id=project_id,
            top_k=args.top_k
        ))
    elif args.batch:
        # Run batch tests
        asyncio.run(run_batch_tests(model_name=args.model))
    else:
        # Run single query
        if not args.question:
            parser.error("--question is required unless --batch is specified")
        asyncio.run(test_graph(
            user_question=args.question,
            product_name=args.product_name,
            model_name=args.model,
            actor=args.actor,
            project_id=args.project_id
        ))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

