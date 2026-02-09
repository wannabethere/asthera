"""
Vector store abstraction for agents app.
Supports Chroma and Qdrant using documents.py and qdrant_store.py, similar to the knowledge app.
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document as LangchainDocument

from app.settings import get_settings, VectorStoreType

logger = logging.getLogger(__name__)

# Store name -> (collection_name, tf_idf) for Chroma. Matches dependencies.py and project_reader_qdrant.
STORE_TO_COLLECTION_TFIDF = {
    "table_description": ("table_descriptions", False),
    "alert_knowledge_base": ("alert_knowledge_base", True),
    "column_metadata": ("column_metadata", True),
    "sql_functions": ("sql_functions", True),
}


class VectorStoreClient(ABC):
    """Abstract base class for vector store clients."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the vector store client."""
        pass

    @abstractmethod
    async def get_collection(self, collection_name: str, create_if_not_exists: bool = True):
        """Get or create a collection."""
        pass

    @abstractmethod
    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add documents to a collection."""
        pass

    @abstractmethod
    async def query(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query the vector store."""
        pass

    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Delete documents from a collection."""
        pass

    @abstractmethod
    async def get_embeddings_model(self) -> OpenAIEmbeddings:
        """Get the embeddings model."""
        pass

    @abstractmethod
    def normalize_filter(self, where: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Normalize filter for the backend."""
        pass


