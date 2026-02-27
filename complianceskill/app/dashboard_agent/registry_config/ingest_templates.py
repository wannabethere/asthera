"""
CCE Template Vector Store — Ingestion Script
=============================================
Loads all 23 templates (17 base + 6 L&D) into a vector store.
Supports FAISS (in-memory) and ChromaDB (persistent) backends.

Usage:
    # With OpenAI embeddings
    python ingest_templates.py --backend faiss --embeddings openai

    # With HuggingFace local embeddings
    python ingest_templates.py --backend chroma --embeddings huggingface --persist ./chroma_db

    # Verify ingestion
    python ingest_templates.py --verify --query "training compliance dashboard"
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
from typing import Optional

from langchain_core.documents import Document

from registry_unified import (
    ALL_TEMPLATES, ALL_CATEGORIES,
    get_unified_embedding_text, get_ld_templates,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# DOCUMENT BUILDER
# ═══════════════════════════════════════════════════════════════════════

def build_all_documents() -> list[Document]:
    """Build LangChain Documents from all 23 templates."""
    docs = []
    for tid, tpl in ALL_TEMPLATES.items():
        text = get_unified_embedding_text(tpl)

        metadata = {
            "template_id": tid,
            "name": tpl["name"],
            "category": tpl["category"],
            "category_label": ALL_CATEGORIES.get(tpl["category"], {}).get("label", ""),
            "domains": json.dumps(tpl.get("domains", [])),
            "complexity": tpl.get("complexity", "medium"),
            "has_chat": tpl.get("has_chat", False),
            "has_graph": tpl.get("has_graph", False),
            "strip_cells": tpl.get("strip_cells", 0),
            "best_for": json.dumps(tpl.get("best_for", [])),
            "primitives": json.dumps(tpl.get("primitives", [])),
            "theme": tpl.get("theme_hint", "light"),
        }

        # L&D specific metadata
        if tpl.get("chart_types"):
            metadata["chart_types"] = json.dumps(tpl["chart_types"])
        if tpl.get("activity_types"):
            metadata["activity_types"] = json.dumps(tpl["activity_types"])
        if tpl.get("table_columns"):
            if isinstance(tpl["table_columns"], list):
                metadata["table_columns"] = json.dumps(tpl["table_columns"])
            elif isinstance(tpl["table_columns"], dict):
                metadata["table_columns"] = json.dumps(tpl["table_columns"])

        docs.append(Document(page_content=text, metadata=metadata))

    return docs


# ═══════════════════════════════════════════════════════════════════════
# EMBEDDING FACTORY
# ═══════════════════════════════════════════════════════════════════════

def get_embeddings(provider: str = "openai"):
    """Create embeddings based on provider."""
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")

    elif provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

    elif provider == "anthropic":
        # Anthropic doesn't have embeddings API — use Voyage
        from langchain_voyageai import VoyageAIEmbeddings
        return VoyageAIEmbeddings(model="voyage-3-lite")

    elif provider == "fake":
        # For testing without API keys
        from langchain_core.embeddings import FakeEmbeddings
        return FakeEmbeddings(size=384)

    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


# ═══════════════════════════════════════════════════════════════════════
# VECTOR STORE BUILDER
# ═══════════════════════════════════════════════════════════════════════

def build_vector_store(
    docs: list[Document],
    embeddings,
    backend: str = "faiss",
    persist_dir: Optional[str] = None,
):
    """Build vector store from documents."""
    if backend == "faiss":
        from langchain_community.vectorstores import FAISS
        store = FAISS.from_documents(docs, embeddings)
        logger.info(f"Built FAISS store with {len(docs)} documents")

        if persist_dir:
            store.save_local(persist_dir)
            logger.info(f"Saved FAISS index to {persist_dir}")

        return store

    elif backend == "chroma":
        from langchain_chroma import Chroma
        store = Chroma.from_documents(
            docs,
            embeddings,
            collection_name="cce_layout_templates_v2",
            persist_directory=persist_dir or "./chroma_templates",
        )
        logger.info(f"Built Chroma store with {len(docs)} documents at {persist_dir or './chroma_templates'}")
        return store

    else:
        raise ValueError(f"Unknown backend: {backend}")


# ═══════════════════════════════════════════════════════════════════════
# VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

def verify_store(store, queries: list[str], k: int = 5):
    """Run test queries against the store."""
    print(f"\n{'='*60}")
    print("  VERIFICATION — Searching {0} templates".format(len(ALL_TEMPLATES)))
    print(f"{'='*60}")

    for query in queries:
        print(f"\n  Query: \"{query}\"")
        print(f"  {'─'*50}")
        results = store.similarity_search_with_score(query, k=k)
        for i, (doc, score) in enumerate(results):
            tid = doc.metadata["template_id"]
            name = doc.metadata["name"]
            cat = doc.metadata["category_label"]
            sim = round(1 - score, 4) if score <= 1 else round(score, 4)
            print(f"  {i+1}. {name:40s} [{cat}]  score={sim}")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Ingest CCE templates into vector store")
    parser.add_argument("--backend", choices=["faiss", "chroma"], default="faiss")
    parser.add_argument("--embeddings", choices=["openai", "huggingface", "anthropic", "fake"], default="fake")
    parser.add_argument("--persist", type=str, default=None, help="Directory to persist vector store")
    parser.add_argument("--verify", action="store_true", help="Run verification queries")
    parser.add_argument("--query", type=str, default=None, help="Custom verification query")
    args = parser.parse_args()

    # Build documents
    docs = build_all_documents()
    logger.info(f"Built {len(docs)} documents from {len(ALL_TEMPLATES)} templates")

    # Print summary
    by_cat = {}
    for d in docs:
        cat = d.metadata["category_label"] or d.metadata["category"]
        by_cat.setdefault(cat, []).append(d.metadata["name"])

    for cat, names in sorted(by_cat.items()):
        logger.info(f"  {cat}: {len(names)} templates")
        for n in names:
            logger.info(f"    → {n}")

    # Get embeddings
    embeddings = get_embeddings(args.embeddings)
    logger.info(f"Using {args.embeddings} embeddings")

    # Build store
    store = build_vector_store(docs, embeddings, args.backend, args.persist)

    # Verify
    if args.verify or args.query:
        test_queries = [
            "training compliance dashboard for team manager",
            "individual learner training history employee profile",
            "L&D operations cost vendor spend analysis",
            "LMS login engagement analytics adoption tracking",
            "SOC2 compliance posture monitoring",
            "enterprise learning measurement ILT courses",
            "training plan assignment completion tracking",
            "vulnerability management patch compliance",
        ]
        if args.query:
            test_queries = [args.query] + test_queries[:3]

        verify_store(store, test_queries)

    logger.info("Done!")
    return store


if __name__ == "__main__":
    main()
