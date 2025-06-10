from typing import Optional, Dict, Any, List
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api.models.Collection import Collection
import logging
from app.settings import get_settings

logger = logging.getLogger(__name__)

class CollectionManager:
    """Manager for handling ChromaDB collections"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = self._initialize_client()
        self._collections: Dict[str, Collection] = {}
        
    def _initialize_client(self) -> chromadb.Client:
        """Initialize ChromaDB client based on settings"""
        try:
            if self.settings.CHROMA_USE_LOCAL:
                # Use local persistent client
                return chromadb.PersistentClient(
                    path=self.settings.CHROMA_PERSIST_DIRECTORY,
                    settings=ChromaSettings(
                        anonymized_telemetry=False
                    )
                )
            else:
                # Use HTTP client
                return chromadb.HttpClient(
                    host=self.settings.CHROMA_HOST,
                    port=self.settings.CHROMA_PORT,
                    settings=ChromaSettings(
                        anonymized_telemetry=False
                    )
                )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
            
    def get_collection(self, collection_name: str) -> Collection:
        """
        Get or create a ChromaDB collection
        
        Args:
            collection_name: Name of the collection to get or create
            
        Returns:
            Collection: ChromaDB collection instance
        """
        try:
            # Return cached collection if exists
            if collection_name in self._collections:
                return self._collections[collection_name]
            
            # Try to get existing collection
            try:
                collection = self.client.get_collection(collection_name)
            except ValueError:
                # Create new collection if it doesn't exist
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"description": f"Collection for {collection_name}"}
                )
            
            # Cache the collection
            self._collections[collection_name] = collection
            return collection
            
        except Exception as e:
            logger.error(f"Error getting/creating collection {collection_name}: {e}")
            raise
            
    def list_collections(self) -> List[str]:
        """List all available collections"""
        try:
            return [col.name for col in self.client.list_collections()]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []
            
    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection
        
        Args:
            collection_name: Name of the collection to delete
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            self.client.delete_collection(collection_name)
            if collection_name in self._collections:
                del self._collections[collection_name]
            return True
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            return False
            
    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        Add documents to a collection
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: Optional list of metadata dictionaries
            ids: Optional list of document IDs
            
        Returns:
            bool: True if addition was successful
        """
        try:
            collection = self.get_collection(collection_name)
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            logger.error(f"Error adding documents to collection {collection_name}: {e}")
            return False
            
    def query_collection(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query a collection
        
        Args:
            collection_name: Name of the collection to query
            query_texts: List of query texts
            n_results: Number of results to return
            where: Optional metadata filter
            
        Returns:
            Dict containing query results
        """
        try:
            collection = self.get_collection(collection_name)
            results = collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Error querying collection {collection_name}: {e}")
            return {
                "ids": [],
                "distances": [],
                "metadatas": [],
                "documents": []
            } 