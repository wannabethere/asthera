#!/usr/bin/env python3
import json
import uuid
import logging
from typing import Dict, List, Any, Optional, Union

from app.config.settings import get_settings
from app.services.vectorstore.documentstore import DocumentChromaStore
from ..storage.base import IStorage

logger = logging.getLogger(__name__)

class ChromaDBStorage(IStorage):
    """
    Storage implementation for ChromaDB vector database.
    Handles storing documents, vectors, and insights in ChromaDB collections.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ChromaDB storage.
        
        Args:
            config: Configuration parameters including collection names
        """
        self.config = config or {}
        self.settings = get_settings()
        
        # Set default collection names
        self.documents_collection = self.config.get("documents_collection", "documents")
        self.chunks_collection = self.config.get("chunks_collection", "document_chunks")
        self.insights_collection = self.config.get("insights_collection", "insights")
        self.summaries_collection = self.config.get("summaries_collection", "document_summaries")
        self.key_facts_collection = self.config.get("key_facts_collection", "key_facts")
        
        # Flag to enable/disable debug logging
        self.debug = self.config.get("debug", False)
    
    def store_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a full document in ChromaDB.
        
        Args:
            document: The document to store
            
        Returns:
            Result dictionary with status and document ID
        """
        try:
            chroma_store = DocumentChromaStore(collection_name=self.documents_collection)
            
            # Generate a document ID if not provided
            doc_id = document.get("id", "") or str(uuid.uuid4())
            
            # Extract text content and metadata
            content = document.get("content", "")
            metadata = document.get("metadata", {})
            
            # Add document ID to metadata if not present
            if "document_id" not in metadata:
                metadata["document_id"] = doc_id
            
            # Store in ChromaDB
            self._log_info(f"Storing document {doc_id} in ChromaDB collection '{self.documents_collection}'")
            chroma_store.collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata]
            )
            
            return {
                "success": True,
                "document_id": doc_id,
                "collection": self.documents_collection
            }
        except Exception as e:
            logger.error(f"Error storing document in ChromaDB: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def store_chunks(self, chunks: List[Dict[str, Any]], parent_doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Store document chunks in ChromaDB.
        
        Args:
            chunks: List of document chunks to store
            parent_doc_id: Optional parent document ID
            
        Returns:
            List of result dictionaries with status and chunk IDs
        """
        results = []
        
        try:
            chroma_store = DocumentChromaStore(collection_name=self.chunks_collection)
            
            for chunk in chunks:
                try:
                    # Generate a chunk ID if not provided
                    if chunk.get("id"):
                        chunk_id = chunk["id"]
                    elif parent_doc_id:
                        chunk_id = f"{parent_doc_id}_chunk{len(results) + 1}"
                    else:
                        chunk_id = str(uuid.uuid4())
                    
                    # Extract text content and metadata
                    content = chunk.get("text", chunk.get("content", ""))
                    metadata = chunk.get("metadata", {})
                    
                    # Skip empty chunks
                    if not content or content.strip() == "":
                        continue
                    
                    # Add IDs to metadata if not present
                    if "document_id" not in metadata:
                        metadata["document_id"] = chunk_id
                    if parent_doc_id and "parent_document_id" not in metadata:
                        metadata["parent_document_id"] = parent_doc_id
                    
                    # Add chunk type and number if provided
                    if "chunk_type" in chunk:
                        metadata["chunk_type"] = chunk["chunk_type"]
                    if "chunk_num" in chunk:
                        metadata["chunk_num"] = chunk["chunk_num"]
                    
                    # Store in ChromaDB
                    self._log_info(f"Storing chunk {chunk_id} in ChromaDB collection '{self.chunks_collection}'")
                    chroma_store.collection.add(
                        ids=[chunk_id],
                        documents=[content],
                        metadatas=[metadata]
                    )
                    
                    results.append({
                        "success": True,
                        "chunk_id": chunk_id,
                        "parent_document_id": parent_doc_id,
                        "collection": self.chunks_collection
                    })
                except Exception as e:
                    logger.error(f"Error storing chunk in ChromaDB: {e}")
                    results.append({
                        "success": False,
                        "error": str(e)
                    })
        except Exception as e:
            logger.error(f"Error initializing ChromaDB for chunks: {e}")
            results.append({
                "success": False,
                "error": str(e)
            })
        
        return results
    
    def store_insights(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Store document insights in ChromaDB.
        
        Args:
            insights: List of document insights to store
            
        Returns:
            List of result dictionaries with status and insight IDs
        """
        results = []
        
        try:
            chroma_store = DocumentChromaStore(collection_name=self.insights_collection)
            
            for insight in insights:
                try:
                    # Extract original document ID and generate insight ID
                    original_doc_id = insight.get("document_id") or insight.get("call_id", "")
                    insight_id = insight.get("id", "") or str(uuid.uuid4())
                    
                    # Extract text content
                    content = insight.get("content", "")
                    
                    # Prepare metadata with rich information
                    metadata = {
                        "document_id": insight_id,
                        "original_document_id": original_doc_id,
                        "document_type": insight.get("document_type", "document_insights"),
                        "title": insight.get("title", ""),
                        "url": insight.get("url", ""),
                        "source_type": insight.get("source_type", "unknown"),
                        "event_type": "insight"
                    }
                    
                    # Add date information if available
                    if "date" in insight:
                        metadata["date"] = insight["date"]
                    if "date_timestamp" in insight:
                        metadata["date_timestamp"] = insight["date_timestamp"]
                    
                    # Add structured insights as metadata if available
                    if "insights" in insight and isinstance(insight["insights"], dict):
                        insights_data = insight["insights"]
                        for key, value in insights_data.items():
                            if value:
                                metadata[key] = json.dumps(value)
                    
                    # Add additional metadata fields if available
                    for field in ["entities", "keywords", "topics", "categories"]:
                        if field in insight and insight[field]:
                            metadata[field] = json.dumps(insight[field])
                    
                    # Store in ChromaDB
                    self._log_info(f"Storing insight {insight_id} for document {original_doc_id} in ChromaDB collection '{self.insights_collection}'")
                    chroma_store.collection.add(
                        ids=[insight_id],
                        documents=[content],
                        metadatas=[metadata]
                    )
                    
                    results.append({
                        "success": True,
                        "insight_id": insight_id,
                        "document_id": original_doc_id,
                        "collection": self.insights_collection
                    })
                except Exception as e:
                    logger.error(f"Error storing insight in ChromaDB: {e}")
                    results.append({
                        "success": False,
                        "document_id": insight.get("document_id", "unknown"),
                        "error": str(e)
                    })
        except Exception as e:
            logger.error(f"Error initializing ChromaDB for insights: {e}")
            results.append({
                "success": False,
                "error": str(e)
            })
        
        return results
    
    def store_document_chunks(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Store PDF document chunks, summaries, or key facts in ChromaDB based on their vector_type.
        This method routes the document to the appropriate collection based on its metadata.
        
        Args:
            document: The document chunk, summary, or key fact to store
            
        Returns:
            List of result dictionaries with status and IDs
        """
        results = []
        
        try:
            # Determine the appropriate collection based on vector_type in metadata
            metadata = document.get("metadata", {})
            vector_type = metadata.get("vector_type", "chunk")
            
            if vector_type == "summary":
                # Store in summaries collection
                collection_name = self.summaries_collection
            elif vector_type == "key_fact":
                # Store in key facts collection
                collection_name = self.key_facts_collection
            else:
                # Default to chunks collection
                collection_name = self.chunks_collection
            
            chroma_store = DocumentChromaStore(collection_name=collection_name)
            
            # Generate a document ID if not provided
            doc_id = document.get("id", "") or str(uuid.uuid4())
            
            # Extract content
            content = document.get("content", "")
            
            # Skip empty documents
            if not content or content.strip() == "":
                return [{
                    "success": False,
                    "error": "Empty document content"
                }]
            
            # Add document ID to metadata if not present
            if "document_id" not in metadata:
                metadata["document_id"] = doc_id
            
            # Store in ChromaDB
            self._log_info(f"Storing {vector_type} {doc_id} in ChromaDB collection '{collection_name}'")
            chroma_store.collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata]
            )
            
            results.append({
                "success": True,
                "document_id": doc_id,
                "vector_type": vector_type,
                "collection": collection_name
            })
            
        except Exception as e:
            logger.error(f"Error storing document in ChromaDB: {e}")
            results.append({
                "success": False,
                "error": str(e)
            })
        
        return results
    
    def store_gong_chunks(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Special method to store Gong document chunks in ChromaDB.
        This follows the specific chunking strategy from gong_call_ingestion.py.
        
        Args:
            document: The Gong document with unstructured data
            
        Returns:
            List of result dictionaries with status and chunk IDs
        """
        results = []
        
        try:
            chroma_store = DocumentChromaStore(collection_name=self.chunks_collection)
            
            # Generate a consistent document ID as parent ID
            parent_doc_id = document.get("id", "") or str(uuid.uuid4())
            
            # CHUNK 1: Overview & Summary
            chunk1_id = f"{parent_doc_id}_chunk1"
            chunk1_parts = []
            
            if document.get("title"):
                chunk1_parts.append(f"Title: {document['title']}")
            # Add date if available
            if document.get("date"):
                chunk1_parts.append(f"Date: {document['date']}")
            if document.get("brief"):
                chunk1_parts.append(f"Brief: {document['brief']}")
            
            # Add action items
            if document.get("actionItems"):
                action_items_text = "Action Items:\n" + "\n".join(f"- {item}" for item in document["actionItems"])
                chunk1_parts.append(action_items_text)
            
            # Add participants
            if document.get("participants"):
                participants = document["participants"]
                if participants.get("tellius"):
                    # Filter out None values before joining
                    tellius_participants = [p for p in participants["tellius"] if p is not None]
                    chunk1_parts.append("Internal participants: " + ", ".join(tellius_participants))
                if participants.get("nonTellius"):
                    # Filter out None values before joining
                    non_tellius_participants = [p for p in participants["nonTellius"] if p is not None]
                    chunk1_parts.append("External participants: " + ", ".join(non_tellius_participants))
            
            chunk1_text = "\n\n".join(chunk1_parts)
            
            # CHUNK 2 & 3: Outline Parts
            outline_sections = []
            if document.get("outline"):
                for section in document["outline"]:
                    section_title = section.get("section", "")
                    items = section.get("items", [])
                    if section_title and items:
                        section_text = f"Section: {section_title}\n"
                        section_text += "\n".join(f"- {item}" for item in items)
                        outline_sections.append(section_text)
            
            # Split outline into two chunks
            chunk2_sections = []
            chunk3_sections = []
            
            if outline_sections:
                midpoint = len(outline_sections) // 2
                chunk2_sections = outline_sections[:midpoint]
                chunk3_sections = outline_sections[midpoint:]
            
            chunk2_id = f"{parent_doc_id}_chunk2"
            chunk2_parts = []
            if document.get("title"):
                chunk2_parts.append(f"Title: {document['title']} (Outline Part 1)")
            if chunk2_sections:
                chunk2_parts.append("\n\n".join(chunk2_sections))
            chunk2_text = "\n\n".join(chunk2_parts)
            
            chunk3_id = f"{parent_doc_id}_chunk3"
            chunk3_parts = []
            if document.get("title"):
                chunk3_parts.append(f"Title: {document['title']} (Outline Part 2)")
            if chunk3_sections:
                chunk3_parts.append("\n\n".join(chunk3_sections))
            chunk3_text = "\n\n".join(chunk3_parts)
            
            # CHUNK 4: Additional Data (Trackers & Collaboration)
            chunk4_id = f"{parent_doc_id}_chunk4"
            chunk4_parts = []
            
            if document.get("title"):
                chunk4_parts.append(f"Title: {document['title']} (Additional Data)")
            
            # Add trackers
            if document.get("trackers"):
                trackers_text = "Trackers:\n"
                for tracker in document["trackers"]:
                    tracker_name = tracker.get("name", "")
                    tracker_type = tracker.get("type", "")
                    tracker_count = tracker.get("count", 0)
                    trackers_text += f"- {tracker_name} ({tracker_type}): {tracker_count}\n"
                chunk4_parts.append(trackers_text)
            
            # Add collaboration if it exists and has content
            if document.get("collaboration") and document["collaboration"]:
                collab_data = json.dumps(document["collaboration"], indent=2)
                chunk4_parts.append(f"Collaboration: {collab_data}")
            
            chunk4_text = "\n\n".join(chunk4_parts)
            
            # Base metadata for all chunks
            base_metadata = {
                "parent_document_id": parent_doc_id,
                "id": document.get("id", ""),  # Original document ID
                "document_type": "gong_vectordb",
                "title": document.get("title", ""),
                "url": document.get("url", ""),
                "source_type": "gong",
                "event_type": "import",
                # Add date information
                "date": document.get("date", ""),
                "date_timestamp": document.get("date_timestamp", 0)
            }
            
            # Store chunks in ChromaDB
            chunks_to_store = [
                {"id": chunk1_id, "text": chunk1_text, "chunk_type": "overview", "chunk_num": 1},
                {"id": chunk2_id, "text": chunk2_text, "chunk_type": "outline_part1", "chunk_num": 2},
                {"id": chunk3_id, "text": chunk3_text, "chunk_type": "outline_part2", "chunk_num": 3},
            ]
            
            # Only add chunk 4 if it has content
            if chunk4_parts and len(chunk4_parts) > 1:  # More than just the title
                chunks_to_store.append({"id": chunk4_id, "text": chunk4_text, "chunk_type": "additional_data", "chunk_num": 4})
            
            # Store all chunks
            for chunk in chunks_to_store:
                # Skip empty chunks
                if not chunk["text"] or chunk["text"].strip() == "" or chunk["text"].strip() == chunk.get("title", ""):
                    continue
                    
                chunk_metadata = base_metadata.copy()
                chunk_metadata["document_id"] = chunk["id"]
                chunk_metadata["chunk_type"] = chunk["chunk_type"]
                chunk_metadata["chunk_num"] = chunk["chunk_num"]
                
                self._log_info(f"Storing chunk {chunk['chunk_num']} ({chunk['chunk_type']}) for document {parent_doc_id} in ChromaDB")
                chroma_store.collection.add(
                    ids=[chunk["id"]],
                    documents=[chunk["text"]],
                    metadatas=[chunk_metadata]
                )
                
                results.append({
                    "success": True,
                    "chunk_id": chunk["id"],
                    "parent_document_id": parent_doc_id,
                    "chunk_type": chunk["chunk_type"],
                    "collection": self.chunks_collection
                })
            
            self._log_info(f"Successfully stored chunked document {parent_doc_id} in ChromaDB")
        except Exception as e:
            logger.error(f"Error storing Gong document chunks in ChromaDB: {e}")
            results.append({
                "success": False,
                "document_id": document.get("id", "unknown"),
                "error": str(e)
            })
        
        return results
    
    def _log_info(self, message: str) -> None:
        """Log info messages only when debug is enabled."""
        if self.debug:
            logger.info(message) 