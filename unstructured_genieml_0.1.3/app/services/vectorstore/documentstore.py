from typing import Any, Dict, Optional, List
import uuid
import json
import traceback

import chromadb
from chromadb import HttpClient

from app.models.dbmodels import DocumentInsight
from app.config.settings import get_settings


class DocumentChromaStore:
    def __init__(self, collection_name: str = "documents"):
        # Use HTTP client to connect to the server rather than a local persistent client
        settings = get_settings()
        self.client = HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        
    def store_document_insight(self, doc_insight: DocumentInsight) -> List[str]:
        """
        Store a document insight in ChromaDB.
        
        Args:
            doc_insight: The document insight to store
            
        Returns:
            List of ChromaDB IDs for the stored documents
        """
        if not doc_insight or not doc_insight.document:
            print("[CHROMA_STORE] No document insight or content to store")
            return []
            
        try:
            # Prepare metadata for the main document
            metadata = {
                "document_id": doc_insight.document_id,
                "source_type": doc_insight.source_type,
                "document_type": doc_insight.document_type,
                "event_type": doc_insight.event_type,
                "created_by": doc_insight.created_by,
                "event_timestamp": doc_insight.event_timestamp,
                "insight": json.dumps(doc_insight.insight),
                "extracted_entities": json.dumps(doc_insight.extracted_entities),
                "enhanced_insights": ""
            }
            
            # Add phrases as metadata if they exist
            if doc_insight.phrases and len(doc_insight.phrases) > 0:
                # Convert phrases to a list of dictionaries with their metadata
                phrase_metadata = []
                for i, phrase in enumerate(doc_insight.phrases):
                    if isinstance(phrase, dict):
                        # If phrase is already a dict with metadata, use it
                        phrase_metadata.append(phrase)
                    else:
                        # If phrase is just text, create a basic metadata structure
                        phrase_metadata.append({
                            "text": phrase,
                            "index": i
                        })
                metadata["phrases"] = json.dumps(phrase_metadata)
            else:
                metadata["phrases"] = "[]"
            
            # Apply safe type conversion to ensure no None values
            metadata = self._ensure_safe_types(metadata)
            
            # Log metadata to verify structure
            print(f"[CHROMA_STORE] Metadata before storage: {metadata}")
            
            # Store the main document with all metadata
            doc_id = f"doc_{doc_insight.document_id}"
            content = doc_insight.document.content[:100000]  # Truncate if too long
            
            # Add the document to ChromaDB
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            print(f"[CHROMA_STORE] Successfully stored document {doc_id}")
            return [doc_id]
            
        except Exception as e:
            print(f"[CHROMA_STORE] Error storing document: {e}")
            return []
    
    def _ensure_safe_types(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert all values to safe types for ChromaDB (str, int, float, bool).
        This handles UUID objects and other complex types by converting them to strings.
        """
        safe_data = {}
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)):
                safe_data[key] = value
            elif isinstance(value, uuid.UUID):
                safe_data[key] = str(value)
            elif value is None:
                safe_data[key] = ""  # Convert None to empty string
            else:
                # Convert other types to string
                safe_data[key] = str(value)
        return safe_data
        
    def search_similar(self, query: str, n_results: int = 3, filter_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Search for similar documents in ChromaDB"""
        # Ensure filter criteria uses safe types
        if filter_criteria:
            filter_criteria = self._ensure_safe_types(filter_criteria)
            
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=filter_criteria
        )
        return {
            'ids': results['ids'],
            'distances': results['distances'],
            'documents': results['documents']
        } 