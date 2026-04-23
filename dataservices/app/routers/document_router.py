"""
Document Router for DataServices using Document Persistence Service and Doc Insights
Provides the same interfaces as the original documents.py router
"""

import uuid
import logging
import traceback
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import our services and schemas
from app.service.document_persistence_service import DocumentPersistenceService, create_document_persistence_service
from app.dataingest.docingest_insights import DocumentIngestionService, create_ingestion_service, ProcessingConfig
from app.schemas.document_schemas import (
    DocumentType, DocumentSource, TestMode, Document, MarkdownResponse, 
    UploadedDocument, DOCUMENT_SCHEMAS, UNIFIED_DOCUMENT_SCHEMA
)
from app.schemas.docs.docmodels import Document as DocModel, DocumentInsight
from app.core.session_manager import SessionManager
from app.utils.history import DomainManager
from app.core.settings import ServiceConfig
from app.core.dependencies import get_async_db_session

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Global service instances (will be initialized in startup)
document_persistence_service: Optional[DocumentPersistenceService] = None
document_ingestion_service: Optional[DocumentIngestionService] = None
session_manager: Optional[SessionManager] = None
domain_manager: Optional[DomainManager] = None

async def get_document_services():
    """Dependency to get document services"""
    global document_persistence_service, document_ingestion_service
    
    if document_persistence_service is None or document_ingestion_service is None:
        # Initialize services
        config = ServiceConfig()
        session_manager = SessionManager(config)
        domain_manager = DomainManager(None)
        
        # Create services (vector store: Chroma or Qdrant from settings)
        document_persistence_service = create_document_persistence_service(session_manager, domain_manager)
        document_ingestion_service = create_ingestion_service(
            session_manager=session_manager,
            domain_manager=domain_manager,
        )
    
    return document_persistence_service, document_ingestion_service

class MetadataSummarizer:
    """Document content and insights summarizer for markdown generation"""
    
    @staticmethod
    def summarize_metadata(document_type: str, document_id: str, document_name: str, 
                          document_content: str, insight, metadata: Dict[str, Any]) -> str:
        """Generate markdown summary from document content and insights"""
        summary_parts = [
            f"# Document Summary",
            f"",
            f"**Document Type:** {document_type}",
            f"**Document ID:** {document_id}",
            f"**Document Name:** {document_name}",
            f"",
            f"## Document Content",
            f"",
            f"{document_content[:2000]}{'...' if len(document_content) > 2000 else ''}",
            f""
        ]
        
        # Add key phrases if available
        if insight.key_phrases and len(insight.key_phrases) > 0:
            summary_parts.extend([
                f"## Key Phrases",
                f"",
                f"{', '.join(insight.key_phrases[:20])}{'...' if len(insight.key_phrases) > 20 else ''}",
                f""
            ])
        
        # Add extracted insights if available
        if insight.insights:
            summary_parts.extend([
                f"## Extracted Insights",
                f""
            ])
            
            # Add business intelligence insights
            if 'business_intelligence' in insight.insights:
                bi_data = insight.insights['business_intelligence']
                summary_parts.append(f"### Business Intelligence")
                if bi_data.get('kpis'):
                    if isinstance(bi_data['kpis'], dict):
                        summary_parts.append(f"**KPIs:** {', '.join(list(bi_data['kpis'].keys())[:10])}")
                    else:
                        summary_parts.append(f"**KPIs:** {', '.join(str(kpi) for kpi in bi_data['kpis'][:10])}")
                if bi_data.get('business_terms'):
                    if isinstance(bi_data['business_terms'], dict):
                        summary_parts.append(f"**Business Terms:** {', '.join(list(bi_data['business_terms'].keys())[:10])}")
                    else:
                        summary_parts.append(f"**Business Terms:** {', '.join(str(term) for term in bi_data['business_terms'][:10])}")
                summary_parts.append("")
            
            # Add entities if available
            if 'entities' in insight.insights:
                entities = insight.insights['entities']
                if entities:
                    if isinstance(entities, dict):
                        summary_parts.extend([
                            f"### Entities",
                            f"**Extracted Entities:** {', '.join(list(entities.keys())[:15])}",
                            f""
                        ])
                    else:
                        summary_parts.extend([
                            f"### Entities",
                            f"**Extracted Entities:** {', '.join(str(entity) for entity in entities[:15])}",
                            f""
                        ])
        
        # Add processing metadata
        summary_parts.extend([
            f"## Processing Information",
            f"",
            f"**Extraction Types:** {', '.join(metadata.get('extraction_types', []))}",
            f"**Key Phrases Count:** {metadata.get('key_phrases_count', 0)}",
            f"**Content Length:** {metadata.get('chunk_content_length', 0)} characters",
            f"**ChromaDB Status:** {metadata.get('chromadb_status', 'Unknown')}",
            f"**Extraction Date:** {metadata.get('extraction_date', 'Unknown')}",
            f""
        ])
        
        return "\n".join(summary_parts)

