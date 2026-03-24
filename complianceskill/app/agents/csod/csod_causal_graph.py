"""
CSOD Causal Graph Retrieval Module

Implements hybrid causal graph retrieval using:
- VectorStoreClient (ChromaDB/Qdrant) for semantic edge/node discovery
- Postgres for structural adjacency lookups
- LRU cache for embedding reuse

Based on hybrid_causal_graph.md design pattern.
Uses the unified storage architecture from app.storage.vector_store and app.storage.documents.
"""
from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning("psycopg2 not available, causal graph retrieval will be limited")

from app.storage.vector_store import get_vector_store_client, VectorStoreClient
from app.core.settings import get_settings
from app.agents.causalgraph.vector_causal_graph_builder import (
    lms_causal_edge_collection,
    lms_causal_node_collection,
)

logger = logging.getLogger(__name__)

# Module-level singleton for vector store client and embeddings
_vector_store_client: Optional[VectorStoreClient] = None
_embeddings_model = None


def _get_vector_store_client() -> Optional[VectorStoreClient]:
    """Get or create the vector store client singleton."""
    global _vector_store_client
    if _vector_store_client is None:
        try:
            settings = get_settings()
            config = settings.get_vector_store_config()
            _vector_store_client = get_vector_store_client(config=config)
        except Exception as e:
            logger.warning(f"Failed to initialize vector store client: {e}")
            return None
    return _vector_store_client


async def _get_embeddings_model():
    """Get or create the embeddings model from vector store client."""
    global _embeddings_model
    if _embeddings_model is None:
        client = _get_vector_store_client()
        if client:
            try:
                # Initialize client if needed
                await client.initialize()
                _embeddings_model = await client.get_embeddings_model()
            except Exception as e:
                logger.warning(f"Failed to get embeddings model: {e}")
                return None
    return _embeddings_model


# ============================================================================
# 1. Embedding cache — compute once, reuse for both collections
# ============================================================================

# Cache for embeddings (keyed by query text)
_embedding_cache: Dict[str, List[float]] = {}


async def get_query_embedding(query: str) -> List[float]:
    """
    Compute and cache the embedding for a query string.
    
    Uses the vector store client's embeddings model.
    Caches results in-memory to avoid redundant computation.
    Returns a list (vector stores expect list, not tuple).
    """
    # Check cache first
    if query in _embedding_cache:
        return _embedding_cache[query]
    
    # Get embeddings model
    embeddings_model = await _get_embeddings_model()
    if embeddings_model is None:
        logger.warning("Embeddings model not available, returning empty embedding")
        return []
    
    try:
        # Use the embeddings model to embed the query
        vec = await asyncio.to_thread(embeddings_model.embed_query, query)
        # Cache the result
        _embedding_cache[query] = vec
        return vec
    except Exception as e:
        logger.error(f"Failed to compute embedding: {e}", exc_info=True)
        return []


# ============================================================================
# 2. Postgres adjacency table helpers
# ============================================================================

