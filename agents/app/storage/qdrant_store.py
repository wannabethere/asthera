"""
Qdrant-backed document store with interface compatible with DocumentChromaStore
so existing indexing processors (DBSchema, TableDescription, etc.) work unchanged.
Used by ProjectReaderQdrant to index sql_meta projects into Qdrant with core_* collections.
"""
import logging
import uuid
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.documents import Document as LangchainDocument

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, Filter, FieldCondition, MatchValue, VectorParams
    try:
        from langchain_qdrant import QdrantVectorStore as LangchainQdrant
    except ImportError:
        from langchain_qdrant import Qdrant as LangchainQdrant
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    LangchainQdrant = None


def _to_qdrant_point_id(s: str):
    """Convert string to valid Qdrant point id (UUID or hash)."""
    try:
        uuid.UUID(s)
        return s
    except (ValueError, AttributeError, TypeError):
        pass
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "qdrant.point." + s))


class QdrantCollectionAdapter:
    """
    Chroma-like .collection adapter so processors that call
    document_store.collection.delete(where={"project_id": x}) work with Qdrant.
    """
    def __init__(self, qdrant_client: "QdrantClient", collection_name: str):
        self._client = qdrant_client
        self._collection_name = collection_name

    def _project_id_filter(self, project_id: str):
        """LangChain Qdrant stores metadata in payload; try metadata.project_id then project_id."""
        return Filter(
            must=[FieldCondition(key="metadata.project_id", match=MatchValue(value=project_id))]
        )

    def delete(self, where: Optional[Dict] = None, ids: Optional[List] = None):
        if ids:
            self._client.delete(collection_name=self._collection_name, points_selector=ids)
            return
        if where and "project_id" in where:
            project_id = where["project_id"]
            scroll_result = self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=self._project_id_filter(project_id),
                limit=10_000,
            )
            point_ids = [p.id for p in scroll_result[0]]
            if point_ids:
                self._client.delete(collection_name=self._collection_name, points_selector=point_ids)
            return
        # delete all: scroll and delete in chunks
        from qdrant_client.models import PointIdsList
        offset = None
        while True:
            result, offset = self._client.scroll(
                collection_name=self._collection_name, limit=100, offset=offset
            )
            if not result:
                break
            self._client.delete(
                collection_name=self._collection_name,
                points_selector=PointIdsList(points=[p.id for p in result]),
            )
            if offset is None:
                break

    def get(self, where: Optional[Dict] = None, **kwargs):
        """Minimal get for compatibility; returns dict with 'ids' and 'metadatas'."""
        if not where:
            result, _ = self._client.scroll(collection_name=self._collection_name, limit=100)
            return {"ids": [str(p.id) for p in result], "metadatas": [p.payload or {} for p in result]}
        if "project_id" in where:
            project_id = where["project_id"]
            result, _ = self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=self._project_id_filter(project_id),
                limit=10_000,
            )
            return {"ids": [str(p.id) for p in result], "metadatas": [p.payload or {} for p in result]}
        return {"ids": [], "metadatas": []}


