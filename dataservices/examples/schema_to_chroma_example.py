#!/usr/bin/env python3
"""
Complete example: Schema Documentation to ChromaDB Storage
Demonstrates the full workflow from generating schema documentation
to storing it in ChromaDB for vector search.
"""

import asyncio
import json
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.agents.schema_manager import (
    LLMSchemaDocumentationGenerator,
    SchemaDocumentationUtils,
    SchemaDocumentationExamples
)
from app.service.models import SchemaInput, ProjectContext
from app.storage.documents import DocumentChromaStore, AsyncDocumentWriter, DuplicatePolicy
from app.agents.indexing.db_schema import DBSchema
import chromadb
from langchain_openai import OpenAIEmbeddings


async def complete_workflow_example():
    """Complete workflow example from schema to ChromaDB storage"""
    
    print("🚀 Complete Schema Documentation to ChromaDB Workflow")
    print("=" * 60)
    
    # Step 1: Get example data
    print("\n📋 Step 1: Loading example data...")
    project_context, ddl_statement, schema_json = (
        SchemaDocumentationExamples.cornerstone_training_example()
    )
    
    # Convert to SchemaInput
    schema_input = SchemaInput(
        table_name=schema_json['table_name'],
        table_description=schema_json.get('description'),
        columns=schema_json['columns'],
        sample_data=schema_json.get('sample_data')
    )
    
    print(f"✅ Loaded schema for table: {schema_input.table_name}")
    
    # Step 2: Generate schema documentation
    print("\n🔄 Step 2: Generating schema documentation...")
    try:
        schema_manager = LLMSchemaDocumentationGenerator()
        documented_table = await schema_manager.document_table_schema(schema_input, project_context)
        print("✅ Schema documentation generated successfully!")
        
        # Show summary
        print(f"  - Table: {documented_table.table_name}")
        print(f"  - Display Name: {documented_table.display_name}")
        print(f"  - Columns: {len(documented_table.columns)}")
        print(f"  - Business Purpose: {documented_table.business_purpose[:100]}...")
        
    except Exception as e:
        print(f"❌ Error generating documentation: {e}")
        return
    
    # Step 3: Convert to MDL format
    print("\n🔄 Step 3: Converting to MDL format...")
    try:
        mdl_json = SchemaDocumentationUtils.documented_table_to_mdl(documented_table, project_context.project_id)
        print("✅ MDL format generated")
        print(f"  - MDL size: {len(mdl_json)} characters")
        
    except Exception as e:
        print(f"❌ Error converting to MDL: {e}")
        return
    
    # Step 4: Convert to ChromaDB documents
    print("\n🔄 Step 4: Converting to ChromaDB documents...")
    try:
        chroma_documents = SchemaDocumentationUtils.documented_table_to_chroma_documents(
            documented_table, project_context.project_id
        )
        print(f"✅ Generated {len(chroma_documents)} ChromaDB documents")
        
        # Show document types
        table_docs = [d for d in chroma_documents if d.metadata.get('documentation_type') == 'table_overview']
        column_docs = [d for d in chroma_documents if d.metadata.get('documentation_type') == 'column_detail']
        print(f"  - Table documents: {len(table_docs)}")
        print(f"  - Column documents: {len(column_docs)}")
        
    except Exception as e:
        print(f"❌ Error converting to ChromaDB documents: {e}")
        return
    
    # Step 5: Initialize ChromaDB (optional - for demonstration)
    print("\n🔄 Step 5: ChromaDB Storage Options...")
    print("Choose storage method:")
    print("1. Direct ChromaDB storage (requires ChromaDB setup)")
    print("2. DBSchema processing (requires full setup)")
    print("3. Show document structure only")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        await store_direct_to_chroma(chroma_documents, project_context.project_id)
    elif choice == "2":
        await process_with_dbschema(mdl_json, project_context.project_id)
    else:
        show_document_structure(chroma_documents)
    
    print("\n✅ Workflow completed!")


