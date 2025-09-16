"""
Document Persistence Service using the same pattern as DefinitionPersistenceService
"""

import uuid
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.session_manager import SessionManager
from app.services.docs.docmodels import Document, DocumentInsight
from app.services.docs.docmodels import DocumentVersion, DocumentInsightVersion
from app.services.docs.document_requests import (
    DocumentSearchRequest, DocumentGetRequest, DocumentInsightsRequest, 
    DocumentDeleteRequest, DocumentResponse, DocumentSearchResponse, 
    DocumentInsightsResponse
)
from app.services.servicebase import BaseService
import chromadb

logger = logging.getLogger(__name__)


class DocumentPersistenceService(BaseService[DocumentSearchRequest, DocumentResponse]):
    """Service for persisting documents and insights using session manager pattern"""
    
    def __init__(self, session_manager: SessionManager, pipelines: Dict[str, Any] = None):
        # Initialize BaseService with empty pipelines since this service doesn't use them
        super().__init__(pipelines or {})
        self.session_manager = session_manager
   
    async def _process_request_impl(self, request: DocumentSearchRequest) -> Any:
        """Implementation of request processing logic for document search."""
        try:
            documents = await self.search_documents(
                query=request.query,
                document_type=request.document_type,
                source_type=request.source_type,
                domain_id=request.domain_id,
                created_by=request.created_by,
                limit=request.limit
            )
            
            return {
                "documents": [self._document_to_dict(doc) for doc in documents],
                "total_count": len(documents)
            }
        except Exception as e:
            logger.error(f"Error processing document search request: {e}")
            raise

    def _create_response(self, event_id: str, result: Any) -> DocumentResponse:
        """Create a response object from the processing result."""
        if isinstance(result, dict) and "error" in result:
            return DocumentResponse(
                success=False,
                message="Document search failed",
                error=result["error"]
            )
        
        return DocumentResponse(
            success=True,
            message="Document search completed successfully",
            data=result
        )

    def _document_to_dict(self, document: Document) -> Dict[str, Any]:
        """Convert Document object to dictionary for serialization."""
        return {
            "id": str(document.id),
            "document_id": str(document.document_id),
            "version": document.version,
            "content": document.content,
            "json_metadata": document.json_metadata,
            "source_type": document.source_type,
            "document_type": document.document_type,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "created_by": document.created_by,
            "domain_id": document.domain_id
        }

    def _insight_to_dict(self, insight: DocumentInsight) -> Dict[str, Any]:
        """Convert DocumentInsight object to dictionary for serialization."""
        return {
            "id": insight.id,
            "document_id": insight.document_id,
            "source_type": insight.source_type,
            "document_type": insight.document_type,
            "event_timestamp": insight.event_timestamp,
            "chromadb_ids": insight.chromadb_ids,
            "event_type": insight.event_type,
            "created_by": insight.created_by,
            "domain_id": insight.domain_id,
            "chunk_content": insight.chunk_content,
            "key_phrases": insight.key_phrases,
            "insights": insight.insights,
            "extraction_config": insight.extraction_config,
            "extraction_date": insight.extraction_date
        }

    async def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """Retrieve document by ID from database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(DocumentVersion).where(DocumentVersion.id == document_id)
                )
                doc_version = result.scalar_one_or_none()
                
                if doc_version:
                    return Document(
                        id=doc_version.id,
                        document_id=doc_version.document_id,
                        version=doc_version.version,
                        content=doc_version.content,
                        json_metadata=doc_version.json_metadata,
                        source_type=doc_version.source_type,
                        document_type=doc_version.document_type,
                        created_at=doc_version.created_at,
                        created_by=doc_version.created_by,
                        domain_id=doc_version.domain_id
                    )
                return None
                
            except Exception as e:
                logger.error(f"Error retrieving document {document_id}: {e}")
                return None
    
    async def get_insights_by_document_id(self, document_id: str) -> List[DocumentInsight]:
        """Retrieve all insights for a document"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(DocumentInsightVersion).where(
                        DocumentInsightVersion.document_id == document_id
                    )
                )
                insight_versions = result.scalars().all()
                
                insights = []
                for insight_version in insight_versions:
                    insight = DocumentInsight(
                        id=insight_version.id,
                        document_id=insight_version.document_id,
                        source_type=insight_version.source_type,
                        document_type=insight_version.document_type,
                        event_timestamp=insight_version.event_timestamp,
                        chromadb_ids=insight_version.chromadb_ids,
                        event_type=insight_version.event_type,
                        created_by=insight_version.created_by,
                        chunk_content=insight_version.chunk_content,
                        key_phrases=insight_version.key_phrases,
                        insights=insight_version.insights,
                        extraction_config=insight_version.extraction_config,
                        extraction_date=insight_version.extraction_date.isoformat() if insight_version.extraction_date else None
                    )
                    insights.append(insight)
                
                return insights
                
            except Exception as e:
                logger.error(f"Error retrieving insights for document {document_id}: {e}")
                return []
    
    async def search_documents(self, 
                             query: str = None,
                             document_type: Optional[str] = None,
                             source_type: Optional[str] = None,
                             domain_id: Optional[str] = None,
                             created_by: Optional[str] = None,
                             limit: int = 10) -> List[Document]:
        """Search documents using database queries"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Build query
                db_query = select(DocumentVersion)
                
                # Add filters
                if document_type:
                    db_query = db_query.where(DocumentVersion.document_type == document_type)
                if source_type:
                    db_query = db_query.where(DocumentVersion.source_type == source_type)
                if domain_id:
                    db_query = db_query.where(DocumentVersion.domain_id == domain_id)
                if created_by:
                    db_query = db_query.where(DocumentVersion.created_by == created_by)
                
                # Add text search if query provided
                if query:
                    db_query = db_query.where(
                        DocumentVersion.content.ilike(f"%{query}%")
                    )
                
                # Add ordering and limit
                db_query = db_query.order_by(DocumentVersion.created_at.desc()).limit(limit)
                
                result = await session.execute(db_query)
                doc_versions = result.scalars().all()
                
                # Convert to Document objects
                documents = []
                for doc_version in doc_versions:
                    document = Document(
                        id=doc_version.id,
                        document_id=doc_version.document_id,
                        version=doc_version.version,
                        content=doc_version.content,
                        json_metadata=doc_version.json_metadata,
                        source_type=doc_version.source_type,
                        document_type=doc_version.document_type,
                        created_at=doc_version.created_at,
                        created_by=doc_version.created_by,
                        domain_id=doc_version.domain_id
                    )
                    documents.append(document)
                
                return documents
                
            except Exception as e:
                logger.error(f"Error searching documents: {e}")
                return []
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document and its insights"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Delete insights first
                await session.execute(
                    select(DocumentInsightVersion).where(
                        DocumentInsightVersion.document_id == document_id
                    )
                )
                
                # Delete document
                await session.execute(
                    select(DocumentVersion).where(DocumentVersion.id == document_id)
                )
                
                await session.commit()
                logger.info(f"Deleted document {document_id}")
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error deleting document {document_id}: {e}")
                return False


    # Convenience methods for different operations
    async def search_documents_async(self, request: DocumentSearchRequest) -> DocumentSearchResponse:
        """Search documents asynchronously using the BaseService pattern."""
        try:
            result = await self.process_request(request)
            if result.success and result.data:
                return DocumentSearchResponse(
                    success=True,
                    documents=result.data.get("documents", []),
                    total_count=result.data.get("total_count", 0)
                )
            else:
                return DocumentSearchResponse(
                    success=False,
                    error=result.error or "Search failed"
                )
        except Exception as e:
            logger.error(f"Error in search_documents_async: {e}")
            return DocumentSearchResponse(
                success=False,
                error=str(e)
            )

    async def get_document_async(self, request: DocumentGetRequest) -> DocumentResponse:
        """Get a single document asynchronously."""
        try:
            document = await self.get_document_by_id(request.document_id)
            if document:
                return DocumentResponse(
                    success=True,
                    message="Document retrieved successfully",
                    data=self._document_to_dict(document)
                )
            else:
                return DocumentResponse(
                    success=False,
                    message="Document not found",
                    error="Document not found"
                )
        except Exception as e:
            logger.error(f"Error in get_document_async: {e}")
            return DocumentResponse(
                success=False,
                message="Error retrieving document",
                error=str(e)
            )

    async def get_document_insights_async(self, request: DocumentInsightsRequest) -> DocumentInsightsResponse:
        """Get document insights asynchronously."""
        try:
            insights = await self.get_insights_by_document_id(request.document_id)
            return DocumentInsightsResponse(
                success=True,
                insights=[self._insight_to_dict(insight) for insight in insights],
                total_count=len(insights)
            )
        except Exception as e:
            logger.error(f"Error in get_document_insights_async: {e}")
            return DocumentInsightsResponse(
                success=False,
                error=str(e)
            )

    async def delete_document_async(self, request: DocumentDeleteRequest) -> DocumentResponse:
        """Delete a document asynchronously."""
        try:
            success = await self.delete_document(request.document_id)
            if success:
                return DocumentResponse(
                    success=True,
                    message="Document deleted successfully"
                )
            else:
                return DocumentResponse(
                    success=False,
                    message="Failed to delete document",
                    error="Delete operation failed"
                )
        except Exception as e:
            logger.error(f"Error in delete_document_async: {e}")
            return DocumentResponse(
                success=False,
                message="Error deleting document",
                error=str(e)
            )


# Factory function following the same pattern as DefinitionPersistenceService
def create_document_persistence_service(session_manager: SessionManager) -> DocumentPersistenceService:
    """Factory function to create DocumentPersistenceService"""
    return DocumentPersistenceService(session_manager)
