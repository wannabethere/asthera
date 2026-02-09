"""
Integration Test for Contextual Assistants

This test demonstrates the full capabilities of contextual assistants:
1. Setting up contextual assistant factory
2. Creating and registering assistants
3. Testing full workflow: Intent → Context Retrieval → Reasoning → Q&A/Executor → Writer → Finalize
4. Testing different actor types
5. Testing different intents (question vs execution)
6. Demonstrating writer decision-making (summary vs return_result)
7. Testing with streaming service integration

Prerequisites:
- PostgreSQL database with tables created (see migrations/)
- Vector store (ChromaDB or Qdrant) with existing data (run test_integration_document_ingestion.py first)
- OPENAI_API_KEY environment variable must be set
- Data should already be stored from previous ingestion test

Note: This test uses the unified vector store client from dependencies.py, which supports
both ChromaDB and Qdrant. The vector store type is configured via VECTOR_STORE_TYPE environment variable.

IMPORTANT: Test Data vs Indexed Data
------------------------------------
This test expects data to be indexed from indexing_preview/ directory OR created by
test_integration_document_ingestion.py (which uses synthetic test data from test_data.py).

The test_data.py contains sample HIPAA/SOC2 controls, but the actual indexed data in
indexing_preview/ comes from real sources (policy PDFs, database schemas, etc.).

See tests/TEST_DATA_VS_INDEXED_DATA.md for more details about this discrepancy.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncpg
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

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
    ContextualGraphReasoningPipeline,
    create_contextual_reasoning_assembly,
    PipelineAssembly,
    PipelineStep,
    PipelineAssemblyConfig,
    PipelineExecutionMode
)
from app.assistants import (
    create_contextual_assistant_factory,
    ActorType
)
from app.streams.graph_registry import get_registry
from app.streams.streaming_service import GraphStreamingService
from tests.test_indexed_data_loader import get_indexed_data_loader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContextualAssistantIntegrationTest:
    """Integration test for contextual assistants"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_pool: asyncpg.Pool = None
        self.vector_store_client = None  # VectorStoreClient (supports ChromaDB, Qdrant, etc.)
        self.chroma_client = None  # For backward compatibility if needed
        self.embeddings: OpenAIEmbeddings = None
        self.llm: ChatOpenAI = None
        self.contextual_graph_service: ContextualGraphService = None
        self.retrieval_pipeline: ContextualGraphRetrievalPipeline = None
        self.reasoning_pipeline: ContextualGraphReasoningPipeline = None
        self.assistant_factory = None
        self.streaming_service: GraphStreamingService = None
        
        # Indexed data loader
        self.indexed_data_loader = get_indexed_data_loader()
        self.indexed_contexts: List[str] = []
        self.indexed_context_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Test results storage
        self.test_results: List[Dict[str, Any]] = []
    
    def _get_graph_config(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get LangGraph config with thread_id for checkpointer.
        
        Args:
            session_id: Optional session ID (auto-generated if None)
            
        Returns:
            Config dictionary with configurable.thread_id
        """
        import uuid
        thread_id = session_id or str(uuid.uuid4())
        return {"configurable": {"thread_id": thread_id}}
    
    async def setup(self):
        """Set up database and service connections"""
        logger.info("=" * 80)
        logger.info("Setting up Contextual Assistant Integration Test")
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
        self.vector_store_client = await get_vector_store_client(embeddings_model=self.embeddings)
        logger.info(f"Vector store client initialized: {type(self.vector_store_client).__name__}")
        
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
        # (Some code might still reference it, but it's not required for ContextualGraphService)
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
        
        # Initialize Assistant Factory
        logger.info("Initializing Assistant Factory...")
        registry = get_registry()
        self.assistant_factory = create_contextual_assistant_factory(
            contextual_graph_service=self.contextual_graph_service,
            retrieval_pipeline=self.retrieval_pipeline,
            reasoning_pipeline=self.reasoning_pipeline,
            graph_registry=registry,
            llm=self.llm,
            model_name=self.settings.LLM_MODEL
        )
        logger.info("Assistant Factory initialized")
        
        # Create pipeline assembly for demonstration
        logger.info("Creating pipeline assembly...")
        self.pipeline_assembly = create_contextual_reasoning_assembly(
            retrieval_pipeline=self.retrieval_pipeline,
            reasoning_pipeline=self.reasoning_pipeline,
            assembly_id="demo_assembly"
        )
        await self.pipeline_assembly.initialize()
        logger.info("Pipeline Assembly initialized")
        
        # Initialize Streaming Service
        logger.info("Initializing Streaming Service...")
        self.streaming_service = GraphStreamingService(registry=registry)
        logger.info("Streaming Service initialized")
        
        # Verify indexed collections have data
        await self._verify_indexed_collections()
        
        # Discover indexed data
        logger.info("Discovering indexed data from indexing_preview/...")
        indexed_data = self.indexed_data_loader.discover_indexed_data()
        self.indexed_contexts = indexed_data["contexts"]
        self.indexed_context_metadata = indexed_data["context_metadata"]
        
        logger.info(f"Found {len(self.indexed_contexts)} indexed contexts")
        if self.indexed_contexts:
            logger.info("Sample contexts:")
            for ctx_id in self.indexed_contexts[:3]:
                metadata = self.indexed_context_metadata.get(ctx_id, {})
                logger.info(f"  - {ctx_id} ({metadata.get('extraction_type', 'unknown')})")
    
    async def _verify_indexed_collections(self):
        """Verify that indexed collections have data based on ingest_preview_files.py mappings."""
        if not hasattr(self.vector_store_client, 'client'):
            return
        
        try:
            chroma_client = self.vector_store_client.client
            
            # Collections based on CONTENT_TYPE_TO_STORE mapping
            content_type_collections = [
                "comprehensive_index_table_definitions",
                "comprehensive_index_table_descriptions",
                "comprehensive_index_column_definitions",
                "comprehensive_index_schema_descriptions",
                "comprehensive_index_risk_controls",
                "comprehensive_index_compliance_controls",
            ]
            
            # Collections based on EXTRACTION_TYPE_TO_POLICY_STORE mapping
            policy_collections = [
                "comprehensive_index_policy_context",
                "comprehensive_index_policy_entities",
                "comprehensive_index_policy_requirements",
                "comprehensive_index_policy_documents",
                "comprehensive_index_policy_evidence",
                "comprehensive_index_policy_fields",
            ]
            
            expected_collections = content_type_collections + policy_collections
            
            logger.info("=" * 80)
            logger.info("Verifying indexed collections...")
            logger.info(f"ChromaDB path: {os.environ.get('CHROMA_STORE_PATH', 'not set')}")
            logger.info("=" * 80)
            
            total_docs = 0
            for collection_name in expected_collections:
                try:
                    collection = chroma_client.get_collection(collection_name)
                    count = collection.count()
                    total_docs += count
                    status = "✓" if count > 0 else "✗ (empty)"
                    logger.info(f"  {status} '{collection_name}': {count} documents")
                except Exception:
                    logger.warning(f"  ✗ '{collection_name}': collection does not exist")
            
            logger.info(f"Total documents across all collections: {total_docs}")
            logger.info("=" * 80)
            
            if total_docs == 0:
                logger.warning("")
                logger.warning("WARNING: No indexed data found!")
                logger.warning("To index data, run:")
                logger.warning("  export CHROMA_STORE_PATH=/Users/sameermangalampalli/data/chroma_db")
                logger.warning("  export CHROMA_USE_LOCAL=true")
                logger.warning("  python -m indexing_cli.ingest_preview_files \\")
                logger.warning("    --preview-dir indexing_preview \\")
                logger.warning("    --collection-prefix comprehensive_index")
                logger.warning("")
        except Exception as e:
            logger.warning(f"Could not verify collections: {str(e)}")
    
    async def test_create_and_register_assistant(self):
        """Test 1: Create and register a contextual assistant"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Create and Register Assistant")
        logger.info("=" * 80)
        
        try:
            graph_config = self.assistant_factory.create_and_register_assistant(
                assistant_id="demo_assistant",
                name="Demo Contextual Assistant",
                description="Demo assistant for testing contextual reasoning capabilities",
                use_checkpointing=True,
                set_as_default=True
            )
            
            logger.info(f"✓ Assistant created and registered")
            logger.info(f"  Assistant ID: demo_assistant")
            logger.info(f"  Graph ID: {graph_config.graph_id}")
            logger.info(f"  Name: {graph_config.name}")
            
            # Verify registration
            registry = get_registry()
            assistant = registry.get_assistant("demo_assistant")
            if assistant:
                logger.info(f"✓ Assistant verified in registry")
                logger.info(f"  Graphs registered: {len(assistant.graphs)}")
                logger.info(f"  Default graph: {assistant.default_graph_id}")
            else:
                logger.error("✗ Assistant not found in registry")
            
            self.test_results.append({
                "test": "create_assistant",
                "success": True,
                "assistant_id": "demo_assistant",
                "graph_id": graph_config.graph_id
            })
            
        except Exception as e:
            logger.error(f"✗ Failed to create assistant: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "create_assistant",
                "success": False,
                "error": str(e)
            })
    
    async def test_question_intent_with_executive_actor(self):
        """Test 2: Question intent with executive actor (should use Q&A → Writer)"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: Question Intent with Executive Actor")
        logger.info("=" * 80)
        
        # Use a query that should match indexed policy/compliance data
        query = "What access control measures and security policies should I prioritize for compliance?"
        
        try:
            registry = get_registry()
            graph_config = registry.get_assistant_graph("demo_assistant")
            
            if not graph_config:
                logger.error("✗ Assistant graph not found")
                return
            
            logger.info(f"\nQuery: {query}")
            logger.info(f"Actor Type: executive")
            logger.info(f"Expected Flow: Intent → Context → Reasoning → Q&A → Writer → Finalize")
            
            # Invoke graph
            result = await graph_config.graph.ainvoke(
                {
                    "query": query,
                    "actor_type": "executive",
                    "user_context": {
                        "filters": {
                            "domain": "compliance"
                        }
                    }
                },
                config=self._get_graph_config("test_executive_session")
            )
            
            # Analyze results
            intent = result.get("intent", "unknown")
            qa_answer = result.get("qa_answer", "")
            written_content = result.get("written_content", "")
            writer_decision = result.get("writer_decision", "")
            final_answer = result.get("final_answer", "")
            
            logger.info(f"\n✓ Graph execution completed")
            logger.info(f"  Intent: {intent}")
            logger.info(f"  Writer Decision: {writer_decision}")
            logger.info(f"  Has Q&A Answer: {bool(qa_answer)}")
            logger.info(f"  Has Written Content: {bool(written_content)}")
            
            if qa_answer:
                logger.info(f"\n  Q&A Answer Preview:\n  {qa_answer[:200]}...")
            
            if written_content:
                logger.info(f"\n  Written Content Preview:\n  {written_content[:200]}...")
            
            if final_answer:
                logger.info(f"\n  Final Answer Preview:\n  {final_answer[:200]}...")
            
            # Verify workflow
            if intent == "question" and qa_answer and written_content:
                logger.info(f"\n✓ Workflow verified: Question → Q&A → Writer → Finalize")
            else:
                logger.warning(f"\n⚠ Workflow may not have completed as expected")
            
            self.test_results.append({
                "test": "question_intent_executive",
                "success": True,
                "intent": intent,
                "writer_decision": writer_decision,
                "has_qa": bool(qa_answer),
                "has_writer": bool(written_content)
            })
            
        except Exception as e:
            logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "question_intent_executive",
                "success": False,
                "error": str(e)
            })
    
    async def test_question_intent_with_compliance_officer_actor(self):
        """Test 3: Question intent with compliance officer actor (detailed response)"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: Question Intent with Compliance Officer Actor")
        logger.info("=" * 80)
        
        # Use a query that should match indexed policy/compliance data
        query = "What are the specific requirements for access control reviews and security policies?"
        
        try:
            registry = get_registry()
            graph_config = registry.get_assistant_graph("demo_assistant")
            
            if not graph_config:
                logger.error("✗ Assistant graph not found")
                return
            
            logger.info(f"\nQuery: {query}")
            logger.info(f"Actor Type: compliance_officer")
            logger.info(f"Expected: Detailed, regulatory-focused response")
            
            result = await graph_config.graph.ainvoke(
                {
                    "query": query,
                    "actor_type": "compliance_officer",
                    "user_context": {
                        "filters": {
                            "domain": "compliance"
                        }
                    }
                },
                config=self._get_graph_config("test_compliance_officer_session")
            )
            
            intent = result.get("intent", "unknown")
            final_answer = result.get("final_answer", "")
            writer_decision = result.get("writer_decision", "")
            
            logger.info(f"\n✓ Graph execution completed")
            logger.info(f"  Intent: {intent}")
            logger.info(f"  Writer Decision: {writer_decision}")
            
            if final_answer:
                logger.info(f"\n  Final Answer (first 300 chars):\n  {final_answer[:300]}...")
                logger.info(f"  Answer Length: {len(final_answer)} characters")
            
            self.test_results.append({
                "test": "question_intent_compliance_officer",
                "success": True,
                "intent": intent,
                "writer_decision": writer_decision,
                "answer_length": len(final_answer) if final_answer else 0
            })
            
        except Exception as e:
            logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "question_intent_compliance_officer",
                "success": False,
                "error": str(e)
            })
    
    async def test_execution_intent_with_data_scientist_actor(self):
        """Test 4: Execution intent with data scientist actor (should use Executor → Writer)"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 4: Execution Intent with Data Scientist Actor")
        logger.info("=" * 80)
        
        query = "Analyze the risk scores for all access control controls and generate a prioritized list"
        
        try:
            registry = get_registry()
            graph_config = registry.get_assistant_graph("demo_assistant")
            
            if not graph_config:
                logger.error("✗ Assistant graph not found")
                return
            
            logger.info(f"\nQuery: {query}")
            logger.info(f"Actor Type: data_scientist")
            logger.info(f"Expected Flow: Intent → Context → Reasoning → Executor → Writer → Finalize")
            
            result = await graph_config.graph.ainvoke(
                {
                    "query": query,
                    "actor_type": "data_scientist",
                    "user_context": {
                        "filters": {
                            "domain": "compliance"
                        }
                    }
                },
                config=self._get_graph_config("test_data_scientist_session")
            )
            
            intent = result.get("intent", "unknown")
            executor_output = result.get("executor_output", "")
            executor_actions = result.get("executor_actions", [])
            written_content = result.get("written_content", "")
            writer_decision = result.get("writer_decision", "")
            final_answer = result.get("final_answer", "")
            
            logger.info(f"\n✓ Graph execution completed")
            logger.info(f"  Intent: {intent}")
            logger.info(f"  Executor Actions: {len(executor_actions)}")
            logger.info(f"  Writer Decision: {writer_decision}")
            logger.info(f"  Has Executor Output: {bool(executor_output)}")
            logger.info(f"  Has Written Content: {bool(written_content)}")
            
            if executor_actions:
                logger.info(f"\n  Executor Actions:")
                for i, action in enumerate(executor_actions[:3], 1):
                    logger.info(f"    {i}. {action}")
            
            if executor_output:
                logger.info(f"\n  Executor Output Preview:\n  {executor_output[:200]}...")
            
            if final_answer:
                logger.info(f"\n  Final Answer Preview:\n  {final_answer[:200]}...")
            
            # Verify workflow
            if intent == "execution" and executor_output and written_content:
                logger.info(f"\n✓ Workflow verified: Execution → Executor → Writer → Finalize")
            else:
                logger.warning(f"\n⚠ Workflow may not have completed as expected")
            
            self.test_results.append({
                "test": "execution_intent_data_scientist",
                "success": True,
                "intent": intent,
                "executor_actions_count": len(executor_actions),
                "writer_decision": writer_decision
            })
            
        except Exception as e:
            logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "execution_intent_data_scientist",
                "success": False,
                "error": str(e)
            })
    
    async def test_writer_decision_making(self):
        """Test 5: Test writer's decision-making (summary vs return_result)"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 5: Writer Decision-Making")
        logger.info("=" * 80)
        
        # Test case 1: Simple question (should return_result)
        logger.info("\n--- Test 5.1: Simple question (expected: return_result) ---")
        simple_query = "What is HIPAA?"
        
        try:
            registry = get_registry()
            graph_config = registry.get_assistant_graph("demo_assistant")
            
            if not graph_config:
                logger.error("✗ Assistant graph not found")
                return
            
            result1 = await graph_config.graph.ainvoke(
                {
                    "query": simple_query,
                    "actor_type": "executive"
                },
                config=self._get_graph_config("test_writer_simple_session")
            )
            
            writer_decision1 = result1.get("writer_decision", "")
            logger.info(f"  Query: {simple_query}")
            logger.info(f"  Writer Decision: {writer_decision1}")
            
            # Test case 2: Complex analysis (should summary)
            logger.info("\n--- Test 5.2: Complex analysis (expected: summary) ---")
            complex_query = "Analyze all access control requirements, evidence types, and measurements for healthcare organizations preparing for HIPAA audit, including risk scores and implementation recommendations"
            
            result2 = await graph_config.graph.ainvoke(
                {
                    "query": complex_query,
                    "actor_type": "compliance_officer"
                },
                config=self._get_graph_config("test_writer_complex_session")
            )
            
            writer_decision2 = result2.get("writer_decision", "")
            logger.info(f"  Query: {complex_query[:80]}...")
            logger.info(f"  Writer Decision: {writer_decision2}")
            
            logger.info(f"\n✓ Decision-making test completed")
            logger.info(f"  Simple query decision: {writer_decision1}")
            logger.info(f"  Complex query decision: {writer_decision2}")
            
            self.test_results.append({
                "test": "writer_decision_making",
                "success": True,
                "simple_decision": writer_decision1,
                "complex_decision": writer_decision2
            })
            
        except Exception as e:
            logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "writer_decision_making",
                "success": False,
                "error": str(e)
            })
    
    async def test_streaming_execution(self):
        """Test 6: Test streaming execution via streaming service"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 6: Streaming Execution")
        logger.info("=" * 80)
        
        query = "What are the top 3 priority controls for healthcare compliance?"
        
        try:
            logger.info(f"\nQuery: {query}")
            logger.info(f"Streaming execution via GraphStreamingService...")
            
            input_data = {
                    "query": query,
                    "actor_type": "business_analyst",
                    "user_context": {
                        "filters": {
                            "domain": "compliance"
                        }
                    }
            }
            
            session_id = "test_session_123"
            events_received = []
            
            async for event in self.streaming_service.stream_graph_execution(
                assistant_id="demo_assistant",
                graph_id=None,  # Use default
                input_data=input_data,
                session_id=session_id
            ):
                # Parse SSE event
                if "event:" in event:
                    event_type = event.split("event:")[1].split("\n")[0].strip()
                    events_received.append(event_type)
                    
                    # Log key events
                    if "graph_started" in event:
                        logger.info("  ✓ Graph started")
                    elif "node_started" in event:
                        if "data:" in event:
                            node_name = event.split('"node_name":"')[1].split('"')[0] if '"node_name":"' in event else "unknown"
                            logger.info(f"  → Node started: {node_name}")
                    elif "node_completed" in event:
                        if "data:" in event:
                            node_name = event.split('"node_name":"')[1].split('"')[0] if '"node_name":"' in event else "unknown"
                            logger.info(f"  ✓ Node completed: {node_name}")
                    elif "result" in event:
                        logger.info("  ✓ Result received")
                    elif "graph_completed" in event:
                        logger.info("  ✓ Graph completed")
            
            logger.info(f"\n✓ Streaming test completed")
            logger.info(f"  Total events received: {len(events_received)}")
            logger.info(f"  Event types: {set(events_received)}")
            
            self.test_results.append({
                "test": "streaming_execution",
                "success": True,
                "events_count": len(events_received),
                "event_types": list(set(events_received))
            })
            
        except Exception as e:
            logger.error(f"✗ Streaming test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "streaming_execution",
                "success": False,
                "error": str(e)
            })
    
    async def test_pipeline_assembly(self):
        """Test 7: Test pipeline assembly architecture"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 7: Pipeline Assembly Architecture")
        logger.info("=" * 80)
        
        query = "What are the priority controls for compliance and security?"
        
        try:
            logger.info(f"\nQuery: {query}")
            logger.info("Testing pipeline assembly (retrieval → reasoning)")
            
            # Test assembly execution
            result = await self.pipeline_assembly.run(
                inputs={
                    "query": query,
                    "include_all_contexts": True,
                    "top_k": 3,
                    "reasoning_type": "multi_hop",
                    "max_hops": 3
                },
                status_callback=lambda status, data: logger.info(f"  Assembly status: {status}")
            )
            
            if result.get("success"):
                data = result.get("data", {})
                final_state = data.get("final_state", {})
                step_results = data.get("step_results", [])
                
                logger.info(f"\n✓ Assembly execution completed")
                logger.info(f"  Steps executed: {len(step_results)}")
                logger.info(f"  Contexts retrieved: {len(final_state.get('context_ids', []))}")
                logger.info(f"  Has reasoning result: {bool(final_state.get('reasoning_result'))}")
                
                for step_result in step_results:
                    step_name = step_result.get("step_name", "unknown")
                    success = step_result.get("success", False)
                    logger.info(f"    {step_name}: {'✓' if success else '✗'}")
                
                self.test_results.append({
                    "test": "pipeline_assembly",
                    "success": True,
                    "steps_executed": len(step_results),
                    "has_contexts": bool(final_state.get("context_ids")),
                    "has_reasoning": bool(final_state.get("reasoning_result"))
                })
            else:
                logger.error(f"✗ Assembly execution failed: {result.get('error')}")
                self.test_results.append({
                    "test": "pipeline_assembly",
                    "success": False,
                    "error": result.get("error")
                })
                
        except Exception as e:
            logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "pipeline_assembly",
                "success": False,
                "error": str(e)
            })
    
    async def test_data_assistance_assistant(self):
        """Test 8: Test Data Assistance Assistant with project_id csod_risk_attrition"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 8: Data Assistance Assistant")
        logger.info("=" * 80)
        
        query = "What metrics will help for SOC2 Controls from my data source?"
        project_id = "csod_risk_attrition"
        
        try:
            # Import data assistance factory
            from app.agents.data.retrieval_helper import RetrievalHelper
            from app.assistants import create_data_assistance_factory
            
            # Create RetrievalHelper
            retrieval_helper = RetrievalHelper()
            
            # Create factory
            factory = create_data_assistance_factory(
                retrieval_helper=retrieval_helper,
                contextual_graph_service=self.contextual_graph_service,
                retrieval_pipeline=self.retrieval_pipeline,
                reasoning_pipeline=self.reasoning_pipeline,
                graph_registry=get_registry(),
                llm=self.llm,
                model_name=self.settings.LLM_MODEL
            )
            
            # Create and register assistant
            graph_config = factory.create_and_register_assistant(
                assistant_id="test_data_assistance_assistant",
                name="Test Data Assistance Assistant",
                description="Test assistant for data assistance capabilities",
                use_checkpointing=True,
                set_as_default=True
            )
            
            logger.info(f"\nQuery: {query}")
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Expected: Retrieve schemas, metrics, and controls for project")
            
            # Invoke graph
            result = await graph_config.graph.ainvoke(
                {
                    "query": query,
                    "project_id": project_id,
                    "actor_type": "compliance_officer",
                    "user_context": {
                        "framework": "SOC2"
                    }
                },
                config=self._get_graph_config("test_data_assistance_session")
            )
            
            # Analyze results
            data_knowledge = result.get("data_knowledge", {})
            schemas = data_knowledge.get("schemas", [])
            metrics = data_knowledge.get("metrics", [])
            controls = data_knowledge.get("controls", [])
            generated_metrics = result.get("generated_metrics", [])
            final_answer = result.get("final_answer", "")
            
            logger.info(f"\n✓ Graph execution completed")
            logger.info(f"  Schemas retrieved: {len(schemas)}")
            logger.info(f"  Metrics retrieved: {len(metrics)}")
            logger.info(f"  Controls retrieved: {len(controls)}")
            logger.info(f"  Generated metrics: {len(generated_metrics)}")
            logger.info(f"  Framework: {data_knowledge.get('framework', 'None')}")
            
            if schemas:
                logger.info(f"\n  Schema Preview:")
                for i, schema in enumerate(schemas[:3], 1):
                    table_name = schema.get("table_name", "Unknown")
                    logger.info(f"    {i}. {table_name}")
            
            if metrics:
                logger.info(f"\n  Metrics Preview:")
                for i, metric in enumerate(metrics[:3], 1):
                    metric_name = metric.get("metric_name") or metric.get("name", "Unknown")
                    logger.info(f"    {i}. {metric_name}")
            
            if controls:
                logger.info(f"\n  Controls Preview:")
                for i, control in enumerate(controls[:3], 1):
                    if isinstance(control, dict):
                        control_obj = control.get("control") or control
                        control_id = control_obj.get("control_id") or control.get("control_id", "Unknown")
                        logger.info(f"    {i}. {control_id}")
            
            if generated_metrics:
                logger.info(f"\n  Generated Metrics Preview:")
                for i, metric in enumerate(generated_metrics[:3], 1):
                    metric_name = metric.get("name", "Unknown")
                    display_name = metric.get("display_name", metric_name)
                    logger.info(f"    {i}. {display_name} ({metric_name})")
            
            if final_answer:
                logger.info(f"\n  Final Answer Preview:\n  {final_answer[:300]}...")
            
            # Verify workflow
            if schemas or metrics or controls:
                logger.info(f"\n✓ Data assistance workflow verified: Retrieved schemas/metrics/controls")
            else:
                logger.warning(f"\n⚠ No schemas, metrics, or controls retrieved")
            
            self.test_results.append({
                "test": "data_assistance_assistant",
                "success": True,
                "schemas_count": len(schemas),
                "metrics_count": len(metrics),
                "controls_count": len(controls),
                "generated_metrics_count": len(generated_metrics),
                "has_answer": bool(final_answer)
            })
            
        except Exception as e:
            logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "data_assistance_assistant",
                "success": False,
                "error": str(e)
            })
    
    async def test_multiple_actor_types(self):
        """Test 9: Test same query with different actor types"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 9: Multiple Actor Types Comparison")
        logger.info("=" * 80)
        
        query = "What should I prioritize for compliance?"
        actor_types = ["executive", "compliance_officer", "data_scientist", "business_analyst"]
        
        try:
            registry = get_registry()
            graph_config = registry.get_assistant_graph("demo_assistant")
            
            if not graph_config:
                logger.error("✗ Assistant graph not found")
                return
            
            results = {}
            
            for actor_type in actor_types:
                logger.info(f"\n--- Testing with {actor_type} actor ---")
                
                result = await graph_config.graph.ainvoke(
                    {
                        "query": query,
                        "actor_type": actor_type
                    },
                    config=self._get_graph_config(f"test_{actor_type}_session")
                )
                
                final_answer = result.get("final_answer", "")
                writer_decision = result.get("writer_decision", "")
                
                results[actor_type] = {
                    "answer_length": len(final_answer) if final_answer else 0,
                    "writer_decision": writer_decision,
                    "preview": final_answer[:150] + "..." if final_answer else "No answer"
                }
                
                logger.info(f"  Writer Decision: {writer_decision}")
                logger.info(f"  Answer Length: {len(final_answer) if final_answer else 0} chars")
                logger.info(f"  Preview: {final_answer[:100]}..." if final_answer else "  No answer")
            
            logger.info(f"\n✓ Actor type comparison completed")
            logger.info(f"\n  Summary:")
            for actor_type, result_data in results.items():
                logger.info(f"    {actor_type}: {result_data['answer_length']} chars, decision: {result_data['writer_decision']}")
            
            self.test_results.append({
                "test": "multiple_actor_types",
                "success": True,
                "results": results
            })
            
        except Exception as e:
            logger.error(f"✗ Test failed: {str(e)}", exc_info=True)
            self.test_results.append({
                "test": "multiple_actor_types",
                "success": False,
                "error": str(e)
            })
    
    async def display_summary(self):
        """Display test summary"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.get("success", False))
        failed_tests = total_tests - successful_tests
        
        logger.info(f"\nTotal Tests: {total_tests}")
        logger.info(f"Successful: {successful_tests}")
        logger.info(f"Failed: {failed_tests}")
        
        logger.info("\nTest Results:")
        for result in self.test_results:
            status = "✓" if result.get("success", False) else "✗"
            test_name = result.get("test", "unknown")
            logger.info(f"  {status} {test_name}")
            
            if not result.get("success", False):
                error = result.get("error", "Unknown error")
                logger.info(f"    Error: {error}")
        
        logger.info("\n" + "=" * 80)
        logger.info("All tests completed!")
        logger.info("=" * 80)
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("\nCleaning up...")
        if hasattr(self, 'pipeline_assembly') and self.pipeline_assembly:
            await self.pipeline_assembly.cleanup()
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
            await self.test_create_and_register_assistant()
            await self.test_question_intent_with_executive_actor()
            await self.test_question_intent_with_compliance_officer_actor()
            await self.test_execution_intent_with_data_scientist_actor()
            await self.test_writer_decision_making()
            await self.test_streaming_execution()
            await self.test_pipeline_assembly()
            await self.test_data_assistance_assistant()
            await self.test_multiple_actor_types()
            await self.display_summary()
        except Exception as e:
            logger.error(f"Test suite failed with error: {str(e)}", exc_info=True)
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    test = ContextualAssistantIntegrationTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())

