"""
Ingest dashboard templates into dashboard_templates collection.

This script reads dashboard templates from the unified registry (registry_unified.py)
and indexes them into Qdrant/ChromaDB for use by the dashboard template retrieval service.

Each template is indexed as a standalone document with:
- template_id, name, description
- category, domains, complexity
- features (has_chat, has_graph, has_filters, strip_cells)
- best_for, primitives, theme_hint
- L&D specific fields (chart_types, activity_types, table_columns)

Usage:
    python -m app.ingestion.ingest_dashboard_templates
    python -m app.ingestion.ingest_dashboard_templates --reinit
    python -m app.ingestion.ingest_dashboard_templates --verify
"""

import argparse
import json
import logging
import sys
import uuid
from typing import Dict, List, Optional, Any

# Initialize settings FIRST before any other imports
try:
    from app.core.settings import get_settings
    _ = get_settings()
except Exception as e:
    print(f"Warning: Could not load settings early: {e}")

from langchain_core.documents import Document as LangchainDocument

from app.ingestion.embedder import EmbeddingService
from app.storage.collections import MDLCollections
from app.core.dependencies import get_doc_store_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _stable_uuid(seed: str) -> str:
    """Generate a deterministic UUID v5 from a seed string."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def build_template_embedding_text(template: Dict[str, Any]) -> str:
    """
    Build embedding text for a template from unified registry format.
    
    Uses the same function from registry_unified.py if available.
    """
    try:
        from app.utils.registry_config.registry_unified import get_unified_embedding_text
        return get_unified_embedding_text(template)
    except ImportError:
        # Fallback to basic text building
        parts = [
            template.get("name", ""),
            template.get("description", ""),
            f"Category: {template.get('category', '')}",
            f"Domains: {', '.join(template.get('domains', []))}",
            f"Best for: {', '.join(template.get('best_for', []))}",
        ]
        return "\n".join(parts)


def parse_template_document(
    template_id: str,
    template: Dict[str, Any],
    categories: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Parse a template into a document for indexing.
    
    Returns:
        Dict with all fields needed for indexing
    """
    category_info = categories.get(template.get("category", ""), {})
    
    doc = {
        "id": _stable_uuid(f"dashboard_template:{template_id}"),
        "template_id": template_id,
        "name": template.get("name", ""),
        "description": template.get("description", ""),
        "category": template.get("category", ""),
        "category_label": category_info.get("label", ""),
        "icon": template.get("icon", ""),
        "domains": template.get("domains", []),
        "complexity": template.get("complexity", "medium"),
        "has_chat": template.get("has_chat", False),
        "has_graph": template.get("has_graph", False),
        "has_filters": template.get("has_filters", False),
        "strip_cells": template.get("strip_cells", 0),
        "best_for": template.get("best_for", []),
        "primitives": template.get("primitives", []),
        "theme_hint": template.get("theme_hint", "light"),
        "metadata": {
            "chart_types": template.get("chart_types", []),
            "activity_types": template.get("activity_types", []),
            "table_columns": template.get("table_columns"),
            "strip_example": template.get("strip_example", []),
            "card_anatomy": template.get("card_anatomy"),
            "layout_grid": template.get("layout_grid"),
            "panels": template.get("panels"),
            "filter_options": template.get("filter_options", []),
        }
    }
    
    return doc