class ChromaVectorStoreClient(VectorStoreClient):
    """ChromaDB implementation using DocumentChromaStore from app.storage.documents."""

    def __init__(self, config: Dict[str, Any], embeddings_model: Optional[OpenAIEmbeddings] = None):
        self.config = config
        self._embeddings_model = embeddings_model
        import chromadb
        if config.get("use_local", True):
            persist_directory = config.get("persist_directory")
            if not persist_directory:
                settings = get_settings()
                persist_directory = settings.CHROMA_STORE_PATH
            if not os.path.isabs(persist_directory):
                settings = get_settings()
                persist_directory = str(settings.BASE_DIR / persist_directory)
            self._client = chromadb.PersistentClient(path=persist_directory)
        else:
            self._client = chromadb.HttpClient(
                host=config.get("host", "localhost"),
                port=config.get("port", 8888),
            )
        self._document_stores: Dict[str, Any] = {}
        self._embeddings_model = embeddings_model or self._get_default_embeddings()

    @property
    def client(self):
        return self._client

    def _get_default_embeddings(self) -> OpenAIEmbeddings:
        settings = get_settings()
        return OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )

    def _get_document_store(self, store_name: str):
        """Get or create a DocumentChromaStore for a store (store_name may map to different collection name)."""
        if store_name not in self._document_stores:
            from app.storage.documents import DocumentChromaStore
            coll_tfidf = STORE_TO_COLLECTION_TFIDF.get(store_name)
            if coll_tfidf:
                collection_name, tf_idf = coll_tfidf
            else:
                collection_name = store_name
                tf_idf = self.config.get("tf_idf", False)
            self._document_stores[store_name] = DocumentChromaStore(
                persistent_client=self._client,
                collection_name=collection_name,
                embeddings_model=self._embeddings_model,
                tf_idf=tf_idf,
            )
        return self._document_stores[store_name]

    async def initialize(self) -> None:
        logger.info("ChromaDB client initialized using DocumentChromaStore")

    async def get_collection(self, collection_name: str, create_if_not_exists: bool = True):
        doc_store = self._get_document_store(collection_name)
        return doc_store.collection

    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        doc_store = self._get_document_store(collection_name)
        metadatas = metadatas or [{}] * len(documents)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        langchain_docs = [
            LangchainDocument(page_content=text, metadata={**meta, "id": did})
            for text, meta, did in zip(documents, metadatas, ids)
        ]
        result_ids = doc_store.add_documents(langchain_docs)
        return result_ids if result_ids else ids

    async def query(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        doc_store = self._get_document_store(collection_name)
        if query_texts is None and query_embeddings is None:
            raise ValueError("Either query_texts or query_embeddings must be provided")
        if query_texts:
            query = query_texts[0] if isinstance(query_texts, list) and query_texts else (query_texts or "")
            if not query:
                raise ValueError("query_texts must contain at least one non-empty query")
            results = doc_store.semantic_search(query=query, k=n_results, where=where)
            return {
                "ids": [[r.get("id")] for r in results] if results else [],
                "documents": [[r.get("content")] for r in results] if results else [],
                "metadatas": [[r.get("metadata")] for r in results] if results else [],
                "distances": [[r.get("score", 0.0)] for r in results] if results else [],
            }
        collection = doc_store.collection
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
        )
        return results

    async def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> bool:
        doc_store = self._get_document_store(collection_name)
        if ids:
            doc_store.collection.delete(ids=ids)
        elif where:
            doc_store.collection.delete(where=where)
        else:
            raise ValueError("Either ids or where must be provided")
        return True

    async def get_embeddings_model(self) -> OpenAIEmbeddings:
        return self._embeddings_model

    def normalize_filter(self, where: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not where:
            return where
        formatted = {}
        for k, v in where.items():
            if not k.startswith("$"):
                formatted[k] = {"$in": v} if isinstance(v, list) and v else v
        if len(formatted) <= 1:
            return formatted
        return {"$and": [{k: v} for k, v in formatted.items()]}


class QdrantVectorStoreClient(VectorStoreClient):
    """Qdrant implementation using DocumentQdrantStore from app.storage.qdrant_store."""

    def __init__(self, config: Dict[str, Any], embeddings_model: Optional[OpenAIEmbeddings] = None):
        self.config = config
        self._embeddings_model = embeddings_model or self._get_default_embeddings()
        self._document_stores: Dict[str, Any] = {}
        from app.storage.qdrant_store import QDRANT_AVAILABLE, QdrantClient
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client and langchain-qdrant required for QdrantVectorStoreClient")
        self._client = QdrantClient(
            host=config.get("host", "localhost"),
            port=config.get("port", 6333),
        )

    def _get_default_embeddings(self) -> OpenAIEmbeddings:
        settings = get_settings()
        return OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )

    def _collection_name(self, store_name: str, prefix: Optional[str] = None) -> str:
        """Resolve store name to Qdrant collection name (matches project_reader_qdrant COLLECTION_NAMES)."""
        coll, _ = STORE_TO_COLLECTION_TFIDF.get(store_name, (store_name, False))
        return (prefix or "") + coll

    def _get_document_store(self, store_name: str, collection_prefix: Optional[str] = None):
        """Get or create a DocumentQdrantStore for a store."""
        key = (store_name, collection_prefix or "")
        if key not in self._document_stores:
            from app.storage.qdrant_store import DocumentQdrantStore
            collection_name = self._collection_name(store_name, collection_prefix)
            self._document_stores[key] = DocumentQdrantStore(
                qdrant_client=self._client,
                collection_name=collection_name,
                embeddings_model=self._embeddings_model,
            )
        return self._document_stores[key]

    async def initialize(self) -> None:
        logger.info("Qdrant client initialized using DocumentQdrantStore")

    async def get_collection(self, collection_name: str, create_if_not_exists: bool = True):
        doc_store = self._get_document_store(collection_name)
        return doc_store.qdrant_client

    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        doc_store = self._get_document_store(collection_name)
        metadatas = metadatas or [{}] * len(documents)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        langchain_docs = [
            LangchainDocument(page_content=text, metadata={**meta, "id": did})
            for text, meta, did in zip(documents, metadatas, ids)
        ]
        doc_store.add_documents(langchain_docs)
        return list(ids)

    async def query(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        doc_store = self._get_document_store(collection_name)
        if query_texts is None and query_embeddings is None:
            raise ValueError("Either query_texts or query_embeddings must be provided")
        if query_texts:
            query = query_texts[0] if isinstance(query_texts, list) and query_texts else (query_texts or "")
            if not query:
                raise ValueError("query_texts must contain at least one non-empty query")
            results = doc_store.semantic_search(query=query, k=n_results, where=where)
        else:
            # Agents DocumentQdrantStore does not support query_embedding; would need embedding from query
            results = doc_store.semantic_search(query="", k=n_results, where=where)
        return {
            "ids": [[r.get("id")] for r in results] if results else [],
            "documents": [[r.get("content")] for r in results] if results else [],
            "metadatas": [[r.get("metadata")] for r in results] if results else [],
            "distances": [[r.get("score", 0.0)] for r in results] if results else [],
        }

    async def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> bool:
        doc_store = self._get_document_store(collection_name)
        if ids:
            doc_store.qdrant_client.delete(collection_name=doc_store.collection_name, points_selector=ids)
        elif where:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in where.items() if v is not None]
            if conditions:
                doc_store.qdrant_client.delete(
                    collection_name=doc_store.collection_name,
                    points_selector=Filter(must=conditions),
                )
        else:
            raise ValueError("Either ids or where must be provided")
        return True

    async def get_embeddings_model(self) -> OpenAIEmbeddings:
        return self._embeddings_model

    def normalize_filter(self, where: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return where


def get_vector_store_client(
    embeddings_model: Optional[OpenAIEmbeddings] = None,
    config: Optional[Dict[str, Any]] = None,
):
    """Return a VectorStoreClient (Chroma or Qdrant) based on settings."""
    settings = get_settings()
    config = config or settings.get_vector_store_config()
    vector_store_type = config.get("type", VectorStoreType.CHROMA)
    if vector_store_type == VectorStoreType.CHROMA:
        return ChromaVectorStoreClient(config, embeddings_model)
    if vector_store_type == VectorStoreType.QDRANT:
        return QdrantVectorStoreClient(config, embeddings_model)
    raise ValueError(f"Unsupported vector store type: {vector_store_type}")
