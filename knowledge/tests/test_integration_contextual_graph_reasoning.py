"""
Integration Test for Contextual Graph Reasoning Pipeline

This test demonstrates:
1. Using existing data in PostgreSQL and ChromaDB (assumes data is already stored)
2. Testing ContextualGraphRetrievalPipeline - retrieving contexts and creating reasoning plans
3. Testing ContextualGraphReasoningPipeline - performing context-aware reasoning
4. Testing all reasoning types: multi_hop, priority_controls, synthesis, infer_properties
5. Verifying enriched results with all data stores (requirements, evidence, measurements, edges)

Prerequisites:
- PostgreSQL database with tables created (see migrations/)
- ChromaDB with existing data (run test_integration_document_ingestion.py first)
- OPENAI_API_KEY environment variable must be set
- Data should already be stored from previous ingestion test
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncpg
import chromadb
from langchain_openai import OpenAIEmbeddings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.settings import get_settings, clear_settings_cache
from app.core.dependencies import (
    get_chromadb_client,
    get_database_pool,
    get_embeddings_model,
    get_llm,
    clear_all_caches
)
from app.services.contextual_graph_service import ContextualGraphService
from app.agents.pipelines import (
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline
)
from tests.test_data import (
    HEALTHCARE_CONTEXT_DESCRIPTION,
    TECH_COMPANY_CONTEXT_DESCRIPTION
)

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
        self.chroma_client: chromadb.PersistentClient = None
        self.embeddings: OpenAIEmbeddings = None
        self.llm: Any = None  # LLM from get_llm() dependency injection
        self.contextual_graph_service: ContextualGraphService = None
        self.retrieval_pipeline: ContextualGraphRetrievalPipeline = None
        self.reasoning_pipeline: ContextualGraphReasoningPipeline = None
        
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
        
        # Set test-specific ChromaDB path
        test_chroma_path = "./test_chroma_db"
        os.environ["CHROMA_STORE_PATH"] = test_chroma_path
        os.environ["CHROMA_USE_LOCAL"] = "true"
        
        # Clear caches
        clear_settings_cache()
        clear_all_caches()
        
        # Initialize PostgreSQL connection pool
        logger.info("Connecting to PostgreSQL...")
        self.db_pool = await get_database_pool()
        logger.info(f"Connected to PostgreSQL: {self.settings.POSTGRES_DB}")
        
        # Initialize ChromaDB
        logger.info(f"Initializing ChromaDB at: {test_chroma_path}")
        self.chroma_client = get_chromadb_client()
        logger.info("ChromaDB initialized")
        
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
        
        # Initialize Contextual Graph Service
        logger.info("Initializing ContextualGraphService...")
        self.contextual_graph_service = ContextualGraphService(
            db_pool=self.db_pool,
            chroma_client=self.chroma_client,
            embeddings_model=self.embeddings,
            llm=self.llm
        )
        logger.info("ContextualGraphService initialized")
        
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
    
    async def test_context_retrieval(self):
        """Test 1: Retrieve contexts and create reasoning plans"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Context Retrieval and Reasoning Plan Creation")
        logger.info("=" * 80)
        
        # Test 1.1: Retrieve contexts for healthcare query
        logger.info("\n--- Test 1.1: Retrieve contexts for healthcare compliance ---")
        result = await self.retrieval_pipeline.run(
            inputs={
                "query": "What access control measures should I prioritize for a healthcare organization preparing for HIPAA audit?",
                "include_all_contexts": True,
                "top_k": 5,
                "target_domain": "healthcare"
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
        
        # Test 1.2: Retrieve specific contexts
        logger.info("\n--- Test 1.2: Retrieve specific contexts by ID ---")
        if self.retrieved_contexts:
            context_ids = [ctx.get("context_id") for ctx in self.retrieved_contexts[:2]]
            result = await self.retrieval_pipeline.run(
                inputs={
                    "query": "healthcare compliance context",
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