def ingest_templates(
    embedder: EmbeddingService,
    doc_store,
    reinit: bool = False,
) -> int:
    """
    Ingest all dashboard templates from unified registry.
    
    Args:
        embedder: EmbeddingService instance
        doc_store: Document store instance (from get_doc_store_provider)
        reinit: If True, reinitialize the collection
    
    Returns:
        Number of templates indexed
    """
    logger.info("Loading templates from unified registry...")
    
    try:
        from app.utils.registry_config.registry_unified import (
            ALL_TEMPLATES,
            ALL_CATEGORIES,
        )
    except ImportError:
        logger.error("Failed to import unified registry. Falling back to base templates.")
        from app.agents.dashboard_agent.templates import TEMPLATES as ALL_TEMPLATES, CATEGORIES as ALL_CATEGORIES
    
    logger.info(f"Found {len(ALL_TEMPLATES)} templates to index")
    
    # Reinitialize collection if requested
    if reinit:
        logger.info("Reinitializing collection...")
        try:
            if hasattr(doc_store, "qdrant_client"):
                if doc_store.qdrant_client.collection_exists(doc_store.collection_name):
                    doc_store.qdrant_client.delete_collection(doc_store.collection_name)
                    logger.info("Deleted existing collection")
                doc_store.vectorstore = None
                doc_store.initialize()
            elif hasattr(doc_store, "persistent_client"):
                try:
                    doc_store.persistent_client.delete_collection(name=doc_store.collection_name)
                    logger.info("Deleted existing collection")
                except Exception:
                    pass
                doc_store.collection = None
                doc_store.initialize()
            elif hasattr(doc_store, "delete_collection"):
                doc_store.delete_collection()
                logger.info("Deleted existing collection")
            else:
                logger.warning("Store has no delete_collection; skipping reinit")
        except Exception as e:
            logger.warning(f"Could not delete collection (may not exist): {e}")
    
    # Parse templates into documents
    documents = []
    for template_id, template in ALL_TEMPLATES.items():
        doc = parse_template_document(template_id, template, ALL_CATEGORIES)
        documents.append(doc)
    
    if not documents:
        logger.error("No templates to index")
        return 0
    
    # Build LangChain documents for indexing
    logger.info(f"Building documents for {len(documents)} templates...")
    langchain_docs = []
    
    for doc in documents:
        # Build embedding text
        text = build_template_embedding_text(ALL_TEMPLATES[doc["template_id"]])
        
        # Build metadata (flatten nested metadata)
        metadata = {
            "id": doc["id"],
            "template_id": doc["template_id"],
            "name": doc["name"],
            "description": doc["description"],
            "category": doc["category"],
            "category_label": doc["category_label"],
            "icon": doc.get("icon", ""),
            "domains": json.dumps(doc["domains"]),
            "complexity": doc["complexity"],
            "has_chat": doc["has_chat"],
            "has_graph": doc["has_graph"],
            "has_filters": doc["has_filters"],
            "strip_cells": doc["strip_cells"],
            "best_for": json.dumps(doc["best_for"]),
            "primitives": json.dumps(doc["primitives"]),
            "theme_hint": doc["theme_hint"],
        }
        
        # Add L&D specific metadata (serialize complex types)
        if doc["metadata"].get("chart_types"):
            metadata["chart_types"] = json.dumps(doc["metadata"]["chart_types"])
        if doc["metadata"].get("activity_types"):
            metadata["activity_types"] = json.dumps(doc["metadata"]["activity_types"])
        if doc["metadata"].get("table_columns"):
            metadata["table_columns"] = json.dumps(doc["metadata"]["table_columns"])
        if doc["metadata"].get("strip_example"):
            metadata["strip_example"] = json.dumps(doc["metadata"]["strip_example"])
        if doc["metadata"].get("card_anatomy"):
            metadata["card_anatomy"] = json.dumps(doc["metadata"]["card_anatomy"])
        if doc["metadata"].get("layout_grid"):
            metadata["layout_grid"] = json.dumps(doc["metadata"]["layout_grid"])
        if doc["metadata"].get("panels"):
            metadata["panels"] = json.dumps(doc["metadata"]["panels"])
        if doc["metadata"].get("filter_options"):
            metadata["filter_options"] = json.dumps(doc["metadata"]["filter_options"])
        
        langchain_docs.append(LangchainDocument(
            page_content=text,
            metadata=metadata
        ))
    
    # Index documents in batches
    logger.info(f"Indexing {len(langchain_docs)} templates...")
    try:
        # Document stores handle batching internally
        result_ids = doc_store.add_documents(langchain_docs)
        indexed_count = len(result_ids) if result_ids else len(langchain_docs)
        logger.info(f"Successfully indexed {indexed_count} templates")
    except Exception as e:
        logger.error(f"Failed to index templates: {e}", exc_info=True)
        indexed_count = 0
    
    logger.info(f"Successfully indexed {indexed_count}/{len(documents)} templates")
    return indexed_count


