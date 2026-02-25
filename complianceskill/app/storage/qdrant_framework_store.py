"""
Qdrant client for framework ingestion.
Uses the existing vector_store.py infrastructure via QdrantVectorStoreClient.
"""

import logging
from typing import Optional, List, Dict, Any

from qdrant_client.http import models as qmodels

from app.core.settings import get_settings
from app.storage.vector_store import QdrantVectorStoreClient, get_vector_store_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config - reuses existing Qdrant settings
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 1536   # text-embedding-3-small

# Collection names as constants — import these everywhere else
class Collections:
    CONTROLS = "framework_controls"
    REQUIREMENTS = "framework_requirements"
    RISKS = "framework_risks"
    TEST_CASES = "framework_test_cases"
    SCENARIOS = "framework_scenarios"
    USER_POLICIES = "user_policies"

    ALL_FRAMEWORK = [CONTROLS, REQUIREMENTS, RISKS, TEST_CASES, SCENARIOS]
    ALL = ALL_FRAMEWORK + [USER_POLICIES]


# ---------------------------------------------------------------------------
# Client factory - uses vector_store infrastructure
# ---------------------------------------------------------------------------

_vector_store_client: Optional[QdrantVectorStoreClient] = None


_underlying_qdrant_client = None


def _get_vector_store_client() -> QdrantVectorStoreClient:
    """Get or create the QdrantVectorStoreClient singleton."""
    global _vector_store_client
    if _vector_store_client is None:
        settings = get_settings()
        config = settings.get_vector_store_config()
        
        # Ensure we're using Qdrant
        if config.get("type") != "qdrant":
            logger.warning(f"Vector store type is {config.get('type')}, but framework store requires Qdrant. Overriding to Qdrant.")
            config = config.copy()
            config["type"] = "qdrant"
        
        _vector_store_client = get_vector_store_client(config=config)
        logger.info("QdrantVectorStoreClient initialized for framework store")
    return _vector_store_client


def _get_underlying_qdrant_client():
    """
    Get the underlying QdrantClient from the vector store for direct operations.
    The DocumentQdrantStore initializes the QdrantClient internally, so we access it through the document store.
    """
    global _underlying_qdrant_client
    if _underlying_qdrant_client is None:
        vector_client = _get_vector_store_client()
        # Get the document store to access the underlying QdrantClient
        # Use a dummy collection name - the document store will initialize the client
        doc_store = vector_client._get_document_store("_temp")
        _underlying_qdrant_client = doc_store.qdrant_client
        logger.debug("Underlying QdrantClient accessed from vector store")
    return _underlying_qdrant_client


# ---------------------------------------------------------------------------
# Collection setup
# ---------------------------------------------------------------------------

def _vector_params() -> qmodels.VectorParams:
    return qmodels.VectorParams(
        size=EMBEDDING_DIM,
        distance=qmodels.Distance.COSINE,
    )


def _framework_payload_schema() -> Dict[str, Any]:
    """Shared payload index fields for all framework collections."""
    return {
        "framework_id": qmodels.PayloadSchemaType.KEYWORD,
        "artifact_type": qmodels.PayloadSchemaType.KEYWORD,
        "artifact_id": qmodels.PayloadSchemaType.KEYWORD,
        "domain": qmodels.PayloadSchemaType.KEYWORD,
    }


def _ensure_collection(name: str, recreate: bool = False) -> None:
    """Create collection if it doesn't exist; optionally recreate."""
    client = _get_underlying_qdrant_client()
    exists = False
    try:
        client.get_collection(name)
        exists = True
    except Exception:
        exists = False

    if exists and recreate:
        client.delete_collection(name)
        exists = False
        logger.info(f"Collection '{name}' deleted for recreation.")

    if not exists:
        client.create_collection(
            collection_name=name,
            vectors_config=_vector_params(),
        )
        logger.info(f"Collection '{name}' created.")
    else:
        logger.debug(f"Collection '{name}' already exists, skipping.")


def _create_payload_indexes(collection: str, fields: Dict[str, Any]) -> None:
    """Create payload indexes for efficient filtered search."""
    client = _get_underlying_qdrant_client()
    for field, schema_type in fields.items():
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=schema_type,
            )
        except Exception as exc:
            logger.debug(f"Payload index '{field}' on '{collection}': {exc}")


def initialize_collections(recreate: bool = False) -> None:
    """
    Create all Qdrant collections and payload indexes.
    Call once during startup or when bootstrapping a fresh environment.
    Uses the vector_store infrastructure.

    Args:
        recreate: If True, delete and recreate existing collections.
                  Destructive — only for dev/test.
    """
    framework_fields = _framework_payload_schema()

    # Framework artifact collections share the same index structure
    for collection in Collections.ALL_FRAMEWORK:
        _ensure_collection(collection, recreate=recreate)
        _create_payload_indexes(collection, framework_fields)

    # User policies collection has additional fields
    _ensure_collection(Collections.USER_POLICIES, recreate=recreate)
    _create_payload_indexes(Collections.USER_POLICIES, {
        **framework_fields,
        "source_doc_id": qmodels.PayloadSchemaType.KEYWORD,
        "session_id": qmodels.PayloadSchemaType.KEYWORD,
    })

    logger.info("All Qdrant collections initialized.")


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_points(
    collection: str,
    points: List[qmodels.PointStruct],
    batch_size: int = 100,
) -> None:
    """
    Upsert a list of PointStructs into a Qdrant collection in batches.
    Each PointStruct must have: id (str UUID), vector (list[float]), payload (dict).
    
    Uses the underlying QdrantClient for direct point operations.
    """
    client = _get_underlying_qdrant_client()
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=collection, points=batch)
        logger.debug(f"Upserted batch {i//batch_size + 1} to '{collection}' ({len(batch)} points).")
    logger.info(f"Upserted {len(points)} points into '{collection}'.")


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def search_collection(
    collection: str,
    query_vector: List[float],
    limit: int = 10,
    filters: Optional[qmodels.Filter] = None,
    with_payload: bool = True,
) -> List[qmodels.ScoredPoint]:
    """
    Semantic search with optional payload filters.
    Uses the underlying QdrantClient for direct query operations.
    """
    # Use the underlying QdrantClient directly for synchronous operations
    # This avoids async complexity since search_collection is called from sync code
    client = _get_underlying_qdrant_client()
    search_result = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=limit,
        query_filter=filters,
        with_payload=with_payload,
    )
    return search_result.points




# ---------------------------------------------------------------------------
# Connection check
# ---------------------------------------------------------------------------

def check_qdrant_connection() -> bool:
    """Verify Qdrant connectivity."""
    try:
        client = _get_underlying_qdrant_client()
        client.get_collections()
        return True
    except Exception as exc:
        logger.error(f"Qdrant connection failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Backward compatibility - get_qdrant_client for existing code
# ---------------------------------------------------------------------------

def get_qdrant_client():
    """
    Get the underlying QdrantClient for backward compatibility.
    Use this only if you need direct QdrantClient access.
    Prefer using search_collection() and upsert_points() instead.
    """
    return _get_underlying_qdrant_client()
