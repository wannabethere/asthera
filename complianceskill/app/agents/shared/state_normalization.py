"""
State normalization utilities for calculation planner.

Converts workflow-specific state formats (CSOD, DT) to standardized format
that the calculation planner expects.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def normalize_state_for_calculation_planner(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize workflow-specific state to standardized format for calculation planner.
    
    Standardized format:
    - resolved_metrics: List[Dict] - standardized metric format
    - mdl_schemas: List[Dict] - standardized schema format with table_name, table_ddl, description, column_metadata
    - user_query: str
    - data_enrichment: Dict with metrics_intent
    - data_science_insights: Optional[List[Dict]] - optional insights with SQL functions
    
    Returns normalized state dict with only the fields calculation planner needs.
    """
    normalized = {
        "resolved_metrics": [],
        "mdl_schemas": [],
        "user_query": state.get("user_query", ""),
        "data_enrichment": state.get("data_enrichment", {}),
        "data_science_insights": [],
        "needs_calculation": state.get("needs_calculation", True),
    }
    
    # ── Normalize metrics ────────────────────────────────────────────────────────
    # Try DT workflow format first
    resolved_metrics = state.get("resolved_metrics", [])
    
    # Try CSOD workflow format
    if not resolved_metrics:
        csod_metric_recommendations = state.get("csod_metric_recommendations", [])
        if csod_metric_recommendations:
            resolved_metrics = _convert_csod_metrics_to_standard(csod_metric_recommendations)
    
    normalized["resolved_metrics"] = resolved_metrics
    
    # ── Normalize schemas ────────────────────────────────────────────────────────
    # Try DT workflow format (from context_cache.schema_resolution)
    schema_resolution_output = state.get("context_cache", {}).get("schema_resolution", {})
    mdl_schemas = []
    
    if isinstance(schema_resolution_output, dict):
        # Extract from DT workflow format
        schemas_list = schema_resolution_output.get("schemas", [])
        table_descs_list = schema_resolution_output.get("table_descriptions", [])
        
        # Format schemas (from leen_db_schema)
        for s in schemas_list:
            if isinstance(s, dict):
                mdl_schemas.append(_normalize_schema(s))
        
        # Format table descriptions (from leen_table_description)
        for td in table_descs_list:
            if isinstance(td, dict):
                table_name = td.get("table_name", "")
                # Check if we already have this table
                existing = next((s for s in mdl_schemas if s.get("table_name") == table_name), None)
                if existing:
                    # Merge description if not present
                    if not existing.get("description") and td.get("description"):
                        existing["description"] = td.get("description")
                    # Merge columns/relationships
                    if td.get("columns") and not existing.get("column_metadata"):
                        existing["column_metadata"] = td.get("columns", [])
                else:
                    # Add as new schema
                    mdl_schemas.append({
                        "table_name": table_name,
                        "table_ddl": "",  # Table descriptions don't have DDL
                        "description": td.get("description", ""),
                        "column_metadata": td.get("columns", [])
                    })
    
    # Try CSOD workflow format
    csod_resolved_schemas = state.get("csod_resolved_schemas", [])
    if csod_resolved_schemas:
        for s in csod_resolved_schemas:
            if isinstance(s, dict):
                table_name = s.get("table_name", "")
                # Check if we already have this table
                existing = next((sch for sch in mdl_schemas if sch.get("table_name") == table_name), None)
                if existing:
                    # Merge if needed
                    if not existing.get("table_ddl") and s.get("table_ddl"):
                        existing["table_ddl"] = s.get("table_ddl")
                    if not existing.get("description") and s.get("description"):
                        existing["description"] = s.get("description")
                    if not existing.get("column_metadata") and s.get("column_metadata"):
                        existing["column_metadata"] = s.get("column_metadata")
                else:
                    mdl_schemas.append(_normalize_schema(s))
    
    normalized["mdl_schemas"] = mdl_schemas
    
    # ── Normalize data science insights (CSOD workflow) ─────────────────────────
    csod_data_science_insights = state.get("csod_data_science_insights", [])
    if csod_data_science_insights:
        normalized["data_science_insights"] = csod_data_science_insights
    
    return normalized


def _convert_csod_metrics_to_standard(csod_metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert CSOD metric recommendations to standardized resolved_metrics format."""
    resolved_metrics = []
    for m in csod_metrics:
        resolved_metrics.append({
            "metric_id": m.get("metric_id", ""),
            "name": m.get("name", ""),
            "description": m.get("description", ""),
            "category": m.get("category", ""),
            "kpis": m.get("kpis_covered", []),
            "trends": [],
            "natural_language_question": m.get("natural_language_question", ""),
            "source_schemas": m.get("mapped_tables", []),
            "data_capability": "temporal" if m.get("metrics_intent") == "trend" else "current_state",
        })
    return resolved_metrics


def _normalize_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a schema dict to standard format."""
    return {
        "table_name": schema.get("table_name", ""),
        "table_ddl": schema.get("table_ddl", ""),
        "description": schema.get("description", ""),
        "column_metadata": schema.get("column_metadata", []),
    }
