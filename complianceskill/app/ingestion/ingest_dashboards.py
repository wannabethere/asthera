"""
Ingest dashboard components into mdl_dashboards collection.

This script parses dashboard JSON responses and indexes individual dashboard components
(one document per component) into Qdrant for use by the dashboard generation workflow.

Each dashboard component is indexed as a standalone document with:
- question (natural language question)
- component_type (kpi/metric/table/insight)
- reasoning (why this component type was chosen)
- dashboard context (parent dashboard name/description)
- table/column references
- SQL query (for reference)

Usage:
    python -m app.ingestion.ingest_dashboards --dashboard-file /path/to/dashboard.json
    python -m app.ingestion.ingest_dashboards --dashboard-file /path/to/dashboard.json --reinit-qdrant
    python -m app.ingestion.ingest_dashboards --dashboard-dir /path/to/dashboards --reinit-qdrant
"""

import argparse
import json
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

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


def extract_table_names_from_sql(sql: str) -> List[str]:
    """Extract table names from SQL query (FROM/JOIN clauses)."""
    if not sql:
        return []
    
    # Simple regex to find table names after FROM and JOIN
    table_pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(table_pattern, sql, re.IGNORECASE)
    return list(dict.fromkeys(matches))  # Deduplicate while preserving order


def extract_columns_from_sql(sql: str) -> List[str]:
    """Extract column names from SQL SELECT clause."""
    if not sql:
        return []
    
    # Extract SELECT clause
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return []
    
    select_clause = select_match.group(1)
    # Split by comma and extract column names (handle aliases)
    columns = []
    for col in select_clause.split(','):
        col = col.strip()
        # Remove aliases (AS alias or column alias)
        col = re.sub(r'\s+AS\s+\w+$', '', col, flags=re.IGNORECASE)
        col = re.sub(r'\s+\w+$', '', col)  # Remove trailing word (alias)
        # Extract column name (handle table.column)
        col_match = re.search(r'\.?([a-zA-Z_][a-zA-Z0-9_]*)$', col)
        if col_match:
            columns.append(col_match.group(1))
    
    return columns


def infer_component_type(chart_schema: Dict[str, Any]) -> str:
    """Infer component_type from chart_schema."""
    if not chart_schema:
        return "table"  # Default
    
    chart_type = chart_schema.get("chart_type", "").lower()
    if "kpi" in chart_type or "gauge" in chart_type or "stat" in chart_type:
        return "kpi"
    elif "bar" in chart_type or "line" in chart_type or "pie" in chart_type:
        return "metric"
    elif "table" in chart_type or "data_table" in chart_type:
        return "table"
    else:
        return "metric"  # Default to metric for charts


def infer_data_domain(question: str, table_names: List[str], tags: List[str]) -> str:
    """Infer data domain from question, table names, and tags."""
    question_lower = question.lower()
    tables_lower = [t.lower() for t in table_names]
    tags_lower = [t.lower() for t in tags]
    
    # Training compliance
    if any(word in question_lower for word in ["training", "course", "lms", "enrollment", "completion"]):
        return "training_compliance"
    if any("training" in t or "course" in t for t in tables_lower):
        return "training_compliance"
    
    # Vulnerability management
    if any(word in question_lower for word in ["vulnerability", "cve", "remediation", "scan"]):
        return "vulnerability_management"
    if any("vuln" in t or "cve" in t for t in tables_lower):
        return "vulnerability_management"
    
    # Access control
    if any(word in question_lower for word in ["access", "login", "permission", "auth"]):
        return "access_control"
    if any("access" in t or "login" in t or "auth" in t for t in tables_lower):
        return "access_control"
    
    # User management
    if any(word in question_lower for word in ["user", "employee", "department", "role"]):
        return "user_management"
    
    # Incident management
    if any(word in question_lower for word in ["incident", "ticket", "alert"]):
        return "incident_management"
    
    # Default
    return "unknown"


