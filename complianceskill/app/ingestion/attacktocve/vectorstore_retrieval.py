"""
Vector Store Retrieval Tool
============================
Queries a pre-populated vector store (Qdrant OR ChromaDB) to retrieve the
most semantically similar CIS Risk Scenarios for a given ATT&CK technique.

Indexing contract
-----------------
Each vector document represents a CIS Risk Scenario with:
  - text  = f"{scenario.name}. {scenario.description}"
  - metadata = {
        scenario_id, name, asset, trigger, loss_outcomes (comma-sep), controls
    }

Usage
-----
    from tools.vectorstore_retrieval import create_vectorstore_tool, VectorStoreConfig

    # Create from settings (recommended)
    config = VectorStoreConfig.from_settings()
    
    # Or create manually
    tool = create_vectorstore_tool(
        VectorStoreConfig(backend="qdrant", collection="cis_controls", ...)
    )

The tool also ships an ingest helper:
    from tools.vectorstore_retrieval import ingest_cis_scenarios
    ingest_cis_scenarios(scenarios, config)
"""

from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Namespace UUID for generating deterministic UUIDs from string IDs
# This ensures the same document ID always maps to the same UUID
_COMPLIANCE_SKILL_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _string_id_to_uuid(string_id: str) -> uuid.UUID:
    """Convert a string ID to a deterministic UUID using uuid5."""
    return uuid.uuid5(_COMPLIANCE_SKILL_NAMESPACE, str(string_id))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class VectorBackend(str, Enum):
    QDRANT = "qdrant"
    CHROMA = "chroma"


class VectorStoreConfig(BaseModel):
    backend: VectorBackend = Field(default=VectorBackend.CHROMA)
    collection: str = Field(default="cis_controls_v8_1")

    # Qdrant
    qdrant_url: Optional[str] = Field(default=None)
    qdrant_api_key: Optional[str] = Field(default=None)

    # Chroma
    chroma_persist_dir: Optional[str] = Field(default=None)
    chroma_host: Optional[str] = Field(default=None)   # set for remote Chroma server
    chroma_port: int = Field(default=8888)

    # Embedding
    embedding_model: str = Field(default="text-embedding-3-small")  # OpenAI model name
    openai_api_key: Optional[str] = Field(default=None)

    # Retrieval
    top_k: int = Field(default=5)
    score_threshold: float = Field(default=0.30)       # minimum cosine similarity

    @classmethod
    def from_settings(cls, collection: Optional[str] = None) -> "VectorStoreConfig":
        """
        Create VectorStoreConfig from centralized settings.
        
        Args:
            collection: Optional collection name override. If not provided,
                       uses the default collection from settings.
        
        Returns:
            VectorStoreConfig instance populated from settings.
        """
        try:
            from app.core.settings import get_settings
        except ImportError:
            # Fallback for when run as script
            try:
                import sys
                from pathlib import Path
                workspace_root = Path(__file__).resolve().parent.parent.parent.parent.parent
                sys.path.insert(0, str(workspace_root))
                from app.core.settings import get_settings
            except ImportError:
                logger.warning("Could not import settings, using defaults")
                return cls()
        
        settings = get_settings()
        
        # Determine backend from settings
        if settings.VECTOR_STORE_TYPE.value == "qdrant":
            backend = VectorBackend.QDRANT
            # Build Qdrant URL
            qdrant_url = settings.QDRANT_URL
            if not qdrant_url:
                host = settings.QDRANT_HOST or "localhost"
                port = settings.QDRANT_PORT
                qdrant_url = f"http://{host}:{port}"
            
            return cls(
                backend=backend,
                collection=collection or settings.QDRANT_COLLECTION_NAME,
                qdrant_url=qdrant_url,
                qdrant_api_key=settings.QDRANT_API_KEY,
                openai_api_key=settings.OPENAI_API_KEY,
                embedding_model=settings.EMBEDDING_MODEL,
            )
        else:
            # ChromaDB
            backend = VectorBackend.CHROMA
            chroma_persist_dir = settings.CHROMA_PERSIST_DIRECTORY or settings.CHROMA_STORE_PATH
            
            return cls(
                backend=backend,
                collection=collection or settings.CHROMA_COLLECTION_NAME,
                chroma_persist_dir=chroma_persist_dir,
                chroma_host=settings.CHROMA_HOST,
                chroma_port=settings.CHROMA_PORT,
                openai_api_key=settings.OPENAI_API_KEY,
                embedding_model=settings.EMBEDDING_MODEL,
            )


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class VectorRetrievalInput(BaseModel):
    query: str = Field(
        description=(
            "Natural-language query derived from ATT&CK technique description, "
            "tactics, and platforms. Used for semantic similarity search."
        )
    )
    top_k: Optional[int] = Field(
        default=None,
        description="Override default top_k result count.",
    )
    asset_filter: Optional[str] = Field(
        default=None,
        description="Optional CIS asset domain filter (e.g. 'operations_security').",
    )


