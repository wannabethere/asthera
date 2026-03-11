"""
Vector-Store-Backed Causal Graph Builder

Implements the vector-store approach for causal graph construction:
- Uses unified VectorStoreClient (ChromaDB/Qdrant) for semantic search
- Postgres for structural adjacency lookups
- Single LLM call for graph assembly (replaces N1-N5 pipeline)

Based on vector_causal_graph_builder.py but adapted for:
- Unified storage architecture (app.storage.vector_store)
- CSOD workflow integration
- LMS/HR vertical support
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import networkx as nx
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
from app.storage.vector_store import get_vector_store_client, VectorStoreClient
from app.core.settings import get_settings
from app.agents.csod.csod_tool_integration import run_async

logger = logging.getLogger(__name__)

# Collection names
EDGE_COLLECTION = "cce_causal_edges"
NODE_COLLECTION = "cce_causal_nodes"

# Module-level singleton
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
                await client.initialize()
                _embeddings_model = await client.get_embeddings_model()
            except Exception as e:
                logger.warning(f"Failed to get embeddings model: {e}")
                return None
    return _embeddings_model


# ============================================================================
# SECTION 1 — Document Conversion Helpers
# ============================================================================

def _node_to_document(node: Dict[str, Any]) -> Tuple[str, str, Dict]:
    """
    Convert a node dict → (doc_id, doc_text, metadata).
    
    doc_text is what gets embedded. It packs the causal role description
    alongside the metric name and category for semantic search.
    """
    node_id = node.get("node_id", node.get("metric_ref", str(uuid.uuid4())))

    doc_text = (
        f"{node.get('name', node_id)} "
        f"{node.get('category', '')} "
        f"{node.get('node_type', '')} node. "
        f"{node.get('description', '')} "
        f"temporal grain: {node.get('temporal_grain', 'monthly')}. "
        f"{'leading indicator.' if node.get('is_leading_indicator') else ''}"
        f"{'lagging outcome.' if node.get('is_lagging_indicator') else ''}"
    ).strip()

    metadata = {
        "node_id":          node_id,
        "metric_ref":       node.get("metric_ref", node_id),
        "category":         node.get("category", ""),
        "node_type":        node.get("node_type", "mediator"),
        "temporal_grain":   node.get("temporal_grain", "monthly"),
        "observable":       str(node.get("observable", True)),
        "latent_proxy":     node.get("latent_proxy", "") or "",
        "is_outcome":       str(node.get("node_type") == "terminal"),
        "collider_warning": str(node.get("node_type") == "collider"),
        "vertical":         node.get("vertical", "lms"),
        "source":           node.get("source", "seed"),
    }
    return node_id, doc_text, metadata


def _edge_to_document(edge: Dict[str, Any]) -> Tuple[str, str, Dict]:
    """
    Convert a corpus entry / edge dict → (doc_id, doc_text, metadata).
    
    doc_text embeds the mechanism verbatim for semantic search.
    """
    edge_id = edge.get(
        "edge_id",
        edge.get("entry_id", f"E_{edge.get('source_node_id','')}_{edge.get('target_node_id','')}"),
    )

    src_name = edge.get("source_name", edge.get("source_node_id", ""))
    tgt_name = edge.get("target_name", edge.get("target_node_id", ""))

    doc_text = (
        f"{src_name} causes {tgt_name}: {edge.get('mechanism', '')} "
        f"Direction: {edge.get('direction', 'positive')}. "
        f"Lag: {edge.get('lag_window_days', 14)} days. "
        f"Evidence: {edge.get('evidence_type', 'operational_study')}. "
        f"Domain: {edge.get('domain', '')}."
    ).strip()

    metadata = {
        "edge_id":           edge_id,
        "source_node_id":    edge.get("source_node_id", edge.get("source_node", "")),
        "target_node_id":    edge.get("target_node_id", edge.get("target_node", "")),
        "source_category":   edge.get("source_node_category", edge.get("source_category", "")),
        "target_category":   edge.get("target_node_category", edge.get("target_category", "")),
        "direction":         edge.get("direction", "positive"),
        "lag_window_days":   str(edge.get("lag_window_days", 14)),
        "confidence":        str(edge.get("confidence", edge.get("confidence_score", 0.5))),
        "corpus_match_type": edge.get("corpus_match_type", "confirmed"),
        "evidence_type":     edge.get("evidence_type", "operational_study"),
        "vertical":          edge.get("vertical", "lms"),
        "domain":            edge.get("domain", ""),
        "provenance":        edge.get("provenance", ""),
        "source":            edge.get("source", "seed"),
    }
    return edge_id, doc_text, metadata


# ============================================================================
# SECTION 2 — Ingestion Helpers
# ============================================================================

async def ingest_nodes(
    nodes: List[Dict[str, Any]],
    batch_size: int = 50,
) -> int:
    """
    Upsert a list of node dicts into the node collection using VectorStoreClient.
    
    Returns the number of nodes ingested.
    """
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.error("Vector store client not available for node ingestion")
        return 0
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass  # Already initialized
    
    ids, docs, metas = [], [], []
    for node in nodes:
        doc_id, doc_text, metadata = _node_to_document(node)
        ids.append(doc_id)
        docs.append(doc_text)
        metas.append(metadata)

    # Process in batches
    ingested = 0
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_docs = docs[i:i + batch_size]
        batch_metas = metas[i:i + batch_size]
        
        await vector_store_client.add_documents(
            collection_name=NODE_COLLECTION,
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids,
        )
        ingested += len(batch_ids)

    logger.info(f"ingest_nodes: upserted {ingested} nodes into {NODE_COLLECTION}")
    return ingested


async def ingest_edges(
    edges: List[Dict[str, Any]],
    batch_size: int = 50,
) -> int:
    """
    Upsert a list of edge / corpus entry dicts into the edge collection.
    
    Returns the number of edges ingested.
    """
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.error("Vector store client not available for edge ingestion")
        return 0
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass  # Already initialized
    
    ids, docs, metas = [], [], []
    for edge in edges:
        doc_id, doc_text, metadata = _edge_to_document(edge)
        ids.append(doc_id)
        docs.append(doc_text)
        metas.append(metadata)

    ingested = 0
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_docs = docs[i:i + batch_size]
        batch_metas = metas[i:i + batch_size]
        
        await vector_store_client.add_documents(
            collection_name=EDGE_COLLECTION,
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids,
        )
        ingested += len(batch_ids)

    logger.info(f"ingest_edges: upserted {ingested} edges into {EDGE_COLLECTION}")
    return ingested


# ============================================================================
# SECTION 3 — Retrieval Helpers
# ============================================================================

async def retrieve_causal_nodes(
    query: str,
    vertical: str = "lms",
    n_results: int = 20,
    confidence_floor: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most semantically relevant causal nodes for a query.
    
    Uses VectorStoreClient for semantic search.
    """
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.warning("Vector store client not available")
        return []
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass
    
    # Normalize filter for vector store
    where_filter = vector_store_client.normalize_filter({"vertical": vertical}) if vertical else None
    
    try:
        results = await vector_store_client.query(
            collection_name=NODE_COLLECTION,
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
        )
        
        nodes = []
        if results and results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                dist = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 1.0
                
                # Convert distance to similarity score
                similarity = 1.0 - (dist / 2.0) if dist <= 2.0 else 0.0
                if similarity < confidence_floor:
                    continue
                
                node = dict(meta)
                node["_doc_text"] = doc
                node["_retrieval_score"] = round(similarity, 4)
                # Re-cast booleans (vector stores may store as strings)
                node["observable"] = str(node.get("observable", "True")).lower() == "true"
                node["is_outcome"] = str(node.get("is_outcome", "False")).lower() == "true"
                node["collider_warning"] = str(node.get("collider_warning", "False")).lower() == "true"
                nodes.append(node)
        
        logger.debug(f"retrieve_causal_nodes: '{query[:60]}' → {len(nodes)} nodes")
        return nodes
    except Exception as e:
        logger.error(f"Failed to retrieve causal nodes: {e}", exc_info=True)
        return []