def parse_dashboard_component(
    component: Dict[str, Any],
    dashboard_id: str,
    dashboard_name: str,
    dashboard_description: str,
    dashboard_type: str,
    project_id: str,
    source_id: str,
    component_sequence: int,
) -> Optional[Dict[str, Any]]:
    """
    Parse a single dashboard component into a document for indexing.
    
    Returns:
        Dict with all fields needed for indexing, or None if component is invalid
    """
    # Extract component fields
    question = component.get("natural_language_question", "")
    if not question:
        logger.warning(f"Component {component_sequence} missing natural_language_question, skipping")
        return None
    
    sql_query = component.get("sql_query", "")
    chart_schema = component.get("chart_schema", {})
    reasoning = component.get("reasoning", "")
    
    # Infer component_type from chart_schema
    component_type = component.get("component_type") or infer_component_type(chart_schema)
    
    # Extract table names from SQL
    data_tables = component.get("data_tables", [])
    if not data_tables and sql_query:
        data_tables = extract_table_names_from_sql(sql_query)
    
    # Extract columns from SQL
    columns_used = component.get("columns_used", [])
    if not columns_used and sql_query:
        columns_used = extract_columns_from_sql(sql_query)
    
    # Extract filters from chart_schema
    filters_available = component.get("suggested_filters", [])
    if not filters_available and chart_schema:
        encoding = chart_schema.get("encoding", {})
        if encoding:
            # Extract filter fields from encoding
            for key, value in encoding.items():
                if isinstance(value, dict) and value.get("field"):
                    filters_available.append(value["field"])
    
    # Generate tags from question and dashboard name
    tags = component.get("tags", [])
    if not tags:
        # Extract keywords from question
        words = re.findall(r'\b[a-zA-Z]{4,}\b', question.lower())
        tags = list(set(words))[:10]  # Limit to 10 tags
    
    # Infer data domain
    data_domain = infer_data_domain(question, data_tables, tags)
    
    # Get chart hint
    chart_hint = component.get("chart_hint")
    if not chart_hint and chart_schema:
        chart_type = chart_schema.get("chart_type", "")
        chart_hint = chart_type.lower() if chart_type else "kpi_card"
    
    # Build document
    doc = {
        "id": _stable_uuid(f"{dashboard_id}:{component_sequence}"),
        "question": question,
        "component_type": component_type,
        "data_tables": data_tables,
        "reasoning": reasoning,
        "chart_hint": chart_hint,
        "columns_used": columns_used,
        "filters_available": filters_available,
        "dashboard_id": dashboard_id,
        "dashboard_name": dashboard_name,
        "dashboard_description": dashboard_description,
        "dashboard_type": dashboard_type,
        "project_id": project_id,
        "source_id": source_id,
        "component_sequence": component_sequence,
        "sql_query": sql_query,
        "tags": tags,
        "metadata": {
            "data_domain": data_domain,
            "parent_component_count": len(component.get("parent_components", [])),
            "audience": component.get("audience", "mixed"),
        }
    }
    
    return doc


def build_embedding_text(doc: Dict[str, Any]) -> str:
    """
    Build text for embedding from dashboard component document.
    
    Format: question | reasoning | dashboard_description
    This ensures the vector captures what, why, and context.
    """
    parts = []
    
    # Question (what is being asked)
    if doc.get("question"):
        parts.append(doc["question"])
    
    # Reasoning (why it matters)
    if doc.get("reasoning"):
        parts.append(doc["reasoning"])
    
    # Dashboard description (context)
    if doc.get("dashboard_description"):
        parts.append(doc["dashboard_description"])
    
    return " | ".join(parts)


