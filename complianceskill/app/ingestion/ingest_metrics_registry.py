"""
Ingest metrics registry JSON files into leen_metrics_registry Qdrant collection.

This script reads metrics registry JSON files (conforming to metric_registry_schema.json)
and indexes individual metrics into Qdrant for use by compliance skill metrics recommender.

Each metric is indexed as a standalone document with:
- metric definition (id, name, description)
- category (vulnerabilities, asset_management, etc.)
- source_capabilities (e.g., "qualys.vulnerabilities")
- data_filters, data_groups, kpis, trends
- natural_language_question

Usage:
    python -m app.ingestion.ingest_metrics_registry --metrics-dir /path/to/metrics
    python -m app.ingestion.ingest_metrics_registry --metrics-file /path/to/metrics.json
    python -m app.ingestion.ingest_metrics_registry --metrics-dir /path/to/metrics --reinit-qdrant
    python -m app.ingestion.ingest_metrics_registry --metrics-dir /path/to/enriched --enriched
    python -m app.ingestion.ingest_metrics_registry --metrics-file /path/to/metrics_enriched.json --enriched
"""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

# Initialize settings FIRST before any other imports
# This ensures .env file is loaded and settings are available
try:
    from app.core.settings import get_settings
    # Load settings early to ensure .env is read
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


def build_metric_embedding_text(metric: Dict[str, Any], is_enriched: bool = False) -> str:
    """
    Build embedding text for a metric from metric registry format.
    
    Args:
        metric: Metric dictionary from metric registry JSON
        is_enriched: Whether this is an enriched metric with additional fields
    
    Returns:
        Text string for embedding
    """
    parts = []
    
    # Core metric information
    parts.append(f"Metric: {metric.get('name', '')}")
    parts.append(f"Description: {metric.get('description', '')}")
    
    # Category
    category = metric.get('category', '')
    if category:
        parts.append(f"Category: {category}")
    
    # Natural language question
    question = metric.get('natural_language_question', '')
    if question:
        parts.append(f"Question: {question}")
    
    # KPIs
    kpis = metric.get('kpis', [])
    if kpis:
        parts.append(f"KPIs: {', '.join(kpis)}")
    
    # Trends
    trends = metric.get('trends', [])
    if trends:
        parts.append(f"Trends: {', '.join(trends)}")
    
    # Source capabilities
    source_capabilities = metric.get('source_capabilities', [])
    if source_capabilities:
        parts.append(f"Source capabilities: {', '.join(source_capabilities)}")
    
    # Data capabilities
    data_capability = metric.get('data_capability', [])
    if data_capability:
        parts.append(f"Data capabilities: {', '.join(data_capability)}")
    
    # Transformation layer
    transformation_layer = metric.get('transformation_layer', '')
    if transformation_layer:
        parts.append(f"Transformation layer: {transformation_layer}")
    
    # Source schemas
    source_schemas = metric.get('source_schemas', [])
    if source_schemas:
        parts.append(f"Source schemas: {', '.join(source_schemas)}")
    
    # Data filters and groups
    data_filters = metric.get('data_filters', [])
    if data_filters:
        parts.append(f"Filters: {', '.join(data_filters)}")
    
    data_groups = metric.get('data_groups', [])
    if data_groups:
        parts.append(f"Groups: {', '.join(data_groups)}")
    
    # Enriched fields (if available)
    if is_enriched:
        # Goals
        goals = metric.get('goals', [])
        if goals:
            parts.append(f"Goals: {', '.join(goals)}")
        
        # Focus areas
        focus_areas = metric.get('focus_areas', [])
        if focus_areas:
            parts.append(f"Focus Areas: {', '.join(focus_areas)}")
        
        # Use cases
        use_cases = metric.get('use_cases', [])
        if use_cases:
            parts.append(f"Use Cases: {', '.join(use_cases)}")
        
        # Audience levels
        audience_levels = metric.get('audience_levels', [])
        if audience_levels:
            parts.append(f"Audience Levels: {', '.join(audience_levels)}")
        
        # Metric type (enriched version, may differ from 'type')
        metric_type = metric.get('metric_type', '')
        if metric_type:
            parts.append(f"Metric Type: {metric_type}")
        
        # Aggregation windows
        aggregation_windows = metric.get('aggregation_windows', [])
        if aggregation_windows:
            parts.append(f"Aggregation Windows: {', '.join(aggregation_windows)}")
        
        # Group affinity
        group_affinity = metric.get('group_affinity', [])
        if group_affinity:
            parts.append(f"Group Affinity: {', '.join(group_affinity)}")
        
        # Mapped control domains
        mapped_control_domains = metric.get('mapped_control_domains', [])
        if mapped_control_domains:
            parts.append(f"Control Domains: {', '.join(mapped_control_domains)}")
        
        # Mapped risk categories
        mapped_risk_categories = metric.get('mapped_risk_categories', [])
        if mapped_risk_categories:
            parts.append(f"Risk Categories: {', '.join(mapped_risk_categories)}")
    
    return "\n".join(parts)