# Initialize metadata summarizer
metadata_summarizer = MetadataSummarizer()

@router.post("/", response_model=UploadedDocument, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.GENERIC),
    test_mode: TestMode = Form(TestMode.DISABLED),
    user_context: str = Form(None),
    questions: Optional[str] = Form(None),
    domain_id: str = Form("default_domain"),
    created_by: str = Form("api_user")
):
    """
    Upload a document for processing using Document Persistence Service and Doc Insights

    - The document content will be extracted and processed
    - Metadata will be extracted based on document type using advanced extraction
    - Set test_mode=enabled to process the document without writing to the database
    - Response includes all document metadata and insights that would be stored in databases
    - Optional user_context can be provided to customize extraction behavior
    - Optional questions can be provided for targeted extraction
    """
    is_test_mode = test_mode == TestMode.ENABLED
    document_id = None

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

        # Get document services
        persistence_service, ingestion_service = await get_document_services()

        # Determine input type based on file extension
        input_type = _detect_input_type(filename, file.content_type)
        
        # Parse questions if provided
        questions_list = []
        if questions:
            questions_list = [q.strip() for q in questions.split(',') if q.strip()]

        # Prepare metadata
        metadata = {
            "filename": filename,
            "content_type": file.content_type,
            "file_size": len(content),
            "user_context": user_context,
            "test_mode": is_test_mode
        }

        if input_type == "pdf":
            # For PDF files, save to temporary location and process
            temp_path = f"/tmp/{filename}"
            with open(temp_path, "wb") as f:
                f.write(content)
            
            try:
                # Process PDF using ingestion service
                document, insight = await ingestion_service.ingest_document(
                    input_data=temp_path,
                    input_type="pdf",
                    source_type="upload",
                    document_type=document_type.value,
                    created_by=created_by,
                    domain_id=domain_id,
                    questions=questions_list,
                    metadata=metadata,
                    event_type="document_upload"
                )
                
                document_id = str(document.id)
                
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)
                
            except Exception as e:
                # Clean up temp file on error
                Path(temp_path).unlink(missing_ok=True)
                raise e
                
        else:
            # For other file types, process content directly
            if input_type == "text":
                text_content = content.decode("utf-8", errors="ignore")
                document, insight = await ingestion_service.ingest_document(
                    input_data=text_content,
                    input_type="text",
                    source_type="upload",
                    document_type=document_type.value,
                    created_by=created_by,
                    domain_id=domain_id,
                    questions=questions_list,
                    metadata=metadata,
                    event_type="document_upload"
                )
            elif input_type == "json":
                import json
                json_data = json.loads(content.decode("utf-8", errors="ignore"))
                document, insight = await ingestion_service.ingest_document(
                    input_data=json_data,
                    input_type="json",
                    source_type="upload",
                    document_type=document_type.value,
                    created_by=created_by,
                    domain_id=domain_id,
                    questions=questions_list,
                    metadata=metadata,
                    event_type="document_upload"
                )
            else:
                # Default to text processing
                text_content = content.decode("utf-8", errors="ignore")
                document, insight = await ingestion_service.ingest_document(
                    input_data=text_content,
                    input_type="text",
                    source_type="upload",
                    document_type=document_type.value,
                    created_by=created_by,
                    domain_id=domain_id,
                    questions=questions_list,
                    metadata=metadata,
                    event_type="document_upload"
                )
            
            document_id = str(document.id)

        # Generate markdown summary
        markdown_summary = metadata_summarizer.summarize_metadata(
            document_type=document_type.value,
            document_id=document_id,
            document_name=filename,
            document_content=document.content,
            insight=insight,
            metadata={
                "chromadb_ids": insight.chromadb_ids if insight.chromadb_ids else [],
                "extraction_types": insight.extraction_config.get("extraction_types", []) if insight.extraction_config else [],
                "key_phrases_count": len(insight.key_phrases) if insight.key_phrases else 0,
                "chunk_content_length": len(insight.chunk_content) if insight.chunk_content else 0,
                "extraction_date": insight.extraction_date,
                "source_type": insight.source_type,
                "event_type": insight.event_type,
                "chromadb_status": "Success" if insight.chromadb_ids else "Failed or Pending"
            }
        )

        # Return complete result with all metadata and insights
        return {
            "filename": filename,
            "content_type": file.content_type,
            "document_type": document_type,
            "text_length": len(content),
            "document_id": document_id,
            "source_type": insight.source_type,
            "event_type": insight.event_type,
            "event_timestamp": insight.event_timestamp,
            "created_by": insight.created_by,
            "metadata": {
                "chromadb_ids": insight.chromadb_ids,
                "extraction_types": insight.extraction_config.get("extraction_types", []) if insight.extraction_config else [],
                "key_phrases": insight.key_phrases or [],
                "insights_summary": {
                    "has_business_intelligence": "business_intelligence" in (insight.insights or {}),
                    "has_entities": "entities" in (insight.insights or {}),
                    "has_financial_metrics": "financial_metrics" in (insight.insights or {}),
                    "has_compliance_terms": "compliance_terms" in (insight.insights or {})
                }
            },
            "markdown_summary": markdown_summary,
            "test_mode": is_test_mode,
            "success": True
        }

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

