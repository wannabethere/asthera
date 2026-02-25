"""
MDL Contextual Preview Generator
=================================

Builds preview files for MDL contextual edges (concepts, patterns, evidences, fields,
metrics, edges for table, edges for column) without creating graph traversal edges.
Uses cybersecurity categories to map edges for query fixing. Tables, schema, definitions,
and descriptions are unchanged; this only adds mdl_docs preview files.

Metrics, evidences, and patterns can be derived from enriched metadata only, or from
LLM extraction per table using dependencies (relationships), architecture, and provider
context for usage-specific output (--use-llm).

Usage:
    # From existing enriched metadata + MDL (no LLM)
    python -m indexing_cli.index_mdl_preview_contextual \
        --enriched-file indexing_preview/mdl_enriched/enriched_metadata_20260128_005808_Snyk.json \
        --mdl-file path/to/snyk_mdl.json \
        --product-name "Snyk" \
        --preview-dir indexing_preview

    # With LLM for usage-specific metrics, evidences, patterns (dependencies, architecture, provider)
    python -m indexing_cli.index_mdl_preview_contextual \
        --enriched-file ... --mdl-file ... --product-name "Snyk" --use-llm

    # Batched LLM with checkpointing (resume from where you left off; 400+ tables)
    python -m indexing_cli.index_mdl_preview_contextual \
        --enriched-file ... --mdl-file ... --product-name "Snyk" --use-llm \
        --batch-size 25 --checkpoint-dir indexing_preview/mdl_docs/checkpoints

    # Only write MDL usage outputs (metrics, evidences, patterns) and skip key_concepts/fields/edges
    python -m indexing_cli.index_mdl_preview_contextual \
        --enriched-file ... --mdl-file ... --product-name "Snyk" --use-llm --mdl-only

Output (preview_dir/mdl_docs/):
    mdl_key_concepts.json, mdl_patterns.json, mdl_evidences.json,
    mdl_fields.json, mdl_metrics.json, mdl_edges_table.json, mdl_edges_column.json
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from pydantic import BaseModel, Field
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    from app.core.dependencies import get_llm
    try:
        from app.config.organization_config import get_product_organization
    except ImportError:
        get_product_organization = None
    _LLM_AVAILABLE = True
except ImportError:
    BaseModel = None
    Field = None
    ChatPromptTemplate = None
    JsonOutputParser = None
    get_llm = None
    get_product_organization = None
    _LLM_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Categories for cybersecurity/schema mapping (same as schema_descriptions and index_mdl_enriched)
ALLOWED_CATEGORIES = [
    "access requests",
    "application data",
    "assets",
    "projects",
    "vulnerabilities",
    "integrations",
    "configuration",
    "audit logs",
    "risk management",
    "deployment",
    "groups",
    "organizations",
    "memberships and roles",
    "issues",
    "artifacts",
    "other",
]

# ---------------------------------------------------------------------------
# LLM usage extraction (metrics, evidences, patterns) with deps/arch/provider
# ---------------------------------------------------------------------------

if _LLM_AVAILABLE and BaseModel is not None:

    class UsageMetric(BaseModel):
        """Usage-specific metric for a table (considering dependencies, architecture, provider)."""
        metric_name: str
        description: str
        calculation: str
        category: str = "operational"  # performance, security, compliance, operational
        columns_used: List[str] = Field(default_factory=list)
        dependency_context: str = ""  # how related tables/joins are used

    class UsageEvidence(BaseModel):
        """Usage-specific evidence: what columns/tables support which usage."""
        evidence_type: str  # time_dimension, join_key, filter_field, aggregate_source, etc.
        description: str
        columns_or_tables: List[str] = Field(default_factory=list)
        supports_usage: str = ""  # what usage this evidence supports

    class UsagePattern(BaseModel):
        """Usage-specific query pattern (how to use this table with dependencies)."""
        pattern_type: str  # example_query, filter_pattern, join_pattern, aggregation_pattern
        natural_question: str = ""
        sql_or_steps: str = ""
        complexity: str = "moderate"
        dependency_context: str = ""

    class UsageExtractionOutput(BaseModel):
        """LLM output for usage-specific metrics, evidences, patterns per table."""
        usage_metrics: List[UsageMetric] = Field(default_factory=list, max_length=8)
        usage_evidences: List[UsageEvidence] = Field(default_factory=list, max_length=10)
        usage_patterns: List[UsagePattern] = Field(default_factory=list, max_length=6)

    USAGE_EXTRACTION_PROMPT = """You are a data expert for {product_name}. Extract **usage-specific** metrics, evidences, and patterns for this table so they can be used for query fixing and search.

