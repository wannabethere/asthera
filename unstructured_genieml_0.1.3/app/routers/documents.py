from typing import Any, Dict, Union, Optional
import logging
import traceback
import sys
from enum import Enum
from datetime import datetime
import uuid
import os
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status, Query
from pydantic import BaseModel

from app.handlers import document_handler
from app.schemas.document_schemas import DOCUMENT_SCHEMAS, DocumentType
from ingestions.extraction_pipeline import DocumentExtractor
from app.utils.chromadb import ChromaDB
from app.utils.postgresdb import PostgresDB
from app.agentic.processing.metadata_summarizer import metadata_summarizer
from app.config.settings import get_settings
from ingestions.pdf_document_ingestion import extract_text_from_binary_pdf, summarize_pdf_content, generate_insights_with_context
from app.services.database.dbservice import DatabaseService

# Get logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure logging to file as well
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"documents_api_{datetime.now().strftime('%Y%m%d')}.log")
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Add a specific stream handler if needed
if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(stream_handler)

# Create router
router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


class Document(BaseModel):
    document_type: DocumentType
    document_id: str
    document_name: str
    document_content: Union[str, Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
    source_type: Optional[str] = None
    event_type: Optional[str] = None
    event_timestamp: Optional[str] = None
    created_by: Optional[str] = None
    test_mode: Optional[bool] = None
    success: Optional[bool] = None


class SimpleDocument(BaseModel):
    document_type: DocumentType
    document_id: str
    document_name: str
    document_content: Union[str, Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class MarkdownResponse(BaseModel):
    document_type: DocumentType
    document_id: str
    document_name: str
    document_content: Union[str, Dict[str, Any]]
    markdown_summary: str
    raw_metadata: Optional[Dict[str, Any]] = None


class DocumentMetadata(BaseModel):
    chromadb_ids: list = []


class UploadedDocument(BaseModel):
    filename: str
    content_type: str
    document_type: DocumentType
    text_length: int
    document_id: str
    source_type: str = ""
    event_type: str = "upload"
    event_timestamp: str = ""
    created_by: str = "api_upload"
    metadata: DocumentMetadata
    markdown_summary: Optional[str] = None
    test_mode: bool = False
    success: bool = True


class TestMode(str, Enum):
    """Test mode options for API"""
    ENABLED = "enabled"
    DISABLED = "disabled"


def sanitize_text_for_postgres(text: str) -> str:
    """
    Sanitize text for PostgreSQL by removing null bytes and other problematic characters.
    
    Args:
        text: The input text to sanitize
        
    Returns:
        Sanitized text safe for PostgreSQL storage
    """
    # Remove null bytes (0x00)
    if text is None:
        return ""
    
    # Replace null bytes with empty string
    sanitized = text.replace('\x00', '')
    
    # Optionally replace other problematic characters if needed
    # For example, you might want to handle other control characters
    
    return sanitized


@router.post("/", response_model=UploadedDocument, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.GENERIC),
    test_mode: TestMode = Form(TestMode.DISABLED),
    user_context: str = Form(None),
):
    """
    Upload a document for processing

    - The document content will be extracted and processed
    - Metadata will be extracted based on document type using langgraph
    - Set test_mode=enabled to process the document without writing to the database
    - Response includes all document metadata and insights that would be stored in databases
    - Optional user_context can be provided to customize extraction behavior
    """
    is_test_mode = test_mode == TestMode.ENABLED
    document_id = None

    # Ensure PDF processing logs are properly configured
    pdf_logger = logging.getLogger("pdf_document_ingestion")
    if not pdf_logger.handlers:
        # Configure the PDF logger if it doesn't have handlers
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        pdf_log_file = os.path.join(log_dir, f"pdf_processing_{datetime.now().strftime('%Y%m%d')}.log")
        pdf_file_handler = logging.FileHandler(pdf_log_file)
        pdf_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        pdf_logger.addHandler(pdf_file_handler)
        
        # Add console handler
        pdf_console_handler = logging.StreamHandler(sys.stdout)
        pdf_console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        pdf_logger.addHandler(pdf_console_handler)
        pdf_logger.setLevel(logging.INFO)
        pdf_logger.propagate = True

    logger.info(f"Document upload started: type={document_type}, test_mode={is_test_mode}, filename={file.filename}")

    try:
        # Validate file
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        # Read the file content
        try:
            content = await file.read()
            if not content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Empty file provided"
                )
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error reading file: {str(e)}"
            )
        
        # Ensure filename is not None
        filename = file.filename or f"unnamed_document_{document_type}"
        logger.info(f"Processing document: {filename} (type: {document_type}, test_mode: {is_test_mode})")

        # Handle PDF files with OCR using Unstructured library
        if file.content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                # Initialize settings
                settings = get_settings()
                
                # Extract text from PDF using Unstructured
                logger.info(f"Processing PDF document: {filename}")
                text_from_pdf = extract_text_from_binary_pdf(content, filename)
                
                # Sanitize text to remove null bytes and other problematic characters
                sanitized_text = sanitize_text_for_postgres(text_from_pdf)
                logger.info(f"Sanitized PDF text to remove null bytes")
                
                # Generate a document ID
                document_id = str(uuid.uuid4())
                logger.info(f"Generated document ID: {document_id}")
                
                # Generate a markdown summary
                logger.info(f"Generating markdown summary")
                markdown_summary = summarize_pdf_content(
                    content=sanitized_text,
                    document_id=document_id,
                    filename=filename,
                    document_type=document_type.value
                )
                
                # Initialize the DocumentExtractor for NLP processing
                doc_extractor = DocumentExtractor(use_advanced_nlp=True)
                
                # Initialize document metadata
                document_metadata = {
                    "document_id": document_id,
                    "filename": filename,
                    "document_type": document_type.value,
                    "event_timestamp": datetime.now().isoformat(),
                    "created_by": "api_upload",
                    "source_type": "pdf",
                    "event_type": "upload",
                    "user_context": user_context
                }
                
                # If not in test mode, store the document properly using the DB service
                # This handles both ChromaDB and PostgreSQL storage
                if not is_test_mode:
                    # Initialize ChromaDB
                    chroma_db = ChromaDB()
                    collection_name = "documents"
                    
                    # Create a properly structured document for processing
                    structured_doc = {
                        "document": {
                            "content": sanitized_text,
                            "metadata": document_metadata
                        }
                    }
                    
                    # Process with DocumentExtractor
                    extraction_metadata = {
                        "document_id": document_id,
                        "document_type": document_type.value,
                        "source_type": "pdf",
                        "filename": filename,
                        "event_type": "upload",
                        "user_context": user_context
                    }
                    
                    # Store the document in ChromaDB
                    documents_collection = chroma_db.get_collection(collection_name)
                    documents_collection.add(
                        documents=[sanitized_text],
                        ids=[document_id],
                        metadatas=[document_metadata]
                    )
                    logger.info(f"Stored full document in ChromaDB with ID: {document_id}")
                
                # Process document with NLP extraction
                logger.info(f"Processing document with NLP extraction")
                batch_result = await doc_extractor.process_documents_batch(
                    documents=[{
                        "id": f"pdf_{document_id}",
                        "content": sanitized_text,
                        "metadata": extraction_metadata
                    }],
                    chunk_size=None,  # Use dynamic chunking
                    overlap=None,     # Use dynamic overlap
                    max_workers=2     # Use fewer workers for API endpoint
                )
                
                # Get NLP extraction results
                all_entities = set()
                all_keywords = set()
                all_topics = set()
                
                # Collect extraction results from chunks
                for chunk in batch_result:
                    # Extract entities, keywords, topics from NLP processing
                    chunk_entities = chunk.extraction.entities if hasattr(chunk.extraction, 'entities') else []
                    chunk_keywords = chunk.extraction.keywords if hasattr(chunk.extraction, 'keywords') else []
                    chunk_topics = chunk.extraction.topics if hasattr(chunk.extraction, 'topics') else []
                    
                    # Update overall collections
                    all_entities.update(chunk_entities)
                    all_keywords.update(chunk_keywords)
                    all_topics.update(chunk_topics)
                    
                    # Store the chunk in ChromaDB if not in test mode
                    if not is_test_mode:
                        chunk_metadata = {
                            "chunk_id": chunk.chunk_id,
                            "parent_doc_id": document_id,
                            "document_id": document_id,
                            "chunk_index": chunk.chunk_index,
                            "document_type": document_type.value,
                            "source_type": "pdf",
                            "event_type": "extraction",
                            "filename": filename,
                            "entities": json.dumps(chunk_entities),
                            "keywords": json.dumps(chunk_keywords),
                            "topics": json.dumps(chunk_topics),
                            "start_position": chunk.start_position,
                            "end_position": chunk.end_position,
                            "chunk_type": "pdf_chunk"
                        }
                        
                        documents_collection = chroma_db.get_collection(collection_name)
                        documents_collection.add(
                            ids=[chunk.chunk_id],
                            documents=[chunk.text],
                            metadatas=[chunk_metadata]
                        )
                
                # Now store in PostgreSQL with all the enriched metadata
                if not is_test_mode:
                    # Generate insights with context
                    logger.info(f"Generating insights for document {document_id}")
                    insights_content = generate_insights_with_context(
                        content=sanitized_text,
                        user_context=user_context if user_context else "Provide a comprehensive overview of this document, highlighting key points, entities, and main insights without focusing on any specific aspect."
                    )
                    logger.info(f"Generated insights for document {document_id}")
                    
                    # Create enriched metadata with NLP extraction results
                    enriched_metadata = {
                        **document_metadata,  # Unpack the original metadata
                        "entities": json.dumps(list(all_entities)),
                        "keywords": json.dumps(list(all_keywords)),
                        "topics": json.dumps(list(all_topics)),
                        "categories": json.dumps([f"type_{document_type.value}", "file_pdf"]),
                        "summary": markdown_summary,
                        "insights": insights_content,  # Use generated insights
                        "extraction_processed": True
                    }
                    
                    # Store in PostgreSQL with complete metadata
                    db_service = DatabaseService()
                    try:
                        logger.info(f"Storing document {document_id} in PostgreSQL with complete metadata")
                        db_service.store_document(
                            content=sanitized_text,
                            metadata=enriched_metadata,
                            source_type="pdf",
                            document_type=document_type.value
                        )
                        logger.info(f"Successfully stored document {document_id} in PostgreSQL")
                    except Exception as pg_e:
                        logger.error(f"Error storing document {document_id} in PostgreSQL: {str(pg_e)}\n{traceback.format_exc()}")
                
                # Prepare response with extraction results
                result = {
                    "success": True,
                    "document_id": document_id,
                    "source_type": "pdf",
                    "event_type": "upload",
                    "event_timestamp": datetime.now().isoformat(),
                    "created_by": "api_upload",
                    "chromadb_ids": [document_id] + [chunk.chunk_id for chunk in batch_result],
                    "markdown_summary": markdown_summary,
                    "test_mode": is_test_mode,
                    "chunk_count": len(batch_result),
                    "entities": list(all_entities)[:10],
                    "keywords": list(all_keywords)[:10],
                    "topics": list(all_topics)[:10]
                }
                
                # Return complete result with all metadata and insights
                return {
                    "filename": filename,
                    "content_type": file.content_type,
                    "document_type": document_type,
                    "text_length": len(content),
                    "document_id": document_id,
                    "source_type": "pdf",
                    "event_type": "upload",
                    "event_timestamp": datetime.now().isoformat(),
                    "created_by": "api_upload",
                    "metadata": {
                        "chromadb_ids": result.get("chromadb_ids", []),
                        "entities": list(all_entities)[:10],
                        "keywords": list(all_keywords)[:10],
                        "topics": list(all_topics)[:10]
                    },
                    "markdown_summary": markdown_summary,
                    "test_mode": is_test_mode,
                    "success": True
                }
            except Exception as e:
                logger.error(f"PDF processing error: {str(e)}\n{traceback.format_exc()}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "PDF processing failed",
                        "detail": str(e),
                        "traceback": traceback.format_exc() if is_test_mode else None,
                        "document_id": document_id if 'document_id' in locals() else None,
                        "stage": "pdf_processing"
                    }
                )
        else:
            try:
                # For non-PDF files, use standard text processing
                text_content = content.decode("utf-8", errors="ignore")

                # Extract metadata using our service
                result = await document_handler.upload_document(
                    filename, text_content, document_type, is_test_mode, user_context
                )
                document_id = result.get("document_id")

                if not result.get("success", False):
                    raise ValueError(result.get("error", "Unknown error in text processing"))

                # Generate markdown summary from metadata
                metadata = {
                    "chromadb_ids": result.get("chromadb_ids", []),
                }
                
                markdown_summary = metadata_summarizer.summarize_metadata(
                    document_type=str(document_type),
                    document_id=result.get("document_id", ""),
                    document_name=filename,
                    metadata=metadata
                )

                # Convert to standardized response format
                return {
                    "filename": filename,
                    "content_type": file.content_type,
                    "document_type": document_type,
                    "text_length": len(text_content),
                    "document_id": result.get("document_id", ""),
                    "source_type": result.get("source_type", "text"),
                    "event_type": result.get("event_type", "upload"),
                    "event_timestamp": result.get("event_timestamp", "") if isinstance(result.get("event_timestamp", ""), str) else (result.get("event_timestamp", datetime.now()).isoformat() if hasattr(result.get("event_timestamp", ""), "isoformat") else str(result.get("event_timestamp", ""))),
                    "created_by": result.get("created_by", "api_upload"),
                    "metadata": {
                        "chromadb_ids": result.get("chromadb_ids", []),
                    },
                    "markdown_summary": markdown_summary,
                    "test_mode": is_test_mode,
                    "success": result.get("success", True)
                }
            except Exception as e:
                logger.error(f"Text processing error: {str(e)}\n{traceback.format_exc()}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "Text processing failed",
                        "detail": str(e),
                        "traceback": traceback.format_exc() if is_test_mode else None,
                        "document_id": document_id,
                        "stage": "text_processing"
                    }
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in document upload: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Unexpected error in document upload",
                "detail": str(e),
                "traceback": traceback.format_exc() if is_test_mode else None,
                "document_id": document_id,
                "stage": "upload"
            }
        )


