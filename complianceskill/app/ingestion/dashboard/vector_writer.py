"""
CCE Dashboard Enricher — Vector Store Writer
=============================================
Embeds and indexes enriched entities into three collections:

  Collection                Purpose                         Retrieval point
  ────────────────────────────────────────────────────────────────────────
  layout_templates          Template similarity scoring     RETRIEVAL POINT 1
  metric_catalog            Per-metric config for spec gen  RETRIEVAL POINT 2
  decision_tree_options     LLM resolution examples         Prompt injection

Embedding:
  Default: OpenAI text-embedding-3-small  (swap _embed() to change)
  Fallback: TF-IDF hash fingerprint       (if embedder unavailable)

Vector store:
  Default: ChromaDB PersistentClient     (swap _get_client() to change)
  Swap candidates: Qdrant, pgvector

Safe to re-run — uses content_hash for skip detection.
"""

from __future__ import annotations

import json
import logging
import os
import hashlib
from typing import Optional

logger = logging.getLogger(__name__)

# ── Try to import optional vector store + embedding libs ──────────────

try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

try:
    from openai import OpenAI as _OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from models import EnrichedTemplate, EnrichedMetric, DecisionTree


# ═══════════════════════════════════════════════════════════════════════
# CLIENT FACTORY — swap this for Qdrant / pgvector
# ═══════════════════════════════════════════════════════════════════════

def _get_client(persist_dir: str):
    """
    ┌─ SWAP POINT ──────────────────────────────────────────────────┐
    │  ChromaDB (default)                                            │
    │    chromadb.PersistentClient(path=persist_dir)                 │
    │  Qdrant                                                        │
    │    from qdrant_client import QdrantClient                      │
    │    QdrantClient(url=os.environ["QDRANT_URL"])                  │
    │  In-memory (dev/test)                                          │
    │    chromadb.Client()                                           │
    └────────────────────────────────────────────────────────────────┘
    """
    if not HAS_CHROMA:
        raise ImportError("chromadb not installed. Run: pip install chromadb")
    return chromadb.PersistentClient(path=persist_dir)


def _get_or_create(client, name: str):
    """Get or create a collection, tolerating both ChromaDB and Qdrant APIs."""
    return client.get_or_create_collection(name)


# ═══════════════════════════════════════════════════════════════════════
# EMBEDDING — swap _embed() to change the embedding model
# ═══════════════════════════════════════════════════════════════════════

def _embed(texts: list[str]) -> list[list[float]]:
    """
    ┌─ SWAP POINT ──────────────────────────────────────────────────┐
    │  OpenAI (default)  model: text-embedding-3-small               │
    │  Cohere            model: embed-english-v3.0                   │
    │  SentenceTransformers  model: all-MiniLM-L6-v2 (local)         │
    │  Fallback: TF-IDF hash fingerprint (no external deps)          │
    └────────────────────────────────────────────────────────────────┘
    """
    if HAS_OPENAI and os.environ.get("OPENAI_API_KEY"):
        client = _OpenAI()
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-small",
        )
        return [r.embedding for r in response.data]

    # ── Fallback: deterministic hash fingerprint (1536-dim, no API) ──
    logger.warning("No embedding API configured — using hash fingerprint fallback")
    return [_hash_embed(t) for t in texts]


