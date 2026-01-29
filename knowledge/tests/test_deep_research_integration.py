"""
CLI script to test Deep Research Integration with Data Assistance Assistant

This test demonstrates the full flow:
1. MDL Context Breakdown (with evidence gathering planning)
2. MDL Reasoning (table curation)
3. Data Knowledge Retrieval
4. Deep Research Integration (with contextual edges)
5. Table-Specific Reasoning
6. Final Q&A with comprehensive summary

Expected Data Structures:
- generic_breakdown: Can be either:
  * ContextBreakdown dataclass from new agents (app.agents.contextual_agents)
  * Dict from legacy ContextBreakdownService
  
  Fields expected (accessible via get_breakdown_field helper):
  - query_type: str (e.g., 'mdl', 'compliance', 'hybrid')
  - identified_entities: List[str]
  - evidence_gathering_required: bool
  - evidence_types_needed: List[str]
  - data_retrieval_plan: List[Dict]
  - metrics_kpis_needed: List[Dict]

Usage:
    # Test evidence gathering question
    python -m tests.test_deep_research_integration \
        --question "why my assets are having a soc 2 control for user access high" \
        --product-name Snyk \
        --project-id Snyk
    
    # Test with different actor
    nohup python -m tests.test_deep_research_integration \
        --question "why my assets are having a soc 2 control for user access high" \
        --product-name Snyk \
        --project-id Snyk \
        --actor "Compliance Officer" > test.out 2>&1 &
    
    # Test other evidence gathering questions
    python -m tests.test_deep_research_integration \
        --question "gather evidence for why access control metrics are failing" \
        --product-name Snyk \
        --project-id Snyk
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
    get_vector_store_client,
    get_embeddings_model,
    get_llm,
    get_database_pool
)
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory
from app.assistants import create_data_assistance_factory
from app.pipelines import (
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline
)
from app.services.contextual_graph_service import ContextualGraphService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_breakdown_field(breakdown, field_name, default=None):
    """
    Helper to extract a field from either a ContextBreakdown dataclass or dict.
    
    Args:
        breakdown: Either a ContextBreakdown dataclass or dict
        field_name: Name of the field to extract
        default: Default value if field not found
        
    Returns:
        Field value or default
    """
    if breakdown is None:
        return default
    
    # Try dataclass attribute access first
    if hasattr(breakdown, field_name):
        return getattr(breakdown, field_name, default)
    
    # Fall back to dict access
    if isinstance(breakdown, dict):
        return breakdown.get(field_name, default)
    
    return default


async def test_deep_research_integration(
    user_question: str,
    product_name: str = "Snyk",
    model_name: str = "gpt-4o",
    actor: Optional[str] = None,
    project_id: Optional[str] = None
):
    """Test deep research integration with data assistance assistant"""
    logger.info("=" * 80)
    logger.info("Deep Research Integration Test")
    logger.info("=" * 80)
    logger.info(f"Question: {user_question}")
    logger.info(f"Product: {product_name}")
    logger.info(f"Project ID: {project_id or product_name}")
    if actor:
        logger.info(f"Actor: {actor}")
    logger.info("")
    
    # Clear settings cache
    clear_settings_cache()
    
    # Get dependencies - use proper vector store based on settings
    logger.info("Initializing dependencies...")
    from app.core.settings import get_settings
    
    settings = get_settings()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.3, model=model_name)
    
    # Get vector store client based on settings (Qdrant by default)
    logger.info(f"Using vector store: {settings.VECTOR_STORE_TYPE}")
    vector_store_client = await get_vector_store_client(
        embeddings_model=embeddings,
        config=settings.get_vector_store_config()
    )
    
    collection_factory = CollectionFactory(
        vector_store_client=vector_store_client,
        embeddings_model=embeddings,
        collection_prefix=""
    )
    
    # Initialize contextual graph storage
    contextual_graph_storage = ContextualGraphStorage(
        vector_store_client=vector_store_client,
        embeddings_model=embeddings,
        collection_prefix="",
        collection_factory=collection_factory
    )
    
    # Initialize contextual graph service
    # Need db_pool for ContextualGraphService - try to get it
    try:
        db_pool = await get_database_pool()
        contextual_graph_service = ContextualGraphService(
            db_pool=db_pool,
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            llm=llm,
            collection_prefix=""
        )
        logger.info("ContextualGraphService created successfully")
    except Exception as e:
        logger.warning(f"Could not create ContextualGraphService with db_pool: {e}")
        # Create minimal service for testing
        contextual_graph_service = None
    
    # Initialize pipelines
    if contextual_graph_service:
        retrieval_pipeline = ContextualGraphRetrievalPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=model_name
        )
        await retrieval_pipeline.initialize()
        
        reasoning_pipeline = ContextualGraphReasoningPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=model_name
        )
        await reasoning_pipeline.initialize()
    else:
        logger.warning("Skipping pipeline initialization - ContextualGraphService not available")
        retrieval_pipeline = None
        reasoning_pipeline = None
    
    # Create retrieval helper with vector_store_client (required for table retrieval via MDL queries)
    try:
        from app.agents.data.retrieval_helper import RetrievalHelper
        logger.info(f"Creating RetrievalHelper with vector_store_client type: {type(vector_store_client)}")
        logger.info(f"Vector store client initialized: {getattr(vector_store_client, '_initialized', False)}")
        retrieval_helper = RetrievalHelper(vector_store_client=vector_store_client)
        logger.info("✅ RetrievalHelper created successfully with vector_store_client")
        logger.info(f"RetrievalHelper has get_table_names_and_schema_contexts: {hasattr(retrieval_helper, 'get_table_names_and_schema_contexts')}")
    except Exception as e:
        logger.error(f"❌ Failed to create RetrievalHelper: {e}")
        import traceback
        logger.error(traceback.format_exc())
        retrieval_helper = None
    
    # Validate required services
    if not contextual_graph_service or not retrieval_pipeline or not reasoning_pipeline:
        logger.error("Required services not available. Cannot create data assistance assistant.")
        logger.error("Please ensure all dependencies are properly initialized.")
        return
    
    # Create data assistance factory
    logger.info("Creating data assistance factory...")
    factory = create_data_assistance_factory(
        retrieval_helper=retrieval_helper,
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        contextual_graph_storage=contextual_graph_storage,
        collection_factory=collection_factory,
        llm=llm,
        model_name=model_name
    )
    
    # Create and register assistant
    logger.info("Creating data assistance assistant with deep research integration...")
    graph_config = factory.create_default_assistant(
        assistant_id="test_data_assistance",
        use_checkpointing=False
    )
    
    graph = graph_config.graph
    
    # Initial state
    initial_state = {
        "query": user_question,
        "project_id": project_id or product_name,
        "user_context": {
            "product_name": product_name,
            "actor": actor or "consultant"
        },
        "actor_type": actor or "consultant",
        "context_ids": [],
        "messages": [],
        "current_node": "start",
        "next_node": None,
        "status": "processing"
    }
    
    try:
        # Run graph
        logger.info("Running data assistance graph with deep research integration...")
        logger.info("")
        result = await graph.ainvoke(initial_state)
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("RESULTS")
        logger.info("=" * 80)
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Current Node: {result.get('current_node')}")
        
        if result.get("error"):
            logger.error(f"Error: {result.get('error')}")
            return
        
        # 1. Generic Breakdown (Evidence Gathering Planning)
        generic_breakdown = result.get("generic_breakdown")
        if generic_breakdown:
            logger.info("")
            logger.info("1. GENERIC BREAKDOWN (Evidence Gathering Planning):")
            
            # Use helper to extract fields from either dataclass or dict
            query_type = get_breakdown_field(generic_breakdown, 'query_type', 'unknown')
            evidence_required = get_breakdown_field(generic_breakdown, 'evidence_gathering_required', False)
            evidence_types = get_breakdown_field(generic_breakdown, 'evidence_types_needed', [])
            data_plan = get_breakdown_field(generic_breakdown, 'data_retrieval_plan', [])
            metrics_needed = get_breakdown_field(generic_breakdown, 'metrics_kpis_needed', [])
            identified_entities = get_breakdown_field(generic_breakdown, 'identified_entities', [])
            
            logger.info(f"   Query Type: {query_type}")
            logger.info(f"   Evidence Gathering Required: {evidence_required}")
            logger.info(f"   Identified Entities: {len(identified_entities)}")
            
            if evidence_required:
                logger.info(f"   Evidence Types Needed: {', '.join(evidence_types) if evidence_types else 'None'}")
                logger.info(f"   Data Retrieval Plan Items: {len(data_plan)}")
                for i, plan_item in enumerate(data_plan[:5], 1):
                    # Handle both string and dict formats
                    if isinstance(plan_item, dict):
                        data_type = plan_item.get('data_type', 'Unknown')
                        category = plan_item.get('category', '')
                        purpose = plan_item.get('purpose', '')[:60]
                        logger.info(f"     {i}. {data_type} - category: {category} - {purpose}")
                    else:
                        logger.info(f"     {i}. {str(plan_item)[:80]}")
                logger.info(f"   Metrics/KPIs Needed: {len(metrics_needed)}")
                for i, metric in enumerate(metrics_needed[:3], 1):
                    # Handle both string and dict formats
                    if isinstance(metric, dict):
                        metric_type = metric.get('metric_type', 'Unknown')
                        purpose = metric.get('purpose', '')[:60]
                        logger.info(f"     {i}. {metric_type} - {purpose}")
                    else:
                        logger.info(f"     {i}. {str(metric)[:80]}")
                
                # Log MDL queries if available (these might be in result root, not in breakdown)
                mdl_queries_planning = result.get('mdl_queries_planning', [])
                mdl_queries = result.get('mdl_queries', [])
                if mdl_queries_planning:
                    logger.info(f"   MDL Queries Generated: {len(mdl_queries_planning)}")
                    for i, query_obj in enumerate(mdl_queries_planning, 1):
                        if isinstance(query_obj, dict):
                            query_text = query_obj.get("query", "")
                            query_type = query_obj.get("type", "")
                            logger.info(f"     {i}. {query_text} (type: {query_type})")
                        else:
                            logger.info(f"     {i}. {query_obj}")
                elif mdl_queries:
                    logger.info(f"   MDL Queries Generated: {len(mdl_queries)}")
                    for i, mdl_query in enumerate(mdl_queries, 1):
                        logger.info(f"     {i}. {mdl_query}")
        
        # 2. MDL Reasoning Results
        curated_tables = result.get("mdl_curated_tables", []) or result.get("suggested_tables", [])
        if curated_tables:
            logger.info("")
            logger.info("2. MDL REASONING (Curated Tables):")
            logger.info(f"   Curated Tables: {len(curated_tables)}")
            for table in curated_tables[:10]:
                if isinstance(table, dict):
                    logger.info(f"     - {table.get('table_name', 'Unknown')} (score: {table.get('relevance_score', 0.0):.2f})")
        
        mdl_edges = result.get("mdl_edges_discovered", [])
        if mdl_edges:
            logger.info(f"   MDL Edges Discovered: {len(mdl_edges)}")
        
        # 3. Deep Research Results
        deep_research = result.get("deep_research_review", {})
        if deep_research:
            logger.info("")
            logger.info("3. DEEP RESEARCH INTEGRATION:")
            logger.info(f"   Contextual Edges Used: {deep_research.get('contextual_edges_used', 0)}")
            
            recommended_features = deep_research.get("recommended_features", [])
            logger.info(f"   Recommended Features/KPIs/Metrics: {len(recommended_features)}")
            for i, feature in enumerate(recommended_features[:5], 1):
                feature_name = feature.get("feature_name", "Unknown")
                feature_type = feature.get("feature_type", "metric")
                question = feature.get("natural_language_question", "")
                logger.info(f"     {i}. {feature_name} ({feature_type})")
                if question:
                    logger.info(f"        Question: {question[:100]}")
            
            evidence_plan = deep_research.get("evidence_gathering_plan", [])
            logger.info(f"   Evidence Gathering Plan Items: {len(evidence_plan)}")
            for i, evidence in enumerate(evidence_plan[:3], 1):
                evidence_type = evidence.get("evidence_type", "Unknown")
                priority = evidence.get("priority", "medium")
                source_tables = evidence.get("source_tables", [])
                logger.info(f"     {i}. {evidence_type} (Priority: {priority})")
                if source_tables:
                    logger.info(f"        Source Tables: {', '.join(source_tables[:3])}")
            
            data_gaps = deep_research.get("data_gaps", [])
            if data_gaps:
                logger.info(f"   Data Gaps Identified: {len(data_gaps)}")
                for i, gap in enumerate(data_gaps[:3], 1):
                    gap_desc = gap.get("description", "") if isinstance(gap, dict) else str(gap)
                    logger.info(f"     {i}. {gap_desc[:100]}")
            
            summary = deep_research.get("summary", "")
            if summary:
                logger.info(f"   Summary: {summary[:200]}...")
        
        # 4. Table-Specific Reasoning
        table_reasoning = result.get("table_specific_reasoning", {})
        if table_reasoning:
            logger.info("")
            logger.info("4. TABLE-SPECIFIC REASONING:")
            table_insights = table_reasoning.get("table_insights", [])
            logger.info(f"   Tables Processed: {len(table_insights)}")
            for insight in table_insights[:5]:
                table_name = insight.get("table_name", "Unknown")
                relevance = insight.get("relevance_to_question", 0.0)
                metrics = insight.get("recommended_metrics", [])
                logger.info(f"     - {table_name} (relevance: {relevance:.2f}, {len(metrics)} metrics)")
        
        # 5. Final Q&A Answer
        qa_answer = result.get("qa_answer", "")
        if qa_answer:
            logger.info("")
            logger.info("5. FINAL Q&A ANSWER:")
            logger.info("=" * 80)
            logger.info(qa_answer)
            logger.info("=" * 80)
        
        # 6. Sources
        qa_sources = result.get("qa_sources", {})
        if qa_sources:
            logger.info("")
            logger.info("6. SOURCES:")
            logger.info(f"   Schemas: {qa_sources.get('schemas_count', 0)}")
            logger.info(f"   Metrics: {qa_sources.get('metrics_count', 0)}")
            logger.info(f"   Generated Metrics: {qa_sources.get('generated_metrics_count', 0)}")
            logger.info(f"   Controls: {qa_sources.get('controls_count', 0)}")
            logger.info(f"   Features: {qa_sources.get('features_count', 0)}")
            logger.info(f"   Deep Research Features: {qa_sources.get('deep_research_features_count', 0)}")
            logger.info(f"   Table Insights: {qa_sources.get('table_insights_count', 0)}")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("Test completed successfully!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error running test: {str(e)}", exc_info=True)
        raise


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test Deep Research Integration")
    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="User question to test"
    )
    parser.add_argument(
        "--product-name",
        type=str,
        default="Snyk",
        help="Product name (default: Snyk)"
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="Project ID (defaults to product-name)"
    )
    parser.add_argument(
        "--actor",
        type=str,
        default=None,
        help="Actor type (e.g., 'Compliance Officer', 'Data Engineer')"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="LLM model name (default: gpt-4o)"
    )
    
    args = parser.parse_args()
    
    await test_deep_research_integration(
        user_question=args.question,
        product_name=args.product_name,
        project_id=args.project_id or args.product_name,
        actor=args.actor,
        model_name=args.model
    )


if __name__ == "__main__":
    asyncio.run(main())