**Table:** {table_name}
**Description:** {table_description}

**Columns (name, type, description):**
{columns_info}

**Dependencies (relationships / joins to other tables):**
{dependencies_info}

**Provider / architecture context:** {provider_architecture}

**Category (cybersecurity/schema):** {category}

Extract the following with **concrete specifics** tied to columns and dependencies:

1. **Usage metrics** (2-6): KPIs or measures that users would compute using this table. For each: name, description, how to calculate (mention which columns and any joins), category (performance/security/compliance/operational), and brief dependency_context if joins are needed.

2. **Usage evidences** (2-8): What columns or table relationships support specific usages. For each: evidence_type (e.g. time_dimension, join_key, filter_field, aggregate_source), description, columns_or_tables involved, and what usage this supports.

3. **Usage patterns** (2-4): Example questions or query patterns that use this table (and its dependencies). For each: pattern_type (example_query, filter_pattern, join_pattern, aggregation_pattern), natural_question, sql_or_steps, complexity, and dependency_context if joins are involved.

Be specific to this table and its columns; reference actual column names and dependency tables where relevant.

{format_instructions}
"""


def _provider_architecture_context(product_name: str) -> str:
    """Build provider/architecture context from organization config."""
    if not get_product_organization:
        return f"Product: {product_name}."
    try:
        org = get_product_organization(product_name)
        parts = [f"Product: {product_name}.", f"Organization: {org.organization_name}."]
        if org.metadata:
            parts.append("Context: " + ", ".join(f"{k}={v}" for k, v in org.metadata.items()))
        return " ".join(parts)
    except Exception:
        return f"Product: {product_name}."


async def extract_usage_specifics_llm(
    table_name: str,
    table_description: str,
    columns: List[Dict[str, Any]],
    relationships: List[str],
    category: str,
    product_name: str,
    llm: Any,
) -> UsageExtractionOutput:
    """Extract usage-specific metrics, evidences, patterns via LLM (dependencies, architecture, provider)."""
    columns_str = "\n".join([
        f"  - {c.get('name', '')} ({c.get('type', 'unknown')}): {c.get('description', 'No description')}"
        for c in (columns or [])[:25]
    ])
    if len(columns or []) > 25:
        columns_str += f"\n  ... and {len(columns) - 25} more columns"
    deps_str = "\n".join([f"  - {r}" for r in relationships]) if relationships else "  (none)"
    provider_arch = _provider_architecture_context(product_name)
    parser = JsonOutputParser(pydantic_object=UsageExtractionOutput)
    prompt = ChatPromptTemplate.from_template(USAGE_EXTRACTION_PROMPT)
    chain = prompt | llm | parser
    try:
        result = await chain.ainvoke({
            "product_name": product_name,
            "table_name": table_name,
            "table_description": table_description or "No description",
            "columns_info": columns_str,
            "dependencies_info": deps_str,
            "provider_architecture": provider_arch,
            "category": category,
            "format_instructions": parser.get_format_instructions(),
        })
        return UsageExtractionOutput(**result)
    except Exception as e:
        logger.warning("LLM usage extraction failed for %s: %s. Using empty usage specifics.", table_name, e)
        return UsageExtractionOutput()


def _load_enriched(enriched_path: Path) -> List[Dict[str, Any]]:
    """Load enriched metadata JSON. Expects list of {table, metadata}."""
    with open(enriched_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("enriched_file must be a JSON array of {table, metadata}")
    return data


def _load_mdl(mdl_path: Path) -> Dict[str, Any]:
    """Load MDL JSON; return dict with models and relationships."""
    with open(mdl_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_category_enrichment(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Load category_enrichment.json (control examples, evidence examples, frameworks per category)."""
    if not path or not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("categories") or data
    except Exception as e:
        logger.warning("Could not load category enrichment from %s: %s", path, e)
        return None


def build_mdl_category_enrichment(
    category_enrichment: Dict[str, Any],
    product_name: str,
) -> List[Dict[str, Any]]:
    """Build docs for each category with control examples, evidence examples, framework relations (NIST, ISO, SOC2, etc.)."""
    docs = []
    for category, data in category_enrichment.items():
        if not isinstance(data, dict):
            continue
        control_examples = data.get("control_examples") or []
        evidence_examples = data.get("evidence_examples") or []
        frameworks = data.get("frameworks") or []
        page_content = (
            f"Category: {category}. "
            f"Control examples: {', '.join(control_examples)}. "
            f"Evidence examples: {', '.join(evidence_examples)}. "
            f"Frameworks: {', '.join(frameworks)}. "
            f"Product: {product_name}."
        )
        docs.append(
            _doc_record(
                page_content,
                "mdl_category_enrichment",
                {
                    "category": category,
                    "control_examples": control_examples,
                    "evidence_examples": evidence_examples,
                    "frameworks": frameworks,
                    "product_name": product_name,
                },
            )
        )
    return docs


