"""
Ingest enriched control taxonomy JSON files into Qdrant collection.

This script reads enriched control taxonomy JSON files (e.g., hipaa_enriched.json, 
soc2_enriched.json) and indexes individual controls into Qdrant for use by 
compliance skill control taxonomy recommender.

Each control is indexed as a standalone document with:
- control_code, domain, sub_domain
- measurement_goal
- focus_areas, risk_categories
- metric_type_preferences (primary, secondary, rationale)
- evidence_requirements (what_to_measure, data_signals, temporal_expectation, etc.)
- affinity_keywords
- control_type_classification
- differentiation_note

Usage:
    python -m app.ingestion.ingest_control_taxonomy --taxonomy-dir /path/to/control_taxonomy_enriched
    python -m app.ingestion.ingest_control_taxonomy --taxonomy-file /path/to/hipaa_enriched.json
    python -m app.ingestion.ingest_control_taxonomy --taxonomy-dir /path/to/taxonomy --reinit-qdrant
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


def build_control_taxonomy_embedding_text(control: Dict[str, Any], framework_id: str) -> str:
    """
    Build embedding text for an enriched control taxonomy entry.
    
    Args:
        control: Control dictionary from enriched taxonomy JSON
        framework_id: Framework identifier (e.g., "hipaa", "soc2")
    
    Returns:
        Text string for embedding
    """
    parts = []
    
    # Framework and control identification
    parts.append(f"Framework: {framework_id.upper()}")
    control_code = control.get('control_code', '')
    if control_code:
        parts.append(f"Control Code: {control_code}")
    
    # Domain and sub-domain
    domain = control.get('domain', '')
    if domain:
        parts.append(f"Domain: {domain}")
    
    sub_domain = control.get('sub_domain', '')
    if sub_domain:
        parts.append(f"Sub-domain: {sub_domain}")
    
    # Measurement goal (key field)
    measurement_goal = control.get('measurement_goal', '')
    if measurement_goal:
        parts.append(f"Measurement Goal: {measurement_goal}")
    
    # Focus areas
    focus_areas = control.get('focus_areas', [])
    if focus_areas:
        parts.append(f"Focus Areas: {', '.join(focus_areas)}")
    
    # Risk categories
    risk_categories = control.get('risk_categories', [])
    if risk_categories:
        parts.append(f"Risk Categories: {', '.join(risk_categories)}")
    
    # Metric type preferences
    metric_type_prefs = control.get('metric_type_preferences', {})
    if metric_type_prefs:
        primary = metric_type_prefs.get('primary', '')
        if primary:
            parts.append(f"Primary Metric Type: {primary}")
        
        secondary = metric_type_prefs.get('secondary', [])
        if secondary:
            parts.append(f"Secondary Metric Types: {', '.join(secondary)}")
        
        rationale = metric_type_prefs.get('rationale', '')
        if rationale:
            parts.append(f"Metric Type Rationale: {rationale}")
    
    # Evidence requirements (very important for retrieval)
    evidence_req = control.get('evidence_requirements', {})
    if evidence_req:
        what_to_measure = evidence_req.get('what_to_measure', '')
        if what_to_measure:
            parts.append(f"What to Measure: {what_to_measure}")
        
        data_signals = evidence_req.get('data_signals', [])
        if data_signals:
            parts.append(f"Data Signals: {', '.join(data_signals)}")
        
        temporal_expectation = evidence_req.get('temporal_expectation', '')
        if temporal_expectation:
            parts.append(f"Temporal Expectation: {temporal_expectation}")
        
        comparison_baseline = evidence_req.get('comparison_baseline', '')
        if comparison_baseline:
            parts.append(f"Comparison Baseline: {comparison_baseline}")
        
        evidence_strength = evidence_req.get('evidence_strength_indicators', [])
        if evidence_strength:
            # Include first few indicators (they can be long)
            strength_text = '; '.join(evidence_strength[:3])
            parts.append(f"Evidence Strength: {strength_text}")
    
    # Affinity keywords (important for semantic search)
    affinity_keywords = control.get('affinity_keywords', [])
    if affinity_keywords:
        parts.append(f"Keywords: {', '.join(affinity_keywords)}")
    
    # Control type classification
    control_type = control.get('control_type_classification', {})
    if control_type:
        ctrl_type = control_type.get('type', '')
        if ctrl_type:
            parts.append(f"Control Type: {ctrl_type}")
        
        reasoning = control_type.get('reasoning', '')
        if reasoning:
            parts.append(f"Control Type Reasoning: {reasoning}")
    
    # Differentiation note
    differentiation = control.get('differentiation_note', '')
    if differentiation:
        parts.append(f"Differentiation: {differentiation}")
    
    return "\n".join(parts)


def ingest_taxonomy_file(
    taxonomy_file: Path,
    embedder: EmbeddingService,
    qdrant_client,
    collection_name: str,
    reinit: bool = False,
) -> int:
    """
    Ingest a single enriched control taxonomy JSON file into Qdrant.
    
    Args:
        taxonomy_file: Path to enriched taxonomy JSON file
        embedder: EmbeddingService instance
        qdrant_client: Qdrant client instance
        collection_name: Qdrant collection name
        reinit: If True, delete and recreate collection
    
    Returns:
        Number of controls indexed
    """
    taxonomy_file = Path(taxonomy_file)
    if not taxonomy_file.exists():
        logger.error(f"Taxonomy file not found: {taxonomy_file}")
        return 0
    
    logger.info(f"Loading taxonomy from: {taxonomy_file.name}")
    
    # Load taxonomy JSON
    try:
        with open(taxonomy_file, 'r') as f:
            taxonomy_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading taxonomy file {taxonomy_file}: {e}")
        return 0
    
    # Extract framework ID from filename (e.g., "hipaa_enriched.json" -> "hipaa")
    framework_id = taxonomy_file.stem.replace('_enriched', '').lower()
    
    # Extract controls - structure is {"framework_id": {"control_code": {...}, ...}}
    controls = {}
    if isinstance(taxonomy_data, dict):
        # Check if data is organized by framework
        if framework_id in taxonomy_data:
            controls = taxonomy_data[framework_id]
        elif len(taxonomy_data) == 1:
            # Single framework in file, use the key
            framework_id = list(taxonomy_data.keys())[0]
            controls = taxonomy_data[framework_id]
        else:
            # Multiple frameworks, try to find matching one
            if framework_id in taxonomy_data:
                controls = taxonomy_data[framework_id]
            else:
                logger.warning(f"Could not find framework '{framework_id}' in {taxonomy_file.name}")
                logger.info(f"Available frameworks: {list(taxonomy_data.keys())}")
                # Use first framework as fallback
                framework_id = list(taxonomy_data.keys())[0]
                controls = taxonomy_data[framework_id]
                logger.info(f"Using framework '{framework_id}' as fallback")
    
    if not controls:
        logger.warning(f"No controls found in {taxonomy_file.name}")
        return 0
    
    logger.info(f"Found {len(controls)} controls for framework '{framework_id}' in {taxonomy_file.name}")
    
    # Build documents for each control
    documents = []
    for control_code, control_data in controls.items():
        if not isinstance(control_data, dict):
            logger.warning(f"Skipping invalid control entry: {control_code}")
            continue
        
        # Ensure control_code is in the data
        if 'control_code' not in control_data:
            control_data['control_code'] = control_code
        
        # Generate stable UUID for this control
        # Use framework_id + control_code to ensure uniqueness
        qdrant_id = _stable_uuid(f"{framework_id}:{control_code}")
        
        # Build embedding text
        embedding_text = build_control_taxonomy_embedding_text(control_data, framework_id)
        
        # Build document
        doc = {
            "id": qdrant_id,
            "framework_id": framework_id,
            "control_code": control_code,
            "domain": control_data.get('domain', ''),
            "sub_domain": control_data.get('sub_domain', ''),
            "measurement_goal": control_data.get('measurement_goal', ''),
            "focus_areas": control_data.get('focus_areas', []),
            "risk_categories": control_data.get('risk_categories', []),
            "metric_type_preferences": control_data.get('metric_type_preferences', {}),
            "evidence_requirements": control_data.get('evidence_requirements', {}),
            "affinity_keywords": control_data.get('affinity_keywords', []),
            "control_type_classification": control_data.get('control_type_classification', {}),
            "differentiation_note": control_data.get('differentiation_note', ''),
            "embedding_text": embedding_text,
            "full_control_data": control_data,  # Store full data for retrieval
        }
        documents.append(doc)
    
    if not documents:
        logger.warning(f"No valid controls to index from {taxonomy_file.name}")
        return 0
    
    # Build embedding texts
    embedding_texts = [doc["embedding_text"] for doc in documents]
    
    # Embed with smaller batch size for control taxonomies (they have very long text)
    # Control taxonomy entries can be 200-300 tokens each, so we use a smaller batch
    # to stay well under the 300k token limit (aim for ~50k tokens per batch = ~200 controls)
    # Using batch_size=50 to be safe (50 * 300 tokens = 15k tokens, well under 300k limit)
    logger.info(f"Embedding {len(embedding_texts)} controls with batch_size=50 (control taxonomies have long text)...")
    try:
        vectors = embedder.embed(embedding_texts, batch_size=50)
    except ValueError as e:
        if "Batch too large" in str(e):
            # If still too large, try even smaller batch
            logger.warning(f"Batch size 50 still too large, trying batch_size=25...")
            vectors = embedder.embed(embedding_texts, batch_size=25)
        else:
            raise
    
    # Prepare Qdrant points
    points = []
    for doc, vector in zip(documents, vectors):
        point = qmodels.PointStruct(
            id=doc["id"],
            vector=vector,
            payload={
                "metadata": {
                    "framework_id": doc["framework_id"],
                    "control_code": doc["control_code"],
                    "domain": doc["domain"],
                    "sub_domain": doc["sub_domain"],
                    "measurement_goal": doc["measurement_goal"],
                    "focus_areas": doc["focus_areas"],
                    "risk_categories": doc["risk_categories"],
                    "affinity_keywords": doc["affinity_keywords"],
                },
                "page_content": doc["embedding_text"],
                # Also include full control data for retrieval
                "content": doc["full_control_data"],
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
    logger.info(f"Upserting {len(points)} controls to {collection_name}...")
    try:
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )
        logger.info(f"✓ Indexed {len(points)} controls from {taxonomy_file.name}")
        return len(points)
    except Exception as e:
        logger.error(f"Error upserting controls: {e}")
        return 0


def ingest_taxonomy_directory(
    taxonomy_dir: Path,
    embedder: EmbeddingService,
    qdrant_client,
    collection_name: str,
    reinit: bool = False,
) -> Dict[str, int]:
    """
    Ingest all enriched control taxonomy files from a directory.
    
    Args:
        taxonomy_dir: Directory containing enriched taxonomy JSON files
        embedder: EmbeddingService instance
        qdrant_client: Qdrant client instance
        collection_name: Qdrant collection name
        reinit: If True, delete and recreate collection on first file
    
    Returns:
        Dictionary mapping filename -> count of controls indexed
    """
    taxonomy_dir = Path(taxonomy_dir)
    if not taxonomy_dir.exists():
        logger.error(f"Taxonomy directory not found: {taxonomy_dir}")
        return {}
    
    # Find all enriched taxonomy JSON files
    taxonomy_files = list(taxonomy_dir.glob("*_enriched.json"))
    if not taxonomy_files:
        logger.warning(f"No enriched taxonomy files found in {taxonomy_dir}")
        return {}
    
    logger.info(f"Found {len(taxonomy_files)} taxonomy file(s)")
    
    results = {}
    first_file = True
    
    for taxonomy_file in taxonomy_files:
        count = ingest_taxonomy_file(
            taxonomy_file=taxonomy_file,
            embedder=embedder,
            qdrant_client=qdrant_client,
            collection_name=collection_name,
            reinit=reinit and first_file,  # Only reinit on first file
        )
        results[taxonomy_file.name] = count
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
        description="Ingest enriched control taxonomy JSON files into Qdrant"
    )
    parser.add_argument(
        "--taxonomy-dir",
        type=str,
        default=None,
        help="Directory containing enriched taxonomy JSON files (e.g., control_taxonomy_enriched/)"
    )
    parser.add_argument(
        "--taxonomy-file",
        type=str,
        default=None,
        help="Single enriched taxonomy JSON file to ingest"
    )
    parser.add_argument(
        "--reinit-qdrant",
        action="store_true",
        help="Delete and recreate Qdrant collection (destructive)",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default="control_taxonomy_enriched",
        help="Qdrant collection name (default: control_taxonomy_enriched)",
    )
    
    args = parser.parse_args()
    
    if not args.taxonomy_dir and not args.taxonomy_file:
        logger.error("Either --taxonomy-dir or --taxonomy-file must be provided")
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
    
    # Ingest taxonomy
    try:
        if args.taxonomy_file:
            logger.info("=" * 60)
            logger.info("Ingesting single taxonomy file")
            logger.info("=" * 60)
            
            taxonomy_path = Path(args.taxonomy_file)
            if not taxonomy_path.exists():
                logger.error(f"Taxonomy file not found: {taxonomy_path}")
                return 1
            
            count = ingest_taxonomy_file(
                taxonomy_file=taxonomy_path,
                embedder=embedder,
                qdrant_client=qdrant_client,
                collection_name=args.collection_name,
                reinit=args.reinit_qdrant,
            )
            
            logger.info("=" * 60)
            logger.info(f"Ingestion complete: {count} controls indexed")
            logger.info("=" * 60)
            
            return 0 if count > 0 else 1
        
        else:
            logger.info("=" * 60)
            logger.info("Ingesting taxonomy directory")
            logger.info(f"Directory: {Path(args.taxonomy_dir).resolve()}")
            logger.info("=" * 60)
            
            taxonomy_dir = Path(args.taxonomy_dir)
            if not taxonomy_dir.exists():
                logger.error(f"Taxonomy directory not found: {taxonomy_dir}")
                return 1
            
            results = ingest_taxonomy_directory(
                taxonomy_dir=taxonomy_dir,
                embedder=embedder,
                qdrant_client=qdrant_client,
                collection_name=args.collection_name,
                reinit=args.reinit_qdrant,
            )
            
            total = sum(results.values())
            
            logger.info("=" * 60)
            logger.info("Ingestion Summary")
            logger.info("=" * 60)
            for filename, count in results.items():
                logger.info(f"  {filename}: {count} controls")
            logger.info(f"Total: {total} controls indexed")
            logger.info("=" * 60)
            
            return 0 if total > 0 else 1
    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