# ---------------------------------------------------------------------------
# Retrieval result
# ---------------------------------------------------------------------------

class RetrievedScenario(BaseModel):
    scenario_id: str
    name: str
    asset: str
    trigger: str
    loss_outcomes: List[str]
    description: str
    controls: List[str]
    score: float
    source: str  # "qdrant" | "chroma"


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------

def _get_embedder(config: VectorStoreConfig):
    """Return a LangChain embeddings object."""
    try:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=config.embedding_model,
            api_key=config.openai_api_key,
        )
    except ImportError:
        raise ImportError(
            "langchain-openai is required. "
            "Install with: pip install langchain-openai"
        )


# ---------------------------------------------------------------------------
# Qdrant retriever
# ---------------------------------------------------------------------------

class QdrantRetriever:
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self._client = None
        self._embedder = _get_embedder(config)

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
            )
        return self._client

    def retrieve(
        self,
        query: str,
        top_k: int,
        asset_filter: Optional[str] = None,
        framework_filter: Optional[str] = None,
    ) -> List[RetrievedScenario]:
        client = self._get_client()
        query_vector = self._embedder.embed_query(query)

        # Optional payload filter
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        conditions = []
        if asset_filter:
            conditions.append(FieldCondition(key="asset", match=MatchValue(value=asset_filter)))
        if framework_filter:
            conditions.append(FieldCondition(key="framework", match=MatchValue(value=framework_filter)))
        
        qdrant_filter = None
        if conditions:
            qdrant_filter = Filter(must=conditions)

        results = client.search(
            collection_name=self.config.collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
            score_threshold=self.config.score_threshold,
        )

        scenarios = []
        for hit in results:
            payload = hit.payload or {}
            scenarios.append(
                RetrievedScenario(
                    scenario_id=payload.get("scenario_id", ""),
                    name=payload.get("name", ""),
                    asset=payload.get("asset", ""),
                    trigger=payload.get("trigger", ""),
                    loss_outcomes=payload.get("loss_outcomes", "").split(","),
                    description=payload.get("description", ""),
                    controls=payload.get("controls", "").split(",") if payload.get("controls") else [],
                    score=hit.score,
                    source="qdrant",
                )
            )
        return scenarios

    def ingest(self, documents: List[Dict[str, Any]]) -> int:
        """Upsert framework documents (scenarios, controls, requirements, risks) into Qdrant collection."""
        from qdrant_client import QdrantClient
        from qdrant_client.models import (
            Distance, VectorParams, PointStruct, PayloadSchemaType
        )
        import uuid

        client = self._get_client()

        # Ensure collection exists
        existing = [c.name for c in client.get_collections().collections]
        if self.config.collection not in existing:
            client.create_collection(
                collection_name=self.config.collection,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
            # Create indexes for common fields
            for field in ["asset", "framework", "document_type"]:
                try:
                    client.create_payload_index(
                        collection_name=self.config.collection,
                        field_name=field,
                        field_schema=PayloadSchemaType.KEYWORD,
                    )
                except Exception as e:
                    logger.debug(f"Index for {field} may already exist: {e}")

        points = []
        for doc in documents:
            # Determine document type and extract text for embedding
            doc_type = doc.get("document_type", "scenarios")
            
            # Build text for embedding based on document type
            if doc_type == "scenarios":
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                payload = {
                    "scenario_id": doc.get("scenario_id", ""),
                    "name": doc.get("name", ""),
                    "asset": doc.get("asset", ""),
                    "trigger": doc.get("trigger", ""),
                    "loss_outcomes": ",".join(doc.get("loss_outcomes", [])),
                    "description": description[:2000] if description else "",
                    "controls": ",".join(doc.get("controls", [])),
                    "framework": doc.get("framework", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "controls":
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                payload = {
                    "control_id": doc.get("control_id", ""),
                    "name": doc.get("name", ""),
                    "description": description[:2000] if description else "",
                    "domain": doc.get("domain", ""),
                    "type": doc.get("type", ""),
                    "framework_requirement": doc.get("framework_requirement", ""),
                    "framework": doc.get("framework", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "requirements":
                description = doc.get("description", "") or ""
                text = f"{doc.get('requirement_id', '')}. {description}" if description else doc.get('requirement_id', '')
                payload = {
                    "requirement_id": doc.get("requirement_id", ""),
                    "description": description[:2000] if description else "",
                    "framework": doc.get("framework", ""),
                    "framework_version": doc.get("framework_version", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "risks":
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                payload = {
                    "risk_id": doc.get("risk_id") or doc.get("scenario_id", ""),
                    "scenario_id": doc.get("scenario_id") or doc.get("risk_id", ""),
                    "name": doc.get("name", ""),
                    "asset": doc.get("asset", ""),
                    "trigger": doc.get("trigger", ""),
                    "loss_outcomes": ",".join(doc.get("loss_outcomes", [])),
                    "description": description[:2000] if description else "",
                    "mitigated_by": ",".join(doc.get("mitigated_by", [])),
                    "controls": ",".join(doc.get("controls", [])),
                    "framework": doc.get("framework", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "techniques":
                description = doc.get("description", "") or ""
                text = f"{doc.get('technique_id', '')}. {doc.get('name', '')}. {description}" if description else f"{doc.get('technique_id', '')}. {doc.get('name', '')}"
                payload = {
                    "technique_id": doc.get("technique_id", ""),
                    "name": doc.get("name", ""),
                    "description": description[:2000] if description else "",
                    "tactics": ",".join(doc.get("tactics", [])),
                    "platforms": ",".join(doc.get("platforms", [])),
                    "data_sources": ",".join(doc.get("data_sources", [])),
                    "detection": (doc.get("detection") or "")[:1000],
                    "url": doc.get("url", ""),
                    "document_type": doc_type,
                }
            else:
                # Generic document type
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                payload = {**doc, "document_type": doc_type}
                # Ensure description is truncated
                if "description" in payload:
                    payload["description"] = payload["description"][:2000] if payload["description"] else ""
            
            vector = self._embedder.embed_query(text)
            # Get the string ID from payload
            string_id = (
                payload.get("technique_id") or payload.get("control_id")
                or payload.get("requirement_id") or payload.get("scenario_id")
                or payload.get("risk_id")
            )
            # Convert to UUID (Qdrant requires UUID or integer)
            if string_id:
                doc_id = _string_id_to_uuid(string_id)
            else:
                # Generate a random UUID if no ID is available
                doc_id = uuid.uuid4()
            points.append(PointStruct(id=doc_id, vector=vector, payload=payload))

        if points:
            client.upsert(collection_name=self.config.collection, points=points)
            logger.info(f"Upserted {len(points)} {doc_type} documents into Qdrant [{self.config.collection}]")
        return len(points)


# ---------------------------------------------------------------------------
# ChromaDB retriever
# ---------------------------------------------------------------------------

class ChromaRetriever:
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self._collection = None
        self._embedder = _get_embedder(config)

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        import chromadb
        from chromadb.config import Settings

        if self.config.chroma_host:
            client = chromadb.HttpClient(
                host=self.config.chroma_host,
                port=self.config.chroma_port,
            )
        else:
            client = chromadb.PersistentClient(path=self.config.chroma_persist_dir)

        self._collection = client.get_or_create_collection(
            name=self.config.collection,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    def retrieve(
        self,
        query: str,
        top_k: int,
        asset_filter: Optional[str] = None,
        framework_filter: Optional[str] = None,
    ) -> List[RetrievedScenario]:
        collection = self._get_collection()
        query_embedding = self._embedder.embed_query(query)

        # Build where clause with optional filters
        where_clause = {}
        if asset_filter:
            where_clause["asset"] = {"$eq": asset_filter}
        if framework_filter:
            where_clause["framework"] = {"$eq": framework_filter}
        where_clause = where_clause if where_clause else None

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause,
            include=["documents", "metadatas", "distances"],
        )

        scenarios = []
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, dist in zip(metadatas, distances):
            cosine_score = 1.0 - dist  # Chroma returns L2 or cosine dist
            if cosine_score < self.config.score_threshold:
                continue
            scenarios.append(
                RetrievedScenario(
                    scenario_id=meta.get("scenario_id", ""),
                    name=meta.get("name", ""),
                    asset=meta.get("asset", ""),
                    trigger=meta.get("trigger", ""),
                    loss_outcomes=meta.get("loss_outcomes", "").split(","),
                    description=meta.get("description", ""),
                    controls=meta.get("controls", "").split(",") if meta.get("controls") else [],
                    score=cosine_score,
                    source="chroma",
                )
            )
        return scenarios

    def ingest(self, documents: List[Dict[str, Any]]) -> int:
        """Upsert framework documents (scenarios, controls, requirements, risks) into Chroma collection."""
        collection = self._get_collection()
        import uuid

        ids, embeddings, documents_list, metadatas = [], [], [], []
        for doc in documents:
            # Determine document type and extract text for embedding
            doc_type = doc.get("document_type", "scenarios")
            
            # Build text for embedding based on document type
            if doc_type == "scenarios":
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                doc_id = doc.get("scenario_id", str(uuid.uuid4()))
                metadata = {
                    "scenario_id": doc.get("scenario_id", ""),
                    "name": doc.get("name", ""),
                    "asset": doc.get("asset", ""),
                    "trigger": doc.get("trigger", ""),
                    "loss_outcomes": ",".join(doc.get("loss_outcomes", [])),
                    "description": description[:2000] if description else "",
                    "controls": ",".join(doc.get("controls", [])),
                    "framework": doc.get("framework", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "controls":
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                doc_id = doc.get("control_id", str(uuid.uuid4()))
                metadata = {
                    "control_id": doc.get("control_id", ""),
                    "name": doc.get("name", ""),
                    "description": description[:2000] if description else "",
                    "domain": doc.get("domain", ""),
                    "type": doc.get("type", ""),
                    "framework_requirement": doc.get("framework_requirement", ""),
                    "framework": doc.get("framework", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "requirements":
                description = doc.get("description", "") or ""
                text = f"{doc.get('requirement_id', '')}. {description}" if description else doc.get('requirement_id', '')
                doc_id = doc.get("requirement_id", str(uuid.uuid4()))
                metadata = {
                    "requirement_id": doc.get("requirement_id", ""),
                    "description": description[:2000] if description else "",
                    "framework": doc.get("framework", ""),
                    "framework_version": doc.get("framework_version", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "risks":
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                doc_id = doc.get("risk_id") or doc.get("scenario_id", str(uuid.uuid4()))
                metadata = {
                    "risk_id": doc.get("risk_id") or doc.get("scenario_id", ""),
                    "scenario_id": doc.get("scenario_id") or doc.get("risk_id", ""),
                    "name": doc.get("name", ""),
                    "asset": doc.get("asset", ""),
                    "trigger": doc.get("trigger", ""),
                    "loss_outcomes": ",".join(doc.get("loss_outcomes", [])),
                    "description": description[:2000] if description else "",
                    "mitigated_by": ",".join(doc.get("mitigated_by", [])),
                    "controls": ",".join(doc.get("controls", [])),
                    "framework": doc.get("framework", ""),
                    "document_type": doc_type,
                }
            elif doc_type == "techniques":
                description = doc.get("description", "") or ""
                text = f"{doc.get('technique_id', '')}. {doc.get('name', '')}. {description}" if description else f"{doc.get('technique_id', '')}. {doc.get('name', '')}"
                doc_id = doc.get("technique_id", str(uuid.uuid4()))
                metadata = {
                    "technique_id": doc.get("technique_id", ""),
                    "name": doc.get("name", ""),
                    "description": description[:2000] if description else "",
                    "tactics": ",".join(doc.get("tactics", [])),
                    "platforms": ",".join(doc.get("platforms", [])),
                    "data_sources": ",".join(doc.get("data_sources", [])),
                    "detection": (doc.get("detection") or "")[:1000],
                    "url": doc.get("url", ""),
                    "document_type": doc_type,
                }
            else:
                # Generic document type
                description = doc.get("description", "") or ""
                text = f"{doc.get('name', '')}. {description}" if description else doc.get('name', '')
                doc_id = doc.get("id") or str(uuid.uuid4())
                metadata = {**doc, "document_type": doc_type}
                # Ensure description is truncated
                if "description" in metadata:
                    metadata["description"] = metadata["description"][:2000] if metadata["description"] else ""
            
            ids.append(doc_id)
            embeddings.append(self._embedder.embed_query(text))
            documents_list.append(text[:2000])
            metadatas.append(metadata)

        if ids:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents_list,
                metadatas=metadatas,
            )
            doc_type = documents[0].get("document_type", "documents") if documents else "documents"
            logger.info(f"Upserted {len(ids)} {doc_type} into Chroma [{self.config.collection}]")
        return len(ids)


# ---------------------------------------------------------------------------
# Unified retrieval facade
# ---------------------------------------------------------------------------

class VectorStoreRetriever:
    """Backend-agnostic facade.  Swap Qdrant ↔ Chroma via config."""

    def __init__(self, config: VectorStoreConfig):
        self.config = config
        if config.backend == VectorBackend.QDRANT:
            self._impl = QdrantRetriever(config)
        else:
            self._impl = ChromaRetriever(config)

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        asset_filter: Optional[str] = None,
        framework_filter: Optional[str] = None,
    ) -> List[RetrievedScenario]:
        k = top_k or self.config.top_k
        return self._impl.retrieve(query, k, asset_filter)

    def ingest(self, documents: List[Dict[str, Any]]) -> int:
        """Ingest documents (scenarios, controls, requirements, risks) into vector store."""
        return self._impl.ingest(documents)


# ---------------------------------------------------------------------------
# LangChain tool factory
# ---------------------------------------------------------------------------

def create_vectorstore_tool(config: VectorStoreConfig) -> StructuredTool:
    """
    Returns a LangChain StructuredTool for semantic CIS scenario retrieval.

    Args:
        config: VectorStoreConfig — backend, collection, credentials, top_k.

    Returns:
        StructuredTool that accepts a query + optional filters and returns
        a list of RetrievedScenario dicts ranked by similarity.
    """
    retriever = VectorStoreRetriever(config)

    def _execute(
        query: str,
        top_k: Optional[int] = None,
        asset_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            results = retriever.retrieve(query, top_k=top_k, asset_filter=asset_filter, framework_filter=None)
            return [r.model_dump() for r in results]
        except Exception as exc:
            logger.error(f"VectorStore retrieval error: {exc}")
            return [{"error": str(exc)}]

    return StructuredTool.from_function(
        func=_execute,
        name="cis_scenario_retrieval",
        description=(
            "Semantic search over CIS Controls v8.1 risk scenarios. "
            "Given a natural-language query (derived from an ATT&CK technique), "
            "returns the top-k most relevant CIS risk scenarios with similarity scores. "
            "Optionally filter by 'asset_filter' (e.g. 'operations_security')."
        ),
        args_schema=VectorRetrievalInput,
    )


# ---------------------------------------------------------------------------
# Ingest helper (called once during setup)
# ---------------------------------------------------------------------------

def ingest_cis_scenarios(
    scenarios: List[Dict[str, Any]],
    config: VectorStoreConfig,
) -> int:
    """
    Embed and upsert all CIS risk scenarios into the vector store.

    Example:
        from tools.control_loader import load_cis_scenarios
        from tools.vectorstore_retrieval import ingest_cis_scenarios, VectorStoreConfig

        scenarios = load_cis_scenarios("cis_controls_v8_1_risk_controls.yaml")
        n = ingest_cis_scenarios(
            [s.model_dump() for s in scenarios],
            VectorStoreConfig(backend="chroma", collection="cis_controls_v8_1"),
        )
        print(f"Ingested {n} scenarios")
    """
    retriever = VectorStoreRetriever(config)
    # Add document_type metadata
    for s in scenarios:
        s["document_type"] = "scenarios"
    return retriever.ingest(scenarios)


def ingest_attack_techniques(
    techniques: List[Dict[str, Any]],
    config: VectorStoreConfig,
) -> int:
    """
    Ingest ATT&CK techniques into the vector store for semantic search.

    Each technique dict should have: technique_id, name, description, tactics,
    platforms, data_sources, detection, url.
    """
    return ingest_framework_documents(
        documents=techniques,
        config=config,
        document_type="techniques",
    )


def ingest_framework_documents(
    documents: List[Dict[str, Any]],
    config: VectorStoreConfig,
    document_type: str = "scenarios",
) -> int:
    """
    Generic ingestion function for any framework document type.
    
    Args:
        documents: List of document dictionaries
        config: VectorStoreConfig with collection name
        document_type: Type of document ("scenarios", "controls", "requirements", "risks", "test_cases")
        
    Returns:
        Number of documents ingested
    """
    retriever = VectorStoreRetriever(config)
    
    # Add document_type metadata to each document
    for doc in documents:
        doc["document_type"] = document_type
    
    return retriever.ingest(documents)
