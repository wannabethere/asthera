import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models.dbmodels import (
    Base,
    DocumentInsightVersion,
    DocumentVersion,
)
from app.services.database.connection_service import connection_service


class DatabaseService:
    def __init__(self):
        """
        Initialize the database service using the connection service.
        """
        # Initialize PostgreSQL
        Base.metadata.create_all(connection_service.postgres_engine)
        self.session = connection_service.postgres_session
    
    def store_document(
        self, 
        content: str, 
        metadata: Dict = {}, 
        created_by: Optional[str] = None,
        source_type: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> str:
        """
        Store a document in both PostgreSQL and ChromaDB.
        
        Args:
            content: The document content
            metadata: Additional metadata for the document
            created_by: Optional identifier of who created the document
            source_type: Type of source (e.g., 'file', 'web', 'api')
            document_type: Type of document (e.g., 'pdf', 'html', 'text')
            
        Returns:
            str: The document ID
        """
        doc_id = metadata.get("document_id", str(uuid.uuid4()))

        metadata.update({
            "id": doc_id,
            "source_type": source_type,
            "document_type": document_type
        })
        
        # Create initial version
        version = DocumentVersion(
            document_id=uuid.UUID(doc_id),
            version=1,
            content=content,
            json_metadata=metadata or {},
            created_by=created_by,
            source_type=source_type,
            document_type=document_type
        )
        self.session.add(version)
        self.session.commit()
        
        return doc_id
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """
        Retrieve a document by ID.
        
        Args:
            doc_id: The document ID
            
        Returns:
            Optional[Dict]: The document data if found, None otherwise
        """
        version = self.session.query(DocumentVersion).filter(
            DocumentVersion.document_id == uuid.UUID(doc_id)
        ).order_by(DocumentVersion.version.desc()).first()
        
        if not version:
            return None
            
        return {
            "id": str(version.document_id),
            "content": version.content,
            "json_metadata": version.json_metadata,
            "created_at": version.created_at,
            "source_type": version.source_type,
            "document_type": version.document_type,
            "version": version.version
        }
    
    def update_document(
        self, 
        doc_id: str, 
        content: Optional[str] = None, 
        metadata: Optional[Dict] = None, 
        created_by: Optional[str] = None,
        source_type: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> bool:
        """
        Update a document's content and/or metadata.
        
        Args:
            doc_id: The document ID
            content: New content (optional)
            metadata: New metadata (optional)
            created_by: Optional identifier of who made the update
            source_type: Updated source type (optional)
            document_type: Updated document type (optional)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        # Get current version
        current_version = self.session.query(DocumentVersion).filter(
            DocumentVersion.document_id == uuid.UUID(doc_id)
        ).order_by(DocumentVersion.version.desc()).first()
        
        if not current_version:
            return False
            
        new_version = current_version.version + 1
        
        # Update metadata if provided
        if metadata:
            metadata.update({
                "source_type": source_type if source_type is not None else current_version.source_type,
                "document_type": document_type if document_type is not None else current_version.document_type
            })
        
        # Create new version
        version = DocumentVersion(
            document_id=uuid.UUID(doc_id),
            version=new_version,
            content=content if content is not None else current_version.content,
            json_metadata=metadata if metadata is not None else current_version.json_metadata,
            created_by=created_by,
            source_type=source_type if source_type is not None else current_version.source_type,
            document_type=document_type if document_type is not None else current_version.document_type
        )
        self.session.add(version)
        self.session.commit()
        
        return True
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from both PostgreSQL and ChromaDB.
        
        Args:
            doc_id: The document ID
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        # Delete all versions
        result = self.session.query(DocumentVersion).filter(
            DocumentVersion.document_id == uuid.UUID(doc_id)
        ).delete()
        
        if result == 0:
            return False
            
        self.session.commit()
        
        return True

    def get_document_versions(self, doc_id: str) -> List[Dict]:
        """
        Get all versions of a document.
        
        Args:
            doc_id: The document ID
            
        Returns:
            List[Dict]: List of document versions
        """
        versions = self.session.query(DocumentVersion).filter(
            DocumentVersion.document_id == uuid.UUID(doc_id)
        ).order_by(DocumentVersion.version.desc()).all()
        
        return [{
            "id": str(version.document_id),
            "version": version.version,
            "content": version.content,
            "json_metadata": version.json_metadata,
            "created_at": version.created_at,
            "created_by": version.created_by,
            "source_type": version.source_type,
            "document_type": version.document_type
        } for version in versions]
    
    def add_document_insight(
        self,
        document_id: str,
        phrases: List[str],
        insight: Optional[Dict] = None,
        extracted_entities: Optional[Dict] = None,
        ner_text: Optional[str] = None,
        chromadb_ids: Optional[List[str]] = None,
        event_type: Optional[str] = None,
        created_by: Optional[str] = None,
        source_type: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> str:
        """
        Add an insight event for a document.
        
        Args:
            document_id: The ID of the document
            phrases: List of phrases associated with the insight
            insight: JSON data containing insight information
            extracted_entities: JSON data containing extracted entities
            ner_text: Processed text from NER
            chromadb_ids: List of associated ChromaDB chunk IDs
            event_type: Type of the insight event
            created_by: Optional identifier of who created the insight
            source_type: Type of source for the insight
            document_type: Type of document for the insight
            
        Returns:
            str: The ID of the created insight event
        """
        # Verify document exists
        doc_version = self.session.query(DocumentVersion).filter(
            DocumentVersion.document_id == uuid.UUID(document_id)
        ).first()
        
        if not doc_version:
            raise ValueError(f"Document with ID {document_id} not found")
            
        insight_id = str(uuid.uuid4())
        
        metadata = {}
        metadata["id"] = insight_id
        metadata["phrases"] = " ".join(phrases)
        metadata["insight"] = json.dumps(insight)
        metadata["extracted_entities"] = json.dumps(extracted_entities)
        metadata["ner_text"] = ner_text
        metadata["chromadb_ids"] = " ".join(chromadb_ids) if chromadb_ids else ""
        metadata["event_type"] = event_type
        metadata["source_type"] = source_type if source_type is not None else doc_version.source_type
        metadata["document_type"] = document_type if document_type is not None else doc_version.document_type

        # Create initial version
        version = DocumentInsightVersion(
            insight_id=uuid.UUID(insight_id),
            version=1,
            phrases=phrases if phrases is not None else [],
            insight=insight if insight is not None else {},
            extracted_entities=extracted_entities if extracted_entities is not None else {},
            ner_text=ner_text if ner_text is not None else "",
            event_timestamp=datetime.now(timezone.utc),
            chromadb_ids=chromadb_ids if chromadb_ids is not None else [],
            event_type=event_type if event_type is not None else "",
            created_by=created_by,
            source_type=source_type if source_type is not None else doc_version.source_type,
            document_type=document_type if document_type is not None else doc_version.document_type
        )
        version_dict = {
            "id": str(version.id),
            "insight_id": str(version.insight_id),
            "version": version.version,
            "phrases": version.phrases,
            "insight": version.insight,
            "extracted_entities": version.extracted_entities,
            "ner_text": version.ner_text,
            "event_timestamp": version.event_timestamp.isoformat(),
            "chromadb_ids": version.chromadb_ids,
            "event_type": version.event_type,
            "created_by": version.created_by,
            "source_type": version.source_type,
            "document_type": version.document_type
        }
        self.session.add(version)
        self.session.commit()
        
        return insight_id
    
    def update_document_insight(
        self,
        insight_id: str,
        phrases: Optional[List[str]] = None,
        insight: Optional[Dict] = None,
        extracted_entities: Optional[Dict] = None,
        ner_text: Optional[str] = None,
        chromadb_ids: Optional[List[str]] = None,
        event_type: Optional[str] = None,
        created_by: Optional[str] = None,
        source_type: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> bool:
        """
        Update an insight event.
        
        Args:
            insight_id: The ID of the insight event
            phrases: New phrases (optional)
            insight: New insight data (optional)
            extracted_entities: New extracted entities (optional)
            ner_text: New NER text (optional)
            chromadb_ids: New ChromaDB IDs (optional)
            event_type: New event type (optional)
            created_by: Optional identifier of who made the update
            source_type: Updated source type (optional)
            document_type: Updated document type (optional)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        # Get current version
        current_version = self.session.query(DocumentInsightVersion).filter(
            DocumentInsightVersion.insight_id == uuid.UUID(insight_id)
        ).order_by(DocumentInsightVersion.version.desc()).first()
        
        if not current_version:
            return False
            
        new_version = current_version.version + 1
        
        # Create new version
        version = DocumentInsightVersion(
            insight_id=uuid.UUID(insight_id),
            version=new_version,
            phrases=phrases if phrases is not None else current_version.phrases,
            insight=insight if insight is not None else current_version.insight,
            extracted_entities=extracted_entities if extracted_entities is not None else current_version.extracted_entities,
            ner_text=ner_text if ner_text is not None else current_version.ner_text,
            event_timestamp=current_version.event_timestamp,
            chromadb_ids=chromadb_ids if chromadb_ids is not None else current_version.chromadb_ids,
            event_type=event_type if event_type is not None else current_version.event_type,
            created_by=created_by,
            source_type=source_type if source_type is not None else current_version.source_type,
            document_type=document_type if document_type is not None else current_version.document_type
        )
        self.session.add(version)
        self.session.commit()
        
        return True
    
    def get_insight_versions(self, insight_id: str) -> List[Dict]:
        """
        Get all versions of an insight event.
        
        Args:
            insight_id: The insight event ID
            
        Returns:
            List[Dict]: List of insight versions
        """
        versions = self.session.query(DocumentInsightVersion).filter(
            DocumentInsightVersion.insight_id == uuid.UUID(insight_id)
        ).order_by(DocumentInsightVersion.version.desc()).all()
        
        return [{
            "id": str(version.insight_id),
            "version": version.version,
            "phrases": version.phrases,
            "insight": version.insight,
            "extracted_entities": version.extracted_entities,
            "ner_text": version.ner_text,
            "event_timestamp": version.event_timestamp,
            "chromadb_ids": version.chromadb_ids,
            "event_type": version.event_type,
            "created_at": version.created_at,
            "created_by": version.created_by,
            "source_type": version.source_type,
            "document_type": version.document_type
        } for version in versions]
    
    def delete_document_insight(self, insight_id: str) -> bool:
        """
        Delete an insight event.
        
        Args:
            insight_id: The ID of the insight event
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        # Delete all versions
        result = self.session.query(DocumentInsightVersion).filter(
            DocumentInsightVersion.insight_id == uuid.UUID(insight_id)
        ).delete()
        
        if result == 0:
            return False
            
        self.session.commit()
        
        return True
    

if __name__ == "__main__":
    # Initialize the database service
    from datetime import datetime

    from app.services.database.connection_service import connection_service
    db_service = DatabaseService()
    
    # Test document creation
    test_doc = {
        "content": "This is a test document",
        "metadata": {
            "title": "Test Document",
            "author": "Test Author",
            "category": "Test"
        },
        "source_type": "file",
        "document_type": "pdf"
    }
    
    # Create a document
    doc_id = db_service.store_document(
        content=test_doc["content"],
        metadata=test_doc["metadata"],
        source_type=test_doc["source_type"],
        document_type=test_doc["document_type"]
    )
    print(f"Created document with ID: {doc_id}")
    
    # Get the document
    doc = db_service.get_document(doc_id)
    print(f"Retrieved document: {doc}")
    
    # Update the document
    updated_metadata = {
        "title": "Updated Test Document",
        "author": "Updated Author",
        "category": "Updated Category"
    }
    success = db_service.update_document(
        doc_id=doc_id,
        content="This is an updated test document",
        metadata=updated_metadata,
        source_type="web",
        document_type="html"
    )
    print(f"Document update successful: {success}")
    
    # Get document versions
    versions = db_service.get_document_versions(doc_id)
    print(f"Document versions: {versions}")
    
    # Create an insight for the document
    insight_id = db_service.add_document_insight(
        document_id=doc_id,
        phrases=["test phrase 1", "test phrase 2"],
        insight={"key": "value"},
        extracted_entities={"entity": "value"},
        ner_text="Named entity recognition text",
        chromadb_ids=["id1", "id2"],
        event_type="test_event",
        source_type="api",
        document_type="text"
    )
    print(f"Created insight with ID: {insight_id}")
    
    # Get insight versions
    insight_versions = db_service.get_insight_versions(insight_id)
    print(f"Insight versions: {insight_versions}")
    
    # Update the insight
    update_success = db_service.update_document_insight(
        insight_id=insight_id,
        phrases=["updated phrase 1", "updated phrase 2"],
        insight={"updated_key": "updated_value"},
        source_type="web",
        document_type="html"
    )
    print(f"Insight update successful: {update_success}")
    
    # Get updated insight versions
    updated_insight_versions = db_service.get_insight_versions(insight_id)
    print(f"Updated insight versions: {updated_insight_versions}")
    
    # Delete the insight
    delete_success = db_service.delete_document_insight(insight_id)
    print(f"Insight deletion successful: {delete_success}")
    
    # Delete the document
    delete_doc_success = db_service.delete_document(doc_id)
    print(f"Document deletion successful: {delete_doc_success}")
    
    # Clean up
    db_service.session.close()