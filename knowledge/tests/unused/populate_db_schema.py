"""
Populate db_schema collection from table_descriptions JSON files.
Uses the same MDL processing logic as project_reader.py to create TABLE_SCHEMA documents.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from langchain_core.documents import Document

from app.core.settings import get_settings, set_os_environ
from app.storage.vector_store import get_vector_store_client
from app.storage.documents import DocumentChromaStore
from langchain_openai import OpenAIEmbeddings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_mdl_from_source(source_file: str) -> Dict[str, Any]:
    """Load MDL data from the source file."""
    try:
        mdl_path = Path(source_file)
        if not mdl_path.exists():
            # Try relative to current directory
            mdl_path = Path.cwd() / source_file
        if not mdl_path.exists():
            # Try in the data directory
            mdl_path = Path.cwd() / "data" / "cvedata" / mdl_path.name
        
        if not mdl_path.exists():
            logger.error(f"Could not find MDL file: {source_file}")
            return None
        
        logger.info(f"Loading MDL from: {mdl_path}")
        with open(mdl_path, 'r') as f:
            mdl_data = json.load(f)
        
        return mdl_data
    except Exception as e:
        logger.error(f"Error loading MDL from {source_file}: {e}")
        return None


def create_table_schema_document(table: Dict[str, Any], project_id: str) -> Document:
    """
    Create a TABLE_SCHEMA document from table data.
    Mimics the format created by project_reader's db_schema component.
    """
    # Extract table information
    table_name = table.get("name", "")
    description = table.get("description", "")
    columns = table.get("columns", [])
    relationships = table.get("relationships", [])
    properties = table.get("properties", {})
    
    # Build DDL-style content
    ddl_lines = []
    
    # Add table comment with description
    if description:
        ddl_lines.append(f"-- {description}")
    
    # Add CREATE TABLE statement
    ddl_lines.append(f"CREATE TABLE {table_name} (")
    
    # Add columns
    column_defs = []
    for col in columns:
        col_name = col.get("name", "")
        col_type = col.get("type", "VARCHAR")
        col_desc = col.get("description", "")
        is_calculated = col.get("isCalculated", False)
        expression = col.get("expression", "")
        not_null = col.get("notNull", False)
        
        # Build column definition
        col_def = f"  {col_name} {col_type}"
        if not_null:
            col_def += " NOT NULL"
        
        # Add comment for column description
        if col_desc:
            col_def += f"  -- {col_desc}"
        
        # Add calculated field info
        if is_calculated and expression:
            col_def += f" [CALCULATED: {expression}]"
        
        column_defs.append(col_def)
    
    ddl_lines.append(",\n".join(column_defs))
    ddl_lines.append(");")
    
    # Add relationships as comments
    if relationships:
        ddl_lines.append("\n-- Relationships:")
        for rel in relationships:
            rel_type = rel.get("type", "UNKNOWN")
            models = rel.get("models", [])
            ddl_lines.append(f"-- {rel_type}: {' -> '.join(models)}")
    
    page_content = "\n".join(ddl_lines)
    
    # Create metadata matching db_schema format
    metadata = {
        "type": "TABLE_SCHEMA",  # This is the key difference from table_descriptions
        "name": table_name,
        "project_id": project_id,
        "description": description,
        "relationships": relationships,
        "properties": properties,
        "column_count": len(columns),
    }
    
    return Document(page_content=page_content, metadata=metadata)


async def populate_db_schema_from_json(json_file: Path):
    """
    Populate db_schema collection from a table_descriptions JSON file.
    """
    try:
        logger.info(f"Processing JSON file: {json_file}")
        
        # Load JSON file
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        metadata = data.get("metadata", {})
        documents_data = data.get("documents", [])
        
        project_id = metadata.get("product_name", "default")
        source_file = metadata.get("source_file", "")
        
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Source file: {source_file}")
        logger.info(f"Document count: {len(documents_data)}")
        
        # Load original MDL data
        mdl_data = await load_mdl_from_source(source_file)
        if not mdl_data:
            logger.warning("Could not load MDL data, will create schema documents from JSON data only")
            mdl_models = []
        else:
            mdl_models = mdl_data.get("models", [])
            logger.info(f"Loaded {len(mdl_models)} models from MDL")
        
        # Create TABLE_SCHEMA documents
        schema_documents = []
        
        # If we have MDL data, use it for richer schema information
        if mdl_models:
            for model in mdl_models:
                if model.get("isHidden"):
                    continue
                
                doc = create_table_schema_document(model, project_id)
                schema_documents.append(doc)
        else:
            # Fallback: create from JSON documents
            for doc_data in documents_data:
                doc_metadata = doc_data.get("metadata", {})
                table_name = doc_metadata.get("name", "")
                description = doc_metadata.get("description", "")
                
                # Parse columns from page_content (it's a string representation)
                page_content = doc_data.get("page_content", "")
                
                # Create a minimal table schema document
                table_dict = {
                    "name": table_name,
                    "description": description,
                    "columns": [],  # We don't have full column info in this format
                    "relationships": doc_metadata.get("relationships", []),
                    "properties": {}
                }
                
                doc = create_table_schema_document(table_dict, project_id)
                schema_documents.append(doc)
        
        logger.info(f"Created {len(schema_documents)} TABLE_SCHEMA documents")
        
        # Initialize vector store
        settings = get_settings()
        set_os_environ(settings)
        
        embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Get vector store client
        vector_store_client = get_vector_store_client(embeddings_model=embeddings)
        
        # Get or create db_schema document store
        if hasattr(vector_store_client, '_get_document_store'):
            db_schema_store = vector_store_client._get_document_store("db_schema")
        else:
            # Fallback: create directly
            db_schema_store = DocumentChromaStore(
                persistent_client=vector_store_client.client,
                collection_name="db_schema",
                embeddings_model=embeddings,
                tf_idf=False
            )
        
        logger.info("Ingesting documents to db_schema collection...")
        
        # Filter complex metadata
        from app.storage.documents import filter_complex_metadata
        filtered_docs = filter_complex_metadata(schema_documents)
        
        # Add documents to db_schema
        result_ids = db_schema_store.add_documents(filtered_docs)
        
        logger.info(f"✅ Successfully ingested {len(result_ids)} documents to db_schema collection")
        
        # Verify collection count
        collection = db_schema_store.collection
        count = collection.count()
        logger.info(f"✅ db_schema collection now has {count} documents total")
        
        return len(result_ids)
        
    except Exception as e:
        logger.error(f"Error populating db_schema: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def main():
    """Main function to populate db_schema from all table_descriptions JSON files."""
    try:
        logger.info("=" * 80)
        logger.info("Starting db_schema population from table_descriptions JSON files")
        logger.info("=" * 80)
        
        # Find all table_descriptions JSON files
        preview_dir = Path("indexing_preview/table_descriptions")
        if not preview_dir.exists():
            preview_dir = Path("../indexing_preview/table_descriptions")
        if not preview_dir.exists():
            logger.error("Could not find indexing_preview/table_descriptions directory")
            return
        
        json_files = list(preview_dir.glob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        total_docs = 0
        for json_file in json_files:
            logger.info(f"\nProcessing: {json_file.name}")
            docs_added = await populate_db_schema_from_json(json_file)
            total_docs += docs_added
        
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Successfully populated db_schema with {total_docs} documents")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
