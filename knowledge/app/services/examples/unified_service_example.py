"""
Example usage of Unified Contextual Graph Service

Demonstrates the async service architecture following pipeline pattern
"""
import asyncio
import logging
import os
import asyncpg
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from app.services import ContextualGraphService
from app.services.models import (
    ContextSearchRequest,
    ContextSaveRequest,
    ControlSaveRequest,
    ControlSearchRequest,
    MeasurementSaveRequest,
    MeasurementQueryRequest,
    MultiHopQueryRequest,
    PriorityControlsRequest
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Example of using unified service"""
    
    # ============================================================================
    # Step 1: Initialize Service
    # ============================================================================
    logger.info("=== Step 1: Initializing Service ===")
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY not set")
        return
    
    # Initialize dependencies
    db_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "compliance_db")
    )
    
    chroma_client = chromadb.PersistentClient(path="./chroma_store")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=openai_api_key
    )
    llm = ChatOpenAI(model="gpt-4o", openai_api_key=openai_api_key)
    
    # Create unified service
    service = ContextualGraphService(
        db_pool=db_pool,
        chroma_client=chroma_client,
        embeddings_model=embeddings,
        llm=llm
    )
    
    # ============================================================================
    # Step 2: Search for Contexts
    # ============================================================================
    logger.info("\n=== Step 2: Searching for Contexts ===")
    
    search_request = ContextSearchRequest(
        description="""
        Healthcare provider with 2000 employees. Uses Epic EHR and Workday.
        Preparing for HIPAA audit in 3 months. Has Okta but needs access reviews.
        """,
        top_k=3
    )
    
    search_response = await service.search_contexts(search_request)
    
    if search_response.success:
        logger.info(f"Found {len(search_response.data['contexts'])} contexts")
        for ctx in search_response.data['contexts']:
            logger.info(f"  - {ctx['context_id']}")
    else:
        logger.error(f"Search failed: {search_response.error}")
    
    # ============================================================================
    # Step 3: Save Context
    # ============================================================================
    logger.info("\n=== Step 3: Saving Context ===")
    
    save_request = ContextSaveRequest(
        context_id="ctx_example_001",
        document="""
        Large healthcare organization with developing compliance maturity.
        Operates in United States with 1000-5000 employees. Manages electronic 
        Protected Health Information (ePHI) across Epic EHR, Workday HCM, and 
        PACS systems. Subject to HIPAA and state breach notification laws.
        """,
        industry="healthcare",
        organization_size="large",
        maturity_level="developing",
        regulatory_frameworks=["HIPAA", "state_breach_laws"]
    )
    
    save_response = await service.save_context(save_request)
    
    if save_response.success:
        logger.info(f"Saved context: {save_response.data['context_id']}")
    else:
        logger.error(f"Save failed: {save_response.error}")
    
    # ============================================================================
    # Step 4: Save Control
    # ============================================================================
    logger.info("\n=== Step 4: Saving Control ===")
    
    control_request = ControlSaveRequest(
        control_id="HIPAA-AC-001",
        framework="HIPAA",
        control_name="Access Control to ePHI Systems",
        control_description="Implement technical policies for access control",
        category="access_control",
        context_document="""
        HIPAA Access Control implementation for large healthcare organization.
        
        Implementation: Configure Okta access review workflows. Integrate with
        Epic EHR and Workday. Set up quarterly automated reviews.
        
        Effort: 80 hours
        Cost: $15,000
        Timeline: 12 weeks
        """,
        context_metadata={"context_id": "ctx_example_001"}
    )
    
    control_response = await service.save_control(control_request)
    
    if control_response.success:
        logger.info(f"Saved control: {control_response.data['control_id']}")
    else:
        logger.error(f"Save failed: {control_response.error}")
    
    # ============================================================================
    # Step 5: Save Measurement
    # ============================================================================
    logger.info("\n=== Step 5: Saving Measurement ===")
    
    measurement_request = MeasurementSaveRequest(
        control_id="HIPAA-AC-001",
        measured_value=65.0,
        passed=False,
        context_id="ctx_example_001",
        data_source="Okta access review system"
    )
    
    measurement_response = await service.save_measurement(measurement_request)
    
    if measurement_response.success:
        logger.info(f"Saved measurement: {measurement_response.data['measurement_id']}")
    
    # ============================================================================
    # Step 6: Query Measurements
    # ============================================================================
    logger.info("\n=== Step 6: Querying Measurements ===")
    
    query_request = MeasurementQueryRequest(
        control_id="HIPAA-AC-001",
        context_id="ctx_example_001"
    )
    
    query_response = await service.query_measurements(query_request)
    
    if query_response.success:
        analytics = query_response.data.get("analytics")
        if analytics:
            logger.info(f"Average Compliance: {analytics.get('avg_compliance_score', 'N/A')}%")
            logger.info(f"Trend: {analytics.get('trend', 'N/A')}")
            logger.info(f"Risk Level: {analytics.get('risk_level', 'N/A')}")
    
    # ============================================================================
    # Step 7: Multi-Hop Query
    # ============================================================================
    logger.info("\n=== Step 7: Multi-Hop Query ===")
    
    multi_hop_request = MultiHopQueryRequest(
        query="What evidence do I need for access controls?",
        context_id="ctx_example_001",
        max_hops=3
    )
    
    multi_hop_response = await service.multi_hop_query(multi_hop_request)
    
    if multi_hop_response.success:
        logger.info("\nReasoning Path:")
        for hop in multi_hop_response.data["reasoning_path"]:
            logger.info(f"  Hop {hop['hop']}: {hop['entity_type']}")
            logger.info(f"    Entities: {hop['entities_found']}")
        
        logger.info(f"\nFinal Answer:\n{multi_hop_response.data['final_answer']}")
    
    # ============================================================================
    # Step 8: Get Priority Controls
    # ============================================================================
    logger.info("\n=== Step 8: Getting Priority Controls ===")
    
    priority_request = PriorityControlsRequest(
        context_id="ctx_example_001",
        query="access control requirements for audit",
        top_k=5
    )
    
    priority_response = await service.get_priority_controls(priority_request)
    
    if priority_response.success:
        logger.info(f"Found {len(priority_response.data['controls'])} priority controls")
        for ctrl in priority_response.data['controls']:
            profile = ctrl.get('context_profile', {})
            compliance = ctrl.get('current_compliance', {})
            logger.info(f"  - {ctrl['control_id']}")
            logger.info(f"    Risk: {profile.get('risk_level', 'N/A')}")
            logger.info(f"    Compliance: {compliance.get('avg_compliance_score', 'N/A')}%")
    
    # ============================================================================
    # Step 9: Async Request Processing
    # ============================================================================
    logger.info("\n=== Step 9: Async Request Processing ===")
    
    # Process request asynchronously
    async_request = ControlSearchRequest(
        context_id="ctx_example_001",
        top_k=10
    )
    
    request_id = await service.process_request_async(async_request)
    logger.info(f"Started async request: {request_id}")
    
    # Check status
    status = service.get_request_status(request_id)
    logger.info(f"Status: {status.get('status', 'unknown')}")
    
    # Wait a bit and check again
    await asyncio.sleep(1)
    status = service.get_request_status(request_id)
    logger.info(f"Status after wait: {status.get('status', 'unknown')}")
    
    # ============================================================================
    # Cleanup
    # ============================================================================
    await db_pool.close()
    logger.info("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

