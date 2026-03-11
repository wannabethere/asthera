"""
Ingest Causal Edge Seed Data into Postgres and Vector Store

This script:
1. Loads seed edges from lms_causal_edge_seed.json
2. Inserts into Postgres (cce.causal_corpus + cce.causal_adjacency)
3. Ingests into vector store (cce_causal_edges collection)

Usage:
    # Uses settings from .env file (POSTGRES_HOST, POSTGRES_DB, etc.)
    python ingest_causal_seed_data.py
    
    # Or override with explicit connection string
    python ingest_causal_seed_data.py --db-url postgresql://...
    
    # Or set CCE_DB_URL environment variable
    CCE_DB_URL=postgresql://... python ingest_causal_seed_data.py

The script will use database settings from .env file (loaded via settings.py).
Priority: --db-url > CCE_DB_URL env var > POSTGRES_* settings from .env
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning("psycopg2 not available, Postgres ingestion will be skipped")

# Add project root to path for imports
# Script is at: app/agents/causalgraph/scripts/ingest_causal_seed_data.py
# Need to go up to complianceskill/ (project root)
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent.parent  # Up to complianceskill/
sys.path.insert(0, str(project_root))

from app.agents.causalgraph.vector_causal_graph_builder import ingest_edges
from app.core.settings import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def build_db_connection_string(settings=None) -> Optional[str]:
    """
    Build Postgres connection string from settings.
    
    Priority:
    1. CCE_DB_URL environment variable (if set)
    2. Settings from .env file (POSTGRES_* variables)
    
    Returns None if no database config is available.
    """
    # Check environment variable first
    cce_db_url = os.getenv("CCE_DB_URL")
    if cce_db_url:
        logger.info("Using CCE_DB_URL from environment variable")
        return cce_db_url
    
    # Use settings from .env file
    if settings is None:
        settings = get_settings()
    
    db_config = settings.get_database_config()
    
    if db_config.get("type") != "postgres":
        logger.warning(f"Database type is {db_config.get('type')}, not postgres. Skipping Postgres ingestion.")
        return None
    
    host = db_config.get("host")
    port = db_config.get("port")
    database = db_config.get("database")
    user = db_config.get("user")
    password = db_config.get("password")
    
    if not all([host, database, user]):
        logger.warning("Postgres settings incomplete (missing host, database, or user). Skipping Postgres ingestion.")
        return None
    
    # Build connection string with proper URL encoding for special characters
    # URL-encode user, password, and database name to handle special characters
    encoded_user = quote_plus(user)
    encoded_password = quote_plus(password) if password else ""
    encoded_database = quote_plus(database)
    
    if password:
        conn_string = f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{encoded_database}"
    else:
        conn_string = f"postgresql://{encoded_user}@{host}:{port}/{encoded_database}"
    
    logger.info(f"Built connection string from settings: postgresql://{encoded_user}@{'***' if password else ''}@{host}:{port}/{encoded_database}")
    return conn_string


def load_seed_edges(seed_file: str) -> List[Dict[str, Any]]:
    """Load seed edges from JSON file."""
    seed_path = Path(__file__).parent.parent / "data" / seed_file
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")
    
    with open(seed_path, "r") as f:
        edges = json.load(f)
    
    logger.info(f"Loaded {len(edges)} seed edges from {seed_path}")
    return edges


def insert_into_causal_corpus(conn_string: str, edges: List[Dict[str, Any]]) -> int:
    """Insert edges into cce.causal_corpus table."""
    if not POSTGRES_AVAILABLE:
        logger.warning("Postgres not available, skipping causal_corpus insertion")
        return 0
    
    inserted = 0
    try:
        with psycopg2.connect(conn_string) as conn:
            with conn.cursor() as cur:
                for edge in edges:
                    cur.execute("""
                        INSERT INTO cce.causal_corpus
                            (entry_id, source_node_category, target_node_category,
                             direction, mechanism, lag_window_days, confidence,
                             evidence_type, vertical, domain, provenance, source)
                        VALUES
                            (%(entry_id)s, %(source_node_category)s, %(target_node_category)s,
                             %(direction)s, %(mechanism)s, %(lag_window_days)s, %(confidence)s,
                             %(evidence_type)s, %(vertical)s, %(domain)s,
                             %(provenance)s, %(source)s)
                        ON CONFLICT (entry_id) DO UPDATE SET
                            confidence = EXCLUDED.confidence,
                            mechanism = EXCLUDED.mechanism,
                            updated_at = NOW()
                    """, {
                        "entry_id": edge.get("entry_id", edge.get("edge_id", "")),
                        "source_node_category": edge.get("source_node_category", ""),
                        "target_node_category": edge.get("target_node_category", ""),
                        "direction": edge.get("direction", "positive"),
                        "mechanism": edge.get("mechanism", ""),
                        "lag_window_days": edge.get("lag_window_days", 14),
                        "confidence": edge.get("confidence", 0.5),
                        "evidence_type": edge.get("evidence_type", "operational_study"),
                        "vertical": edge.get("vertical", "lms"),
                        "domain": edge.get("domain", ""),
                        "provenance": edge.get("provenance", ""),
                        "source": edge.get("source", "seed"),
                    })
                    inserted += 1
            conn.commit()
        logger.info(f"Inserted/updated {inserted} edges into cce.causal_corpus")
    except Exception as e:
        logger.error(f"Failed to insert into causal_corpus: {e}", exc_info=True)
        raise
    
    return inserted


def insert_into_causal_adjacency(conn_string: str, edges: List[Dict[str, Any]]) -> int:
    """Insert edges into cce.causal_adjacency table for structural lookups."""
    if not POSTGRES_AVAILABLE:
        logger.warning("Postgres not available, skipping causal_adjacency insertion")
        return 0
    
    inserted = 0
    try:
        with psycopg2.connect(conn_string) as conn:
            with conn.cursor() as cur:
                for edge in edges:
                    cur.execute("""
                        INSERT INTO cce.causal_adjacency
                            (edge_id, source_node_id, target_node_id,
                             direction, lag_window_days, confidence,
                             corpus_match_type, evidence_type, mechanism,
                             vertical, domain, provenance, source)
                        VALUES
                            (%(edge_id)s, %(source_node_id)s, %(target_node_id)s,
                             %(direction)s, %(lag_window_days)s, %(confidence)s,
                             %(corpus_match_type)s, %(evidence_type)s, %(mechanism)s,
                             %(vertical)s, %(domain)s, %(provenance)s, %(source)s)
                        ON CONFLICT (edge_id) DO UPDATE SET
                            confidence = EXCLUDED.confidence,
                            mechanism = EXCLUDED.mechanism,
                            updated_at = NOW()
                    """, {
                        "edge_id": edge.get("edge_id", edge.get("entry_id", "")),
                        "source_node_id": edge.get("source_node_id", ""),
                        "target_node_id": edge.get("target_node_id", ""),
                        "direction": edge.get("direction", "positive"),
                        "lag_window_days": edge.get("lag_window_days", 14),
                        "confidence": edge.get("confidence", 0.5),
                        "corpus_match_type": edge.get("corpus_match_type", "confirmed"),
                        "evidence_type": edge.get("evidence_type", "operational_study"),
                        "mechanism": edge.get("mechanism", ""),
                        "vertical": edge.get("vertical", "lms"),
                        "domain": edge.get("domain", ""),
                        "provenance": edge.get("provenance", ""),
                        "source": edge.get("source", "seed"),
                    })
                    inserted += 1
            conn.commit()
        logger.info(f"Inserted/updated {inserted} edges into cce.causal_adjacency")
    except Exception as e:
        logger.error(f"Failed to insert into causal_adjacency: {e}", exc_info=True)
        raise
    
    return inserted


async def ingest_into_vector_store(edges: List[Dict[str, Any]]) -> int:
    """Ingest edges into vector store using existing ingest_edges function."""
    try:
        ingested = await ingest_edges(edges, batch_size=50)
        logger.info(f"Ingested {ingested} edges into vector store (cce_causal_edges collection)")
        return ingested
    except Exception as e:
        logger.error(f"Failed to ingest into vector store: {e}", exc_info=True)
        raise


async def main():
    parser = argparse.ArgumentParser(description="Ingest causal edge seed data")
    parser.add_argument(
        "--seed-file",
        default="lms_causal_edge_seed.json",
        help="Seed JSON file name (in app/agents/causalgraph/data/)"
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Postgres connection string (optional, uses settings from .env if not provided)"
    )
    parser.add_argument(
        "--skip-postgres",
        action="store_true",
        help="Skip Postgres ingestion (vector store only)"
    )
    parser.add_argument(
        "--skip-vector",
        action="store_true",
        help="Skip vector store ingestion (Postgres only)"
    )
    
    args = parser.parse_args()
    
    # Get settings (loads from .env file)
    settings = get_settings()
    
    # Determine database connection string
    db_url = args.db_url
    if not db_url and not args.skip_postgres:
        db_url = build_db_connection_string(settings)
        if not db_url:
            logger.error("No database connection available. Set CCE_DB_URL env var, provide --db-url, or configure POSTGRES_* in .env file")
            sys.exit(1)
    
    # Load seed edges
    edges = load_seed_edges(args.seed_file)
    logger.info(f"Processing {len(edges)} seed edges")
    
    # Ingest into Postgres
    if not args.skip_postgres and db_url:
        logger.info("Ingesting into Postgres...")
        corpus_count = insert_into_causal_corpus(db_url, edges)
        adjacency_count = insert_into_causal_adjacency(db_url, edges)
        logger.info(f"Postgres: {corpus_count} corpus entries, {adjacency_count} adjacency entries")
    else:
        logger.info("Skipping Postgres ingestion")
    
    # Ingest into vector store
    if not args.skip_vector:
        logger.info("Ingesting into vector store...")
        vector_count = await ingest_into_vector_store(edges)
        logger.info(f"Vector store: {vector_count} edges ingested")
    else:
        logger.info("Skipping vector store ingestion")
    
    logger.info("Ingestion complete!")


if __name__ == "__main__":
    asyncio.run(main())
