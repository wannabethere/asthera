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
from app.utils.history import DomainManager
from app.schemas.docs.docmodels import Document, DocumentInsight
from app.schemas.docs.docmodels import DocumentVersion, DocumentInsightVersion
import chromadb

logger = logging.getLogger(__name__)


class DocumentPersistenceService:
    """Service for persisting documents and insights using session manager pattern"""
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
        self.ingestion_service = None
    
    def _get_ingestion_service(self, config = None, 
                             chroma_client: chromadb.PersistentClient = None):
        """Get or create ingestion service instance"""
        from app.dataingest.docingest_insights import DocumentIngestionService, ProcessingConfig
        
        if self.ingestion_service is None:
            self.ingestion_service = DocumentIngestionService(
                session_manager=self.session_manager,
                domain_manager=self.domain_manager,
                config=config or ProcessingConfig(),
                chroma_client=chroma_client
            )
        return self.ingestion_service
    
    async def persist_document(self, 
                             input_data: Union[str, Dict],
                             input_type: str,
                             source_type: str,
                             document_type: str,
                             created_by: str,
                             domain_id: str,
                             questions: Optional[List[str]] = None,
                             metadata: Optional[Dict] = None,
                             event_type: str = "document_ingestion",
                             config = None,
                             chroma_client: chromadb.PersistentClient = None) -> Tuple[Document, DocumentInsight]:
        """Persist document and insights using session manager pattern"""
        
        # Get ingestion service
        ingestion_service = self._get_ingestion_service(config, chroma_client)
        
        # Use the ingestion service to process and store the document
        return await ingestion_service.ingest_document(
            input_data=input_data,
            input_type=input_type,
            source_type=source_type,
            document_type=document_type,
            created_by=created_by,
            domain_id=domain_id,
            questions=questions,
            metadata=metadata,
            event_type=event_type
        )
    
    async def persist_document_auto(self,
                                  input_data: Union[str, Dict],
                                  source_type: str,
                                  document_type: str,
                                  created_by: str,
                                  domain_id: str,
                                  questions: Optional[List[str]] = None,
                                  metadata: Optional[Dict] = None,
                                  event_type: str = "document_ingestion",
                                  config = None,
                                  chroma_client: chromadb.PersistentClient = None) -> Tuple[Document, DocumentInsight]:
        """Auto-detect document type and persist using session manager pattern"""
        
        # Get ingestion service
        ingestion_service = self._get_ingestion_service(config, chroma_client)
        
        # Use auto-detection
        return await ingestion_service.ingest_document_auto(
            input_data=input_data,
            source_type=source_type,
            document_type=document_type,
            created_by=created_by,
            domain_id=domain_id,
            questions=questions,
            metadata=metadata,
            event_type=event_type
        )
    
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


# Factory function following the same pattern as DefinitionPersistenceService
def create_document_persistence_service(session_manager: SessionManager, 
                                      domain_manager: DomainManager) -> DocumentPersistenceService:
    """Factory function to create DocumentPersistenceService"""
    return DocumentPersistenceService(session_manager, domain_manager)
