"""
Simple script to create db_schema documents from MDL file.
Run this with: python3 -m create_db_schema_simple
"""
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from pathlib import Path

# Direct imports
import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document


def create_ddl_from_model(model: dict, project_id: str) -> Document:
    """Create a TABLE_SCHEMA document with DDL-style content."""
    table_name = model.get("name", "")
    description = model.get("properties", {}).get("description", "")
    columns = model.get("columns", [])
    relationships = model.get("relationships", [])
    
    # Build DDL
    ddl_lines = []
    if description:
        ddl_lines.append(f"-- {description}")
    
    ddl_lines.append(f"CREATE TABLE {table_name} (")
    
    col_defs = []
    for col in columns:
        if col.get("isHidden"):
            continue
        col_name = col.get("name", "")
        col_type = col.get("type", "VARCHAR")
        col_desc = col.get("properties", {}).get("description", "")
        not_null = col.get("notNull", False)
        is_calc = col.get("isCalculated", False)
        
        col_def = f"  {col_name} {col_type}"
        if not_null:
            col_def += " NOT NULL"
        if col_desc:
            col_def += f"  -- {col_desc}"
        if is_calc:
            expr = col.get("expression", "")
            col_def += f" [CALCULATED: {expr}]"
        
        col_defs.append(col_def)
    
    ddl_lines.append(",\n".join(col_defs))
    ddl_lines.append(");")
    
    page_content = "\n".join(ddl_lines)
    
    metadata = {
        "type": "TABLE_SCHEMA",  # Important: not TABLE_DESCRIPTION
        "name": table_name,
        "project_id": project_id,
        "description": description,
    }
    
    return Document(page_content=page_content, metadata=metadata)


async def main():
    print("=" * 80)
    print("Creating db_schema from MDL")
    print("=" * 80)
    
    # Load MDL file
    mdl_path = Path("/Users/sameermangalampalli/flowharmonicai/data/cvedata/snyk_mdl1.json")
    print(f"Loading MDL from: {mdl_path}")
    
    with open(mdl_path, 'r') as f:
        mdl_data = json.load(f)
    
    models = mdl_data.get("models", [])
    print(f"Found {len(models)} models in MDL")
    
    # Create TABLE_SCHEMA documents
    project_id = "Snyk"
    documents = []
    
    for model in models:
        if model.get("isHidden"):
            continue
        doc = create_ddl_from_model(model, project_id)
        documents.append(doc)
    
    print(f"Created {len(documents)} TABLE_SCHEMA documents")
    
    # Initialize ChromaDB client directly
    chroma_path = "/Users/sameermangalampalli/flowharmonicai/knowledge/../../data/chroma_db"
    print(f"Connecting to ChromaDB at: {chroma_path}")
    
    client = chromadb.PersistentClient(path=chroma_path)
    
    # Get or create db_schema collection
    try:
        collection = client.get_collection("db_schema")
        print(f"Found existing db_schema collection with {collection.count()} documents")
    except:
        collection = client.create_collection("db_schema")
        print("Created new db_schema collection")
    
    # Initialize embeddings
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.environ.get("OPENAI_API_KEY", "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")
    )
    
    # Add documents in batches
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        
        ids = [f"schema_{doc.metadata['name']}_{project_id}" for doc in batch]
        texts = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        
        # Generate embeddings
        print(f"Generating embeddings for batch {i//batch_size + 1}...")
        embed_vectors = await embeddings.aembed_documents(texts)
        
        # Add to collection
        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embed_vectors,
            metadatas=metadatas
        )
        print(f"  Added {len(batch)} documents")
    
    print(f"\n✅ Successfully added {len(documents)} documents to db_schema collection")
    print(f"✅ db_schema collection now has {collection.count()} total documents")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