async def store_direct_to_chroma(documents, project_id):
    """Store documents directly to ChromaDB"""
    print("\n🔄 Storing directly to ChromaDB...")
    
    try:
        # Initialize ChromaDB (you would normally get these from config)
        print("  - Initializing ChromaDB...")
        persistent_client = chromadb.PersistentClient(path="./chroma_db")
        doc_store = DocumentChromaStore(
            persistent_client=persistent_client,
            collection_name="schema_documentation"
        )
        
        # Create writer
        writer = AsyncDocumentWriter(
            document_store=doc_store,
            policy=DuplicatePolicy.OVERWRITE,
        )
        
        # Store documents
        print("  - Writing documents...")
        write_result = await writer.run(documents=documents)
        print(f"✅ Successfully stored {write_result['documents_written']} documents")
        
        # Show collection info
        collection = doc_store.collection
        count = collection.count()
        print(f"  - Total documents in collection: {count}")
        
    except Exception as e:
        print(f"❌ Error storing to ChromaDB: {e}")
        print("Note: Make sure ChromaDB is properly configured")


async def process_with_dbschema(mdl_json, project_id):
    """Process using DBSchema class"""
    print("\n🔄 Processing with DBSchema...")
    
    try:
        # Initialize components
        print("  - Initializing DBSchema components...")
        persistent_client = chromadb.PersistentClient(path="./chroma_db")
        doc_store = DocumentChromaStore(
            persistent_client=persistent_client,
            collection_name="schema_documentation"
        )
        embeddings = OpenAIEmbeddings()
        
        db_schema = DBSchema(
            document_store=doc_store,
            embedder=embeddings
        )
        
        # Process the MDL
        print("  - Processing MDL...")
        result = await db_schema.run(mdl_json, project_id=project_id)
        print(f"✅ DBSchema processed {result['documents_written']} documents")
        
    except Exception as e:
        print(f"❌ Error with DBSchema: {e}")
        print("Note: Make sure all dependencies are properly configured")


def show_document_structure(documents):
    """Show the structure of generated documents"""
    print("\n📄 Document Structure Analysis:")
    
    if not documents:
        print("  - No documents generated")
        return
    
    # Show table document
    table_docs = [d for d in documents if d.metadata.get('documentation_type') == 'table_overview']
    if table_docs:
        print(f"\n📋 Table Document:")
        print(f"  - ID: {table_docs[0].metadata.get('id', 'N/A')}")
        print(f"  - Name: {table_docs[0].metadata.get('name')}")
        print(f"  - Project: {table_docs[0].metadata.get('project_id')}")
        print(f"  - Content preview: {table_docs[0].page_content[:150]}...")
    
    # Show column documents
    column_docs = [d for d in documents if d.metadata.get('documentation_type') == 'column_detail']
    if column_docs:
        print(f"\n📊 Column Documents ({len(column_docs)}):")
        for i, doc in enumerate(column_docs[:3]):  # Show first 3
            print(f"  {i+1}. {doc.metadata.get('name')}")
            print(f"     - Type: {doc.metadata.get('column_name')}")
            print(f"     - Content preview: {doc.page_content[:100]}...")
        
        if len(column_docs) > 3:
            print(f"  ... and {len(column_docs) - 3} more columns")


def show_usage_examples():
    """Show usage examples"""
    print("\n📚 Usage Examples:")
    print("=" * 40)
    
    print("\n1. Basic Schema Documentation:")
    print("""
    # Generate documentation
    schema_manager = LLMSchemaDocumentationGenerator()
    documented_table = await schema_manager.document_table_schema(schema_input, project_context)
    """)
    
    print("\n2. Convert to MDL:")
    print("""
    # Convert to MDL format for DBSchema
    mdl_json = SchemaDocumentationUtils.documented_table_to_mdl(documented_table, project_id)
    """)
    
    print("\n3. Convert to ChromaDB Documents:")
    print("""
    # Convert to ChromaDB format
    documents = SchemaDocumentationUtils.documented_table_to_chroma_documents(documented_table, project_id)
    """)
    
    print("\n4. Complete Workflow:")
    print("""
    # One-step process and store
    result = await SchemaDocumentationUtils.process_and_store_schema(
        schema_input, project_context, document_store
    )
    """)


if __name__ == "__main__":
    print("Schema Documentation to ChromaDB Example")
    print("=" * 50)
    
    # Show usage examples
    show_usage_examples()
    
    # Run the complete workflow
    asyncio.run(complete_workflow_example()) 