def _hash_embed(text: str, dim: int = 1536) -> list[float]:
    """Deterministic float vector from text hash. Not semantic — dev/test only."""
    import struct
    h = hashlib.sha256(text.encode()).digest()
    # Repeat hash bytes to fill dim floats
    raw = (h * ((dim * 4 // len(h)) + 1))[:dim * 4]
    floats = list(struct.unpack(f"{dim}f", raw))
    # Normalise to unit sphere
    norm = sum(x * x for x in floats) ** 0.5 or 1.0
    return [x / norm for x in floats]


# ═══════════════════════════════════════════════════════════════════════
# VECTOR STORE WRITER
# ═══════════════════════════════════════════════════════════════════════

BATCH_SIZE = 32   # embed this many at once to stay within API rate limits


class VectorStoreWriter:
    """
    Indexes enriched entities into three vector store collections.
    Safe to re-run: skips documents where content_hash matches stored metadata.
    """

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            self._client = _get_client(self.persist_dir)

    def _collection(self, name: str):
        self._ensure_client()
        return _get_or_create(self._client, name)

    # ── Templates → "layout_templates" ───────────────────────────────

    def index_templates(self, templates: list[EnrichedTemplate]) -> tuple[int, int]:
        """
        Index all EnrichedTemplates into the 'layout_templates' collection.
        Used by RETRIEVAL POINT 1 in scoring_node.
        Returns (indexed, skipped).
        """
        col = self._collection("layout_templates")
        indexed = skipped = 0

        # Batch process
        to_index = []
        for t in templates:
            existing = _safe_get(col, t.template_id)
            if existing and existing.get("content_hash") == t.content_hash:
                skipped += 1
                continue
            to_index.append(t)

        for batch in _batches(to_index, BATCH_SIZE):
            texts = [t.embedding_text for t in batch]
            embeddings = _embed(texts)

            col.upsert(
                ids=[t.template_id for t in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "template_id":     t.template_id,
                    "registry_source": t.registry_source,
                    "name":            t.name,
                    "category":        t.category.value,
                    "complexity":      t.complexity.value,
                    "focus_areas":     "|".join(t.focus_areas),
                    "destinations":    "|".join(d.value for d in t.supported_destinations),
                    "audience":        "|".join(a.value for a in t.audience_levels),
                    "has_chat":        str(t.has_chat),
                    "has_graph":       str(t.has_graph),
                    "content_hash":    t.content_hash,
                } for t in batch],
            )
            indexed += len(batch)
            logger.info(f"  layout_templates: indexed {indexed}/{len(to_index)}")

        logger.info(f"layout_templates: {indexed} indexed, {skipped} skipped")
        return indexed, skipped

    # ── Metrics → "metric_catalog" ────────────────────────────────────

    def index_metrics(self, metrics: list[EnrichedMetric]) -> tuple[int, int]:
        """
        Index all EnrichedMetrics into the 'metric_catalog' collection.
        Used by RETRIEVAL POINT 2 in retrieve_context_node.
        Returns (indexed, skipped).
        """
        col = self._collection("metric_catalog")
        indexed = skipped = 0

        to_index = []
        for m in metrics:
            existing = _safe_get(col, m.metric_id)
            if existing and existing.get("content_hash") == m.content_hash:
                skipped += 1
                continue
            to_index.append(m)

        for batch in _batches(to_index, BATCH_SIZE):
            texts = [m.embedding_text for m in batch]
            embeddings = _embed(texts)

            col.upsert(
                ids=[m.metric_id for m in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "metric_id":           m.metric_id,
                    "dashboard_id":        m.dashboard_id,
                    "name":                m.name,
                    "display_name":        m.display_name,
                    "metric_type":         m.metric_type,
                    "unit":                m.unit,
                    "chart_type":          m.chart_type,
                    "category":            m.category.value,
                    "metric_profile":      m.metric_profile.value,
                    "focus_areas":         "|".join(m.focus_areas),
                    "source_capabilities": "|".join(m.source_capabilities),
                    "good_direction":      m.good_direction,
                    "axis_label":          m.axis_label,
                    "aggregation":         m.aggregation,
                    "threshold_warning":   str(m.threshold_warning or ""),
                    "threshold_critical":  str(m.threshold_critical or ""),
                    "content_hash":        m.content_hash,
                } for m in batch],
            )
            indexed += len(batch)

        logger.info(f"metric_catalog: {indexed} indexed, {skipped} skipped")
        return indexed, skipped

    # ── Decision Tree Options → "decision_tree_options" ───────────────

    def index_decision_tree(self, tree: DecisionTree) -> int:
        """
        Index each decision option as a separate document in 'decision_tree_options'.
        Used to inject examples into the LLM resolution prompt at runtime.
        Returns number of options indexed.
        """
        col = self._collection("decision_tree_options")
        docs, ids, metas = [], [], []

        for q in tree.questions:
            for opt in q.options:
                doc_id = f"{q.question_id}::{opt.option_id}"
                text = (
                    f"Question: {q.question}\n"
                    f"Option: {opt.label}\n"
                    f"Keywords: {', '.join(opt.keywords)}\n"
                    f"Maps to: {json.dumps(opt.maps_to)}"
                )
                docs.append(text)
                ids.append(doc_id)
                metas.append({
                    "question_id": q.question_id,
                    "option_id":   opt.option_id,
                    "label":       opt.label,
                    "keywords":    "|".join(opt.keywords),
                    "maps_to":     json.dumps(opt.maps_to),
                    "confidence":  str(opt.confidence),
                    "field":       q.field,
                })

        if not docs:
            return 0

        embeddings = _embed(docs)
        # Batch to avoid ChromaDB size limits
        for i in range(0, len(docs), BATCH_SIZE):
            col.upsert(
                ids=ids[i:i+BATCH_SIZE],
                embeddings=embeddings[i:i+BATCH_SIZE],
                documents=docs[i:i+BATCH_SIZE],
                metadatas=metas[i:i+BATCH_SIZE],
            )

        logger.info(f"decision_tree_options: {len(docs)} options indexed")
        return len(docs)

    def collection_counts(self) -> dict[str, int]:
        """Return document count per collection."""
        counts = {}
        for name in ["layout_templates", "metric_catalog", "decision_tree_options"]:
            try:
                col = self._collection(name)
                counts[name] = col.count()
            except Exception:
                counts[name] = -1
        return counts


# ── Utilities ──────────────────────────────────────────────────────────

def _safe_get(col, doc_id: str) -> Optional[dict]:
    """Return metadata for a document ID, or None if not found."""
    try:
        result = col.get(ids=[doc_id], include=["metadatas"])
        if result["metadatas"]:
            return result["metadatas"][0]
    except Exception:
        pass
    return None


def _batches(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]
