"""
Standalone MDL Indexing Script
Indexes MDL files into db_schema, table_descriptions, and column_metadata collections.

This script follows the same structure as db_schema.py and project_reader.py,
ensuring compatibility with retrieval.py and retrieval_helper.py.

Usage:
    # PREVIEW MODE: Generate preview files for review (recommended)
    python -m indexing_cli.index_mdl_standalone \
        --mdl-file path/to/mdl.json \
        --project-id "project_name" \
        --product-name "ProductName" \
        --preview-mode \
        --preview-dir ./indexing_preview

    # Then review the generated files and ingest them:
    python -m indexing_cli.ingest_preview_files \
        --preview-dir ./indexing_preview \
        --content-types table_definitions table_descriptions column_definitions

    # DIRECT MODE: Index directly to database (skip preview)
    python -m indexing_cli.index_mdl_standalone \
        --mdl-file path/to/mdl.json \
        --project-id "project_name" \
        --product-name "ProductName"

    # Use existing preview files (with fixed categories)
    python -m indexing_cli.index_mdl_standalone \
        --mdl-file path/to/mdl.json \
        --project-id "project_name" \
        --product-name "ProductName" \
        --preview-dir ./indexing_preview
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.indexing.processors.db_schema_processor import DBSchemaProcessor
from app.indexing.processors.table_description_processor import TableDescriptionProcessor
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_doc_store_provider
from app.storage.documents import ChromaDBEmbeddingFunction
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def write_preview_file(
    documents: List[Any],
    preview_dir: Path,
    content_type: str,
    product_name: str,
    metadata: Dict[str, Any] = None
) -> Path:
    """
    Write documents to a preview JSON file.
    
    Args:
        documents: List of Document objects
        preview_dir: Preview directory path
        content_type: Content type (e.g., "table_definitions", "table_descriptions")
        product_name: Product name for filename
        metadata: Additional metadata to include in file
        
    Returns:
        Path to written file
    """
    from datetime import datetime
    
    # Create subdirectory for content type
    content_dir = preview_dir / content_type
    content_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Create filename
    filename = f"{content_type}_{timestamp}_{product_name}.json"
    filepath = content_dir / filename
    
    # Convert documents to serializable format
    doc_list = []
    for doc in documents:
        doc_data = {
            "page_content": doc.page_content,
            "metadata": doc.metadata if hasattr(doc, 'metadata') else {}
        }
        doc_list.append(doc_data)
    
    # Create file data structure
    file_data = {
        "metadata": {
            "content_type": content_type,
            "product_name": product_name,
            "document_count": len(doc_list),
            "timestamp": timestamp,
            "indexed_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        },
        "documents": doc_list
    }
    
    # Write to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(file_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"  ✓ Wrote {len(doc_list)} documents to {filepath.name}")
    
    # Also write summary file
    summary_file = content_dir / f"{content_type}_summary_{timestamp}.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"Content Type: {content_type}\n")
        f.write(f"Product: {product_name}\n")
        f.write(f"Document Count: {len(doc_list)}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"\nFile: {filename}\n")
    
    return filepath


async def index_mdl_standalone(
    mdl_file_path: str,
    project_id: str,
    product_name: Optional[str] = None,
    domain: Optional[str] = None,
    collections: Optional[List[str]] = None,
    column_batch_size: int = 200,
    force_recreate_column_metadata: bool = False,
    preview_dir: Optional[str] = None,
    preview_mode: bool = False
):
    """
    Index MDL file into db_schema, table_descriptions, and column_metadata collections.
    
    Args:
        mdl_file_path: Path to MDL JSON file
        project_id: Project ID (used as project_id in metadata)
        product_name: Product name (optional, defaults to project_id)
        domain: Domain filter (optional)
        collections: List of collections to index (default: all)
        column_batch_size: Batch size for column processing in db_schema
        preview_dir: Optional path to preview directory for reading/writing preview JSON files
        preview_mode: If True, write preview files instead of indexing to database
    """
    mdl_path = Path(mdl_file_path)
    if not mdl_path.exists():
        raise FileNotFoundError(f"MDL file not found: {mdl_file_path}")
    
    # Default collections if not specified
    if collections is None:
        collections = ["db_schema", "table_descriptions", "column_metadata"]
    
    logger.info("=" * 80)
    logger.info("MDL Standalone Indexing")
    logger.info("=" * 80)
    logger.info(f"MDL File: {mdl_file_path}")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Product Name: {product_name or project_id}")
    logger.info(f"Domain: {domain or 'None'}")
    logger.info(f"Collections: {', '.join(collections)}")
    logger.info(f"Preview Dir: {preview_dir or 'None'}")
    logger.info(f"Preview Mode: {preview_mode}")
    logger.info("")
    
    # Load MDL file (always needed unless reading from preview in non-preview mode)
    mdl_data = None
    if preview_mode or not preview_dir or "db_schema" in collections:
        logger.info(f"Loading MDL file: {mdl_path}")
        with open(mdl_path, "r", encoding="utf-8") as f:
            mdl_data = json.load(f)
        
        logger.info(f"Loaded MDL with {len(mdl_data.get('models', []))} models")
        logger.info("")
    
    # Load preview data if provided and not in preview_mode
    preview_data = {}
    if preview_dir and not preview_mode:
        preview_path = Path(preview_dir)
        logger.info(f"Loading preview data from: {preview_path}")
        
        # Try to find the JSON files in preview directory
        preview_files = {
            "table_definitions": None,
            "table_descriptions": None,
            "column_definitions": None
        }
        
        # Search for files in subdirectories
        for key in preview_files.keys():
            subdir = preview_path / key
            if subdir.exists():
                # Find JSON file matching pattern
                json_files = list(subdir.glob(f"{key}_*_{product_name or project_id}.json"))
                if json_files:
                    preview_files[key] = json_files[0]
                    logger.info(f"  Found {key}: {preview_files[key].name}")
        
        # Load the files
        for key, filepath in preview_files.items():
            if filepath and filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    preview_data[key] = json.load(f)
                logger.info(f"  Loaded {key}: {len(preview_data[key].get('documents', []))} documents")
        
        logger.info("")
    
    # Setup preview directory for writing if in preview_mode
    if preview_mode:
        if not preview_dir:
            preview_dir = "indexing_preview"
        preview_path = Path(preview_dir)
        preview_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Preview mode enabled - will write files to: {preview_path}")
        logger.info("")
    
    # Initialize dependencies (only needed in non-preview mode)
    persistent_client = None
    embeddings = None
    doc_store_provider = None
    
    if not preview_mode:
        persistent_client = get_chromadb_client()
        embeddings = get_embeddings_model()
        doc_store_provider = get_doc_store_provider()
    
    results = {}
    
    # Index db_schema collection (or write preview file)
    if "db_schema" in collections:
        logger.info("=" * 80)
        logger.info("Processing db_schema (table_definitions)" if preview_mode else "Indexing db_schema collection")
        logger.info("=" * 80)
        try:
            # Use preview data if available (only in non-preview mode)
            if preview_data.get("table_definitions") and not preview_mode:
                logger.info("Using pre-processed data from preview directory")
                from langchain_core.documents import Document
                
                documents = []
                for doc_data in preview_data["table_definitions"]["documents"]:
                    doc = Document(
                        page_content=doc_data["page_content"],
                        metadata=doc_data["metadata"]
                    )
                    documents.append(doc)
                logger.info(f"Loaded {len(documents)} documents from preview")
            else:
                # Process from MDL
                db_schema_processor = DBSchemaProcessor(column_batch_size=column_batch_size)
                documents = await db_schema_processor.process_mdl(
                    mdl=mdl_data,
                    project_id=project_id,
                    product_name=product_name or project_id,
                    domain=domain,
                    metadata={"source_file": str(mdl_path)}
                )
            
            if preview_mode:
                # Write to preview file
                write_preview_file(
                    documents=documents,
                    preview_dir=Path(preview_dir),
                    content_type="table_definitions",
                    product_name=product_name or project_id,
                    metadata={"source_file": str(mdl_path), "source": "mdl"}
                )
                results["db_schema"] = {
                    "success": True,
                    "documents_written": len(documents),
                    "preview_file": True
                }
            else:
                # Index to database
                db_schema_store = doc_store_provider.get_store("db_schema")
                db_schema_store.add_documents(documents)
                logger.info(f"✓ Indexed {len(documents)} documents to db_schema collection")
                results["db_schema"] = {
                    "success": True,
                    "documents_indexed": len(documents)
                }
        except Exception as e:
            logger.error(f"✗ Error processing db_schema: {e}")
            results["db_schema"] = {
                "success": False,
                "error": str(e)
            }
        logger.info("")
    
    # Index table_descriptions collection (or write preview file)
    if "table_descriptions" in collections:
        logger.info("=" * 80)
        logger.info("Processing table_descriptions" if preview_mode else "Indexing table_descriptions collection")
        logger.info("=" * 80)
        try:
            # Use preview data if available (only in non-preview mode)
            if preview_data.get("table_descriptions") and not preview_mode:
                logger.info("Using pre-processed data from preview directory")
                from langchain_core.documents import Document
                from datetime import datetime
                
                documents = []
                for doc_data in preview_data["table_descriptions"]["documents"]:
                    doc = Document(
                        page_content=doc_data["page_content"],
                        metadata=doc_data["metadata"]
                    )
                    documents.append(doc)
                logger.info(f"Loaded {len(documents)} documents from preview")
            else:
                # Process from MDL
                table_description_processor = TableDescriptionProcessor()
                documents = await table_description_processor.process_mdl(
                    mdl=mdl_data,
                    project_id=project_id,
                    product_name=product_name or project_id,
                    domain=domain,
                    metadata={"source_file": str(mdl_path)}
                )
            
            if preview_mode:
                # Write to preview file
                write_preview_file(
                    documents=documents,
                    preview_dir=Path(preview_dir),
                    content_type="table_descriptions",
                    product_name=product_name or project_id,
                    metadata={"source_file": str(mdl_path), "source": "mdl"}
                )
                results["table_descriptions"] = {
                    "success": True,
                    "documents_written": len(documents),
                    "preview_file": True
                }
            else:
                # Index to database
                table_description_store = doc_store_provider.get_store("table_description")
                table_description_store.add_documents(documents)
                logger.info(f"✓ Indexed {len(documents)} documents to table_descriptions collection")
                results["table_descriptions"] = {
                    "success": True,
                    "documents_indexed": len(documents)
                }
        except Exception as e:
            logger.error(f"✗ Error processing table_descriptions: {e}")
            results["table_descriptions"] = {
                "success": False,
                "error": str(e)
            }
        logger.info("")
    
    # Index column_metadata collection (or write preview file)
    if "column_metadata" in collections:
        logger.info("=" * 80)
        logger.info("Processing column_definitions (column_metadata)" if preview_mode else "Indexing column_metadata collection")
        logger.info("=" * 80)
        try:
            # Skip database setup in preview mode
            if not preview_mode:
                # Get column_metadata store and ensure it uses the same embeddings model
                # If dimension mismatch occurs, we'll recreate the store
                from app.storage.documents import DocumentChromaStore
            
            # Force recreate if requested (only in non-preview mode)
            if force_recreate_column_metadata and not preview_mode:
                logger.info("Force recreating column_metadata collection...")
                try:
                    persistent_client.delete_collection("column_metadata")
                    logger.info("Deleted existing column_metadata collection")
                    # Also delete TF-IDF collection if it exists
                    try:
                        persistent_client.delete_collection("column_metadata_tfidf")
                        logger.info("Deleted existing column_metadata_tfidf collection")
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"Could not delete collection (may not exist): {e}")
                
                # Create collection directly with correct embedding function to avoid stale references
                # Wait a moment to ensure deletion is complete
                time.sleep(0.5)
                
                # Create embedding function with correct model
                chroma_embedding_function = ChromaDBEmbeddingFunction(embeddings)
                
                # Create collection directly
                try:
                    collection = persistent_client.create_collection(
                        name="column_metadata",
                        embedding_function=chroma_embedding_function,
                        metadata={"description": "Column metadata collection"}
                    )
                    logger.info("Created new column_metadata collection directly with correct embeddings model")
                except Exception as create_error:
                    if "already exists" in str(create_error).lower() or "unique" in str(create_error).lower():
                        logger.warning("Collection still exists, trying to delete again...")
                        try:
                            persistent_client.delete_collection("column_metadata")
                            time.sleep(0.5)
                            collection = persistent_client.create_collection(
                                name="column_metadata",
                                embedding_function=chroma_embedding_function,
                                metadata={"description": "Column metadata collection"}
                            )
                            logger.info("Successfully created collection after second deletion")
                        except Exception as retry_error:
                            logger.error(f"Failed to create collection after retry: {retry_error}")
                            raise
                    else:
                        raise
                
                # Now create DocumentChromaStore which will use the collection we just created
                column_metadata_store = DocumentChromaStore(
                    persistent_client=persistent_client,
                    collection_name="column_metadata",
                    embeddings_model=embeddings,
                    tf_idf=True
                )
                logger.info("Created DocumentChromaStore with correct embeddings model")
            else:
                try:
                    column_metadata_store = doc_store_provider.get_store("column_metadata")
                    # Verify embedding dimension matches
                    try:
                        # Get current embedding dimension
                        test_embedding = embeddings.embed_query("test")
                        current_dim = len(test_embedding)
                        logger.info(f"Current embedding model dimension: {current_dim}")
                        
                        # Check if collection exists and get its dimension
                        try:
                            collection = persistent_client.get_collection("column_metadata")
                            # Try to get dimension from collection metadata or by checking existing embeddings
                            # ChromaDB stores dimension in collection metadata
                            if hasattr(collection, 'metadata') and collection.metadata:
                                existing_dim = collection.metadata.get('dimension')
                                if existing_dim and existing_dim != current_dim:
                                    logger.warning(f"Dimension mismatch detected: collection={existing_dim}, current={current_dim}")
                                    logger.warning("Recreating column_metadata collection with correct dimension...")
                                    try:
                                        persistent_client.delete_collection("column_metadata")
                                        # Also delete TF-IDF collection if it exists
                                        try:
                                            persistent_client.delete_collection("column_metadata_tfidf")
                                        except:
                                            pass
                                        
                                        # Wait to ensure deletion is complete
                                        time.sleep(0.5)
                                        
                                        # Create collection directly with correct embedding function
                                        chroma_embedding_function = ChromaDBEmbeddingFunction(embeddings)
                                        persistent_client.create_collection(
                                            name="column_metadata",
                                            embedding_function=chroma_embedding_function,
                                            metadata={"description": "Column metadata collection"}
                                        )
                                        
                                        # Now create DocumentChromaStore
                                        column_metadata_store = DocumentChromaStore(
                                            persistent_client=persistent_client,
                                            collection_name="column_metadata",
                                            embeddings_model=embeddings,
                                            tf_idf=True
                                        )
                                        logger.info("✓ Recreated column_metadata collection with correct dimension")
                                    except Exception as recreate_error:
                                        logger.error(f"Error during recreation: {recreate_error}")
                                        raise
                        except Exception as get_collection_error:
                            # Collection might not exist, that's okay
                            logger.debug(f"Collection check: {get_collection_error}")
                    except Exception as dim_check_error:
                        logger.warning(f"Could not verify dimension, proceeding anyway: {dim_check_error}")
                except Exception as store_error:
                    logger.warning(f"Error getting column_metadata store: {store_error}")
                    # Create store directly with correct embeddings
                    column_metadata_store = DocumentChromaStore(
                        persistent_client=persistent_client,
                        collection_name="column_metadata",
                        embeddings_model=embeddings,
                        tf_idf=True
                    )
                    logger.info("Created column_metadata store directly with embeddings model")
            
            # Extract column definitions from preview or MDL
            column_documents = []
            
            if preview_data.get("column_definitions") and not preview_mode:
                logger.info("Using pre-processed column data from preview directory")
                from langchain_core.documents import Document
                
                for doc_data in preview_data["column_definitions"]["documents"]:
                    doc = Document(
                        page_content=doc_data["page_content"],
                        metadata=doc_data["metadata"]
                    )
                    column_documents.append(doc)
                logger.info(f"Loaded {len(column_documents)} column documents from preview")
            else:
                # Extract from MDL
                from langchain_core.documents import Document
                from datetime import datetime
                
                for model in mdl_data.get("models", []):
                    table_name = model.get("name", "")
                    if not table_name:
                        continue
                    
                    for column in model.get("columns", []):
                        if column.get("isHidden") is True:
                            continue
                        
                        column_name = column.get("name", "")
                        column_type = column.get("type", "")
                        column_description = column.get("description", "")
                        column_properties = column.get("properties", {})
                        
                        # Create column metadata document (same format as retrieval_helper expects)
                        column_content = {
                            "column_name": column_name,
                            "table_name": table_name,
                            "type": column_type,
                            "display_name": column_properties.get("displayName", column_name),
                            "description": column_description,
                            "is_calculated": column.get("isCalculated", False),
                            "is_primary_key": column_name == model.get("primaryKey", ""),
                            "is_foreign_key": bool(column.get("relationship")),
                            "properties": column_properties,
                            "expression": column.get("expression", ""),
                            "notNull": column.get("notNull", False)
                        }
                        
                        column_doc = Document(
                            page_content=json.dumps(column_content, indent=2),
                            metadata={
                                "type": "COLUMN_METADATA",
                                "column_name": column_name,
                                "table_name": table_name,
                                "project_id": project_id,
                                "product_name": product_name or project_id,
                                "content_type": "column_definition",
                                "indexed_at": datetime.utcnow().isoformat(),
                                **({"domain": domain} if domain else {})
                            }
                        )
                        column_documents.append(column_doc)
            
            if preview_mode:
                # Write to preview file
                if column_documents:
                    write_preview_file(
                        documents=column_documents,
                        preview_dir=Path(preview_dir),
                        content_type="column_definitions",
                        product_name=product_name or project_id,
                        metadata={"source_file": str(mdl_path), "source": "mdl"}
                    )
                    results["column_metadata"] = {
                        "success": True,
                        "documents_written": len(column_documents),
                        "preview_file": True
                    }
                else:
                    logger.warning("No column documents to write")
                    results["column_metadata"] = {
                        "success": True,
                        "documents_written": 0
                    }
            elif column_documents:
                try:
                    column_metadata_store.add_documents(column_documents)
                    logger.info(f"✓ Indexed {len(column_documents)} documents to column_metadata collection")
                    results["column_metadata"] = {
                        "success": True,
                        "documents_indexed": len(column_documents)
                    }
                except Exception as add_error:
                    error_str = str(add_error)
                    # Check if it's a dimension mismatch error
                    if "dimension" in error_str.lower() or "dimensionality" in error_str.lower():
                        logger.warning(f"Dimension mismatch error detected: {error_str}")
                        logger.warning("Recreating column_metadata collection with correct dimension...")
                        try:
                            # Delete and recreate collection
                            persistent_client.delete_collection("column_metadata")
                            # Also delete TF-IDF collection if it exists
                            try:
                                persistent_client.delete_collection("column_metadata_tfidf")
                            except:
                                pass
                            
                            # Wait to ensure deletion is complete
                            time.sleep(0.5)
                            
                            # Create collection directly with correct embedding function
                            chroma_embedding_function = ChromaDBEmbeddingFunction(embeddings)
                            persistent_client.create_collection(
                                name="column_metadata",
                                embedding_function=chroma_embedding_function,
                                metadata={"description": "Column metadata collection"}
                            )
                            
                            # Now create DocumentChromaStore
                            column_metadata_store = DocumentChromaStore(
                                persistent_client=persistent_client,
                                collection_name="column_metadata",
                                embeddings_model=embeddings,
                                tf_idf=True
                            )
                            logger.info("✓ Recreated column_metadata collection, retrying indexing...")
                            # Retry adding documents
                            column_metadata_store.add_documents(column_documents)
                            logger.info(f"✓ Indexed {len(column_documents)} documents to column_metadata collection")
                            results["column_metadata"] = {
                                "success": True,
                                "documents_indexed": len(column_documents),
                                "collection_recreated": True
                            }
                        except Exception as recreate_error:
                            logger.error(f"✗ Error recreating collection: {recreate_error}")
                            results["column_metadata"] = {
                                "success": False,
                                "error": f"Dimension mismatch and recreation failed: {recreate_error}"
                            }
                    else:
                        # Different error, re-raise
                        raise
            else:
                logger.warning("No column documents to index")
                results["column_metadata"] = {
                    "success": True,
                    "documents_indexed": 0
                }
        except Exception as e:
            logger.error(f"✗ Error indexing column_metadata: {e}")
            results["column_metadata"] = {
                "success": False,
                "error": str(e)
            }
        logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("Preview Generation Summary" if preview_mode else "Indexing Summary")
    logger.info("=" * 80)
    for collection, result in results.items():
        if result.get("success"):
            if preview_mode:
                logger.info(f"✓ {collection}: {result.get('documents_written', 0)} documents written to preview")
            else:
                logger.info(f"✓ {collection}: {result.get('documents_indexed', 0)} documents indexed")
        else:
            logger.error(f"✗ {collection}: Error - {result.get('error', 'Unknown error')}")
    
    if preview_mode:
        logger.info(f"\nPreview files written to: {preview_dir}")
        logger.info(f"Review the files and then use ingest_preview_files.py to ingest them.")
    
    logger.info("=" * 80)
    
    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Index MDL files into db_schema, table_descriptions, and column_metadata collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--mdl-file",
        required=True,
        help="Path to MDL JSON file"
    )
    
    parser.add_argument(
        "--project-id",
        required=True,
        help="Project ID (used as project_id in metadata)"
    )
    
    parser.add_argument(
        "--product-name",
        default=None,
        help="Product name (optional, defaults to project_id)"
    )
    
    parser.add_argument(
        "--domain",
        default=None,
        help="Domain filter (optional)"
    )
    
    parser.add_argument(
        "--collections",
        nargs="+",
        choices=["db_schema", "table_descriptions", "column_metadata"],
        default=None,
        help="Collections to index (default: all)"
    )
    
    parser.add_argument(
        "--column-batch-size",
        type=int,
        default=200,
        help="Batch size for column processing in db_schema (default: 200)"
    )
    
    parser.add_argument(
        "--force-recreate-column-metadata",
        action="store_true",
        help="Force recreate column_metadata collection to fix dimension mismatches"
    )
    
    parser.add_argument(
        "--preview-dir",
        default=None,
        help="Path to preview directory (default: indexing_preview). Used for reading pre-processed files or writing preview files."
    )
    
    parser.add_argument(
        "--preview-mode",
        action="store_true",
        help="Preview mode: Write processed documents to preview JSON files instead of indexing to database. Use for review before ingesting."
    )
    
    args = parser.parse_args()
    
    # Run async function
    asyncio.run(index_mdl_standalone(
        mdl_file_path=args.mdl_file,
        project_id=args.project_id,
        product_name=args.product_name,
        domain=args.domain,
        collections=args.collections,
        column_batch_size=args.column_batch_size,
        force_recreate_column_metadata=args.force_recreate_column_metadata,
        preview_dir=args.preview_dir,
        preview_mode=args.preview_mode
    ))


if __name__ == "__main__":
    main()