def _doc_record(
    page_content: str,
    content_type: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Standard document record for preview JSON (page_content + metadata)."""
    return {"page_content": page_content, "metadata": {**metadata, "source_content_type": content_type}}


def build_mdl_key_concepts(
    enriched_list: List[Dict[str, Any]],
    mdl_data: Dict[str, Any],
    product_name: str,
) -> List[Dict[str, Any]]:
    """Build mdl_key_concepts: one doc per table (and optionally per column) with key concepts, category."""
    docs = []
    models_by_name = {m["name"]: m for m in mdl_data.get("models", [])}
    for item in enriched_list:
        table_name = item.get("table", "")
        meta = item.get("metadata", {})
        if not table_name or not meta:
            continue
        category = meta.get("category", "other")
        if category not in ALLOWED_CATEGORIES:
            category = "other"
        # Table-level concepts from key_insights, common_use_cases, business_purpose
        concepts = []
        concepts.extend(meta.get("key_insights", []))
        concepts.extend(meta.get("common_use_cases", []))
        if meta.get("business_purpose"):
            concepts.append(meta["business_purpose"])
        for c in concepts:
            if not c or not str(c).strip():
                continue
            page_content = f"Key concept: {c}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_key_concepts",
                    {
                        "key_concept": str(c).strip(),
                        "table_name": table_name,
                        "category": category,
                        "product_name": product_name,
                    },
                )
            )
        # Column-level: time_concepts and column descriptions as concepts
        model = models_by_name.get(table_name, {})
        for tc in meta.get("time_concepts", []):
            col = tc.get("column_name", "")
            if not col:
                continue
            desc = tc.get("description", "") or "time dimension"
            page_content = f"Key concept: {desc}. Column: {col}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_key_concepts",
                    {
                        "key_concept": desc,
                        "column_name": col,
                        "table_name": table_name,
                        "category": category,
                        "product_name": product_name,
                    },
                )
            )
        for col in model.get("columns", [])[:30]:
            if col.get("isHidden"):
                continue
            desc = (col.get("description") or "").strip()
            if not desc:
                continue
            col_name = col.get("name", "")
            page_content = f"Key concept: {desc}. Column: {col_name}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_key_concepts",
                    {
                        "key_concept": desc,
                        "column_name": col_name,
                        "table_name": table_name,
                        "category": category,
                        "product_name": product_name,
                    },
                )
            )
    return docs


def build_mdl_patterns(
    enriched_list: List[Dict[str, Any]],
    product_name: str,
    usage_specifics_by_table: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build mdl_patterns: from LLM usage patterns if provided, else from example_queries and instructions."""
    docs = []
    usage_specifics_by_table = usage_specifics_by_table or {}
    for item in enriched_list:
        table_name = item.get("table", "")
        meta = item.get("metadata", {})
        if not table_name or not meta:
            continue
        category = meta.get("category", "other")
        if category not in ALLOWED_CATEGORIES:
            category = "other"
        usage = usage_specifics_by_table.get(table_name, {})
        usage_patterns = usage.get("usage_patterns") or []
        if usage_patterns:
            for p in usage_patterns:
                q = (p.get("natural_question") or "").strip()
                sql = (p.get("sql_or_steps") or "").strip()
                if not q and not sql:
                    continue
                content = q or sql
                page_content = f"Pattern: {content}. Table: {table_name}. Category: {category}. Product: {product_name}. Dependency context: {p.get('dependency_context', '')}."
                docs.append(
                    _doc_record(
                        page_content,
                        "mdl_patterns",
                        {
                            "pattern_type": p.get("pattern_type", "usage_pattern"),
                            "natural_question": q,
                            "sql_query": sql,
                            "table_name": table_name,
                            "category": category,
                            "complexity": p.get("complexity", "moderate"),
                            "dependency_context": p.get("dependency_context", ""),
                            "product_name": product_name,
                        },
                    )
                )
        for eq in meta.get("example_queries", []):
            q = eq.get("natural_question", "").strip()
            sql = eq.get("sql_query", "").strip()
            if not q:
                continue
            page_content = f"Pattern: {q}. SQL: {sql}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_patterns",
                    {
                        "pattern_type": "example_query",
                        "natural_question": q,
                        "sql_query": sql,
                        "table_name": table_name,
                        "category": category,
                        "complexity": eq.get("complexity", "moderate"),
                        "product_name": product_name,
                    },
                )
            )
        for inst in meta.get("instructions", []):
            content = (inst.get("content") or "").strip()
            if not content:
                continue
            page_content = f"Pattern: {content}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_patterns",
                    {
                        "pattern_type": inst.get("instruction_type", "instruction"),
                        "content": content,
                        "table_name": table_name,
                        "category": category,
                        "priority": inst.get("priority", "normal"),
                        "product_name": product_name,
                    },
                )
            )
    return docs


