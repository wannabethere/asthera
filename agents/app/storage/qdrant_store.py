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
    from qdrant_client.models import Distance, Filter, FieldCondition, MatchValue, VectorParams, PointStruct
    try:
        from langchain_qdrant import QdrantVectorStore as LangchainQdrant
    except ImportError:
        from langchain_qdrant import Qdrant as LangchainQdrant
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    LangchainQdrant = None
    PointStruct = None


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

    def add_points_direct(
        self,
        points_data: List[Dict[str, Any]],
        log_schema: bool = True
    ) -> Dict[str, Any]:
        """
        Add documents as Qdrant points directly with enriched metadata.
        
        Args:
            points_data: List of dicts with keys:
                - 'text': The text content to embed
                - 'metadata': Dict with metadata including query_patterns and use_cases
                - 'id': Optional point ID (will be generated if not provided)
            log_schema: If True, log the entire schema for each point
        
        Returns:
            Dict with 'documents_written' count
        """
        if not QDRANT_AVAILABLE or PointStruct is None:
            raise ImportError("Qdrant dependencies not installed")
        
        if not points_data:
            logger.warning("No points data provided")
            return {"documents_written": 0}
        
        logger.info("Creating %s Qdrant points directly for collection %s", len(points_data), self.collection_name)
        
        # Generate embeddings for all texts
        texts = [point["text"] for point in points_data]
        logger.info("Generating embeddings for %s texts", len(texts))
        embeddings = self.embeddings_model.embed_documents(texts)
        
        # Create points
        points = []
        for idx, point_data in enumerate(points_data):
            metadata = point_data.get("metadata", {})
            point_id = point_data.get("id")
            if point_id is None:
                point_id = str(uuid4())
            
            # Convert point_id to valid Qdrant format
            qdrant_id = _to_qdrant_point_id(point_id)
            
            # Prepare payload (metadata stored in Qdrant payload)
            payload = {
                "metadata": metadata,
                "text": point_data["text"]
            }
            
            # Log the entire schema for this point
            if log_schema:
                logger.info("=" * 80)
                logger.info("QDRANT POINT SCHEMA - Collection: %s, Point ID: %s", self.collection_name, qdrant_id)
                logger.info("=" * 80)
                logger.info("Point ID: %s", qdrant_id)
                logger.info("Text (first 200 chars): %s", point_data["text"][:200])
                logger.info("Full Metadata Schema:")
                import json
                logger.info(json.dumps(metadata, indent=2, default=str))
                logger.info("=" * 80)
            
            point = PointStruct(
                id=qdrant_id,
                vector=embeddings[idx],
                payload=payload
            )
            points.append(point)
        
        # Upload points in batches
        batch_size = getattr(self, "batch_size", 200)
        added = 0
        for start in range(0, len(points), batch_size):
            batch_points = points[start : start + batch_size]
            try:
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=batch_points
                )
                added += len(batch_points)
                logger.info("Uploaded batch of %s points (total: %s/%s)", len(batch_points), added, len(points))
            except Exception as e:
                logger.error("Qdrant batch upload failed at offset %s: %s", start, e)
                import traceback
                logger.error("Traceback: %s", traceback.format_exc())
        
        logger.info("Successfully added %s points to Qdrant collection %s", added, self.collection_name)
        return {"documents_written": added}

    def _evaluate_where_clause(self, metadata: Dict, where: Dict) -> bool:
        """Evaluate a where clause against metadata. Supports nested $and, $eq, $in operators."""
        if not where:
            return True
        
        # Handle $and operator
        if "$and" in where:
            conditions = where["$and"]
            return all(self._evaluate_where_clause(metadata, cond) for cond in conditions)
        
        # Handle simple key-value pairs (direct equality)
        if not any(key.startswith("$") for key in where.keys()):
            return all(metadata.get(k) == v for k, v in where.items())
        
        # Handle operators for individual fields
        for key, value in where.items():
            if isinstance(value, dict):
                # Handle $eq operator
                if "$eq" in value:
                    if metadata.get(key) != value["$eq"]:
                        return False
                # Handle $in operator
                elif "$in" in value:
                    if metadata.get(key) not in value["$in"]:
                        return False
                # Handle nested conditions
                else:
                    if not self._evaluate_where_clause(metadata, {key: value}):
                        return False
            else:
                # Direct equality check
                if metadata.get(key) != value:
                    return False
        
        return True

    def _verify_collection_exists(self) -> bool:
        """Verify that the collection exists and has at least some points."""
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            point_count = collection_info.points_count
            logger.debug("Collection '%s' exists with %d points", self.collection_name, point_count)
            return point_count > 0
        except Exception as e:
            logger.warning("Collection '%s' does not exist or error accessing it: %s", self.collection_name, e)
            return False

    def semantic_search(self, query: str, k: int = 5, where: Optional[Dict] = None, query_embedding: Optional[Any] = None) -> List[Dict]:
        """Semantic search with optional where filter.
        
        Args:
            query: The search query string
            k: Number of results to return
            where: Optional metadata filter dictionary with simple key-value pairs
                   Example: {"project_id": "hr_compliance_risk", "type": "TABLE_DESCRIPTION"}
            query_embedding: Optional pre-computed query embedding (ignored)
        """
        if not self.vectorstore:
            return []
        
        if not self._verify_collection_exists():
            return []
        
        try:
            # Build Qdrant filter from where clause
            # Handles both simple {"key": "value"} and complex {"key": {"$eq": "value"}} formats
            qdrant_filter = None
            if where:
                from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
                conditions = []
                
                logger.info(f"Building filter for collection '{self.collection_name}' with where clause: {where}")
                
                # Handle $and operator
                if "$and" in where:
                    for cond in where["$and"]:
                        if not isinstance(cond, dict):
                            continue
                        for key, value in cond.items():
                            if isinstance(value, dict) and "$eq" in value:
                                conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value["$eq"])))
                                logger.info(f"  - Added condition: metadata.{key} == {value['$eq']}")
                            elif isinstance(value, dict) and "$in" in value:
                                in_values = value["$in"] if isinstance(value["$in"], list) else [value["$in"]]
                                conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchAny(any=in_values)))
                                logger.info(f"  - Added condition: metadata.{key} IN {in_values}")
                            else:
                                conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value)))
                                logger.info(f"  - Added condition: metadata.{key} == {value}")
                else:
                    # Simple key-value or complex operator format
                    for key, value in where.items():
                        if key.startswith("$"):
                            continue
                        if isinstance(value, dict):
                            if "$eq" in value:
                                conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value["$eq"])))
                                logger.info(f"  - Added condition: metadata.{key} == {value['$eq']}")
                            elif "$in" in value:
                                in_values = value["$in"] if isinstance(value["$in"], list) else [value["$in"]]
                                conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchAny(any=in_values)))
                                logger.info(f"  - Added condition: metadata.{key} IN {in_values}")
                        else:
                            # Simple value (from test file)
                            conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value)))
                            logger.info(f"  - Added condition: metadata.{key} == {value}")
                
                if conditions:
                    qdrant_filter = Filter(must=conditions)
                    logger.info(f"Built Qdrant filter with {len(conditions)} conditions")
                else:
                    logger.warning(f"No conditions built from where clause: {where}")
            
            # Search using Langchain Qdrant
            search_results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=k * 3 if where else k,  # Get more if filtering
                filter=qdrant_filter
            )
            

            
            
            # Process results
            results = []
            for doc, score in search_results:
                meta = getattr(doc, "metadata", {}) or {}
                content = getattr(doc, "page_content", "") if hasattr(doc, "page_content") else ""
                
                # Handle nested metadata structure
                if isinstance(meta, dict) and "metadata" in meta and isinstance(meta["metadata"], dict):
                    actual_meta = meta["metadata"]
                    actual_meta = {**actual_meta, **{k: v for k, v in meta.items() if k != "metadata"}}
                    meta = actual_meta
                
                # If page_content is empty, try to extract from metadata or payload
                # Documents stored via add_points_direct have text in payload.text
                if not content or not content.strip():
                    # Try to get from metadata.description (common for table descriptions)
                    if isinstance(meta, dict):
                        content = meta.get("description", "") or meta.get("text", "") or ""
                    
                    # If still empty, try to access raw payload from Qdrant point
                    # LangChain might store it differently, so try various attributes
                    if not content and hasattr(doc, "lc_kwargs"):
                        # LangChain document might have payload in lc_kwargs
                        lc_kwargs = getattr(doc, "lc_kwargs", {})
                        if isinstance(lc_kwargs, dict):
                            payload = lc_kwargs.get("payload", {})
                            if isinstance(payload, dict):
                                content = payload.get("text", "") or payload.get("content", "") or ""
                    
                    # Last resort: use description from metadata if available
                    if not content and isinstance(meta, dict):
                        content = meta.get("description", "") or str(meta)
                
                results.append({
                    "content": content,
                    "metadata": meta,
                    "score": float(score),
                    "id": meta.get("id") or meta.get("_id", "")
                })
                
                if len(results) >= k:
                    break
            
            return results[:k]
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