@router.get("/{document_type}/all", response_model=list[Document])
async def get_all_documents(document_type: DocumentType, limit: int = Query(10, ge=1, le=100)):
    """
    Get all documents of a specific type
    
    Returns:
        List of documents with full metadata from both Postgres and ChromaDB
    """
    try:
        logger.info(f"GET /api/documents/{document_type}/all - Fetching up to {limit} documents")
        documents = document_handler.get_all_documents(document_type, limit)
        
        response = []
        for document in documents:
            # Ensure we have metadata
            if "metadata" not in document:
                document["metadata"] = {}
                
            # Ensure document_id is a string
            doc_id = document.get("document_id", "")
            if hasattr(doc_id, "__str__"):  # Convert UUID or other object to string if needed
                doc_id = str(doc_id)
                
            response.append(
                {
                    "document_type": document_type,
                    "document_id": doc_id,
                    "document_name": document.get("document_name", "Untitled Document"),
                    "document_content": document.get("document_content", ""),
                    "metadata": document.get("metadata", {}),
                    "source_type": document.get("metadata", {}).get("source_type", None),
                    "event_type": document.get("metadata", {}).get("event_type", None),
                    "event_timestamp": document.get("metadata", {}).get("event_timestamp", "") if isinstance(document.get("metadata", {}).get("event_timestamp", ""), str) else (document.get("metadata", {}).get("event_timestamp", datetime.now()).isoformat() if hasattr(document.get("metadata", {}).get("event_timestamp", ""), "isoformat") else str(document.get("metadata", {}).get("event_timestamp", ""))),
                    "created_by": document.get("metadata", {}).get("created_by", None),
                    "success": True
                }
            )
        logger.info(f"Found {len(response)} documents of type {document_type}")
        return response
    except Exception as e:
        logger.error(f"Error getting documents of type {document_type}: {str(e)}")
        if "UndefinedTable" in str(e) or "relation" in str(e) and "does not exist" in str(e):
            # Return empty list if table doesn't exist yet
            return []
        # Re-raise other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving documents: {str(e)}"
        )