async def retrieve_causal_edges(
    query: str,
    node_ids: List[str],
    vertical: str = "lms",
    n_results: int = 30,
    min_confidence: float = 0.45,
    conn_string: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve causal edges relevant to the query AND anchored to the retrieved nodes.
    
    Two-phase retrieval:
        Phase 1 — semantic: query the edge collection with the user question
        Phase 2 — structural: filter to edges where source OR target is in node_ids
                    OR use Postgres adjacency lookup if available
    """
    if not node_ids:
        return []
    
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.warning("Vector store client not available")
        return []
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass
    
    # Phase 1: semantic retrieval
    where_filter = vector_store_client.normalize_filter({"vertical": vertical}) if vertical else None
    semantic_n = min(n_results * 2, 100)  # Cast wider net
    
    try:
        results = await vector_store_client.query(
            collection_name=EDGE_COLLECTION,
            query_texts=[query],
            n_results=semantic_n,
            where=where_filter,
        )
        
        node_id_set = set(node_ids)
        edges = []
        
        if results and results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                dist = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 1.0
                
                similarity = 1.0 - (dist / 2.0) if dist <= 2.0 else 0.0
                conf = float(meta.get("confidence", 0.5))
                
                # Phase 2: connectivity filter
                src = meta.get("source_node_id", "")
                tgt = meta.get("target_node_id", "")
                is_connected = (src in node_id_set) or (tgt in node_id_set)
                
                if not is_connected or conf < min_confidence:
                    continue
                
                edge = dict(meta)
                edge["_doc_text"] = doc
                edge["_retrieval_score"] = round(similarity, 4)
                edge["lag_window_days"] = int(meta.get("lag_window_days", 14))
                edge["confidence"] = conf
                edges.append(edge)
    except Exception as e:
        logger.error(f"Failed to retrieve causal edges semantically: {e}", exc_info=True)
        edges = []
    
    # Phase 3: Postgres structural lookup (if available)
    structural_edges = []
    if conn_string:
        try:
            from app.agents.csod.csod_causal_graph import fetch_adjacent_edges_pg
            structural_edges = await asyncio.to_thread(
                fetch_adjacent_edges_pg,
                conn_string, node_ids, vertical, min_confidence
            )
            # Add structural edges that weren't already found
            existing_edge_ids = {e.get("edge_id", "") for e in edges}
            for se in structural_edges:
                if se.get("edge_id", "") not in existing_edge_ids:
                    se["_retrieval_score"] = 0.70  # structural match
                    edges.append(se)
        except Exception as e:
            logger.debug(f"Postgres structural lookup failed (non-fatal): {e}")
    
    # Sort by confidence × retrieval_score
    edges.sort(
        key=lambda e: e.get("confidence", 0.5) * e.get("_retrieval_score", 0.5),
        reverse=True,
    )
    
    logger.debug(f"retrieve_causal_edges: '{query[:60]}' → {len(edges)} edges")
    return edges[:n_results]


# ============================================================================
# SECTION 4 — LLM Graph Assembly
# ============================================================================

_ASSEMBLY_SYSTEM_PROMPT = """You are a causal graph assembler for an enterprise LMS/HR analytics platform.

You are given:
1. A user question about LMS / HR metrics
2. A set of RETRIEVED NODES — pre-validated, typed causal nodes from a curated knowledge base
3. A set of RETRIEVED EDGES — pre-validated causal relationships from a curated corpus

Your task has THREE parts:

PART A — SELECT the nodes and edges that are relevant to the question.
  - Do NOT invent new nodes or edges. Work only from the retrieved candidates.
  - A node is relevant if it lies on a causal path to or from the outcome the question is about.
  - An edge is relevant if both its source AND target are in your selected node set.
  - Mark the primary outcome node as the terminal. There should be exactly 1–3 terminals.
  - Mark upstream exogenous nodes (no parents in scope) as root.

PART B — IDENTIFY structural properties:
  - Colliders: nodes caused by 2+ INDEPENDENT parents. Mark collider_warning=true.
    CRITICAL: Never use a collider as a filter. Flag this in the output.
  - Confounders: nodes that independently cause 2+ other nodes.
  - Hot paths: the 2–3 chains with highest mean edge confidence × 1/lag_days.

PART C — Synthesise a plain-language DIAGNOSIS relevant to the question.
  - 2–4 sentences. State the most likely causal mechanism for what the question asks about.
  - Name the root cause, the mechanism pathway, and the outcome.
  - If a collider warning applies, state it explicitly.

Return ONLY valid JSON:
{
  "selected_nodes": [
    {
      "node_id":        "string",
      "metric_ref":     "string",
      "category":       "string",
      "node_type":      "root|mediator|confounder|collider|terminal",
      "temporal_grain": "string",
      "observable":     true,
      "description":    "string — causal role in this graph, 1–2 sentences",
      "collider_warning": false,
      "is_outcome":     false
    }
  ],
  "selected_edges": [
    {
      "edge_id":        "string",
      "source_node":    "node_id",
      "target_node":    "node_id",
      "direction":      "positive|negative",
      "mechanism":      "string",
      "lag_window_days": 14,
      "confidence_score": 0.80,
      "corpus_match_type": "confirmed|analogous|novel"
    }
  ],
  "terminal_nodes":  ["node_id"],
  "root_nodes":      ["node_id"],
  "collider_nodes":  ["node_id"],
  "confounder_nodes": ["node_id"],
  "hot_paths": [
    {
      "path":            ["node_id", "node_id", "node_id"],
      "path_confidence": 0.78,
      "lag_total_days":  21
    }
  ],
  "diagnosis": "string — plain-language causal mechanism summary",
  "coverage_note": "string — what the retrieved set covers well / what it misses"
}"""


def assemble_causal_graph_with_llm(
    question: str,
    retrieved_nodes: List[Dict[str, Any]],
    retrieved_edges: List[Dict[str, Any]],
    llm: Any,  # BaseChatModel from langchain (obtained via get_llm())
) -> Dict[str, Any]:
    """
    Single LLM call: select relevant nodes+edges and assemble the causal graph.
    
    This replaces N1 (decomposer) + N2 (node proposer) + N3 (edge proposer)
    + N4 (lag estimator) + N5 (validation) in one shot.
    
    Args:
        question: User's natural language question
        retrieved_nodes: List of retrieved causal nodes
        retrieved_edges: List of retrieved causal edges
        llm: LLM instance (obtained via get_llm() from dependencies)
    
    Returns:
        Dict with selected_nodes, selected_edges, terminal_nodes, etc.
    """
    # Build compact representations for the prompt
    node_lines = []
    for n in retrieved_nodes[:25]:
        node_lines.append(
            f"- [{n['node_id']}] type={n['node_type']}, cat={n['category']}, "
            f"grain={n['temporal_grain']}, observable={n['observable']}, "
            f"score={n['_retrieval_score']:.2f} | {n.get('_doc_text', '')[:120]}"
        )

    edge_lines = []
    for e in retrieved_edges[:35]:
        edge_lines.append(
            f"- [{e['edge_id']}] {e['source_node_id']} → {e['target_node_id']} "
            f"({e['direction']}, lag={e['lag_window_days']}d, conf={e['confidence']:.2f}, "
            f"match={e['corpus_match_type']}, score={e['_retrieval_score']:.2f}) | "
            f"{e.get('_doc_text', '')[:150]}"
        )

    human_message = f"""QUESTION: {question}

RETRIEVED NODES ({len(retrieved_nodes[:25])} candidates):
{chr(10).join(node_lines) or 'None retrieved'}

RETRIEVED EDGES ({len(retrieved_edges[:35])} candidates):
{chr(10).join(edge_lines) or 'None retrieved'}

Select the relevant subset, identify structural properties, and produce the diagnosis.
Return JSON only."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", _ASSEMBLY_SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    chain = prompt | llm
    response = chain.invoke({"input": human_message})
    raw = response.content if hasattr(response, "content") else str(response)

    # Parse JSON with fence fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for pat in (r'```json\s*(\{.*?\})\s*```', r'(\{.*\})'):
            m = re.search(pat, raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
    logger.warning("assemble_causal_graph_with_llm: failed to parse LLM response")
    return {"selected_nodes": [], "selected_edges": [], "diagnosis": "Assembly failed"}


# ============================================================================
# SECTION 5 — LangGraph Node (drop-in for CSOD workflow)
# ============================================================================

def vector_causal_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single LangGraph node that replaces the N1→N5 chain using vector retrieval.
    
    Reads from state:
        user_query              — the original question
        causal_vertical         — e.g. 'lms'
        causal_metric_registry   — metric registry (used to infer query terms)
        cce_db_url              — optional Postgres connection string
    
    Writes to state:
        causal_proposed_nodes    — selected nodes
        causal_proposed_edges    — selected edges
        causal_graph_metadata    — partial metadata
        causal_assembly_result   — full LLM assembly output
        causal_retrieval_stats   — retrieval statistics
    """
    try:
        question = state.get("user_query", "")
        vertical = state.get("causal_vertical", state.get("vertical", "lms"))
        conn_string = state.get("cce_db_url") or os.environ.get("CCE_DB_URL")

        # ── Build an enriched retrieval query ────────────────────────────────
        metric_registry = state.get("causal_metric_registry", state.get("metric_registry", []))
        enriched_query = question
        if metric_registry and len(question.split()) < 8:
            top_categories = list({
                m.get("category", "") for m in metric_registry[:10] if m.get("category")
            })[:5]
            enriched_query = f"{question} {' '.join(top_categories)}"

        # ── Retrieve nodes and edges (async) ──────────────────────────────────
        async def _retrieve():
            nodes = await retrieve_causal_nodes(
                query=enriched_query,
                vertical=vertical,
                n_results=20,
            )
            
            if not nodes:
                return [], []
            
            node_ids = [n["node_id"] for n in nodes]
            edges = await retrieve_causal_edges(
                query=enriched_query,
                node_ids=node_ids,
                vertical=vertical,
                n_results=30,
                min_confidence=0.45,
                conn_string=conn_string,
            )
            return nodes, edges
        
        retrieved_nodes, retrieved_edges = run_async(_retrieve())

        if not retrieved_nodes:
            logger.warning("vector_causal_graph_node: no nodes retrieved — graph will be empty")
            state.setdefault("causal_proposed_nodes", [])
            state.setdefault("causal_proposed_edges", [])
            return state

        # ── LLM assembly ─────────────────────────────────────────────────────
        # Get LLM instance from dependencies
        llm = get_llm(temperature=0)
        assembly = assemble_causal_graph_with_llm(
            question=question,
            retrieved_nodes=retrieved_nodes,
            retrieved_edges=retrieved_edges,
            llm=llm,
        )

        # ── Map to causal engine state fields ─────────────────────────────────
        proposed_nodes = []
        for n in assembly.get("selected_nodes", []):
            proposed_nodes.append({
                "node_id":          n.get("node_id", ""),
                "metric_ref":       n.get("metric_ref", n.get("node_id", "")),
                "category":         n.get("category", ""),
                "node_type":        n.get("node_type", "mediator"),
                "observable":       n.get("observable", True),
                "latent_proxy":     n.get("latent_proxy"),
                "temporal_grain":   n.get("temporal_grain", "monthly"),
                "description":      n.get("description", ""),
                "parent_count":     0,  # computed later
                "child_count":      0,
                "collider_warning": n.get("collider_warning", False),
                "is_outcome":       n.get("is_outcome", n.get("node_type") == "terminal"),
            })

        proposed_edges = []
        for idx, e in enumerate(assembly.get("selected_edges", [])):
            proposed_edges.append({
                "edge_id":          e.get("edge_id", f"VE{idx:03d}"),
                "source_node":      e.get("source_node", e.get("source_node_id", "")),
                "target_node":      e.get("target_node", e.get("target_node_id", "")),
                "lag_window_days":  e.get("lag_window_days", 14),
                "lag_confidence":   0.75,
                "direction":        e.get("direction", "positive"),
                "mechanism":        e.get("mechanism", ""),
                "confounders":      e.get("confounders", []),
                "confidence_score": e.get("confidence_score", e.get("confidence", 0.65)),
                "corpus_validated": True,
                "corpus_match_type": e.get("corpus_match_type", "confirmed"),
                "flags":            [],
            })

        # Partial metadata
        partial_metadata = {
            "node_count":             len(proposed_nodes),
            "edge_count":             len(proposed_edges),
            "terminal_node_ids":      assembly.get("terminal_nodes", []),
            "collider_node_ids":      assembly.get("collider_nodes", []),
            "confounder_node_ids":    assembly.get("confounder_nodes", []),
            "hot_paths":              assembly.get("hot_paths", []),
            "show_causal_graph":      len(proposed_nodes) >= 3,
            "coverage_note":          assembly.get("coverage_note", ""),
        }

        state["causal_proposed_nodes"]  = proposed_nodes
        state["causal_proposed_edges"]  = proposed_edges
        state["causal_graph_metadata"]  = partial_metadata
        state["causal_assembly_result"] = assembly
        state["causal_retrieval_stats"] = {
            "nodes_retrieved":    len(retrieved_nodes),
            "edges_retrieved":    len(retrieved_edges),
            "nodes_selected":     len(proposed_nodes),
            "edges_selected":     len(proposed_edges),
            "enriched_query":     enriched_query,
        }

        # Populate decomposed groups for downstream compatibility
        state["causal_decomposed_metric_groups"] = [{
            "group_id":          "vector_retrieved",
            "group_name":        "Vector-Retrieved Causal Group",
            "domain_theme":      vertical,
            "metric_ids":        [n["node_id"] for n in proposed_nodes],
            "terminal_candidates": assembly.get("terminal_nodes", []),
            "bridging_metrics":  [],
            "rationale":         f"Assembled via vector retrieval for: '{question[:80]}'",
        }]

        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"[VectorCausal] Retrieved {len(retrieved_nodes)} nodes, {len(retrieved_edges)} edges → "
                f"selected {len(proposed_nodes)} nodes, {len(proposed_edges)} edges | "
                f"Diagnosis: {assembly.get('diagnosis', '')[:100]}"
            )
        ))

        logger.info(
            f"vector_causal_graph_node: {len(proposed_nodes)} nodes, "
            f"{len(proposed_edges)} edges assembled for '{question[:60]}'"
        )

    except Exception as e:
        logger.error(f"vector_causal_graph_node failed: {e}", exc_info=True)
        state["error"] = f"VectorCausalGraph failed: {str(e)}"
        state.setdefault("causal_proposed_nodes", [])
        state.setdefault("causal_proposed_edges", [])

    return state