@router.get("/{document_type}/all", response_model=List[Document])
async def get_all_documents(
    document_type: DocumentType, 
    limit: int = Query(10, ge=1, le=100),
    domain_id: str = Query("default_domain")
):
    """
    Get all documents of a specific type
    
    Returns:
        List of documents with full metadata from both Postgres and ChromaDB
    """
    try:
        logger.info(f"GET /api/documents/{document_type}/all - Fetching up to {limit} documents")
        
        # Get document services
        persistence_service, ingestion_service = await get_document_services()
        
        # Search documents using persistence service
        documents = await persistence_service.search_documents(
            document_type=document_type.value,
            domain_id=domain_id,
            limit=limit
        )
        
        response = []
        for document in documents:
            # Get insights for each document
            insights = await persistence_service.get_insights_by_document_id(str(document.id))
            
            # Prepare metadata
            metadata = {
                "chromadb_ids": insights[0].chromadb_ids if insights else [],
                "extraction_types": insights[0].extraction_config.get("extraction_types", []) if insights and insights[0].extraction_config else [],
                "key_phrases": insights[0].key_phrases if insights else [],
                "source_type": document.source_type,
                "event_type": insights[0].event_type if insights else "unknown",
                "event_timestamp": insights[0].event_timestamp if insights else document.created_at.isoformat(),
                "created_by": document.created_by,
                "domain_id": document.domain_id
            }
            
            response.append({
                "document_type": document_type,
                "document_id": str(document.id),
                "document_name": f"Document_{str(document.id)[:8]}",
                "document_content": document.content[:1000] + "..." if len(document.content) > 1000 else document.content,
                "metadata": metadata,
                "source_type": document.source_type,
                "event_type": insights[0].event_type if insights else "unknown",
                "event_timestamp": insights[0].event_timestamp if insights else document.created_at.isoformat(),
                "created_by": document.created_by,
                "success": True
            })
        
        logger.info(f"Found {len(response)} documents of type {document_type}")
        return response
        
    except Exception as e:
        logger.error(f"Error getting documents of type {document_type}: {str(e)}")
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
async def get_document(
    document_type: DocumentType, 
    document_id: str, 
    raw_metadata: bool = False,
    domain_id: str = Query("default_domain")
):
    """
    Get a specific document by ID
    
    Returns document with its metadata summarized in markdown format
    Optional query parameter raw_metadata=true to include raw metadata in response
    """
    try:
        logger.info(f"GET /api/documents/{document_type}/{document_id} - Request to fetch document")
        
        # Get document services
        persistence_service, ingestion_service = await get_document_services()
        
        # Get document by ID
        document = await persistence_service.get_document_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )
        
        logger.info(f"Document {document_id} found - generating markdown summary")
        
        # Get insights for the document
        insights = await persistence_service.get_insights_by_document_id(document_id)
        
        # Prepare metadata
        metadata = {
            "chromadb_ids": insights[0].chromadb_ids if insights else [],
            "extraction_types": insights[0].extraction_config.get("extraction_types", []) if insights and insights[0].extraction_config else [],
            "key_phrases": insights[0].key_phrases if insights else [],
            "source_type": document.source_type,
            "event_type": insights[0].event_type if insights else "unknown",
            "event_timestamp": insights[0].event_timestamp if insights else document.created_at.isoformat(),
            "created_by": document.created_by,
            "domain_id": document.domain_id,
            "chunk_content_length": len(insights[0].chunk_content) if insights and insights[0].chunk_content else 0,
            "extraction_date": insights[0].extraction_date if insights else None
        }
        
        # Generate markdown summary from metadata
        markdown_summary = metadata_summarizer.summarize_metadata(
            document_type=document_type.value,
            document_id=document_id,
            document_name=f"Document_{str(document.id)[:8]}",
            metadata=metadata
        )
        
        # Prepare response
        response = {
            "document_type": document_type,
            "document_id": document_id,
            "document_name": f"Document_{str(document.id)[:8]}",
            "document_content": document.content,
            "markdown_summary": markdown_summary,
        }
        
        # Include raw metadata in response if requested
        if raw_metadata:
            response["raw_metadata"] = metadata
        
        logger.info(f"Successfully generated markdown summary for document {document_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id} of type {document_type}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving document: {str(e)}"
        )