ADJACENCY_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS cce.causal_adjacency (
    edge_id             VARCHAR(100) PRIMARY KEY,
    source_node_id      VARCHAR(200) NOT NULL,
    target_node_id      VARCHAR(200) NOT NULL,
    direction           VARCHAR(20)  NOT NULL DEFAULT 'positive',
    lag_window_days     INTEGER      NOT NULL DEFAULT 14,
    confidence          NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    corpus_match_type   VARCHAR(30)  NOT NULL DEFAULT 'confirmed',
    evidence_type       VARCHAR(50)  NOT NULL DEFAULT 'operational_study',
    mechanism           TEXT,
    vertical            VARCHAR(50)  NOT NULL DEFAULT 'lms',
    domain              VARCHAR(100),
    provenance          TEXT,
    source              VARCHAR(30)  NOT NULL DEFAULT 'seed',
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_causal_adj_source
    ON cce.causal_adjacency (source_node_id, vertical);

CREATE INDEX IF NOT EXISTS idx_causal_adj_target
    ON cce.causal_adjacency (target_node_id, vertical);

CREATE INDEX IF NOT EXISTS idx_causal_adj_src_tgt_vertical
    ON cce.causal_adjacency (vertical, source_node_id, target_node_id);
"""


def bootstrap_adjacency_table(conn_string: str) -> None:
    """Run DDL once. Safe to call multiple times (IF NOT EXISTS)."""
    if not POSTGRES_AVAILABLE:
        logger.warning("Postgres not available, skipping adjacency table bootstrap")
        return
    
    try:
        with psycopg2.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(ADJACENCY_TABLE_DDL)
            conn.commit()
        logger.info("cce.causal_adjacency table and indexes are ready")
    except Exception as e:
        logger.error(f"Failed to bootstrap adjacency table: {e}", exc_info=True)


def fetch_adjacent_edges_pg(
    conn_string: str,
    node_ids: List[str],
    vertical: str = "lms",
    min_confidence: float = 0.45,
    domains: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Single indexed Postgres query replacing the 20-call ChromaDB loop.
    
    Uses ANY(ARRAY[...]) which lets Postgres use the B-tree index on
    source_node_id and target_node_id in a single pass.
    """
    if not POSTGRES_AVAILABLE or not node_ids:
        return []
    
    try:
        clean_domains = [d for d in (domains or []) if d and d != "_shared"]
        domain_filter = clean_domains if len(clean_domains) > 1 else None
        if domain_filter:
            sql = """
                SELECT
                    edge_id, source_node_id, target_node_id,
                    direction, lag_window_days, confidence,
                    corpus_match_type, evidence_type, mechanism,
                    vertical, domain, provenance, source
                FROM cce.causal_adjacency
                WHERE vertical = ANY(%(domains)s)
                  AND confidence >= %(min_conf)s
                  AND (
                      source_node_id = ANY(%(node_ids)s)
                      OR
                      target_node_id = ANY(%(node_ids)s)
                  )
                ORDER BY confidence DESC
            """
            params = {
                "domains": domain_filter,
                "min_conf": min_confidence,
                "node_ids": node_ids,
            }
        else:
            sql = """
                SELECT
                    edge_id, source_node_id, target_node_id,
                    direction, lag_window_days, confidence,
                    corpus_match_type, evidence_type, mechanism,
                    vertical, domain, provenance, source
                FROM cce.causal_adjacency
                WHERE vertical = %(vertical)s
                  AND confidence >= %(min_conf)s
                  AND (
                      source_node_id = ANY(%(node_ids)s)
                      OR
                      target_node_id = ANY(%(node_ids)s)
                  )
                ORDER BY confidence DESC
            """
            params = {
                "vertical": vertical,
                "min_conf": min_confidence,
                "node_ids": node_ids,
            }
        with psycopg2.connect(conn_string) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to fetch adjacent edges from Postgres: {e}", exc_info=True)
        return []


# ============================================================================
# 3. Hybrid retrieval — semantic + structural, parallel, one embedding
# ============================================================================


async def hybrid_retrieve(
    query: str,
    vector_store_client: Optional[VectorStoreClient] = None,
    conn_string: Optional[str] = None,
    vertical: str = "lms",
    node_n: int = 20,
    edge_semantic_n: int = 30,
    min_confidence: float = 0.45,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Full hybrid retrieval in three concurrent operations.
    
    Operation A: Vector store node semantic search (async)
    Operation B: Vector store edge semantic search (async)
    Operation C: Postgres structural adjacency fetch (after nodes retrieved)
    
    Returns:
        Tuple of (retrieved_nodes, retrieved_edges)
    """
    retrieved_nodes = []
    semantic_edges = []
    structural_edges = []
    
    # Step 1: embed once
    embedding = await get_query_embedding(query)
    
    if not embedding:
        logger.warning("No embedding available, returning empty results")
        return [], []
    
    # Get vector store client if not provided
    if vector_store_client is None:
        vector_store_client = _get_vector_store_client()
    
    if vector_store_client is None:
        logger.warning("Vector store client not available, returning empty results")
        return [], []
    
    # Step 2: Vector store node + edge searches in parallel
    async def _search_nodes():
        try:
            # Normalize filter for vector store
            where_filter = vector_store_client.normalize_filter({"vertical": vertical})
            
            results = await vector_store_client.query(
                collection_name=lms_causal_node_collection(),
                query_embeddings=[embedding],
                n_results=node_n,
                where=where_filter,
            )
            
            nodes = []
            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                    dist = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 1.0
                    
                    node = dict(meta)
                    node["_doc_text"] = doc
                    node["_retrieval_score"] = round(1.0 - dist / 2.0, 4) if dist <= 2.0 else 0.0
                    node["observable"] = str(meta.get("observable", "True")).lower() == "true"
                    node["is_outcome"] = str(meta.get("is_outcome", "False")).lower() == "true"
                    node["collider_warning"] = str(meta.get("collider_warning", "False")).lower() == "true"
                    nodes.append(node)
            return nodes
        except Exception as e:
            logger.error(f"Vector store node search failed: {e}", exc_info=True)
            return []
    
    async def _search_edges_semantic():
        try:
            # Normalize filter for vector store
            where_filter = vector_store_client.normalize_filter({"vertical": vertical})
            
            results = await vector_store_client.query(
                collection_name=lms_causal_edge_collection(),
                query_embeddings=[embedding],
                n_results=edge_semantic_n,
                where=where_filter,
            )
            
            edges = []
            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                    dist = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 1.0
                    
                    conf = float(meta.get("confidence", 0.5))
                    if conf < min_confidence:
                        continue
                    
                    edge = dict(meta)
                    edge["_doc_text"] = doc
                    edge["_retrieval_score"] = round(1.0 - dist / 2.0, 4) if dist <= 2.0 else 0.0
                    edge["lag_window_days"] = int(meta.get("lag_window_days", 14))
                    edge["confidence"] = conf
                    edges.append(edge)
            return edges
        except Exception as e:
            logger.error(f"Vector store edge search failed: {e}", exc_info=True)
            return []
    
    # Run vector store searches in parallel
    retrieved_nodes, semantic_edges = await asyncio.gather(
        _search_nodes(),
        _search_edges_semantic(),
    )
    
    # Step 3: structural adjacency fetch — fires immediately after node results
    if conn_string and retrieved_nodes:
        node_ids = [n.get("node_id", "") for n in retrieved_nodes if n.get("node_id")]
        if node_ids:
            # Run Postgres query in thread pool to avoid blocking
            structural_edges = await asyncio.to_thread(
                fetch_adjacent_edges_pg,
                conn_string, node_ids, vertical, min_confidence
            )
    
    # Step 4: merge semantic + structural, deduplicate by edge_id
    merged: Dict[str, Dict] = {}
    for e in structural_edges:
        eid = e.get("edge_id", "")
        if eid:
            e["_retrieval_score"] = 0.70  # structural match, no semantic score
            merged[eid] = e
    
    for e in semantic_edges:
        eid = e.get("edge_id", "")
        if eid:
            if eid in merged:
                # Keep structural metadata but upgrade retrieval score
                merged[eid]["_retrieval_score"] = max(
                    merged[eid]["_retrieval_score"],
                    e["_retrieval_score"],
                )
            else:
                merged[eid] = e
    
    final_edges = sorted(
        merged.values(),
        key=lambda e: e.get("confidence", 0.5) * e.get("_retrieval_score", 0.5),
        reverse=True,
    )[:edge_semantic_n]
    
    logger.debug(
        f"hybrid_retrieve: nodes={len(retrieved_nodes)}, "
        f"edges={len(final_edges)} "
        f"(semantic={len(semantic_edges)}, structural={len(structural_edges)})"
    )
    return retrieved_nodes, final_edges


# ============================================================================
# 4. CSOD-specific causal graph retrieval
# ============================================================================

async def retrieve_causal_graph_for_csod(
    query: str,
    state: Dict[str, Any],
    vertical: str = "lms",
) -> Dict[str, Any]:
    """
    Retrieve causal graph nodes and edges for CSOD workflow.
    
    Args:
        query: User query or metric/question
        state: CSOD workflow state
        vertical: Vertical domain (default: "lms")
    
    Returns:
        Dict with keys: nodes, edges, retrieval_stats
    """
    try:
        # Get configuration from state or environment
        conn_string = state.get("cce_db_url") or os.environ.get("CCE_DB_URL")
        
        # Enrich short queries with category terms
        metric_registry = state.get("causal_metric_registry", [])
        enriched_query = query
        if metric_registry and len(query.split()) < 8:
            top_cats = list({
                m.get("category", "") for m in metric_registry[:10] if m.get("category")
            })[:5]
            enriched_query = f"{query} {' '.join(top_cats)}"
        
        # Get vector store client
        vector_store_client = _get_vector_store_client()
        
        # Perform hybrid retrieval
        retrieved_nodes, retrieved_edges = await hybrid_retrieve(
            query=enriched_query,
            vector_store_client=vector_store_client,
            conn_string=conn_string,
            vertical=vertical,
        )
        
        return {
            "nodes": retrieved_nodes,
            "edges": retrieved_edges,
            "retrieval_stats": {
                "nodes_retrieved": len(retrieved_nodes),
                "edges_retrieved": len(retrieved_edges),
                "query": query,
                "enriched_query": enriched_query,
                "vertical": vertical,
            },
        }
    
    except Exception as e:
        logger.error(f"Failed to retrieve causal graph: {e}", exc_info=True)
        return {
            "nodes": [],
            "edges": [],
            "retrieval_stats": {
                "nodes_retrieved": 0,
                "edges_retrieved": 0,
                "error": str(e),
            },
        }