def build_mdl_evidences(
    enriched_list: List[Dict[str, Any]],
    mdl_data: Dict[str, Any],
    product_name: str,
    usage_specifics_by_table: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build mdl_evidences: from LLM usage evidences if provided, else from relationships/time_concepts/features."""
    docs = []
    models_by_name = {m["name"]: m for m in mdl_data.get("models", [])}
    usage_specifics_by_table = usage_specifics_by_table or {}
    for item in enriched_list:
        table_name = item.get("table", "")
        meta = item.get("metadata", {})
        if not table_name or not meta:
            continue
        category = meta.get("category", "other")
        if category not in ALLOWED_CATEGORIES:
            category = "other"
        usage = usage_specifics_by_table.get(table_name, {})
        usage_evidences = usage.get("usage_evidences") or []
        for ev in usage_evidences:
            desc = (ev.get("description") or "").strip()
            if not desc:
                continue
            cols = ev.get("columns_or_tables") or []
            supports = (ev.get("supports_usage") or "").strip()
            page_content = f"Evidence: {desc}. Columns/tables: {', '.join(cols)}. Supports: {supports}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_evidences",
                    {
                        "evidence_type": ev.get("evidence_type", "usage"),
                        "evidence_description": desc,
                        "columns_or_tables": cols,
                        "supports_usage": supports,
                        "table_name": table_name,
                        "category": category,
                        "product_name": product_name,
                    },
                )
            )
        # Table-level: key_relationships as evidence context
        for rel in meta.get("key_relationships", []):
            if not (rel and str(rel).strip()):
                continue
            page_content = f"Evidence/context: {rel}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_evidences",
                    {
                        "evidence_description": str(rel).strip(),
                        "table_name": table_name,
                        "category": category,
                        "product_name": product_name,
                    },
                )
            )
        # Column-level: time_concepts as evidence of time dimension
        for tc in meta.get("time_concepts", []):
            col = tc.get("column_name", "")
            if not col or not tc.get("is_time_dimension"):
                continue
            page_content = f"Evidence: time dimension column {col} (granularity: {tc.get('time_granularity') or 'unknown'}). Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_evidences",
                    {
                        "evidence_type": "time_dimension",
                        "column_name": col,
                        "table_name": table_name,
                        "category": category,
                        "time_granularity": tc.get("time_granularity"),
                        "product_name": product_name,
                    },
                )
            )
        # Features as evidence of what can be computed
        for feat in meta.get("features", []):
            name = feat.get("feature_name", "").strip()
            if not name:
                continue
            page_content = f"Evidence: feature {name}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_evidences",
                    {
                        "evidence_type": "feature",
                        "feature_name": name,
                        "table_name": table_name,
                        "category": category,
                        "product_name": product_name,
                    },
                )
            )
    return docs


def build_mdl_fields(
    enriched_list: List[Dict[str, Any]],
    mdl_data: Dict[str, Any],
    product_name: str,
) -> List[Dict[str, Any]]:
    """Build mdl_fields: each column as a field with table_name, column_name, type, description, category."""
    docs = []
    meta_by_table = {item.get("table", ""): item.get("metadata", {}) for item in enriched_list if item.get("table")}
    for model in mdl_data.get("models", []):
        table_name = model.get("name", "")
        if not table_name:
            continue
        meta = meta_by_table.get(table_name, {})
        category = meta.get("category", "other")
        if category not in ALLOWED_CATEGORIES:
            category = "other"
        for col in model.get("columns", []):
            if col.get("isHidden"):
                continue
            col_name = col.get("name", "")
            col_type = col.get("type", "")
            desc = (col.get("description") or "").strip()
            page_content = f"Field: {col_name}. Type: {col_type}. Description: {desc}. Table: {table_name}. Category: {category}. Product: {product_name}."
            docs.append(
                _doc_record(
                    page_content,
                    "mdl_fields",
                    {
                        "column_name": col_name,
                        "table_name": table_name,
                        "type": col_type,
                        "description": desc,
                        "category": category,
                        "product_name": product_name,
                    },
                )
            )
    return docs


def build_mdl_metrics(
    enriched_list: List[Dict[str, Any]],
    product_name: str,
    usage_specifics_by_table: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build mdl_metrics: from LLM usage metrics if provided, else from enriched metadata metrics."""
    docs = []
    usage_specifics_by_table = usage_specifics_by_table or {}
    for item in enriched_list:
        table_name = item.get("table", "")
        meta = item.get("metadata", {})
        if not table_name or not meta:
            continue
        category = meta.get("category", "other")
        if category not in ALLOWED_CATEGORIES:
            category = "other"
        usage = usage_specifics_by_table.get(table_name, {})
        usage_metrics = usage.get("usage_metrics") or []
        if usage_metrics:
            for m in usage_metrics:
                name = (m.get("metric_name") or "").strip()
                if not name:
                    continue
                desc = (m.get("description") or "").strip()
                calc = (m.get("calculation") or "").strip()
                metric_cat = (m.get("category") or "operational").strip()
                cols = m.get("columns_used") or []
                dep_ctx = (m.get("dependency_context") or "").strip()
                page_content = f"Metric: {name}. Description: {desc}. Calculation: {calc}. Columns: {', '.join(cols)}. Dependency: {dep_ctx}. Table: {table_name}. Category: {category}. Metric category: {metric_cat}. Product: {product_name}."
                docs.append(
                    _doc_record(
                        page_content,
                        "mdl_metrics",
                        {
                            "metric_name": name,
                            "table_name": table_name,
                            "category": category,
                            "metric_category": metric_cat,
                            "columns_used": cols,
                            "dependency_context": dep_ctx,
                            "product_name": product_name,
                        },
                    )
                )
        if not usage_metrics:
            for m in meta.get("metrics", []):
                name = (m.get("metric_name") or "").strip()
                if not name:
                    continue
                desc = (m.get("description") or "").strip()
                calc = (m.get("calculation") or "").strip()
                metric_cat = (m.get("category") or "").strip()
                page_content = f"Metric: {name}. Description: {desc}. Calculation: {calc}. Table: {table_name}. Category: {category}. Metric category: {metric_cat}. Product: {product_name}."
                docs.append(
                    _doc_record(
                        page_content,
                        "mdl_metrics",
                        {
                            "metric_name": name,
                            "table_name": table_name,
                            "category": category,
                            "metric_category": metric_cat,
                            "product_name": product_name,
                        },
                    )
                )
    return docs


def build_mdl_edges_table(product_name: str) -> List[Dict[str, Any]]:
    """Build mdl_edges_table: contextual edge types for tables (for query fixing). Category-mapped."""
    # Edge types: when user asks about X (keywords), search these content_types
    edge_defs = [
        {
            "edge_id": "T1_table_to_concepts",
            "keywords": ["concept", "insight", "purpose", "use case", "overview", "what is"],
            "content_types": ["table_descriptions", "mdl_key_concepts"],
            "links_to_table_descriptions": True,
            "links_to_mdl_key_concepts": True,
        },
        {
            "edge_id": "T2_table_to_metrics",
            "keywords": ["metric", "kpi", "measure", "count", "aggregate", "performance", "security", "compliance"],
            "content_types": ["mdl_metrics", "table_descriptions"],
            "links_to_mdl_metrics": True,
            "links_to_table_descriptions": True,
        },
        {
            "edge_id": "T3_table_to_patterns",
            "keywords": ["query", "example", "how to", "sql", "question"],
            "content_types": ["mdl_patterns", "table_descriptions"],
            "links_to_mdl_patterns": True,
            "links_to_table_descriptions": True,
        },
        {
            "edge_id": "T4_table_to_evidences",
            "keywords": ["evidence", "support", "relationship", "join", "link"],
            "content_types": ["mdl_evidences", "mdl_fields"],
            "links_to_mdl_evidences": True,
            "links_to_mdl_fields": True,
        },
    ]
    docs = []
    for e in edge_defs:
        keywords_str = ", ".join(e["keywords"])
        content_str = ", ".join(e["content_types"])
        page_content = f"Edge type: {e['edge_id']}. Keywords: {keywords_str}. Use to rephrase the question and search these document types: {content_str}. Product: {product_name}. Use categories to map to tables."
        docs.append(
            _doc_record(
                page_content,
                "mdl_edges_table",
                {
                    "edge_id": e["edge_id"],
                    "keywords": e["keywords"],
                    "content_types": e["content_types"],
                    "product_name": product_name,
                },
            )
        )
    return docs


def build_mdl_edges_column(product_name: str) -> List[Dict[str, Any]]:
    """Build mdl_edges_column: contextual edge types for columns (for query fixing)."""
    edge_defs = [
        {
            "edge_id": "C1_column_to_concepts",
            "keywords": ["column", "field", "concept", "meaning", "what does"],
            "content_types": ["mdl_key_concepts", "mdl_fields", "column_definitions"],
            "links_to_mdl_key_concepts": True,
            "links_to_mdl_fields": True,
            "links_to_column_definitions": True,
        },
        {
            "edge_id": "C2_column_to_evidences",
            "keywords": ["evidence", "time dimension", "granularity", "filter", "group by"],
            "content_types": ["mdl_evidences", "mdl_fields"],
            "links_to_mdl_evidences": True,
            "links_to_mdl_fields": True,
        },
    ]
    docs = []
    for e in edge_defs:
        keywords_str = ", ".join(e["keywords"])
        content_str = ", ".join(e["content_types"])
        page_content = f"Edge type: {e['edge_id']}. Keywords: {keywords_str}. Use to rephrase the question and search these document types: {content_str}. Product: {product_name}. Use categories to map to columns."
        docs.append(
            _doc_record(
                page_content,
                "mdl_edges_column",
                {
                    "edge_id": e["edge_id"],
                    "keywords": e["keywords"],
                    "content_types": e["content_types"],
                    "product_name": product_name,
                },
            )
        )
    return docs


def _serialize_usage_output(out: Any) -> Dict[str, Any]:
    """Convert UsageExtractionOutput to dict for usage_specifics_by_table."""
    if out is None:
        return {}
    if hasattr(out, "model_dump"):
        d = out.model_dump()
    elif hasattr(out, "dict"):
        d = out.dict()
    else:
        d = dict(out) if isinstance(out, dict) else {}
    return {
        "usage_metrics": d.get("usage_metrics", []),
        "usage_evidences": d.get("usage_evidences", []),
        "usage_patterns": d.get("usage_patterns", []),
    }


# ---------------------------------------------------------------------------
# Checkpointing for batched LLM extraction (resume from where you left off)
# ---------------------------------------------------------------------------

CHECKPOINT_VERSION = 1


def _checkpoint_path(checkpoint_dir: Path, product_name: str) -> Path:
    """Path to checkpoint JSON for this product."""
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    safe_name = product_name.replace(" ", "_").strip() or "default"
    return checkpoint_dir / f"mdl_usage_checkpoint_{safe_name}.json"


def load_checkpoint(checkpoint_dir: Optional[Path], product_name: str) -> Dict[str, Dict[str, Any]]:
    """Load usage_specifics_by_table from checkpoint if present."""
    if not checkpoint_dir:
        return {}
    path = _checkpoint_path(checkpoint_dir, product_name)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != CHECKPOINT_VERSION:
            return {}
        return data.get("usage_specifics_by_table") or {}
    except Exception as e:
        logger.warning("Could not load checkpoint from %s: %s", path, e)
        return {}


def save_checkpoint(
    checkpoint_dir: Path,
    product_name: str,
    usage_specifics_by_table: Dict[str, Dict[str, Any]],
) -> None:
    """Write checkpoint JSON."""
    path = _checkpoint_path(checkpoint_dir, product_name)
    payload = {
        "version": CHECKPOINT_VERSION,
        "product_name": product_name,
        "usage_specifics_by_table": usage_specifics_by_table,
        "completed_tables": list(usage_specifics_by_table.keys()),
        "last_updated": datetime.utcnow().isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=0, ensure_ascii=False)
    logger.info("  Checkpoint saved: %s tables -> %s", len(usage_specifics_by_table), path.name)


async def _run_with_llm(
    enriched_path: Path,
    mdl_path: Path,
    enriched_list: List[Dict[str, Any]],
    mdl_data: Dict[str, Any],
    product_name: str,
    batch_size: int = 25,
    checkpoint_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Run LLM usage extraction per table in batches; checkpoint after each batch. Resume from checkpoint if present."""
    if not _LLM_AVAILABLE or get_llm is None:
        logger.warning("LLM not available; skipping usage extraction. Install langchain and set get_llm.")
        return {}
    llm = get_llm()
    relationships_map: Dict[str, List[str]] = {}
    for rel in mdl_data.get("relationships", []):
        models = rel.get("models", [])
        if len(models) >= 2:
            a, b = models[0], models[1]
            desc = f"{a} -> {b} ({rel.get('joinType', 'UNKNOWN')})"
            relationships_map.setdefault(a, []).append(desc)
            relationships_map.setdefault(b, []).append(desc)
    models_by_name = {m["name"]: m for m in mdl_data.get("models", [])}

    # Load existing checkpoint so we can resume
    usage_specifics_by_table: Dict[str, Dict[str, Any]] = load_checkpoint(checkpoint_dir, product_name)
    completed = set(usage_specifics_by_table.keys())
    if completed:
        logger.info("Resuming: %s tables already in checkpoint, skipping those.", len(completed))

    # Build list of (index, item) for tables not yet done
    todo: List[tuple] = []
    for idx, item in enumerate(enriched_list):
        table_name = item.get("table", "")
        meta = item.get("metadata", {})
        if not table_name or not meta:
            continue
        if table_name in completed:
            continue
        todo.append((idx, item))

    total_tables = len(completed) + len(todo)
    logger.info("LLM usage extraction: %s done, %s remaining (batch_size=%s).", len(completed), len(todo), batch_size)

    done_this_run = 0
    for batch_start in range(0, len(todo), batch_size):
        batch = todo[batch_start : batch_start + batch_size]
        for idx, item in batch:
            table_name = item.get("table", "")
            meta = item.get("metadata", {})
            model = models_by_name.get(table_name, {})
            columns = model.get("columns", [])
            relationships = relationships_map.get(table_name, [])
            category = meta.get("category", "other")
            if category not in ALLOWED_CATEGORIES:
                category = "other"
            done_this_run += 1
            logger.info("[%s/%s] LLM usage extraction for %s...", len(completed) + done_this_run, total_tables, table_name)
            try:
                out = await extract_usage_specifics_llm(
                    table_name=table_name,
                    table_description=model.get("description", ""),
                    columns=columns,
                    relationships=relationships,
                    category=category,
                    product_name=product_name,
                    llm=llm,
                )
                usage_specifics_by_table[table_name] = _serialize_usage_output(out)
                logger.info(
                    "  ✓ %s: %s metrics, %s evidences, %s patterns",
                    table_name,
                    len(usage_specifics_by_table[table_name].get("usage_metrics", [])),
                    len(usage_specifics_by_table[table_name].get("usage_evidences", [])),
                    len(usage_specifics_by_table[table_name].get("usage_patterns", [])),
                )
            except Exception as e:
                logger.warning("  ✗ %s: %s", table_name, e)
        if checkpoint_dir and usage_specifics_by_table:
            save_checkpoint(checkpoint_dir, product_name, usage_specifics_by_table)

    return usage_specifics_by_table


def run(
    enriched_file: str,
    mdl_file: str,
    product_name: str,
    preview_dir: Optional[str] = None,
    use_llm: bool = False,
    batch_size: int = 25,
    checkpoint_dir: Optional[str] = None,
    mdl_only: bool = False,
    category_enrichment_file: Optional[str] = None,
) -> Path:
    """Load enriched + MDL, optionally run LLM usage extraction (batched, with checkpoint), build mdl_docs preview files."""
    enriched_path = Path(enriched_file)
    mdl_path = Path(mdl_file)
    if not enriched_path.exists():
        raise FileNotFoundError(f"Enriched file not found: {enriched_path}")
    if not mdl_path.exists():
        raise FileNotFoundError(f"MDL file not found: {mdl_path}")

    preview_path = Path(preview_dir or "indexing_preview") / "mdl_docs"
    preview_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    checkpoint_path: Optional[Path] = None
    if checkpoint_dir is not None:
        checkpoint_path = Path(checkpoint_dir)
    elif use_llm:
        checkpoint_path = preview_path / "checkpoints"

    logger.info("Loading enriched metadata and MDL...")
    enriched_list = _load_enriched(enriched_path)
    mdl_data = _load_mdl(mdl_path)
    logger.info(f"Loaded {len(enriched_list)} tables, MDL has {len(mdl_data.get('models', []))} models")

    usage_specifics_by_table: Dict[str, Dict[str, Any]] = {}
    if use_llm:
        logger.info("Running LLM usage extraction (batch_size=%s, checkpoint=%s)...", batch_size, checkpoint_path)
        usage_specifics_by_table = asyncio.run(
            _run_with_llm(
                enriched_path,
                mdl_path,
                enriched_list,
                mdl_data,
                product_name,
                batch_size=batch_size,
                checkpoint_dir=checkpoint_path,
            )
        )
        logger.info("Usage extraction done for %s tables.", len(usage_specifics_by_table))

    # Category enrichment: control examples, evidence examples, frameworks (NIST, ISO, SOC2, etc.) per category
    category_enrichment_path: Optional[Path] = None
    if category_enrichment_file:
        category_enrichment_path = Path(category_enrichment_file)
    else:
        default_ce = (preview_path.parent if preview_path else Path(preview_dir or "indexing_preview")) / "mdl_enriched" / "category_enrichment.json"
        if default_ce.exists():
            category_enrichment_path = default_ce
    category_enrichment_data = _load_category_enrichment(category_enrichment_path) if category_enrichment_path else None

    if mdl_only:
        builders = [
            ("mdl_patterns", lambda: build_mdl_patterns(enriched_list, product_name, usage_specifics_by_table)),
            ("mdl_evidences", lambda: build_mdl_evidences(enriched_list, mdl_data, product_name, usage_specifics_by_table)),
            ("mdl_metrics", lambda: build_mdl_metrics(enriched_list, product_name, usage_specifics_by_table)),
        ]
    else:
        builders = [
            ("mdl_key_concepts", lambda: build_mdl_key_concepts(enriched_list, mdl_data, product_name)),
            ("mdl_patterns", lambda: build_mdl_patterns(enriched_list, product_name, usage_specifics_by_table)),
            ("mdl_evidences", lambda: build_mdl_evidences(enriched_list, mdl_data, product_name, usage_specifics_by_table)),
            ("mdl_fields", lambda: build_mdl_fields(enriched_list, mdl_data, product_name)),
            ("mdl_metrics", lambda: build_mdl_metrics(enriched_list, product_name, usage_specifics_by_table)),
            ("mdl_edges_table", lambda: build_mdl_edges_table(product_name)),
            ("mdl_edges_column", lambda: build_mdl_edges_column(product_name)),
        ]
    if category_enrichment_data:
        builders.append(("mdl_category_enrichment", lambda: build_mdl_category_enrichment(category_enrichment_data, product_name)))

    for name, builder in builders:
        docs = builder()
        filename = f"{name}_{timestamp}_{product_name}.json"
        filepath = preview_path / filename
        payload = {
            "metadata": {
                "content_type": name,
                "product_name": product_name,
                "document_count": len(docs),
                "timestamp": timestamp,
                "indexed_at": datetime.utcnow().isoformat(),
                "source_enriched_file": str(enriched_path),
                "source_mdl_file": str(mdl_path),
                "usage_llm": use_llm,
            },
            "documents": docs,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info(f"  ✓ Wrote {len(docs)} docs to {filepath.name}")

    return preview_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate MDL contextual preview files (concepts, patterns, evidences, fields, metrics, edges)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--enriched-file", required=True, help="Path to enriched_metadata_*_ProductName.json")
    parser.add_argument("--mdl-file", required=True, help="Path to MDL JSON file")
    parser.add_argument("--product-name", required=True, help="Product name (e.g. Snyk)")
    parser.add_argument("--preview-dir", default="indexing_preview", help="Preview root directory")
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Call LLM per table to extract usage-specific metrics, evidences, patterns using dependencies, architecture, and provider context",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of tables to process per batch before saving checkpoint (default: 25). Use with --use-llm for 400+ tables.",
    )
    parser.add_argument(
        "--checkpoint-dir",
        default=None,
        help="Directory for checkpoint JSON (default: preview_dir/mdl_docs/checkpoints when --use-llm). Enables resume from where you left off.",
    )
    parser.add_argument(
        "--mdl-only",
        action="store_true",
        help="Only write MDL usage outputs: mdl_metrics, mdl_evidences, mdl_patterns. Skip key_concepts, fields, edges. Use with --use-llm.",
    )
    parser.add_argument(
        "--category-enrichment-file",
        help="Path to category_enrichment.json (control/evidence/framework examples per category). Default: preview_dir/../mdl_enriched/category_enrichment.json",
    )
    args = parser.parse_args()
    run(
        enriched_file=args.enriched_file,
        mdl_file=args.mdl_file,
        product_name=args.product_name,
        preview_dir=args.preview_dir,
        use_llm=args.use_llm,
        batch_size=args.batch_size,
        checkpoint_dir=args.checkpoint_dir,
        mdl_only=args.mdl_only,
        category_enrichment_file=args.category_enrichment_file,
    )
    logger.info("Done.")


if __name__ == "__main__":
    main()