def ingest_dashboard_file(
    dashboard_file: Path,
    embedder: EmbeddingService,
    qdrant_client,
    collection_name: str,
    reinit: bool = False,
) -> int:
    """
    Ingest a single dashboard JSON file.
    
    Returns:
        Number of components indexed
    """
    logger.info(f"Processing dashboard file: {dashboard_file}")
    
    try:
        with open(dashboard_file, 'r') as f:
            dashboard_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load dashboard file {dashboard_file}: {e}")
        return 0
    
    # Extract dashboard-level fields
    dashboard_id = dashboard_data.get("dashboard_id") or str(uuid.uuid4())
    dashboard_name = dashboard_data.get("dashboard_name", "Unnamed Dashboard")
    dashboard_description = dashboard_data.get("dashboard_description", "")
    dashboard_type = dashboard_data.get("dashboard_type", "Dynamic")
    project_id = dashboard_data.get("project_id", "")
    source_id = dashboard_data.get("source_id", project_id)  # Fallback to project_id
    
    # Extract components
    components = dashboard_data.get("content", {}).get("components", [])
    if not components:
        logger.warning(f"No components found in dashboard {dashboard_id}")
        return 0
    
    logger.info(f"Found {len(components)} components in dashboard '{dashboard_name}'")
    
    # Parse components into documents
    documents = []
    for idx, component in enumerate(components, start=1):
        doc = parse_dashboard_component(
            component=component,
            dashboard_id=dashboard_id,
            dashboard_name=dashboard_name,
            dashboard_description=dashboard_description,
            dashboard_type=dashboard_type,
            project_id=project_id,
            source_id=source_id,
            component_sequence=idx,
        )
        if doc:
            documents.append(doc)
    
    if not documents:
        logger.warning(f"No valid components to index from dashboard {dashboard_id}")
        return 0
    
    # Build embedding texts
    embedding_texts = [build_embedding_text(doc) for doc in documents]
    
    # Embed
    logger.info(f"Embedding {len(embedding_texts)} components...")
    vectors = embedder.embed(embedding_texts)
    
    # Prepare Qdrant points
    points = []
    for doc, vector in zip(documents, vectors):
        point = qmodels.PointStruct(
            id=doc["id"],
            vector=vector,
            payload={
                "metadata": {
                    "question": doc["question"],
                    "component_type": doc["component_type"],
                    "data_tables": doc["data_tables"],
                    "reasoning": doc["reasoning"],
                    "chart_hint": doc["chart_hint"],
                    "columns_used": doc["columns_used"],
                    "filters_available": doc["filters_available"],
                    "dashboard_id": doc["dashboard_id"],
                    "dashboard_name": doc["dashboard_name"],
                    "dashboard_description": doc["dashboard_description"],
                    "dashboard_type": doc["dashboard_type"],
                    "project_id": doc["project_id"],
                    "source_id": doc["source_id"],
                    "component_sequence": doc["component_sequence"],
                    "sql_query": doc["sql_query"],
                    "tags": doc["tags"],
                    **doc["metadata"],
                },
                "page_content": embedding_texts[documents.index(doc)],
            }
        )
        points.append(point)
    
    # Upsert to Qdrant
    logger.info(f"Upserting {len(points)} points to {collection_name}...")
    qdrant_client.upsert(
        collection_name=collection_name,
        points=points,
    )
    
    logger.info(f"✓ Indexed {len(points)} components from dashboard '{dashboard_name}'")
    return len(points)


def main():
    parser = argparse.ArgumentParser(description="Ingest dashboard components into mdl_dashboards collection")
    parser.add_argument(
        "--dashboard-file",
        type=Path,
        help="Path to a single dashboard JSON file",
    )
    parser.add_argument(
        "--dashboard-dir",
        type=Path,
        help="Path to directory containing dashboard JSON files",
    )
    parser.add_argument(
        "--reinit-qdrant",
        action="store_true",
        help="Delete and recreate Qdrant collection before ingestion",
    )
    
    args = parser.parse_args()
    
    if not args.dashboard_file and not args.dashboard_dir:
        parser.error("Must provide either --dashboard-file or --dashboard-dir")
    
    # Initialize services
    embedder = EmbeddingService()
    qdrant_client = _get_underlying_qdrant_client()
    collection_name = MDLCollections.DASHBOARDS
    
    # Initialize collection
    if args.reinit_qdrant:
        logger.info(f"Deleting collection {collection_name}...")
        try:
            qdrant_client.delete_collection(collection_name)
        except Exception as e:
            logger.warning(f"Collection {collection_name} may not exist: {e}")
    
    logger.info(f"Creating/ensuring collection {collection_name} exists...")
    try:
        qdrant_client.get_collection(collection_name)
        logger.info(f"Collection {collection_name} already exists")
    except Exception:
        logger.info(f"Creating collection {collection_name}...")
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=_vector_params(),
        )
    
    # Collect dashboard files
    dashboard_files = []
    if args.dashboard_file:
        if args.dashboard_file.exists():
            dashboard_files.append(args.dashboard_file)
        else:
            logger.error(f"Dashboard file not found: {args.dashboard_file}")
            sys.exit(1)
    elif args.dashboard_dir:
        if not args.dashboard_dir.exists():
            logger.error(f"Dashboard directory not found: {args.dashboard_dir}")
            sys.exit(1)
        dashboard_files = list(args.dashboard_dir.glob("*.json"))
        if not dashboard_files:
            logger.warning(f"No JSON files found in {args.dashboard_dir}")
            sys.exit(0)
    
    # Ingest all dashboards
    total_components = 0
    for dashboard_file in dashboard_files:
        count = ingest_dashboard_file(
            dashboard_file=dashboard_file,
            embedder=embedder,
            qdrant_client=qdrant_client,
            collection_name=collection_name,
            reinit=args.reinit_qdrant,
        )
        total_components += count
    
    logger.info(f"\n{'=' * 50}")
    logger.info(f"Ingestion complete!")
    logger.info(f"  Total dashboards processed: {len(dashboard_files)}")
    logger.info(f"  Total components indexed: {total_components}")
    logger.info(f"{'=' * 50}")


if __name__ == "__main__":
    main()
