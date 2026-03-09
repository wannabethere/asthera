"""
Medallion plan utilities — shared helpers for silver and gold model plans.

Used when silver_tables_info is empty: create a minimal plan for silver table creation
that downstream can use and extend to gold. Kept in shared for reuse across workflows.

Also used when LLM returns requires_gold_model=False with empty specs: create minimal
gold specs from metrics + silver so cube and gold SQL can be generated.
"""
from typing import Any

from .models import (
    GoldModelPlan,
    GoldModelSpecification,
    OutputColumn,
    SilverModelSpecification,
    SilverTableInfo,
    SourceTableColumn,
)


def create_minimal_plan_for_missing_silver(
    metrics: list[dict[str, Any]],
    reasoning: str = "Silver tables not found; minimal plan for silver creation. Downstream can extend to gold.",
) -> GoldModelPlan:
    """Create a minimal medallion plan when silver_tables_info is empty.

    Derives silver specification from metrics' source_schemas so downstream can:
    1. Create silver tables from bronze/source
    2. Extend to gold models

    Args:
        metrics: Resolved metrics or metric recommendations (used for source_schemas)
        reasoning: Optional custom reasoning string

    Returns:
        GoldModelPlan with requires_silver_model=True and a silver_specification
        derived from metrics. specifications=[] (gold specs to be added by downstream).
    """
    source_schema_names: list[str] = []
    for m in metrics or []:
        if isinstance(m, dict):
            for s in m.get("source_schemas", []) or []:
                if s and s not in source_schema_names:
                    source_schema_names.append(s)

    # Derive a placeholder silver name from first schema or generic
    first_schema = source_schema_names[0] if source_schema_names else "metrics"
    silver_name = f"silver_{first_schema.replace('_schema', '')}" if first_schema != "metrics" else "silver_metrics_placeholder"

    silver_spec = SilverModelSpecification(
        name=silver_name,
        description=(
            f"Silver table to be created from source/bronze. "
            f"Required for downstream metrics. "
            f"Source schemas from metrics: {', '.join(source_schema_names[:5]) or 'unknown'}"
            + ("..." if len(source_schema_names) > 5 else "")
        ),
        materialization="table",
        source_tables=[],
        source_schema_names=source_schema_names,
        expected_columns=[
            OutputColumn(name="connection_id", description="Required for multi-tenant filtering"),
        ],
    )

    return GoldModelPlan(
        requires_gold_model=True,
        reasoning=reasoning,
        specifications=[],
        requires_silver_model=True,
        silver_specifications=[silver_spec],
    )


def create_minimal_gold_specs_from_metrics_and_silver(
    silver_tables_info: list[SilverTableInfo],
    metrics: list[dict[str, Any]],
) -> list[GoldModelSpecification]:
    """Create minimal gold specs when LLM returns empty specifications.

    Used as fallback when plan has requires_gold_model=False or empty specs
    but we have metrics and dt_generate_sql - ensures cube and gold SQL are generated.

    Groups silver tables by vendor (first part of table name, e.g. qualys_hosts -> qualys)
    and creates one gold spec per vendor.
    """
    if not silver_tables_info or not metrics:
        return []

    # Group silver tables by vendor (prefix before _)
    vendor_to_tables: dict[str, list[str]] = {}
    for t in silver_tables_info:
        name = t.table_name if hasattr(t, "table_name") else t.get("table_name", "")
        if not name:
            continue
        vendor = name.split("_")[0] if "_" in name else "default"
        if vendor not in vendor_to_tables:
            vendor_to_tables[vendor] = []
        if name not in vendor_to_tables[vendor]:
            vendor_to_tables[vendor].append(name)

    # Collect metric IDs for mapped_metrics
    metric_ids = [
        m.get("metric_id") or m.get("id") or m.get("name", "")
        for m in metrics
        if isinstance(m, dict) and (m.get("metric_id") or m.get("id") or m.get("name"))
    ][:10]

    specs: list[GoldModelSpecification] = []
    for vendor, tables in vendor_to_tables.items():
        if not tables:
            continue
        first_table = tables[0]
        gold_name = f"gold_{vendor}_metrics_snapshot"
        specs.append(
            GoldModelSpecification(
                name=gold_name,
                description=(
                    f"Gold model for {vendor} metrics. Build from silver tables: {', '.join(tables[:3])}. "
                    f"Supports metrics: {', '.join(metric_ids[:5]) or 'all'}. "
                    "Created as fallback when LLM returned empty specs."
                ),
                materialization="table",
                source_tables=tables,
                source_columns=[
                    SourceTableColumn(table_name=first_table, column_name="connection_id", usage="direct mapping"),
                ],
                expected_columns=[
                    OutputColumn(name="connection_id", description="Required for multi-tenant filtering", mapped_metrics=metric_ids),
                ],
            )
        )

    return specs
