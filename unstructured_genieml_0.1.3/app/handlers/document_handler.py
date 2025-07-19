from typing import Dict, List, Optional
import logging
import json
import traceback

from app.schemas.document_schemas import DocumentType
from app.services.metadata_extractor import run_extraction
from app.utils.chromadb import ChromaDB
from app.utils.postgresdb import PostgresDB

# Configure logging
logger = logging.getLogger(__name__)


def get_document(document_type: DocumentType, document_id: str) -> Optional[Dict]:
    """
    Get a document from Postgres
    
    Returns None if document not found
    """
    logger.info(f"[GET_DOCUMENT] Retrieving document {document_id} of type {document_type}")
    
    try:
        db = PostgresDB()
        
        # For generic documents, query document_versions1 directly
        if document_type == DocumentType.GENERIC:
            logger.info(f"[GET_DOCUMENT] Checking document_versions1 table for generic document")
            
            # Try exact match first, then fall back to metadata search
            query = "SELECT * FROM document_versions1 WHERE document_id = %s"
            results = db.execute_query(query, (document_id,))
            
            # If not found, try searching in json_metadata
            if not results:
                query = "SELECT * FROM document_versions1 WHERE json_metadata::text LIKE %s"
                search_pattern = f'%"id": "{document_id}"%'
                results = db.execute_query(query, (search_pattern,))
            
            if results and len(results) > 0:
                document = results[0]
                logger.info(f"[GET_DOCUMENT] Found document in document_versions1")
                
                # Extract metadata
                metadata = {}
                if document.get("json_metadata"):
                    if isinstance(document["json_metadata"], str):
                        try:
                            metadata = json.loads(document["json_metadata"])
                        except json.JSONDecodeError:
                            logger.error(f"[GET_DOCUMENT] Invalid JSON in json_metadata")
                    else:
                        metadata = document["json_metadata"]
                
                # Format response
                return {
                    "document_id": document_id,
                    "document_name": metadata.get("document_key", "unknown"),
                    "document_content": document.get("content", ""),
                    "metadata": metadata
                }
        
        # Fall back to standard document table lookup
        table_name = f"document_{document_type}"
        document = db.get_record(table_name, document_id)
        if document:
            return document
        
        logger.error(f"[GET_DOCUMENT] Document not found in any table")
        return None
        
    except Exception as e:
        logger.error(f"[GET_DOCUMENT] Error retrieving document: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def get_document_metadata_from_chromadb(document_id: str, collection_name: str = "documents") -> Optional[Dict]:
    """
    Get document metadata from ChromaDB
    
    Args:
        document_id: The document ID to retrieve
        collection_name: The ChromaDB collection name (default: "documents")
        
    Returns:
        Dictionary containing document metadata or None if not found
    """
    logger.info(f"[GET_DOCUMENT_FROM_CHROMADB] Retrieving document {document_id} from collection {collection_name}")
    
    try:
        chroma_db = ChromaDB()
        collection = chroma_db.get_collection(collection_name)
        
        # Try different ID formats commonly used in the system
        possible_ids = [
            document_id,                   # Original ID
            f"doc_{document_id}",          # doc_ prefix
        ]
        
        # Create a list of phrase IDs with different suffixes (for chunked documents)
        phrase_ids = [f"phrase_{document_id}_{i}" for i in range(10)]  # Try suffixes _0 through _9
        possible_ids.extend(phrase_ids)
        
        logger.info(f"[GET_DOCUMENT_FROM_CHROMADB] Trying {len(possible_ids)} possible ID formats")
        
        # Initialize result variables
        all_metadata = {}
        content_parts = []
        found_any = False
        found_ids = []
        
        # Check each possible ID format
        for pid in possible_ids:
            try:
                # Query ChromaDB for each possible ID format
                result = collection.get(
                    ids=[pid],
                    include=["metadatas", "documents"]  # type: ignore
                )
                
                if result and len(result.get("ids", [])) > 0:
                    found_any = True
                    found_ids.append(pid)
                    
                    # Extract and merge metadata
                    if "metadatas" in result and result["metadatas"] and len(result["metadatas"]) > 0:
                        metadata = result["metadatas"][0]
                        # Merge with existing metadata
                        for key, value in metadata.items():
                            if key not in all_metadata:
                                all_metadata[key] = value
                    
                    # Collect document content
                    if "documents" in result and result["documents"] and len(result["documents"]) > 0:
                        doc_content = result["documents"][0]
                        if doc_content:
                            content_parts.append(doc_content)
            except Exception as e:
                logger.warning(f"[GET_DOCUMENT_FROM_CHROMADB] Error checking ID format {pid}: {str(e)}")
                continue
        
        if not found_any:
            logger.warning(f"[GET_DOCUMENT_FROM_CHROMADB] Document {document_id} not found in any format in collection {collection_name}")
            return None
        
        # Combine content parts or use the first one
        document_content = "\n\n".join(content_parts) if len(content_parts) > 1 else (content_parts[0] if content_parts else "")
        
        logger.info(f"[GET_DOCUMENT_FROM_CHROMADB] Successfully retrieved document using {len(found_ids)} ID formats: {found_ids[:3]}...")
        
        return {
            "document_id": document_id,
            "collection_name": collection_name,
            "found_ids": found_ids,
            "document_content": document_content,
            "metadata": all_metadata
        }
        
    except Exception as e:
        logger.error(f"[GET_DOCUMENT_FROM_CHROMADB] Error retrieving document: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def get_all_documents(document_type: DocumentType, limit: int = -1) -> List[Dict]:
    """
    Get all documents from Postgres
    
    For generic documents, uses document_versions1 table
    For other types, falls back to document_* tables
    Returns an empty list if the table doesn't exist yet
    """
    logger.info(f"[GET_ALL_DOCUMENTS] Retrieving all documents of type {document_type} with limit {limit}")
    
    db = PostgresDB()
    documents = []
    
    try:
        # For generic documents, query document_versions1 directly
        if document_type == DocumentType.GENERIC:
            logger.info(f"[GET_ALL_DOCUMENTS] Querying document_versions1 table for generic documents")
            
            # Query the document_versions1 table
            limit_clause = f"LIMIT {limit}" if limit > 0 else ""
            query = f"SELECT * FROM document_versions1 ORDER BY created_at DESC {limit_clause}"
            results = db.execute_query(query)
            
            if results:
                logger.info(f"[GET_ALL_DOCUMENTS] Found {len(results)} documents in document_versions1")
                
                for document in results:
                    # Extract metadata like in get_document
                    metadata = {}
                    if document.get("json_metadata"):
                        if isinstance(document["json_metadata"], str):
                            try:
                                metadata = json.loads(document["json_metadata"])
                            except json.JSONDecodeError:
                                logger.error(f"[GET_ALL_DOCUMENTS] Invalid JSON in json_metadata for document {document.get('document_id')}")
                        else:
                            metadata = document["json_metadata"]
                    
                    document_id = document.get("document_id", "")
                    # Make sure document_id is a string
                    if hasattr(document_id, "__str__"):  # Convert UUID or other object to string if needed
                        document_id = str(document_id)
                    
                    # Try to get additional metadata from ChromaDB, like in get_document
                    try:
                        chromadb_data = get_document_metadata_from_chromadb(document_id)
                        if chromadb_data and chromadb_data.get("metadata"):
                            logger.info(f"[GET_ALL_DOCUMENTS] Found additional metadata for document {document_id} in ChromaDB")
                            # Merge ChromaDB metadata with existing metadata
                            chromadb_metadata = chromadb_data.get("metadata", {})
                            metadata.update(chromadb_metadata)
                            
                            # Add information about found IDs to the metadata
                            if "found_ids" in chromadb_data:
                                metadata["chromadb_ids"] = chromadb_data["found_ids"]
                    except Exception as e:
                        logger.warning(f"[GET_ALL_DOCUMENTS] Error getting ChromaDB metadata for document {document_id}: {str(e)}")
                    
                    # Format response like get_document
                    documents.append({
                        "document_id": document_id,
                        "document_name": metadata.get("document_key", metadata.get("source", "unknown")),
                        "document_content": document.get("content", ""),
                        "metadata": metadata
                    })
                
                return documents
        
        # Fall back to standard document table lookup
        logger.info(f"[GET_ALL_DOCUMENTS] Querying document_{document_type} table")
        table_documents = db.get_all_records(f"document_{document_type}", limit)
        
        # For each document, enrich with metadata from ChromaDB if available
        for document in table_documents:
            document_id = document.get("document_id", "")
            # Make sure document_id is a string
            if hasattr(document_id, "__str__"):  # Convert UUID or other object to string if needed
                document_id = str(document_id)
            
            # Only try to get from ChromaDB if we have a valid document_id
            if document_id:
                try:
                    chromadb_data = get_document_metadata_from_chromadb(document_id)
                    if chromadb_data and chromadb_data.get("metadata"):
                        logger.info(f"[GET_ALL_DOCUMENTS] Found additional metadata for document {document_id} in ChromaDB")
                        # Make sure metadata exists in document
                        if "metadata" not in document:
                            document["metadata"] = {}
                        
                        # Merge ChromaDB metadata with existing metadata
                        chromadb_metadata = chromadb_data.get("metadata", {})
                        document["metadata"].update(chromadb_metadata)
                        
                        # Add information about found IDs to the metadata
                        if "found_ids" in chromadb_data:
                            document["metadata"]["chromadb_ids"] = chromadb_data["found_ids"]
                except Exception as e:
                    logger.warning(f"[GET_ALL_DOCUMENTS] Error getting ChromaDB metadata for document {document_id}: {str(e)}")
            
            documents.append(document)
        
        return documents
        
    except Exception as e:
        logger.error(f"[GET_ALL_DOCUMENTS] Error retrieving documents of type {document_type}: {str(e)}")
        logger.error(traceback.format_exc())
        
        if "UndefinedTable" in str(e) or "relation" in str(e) and "does not exist" in str(e):
            # Return empty list if table doesn't exist yet
            return []
        # Re-raise other exceptions
        raise


async def upload_document(
    file_name: str, 
    text_content: str, 
    document_type: DocumentType, 
    test_mode: bool = False,
    user_context: Optional[str] = None
):
    """
    Upload a document to Postgres and ChromaDB
    
    Args:
        file_name: Name of the document file
        text_content: Content of the document
        document_type: Type of document
        test_mode: If True, document will be processed but not saved to database
        user_context: Optional contextual information to guide extraction
        
    Returns:
        Extracted metadata
    """
    return await run_extraction(file_name, text_content, document_type, test_mode, user_context)


def delete_document(document_type: DocumentType, document_id: str):
    """
    Delete a document from Postgres and ChromaDB
    """
    db = PostgresDB()
    db.delete_record("document_versions1", document_id)
    print(f"Deleted postgres record for {document_id}")
    chroma_db = ChromaDB()
    chroma_db.delete_items(document_type, [document_id])
    print(f"Deleted chroma record for {document_id}")
