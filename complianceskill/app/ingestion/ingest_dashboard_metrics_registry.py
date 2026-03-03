"""
Ingest Dashboard Metrics Registry — Unified Dashboard Metrics Collection
========================================================================
Combines dashboard templates, LMS metrics, and security metrics into a unified
dashboard metrics registry for dashboard generation.

Sources:
- ld_templates_registry.json: L&D dashboard templates
- lms_dashboard_metrics.json: LMS dashboard metrics
- templates_registry.json: Base security/compliance templates
- metrics_registry.json: Security metrics (optional, for reference)

Each dashboard/template is indexed with:
- Dashboard/template definition (id, name, description)
- Category, domain, complexity
- Metrics used, chart types, layout patterns
- Goals, focus areas, use cases
- Audience levels, best_for scenarios

Usage:
    python -m app.ingestion.ingest_dashboard_metrics_registry \
        --templates-dir /path/to/registry_config \
        --output-collection dashboard_metrics_registry \
        --reinit
"""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

# Initialize settings FIRST before any other imports
try:
    from app.core.settings import get_settings
    _ = get_settings()
except Exception as e:
    print(f"Warning: Could not load settings early: {e}")

from qdrant_client.http import models as qmodels

from app.ingestion.embedder import EmbeddingService
from app.storage.qdrant_framework_store import _get_underlying_qdrant_client, _vector_params
from app.storage.collections import MDLCollections

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _stable_uuid(seed: str) -> str:
    """Generate a deterministic UUID v5 from a seed string."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def build_dashboard_embedding_text(dashboard: Dict[str, Any], source_type: str) -> str:
    """
    Build embedding text for a dashboard/template from registry format.
    
    Args:
        dashboard: Dashboard/template dictionary
        source_type: "template", "lms_dashboard", or "ld_template"
    
    Returns:
        Text string for embedding
    """
    parts = []
    
    # Core dashboard information
    parts.append(f"Dashboard: {dashboard.get('name', dashboard.get('dashboard_name', ''))}")
    parts.append(f"Description: {dashboard.get('description', dashboard.get('dashboard_description', ''))}")
    
    # Category
    category = dashboard.get('category', dashboard.get('dashboard_category', ''))
    if category:
        parts.append(f"Category: {category}")
    
    # Domain
    domains = dashboard.get('domains', [])
    if domains:
        parts.append(f"Domains: {', '.join(domains)}")
    
    # Complexity
    complexity = dashboard.get('complexity', '')
    if complexity:
        parts.append(f"Complexity: {complexity}")
    
    # Best for / Use cases
    best_for = dashboard.get('best_for', [])
    if best_for:
        parts.append(f"Best for: {', '.join(best_for)}")
    
    # Chart types
    chart_types = dashboard.get('chart_types', [])
    if chart_types:
        parts.append(f"Chart types: {', '.join(chart_types)}")
    
    # Primitives / Layout
    primitives = dashboard.get('primitives', [])
    if primitives:
        parts.append(f"Layout primitives: {', '.join(primitives)}")
    
    # Metrics (for LMS dashboards)
    if source_type == "lms_dashboard":
        metrics = dashboard.get('metrics', [])
        if metrics:
            metric_names = [m.get('name', '') for m in metrics[:10]]  # Limit to first 10
            parts.append(f"Metrics: {', '.join(metric_names)}")
    
    # Panels / Layout grid
    panels = dashboard.get('panels', {})
    if panels:
        panel_desc = ', '.join([f"{k}: {v}" for k, v in list(panels.items())[:5]])
        parts.append(f"Panels: {panel_desc}")
    
    # Theme
    theme = dashboard.get('theme_hint', '')
    if theme:
        parts.append(f"Theme: {theme}")
    
    return "\n".join(parts)


def extract_templates_from_registry(registry_path: Path) -> List[Dict[str, Any]]:
    """Extract templates from templates_registry.json or ld_templates_registry.json."""
    try:
        with open(registry_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading {registry_path}: {e}")
        return []
    
    templates = []
    
    # Handle templates_registry.json structure
    if "templates" in data:
        for template in data["templates"]:
            if isinstance(template, dict):
                template["_source_type"] = "template"
                template["_source_file"] = registry_path.name
                templates.append(template)
    
    # Handle ld_templates_registry.json structure
    elif "templates" in data:
        for template in data["templates"]:
            if isinstance(template, dict):
                template["_source_type"] = "ld_template"
                template["_source_file"] = registry_path.name
                templates.append(template)
    
    return templates


def extract_lms_dashboards_from_registry(registry_path: Path) -> List[Dict[str, Any]]:
    """Extract dashboards from lms_dashboard_metrics.json."""
    try:
        with open(registry_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading {registry_path}: {e}")
        return []
    
    dashboards = []
    
    # Handle lms_dashboard_metrics.json structure
    if "dashboards" in data:
        for dashboard in data["dashboards"]:
            if isinstance(dashboard, dict):
                dashboard["_source_type"] = "lms_dashboard"
                dashboard["_source_file"] = registry_path.name
                dashboards.append(dashboard)
    
    return dashboards


def ingest_dashboard_metrics_registry(
    templates_dir: Path,
    embedder: EmbeddingService,
    qdrant_client,
    collection_name: str,
    reinit: bool = False,
) -> int:
    """
    Ingest dashboard metrics registry from multiple sources.
    
    Args:
        templates_dir: Directory containing registry JSON files
        embedder: EmbeddingService instance
        qdrant_client: Qdrant client instance
        collection_name: Qdrant collection name
        reinit: If True, delete and recreate collection
    
    Returns:
        Number of dashboards/templates indexed
    """
    templates_dir = Path(templates_dir)
    if not templates_dir.exists():
        logger.error(f"Templates directory not found: {templates_dir}")
        return 0
    
    # Find registry files
    ld_templates_file = templates_dir / "ld_templates_registry.json"
    lms_metrics_file = templates_dir / "lms_dashboard_metrics.json"
    templates_file = templates_dir / "templates_registry.json"
    
    all_dashboards = []
    
    # Extract from ld_templates_registry.json
    if ld_templates_file.exists():
        logger.info(f"Loading L&D templates from {ld_templates_file.name}")
        templates = extract_templates_from_registry(ld_templates_file)
        all_dashboards.extend(templates)
        logger.info(f"Found {len(templates)} L&D templates")
    
    # Extract from templates_registry.json
    if templates_file.exists():
        logger.info(f"Loading base templates from {templates_file.name}")
        templates = extract_templates_from_registry(templates_file)
        all_dashboards.extend(templates)
        logger.info(f"Found {len(templates)} base templates")
    
    # Extract from lms_dashboard_metrics.json
    if lms_metrics_file.exists():
        logger.info(f"Loading LMS dashboards from {lms_metrics_file.name}")
        dashboards = extract_lms_dashboards_from_registry(lms_metrics_file)
        all_dashboards.extend(dashboards)
        logger.info(f"Found {len(dashboards)} LMS dashboards")
    
    if not all_dashboards:
        logger.warning("No dashboards/templates found in registry files")
        return 0
    
    logger.info(f"Total dashboards/templates to index: {len(all_dashboards)}")
    
    # Build documents for each dashboard
    documents = []
    for dashboard in all_dashboards:
        dashboard_id = dashboard.get('id', dashboard.get('dashboard_id', ''))
        if not dashboard_id:
            logger.warning(f"Skipping dashboard without id: {dashboard.get('name', 'Unknown')}")
            continue
        
        source_type = dashboard.get('_source_type', 'template')
        source_file = dashboard.get('_source_file', 'unknown')
        
        # Generate stable UUID
        qdrant_id = _stable_uuid(f"dashboard_metrics:{source_type}:{dashboard_id}")
        
        # Build embedding text
        embedding_text = build_dashboard_embedding_text(dashboard, source_type)
        
        # Build document with base fields
        doc = {
            "id": qdrant_id,
            "dashboard_id": dashboard_id,
            "dashboard_name": dashboard.get('name', dashboard.get('dashboard_name', '')),
            "description": dashboard.get('description', dashboard.get('dashboard_description', '')),
            "category": dashboard.get('category', dashboard.get('dashboard_category', '')),
            "domains": dashboard.get('domains', []),
            "complexity": dashboard.get('complexity', 'medium'),
            "has_chat": dashboard.get('has_chat', False),
            "has_graph": dashboard.get('has_graph', False),
            "has_filters": dashboard.get('has_filters', False),
            "strip_cells": dashboard.get('strip_cells', 0),
            "best_for": dashboard.get('best_for', []),
            "primitives": dashboard.get('primitives', []),
            "chart_types": dashboard.get('chart_types', []),
            "theme_hint": dashboard.get('theme_hint', 'light'),
            "source_type": source_type,
            "source_file": source_file,
            "embedding_text": embedding_text,
        }
        
        # Add L&D specific fields
        if dashboard.get('activity_types'):
            doc["activity_types"] = dashboard.get('activity_types', [])
        if dashboard.get('table_columns'):
            doc["table_columns"] = dashboard.get('table_columns')
        if dashboard.get('layout_grid'):
            doc["layout_grid"] = dashboard.get('layout_grid')
        if dashboard.get('panels'):
            doc["panels"] = dashboard.get('panels')
        
        # Add metrics for LMS dashboards
        if source_type == "lms_dashboard" and dashboard.get('metrics'):
            doc["metrics"] = dashboard.get('metrics', [])
            doc["metric_count"] = len(dashboard.get('metrics', []))
        
        documents.append(doc)
    
    if not documents:
        logger.warning("No valid dashboards to index")
        return 0
    
    # Build embedding texts
    embedding_texts = [doc["embedding_text"] for doc in documents]
    
    # Embed
    logger.info(f"Embedding {len(embedding_texts)} dashboards...")
    vectors = embedder.embed(embedding_texts)
    
    # Prepare Qdrant points
    points = []
    for doc, vector in zip(documents, vectors):
        # Build metadata
        metadata = {
            "dashboard_id": doc["dashboard_id"],
            "dashboard_name": doc["dashboard_name"],
            "description": doc["description"],
            "category": doc["category"],
            "domains": doc["domains"],
            "complexity": doc["complexity"],
            "has_chat": doc["has_chat"],
            "has_graph": doc["has_graph"],
            "has_filters": doc["has_filters"],
            "strip_cells": doc["strip_cells"],
            "best_for": doc["best_for"],
            "primitives": doc["primitives"],
            "chart_types": doc["chart_types"],
            "theme_hint": doc["theme_hint"],
            "source_type": doc["source_type"],
            "source_file": doc["source_file"],
        }
        
        # Add optional fields
        if doc.get("activity_types"):
            metadata["activity_types"] = doc["activity_types"]
        if doc.get("metric_count"):
            metadata["metric_count"] = doc["metric_count"]
        
        # Build content
        content = {
            "id": doc["dashboard_id"],
            "name": doc["dashboard_name"],
            "description": doc["description"],
            "category": doc["category"],
            "domains": doc["domains"],
            "complexity": doc["complexity"],
            "best_for": doc["best_for"],
            "chart_types": doc["chart_types"],
            "primitives": doc["primitives"],
        }
        
        point = qmodels.PointStruct(
            id=doc["id"],
            vector=vector,
            payload={
                "metadata": metadata,
                "page_content": doc["embedding_text"],
                "content": content,
            }
        )
        points.append(point)
    
    # Ensure collection exists
    try:
        collections = qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name not in collection_names:
            logger.info(f"Creating collection: {collection_name}")
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=_vector_params(),
            )
        elif reinit:
            logger.info(f"Reinitializing collection: {collection_name}")
            qdrant_client.delete_collection(collection_name=collection_name)
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=_vector_params(),
            )
    except Exception as e:
        logger.error(f"Error ensuring collection {collection_name}: {e}")
        return 0
    
    # Upsert to Qdrant
    logger.info(f"Upserting {len(points)} dashboards to {collection_name}...")
    try:
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )
        logger.info(f"✓ Indexed {len(points)} dashboards/templates")
        return len(points)
    except Exception as e:
        logger.error(f"Error upserting dashboards: {e}")
        return 0


def main() -> int:
    # Initialize settings and dependencies FIRST
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        logger.info("Settings initialized")
    except Exception as e:
        logger.error(f"Failed to initialize settings: {e}", exc_info=True)
        return 1
    
    parser = argparse.ArgumentParser(
        description="Ingest dashboard metrics registry into Qdrant"
    )
    parser.add_argument(
        "--templates-dir",
        type=str,
        required=True,
        help="Directory containing registry JSON files (ld_templates_registry.json, lms_dashboard_metrics.json, templates_registry.json)"
    )
    parser.add_argument(
        "--output-collection",
        type=str,
        default=MDLCollections.DASHBOARD_METRICS_REGISTRY,
        help=f"Qdrant collection name (default: {MDLCollections.DASHBOARD_METRICS_REGISTRY})"
    )
    parser.add_argument(
        "--reinit",
        action="store_true",
        help="Delete and recreate Qdrant collection (destructive)",
    )
    
    args = parser.parse_args()
    
    # Initialize services
    try:
        logger.info("Initializing EmbeddingService...")
        embedder = EmbeddingService()
        logger.info("EmbeddingService initialized")
        
        logger.info("Initializing Qdrant client...")
        qdrant_client = _get_underlying_qdrant_client()
        logger.info("Qdrant client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        return 1
    
    # Ingest dashboard metrics
    try:
        logger.info("=" * 60)
        logger.info("Ingesting Dashboard Metrics Registry")
        logger.info(f"Templates directory: {Path(args.templates_dir).resolve()}")
        logger.info("=" * 60)
        
        templates_dir = Path(args.templates_dir)
        if not templates_dir.exists():
            logger.error(f"Templates directory not found: {templates_dir}")
            return 1
        
        count = ingest_dashboard_metrics_registry(
            templates_dir=templates_dir,
            embedder=embedder,
            qdrant_client=qdrant_client,
            collection_name=args.output_collection,
            reinit=args.reinit,
        )
        
        logger.info("=" * 60)
        logger.info(f"Ingestion complete: {count} dashboards/templates indexed")
        logger.info("=" * 60)
        
        return 0 if count > 0 else 1
    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
