"""
Qdrant-backed document store for dataservices (aligned with complianceskill storage patterns).
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.documents import Document as LangchainDocument
from langchain_openai import OpenAIEmbeddings
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    try:
        from langchain_qdrant import QdrantVectorStore as LangchainQdrant
    except ImportError:
        from langchain_qdrant import Qdrant as LangchainQdrant

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None  # type: ignore[misc, assignment]
    LangchainQdrant = None  # type: ignore[misc, assignment]
    Distance = VectorParams = None  # type: ignore[misc, assignment]


class _QdrantCollectionProxy:
    """Chroma-like ``collection.delete(...)`` for Qdrant."""

    def __init__(self, store: "DocumentQdrantStore") -> None:
        self._store = store

    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Any] = None,
    ) -> None:
        if where_document is not None:
            logger.warning("Qdrant store ignores where_document in delete()")
        name = self._store.collection_name
        client = self._store.qdrant_client
        if ids is not None:
            client.delete(collection_name=name, points_selector=ids)
            return
        if where:
            flt = self._store._convert_chroma_filter_to_qdrant(where)
            if flt is None:
                return
            offset = None
            while True:
                pts, offset = client.scroll(
                    collection_name=name,
                    scroll_filter=flt,
                    limit=256,
                    offset=offset,
                    with_payload=False,
                )
                if not pts:
                    break
                client.delete(collection_name=name, points_selector=[p.id for p in pts])
            return
        offset = None
        while True:
            pts, offset = client.scroll(
                collection_name=name,
                limit=512,
                offset=offset,
                with_payload=False,
            )
            if not pts:
                break
            client.delete(collection_name=name, points_selector=[p.id for p in pts])


class _QdrantChromaCompatClient:
    """Minimal ChromaDB ``get_all_records`` compatibility for duplicate checks."""

    def __init__(self, store: "DocumentQdrantStore") -> None:
        self._store = store

    def get_all_records(self, collection_name: str) -> Dict[str, Any]:
        if collection_name != self._store.collection_name:
            logger.debug(
                "get_all_records called with collection_name=%s but store is %s",
                collection_name,
                self._store.collection_name,
            )
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Any] = []
        offset = None
        while True:
            pts, offset = self._store.qdrant_client.scroll(
                collection_name=self._store.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
            )
            if not pts:
                break
            for p in pts:
                pl = p.payload or {}
                ids.append(str(p.id))
                documents.append(str(pl.get("page_content", "") or ""))
                metadatas.append(pl.get("metadata", pl))
        return {"ids": ids, "documents": documents, "metadatas": metadatas}


def _to_qdrant_point_id(id_value: Any) -> str:
    """Convert a document/section id to a valid Qdrant point ID (UUID). Qdrant accepts only UUID or unsigned integer."""
    if id_value is None:
        return str(uuid4())
    s = str(id_value).strip()
    if not s:
        return str(uuid4())
    try:
        uuid.UUID(s)
        return s
    except (ValueError, AttributeError, TypeError):
        pass
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "qdrant.point." + s))


class DocumentQdrantStore:
    """Handle Qdrant vectorstore operations using the unified storage architecture."""

    is_persistent: bool = True

    def __init__(
        self,
        qdrant_client: Optional[Any] = None,
        collection_name: str = "default",
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        host: Optional[str] = None,
        port: int = 6333,
        tf_idf: bool = False,
        batch_size: int = 200,
    ):
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "Qdrant dependencies not installed. Install with: pip install qdrant-client langchain-qdrant"
            )
        if embeddings_model is None:
            raise ValueError("embeddings_model is required for DocumentQdrantStore")

        self.collection_name = collection_name
        self.embeddings_model = embeddings_model
        self.tf_idf = tf_idf
        self.vectorizer = TfidfVectorizer() if tf_idf else None
        self.batch_size = batch_size
        if tf_idf:
            logger.warning(
                "tf_idf=True on Qdrant is not fully supported in dataservices; semantic/TfIdf hybrid may be limited"
            )

        if qdrant_client:
            self.qdrant_client = qdrant_client
        else:
            host = host or "localhost"
            self.qdrant_client = QdrantClient(host=host, port=port)

        self.vectorstore = None
        self.initialize()
        self.collection = _QdrantCollectionProxy(self)
        self.chroma_client = _QdrantChromaCompatClient(self)

    def list_existing_document_ids(self) -> set:
        """Return point IDs already in the collection (duplicate policy support)."""
        try:
            rec = self.chroma_client.get_all_records(self.collection_name)
            return set(rec.get("ids", []))
        except Exception as e:
            logger.warning("list_existing_document_ids failed: %s", e)
            return set()

    def initialize(self) -> None:
        """Initialize or load the Qdrant vectorstore."""
        try:
            if self.vectorstore:
                return

            logger.info("Initializing Qdrant store with collection %s", self.collection_name)

            if not self.qdrant_client.collection_exists(self.collection_name):
                logger.info("Collection %s doesn't exist, creating it", self.collection_name)
                test_embedding = self.embeddings_model.embed_query("test")
                embedding_dim = len(test_embedding)
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
                )
                logger.info("Created collection %s with dimension %s", self.collection_name, embedding_dim)
            else:
                logger.info("Collection %s already exists", self.collection_name)

            try:
                self.vectorstore = LangchainQdrant(
                    client=self.qdrant_client,
                    collection_name=self.collection_name,
                    embedding=self.embeddings_model,
                )
            except TypeError as e:
                error_str = str(e)
                if "embedding" in error_str and "embeddings" not in error_str:
                    self.vectorstore = LangchainQdrant(
                        client=self.qdrant_client,
                        collection_name=self.collection_name,
                        embeddings=self.embeddings_model,
                    )
                else:
                    logger.error("Failed to initialize Langchain Qdrant: %s", error_str)
                    raise

            logger.info("Successfully initialized Qdrant store with collection %s", self.collection_name)

        except Exception as e:
            logger.error("Failed to initialize Qdrant store: %s", e)
            raise

    def compute_document_embeddings(self, documents: List[LangchainDocument]) -> List[List[float]]:
        try:
            texts = [doc.page_content for doc in documents]
            return self.embeddings_model.embed_documents(texts)
        except Exception as e:
            logger.error("Error computing document embeddings: %s", e)
            return []

    def add_documents(self, docs: List[Any]) -> List[str]:
        from app.storage.documents import create_langchain_doc_util

        if not docs:
            logger.warning("No documents provided to add to the vectorstore.")
            return []

        documents: List[LangchainDocument] = []
        ids: List[str] = []
        for doc in docs:
            if isinstance(doc, LangchainDocument):
                documents.append(doc)
                raw_id = doc.metadata.get("id", None)
                document_id = str(uuid4()) if raw_id is None else raw_id
                if doc.metadata.get("id", None) is None:
                    doc.metadata["id"] = document_id
                ids.append(_to_qdrant_point_id(doc.metadata.get("id", document_id)))
                continue
            if not isinstance(doc, dict):
                logger.warning("Skipping invalid document format: %s", doc)
                continue
            if "metadata" not in doc or "data" not in doc:
                logger.warning("Skipping document missing required fields: %s", doc)
                continue
            try:
                document_id, document = create_langchain_doc_util(metadata=doc["metadata"], data=doc["data"])
                if document and document_id:
                    documents.append(document)
                    ids.append(_to_qdrant_point_id(document_id))
                else:
                    logger.warning("Failed to create document from doc: %s", doc)
            except Exception as e:
                logger.error("Error creating document from doc %s: %s", doc, e)
                continue

        if documents:
            try:
                filtered_documents = filter_complex_metadata(documents)
            except Exception as e:
                logger.warning("Error filtering complex metadata: %s. Using original documents.", e)
                filtered_documents = documents

            added_ids: List[str] = []
            for start in range(0, len(filtered_documents), self.batch_size):
                batch_docs = filtered_documents[start : start + self.batch_size]
                batch_ids = ids[start : start + self.batch_size]
                try:
                    self.vectorstore.add_documents(documents=batch_docs, ids=batch_ids)
                    added_ids.extend(batch_ids)
                except Exception as e:
                    logger.warning("Qdrant batch failed at offset %s (%s docs): %s", start, len(batch_docs), e)
            logger.info("Added %s documents to the Qdrant vectorstore.", len(added_ids))
            return added_ids
        logger.warning("No valid documents were found to add to the vectorstore.")
        return []

    def _apply_manual_filter(self, results: List[Tuple[Any, Any]], where: Dict[str, Any]) -> List[Tuple[Any, Any]]:
        if not where or not results:
            return results

        FIELD_MAPPING = {
            "project_id": "project_id",
            "product_name": "product_name",
            "type": "type",
            "mdl_type": "mdl_type",
            "table_name": "table_name",
            "name": "name",
            "content_type": "content_type",
            "category_name": "category_name",
            "organization_id": "organization_id",
            "sql_pair_id": "sql_pair_id",
            "instruction_id": "instruction_id",
        }

        def get_nested_value(doc_metadata: Dict[str, Any], key: str) -> Any:
            if "metadata" in doc_metadata and isinstance(doc_metadata["metadata"], dict):
                nested_meta = doc_metadata["metadata"]
                mapped_key = FIELD_MAPPING.get(key, key)
                return nested_meta.get(mapped_key)
            mapped_key = FIELD_MAPPING.get(key, key)
            return doc_metadata.get(mapped_key)

        def check_condition(metadata: Dict[str, Any], key: str, value: Any) -> bool:
            actual_value = get_nested_value(metadata, key)
            if isinstance(value, dict):
                if "$eq" in value:
                    return actual_value == value["$eq"]
                if "$in" in value:
                    return actual_value in value["$in"]
                if "$ne" in value:
                    return actual_value != value["$ne"]
                return actual_value == value
            return actual_value == value

        def matches_filter(metadata: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
            if "$and" in filter_dict:
                return all(matches_filter(metadata, cond) for cond in filter_dict["$and"])
            if "$or" in filter_dict:
                return any(matches_filter(metadata, cond) for cond in filter_dict["$or"])
            for fk, fv in filter_dict.items():
                if fk.startswith("$"):
                    continue
                if not check_condition(metadata, fk, fv):
                    return False
            return True

        filtered_results = []
        for doc, score in results:
            if matches_filter(doc.metadata, where):
                filtered_results.append((doc, score))
        logger.info("Manual filtering: %s -> %s results", len(results), len(filtered_results))
        return filtered_results

    def _convert_chroma_filter_to_qdrant(self, where: Dict[str, Any]) -> Optional[Any]:
        if not where:
            return None
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue

            FIELD_MAPPING = {
                "project_id": "metadata.project_id",
                "product_name": "metadata.product_name",
                "type": "metadata.type",
                "mdl_type": "metadata.mdl_type",
                "table_name": "metadata.table_name",
                "name": "metadata.name",
                "content_type": "metadata.content_type",
                "category_name": "metadata.category_name",
                "organization_id": "metadata.organization_id",
                "entity_type": "entity_type",
                "artifact_type": "artifact_type",
                "sql_pair_id": "metadata.sql_pair_id",
                "instruction_id": "metadata.instruction_id",
            }

            def map_field_name(key: str) -> str:
                return FIELD_MAPPING.get(key, f"metadata.{key}")

            def convert_condition(key: str, value: Any) -> Optional[Any]:
                qdrant_key = map_field_name(key)
                if isinstance(value, dict):
                    if "$eq" in value:
                        return FieldCondition(key=qdrant_key, match=MatchValue(value=value["$eq"]))
                    if "$in" in value:
                        return FieldCondition(key=qdrant_key, match=MatchAny(any=value["$in"]))
                    if "$ne" in value:
                        return None
                    return FieldCondition(key=qdrant_key, match=MatchValue(value=value))
                return FieldCondition(key=qdrant_key, match=MatchValue(value=value))

            def parse_filter_dict(filter_dict: Dict[str, Any]) -> Dict[str, Any]:
                must_conditions: List[Any] = []
                should_conditions: List[Any] = []
                must_not_conditions: List[Any] = []
                if "$and" in filter_dict:
                    for condition in filter_dict["$and"]:
                        parsed = parse_filter_dict(condition)
                        if "must" in parsed:
                            must_conditions.extend(parsed["must"])
                        if "should" in parsed:
                            should_conditions.extend(parsed["should"])
                elif "$or" in filter_dict:
                    for condition in filter_dict["$or"]:
                        parsed = parse_filter_dict(condition)
                        if "must" in parsed:
                            should_conditions.extend(parsed["must"])
                        if "should" in parsed:
                            should_conditions.extend(parsed["should"])
                else:
                    for key, value in filter_dict.items():
                        if key.startswith("$"):
                            continue
                        condition = convert_condition(key, value)
                        if condition:
                            must_conditions.append(condition)
                result: Dict[str, Any] = {}
                if must_conditions:
                    result["must"] = must_conditions
                if should_conditions:
                    result["should"] = should_conditions
                if must_not_conditions:
                    result["must_not"] = must_not_conditions
                return result

            qdrant_filter_dict = parse_filter_dict(where)
            if qdrant_filter_dict:
                return Filter(**qdrant_filter_dict)
            return None
        except Exception as e:
            logger.error("Error converting ChromaDB filter to Qdrant: %s", e)
            return None

    def semantic_search(
        self,
        query: str,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.vectorstore:
            logger.warning("Qdrant vectorstore not initialized.")
            return []
        try:
            filter_dict = None
            if where is not None and isinstance(where, dict) and where:
                filter_dict = self._convert_chroma_filter_to_qdrant(where)

            try:
                collection_info = self.vectorstore.client.get_collection(self.collection_name)
                if collection_info.points_count == 0:
                    return []
            except Exception as e:
                logger.warning("Could not check collection point count: %s", e)

            max_retries = 1
            retry_count = 0
            results: List[Tuple[Any, Any]] = []
            while retry_count <= max_retries and not results:
                try:
                    if filter_dict and retry_count == 0:
                        try:
                            results = self.vectorstore.similarity_search_with_score(
                                query=query, k=k, filter=filter_dict
                            )
                        except TypeError as te:
                            logger.warning("Qdrant filter not supported on similarity_search_with_score: %s", te)
                            results = self.vectorstore.similarity_search_with_score(query=query, k=k * 3)
                            results = self._apply_manual_filter(results, where)[:k]
                    else:
                        results = self.vectorstore.similarity_search_with_score(
                            query=query, k=k * 3 if where else k
                        )
                        if where:
                            results = self._apply_manual_filter(results, where)[:k]
                        else:
                            results = results[:k]
                    break
                except Exception as e:
                    retry_count += 1
                    error_msg = str(e)
                    if (
                        "Server disconnected" in error_msg
                        or "Connection" in error_msg
                        or "timeout" in error_msg.lower()
                    ):
                        if retry_count <= max_retries:
                            time.sleep(retry_count)
                        else:
                            return []
                    else:
                        logger.error("Error in similarity search: %s", e)
                        return []

            formatted_results: List[Dict[str, Any]] = []
            for doc, score in results:
                meta = getattr(doc, "metadata", {}) or {}
                if isinstance(meta, dict) and "metadata" in meta and isinstance(meta["metadata"], dict):
                    actual_meta = meta["metadata"]
                    actual_meta = {**actual_meta, **{kk: vv for kk, vv in meta.items() if kk != "metadata"}}
                    meta = actual_meta
                content = getattr(doc, "page_content", "") or getattr(doc, "text", "")
                formatted_results.append(
                    {"content": content, "metadata": meta, "score": float(score), "id": meta.get("id", None)}
                )
            formatted_results.sort(key=lambda x: x["score"])
            return formatted_results
        except Exception as e:
            logger.error("Error during Qdrant semantic search: %s", e)
            return []

    def semantic_search_with_bm25(
        self,
        query: str,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        return self.semantic_search(query, k=k, where=where, query_embedding=query_embedding)

    def semantic_search_with_tfidf(
        self,
        query: str,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        return self.semantic_search(query, k=k, where=where, query_embedding=query_embedding)

    def tfidf_search(self, query: str, k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.tf_idf:
            return []
        logger.warning("tfidf_search on Qdrant is not implemented; returning semantic_search results")
        return self.semantic_search(query, k=k, where=where)

    def delete_by_project_id(self, project_id: str) -> Dict[str, Any]:
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            filter_dict = Filter(must=[FieldCondition(key="metadata.project_id", match=MatchValue(value=project_id))])
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name, scroll_filter=filter_dict, limit=10000
            )
            point_ids = [point.id for point in scroll_result[0]]
            if point_ids:
                self.qdrant_client.delete(collection_name=self.collection_name, points_selector=point_ids)
            return {"documents_deleted": len(point_ids)}
        except Exception as e:
            logger.error("Error deleting documents for project ID %s: %s", project_id, e)
            return {"documents_deleted": 0, "error": str(e)}

    def get_by_filter(self, where: Dict[str, Any], limit: int = 500) -> List[Dict[str, Any]]:
        if not where:
            return []
        try:
            filter_dict = self._convert_chroma_filter_to_qdrant(where)
            if not filter_dict:
                return []
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_dict,
                limit=limit,
                with_payload=True,
            )
            points, _ = scroll_result
            formatted: List[Dict[str, Any]] = []
            for point in points:
                payload = point.payload or {}
                content = payload.get("page_content") or payload.get("content") or payload.get("text") or ""
                metadata = payload.get("metadata", payload)
                if not isinstance(metadata, dict):
                    metadata = payload
                formatted.append(
                    {
                        "content": content if isinstance(content, str) else str(content),
                        "metadata": metadata,
                        "score": 1.0,
                        "id": getattr(point.id, "uuid", str(point.id)) if point.id is not None else None,
                    }
                )
            return formatted
        except Exception as e:
            logger.warning("get_by_filter failed: %s", e)
            return []
