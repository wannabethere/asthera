"""
Integration Test for Contextual Graph Reasoning Pipeline

This test demonstrates:
1. Using existing data in PostgreSQL and vector store (assumes data is already stored)
2. Testing ContextualGraphRetrievalPipeline - retrieving contexts and creating reasoning plans
3. Testing ContextualGraphReasoningPipeline - performing context-aware reasoning
4. Testing all reasoning types: multi_hop, priority_controls, synthesis, infer_properties
5. Verifying enriched results with all data stores (requirements, evidence, measurements, edges)

Prerequisites:
- PostgreSQL database with tables created (see migrations/)
- Vector store (ChromaDB or Qdrant) with existing indexed data
- OPENAI_API_KEY environment variable must be set

IMPORTANT: Before running this test, you MUST index data using ingest_preview_files.py:
  1. Set the ChromaDB path (tests use: /Users/sameermangalampalli/data/chroma_db):
     export CHROMA_STORE_PATH=/Users/sameermangalampalli/data/chroma_db
     export CHROMA_USE_LOCAL=true
  
  2. Run the ingestion script:
     python -m indexing_cli.ingest_preview_files \
       --preview-dir indexing_preview \
       --collection-prefix comprehensive_index
  
  3. Verify collections have data (the test will check and warn if empty)
     Expected collections based on ingest_preview_files.py mappings:
     - comprehensive_index_table_definitions
     - comprehensive_index_table_descriptions
     - comprehensive_index_column_definitions
     - comprehensive_index_schema_descriptions
     - comprehensive_index_risk_controls
     - comprehensive_index_policy_context
     - comprehensive_index_policy_entities
     - comprehensive_index_policy_requirements
     - comprehensive_index_policy_documents
     - comprehensive_index_policy_evidence
     - comprehensive_index_policy_fields

Note: This test uses the unified vector store client from dependencies.py, which supports
both ChromaDB and Qdrant. The vector store type is configured via VECTOR_STORE_TYPE environment variable.
The test uses collection_prefix="comprehensive_index" to match the indexing services.

IMPORTANT: Test Data vs Indexed Data
------------------------------------
This test expects data from indexing_preview/ directory (table_definitions, policy_documents, etc.),
which is DIFFERENT from the synthetic test data in test_data.py used by other tests.

The test_data.py contains sample HIPAA/SOC2 controls, but the actual indexed data comes from
real sources in indexing_preview/ (policy PDFs, database schemas, etc.).

See tests/TEST_DATA_VS_INDEXED_DATA.md for more details about this discrepancy.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncpg
from langchain_openai import OpenAIEmbeddings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.settings import get_settings, clear_settings_cache
from app.core.dependencies import (
    get_chromadb_client,
    get_database_pool,
    get_embeddings_model,
    get_llm,
    get_vector_store_client,
    get_contextual_graph_service,
    clear_all_caches
)
from app.services.contextual_graph_service import ContextualGraphService
from app.pipelines import (
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline
)
from tests.test_indexed_data_loader import get_indexed_data_loader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContextualGraphReasoningTest:
    """Integration test for contextual graph reasoning"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_pool: asyncpg.Pool = None
        self.vector_store_client = None  # VectorStoreClient (supports ChromaDB, Qdrant, etc.)
        self.chroma_client = None  # For backward compatibility if needed
        self.embeddings: OpenAIEmbeddings = None
        self.llm: Any = None  # LLM from get_llm() dependency injection
        self.contextual_graph_service: ContextualGraphService = None
        self.retrieval_pipeline: ContextualGraphRetrievalPipeline = None
        self.reasoning_pipeline: ContextualGraphReasoningPipeline = None
        
        # Indexed data loader
        self.indexed_data_loader = get_indexed_data_loader()
        self.indexed_contexts: List[str] = []
        self.indexed_context_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Test results storage
        self.retrieved_contexts: List[Dict[str, Any]] = []
        self.reasoning_plans: List[Dict[str, Any]] = []
        self.reasoning_results: List[Dict[str, Any]] = []
    
    async def setup(self):
        """Set up database and service connections"""
        logger.info("=" * 80)
        logger.info("Setting up Contextual Graph Reasoning Test")
        logger.info("=" * 80)
        
        # Check for OpenAI API key
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Set test-specific vector store path
        test_chroma_path = "/Users/sameermangalampalli/data/chroma_db"
        os.environ["CHROMA_STORE_PATH"] = test_chroma_path
        os.environ["CHROMA_USE_LOCAL"] = "true"
        logger.info(f"Using ChromaDB path: {test_chroma_path}")
        
        # Set vector store type (supports chroma or qdrant)
        # Default to chroma for tests, but can be overridden via environment
        if "VECTOR_STORE_TYPE" not in os.environ:
            os.environ["VECTOR_STORE_TYPE"] = "chroma"
        
        # Clear caches
        clear_settings_cache()
        clear_all_caches()
        
        # Initialize PostgreSQL connection pool
        logger.info("Connecting to PostgreSQL...")
        self.db_pool = await get_database_pool()
        logger.info(f"Connected to PostgreSQL: {self.settings.POSTGRES_DB}")
        
        # Initialize embeddings
        logger.info("Initializing OpenAI embeddings...")
        self.embeddings = get_embeddings_model()
        logger.info(f"Embeddings model: {self.settings.EMBEDDING_MODEL}")
        
        # Initialize LLM
        logger.info("Initializing LLM...")
        self.llm = get_llm(
            temperature=self.settings.LLM_TEMPERATURE,
            model=self.settings.LLM_MODEL
        )
        logger.info(f"LLM model: {self.settings.LLM_MODEL}")
        
        # Initialize vector store client (supports ChromaDB, Qdrant, etc.)
        logger.info(f"Initializing vector store client (type: {os.environ.get('VECTOR_STORE_TYPE', 'chroma')})...")
        logger.info(f"Using ChromaDB path: {os.environ.get('CHROMA_STORE_PATH', 'default')}")
        self.vector_store_client = await get_vector_store_client(embeddings_model=self.embeddings)
        logger.info(f"Vector store client initialized: {type(self.vector_store_client).__name__}")
        
        # Verify ChromaDB path if using ChromaDB
        if hasattr(self.vector_store_client, 'client'):
            chroma_client = self.vector_store_client.client
            if hasattr(chroma_client, 'persist_directory'):
                logger.info(f"ChromaDB persist directory: {chroma_client.persist_directory}")
        
        # Check collection counts for debugging - focus on comprehensive_index collections
        if hasattr(self.vector_store_client, 'client'):
            try:
                chroma_client = self.vector_store_client.client
                collections = chroma_client.list_collections()
                logger.info(f"Found {len(collections)} total collections in ChromaDB")
                
                # Check comprehensive_index collections specifically (used by indexing services)
                comprehensive_collections = [c for c in collections if c.name.startswith("comprehensive_index")]
                logger.info(f"Found {len(comprehensive_collections)} collections with 'comprehensive_index' prefix")
                
                total_docs = 0
                for collection in comprehensive_collections:
                    try:
                        count = collection.count()
                        total_docs += count
                        status = "✓" if count > 0 else "✗ (empty)"
                        logger.info(f"  {status} '{collection.name}': {count} documents")
                    except Exception as e:
                        logger.warning(f"  ✗ Collection '{collection.name}': Could not get count ({str(e)})")
                
                if total_docs == 0:
                    logger.warning("=" * 80)
                    logger.warning("WARNING: No documents found in comprehensive_index collections!")
                    logger.warning("This test requires data to be indexed first.")
                    logger.warning("Please run: python -m indexing_cli.ingest_preview_files")
                    logger.warning("Make sure to use the same CHROMA_STORE_PATH and collection_prefix")
                    logger.warning("=" * 80)
                else:
                    logger.info(f"Total documents in comprehensive_index collections: {total_docs}")
                    
                # Also check context_definitions collection
                context_collection_name = "comprehensive_index_context_definitions"
                try:
                    context_collection = chroma_client.get_collection(context_collection_name)
                    context_count = context_collection.count()
                    logger.info(f"Context definitions collection '{context_collection_name}': {context_count} documents")
                except Exception as e:
                    logger.info(f"Context definitions collection '{context_collection_name}' not found (will be created if needed)")
                    
            except Exception as e:
                logger.warning(f"Could not list collections: {str(e)}")
        
        # Initialize Contextual Graph Service using factory function
        # Use "comprehensive_index" prefix to match indexing services (ingest_preview_files.py)
        logger.info("Initializing ContextualGraphService...")
        self.contextual_graph_service = await get_contextual_graph_service(
            vector_store_client=self.vector_store_client,
            db_pool=self.db_pool,
            embeddings_model=self.embeddings,
            llm=self.llm,
            collection_prefix="comprehensive_index"  # Match indexing service prefix
        )
        logger.info("ContextualGraphService initialized with collection_prefix='comprehensive_index'")
        
        # Keep chroma_client for backward compatibility if needed
        if hasattr(self.vector_store_client, 'client'):
            self.chroma_client = self.vector_store_client.client
        else:
            # Fallback: get ChromaDB client if vector store is ChromaDB
            if os.environ.get("VECTOR_STORE_TYPE", "chroma") == "chroma":
                self.chroma_client = get_chromadb_client()
            else:
                self.chroma_client = None
        
        # Initialize Pipelines
        logger.info("Initializing pipelines...")
        self.retrieval_pipeline = ContextualGraphRetrievalPipeline(
            contextual_graph_service=self.contextual_graph_service,
            llm=self.llm,
            model_name=self.settings.LLM_MODEL
        )
        
        self.reasoning_pipeline = ContextualGraphReasoningPipeline(
            contextual_graph_service=self.contextual_graph_service,
            llm=self.llm,
            model_name=self.settings.LLM_MODEL
        )
        
        await self.retrieval_pipeline.initialize()
        await self.reasoning_pipeline.initialize()
        logger.info("Pipelines initialized")
        
        # Discover indexed data
        logger.info("Discovering indexed data from indexing_preview/...")
        indexed_data = self.indexed_data_loader.discover_indexed_data()
        self.indexed_contexts = indexed_data["contexts"]
        self.indexed_context_metadata = indexed_data["context_metadata"]
        
        logger.info(f"Found {len(self.indexed_contexts)} indexed contexts")
        logger.info(f"Content types: {list(indexed_data['content_types'].keys())}")
        
        if self.indexed_contexts:
            logger.info("Sample contexts:")
            for ctx_id in self.indexed_contexts[:5]:
                metadata = self.indexed_context_metadata.get(ctx_id, {})
                logger.info(f"  - {ctx_id} ({metadata.get('extraction_type', 'unknown')})")
        else:
            logger.warning("No indexed contexts found. Tests will query for any available contexts.")
    
    async def _verify_indexed_data_exists(self) -> bool:
        """Verify that indexed data exists in comprehensive_index collections.
        
        Checks collections based on CONTENT_TYPE_TO_STORE and EXTRACTION_TYPE_TO_POLICY_STORE mappings
        from ingest_preview_files.py.
        
        Returns:
            True if data exists, False otherwise
        """
        if not hasattr(self.vector_store_client, 'client'):
            return False
        
        try:
            chroma_client = self.vector_store_client.client
            collections = chroma_client.list_collections()
            
            # Collections based on CONTENT_TYPE_TO_STORE mapping
            content_type_collections = [
                "comprehensive_index_table_definitions",
                "comprehensive_index_table_descriptions",
                "comprehensive_index_column_definitions",
                "comprehensive_index_schema_descriptions",
                "comprehensive_index_risk_controls",
                "comprehensive_index_compliance_controls",
            ]
            
            # Collections based on EXTRACTION_TYPE_TO_POLICY_STORE mapping (for policy_documents)
            policy_collections = [
                "comprehensive_index_policy_context",
                "comprehensive_index_policy_entities",
                "comprehensive_index_policy_requirements",
                "comprehensive_index_policy_documents",
                "comprehensive_index_policy_evidence",
                "comprehensive_index_policy_fields",
            ]
            
            # All expected collections
            expected_collections = content_type_collections + policy_collections
            
            logger.info("=" * 80)
            logger.info("Verifying indexed data in collections...")
            logger.info(f"ChromaDB path: {os.environ.get('CHROMA_STORE_PATH', 'not set')}")
            logger.info("=" * 80)
            
            total_docs = 0
            collections_with_data = []
            collections_empty = []
            collections_missing = []
            
            for collection_name in expected_collections:
                try:
                    collection = chroma_client.get_collection(collection_name)
                    count = collection.count()
                    total_docs += count
                    if count > 0:
                        collections_with_data.append((collection_name, count))
                        logger.info(f"✓ '{collection_name}': {count} documents")
                    else:
                        collections_empty.append(collection_name)
                        logger.warning(f"✗ '{collection_name}': 0 documents (empty)")
                except Exception as e:
                    # Collection doesn't exist
                    collections_missing.append(collection_name)
                    logger.warning(f"✗ '{collection_name}': collection does not exist")
            
            # Summary
            logger.info("")
            logger.info("=" * 80)
            logger.info("Collection Verification Summary")
            logger.info("=" * 80)
            logger.info(f"Collections with data: {len(collections_with_data)}")
            logger.info(f"Empty collections: {len(collections_empty)}")
            logger.info(f"Missing collections: {len(collections_missing)}")
            logger.info(f"Total documents: {total_docs}")
            logger.info("=" * 80)
            
            if total_docs == 0:
                logger.warning("")
                logger.warning("WARNING: No indexed data found in comprehensive_index collections!")
                logger.warning("")
                logger.warning("This test requires data to be indexed first.")
                logger.warning("")
                logger.warning("To index data, run:")
                logger.warning("  export CHROMA_STORE_PATH=/Users/sameermangalampalli/data/chroma_db")
                logger.warning("  export CHROMA_USE_LOCAL=true")
                logger.warning("  python -m indexing_cli.ingest_preview_files \\")
                logger.warning("    --preview-dir indexing_preview \\")
                logger.warning("    --collection-prefix comprehensive_index")
                logger.warning("")
                logger.warning("Expected collections (based on ingest_preview_files.py mappings):")
                logger.warning("  Content Type Collections:")
                for coll in content_type_collections:
                    logger.warning(f"    - {coll}")
                logger.warning("  Policy Collections (from policy_documents):")
                for coll in policy_collections:
                    logger.warning(f"    - {coll}")
                logger.warning("=" * 80)
                return False
            
            return True
        except Exception as e:
            logger.warning(f"Could not verify indexed data: {str(e)}")
            return False
    
    async def test_context_retrieval(self):
        """Test 1: Retrieve contexts and create reasoning plans"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Context Retrieval and Reasoning Plan Creation")
        logger.info("=" * 80)
        
        # Verify indexed data exists
        has_data = await self._verify_indexed_data_exists()
        if not has_data:
            logger.warning("Skipping context retrieval test - no indexed data found")
            return
        
        # Test 1.1: Retrieve contexts using actual indexed data
        # Use a general query that should match indexed policy/compliance contexts
        logger.info("\n--- Test 1.1: Retrieve contexts from indexed data ---")
        query = "access control and compliance requirements"
        logger.info(f"Query: {query}")
        logger.info(f"Will search for contexts in indexed data (found {len(self.indexed_contexts)} contexts)")
        
        result = await self.retrieval_pipeline.run(
            inputs={
                "query": query,
                "include_all_contexts": True,
                "top_k": 5
            }
        )
        
        if result["success"]:
            contexts = result["data"]["contexts"]
            reasoning_plan = result["data"]["reasoning_plan"]
            self.retrieved_contexts = contexts
            
            logger.info(f"✓ Retrieved {len(contexts)} contexts")
            for i, ctx in enumerate(contexts[:3], 1):
                logger.info(f"  {i}. {ctx.get('context_id', 'unknown')} - "
                          f"Priority: {ctx.get('priority_score', 0):.2f}")
                logger.info(f"     Edges: {ctx.get('edges_count', 0)}, "
                          f"Controls: {ctx.get('controls_count', 0)}")
            
            if reasoning_plan:
                steps = reasoning_plan.get("reasoning_steps", [])
                logger.info(f"✓ Created reasoning plan with {len(steps)} steps")
                for i, step in enumerate(steps[:3], 1):
                    logger.info(f"  Step {i}: {step.get('step_type', 'unknown')} - "
                              f"{step.get('description', '')[:60]}...")
        else:
            logger.error(f"✗ Context retrieval failed: {result.get('error')}")
        
        # Test 1.2: Retrieve specific contexts by ID from indexed data
        logger.info("\n--- Test 1.2: Retrieve specific contexts by ID from indexed data ---")
        # Use actual indexed context IDs if available, otherwise use retrieved contexts
        if self.indexed_contexts:
            context_ids = self.indexed_contexts[:2]
            logger.info(f"Using indexed context IDs: {context_ids}")
        elif self.retrieved_contexts:
            context_ids = [ctx.get("context_id") for ctx in self.retrieved_contexts[:2]]
            logger.info(f"Using retrieved context IDs: {context_ids}")
        else:
            logger.warning("No context IDs available, skipping specific context retrieval")
            return
        
        result = await self.retrieval_pipeline.run(
            inputs={
                "query": "compliance and access control context",
                "context_ids": context_ids,
                "top_k": 2
            }
        )
        
        if result["success"]:
            logger.info(f"✓ Retrieved {len(result['data']['contexts'])} specific contexts")
        else:
            logger.error(f"✗ Specific context retrieval failed: {result.get('error')}")
    
    async def test_multi_hop_reasoning(self):
        """Test 2: Multi-hop contextual reasoning with integrated retrieval"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: Multi-Hop Contextual Reasoning (with Retrieval)")
        logger.info("=" * 80)
        
        # Step 1: Retrieve contexts first using retrieval pipeline
        logger.info("\n--- Step 1: Retrieve contexts using retrieval pipeline ---")
        retrieval_result = await self.retrieval_pipeline.run(
            inputs={
                "query": "What evidence do I need for access controls?",
                "include_all_contexts": True,
                "top_k": 3
            }
        )
        
        if not retrieval_result.get("success") or not retrieval_result.get("data", {}).get("contexts"):
            logger.warning("Could not retrieve contexts, trying to use previously retrieved contexts")
            if not self.retrieved_contexts:
                logger.warning("No contexts available, skipping multi-hop reasoning test")
                return
            contexts = self.retrieved_contexts
            reasoning_plan = {}
        else:
            contexts = retrieval_result["data"]["contexts"]
            reasoning_plan = retrieval_result["data"].get("reasoning_plan", {})
            logger.info(f"✓ Retrieved {len(contexts)} contexts for reasoning")
        
        context_id = contexts[0].get("context_id") if contexts else None
        if not context_id:
            logger.warning("No valid context_id found, skipping test")
            return
        
        logger.info(f"\n--- Step 2: Using context: {context_id} for multi-hop reasoning ---")
        
        # Test 2.1: Multi-hop reasoning with reasoning plan from retrieval
        logger.info("\n--- Test 2.1: Multi-hop reasoning query with reasoning plan ---")
        result = await self.reasoning_pipeline.run(
            inputs={
                "query": "What evidence do I need for access controls?",
                "context_id": context_id,
                "reasoning_type": "multi_hop",
                "max_hops": 3,
                "reasoning_plan": reasoning_plan
            }
        )
        
        if result["success"]:
            data = result["data"]
            reasoning_path = data.get("reasoning_path", [])
            final_answer = data.get("final_answer", "")
            
            logger.info(f"✓ Multi-hop reasoning completed")
            logger.info(f"  Reasoning path: {len(reasoning_path)} hops")
            for i, hop in enumerate(reasoning_path, 1):
                logger.info(f"  Hop {i}: {hop.get('entity_type', 'unknown')} - "
                          f"{len(hop.get('entities_found', []))} entities")
                if "entities_enriched" in hop:
                    logger.info(f"    Enriched with: {len(hop['entities_enriched'])} entities")
            
            logger.info(f"\n  Final Answer:\n  {final_answer[:200]}...")
            
            self.reasoning_results.append({
                "type": "multi_hop",
                "result": result
            })
        else:
            logger.error(f"✗ Multi-hop reasoning failed: {result.get('error')}")
    
    async def test_priority_controls(self):
        """Test 3: Priority controls reasoning with integrated retrieval"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: Priority Controls Reasoning (with Retrieval)")
        logger.info("=" * 80)
        
        # Step 1: Retrieve contexts first using retrieval pipeline
        logger.info("\n--- Step 1: Retrieve contexts using retrieval pipeline ---")
        retrieval_result = await self.retrieval_pipeline.run(
            inputs={
                "query": "access control compliance for healthcare organization",
                "include_all_contexts": True,
                "top_k": 3,
                "action_type": "risk_assessment"
            }
        )
        
        if not retrieval_result.get("success") or not retrieval_result.get("data", {}).get("contexts"):
            logger.warning("Could not retrieve contexts, trying to use previously retrieved contexts")
            if not self.retrieved_contexts:
                logger.warning("No contexts available, skipping priority controls test")
                return
            contexts = self.retrieved_contexts
        else:
            contexts = retrieval_result["data"]["contexts"]
            logger.info(f"✓ Retrieved {len(contexts)} contexts for priority controls")
            # Update stored contexts for other tests
            if not self.retrieved_contexts:
                self.retrieved_contexts = contexts
        
        context_id = contexts[0].get("context_id") if contexts else None
        if not context_id:
            logger.warning("No valid context_id found, skipping test")
            return
        
        logger.info(f"\n--- Step 2: Using context: {context_id} for priority controls ---")
        
        # Test 3.1: Get priority controls with all enrichment
        logger.info("\n--- Test 3.1: Get priority controls with all enrichment ---")
        result = await self.reasoning_pipeline.run(
            inputs={
                "query": "access control compliance",
                "context_id": context_id,
                "reasoning_type": "priority_controls",
                "top_k": 5,
                "include_requirements": True,
                "include_evidence": True,
                "include_measurements": True
            }
        )
        
        if result["success"]:
            controls = result["data"].get("controls", [])
            logger.info(f"✓ Retrieved {len(controls)} priority controls")
            
            for i, control_info in enumerate(controls[:3], 1):
                control = control_info.get("control", {})
                if isinstance(control, dict):
                    control_name = control.get("control_name", "Unknown")
                else:
                    control_name = getattr(control, "control_name", "Unknown")
                
                logger.info(f"\n  Control {i}: {control_name}")
                logger.info(f"    Requirements: {control_info.get('requirements_count', 0)}")
                logger.info(f"    Evidence types: {control_info.get('evidence_count', 0)}")
                logger.info(f"    Measurements: {control_info.get('measurements_count', 0)}")
                logger.info(f"    Contextual edges: {control_info.get('edges_count', 0)}")
                
                if "risk_analytics" in control_info:
                    analytics = control_info["risk_analytics"]
                    logger.info(f"    Risk level: {analytics.get('risk_level', 'Unknown')}")
                    logger.info(f"    Risk score: {analytics.get('current_risk_score', 'N/A')}")
            
            self.reasoning_results.append({
                "type": "priority_controls",
                "result": result
            })
        else:
            logger.error(f"✗ Priority controls failed: {result.get('error')}")
    
    async def test_multi_context_synthesis(self):
        """Test 4: Multi-context synthesis with integrated retrieval"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 4: Multi-Context Synthesis (with Retrieval)")
        logger.info("=" * 80)
        
        # Step 1: Retrieve multiple contexts using retrieval pipeline
        logger.info("\n--- Step 1: Retrieve multiple contexts using retrieval pipeline ---")
        retrieval_result = await self.retrieval_pipeline.run(
            inputs={
                "query": "What are the highest-risk controls?",
                "include_all_contexts": True,
                "top_k": 3
            }
        )
        
        if not retrieval_result.get("success") or not retrieval_result.get("data", {}).get("contexts"):
            logger.warning("Could not retrieve contexts, trying to use previously retrieved contexts")
            if len(self.retrieved_contexts) < 2:
                logger.warning("Need at least 2 contexts for synthesis test, skipping")
                return
            contexts = self.retrieved_contexts[:2]
        else:
            contexts = retrieval_result["data"]["contexts"][:2]  # Use top 2
            logger.info(f"✓ Retrieved {len(contexts)} contexts for synthesis")
            # Update stored contexts for other tests
            if not self.retrieved_contexts:
                self.retrieved_contexts = retrieval_result["data"]["contexts"]
        
        if len(contexts) < 2:
            logger.warning("Need at least 2 contexts for synthesis test, skipping")
            return
        
        logger.info(f"\n--- Step 2: Synthesizing across {len(contexts)} contexts ---")
        for i, ctx in enumerate(contexts, 1):
            logger.info(f"  Context {i}: {ctx.get('context_id', 'unknown')} - "
                      f"Priority: {ctx.get('priority_score', 0):.2f}")
        
        # Test 4.1: Multi-context synthesis
        logger.info("\n--- Test 4.1: Synthesize reasoning across contexts ---")
        result = await self.reasoning_pipeline.run(
            inputs={
                "query": "What are the highest-risk controls?",
                "contexts": contexts,
                "reasoning_type": "synthesis",
                "max_hops": 2
            }
        )
        
        if result["success"]:
            synthesis = result["data"].get("synthesis", {})
            logger.info(f"✓ Multi-context synthesis completed")
            
            if synthesis:
                synthesized_answer = synthesis.get("synthesized_answer", "")
                common_patterns = synthesis.get("common_patterns", [])
                context_differences = synthesis.get("context_differences", [])
                
                logger.info(f"\n  Synthesized Answer:\n  {synthesized_answer[:300]}...")
                logger.info(f"\n  Common Patterns: {len(common_patterns)}")
                logger.info(f"  Context Differences: {len(context_differences)}")
            
            self.reasoning_results.append({
                "type": "synthesis",
                "result": result
            })
        else:
            logger.error(f"✗ Multi-context synthesis failed: {result.get('error')}")
    
    async def test_infer_properties(self):
        """Test 5: Infer context properties with integrated retrieval"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 5: Infer Context Properties (with Retrieval)")
        logger.info("=" * 80)
        
        # Step 1: Retrieve context first using retrieval pipeline
        logger.info("\n--- Step 1: Retrieve context using retrieval pipeline ---")
        retrieval_result = await self.retrieval_pipeline.run(
            inputs={
                "query": "healthcare compliance context for risk assessment",
                "include_all_contexts": True,
                "top_k": 1
            }
        )
        
        if not retrieval_result.get("success") or not retrieval_result.get("data", {}).get("contexts"):
            logger.warning("Could not retrieve contexts, trying to use previously retrieved contexts")
            if not self.retrieved_contexts:
                logger.warning("No contexts available, skipping infer properties test")
                return
            context_id = self.retrieved_contexts[0].get("context_id")
        else:
            contexts = retrieval_result["data"]["contexts"]
            context_id = contexts[0].get("context_id") if contexts else None
            logger.info(f"✓ Retrieved context: {context_id}")
            # Update stored contexts for other tests
            if not self.retrieved_contexts:
                self.retrieved_contexts = contexts
        
        if not context_id:
            logger.warning("No valid context_id found, skipping test")
            return
        
        # Step 2: Find a control ID from the database
        logger.info(f"\n--- Step 2: Finding control to infer properties for ---")
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT control_id FROM controls LIMIT 1"
                )
                if row:
                    entity_id = row["control_id"]
                    logger.info(f"✓ Found control: {entity_id}")
                    logger.info(f"\n--- Step 3: Inferring properties for control: {entity_id} in context: {context_id} ---")
                    
                    result = await self.reasoning_pipeline.run(
                        inputs={
                            "entity_id": entity_id,
                            "entity_type": "control",
                            "context_id": context_id,
                            "reasoning_type": "infer_properties"
                        }
                    )
                    
                    if result["success"]:
                        properties = result["data"].get("properties", {})
                        entity_info = result["data"].get("entity_info", {})
                        
                        logger.info(f"✓ Property inference completed")
                        logger.info(f"  Properties inferred: {len(properties)}")
                        for prop_name, prop_value in list(properties.items())[:5]:
                            logger.info(f"    {prop_name}: {prop_value}")
                        
                        if entity_info:
                            logger.info(f"  Entity info includes:")
                            logger.info(f"    Outgoing edges: {len(entity_info.get('outgoing_edges', []))}")
                            logger.info(f"    Incoming edges: {len(entity_info.get('incoming_edges', []))}")
                        
                        self.reasoning_results.append({
                            "type": "infer_properties",
                            "result": result
                        })
                    else:
                        logger.error(f"✗ Property inference failed: {result.get('error')}")
                else:
                    logger.warning("No controls found in database, skipping infer properties test")
        except Exception as e:
            logger.warning(f"Could not query database for control: {str(e)}")
    
    async def test_complete_workflow(self):
        """Test 6: Complete workflow - Retrieval → Reasoning"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 6: Complete Workflow (Retrieval → Reasoning)")
        logger.info("=" * 80)
        
        query = "What access control measures should I prioritize for a healthcare organization preparing for HIPAA audit?"
        
        # Step 1: Retrieve contexts and create reasoning plan
        logger.info("\n--- Step 1: Retrieve contexts and create reasoning plan ---")
        retrieval_result = await self.retrieval_pipeline.run(
            inputs={
                "query": query,
                "include_all_contexts": True,
                "top_k": 3,
                "target_domain": "healthcare",
                "action_type": "risk_assessment"
            }
        )
        
        if not retrieval_result.get("success"):
            logger.error(f"✗ Context retrieval failed: {retrieval_result.get('error')}")
            return
        
        contexts = retrieval_result["data"]["contexts"]
        reasoning_plan = retrieval_result["data"].get("reasoning_plan", {})
        
        logger.info(f"✓ Retrieved {len(contexts)} contexts")
        logger.info(f"✓ Created reasoning plan with {len(reasoning_plan.get('reasoning_steps', []))} steps")
        
        if not contexts:
            logger.warning("No contexts retrieved, cannot proceed with reasoning")
            return
        
        # Step 2: Use reasoning plan for multi-hop reasoning
        logger.info("\n--- Step 2: Use reasoning plan for multi-hop reasoning ---")
        primary_context = contexts[0]
        context_id = primary_context.get("context_id")
        
        reasoning_result = await self.reasoning_pipeline.run(
            inputs={
                "query": query,
                "context_id": context_id,
                "reasoning_type": "multi_hop",
                "max_hops": 3,
                "reasoning_plan": reasoning_plan
            }
        )
        
        if reasoning_result.get("success"):
            logger.info(f"✓ Multi-hop reasoning completed using reasoning plan")
            reasoning_path = reasoning_result["data"].get("reasoning_path", [])
            logger.info(f"  Reasoning path: {len(reasoning_path)} hops")
        else:
            logger.error(f"✗ Reasoning failed: {reasoning_result.get('error')}")
        
        # Step 3: Get priority controls using retrieved context
        logger.info("\n--- Step 3: Get priority controls using retrieved context ---")
        priority_result = await self.reasoning_pipeline.run(
            inputs={
                "query": "access control compliance",
                "context_id": context_id,
                "reasoning_type": "priority_controls",
                "top_k": 3,
                "include_requirements": True,
                "include_evidence": True,
                "include_measurements": True
            }
        )
        
        if priority_result.get("success"):
            controls = priority_result["data"].get("controls", [])
            logger.info(f"✓ Retrieved {len(controls)} priority controls")
            logger.info(f"  Controls enriched with requirements, evidence, and measurements")
        else:
            logger.error(f"✗ Priority controls failed: {priority_result.get('error')}")
        
        # Step 4: Display workflow summary
        logger.info("\n--- Workflow Summary ---")
        logger.info(f"  Query: {query[:80]}...")
        logger.info(f"  Contexts Retrieved: {len(contexts)}")
        logger.info(f"  Reasoning Plan Steps: {len(reasoning_plan.get('reasoning_steps', []))}")
        logger.info(f"  Multi-hop Reasoning: {'✓' if reasoning_result.get('success') else '✗'}")
        logger.info(f"  Priority Controls: {'✓' if priority_result.get('success') else '✗'}")
        
        self.reasoning_results.append({
            "type": "complete_workflow",
            "result": {
                "retrieval": retrieval_result,
                "reasoning": reasoning_result,
                "priority_controls": priority_result
            }
        })
    
    async def test_comprehensive_entity_info(self):
        """Test 7: Get comprehensive entity information with integrated retrieval"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 7: Comprehensive Entity Information (with Retrieval)")
        logger.info("=" * 80)
        
        # Step 1: Retrieve context first using retrieval pipeline
        logger.info("\n--- Step 1: Retrieve context using retrieval pipeline ---")
        retrieval_result = await self.retrieval_pipeline.run(
            inputs={
                "query": "healthcare compliance context",
                "include_all_contexts": True,
                "top_k": 1
            }
        )
        
        if not retrieval_result.get("success") or not retrieval_result.get("data", {}).get("contexts"):
            logger.warning("Could not retrieve contexts, trying to use previously retrieved contexts")
            if not self.retrieved_contexts:
                logger.warning("No contexts available, skipping comprehensive entity info test")
                return
            context_id = self.retrieved_contexts[0].get("context_id")
        else:
            contexts = retrieval_result["data"]["contexts"]
            context_id = contexts[0].get("context_id") if contexts else None
            logger.info(f"✓ Retrieved context: {context_id}")
            # Update stored contexts for other tests
            if not self.retrieved_contexts:
                self.retrieved_contexts = contexts
        
        if not context_id:
            logger.warning("No valid context_id found, skipping test")
            return
        
        # Step 2: Find a control ID from the database
        logger.info(f"\n--- Step 2: Finding control to get comprehensive info for ---")
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT control_id FROM controls LIMIT 1"
                )
                if row:
                    entity_id = row["control_id"]
                    logger.info(f"✓ Found control: {entity_id}")
                    logger.info(f"\n--- Step 3: Getting comprehensive info for: {entity_id} in context: {context_id} ---")
                    
                    entity_info = await self.reasoning_pipeline.agent.get_comprehensive_entity_info(
                        entity_id=entity_id,
                        entity_type="control",
                        context_id=context_id
                    )
                    
                    if entity_info.get("success"):
                        logger.info(f"✓ Comprehensive entity info retrieved")
                        logger.info(f"  Outgoing edges: {len(entity_info.get('outgoing_edges', []))}")
                        logger.info(f"  Incoming edges: {len(entity_info.get('incoming_edges', []))}")
                        logger.info(f"  Requirements: {len(entity_info.get('requirements', []))}")
                        logger.info(f"  Measurements: {len(entity_info.get('measurements', []))}")
                        
                        if "risk_analytics" in entity_info:
                            analytics = entity_info["risk_analytics"]
                            logger.info(f"  Risk analytics: {analytics.get('risk_level', 'N/A')}")
                    else:
                        logger.error(f"✗ Comprehensive entity info failed: {entity_info.get('error')}")
                else:
                    logger.warning("No controls found in database, skipping comprehensive entity info test")
        except Exception as e:
            logger.warning(f"Could not query database for control: {str(e)}")
    
    async def display_summary(self):
        """Display test summary"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"\nContexts Retrieved: {len(self.retrieved_contexts)}")
        logger.info(f"Reasoning Plans Created: {len(self.reasoning_plans)}")
        logger.info(f"Reasoning Results: {len(self.reasoning_results)}")
        
        logger.info("\nReasoning Types Tested:")
        for result in self.reasoning_results:
            logger.info(f"  - {result['type']}: {'✓' if result['result'].get('success') else '✗'}")
        
        logger.info("\n" + "=" * 80)
        logger.info("All tests completed!")
        logger.info("=" * 80)
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("\nCleaning up...")
        if self.retrieval_pipeline:
            await self.retrieval_pipeline.cleanup()
        if self.reasoning_pipeline:
            await self.reasoning_pipeline.cleanup()
        if self.db_pool:
            await self.db_pool.close()
        logger.info("Cleanup complete")
    
    async def run_all_tests(self):
        """Run all tests"""
        try:
            await self.setup()
            await self.test_context_retrieval()
            await self.test_multi_hop_reasoning()
            await self.test_priority_controls()
            await self.test_multi_context_synthesis()
            await self.test_infer_properties()
            await self.test_complete_workflow()
            await self.test_comprehensive_entity_info()
            await self.display_summary()
        except Exception as e:
            logger.error(f"Test failed with error: {str(e)}", exc_info=True)
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    test = ContextualGraphReasoningTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())