def extract_metrics_from_registry(registry_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract metrics from registry data, handling different structures.
    
    Supports:
    - Direct metrics array: {"metrics": [...]}
    - Categories structure: {"categories": {"cat_id": {"metrics": [...]}}}
    - Dashboards structure: {"dashboards": [{"metrics": [...]}]}
    
    Args:
        registry_data: Loaded JSON registry data
    
    Returns:
        List of metric dictionaries
    """
    metrics = []
    
    # Priority 1: Direct metrics key
    if "metrics" in registry_data:
        metrics_data = registry_data["metrics"]
        if isinstance(metrics_data, list):
            metrics = [m for m in metrics_data if isinstance(m, dict)]
        elif isinstance(metrics_data, dict):
            metrics = [m for m in metrics_data.values() if isinstance(m, dict)]
    
    # Priority 2: Categories structure
    elif "categories" in registry_data:
        categories_data = registry_data["categories"]
        if isinstance(categories_data, dict):
            for cat_data in categories_data.values():
                if isinstance(cat_data, dict) and "metrics" in cat_data:
                    cat_metrics = cat_data["metrics"]
                    if isinstance(cat_metrics, list):
                        metrics.extend([m for m in cat_metrics if isinstance(m, dict)])
    
    # Priority 3: Dashboards structure
    elif "dashboards" in registry_data:
        dashboards = registry_data["dashboards"]
        if isinstance(dashboards, list):
            for dashboard in dashboards:
                if isinstance(dashboard, dict) and "metrics" in dashboard:
                    dashboard_metrics = dashboard["metrics"]
                    if isinstance(dashboard_metrics, list):
                        metrics.extend([m for m in dashboard_metrics if isinstance(m, dict)])
    
    return metrics


def ingest_metrics_file(
    metrics_file: Path,
    embedder: EmbeddingService,
    qdrant_client,
    collection_name: str,
    reinit: bool = False,
    is_enriched: bool = False,
) -> int:
    """
    Ingest a single metrics registry JSON file into Qdrant.
    
    Args:
        metrics_file: Path to metrics registry JSON file
        embedder: EmbeddingService instance
        qdrant_client: Qdrant client instance
        collection_name: Qdrant collection name
        reinit: If True, delete and recreate collection
        is_enriched: Whether this is an enriched metrics registry file
    
    Returns:
        Number of metrics indexed
    """
    metrics_file = Path(metrics_file)
    if not metrics_file.exists():
        logger.error(f"Metrics file not found: {metrics_file}")
        return 0
    
    logger.info(f"Loading metrics from: {metrics_file.name} (enriched={is_enriched})")
    
    # Load metrics registry JSON
    try:
        with open(metrics_file, 'r') as f:
            registry_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading metrics file {metrics_file}: {e}")
        return 0
    
    # Check if file is enriched (has meta.enriched flag)
    if not is_enriched:
        meta = registry_data.get('meta', {}) or registry_data.get('metadata', {})
        if meta.get('enriched', False):
            logger.info(f"Detected enriched file (has meta.enriched flag), treating as enriched")
            is_enriched = True
    
    # Extract metrics using flexible structure handler
    metrics = extract_metrics_from_registry(registry_data)
    if not metrics:
        logger.warning(f"No metrics found in {metrics_file.name}")
        return 0
    
    logger.info(f"Found {len(metrics)} metrics in {metrics_file.name}")
    
    # Extract schema name from filename
    # Handle both regular and enriched patterns
    schema_name = metrics_file.stem
    if schema_name.endswith('_enriched'):
        schema_name = schema_name.replace('_enriched', '')
    if schema_name.endswith('_metrics'):
        schema_name = schema_name.replace('_metrics', '')
    
    # Build documents for each metric
    documents = []
    for metric in metrics:
        metric_id = metric.get('id', '')
        if not metric_id:
            logger.warning(f"Skipping metric without id: {metric.get('name', 'Unknown')}")
            continue
        
        # Generate stable UUID for this metric
        # Use schema_name + metric_id to ensure uniqueness across files
        qdrant_id = _stable_uuid(f"{schema_name}:{metric_id}")
        
        # Build embedding text
        embedding_text = build_metric_embedding_text(metric, is_enriched=is_enriched)
        
        # Build document with base fields
        doc = {
            "id": qdrant_id,
            "metric_id": metric_id,
            "metric_name": metric.get('name', ''),
            "description": metric.get('description', ''),
            "category": metric.get('category', ''),
            "source_schemas": metric.get('source_schemas', []),
            "source_capabilities": metric.get('source_capabilities', []),
            "data_filters": metric.get('data_filters', []),
            "data_groups": metric.get('data_groups', []),
            "kpis": metric.get('kpis', []),
            "trends": metric.get('trends', []),
            "natural_language_question": metric.get('natural_language_question', ''),
            "data_capability": metric.get('data_capability', []),
            "transformation_layer": metric.get('transformation_layer', ''),
            "schema_name": schema_name,
            "is_enriched": is_enriched,
            "embedding_text": embedding_text,
        }
        
        # Add enriched fields if available
        if is_enriched:
            doc.update({
                "goals": metric.get('goals', []),
                "focus_areas": metric.get('focus_areas', []),
                "use_cases": metric.get('use_cases', []),
                "audience_levels": metric.get('audience_levels', []),
                "metric_type": metric.get('metric_type', metric.get('type', '')),
                "aggregation_windows": metric.get('aggregation_windows', []),
                "group_affinity": metric.get('group_affinity', []),
                "mapped_control_domains": metric.get('mapped_control_domains', []),
                "mapped_risk_categories": metric.get('mapped_risk_categories', []),
                "control_evidence_hints": metric.get('control_evidence_hints', {}),
                "risk_quantification_hints": metric.get('risk_quantification_hints', {}),
                "scenario_detection_hints": metric.get('scenario_detection_hints', {}),
            })
        
        documents.append(doc)
    
    if not documents:
        logger.warning(f"No valid metrics to index from {metrics_file.name}")
        return 0
    
    # Build embedding texts
    embedding_texts = [doc["embedding_text"] for doc in documents]
    
    # Embed
    logger.info(f"Embedding {len(embedding_texts)} metrics...")
    vectors = embedder.embed(embedding_texts)
    
    # Prepare Qdrant points
    points = []
    for doc, vector in zip(documents, vectors):
        # Build base metadata
        metadata = {
            "metric_id": doc["metric_id"],
            "metric_name": doc["metric_name"],
            "description": doc["description"],
            "category": doc["category"],
            "source_schemas": doc["source_schemas"],
            "source_capabilities": doc["source_capabilities"],
            "data_filters": doc["data_filters"],
            "data_groups": doc["data_groups"],
            "kpis": doc["kpis"],
            "trends": doc["trends"],
            "natural_language_question": doc["natural_language_question"],
            "data_capability": doc["data_capability"],
            "transformation_layer": doc["transformation_layer"],
            "schema_name": doc["schema_name"],
            "is_enriched": doc["is_enriched"],
        }
        
        # Build base content
        content = {
            "id": doc["metric_id"],
            "name": doc["metric_name"],
            "description": doc["description"],
            "category": doc["category"],
            "source_schemas": doc["source_schemas"],
            "source_capabilities": doc["source_capabilities"],
            "data_filters": doc["data_filters"],
            "data_groups": doc["data_groups"],
            "kpis": doc["kpis"],
            "trends": doc["trends"],
            "natural_language_question": doc["natural_language_question"],
            "data_capability": doc["data_capability"],
            "transformation_layer": doc["transformation_layer"],
        }
        
        # Add enriched fields if available
        if doc["is_enriched"]:
            metadata.update({
                "goals": doc.get("goals", []),
                "focus_areas": doc.get("focus_areas", []),
                "use_cases": doc.get("use_cases", []),
                "audience_levels": doc.get("audience_levels", []),
                "metric_type": doc.get("metric_type", ""),
                "aggregation_windows": doc.get("aggregation_windows", []),
                "group_affinity": doc.get("group_affinity", []),
                "mapped_control_domains": doc.get("mapped_control_domains", []),
                "mapped_risk_categories": doc.get("mapped_risk_categories", []),
            })
            content.update({
                "goals": doc.get("goals", []),
                "focus_areas": doc.get("focus_areas", []),
                "use_cases": doc.get("use_cases", []),
                "audience_levels": doc.get("audience_levels", []),
                "metric_type": doc.get("metric_type", ""),
                "aggregation_windows": doc.get("aggregation_windows", []),
                "group_affinity": doc.get("group_affinity", []),
                "mapped_control_domains": doc.get("mapped_control_domains", []),
                "mapped_risk_categories": doc.get("mapped_risk_categories", []),
                "control_evidence_hints": doc.get("control_evidence_hints", {}),
                "risk_quantification_hints": doc.get("risk_quantification_hints", {}),
                "scenario_detection_hints": doc.get("scenario_detection_hints", {}),
            })
        
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
    logger.info(f"Upserting {len(points)} metrics to {collection_name}...")
    try:
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )
        logger.info(f"✓ Indexed {len(points)} metrics from {metrics_file.name}")
        return len(points)
    except Exception as e:
        logger.error(f"Error upserting metrics: {e}")
        return 0


def ingest_metrics_directory(
    metrics_dir: Path,
    embedder: EmbeddingService,
    qdrant_client,
    collection_name: str,
    reinit: bool = False,
    is_enriched: bool = False,
) -> Dict[str, int]:
    """
    Ingest all metrics registry files from a directory.
    
    Args:
        metrics_dir: Directory containing metrics JSON files
        embedder: EmbeddingService instance
        qdrant_client: Qdrant client instance
        collection_name: Qdrant collection name
        reinit: If True, delete and recreate collection on first file
        is_enriched: Whether to look for enriched files (*_enriched.json)
    
    Returns:
        Dictionary mapping filename -> count of metrics indexed
    """
    metrics_dir = Path(metrics_dir)
    if not metrics_dir.exists():
        logger.error(f"Metrics directory not found: {metrics_dir}")
        return {}
    
    # Find metrics JSON files based on enriched flag
    if is_enriched:
        # Look for enriched files (pattern: *_enriched.json)
        metrics_files = list(metrics_dir.glob("*_enriched.json"))
        if not metrics_files:
            logger.warning(f"No enriched metrics files (*_enriched.json) found in {metrics_dir}")
            return {}
    else:
        # Look for regular metrics files (exclude enriched)
        # Patterns: *_metrics.json, *metrics_registry*.json (e.g. lms_metrics_registry_from_concepts.json)
        all_metrics_files = list(metrics_dir.glob("*_metrics.json")) + list(
            metrics_dir.glob("*metrics_registry*.json")
        )
        enriched_files = {f.name for f in metrics_dir.glob("*_enriched.json")}
        # Deduplicate and filter out enriched
        seen = set()
        metrics_files = []
        for f in all_metrics_files:
            if f.name in seen or f.name in enriched_files or f.name.endswith("_enriched.json"):
                continue
            seen.add(f.name)
            metrics_files.append(f)
        if not metrics_files:
            logger.warning(f"No metrics files found in {metrics_dir}")
            return {}
    
    logger.info(f"Found {len(metrics_files)} metrics file(s) (enriched={is_enriched})")
    
    results = {}
    first_file = True
    
    for metrics_file in metrics_files:
        count = ingest_metrics_file(
            metrics_file=metrics_file,
            embedder=embedder,
            qdrant_client=qdrant_client,
            collection_name=collection_name,
            reinit=reinit and first_file,  # Only reinit on first file
            is_enriched=is_enriched,
        )
        results[metrics_file.name] = count
        first_file = False
    
    return results


def main() -> int:
    # Initialize settings and dependencies FIRST (loads .env, etc.)
    try:
        from app.core.settings import get_settings
        from app.core.dependencies import get_doc_store_provider
        
        # This will load .env file and initialize settings
        settings = get_settings()
        logger.info("Settings initialized")
        logger.debug(f"Qdrant host: {getattr(settings, 'QDRANT_HOST', 'not set')}")
        logger.debug(f"Qdrant port: {getattr(settings, 'QDRANT_PORT', 'not set')}")
    except Exception as e:
        logger.error(f"Failed to initialize settings: {e}", exc_info=True)
        return 1
    
    parser = argparse.ArgumentParser(
        description="Ingest metrics registry JSON files into Qdrant"
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default=None,
        help="Directory containing metrics JSON files (e.g., leenmodelmetrics/)"
    )
    parser.add_argument(
        "--metrics-file",
        type=str,
        default=None,
        help="Single metrics JSON file to ingest"
    )
    parser.add_argument(
        "--reinit-qdrant",
        action="store_true",
        help="Delete and recreate Qdrant collection (destructive)",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=MDLCollections.METRICS_REGISTRY,
        help=f"Qdrant collection name (default: {MDLCollections.METRICS_REGISTRY})",
    )
    parser.add_argument(
        "--enriched",
        action="store_true",
        help="Ingest enriched metrics registry files (*_enriched.json) instead of regular files",
    )
    
    args = parser.parse_args()
    
    if not args.metrics_dir and not args.metrics_file:
        logger.error("Either --metrics-dir or --metrics-file must be provided")
        return 1
    
    # Initialize services (after settings are loaded)
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
    
    # Ingest metrics
    try:
        if args.metrics_file:
            logger.info("=" * 60)
            logger.info("Ingesting single metrics file")
            logger.info("=" * 60)
            
            metrics_path = Path(args.metrics_file)
            if not metrics_path.exists():
                logger.error(f"Metrics file not found: {metrics_path}")
                return 1
            
            count = ingest_metrics_file(
                metrics_file=metrics_path,
                embedder=embedder,
                qdrant_client=qdrant_client,
                collection_name=args.collection_name,
                reinit=args.reinit_qdrant,
                is_enriched=args.enriched,
            )
            
            logger.info("=" * 60)
            logger.info(f"Ingestion complete: {count} metrics indexed")
            logger.info("=" * 60)
            
            return 0 if count > 0 else 1
        
        else:
            logger.info("=" * 60)
            logger.info("Ingesting metrics directory")
            logger.info(f"Directory: {Path(args.metrics_dir).resolve()}")
            logger.info("=" * 60)
            
            metrics_dir = Path(args.metrics_dir)
            if not metrics_dir.exists():
                logger.error(f"Metrics directory not found: {metrics_dir}")
                return 1
            
            results = ingest_metrics_directory(
                metrics_dir=metrics_dir,
                embedder=embedder,
                qdrant_client=qdrant_client,
                collection_name=args.collection_name,
                reinit=args.reinit_qdrant,
                is_enriched=args.enriched,
            )
            
            total = sum(results.values())
            
            logger.info("=" * 60)
            logger.info("Ingestion Summary")
            logger.info("=" * 60)
            for filename, count in results.items():
                logger.info(f"  {filename}: {count} metrics")
            logger.info(f"Total: {total} metrics indexed")
            logger.info("=" * 60)
            
            return 0 if total > 0 else 1
    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