@router.delete("/{document_type}/{document_id}")
async def delete_document(document_type: DocumentType, document_id: str):
    """
    Delete a specific document by ID
    """
    try:
        # Get document services
        persistence_service, ingestion_service = await get_document_services()
        
        # Delete document
        success = await persistence_service.delete_document(document_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found or could not be deleted"
            )
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting document: {str(e)}"
        )

@router.post("/search")
async def search_documents(
    query: str = Form(...),
    document_type: Optional[DocumentType] = Form(None),
    source_type: Optional[str] = Form(None),
    domain_id: str = Form("default_domain"),
    limit: int = Form(10, ge=1, le=100),
    use_tfidf: bool = Form(True)
):
    """
    Search documents using semantic and TF-IDF search
    
    - query: Search query text
    - document_type: Optional document type filter
    - source_type: Optional source type filter
    - domain_id: Domain ID for multi-tenant support
    - limit: Maximum number of results (1-100)
    - use_tfidf: Whether to use TF-IDF search (default: True)
    """
    try:
        logger.info(f"Searching documents with query: {query}")
        
        # Get document services
        persistence_service, ingestion_service = await get_document_services()
        
        # Perform search using ingestion service
        if use_tfidf and ingestion_service.chroma_store:
            # Use ChromaDB search with TF-IDF
            search_results = ingestion_service.search_documents(
                query=query,
                document_type=document_type.value if document_type else None,
                k=limit,
                use_tfidf=use_tfidf
            )
        else:
            # Use database search
            documents = await persistence_service.search_documents(
                query=query,
                document_type=document_type.value if document_type else None,
                source_type=source_type,
                domain_id=domain_id,
                limit=limit
            )
            
            # Convert to search results format
            search_results = []
            for doc in documents:
                insights = await persistence_service.get_insights_by_document_id(str(doc.id))
                search_results.append({
                    "document_id": str(doc.id),
                    "content": doc.content,
                    "metadata": {
                        "source_type": doc.source_type,
                        "document_type": doc.document_type,
                        "created_by": doc.created_by,
                        "created_at": doc.created_at.isoformat(),
                        "chromadb_ids": insights[0].chromadb_ids if insights else [],
                        "key_phrases": insights[0].key_phrases if insights else []
                    },
                    "score": 1.0  # Default score for database search
                })
        
        return {
            "query": query,
            "results": search_results,
            "total_results": len(search_results),
            "search_type": "tfidf" if use_tfidf else "database"
        }
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching documents: {str(e)}"
        )

@router.get("/insights/{document_id}")
async def get_document_insights(
    document_id: str,
    insight_type: Optional[str] = Query(None),
    domain_id: str = Query("default_domain")
):
    """
    Get insights for a specific document
    
    - document_id: Document ID
    - insight_type: Optional specific insight type to retrieve
    - domain_id: Domain ID for multi-tenant support
    """
    try:
        logger.info(f"Getting insights for document {document_id}")
        
        # Get document services
        persistence_service, ingestion_service = await get_document_services()
        
        # Get insights
        insights = await persistence_service.get_insights_by_document_id(document_id)
        
        if not insights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No insights found for document {document_id}"
            )
        
        insight = insights[0]
        
        if insight_type:
            # Return specific insight type
            if insight.insights and insight_type in insight.insights:
                return {
                    "document_id": document_id,
                    "insight_type": insight_type,
                    "data": insight.insights[insight_type],
                    "extraction_date": insight.extraction_date
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Insight type {insight_type} not found for document {document_id}"
                )
        else:
            # Return all insights
            return {
                "document_id": document_id,
                "insights": insight.insights or {},
                "extraction_config": insight.extraction_config or {},
                "key_phrases": insight.key_phrases or [],
                "chunk_content": insight.chunk_content or "",
                "extraction_date": insight.extraction_date,
                "chromadb_ids": insight.chromadb_ids
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting insights for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving insights: {str(e)}"
        )

def _detect_input_type(filename: str, content_type: str) -> str:
    """Detect input type based on filename and content type"""
    if filename.lower().endswith('.pdf') or content_type == "application/pdf":
        return "pdf"
    elif filename.lower().endswith('.json') or content_type == "application/json":
        return "json"
    elif filename.lower().endswith('.docx') or content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return "docx"
    elif filename.lower().endswith(('.md', '.wiki', '.txt')):
        return "text"
    else:
        return "text"  # Default to text processing
