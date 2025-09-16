#!/usr/bin/env python3
"""
Example script showing how to use DocumentIngestionService with proper DomainManager initialization
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

async def main():
    """Example usage of DocumentIngestionService with proper initialization"""
    
    try:
        # Import required modules
        from app.core.settings import ServiceConfig
        from app.core.session_manager import SessionManager
        from app.utils.history import DomainManager
        from app.dataingest.docingest_insights import create_ingestion_service
        from app.service.document_persistence_service import create_document_persistence_service
        
        print("🚀 Initializing Document Ingestion Service...")
        
        # Step 1: Create configuration
        config = ServiceConfig()
        print("✅ ServiceConfig created")
        
        # Step 2: Initialize session manager
        session_manager = SessionManager(config)
        print("✅ SessionManager initialized")
        
        # Step 3: Initialize domain manager (with None for async usage)
        domain_manager = DomainManager(None)
        print("✅ DomainManager initialized")
        
        # Step 4: Create ingestion service
        ingestion_service = create_ingestion_service(
            session_manager=session_manager,
            domain_manager=domain_manager,
            chroma_path="./chroma_db"
        )
        print("✅ DocumentIngestionService created")
        
        # Step 5: Create persistence service
        persistence_service = create_document_persistence_service(
            session_manager=session_manager,
            domain_manager=domain_manager
        )
        print("✅ DocumentPersistenceService created")
        
        # Step 6: Example document ingestion
        print("\n📄 Example: Ingesting a sample document...")
        
        # Create sample content
        sample_content = """
        This is a sample financial report for Q4 2024.
        
        Key Performance Indicators:
        - Revenue Growth: 15% year-over-year
        - Profit Margin: 12.5%
        - Customer Acquisition Cost: $150
        - Monthly Recurring Revenue: $2.5M
        
        Business Terms:
        - ARR: Annual Recurring Revenue
        - CAC: Customer Acquisition Cost
        - LTV: Lifetime Value
        - Churn Rate: Monthly customer churn percentage
        
        The company has shown strong performance across all key metrics.
        """
        
        # Ingest the document
        document, insight = await ingestion_service.ingest_document(
            input_data=sample_content,
            input_type="text",
            source_type="example",
            document_type="financial_report",
            created_by="example_user",
            domain_id="example_domain_123",
            questions=["What are the key financial metrics?", "What business terms are defined?"]
        )
        
        print(f"✅ Document ingested successfully!")
        print(f"   Document ID: {document.id}")
        print(f"   Insight ID: {insight.id}")
        print(f"   Chunk content length: {len(insight.chunk_content) if insight.chunk_content else 0}")
        print(f"   Key phrases count: {len(insight.key_phrases) if insight.key_phrases else 0}")
        
        # Step 7: Example search
        print("\n🔍 Example: Searching documents...")
        
        # Search by content
        search_results = await persistence_service.search_documents(
            query="revenue growth",
            domain_id="example_domain_123",
            limit=5
        )
        
        print(f"✅ Found {len(search_results)} documents matching 'revenue growth'")
        
        # Step 8: Example insights retrieval
        print("\n📊 Example: Retrieving insights...")
        
        insights = await persistence_service.get_insights_by_document_id(str(document.id))
        print(f"✅ Retrieved {len(insights)} insights for document")
        
        if insights:
            latest_insight = insights[0]
            print(f"   Latest insight created at: {latest_insight.created_at}")
            print(f"   Extraction types: {latest_insight.extraction_config.get('extraction_types', []) if latest_insight.extraction_config else []}")
        
        print("\n🎉 All examples completed successfully!")
        print("\nNext steps:")
        print("1. Set up your database using the SQL scripts in the sql/ directory")
        print("2. Configure your environment variables for database connection")
        print("3. Start using the DocumentIngestionService in your application")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("Document Ingestion Service Example")
    print("==================================")
    
    # Run the async main function
    success = asyncio.run(main())
    
    if success:
        print("\n✅ Example completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Example failed!")
        sys.exit(1)
