"""
Complete usage example for Contextual Graph Storage

Demonstrates:
1. Database setup and initialization
2. Creating contexts with LLM extraction
3. Extracting and saving controls with vector documents
4. Querying with all search patterns
"""
import asyncio
import logging
import os
import asyncpg
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from app.storage import (
    ContextualGraphStorageService,
    ContextualGraphQueryEngine,
    ControlExtractor,
    ContextExtractor,
    Control,
    Requirement,
    ComplianceMeasurement
)
from app.services.contextual_graph_storage import ContextDefinition

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Complete example workflow"""
    
    # ============================================================================
    # Step 1: Initialize Services
    # ============================================================================
    logger.info("=== Step 1: Initializing Services ===")
    
    # Get API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return
    
    # PostgreSQL connection
    db_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "compliance_db")
    )
    
    # ChromaDB client
    chroma_client = chromadb.PersistentClient(path="./chroma_contextual_graph")
    
    # Embeddings
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=openai_api_key
    )
    
    # LLM
    llm = ChatOpenAI(model="gpt-4o", openai_api_key=openai_api_key)
    
    # Initialize unified storage service
    storage = ContextualGraphStorageService(
        db_pool=db_pool,
        chroma_client=chroma_client,
        embeddings_model=embeddings
    )
    
    # Initialize query engine
    query_engine = ContextualGraphQueryEngine(
        chroma_client=chroma_client,
        db_pool=db_pool,
        embeddings_model=embeddings,
        llm=llm
    )
    
    # ============================================================================
    # Step 2: Create Context from Description
    # ============================================================================
    logger.info("\n=== Step 2: Creating Context ===")
    
    context_extractor = ContextExtractor(llm=llm)
    
    user_description = """
    We're a healthcare provider with about 2000 employees. We use Epic for 
    our EHR and Workday for HR. We have a HIPAA audit coming up in about 
    3 months and need to make sure our access controls are solid. We've got 
    Okta set up but haven't really configured access reviews properly yet.
    """
    
    context = await context_extractor.extract_context_from_description(
        description=user_description,
        context_id="ctx_healthcare_001"
    )
    
    storage.save_context_definition(context)
    logger.info(f"Created context: {context.context_id}")
    
    # ============================================================================
    # Step 3: Extract and Save Control
    # ============================================================================
    logger.info("\n=== Step 3: Extracting and Saving Control ===")
    
    control_extractor = ControlExtractor(llm=llm)
    
    regulatory_text = """
    HIPAA 164.312(a)(1) - Access Control: Implement technical policies and 
    procedures for electronic information systems that maintain electronic 
    protected health information to allow access only to those persons or 
    software programs that have been granted access rights as specified in 
    § 164.308(a)(4).
    """
    
    extraction = await control_extractor.extract_control_from_text(
        text=regulatory_text,
        framework="HIPAA",
        context_metadata={"context_id": context.context_id}
    )
    
    if extraction:
        # Create control entity
        control = Control(
            control_id=extraction.get("control_id", "HIPAA-AC-001"),
            framework="HIPAA",
            control_name=extraction.get("control_name", "Access Control"),
            control_description=extraction.get("control_description", ""),
            category=extraction.get("category", "access_control")
        )
        
        # Save with vector document
        await storage.save_control_with_vector(
            control=control,
            context_document=extraction.get("context_document", ""),
            context_metadata={"context_id": context.context_id}
        )
        
        logger.info(f"Saved control: {control.control_id}")
    
    # ============================================================================
    # Step 4: Save Measurement
    # ============================================================================
    logger.info("\n=== Step 4: Saving Compliance Measurement ===")
    
    measurement = ComplianceMeasurement(
        control_id="HIPAA-AC-001",
        measured_value=65.0,
        passed=False,
        context_id=context.context_id,
        data_source="Okta access review system",
        measurement_method="automated"
    )
    
    await storage.save_measurement(measurement)
    logger.info("Saved measurement")
    
    # ============================================================================
    # Step 5: Query Patterns
    # ============================================================================
    logger.info("\n=== Step 5: Query Patterns ===")
    
    # Pattern 1: Find relevant contexts
    logger.info("\n5.1 Finding relevant contexts...")
    contexts = query_engine.find_relevant_contexts(
        user_context_description=user_description,
        top_k=3
    )
    
    for ctx in contexts:
        logger.info(f"  - {ctx['context_id']}: Score {ctx['combined_score']:.3f}")
    
    # Pattern 2: Get priority controls
    logger.info("\n5.2 Getting priority controls for context...")
    controls = await query_engine.get_priority_controls_for_context(
        context_id=context.context_id,
        query="access control requirements for audit",
        top_k=5
    )
    
    for ctrl in controls:
        logger.info(f"  - {ctrl['control_id']}")
        logger.info(f"    Risk: {ctrl['context_profile'].get('risk_level', 'N/A')}")
        logger.info(f"    Compliance: {ctrl['current_compliance'].get('avg_compliance_score', 'N/A')}%")
    
    # Pattern 3: Multi-hop reasoning
    logger.info("\n5.3 Multi-hop contextual search...")
    result = await query_engine.multi_hop_contextual_search(
        initial_query="What evidence do I need for access controls?",
        context_id=context.context_id,
        max_hops=3
    )
    
    logger.info("\nReasoning Path:")
    for hop in result["reasoning_path"]:
        logger.info(f"  Hop {hop['hop']}: {hop['entity_type']}")
        logger.info(f"    Entities: {hop['entities_found']}")
    
    logger.info(f"\nFinal Answer:\n{result['final_answer']}")
    
    # ============================================================================
    # Cleanup
    # ============================================================================
    await db_pool.close()
    logger.info("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

