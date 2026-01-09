"""
Vector Store Abstraction
Supports multiple vector store backends (ChromaDB, Qdrant, Pinecone)
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import chromadb
from langchain_openai import OpenAIEmbeddings

from app.core.settings import get_settings, VectorStoreType

logger = logging.getLogger(__name__)


class VectorStoreClient(ABC):
    """Abstract base class for vector store clients"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the vector store client"""
        pass
    
    @abstractmethod
    async def get_collection(self, collection_name: str, create_if_not_exists: bool = True):
        """Get or create a collection"""
        pass
    
    @abstractmethod
    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Add documents to a collection"""
        pass
    
    @abstractmethod
    async def query(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query the vector store"""
        pass
    
    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Delete documents from a collection"""
        pass
    
    @abstractmethod
    async def get_embeddings_model(self) -> OpenAIEmbeddings:
        """Get the embeddings model"""
        pass


class ChromaVectorStoreClient(VectorStoreClient):
    """ChromaDB implementation of vector store client"""
    
    def __init__(self, config: Dict[str, Any], embeddings_model: Optional[OpenAIEmbeddings] = None):
        """Initialize ChromaDB client"""
        self.config = config
        self._embeddings_model = embeddings_model
        
        if config.get("use_local", True):
            self._client = chromadb.PersistentClient(path=config.get("persist_directory", "./chroma_db"))
        else:
            self._client = chromadb.HttpClient(
                host=config.get("host", "localhost"),
                port=config.get("port", 8888)
            )
        
        self._collections: Dict[str, chromadb.Collection] = {}
    
    @property
    def client(self):
        """Get the underlying ChromaDB client (for backward compatibility)"""
        return self._client
    
    async def initialize(self) -> None:
        """Initialize the client"""
        logger.info("ChromaDB client initialized")
    
    async def get_collection(self, collection_name: str, create_if_not_exists: bool = True):
        """Get or create a collection"""
        if collection_name not in self._collections:
            try:
                collection = self._client.get_collection(name=collection_name)
                self._collections[collection_name] = collection
            except Exception:
                if create_if_not_exists:
                    collection = self._client.create_collection(name=collection_name)
                    self._collections[collection_name] = collection
                else:
                    raise
        
        return self._collections[collection_name]
    
    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Add documents to a collection"""
        collection = await self.get_collection(collection_name)
        
        # Generate embeddings if not provided
        embeddings_model = await self.get_embeddings_model()
        embeddings = await embeddings_model.aembed_documents(documents)
        
        # Generate IDs if not provided
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # Add to collection
        collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas or [{}] * len(documents),
            ids=ids
        )
        
        return ids
    
    async def query(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query the vector store"""
        collection = await self.get_collection(collection_name)
        
        if query_embeddings is None and query_texts is not None:
            embeddings_model = await self.get_embeddings_model()
            query_embeddings = await embeddings_model.aembed_documents(query_texts)
        
        if query_embeddings is None:
            raise ValueError("Either query_texts or query_embeddings must be provided")
        
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where
        )
        
        return results
    
    async def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Delete documents from a collection"""
        collection = await self.get_collection(collection_name)
        
        if ids:
            collection.delete(ids=ids)
        elif where:
            collection.delete(where=where)
        else:
            raise ValueError("Either ids or where must be provided")
        
        return True
    
    async def get_embeddings_model(self) -> OpenAIEmbeddings:
        """Get the embeddings model"""
        if self._embeddings_model is None:
            settings = get_settings()
            self._embeddings_model = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY
            )
        return self._embeddings_model


class QdrantVectorStoreClient(VectorStoreClient):
    """Qdrant implementation of vector store client (placeholder)"""
    
    def __init__(self, config: Dict[str, Any], embeddings_model: Optional[OpenAIEmbeddings] = None):
        """Initialize Qdrant client"""
        self.config = config
        self._embeddings_model = embeddings_model
        # TODO: Implement Qdrant client
        raise NotImplementedError("Qdrant client not yet implemented")
    
    async def initialize(self) -> None:
        pass
    
    async def get_collection(self, collection_name: str, create_if_not_exists: bool = True):
        raise NotImplementedError
    
    async def add_documents(self, collection_name: str, documents: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, ids: Optional[List[str]] = None) -> List[str]:
        raise NotImplementedError
    
    async def query(self, collection_name: str, query_texts: Optional[List[str]] = None, query_embeddings: Optional[List[List[float]]] = None, n_results: int = 10, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError
    
    async def delete(self, collection_name: str, ids: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None) -> bool:
        raise NotImplementedError
    
    async def get_embeddings_model(self) -> OpenAIEmbeddings:
        if self._embeddings_model is None:
            settings = get_settings()
            self._embeddings_model = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY
            )
        return self._embeddings_model


def get_vector_store_client(
    embeddings_model: Optional[OpenAIEmbeddings] = None,
    config: Optional[Dict[str, Any]] = None
) -> VectorStoreClient:
    """
    Factory function to get a vector store client based on settings
    
    Args:
        embeddings_model: Optional embeddings model
        config: Optional configuration override
        
    Returns:
        VectorStoreClient instance
    """
    settings = get_settings()
    config = config or settings.get_vector_store_config()
    
    vector_store_type = config.get("type", VectorStoreType.CHROMA)
    
    if vector_store_type == VectorStoreType.CHROMA:
        return ChromaVectorStoreClient(config, embeddings_model)
    elif vector_store_type == VectorStoreType.QDRANT:
        return QdrantVectorStoreClient(config, embeddings_model)
    else:
        raise ValueError(f"Unsupported vector store type: {vector_store_type}")

