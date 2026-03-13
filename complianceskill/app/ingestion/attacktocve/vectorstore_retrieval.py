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

    tool = create_vectorstore_tool(
        VectorStoreConfig(backend="qdrant", collection="cis_controls", ...)
    )

The tool also ships an ingest helper:
    from tools.vectorstore_retrieval import ingest_cis_scenarios
    ingest_cis_scenarios(scenarios, config)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class VectorBackend(str, Enum):
    QDRANT = "qdrant"
    CHROMA = "chroma"


class VectorStoreConfig(BaseModel):
    backend: VectorBackend = VectorBackend.CHROMA
    collection: str = "cis_controls_v8_1"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None

    # Chroma
    chroma_persist_dir: str = "./chroma_store"
    chroma_host: Optional[str] = None   # set for remote Chroma server
    chroma_port: int = 8000

    # Embedding
    embedding_model: str = "text-embedding-3-small"  # OpenAI model name
    openai_api_key: Optional[str] = None

    # Retrieval
    top_k: int = 5
    score_threshold: float = 0.30       # minimum cosine similarity


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
    ) -> List[RetrievedScenario]:
        client = self._get_client()
        query_vector = self._embedder.embed_query(query)

        # Optional payload filter
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qdrant_filter = None
        if asset_filter:
            qdrant_filter = Filter(
                must=[FieldCondition(key="asset", match=MatchValue(value=asset_filter))]
            )

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

    def ingest(self, scenarios: List[Dict[str, Any]]) -> int:
        """Upsert CIS scenarios into Qdrant collection."""
        from qdrant_client import QdrantClient
        from qdrant_client.models import (
            Distance, VectorParams, PointStruct, PayloadSchemaType
        )

        client = self._get_client()

        # Ensure collection exists
        existing = [c.name for c in client.get_collections().collections]
        if self.config.collection not in existing:
            client.create_collection(
                collection_name=self.config.collection,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
            client.create_payload_index(
                collection_name=self.config.collection,
                field_name="asset",
                field_schema=PayloadSchemaType.KEYWORD,
            )

        points = []
        for i, s in enumerate(scenarios):
            description = s.get("description", "") or ""
            text = f"{s['name']}. {description}" if description else s['name']
            vector = self._embedder.embed_query(text)
            payload = {
                "scenario_id": s["scenario_id"],
                "name": s["name"],
                "asset": s["asset"],
                "trigger": s["trigger"],
                "loss_outcomes": ",".join(s.get("loss_outcomes", [])),
                "description": description[:2000] if description else "",  # Qdrant payload limit
                "controls": ",".join(s.get("controls", [])),
            }
            points.append(PointStruct(id=i, vector=vector, payload=payload))

        client.upsert(collection_name=self.config.collection, points=points)
        logger.info(f"Upserted {len(points)} scenarios into Qdrant [{self.config.collection}]")
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
    ) -> List[RetrievedScenario]:
        collection = self._get_collection()
        query_embedding = self._embedder.embed_query(query)

        where_clause = {"asset": {"$eq": asset_filter}} if asset_filter else None

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

    def ingest(self, scenarios: List[Dict[str, Any]]) -> int:
        """Upsert CIS scenarios into Chroma collection."""
        collection = self._get_collection()

        ids, embeddings, documents, metadatas = [], [], [], []
        for s in scenarios:
            description = s.get("description", "") or ""
            text = f"{s['name']}. {description}" if description else s['name']
            ids.append(s["scenario_id"])
            embeddings.append(self._embedder.embed_query(text))
            documents.append(text[:2000])
            metadatas.append({
                "scenario_id": s["scenario_id"],
                "name": s["name"],
                "asset": s["asset"],
                "trigger": s["trigger"],
                "loss_outcomes": ",".join(s.get("loss_outcomes", [])),
                "description": description[:2000] if description else "",
                "controls": ",".join(s.get("controls", [])),
            })

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(ids)} scenarios into Chroma [{self.config.collection}]")
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
    ) -> List[RetrievedScenario]:
        k = top_k or self.config.top_k
        return self._impl.retrieve(query, k, asset_filter)

    def ingest(self, scenarios: List[Dict[str, Any]]) -> int:
        return self._impl.ingest(scenarios)


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
            results = retriever.retrieve(query, top_k=top_k, asset_filter=asset_filter)
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
    return retriever.ingest(scenarios)