def verify_ingestion(doc_store, sample_queries: Optional[List[str]] = None):
    """Run test queries against the indexed templates. Uses semantic_search (DocumentQdrantStore/DocumentChromaStore)."""
    if sample_queries is None:
        sample_queries = [
            "SOC2 compliance monitoring with AI chat",
            "training compliance dashboard for team manager",
            "vulnerability management patch compliance",
            "executive risk summary board reporting",
        ]
    
    logger.info(f"\n{'='*60}")
    logger.info("  VERIFICATION — Testing template search")
    logger.info(f"{'='*60}")
    
    for query in sample_queries:
        logger.info(f"\n  Query: \"{query}\"")
        logger.info(f"  {'─'*50}")
        
        try:
            # DocumentQdrantStore and DocumentChromaStore use semantic_search (returns List[Dict])
            if hasattr(doc_store, "semantic_search"):
                results = doc_store.semantic_search(query, k=5)
            else:
                # Fallback: try vector_store client
                from app.storage.vector_store import get_vector_store_client
                from app.storage.collections import MDLCollections
                client = get_vector_store_client()
                import asyncio
                out = asyncio.run(client.query(
                    collection_name=MDLCollections.DASHBOARD_TEMPLATES,
                    query_texts=[query],
                    n_results=5,
                ))
                results = [
                    {"metadata": m[0] if m else {}, "content": d[0] if d else ""}
                    for m, d in zip(out.get("metadatas", [[]])[0], out.get("documents", [[]])[0])
                ]
            
            for i, result in enumerate(results, 1):
                metadata = result.get("metadata", result) if isinstance(result, dict) else getattr(result, "metadata", {})
                template_id = metadata.get("template_id", "unknown")
                name = metadata.get("name", "Unknown")
                category = metadata.get("category_label", metadata.get("category", ""))
                logger.info(f"  {i}. {name:40s} [{category}]  id={template_id}")
        except Exception as e:
            logger.error(f"  Error searching: {e}")


def main():
    parser = argparse.ArgumentParser(description="Ingest dashboard templates into vector store")
    parser.add_argument("--reinit", action="store_true", help="Reinitialize collection (delete and recreate)")
    parser.add_argument("--verify", action="store_true", help="Run verification queries after ingestion")
    args = parser.parse_args()
    
    try:
        # Get embedder
        logger.info("Initializing embedding service...")
        embedder = EmbeddingService()
        
        # Get document store provider
        logger.info("Getting document store provider...")
        doc_store_provider = get_doc_store_provider()
        
        # Get dashboard templates store
        stores = doc_store_provider.stores if hasattr(doc_store_provider, 'stores') else {}
        doc_store = stores.get("dashboard_templates")
        
        if not doc_store:
            logger.error("dashboard_templates store not found in document store provider")
            logger.info("Available stores: " + ", ".join(stores.keys()))
            logger.info("Creating dashboard_templates store...")
            
            # Create the store if it doesn't exist
            from app.core.settings import get_settings
            from app.storage.documents import DocumentChromaStore, DocumentQdrantStore
            from langchain_openai import OpenAIEmbeddings
            
            settings = get_settings()
            embeddings_model = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY
            )
            
            if settings.VECTOR_STORE_TYPE.value == "chroma":
                from app.core.dependencies import get_chromadb_client
                client = get_chromadb_client()
                doc_store = DocumentChromaStore(
                    persistent_client=client,
                    collection_name=MDLCollections.DASHBOARD_TEMPLATES,
                    embeddings_model=embeddings_model
                )
            else:
                qdrant_config = settings.get_vector_store_config()
                doc_store = DocumentQdrantStore(
                    collection_name=MDLCollections.DASHBOARD_TEMPLATES,
                    host=qdrant_config.get("host", "localhost"),
                    port=qdrant_config.get("port", 6333),
                    embeddings_model=embeddings_model
                )
        
        # Ingest templates
        count = ingest_templates(embedder, doc_store, reinit=args.reinit)
        
        if count == 0:
            logger.error("No templates were indexed")
            sys.exit(1)
        
        logger.info(f"✓ Successfully indexed {count} dashboard templates")
        
        # Verify if requested
        if args.verify:
            verify_ingestion(doc_store)
        
    except Exception as e:
        logger.error(f"Failed to ingest templates: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
