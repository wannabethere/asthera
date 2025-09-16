"""
Router for Document Persistence Service API endpoints
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.services.docs.document_persistence_service import DocumentPersistenceService
from app.services.docs.document_requests import (
    DocumentSearchRequest, DocumentGetRequest, DocumentInsightsRequest, 
    DocumentDeleteRequest, DocumentSearchResponse, DocumentInsightsResponse
)
from app.core.dependencies import get_app_state
from app.services.service_container import SQLServiceContainer

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_persistence_service(
    app_state = Depends(get_app_state)
) -> DocumentPersistenceService:
    """Dependency to get DocumentPersistenceService instance from service container"""
    # Get the service container
    container = SQLServiceContainer.get_instance()
    
    # Get the document persistence service
    return container.get_document_persistence_service()


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    request: DocumentSearchRequest,
    service: DocumentPersistenceService = Depends(get_document_persistence_service)
):
    """
    Search for documents using various filters
    
    This endpoint searches for documents using the document persistence service
    with support for text search, document type filtering, and other criteria.
    """
    try:
        logger.info(f"Searching documents with query: {request.query}")
        
        response = await service.search_documents_async(request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching documents: {str(e)}")


@router.get("/{document_id}", response_model=Dict[str, Any])
async def get_document(
    document_id: str,
    service: DocumentPersistenceService = Depends(get_document_persistence_service)
):
    """
    Get a specific document by ID
    
    This endpoint retrieves a single document by its ID using the document persistence service.
    """
    try:
        logger.info(f"Getting document: {document_id}")
        
        request = DocumentGetRequest(document_id=document_id)
        response = await service.get_document_async(request)
        
        if not response.success:
            if "not found" in response.error.lower():
                raise HTTPException(status_code=404, detail=response.error)
            else:
                raise HTTPException(status_code=400, detail=response.error)
        
        return response.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting document: {str(e)}")


@router.get("/{document_id}/insights", response_model=DocumentInsightsResponse)
async def get_document_insights(
    document_id: str,
    service: DocumentPersistenceService = Depends(get_document_persistence_service)
):
    """
    Get insights for a specific document
    
    This endpoint retrieves all insights associated with a document using the document persistence service.
    """
    try:
        logger.info(f"Getting insights for document: {document_id}")
        
        request = DocumentInsightsRequest(document_id=document_id)
        response = await service.get_document_insights_async(request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document insights for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting document insights: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    service: DocumentPersistenceService = Depends(get_document_persistence_service)
):
    """
    Delete a document and its associated insights
    
    This endpoint deletes a document and all its insights using the document persistence service.
    """
    try:
        logger.info(f"Deleting document: {document_id}")
        
        request = DocumentDeleteRequest(document_id=document_id)
        response = await service.delete_document_async(request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return {"message": response.message, "success": response.success}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@router.get("/", response_model=DocumentSearchResponse)
async def list_documents(
    query: Optional[str] = Query(None, description="Search query"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    domain_id: Optional[str] = Query(None, description="Filter by domain ID"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(10, description="Maximum number of results"),
    service: DocumentPersistenceService = Depends(get_document_persistence_service)
):
    """
    List documents with optional filtering
    
    This endpoint lists documents with optional filtering parameters using the document persistence service.
    """
    try:
        logger.info(f"Listing documents with filters: query={query}, type={document_type}")
        
        request = DocumentSearchRequest(
            query=query,
            document_type=document_type,
            source_type=source_type,
            domain_id=domain_id,
            created_by=created_by,
            limit=limit
        )
        
        response = await service.search_documents_async(request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")