class DocumentQdrantStore:
    """
    Qdrant document store with the same interface as DocumentChromaStore used by
    indexing processors: add_documents, semantic_search, delete_by_project_id,
    and .collection for clean() (delete by project_id or delete all).
    """

    def __init__(
        self,
        qdrant_client: Optional["QdrantClient"] = None,
        collection_name: str = "default",
        embeddings_model: Optional[Any] = None,
        host: Optional[str] = None,
        port: int = 6333,
        batch_size: int = 200,
    ):
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "Qdrant dependencies not installed. Install with: pip install qdrant-client langchain-qdrant"
            )
        self.collection_name = collection_name
        self.embeddings_model = embeddings_model
        self.batch_size = batch_size
        if qdrant_client is not None:
            self.qdrant_client = qdrant_client
        else:
            host = host or "localhost"
            self.qdrant_client = QdrantClient(host=host, port=port)
        self.vectorstore = None
        self.collection = QdrantCollectionAdapter(self.qdrant_client, self.collection_name)
        self.initialize()

    def initialize(self):
        if self.vectorstore:
            return
        logger.info("Initializing Qdrant store with collection %s", self.collection_name)
        if not self.qdrant_client.collection_exists(self.collection_name):
            test_embedding = self.embeddings_model.embed_query("test")
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=len(test_embedding), distance=Distance.COSINE),
            )
        try:
            self.vectorstore = LangchainQdrant(
                client=self.qdrant_client,
                collection_name=self.collection_name,
                embedding=self.embeddings_model,
            )
        except TypeError:
            self.vectorstore = LangchainQdrant(
                client=self.qdrant_client,
                collection_name=self.collection_name,
                embeddings=self.embeddings_model,
            )
        logger.info("Initialized Qdrant store for collection %s", self.collection_name)

    def add_documents(self, docs: List[Any]):
        """Add documents. Accepts LangchainDocument or dict with 'metadata' and 'data'. Returns dict with documents_written for reader compatibility."""
        if not docs:
            logger.warning("No documents provided to add to the vectorstore.")
            return {"documents_written": 0}

        documents = []
        ids = []
        for doc in docs:
            if isinstance(doc, LangchainDocument):
                documents.append(doc)
                raw_id = doc.metadata.get("id")
                doc_id = str(uuid4()) if raw_id is None else raw_id
                if doc.metadata.get("id") is None:
                    doc.metadata["id"] = doc_id
                ids.append(_to_qdrant_point_id(doc.metadata.get("id", doc_id)))
                continue
            if not isinstance(doc, dict) or "metadata" not in doc or "data" not in doc:
                logger.warning("Skipping invalid document format: %s", type(doc))
                continue
            try:
                from app.storage.documents import create_langchain_doc_util
                document_id, document = create_langchain_doc_util(
                    metadata=doc["metadata"], data=doc["data"]
                )
                if document and document_id:
                    documents.append(document)
                    ids.append(_to_qdrant_point_id(document_id))
            except Exception as e:
                logger.error("Error creating document: %s", e)
                continue

        if not documents:
            return {"documents_written": 0}

        try:
            filtered_documents = filter_complex_metadata(documents)
        except Exception as e:
            logger.warning("Error filtering metadata: %s. Using original documents.", e)
            filtered_documents = documents

        batch_size = getattr(self, "batch_size", 200)
        added = 0
        for start in range(0, len(filtered_documents), batch_size):
            batch_docs = filtered_documents[start : start + batch_size]
            batch_ids = ids[start : start + batch_size]
            try:
                self.vectorstore.add_documents(documents=batch_docs, ids=batch_ids)
                added += len(batch_docs)
            except Exception as e:
                logger.warning("Qdrant batch failed at offset %s: %s", start, e)
        logger.info("Added %s documents to Qdrant collection %s", added, self.collection_name)
        return {"documents_written": added}

    def semantic_search(self, query: str, k: int = 5, where: Optional[Dict] = None) -> List[Dict]:
        """Semantic search. Optional where filter (e.g. project_id) applied in memory if needed."""
        if not self.vectorstore:
            return []
        try:
            if where:
                results = self.vectorstore.similarity_search_with_score(
                    query, k=k * 3
                )  # fetch extra then filter
                filtered = []
                for doc, score in results:
                    meta = getattr(doc, "metadata", {}) or {}
                    if all(meta.get(k) == v for k, v in where.items()):
                        filtered.append({"content": doc.page_content, "metadata": meta, "score": float(score), "id": meta.get("id")})
                    if len(filtered) >= k:
                        break
                return filtered[:k]
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            return [
                {"content": doc.page_content, "metadata": getattr(doc, "metadata", {}), "score": float(score), "id": getattr(doc, "metadata", {}).get("id")}
                for doc, score in results
            ]
        except Exception as e:
            logger.error("Error during Qdrant semantic search: %s", e)
            return []

    def delete_by_project_id(self, project_id: str) -> Dict[str, Any]:
        """Delete all points with the given project_id. Returns dict with documents_deleted."""
        try:
            scroll_filter = Filter(
                must=[FieldCondition(key="metadata.project_id", match=MatchValue(value=project_id))]
            )
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=10_000,
            )
            point_ids = [p.id for p in scroll_result[0]]
            if point_ids:
                self.qdrant_client.delete(
                    collection_name=self.collection_name, points_selector=point_ids
                )
            n = len(point_ids)
            logger.info("Deleted %s documents for project_id %s in %s", n, project_id, self.collection_name)
            return {"documents_deleted": n}
        except Exception as e:
            logger.error("Error deleting by project_id %s: %s", project_id, e)
            return {"documents_deleted": 0, "error": str(e)}