@router.get("/{document_type}/schemas")
async def get_document_type_schema(document_type: DocumentType):
    """
    Get the JSON schema for a specific document type
    """
    return {
        "document_type": document_type,
        "schema": DOCUMENT_SCHEMAS.get(document_type, {}),
    }


@router.get("/{document_type}/{document_id}", response_model=MarkdownResponse)
async def get_document(document_type: DocumentType, document_id: str, raw_metadata: bool = False):
    """
    Get a specific document by ID
    
    Returns document with its metadata summarized in markdown format
    Optional query parameter raw_metadata=true to include raw metadata in response
    """
    try:
        logger.info(f"GET /api/documents/{document_type}/{document_id} - Request to fetch document")
        document = document_handler.get_document(document_type, document_id)
        if document is None:
            logger.error(f"Document {document_id} not found - checking table structure")
            
            # Try to determine if table exists
            try:
                # See if tables exist for this document type
                db = PostgresDB()
                table_name = f"document_{document_type}"
                table_exists = db.check_table_exists(table_name)
                unified_table_exists = db.check_table_exists("unified_documents")
                
                if not table_exists and not unified_table_exists:
                    logger.error(f"Neither {table_name} nor unified_documents tables exist")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document database tables do not exist for type {document_type}"
                    )
                elif not table_exists:
                    logger.error(f"Table {table_name} does not exist but unified_documents does")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document type {document_type} has no dedicated table"
                    )
                else:
                    # Table exists but no document found
                    logger.error(f"Document with ID {document_id} not found in existing tables")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document with ID {document_id} not found"
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error checking database structure: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID {document_id} not found"
                )
        
        logger.info(f"Document {document_id} found - generating markdown summary")
        
        # Get metadata from document
        metadata = document.get("metadata", {})
        document_name = document.get("document_name", "Untitled Document")
        
        # Get document content - ensure we're using the PostgreSQL content
        document_content = document.get("document_content", "")

        # Check if we already have raw_metadata from document_handler
        # Only search ChromaDB if we don't already have enriched metadata for gong_transcript
        if "raw_metadata" not in document and document_type != DocumentType.GONG_TRANSCRIPT:
            # Try to get additional metadata from ChromaDB
            chromadb_data = document_handler.get_document_metadata_from_chromadb(document_id)
            if chromadb_data and chromadb_data.get("metadata"):
                logger.info(f"Found additional metadata for document {document_id} in ChromaDB")
                # Merge ChromaDB metadata with existing metadata
                chromadb_metadata = chromadb_data.get("metadata", {})
                metadata.update(chromadb_metadata)

                # Add information about found IDs to the metadata
                if "found_ids" in chromadb_data:
                    metadata["chromadb_ids"] = chromadb_data["found_ids"]
        elif "raw_metadata" in document:
            # Use the raw_metadata from the document_handler if available
            if raw_metadata:
                metadata = document.get("raw_metadata", {})

                # For gong_transcript, ensure "content" is renamed to "insights" if it exists
                if document_type == DocumentType.GONG_TRANSCRIPT and "content" in metadata and "insights" not in metadata:
                    metadata["insights"] = metadata.pop("content")
        
        # Generate markdown summary from metadata
        markdown_summary = metadata_summarizer.summarize_metadata(
            document_type=str(document_type),
            document_id=document_id,
            document_name=document_name,
            metadata=metadata
        )
        
        # Prepare response
        response = {
            "document_type": document_type,
            "document_id": document_id,
            "document_name": document_name,
            "document_content": document_content,
            "markdown_summary": markdown_summary,
        }
        
        # Include raw metadata in response if requested
        if raw_metadata:
            # Use the raw_metadata from document_handler if available, otherwise use the merged metadata
            raw_md = document.get("raw_metadata", metadata)

            # For gong_transcript, ensure "content" is renamed to "insights" if it exists
            if document_type == DocumentType.GONG_TRANSCRIPT and "content" in raw_md and "insights" not in raw_md:
                raw_md["insights"] = raw_md.pop("content")

            response["raw_metadata"] = raw_md
        
        logger.info(f"Successfully generated markdown summary for document {document_id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id} of type {document_type}: {str(e)}")
        if "UndefinedTable" in str(e) or "relation" in str(e) and "does not exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No documents of type {document_type} exist yet"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving document: {str(e)}"
        )

@router.delete("/{document_type}/{document_id}")
async def delete_document(document_type: DocumentType, document_id: str):
    """
    Delete a specific document by ID
    """
    document_handler.delete_document(document_type, document_id)
    return {"message": "Document deleted successfully"}
