"""
Enhanced MDL Indexing Script with Consolidated LLM Extraction
===============================================================

This script indexes MDL files with enriched metadata extracted in ONE LLM call per table.
It extracts: category, business purpose, examples, features, metrics, instructions, and time concepts.

All extraction happens in a single pass to minimize LLM calls and cost.

Usage:
    python -m indexing_cli.index_mdl_enriched \
        --mdl-file path/to/mdl.json \
        --project-id "Snyk" \
        --product-name "Snyk" \
        --preview  # Optional: save preview files

Output Collections:
    - table_descriptions: Tables with category_name in metadata
    - column_metadata: Columns with time_dimension fields merged in
    - sql_pairs: Examples (natural question → SQL)
    - instructions: Product-specific instructions
    - entities: Products, categories, features, metrics (with mdl_entity_type discriminator)
    - contextual_edges: All relationships between entities
"""

import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.dependencies import (
    get_chromadb_client,
    get_embeddings_model,
    get_doc_store_provider,
    get_llm,
    get_vector_store_client,
)
from app.storage.documents import ChromaDBEmbeddingFunction, DocumentChromaStore
from app.services.contextual_graph_storage import ContextualEdge, ContextualGraphStorage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for LLM Output
# ============================================================================

class TimeConceptInfo(BaseModel):
    """Time dimension information for a column."""
    column_name: str
    is_time_dimension: bool = False
    time_granularity: Optional[str] = None  # "day", "hour", "month", etc.
    is_event_time: bool = False
    is_process_time: bool = False
    description: str = ""


class ExampleQuery(BaseModel):
    """Natural language query mapped to SQL."""
    natural_question: str
    sql_query: str
    complexity: str  # "simple", "moderate", "complex"
    description: str = ""


class Feature(BaseModel):
    """Business feature that can be computed from this table."""
    feature_name: str
    description: str
    calculation_logic: str
    use_cases: List[str] = []


class Metric(BaseModel):
    """Key metric or KPI related to this table."""
    metric_name: str
    description: str
    calculation: str
    category: str  # "performance", "security", "compliance", etc.


class Instruction(BaseModel):
    """Product-specific instruction or best practice."""
    instruction_type: str  # "query_pattern", "best_practice", "constraint", etc.
    content: str
    priority: str = "normal"  # "high", "normal", "low"


class EnrichedTableMetadata(BaseModel):
    """Complete metadata extracted for a table in ONE LLM call."""
    
    # Core identification
    table_name: str
    category: str  # Which of the 15 categories
    business_purpose: str  # Natural language description
    
    # Semantic enrichment
    key_insights: List[str] = Field(default_factory=list)
    common_use_cases: List[str] = Field(default_factory=list)
    
    # Time concepts (merged into column metadata)
    time_concepts: List[TimeConceptInfo] = Field(default_factory=list)
    
    # Examples
    example_queries: List[ExampleQuery] = Field(default_factory=list, max_length=3)
    
    # Features
    features: List[Feature] = Field(default_factory=list, max_length=5)
    
    # Metrics
    metrics: List[Metric] = Field(default_factory=list, max_length=5)
    
    # Instructions
    instructions: List[Instruction] = Field(default_factory=list, max_length=3)
    
    # Relationships context (extracted from MDL relationships)
    key_relationships: List[str] = Field(default_factory=list)


# ============================================================================
# Category Mapping (from index_mdl_contextual.py)
# ============================================================================

CATEGORY_MAPPING = {
    "AccessRequest": "access requests",
    "App": "application data",
    "Asset": "assets",
    "Project": "projects",
    "Risk": "risk management",
    "Integration": "integrations",
    "BrokerConnection": "integrations",
    "Vulnerability": "vulnerabilities",
    "Finding": "vulnerabilities",
    "Config": "configuration",
    "Settings": "configuration",
    "Audit": "audit logs",
    "Log": "audit logs",
    "Catalog": "audit logs",
    "Deploy": "deployment",
    "Group": "groups",
    "Org": "organizations",
    "Organization": "organizations",
    "Membership": "memberships and roles",
    "Role": "memberships and roles",
    "Member": "memberships and roles",
    "Issue": "issues",
    "Artifact": "artifacts",
}


def categorize_table(table_name: str) -> str:
    """Categorize a table based on its name pattern."""
    for prefix, category in CATEGORY_MAPPING.items():
        if table_name.startswith(prefix):
            return category
    return "other"  # fallback


# ============================================================================
# LLM Extraction Prompt
# ============================================================================

EXTRACTION_PROMPT_TEMPLATE = """You are a data expert analyzing a database table for {product_name}.

Extract comprehensive metadata for this table in ONE response. Focus on practical, actionable information.

**Table Information:**
- Name: {table_name}
- Description: {table_description}
- Columns: {columns_info}
- Relationships: {relationships_info}

**Categories** (choose ONE that best fits):
{categories_list}

**Extract the following:**

1. **Category**: Which category above best describes this table?

2. **Business Purpose**: In 1-2 sentences, what business problem does this table help solve?

3. **Key Insights**: 2-3 important things to know about this table

4. **Common Use Cases**: 2-3 common ways this table is used

5. **Time Concepts**: Identify any time-related columns:
   - Column name
   - Is it a time dimension? (yes/no)
   - Time granularity (day, hour, month, year, etc.)
   - Is it event time or process time?
   - Brief description

6. **Example Queries**: Generate 2-3 realistic SQL query examples:
   - Natural language question
   - Corresponding SQL query
   - Complexity (simple/moderate/complex)

7. **Features**: Identify 2-5 business features that can be computed:
   - Feature name
   - Description
   - How to calculate it
   - Use cases

8. **Metrics**: Identify 2-5 key metrics or KPIs:
   - Metric name
   - Description
   - How to calculate
   - Category (performance/security/compliance/operational)

9. **Instructions**: 1-3 important instructions or best practices:
   - Type (query_pattern/best_practice/constraint)
   - Content
   - Priority (high/normal/low)

10. **Key Relationships**: Summarize important relationships (already provided, just confirm relevance)

Be concise and practical. Focus on information that helps users query and understand this table.

Return ONLY a single valid JSON object. Do not wrap in markdown code blocks (no ```json or ```). No explanatory text before or after the JSON.

{format_instructions}
"""


def _repair_json_unescaped_quotes(s: str) -> str:
    """Escape double-quotes that appear inside JSON string values (e.g. SQL with '{\"key\":\"val\"}')."""
    out = []
    i = 0
    n = len(s)
    in_string = False
    while i < n:
        c = s[i]
        if not in_string:
            if c == '"':
                in_string = True
                out.append(c)
            else:
                out.append(c)
            i += 1
            continue
        # We're inside a double-quoted string value
        if c == "\\":
            out.append(c)
            i += 1
            if i < n:
                out.append(s[i])
                i += 1
            continue
        if c == '"':
            # Unescaped quote: could be end of string or broken inner quote (e.g. SQL '{"key": "val"}').
            # If next non-space char is : or , or } or ], this is likely the closing quote.
            j = i + 1
            while j < n and s[j] in " \t\n\r":
                j += 1
            if j < n and s[j] in ":,}]":
                out.append(c)
                in_string = False
                i += 1
                continue
            # Otherwise treat as inner quote and escape it
            out.append("\\")
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _extract_json_from_llm_response(text: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from LLM response, stripping markdown code blocks if present."""
    if not text or not text.strip():
        return None
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    if "```" in text:
        start = text.find("```")
        if start != -1:
            rest = text[start + 3:]
            if rest.lstrip().lower().startswith("json"):
                rest = rest.lstrip()[4:].lstrip()
            end = rest.find("```")
            if end != -1:
                text = rest[:end].strip()
            else:
                text = rest.strip()
    # Find first { and last }
    start_brace = text.find("{")
    if start_brace == -1:
        return None
    end_brace = text.rfind("}")
    if end_brace == -1 or end_brace <= start_brace:
        return None
    json_str = text[start_brace : end_brace + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    # Try repairing unescaped quotes inside string values (common in sql_query with '{"key":"val"}').
    try:
        repaired = _repair_json_unescaped_quotes(json_str)
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def _dict_to_enriched_metadata(
    data: Dict[str, Any],
    table_name: str,
    table_description: str,
    relationships: List[str],
) -> EnrichedTableMetadata:
    """Build EnrichedTableMetadata from a dict with coercion and defaults for LLM output."""
    # Ensure required scalars
    category = (data.get("category") or "").strip() or categorize_table(table_name)
    business_purpose = (data.get("business_purpose") or "").strip() or table_description or f"Table for {table_name} data"
    # Ensure lists and trim to max lengths
    def _list(val: Any, max_len: Optional[int] = None) -> List[Any]:
        if val is None:
            return []
        if isinstance(val, list):
            out = list(val)
            if max_len is not None:
                out = out[:max_len]
            return out
        return []

    def _str_list(val: Any, max_len: Optional[int] = None) -> List[str]:
        return [str(x).strip() for x in _list(val, max_len) if str(x).strip()]

    key_insights = _str_list(data.get("key_insights"))
    common_use_cases = _str_list(data.get("common_use_cases"))
    key_relationships = _str_list(data.get("key_relationships")) or relationships

    # Nested models: accept dicts and coerce to model or skip invalid items
    time_concepts: List[TimeConceptInfo] = []
    for item in _list(data.get("time_concepts")):
        if isinstance(item, dict) and item.get("column_name") is not None:
            try:
                time_concepts.append(TimeConceptInfo(
                    column_name=str(item.get("column_name", "")),
                    is_time_dimension=bool(item.get("is_time_dimension", False)),
                    time_granularity=item.get("time_granularity"),
                    is_event_time=bool(item.get("is_event_time", False)),
                    is_process_time=bool(item.get("is_process_time", False)),
                    description=str(item.get("description", ""))[:500],
                ))
            except Exception:
                pass

    example_queries_list: List[ExampleQuery] = []
    for item in _list(data.get("example_queries"), 3):
        if isinstance(item, dict) and item.get("natural_question") and item.get("sql_query"):
            try:
                example_queries_list.append(ExampleQuery(
                    natural_question=str(item["natural_question"])[:500],
                    sql_query=str(item["sql_query"])[:2000],
                    complexity=str(item.get("complexity", "simple"))[:20] or "simple",
                    description=str(item.get("description", ""))[:300],
                ))
            except Exception:
                pass

    features_list: List[Feature] = []
    for item in _list(data.get("features"), 5):
        if isinstance(item, dict) and item.get("feature_name"):
            try:
                features_list.append(Feature(
                    feature_name=str(item["feature_name"])[:200],
                    description=str(item.get("description", ""))[:500],
                    calculation_logic=str(item.get("calculation_logic", ""))[:500],
                    use_cases=_str_list(item.get("use_cases"), 5),
                ))
            except Exception:
                pass

    metrics_list: List[Metric] = []
    for item in _list(data.get("metrics"), 5):
        if isinstance(item, dict) and item.get("metric_name"):
            try:
                metrics_list.append(Metric(
                    metric_name=str(item["metric_name"])[:200],
                    description=str(item.get("description", ""))[:500],
                    calculation=str(item.get("calculation", ""))[:500],
                    category=str(item.get("category", "operational"))[:50],
                ))
            except Exception:
                pass

    instructions_list: List[Instruction] = []
    for item in _list(data.get("instructions"), 3):
        if isinstance(item, dict) and item.get("content"):
            try:
                instructions_list.append(Instruction(
                    instruction_type=str(item.get("instruction_type", "best_practice"))[:50],
                    content=str(item["content"])[:1000],
                    priority=str(item.get("priority", "normal"))[:20] or "normal",
                ))
            except Exception:
                pass

    return EnrichedTableMetadata(
        table_name=table_name,
        category=category,
        business_purpose=business_purpose,
        key_insights=key_insights,
        common_use_cases=common_use_cases,
        time_concepts=time_concepts,
        example_queries=example_queries_list,
        features=features_list,
        metrics=metrics_list,
        instructions=instructions_list,
        key_relationships=key_relationships,
    )


def _build_contextual_edges(
    mdl_data: Dict[str, Any],
    enriched_tables: List[Dict[str, Any]],
    project_id: str,
    product_name: str,
) -> List[ContextualEdge]:
    """
    Build ContextualEdge list from MDL relationships and enriched key_relationships.
    Deduplicates by (source_entity_id, target_entity_id, edge_type).
    """
    context_id = f"mdl_{project_id}"
    entity_type = "table"
    seen: set = set()
    edges: List[ContextualEdge] = []

    # 1) From MDL relationships
    for idx, rel in enumerate(mdl_data.get("relationships", [])):
        models = rel.get("models", [])
        if len(models) < 2:
            continue
        source, target = models[0], models[1]
        join_type = (rel.get("joinType") or "REFERENCES").strip()
        key = (source, target, join_type)
        if key in seen:
            continue
        seen.add(key)
        edge_id = f"mdl_{project_id}_{source}_{target}_{join_type}_{idx}"
        doc = f"Table {source} relates to {target} via {join_type}. Product: {product_name}."
        edges.append(
            ContextualEdge(
                edge_id=edge_id,
                document=doc,
                source_entity_id=source,
                source_entity_type=entity_type,
                target_entity_id=target,
                target_entity_type=entity_type,
                edge_type=join_type,
                context_id=context_id,
            )
        )

    # 2) From enriched key_relationships (e.g. "SourceTable -> TargetTable (role)" or "X -> Y")
    for item in enriched_tables:
        model = item.get("model") or {}
        metadata = item.get("metadata")
        if metadata is None:
            continue
        key_rels = getattr(metadata, "key_relationships", None) or []
        table_name = model.get("name", "")
        for rel_str in key_rels:
            if "->" not in rel_str:
                continue
            parts = [p.strip() for p in rel_str.split("->", 1)]
            if len(parts) != 2:
                continue
            source, right = parts[0], parts[1]
            target = right.split("(")[0].strip() if "(" in right else right.strip()
            if not source or not target:
                continue
            edge_type = "RELATES_TO"
            key = (source, target, edge_type)
            if key in seen:
                continue
            seen.add(key)
            edge_id = f"mdl_{project_id}_kr_{source}_{target}_{len(edges)}"
            edges.append(
                ContextualEdge(
                    edge_id=edge_id,
                    document=rel_str,
                    source_entity_id=source,
                    source_entity_type=entity_type,
                    target_entity_id=target,
                    target_entity_type=entity_type,
                    edge_type=edge_type,
                    context_id=context_id,
                )
            )

    return edges


# ============================================================================
# Main Indexing Logic
# ============================================================================

async def extract_enriched_metadata(
    table_name: str,
    table_description: str,
    columns: List[Dict[str, Any]],
    relationships: List[str],
    product_name: str,
    llm: Any
) -> EnrichedTableMetadata:
    """
    Extract all metadata for a table in ONE LLM call.
    
    Args:
        table_name: Name of the table
        table_description: Table description from MDL
        columns: List of column dictionaries
        relationships: List of relationship descriptions
        product_name: Product name (e.g., "Snyk")
        llm: LLM instance
    
    Returns:
        EnrichedTableMetadata with all extracted information
    """
    # Format columns info
    columns_str = "\n".join([
        f"  - {col['name']} ({col.get('type', 'unknown')}): {col.get('description', 'No description')}"
        for col in columns[:20]  # Limit to first 20 columns to fit in context
    ])
    if len(columns) > 20:
        columns_str += f"\n  ... and {len(columns) - 20} more columns"
    
    # Format relationships
    relationships_str = "\n".join([f"  - {rel}" for rel in relationships]) if relationships else "  No explicit relationships defined"
    
    # Categories list
    categories_list = """
- access requests: User access and permission requests
- application data: Application configurations and metadata (exclude AppRisk)
- assets: Asset inventory and tracking
- projects: Project/repository information
- risk management: Risk assessment and management
- integrations: Third-party integrations and connectors
- vulnerabilities: Security vulnerabilities and findings
- configuration: System configuration and settings
- audit logs: Audit trails and logging
- deployment: Deployment and release information
- groups: User groups and teams
- organizations: Organization hierarchy
- memberships and roles: User memberships and role assignments
- issues: Issue tracking and management
- artifacts: Build artifacts and packages
- other: Anything else
"""
    
    # Create prompt and parser
    parser = JsonOutputParser(pydantic_object=EnrichedTableMetadata)
    prompt = ChatPromptTemplate.from_template(EXTRACTION_PROMPT_TEMPLATE)
    format_instructions = parser.get_format_instructions()
    invoke_vars = {
        "product_name": product_name,
        "table_name": table_name,
        "table_description": table_description or "No description provided",
        "columns_info": columns_str,
        "relationships_info": relationships_str,
        "categories_list": categories_list,
        "format_instructions": format_instructions,
    }

    try:
        # First try: LLM -> JsonOutputParser
        chain = prompt | llm | parser
        result = await chain.ainvoke(invoke_vars)
        return EnrichedTableMetadata(**result)
    except Exception as e1:
        logger.debug(f"LLM parse failed for {table_name}: {e1}. Trying raw JSON extraction.")
        try:
            # Second try: get raw LLM output, extract JSON, coerce into model
            chain_raw = prompt | llm
            raw_msg = await chain_raw.ainvoke(invoke_vars)
            text = raw_msg.content if hasattr(raw_msg, "content") else str(raw_msg)
            data = _extract_json_from_llm_response(text)
            if data:
                return _dict_to_enriched_metadata(data, table_name, table_description or "", relationships)
        except Exception as e2:
            logger.debug(f"Raw JSON extraction failed for {table_name}: {e2}")
        logger.warning(f"LLM extraction failed for {table_name}: {e1}. Using fallback.")
        return EnrichedTableMetadata(
            table_name=table_name,
            category=categorize_table(table_name),
            business_purpose=table_description or f"Table for {table_name} data",
            key_insights=[],
            common_use_cases=[],
            time_concepts=[],
            example_queries=[],
            features=[],
            metrics=[],
            instructions=[],
            key_relationships=relationships,
        )


# Checkpointing for preview mode (resume across runs for 400+ tables)
_ENRICHED_CHECKPOINT_VERSION = 1


def _enriched_checkpoint_path(preview_path: Path, product_name: str) -> Path:
    safe = (product_name or "default").replace(" ", "_").strip()
    checkpoint_dir = preview_path / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"enriched_checkpoint_{safe}.json"


def _load_enriched_checkpoint(checkpoint_path: Path) -> List[Dict[str, Any]]:
    if not checkpoint_path.exists():
        return []
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != _ENRICHED_CHECKPOINT_VERSION:
            return []
        return data.get("enriched_list") or []
    except Exception as e:
        logger.warning("Could not load checkpoint %s: %s", checkpoint_path, e)
        return []


def _save_enriched_checkpoint(checkpoint_path: Path, product_name: str, enriched_list: List[Dict[str, Any]]) -> None:
    payload = {
        "version": _ENRICHED_CHECKPOINT_VERSION,
        "product_name": product_name,
        "enriched_list": enriched_list,
        "completed_tables": [e["table"] for e in enriched_list],
        "last_updated": datetime.utcnow().isoformat(),
    }
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=0, ensure_ascii=False)
    logger.info("  Checkpoint saved: %s tables -> %s", len(enriched_list), checkpoint_path.name)


def _load_enriched_metadata_json(path: Path) -> List[Dict[str, Any]]:
    """Load enriched metadata from a preview JSON (list of {table, metadata})."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "enriched_list" in data:
        return data["enriched_list"]
    raise ValueError(f"Expected list or dict with 'enriched_list'; got {type(data)}")


async def index_mdl_enriched(
    mdl_file_path: str,
    project_id: str,
    product_name: Optional[str] = None,
    domain: Optional[str] = None,
    preview: bool = False,
    preview_dir: Optional[str] = None,
    batch_size: int = 25,
    checkpoint_dir: Optional[str] = None,
    edges_only: bool = False,
    enriched_metadata_path: Optional[str] = None,
):
    """
    Index MDL file with enriched metadata extracted via ONE LLM call per table.
    With preview=True, supports batch_size and checkpointing to process 400+ tables and resume.
    With edges_only=True, only indexes contextual_edges (requires --enriched-metadata).
    
    Args:
        mdl_file_path: Path to MDL JSON file
        project_id: Project ID
        product_name: Product name (defaults to project_id)
        domain: Domain filter (optional)
        preview: Whether to save preview files
        preview_dir: Directory for preview files (defaults to indexing_preview)
        batch_size: Tables per batch when using checkpoint (default 25)
        checkpoint_dir: Directory for checkpoint (default: preview_dir/mdl_enriched/checkpoints)
        edges_only: If True, only index contextual_edges (skip LLM and other collections)
        enriched_metadata_path: Path to enriched metadata JSON (required when edges_only=True)
    """
    mdl_path = Path(mdl_file_path)
    if not mdl_path.exists():
        raise FileNotFoundError(f"MDL file not found: {mdl_file_path}")
    
    product_name = product_name or project_id
    
    if edges_only and not enriched_metadata_path:
        raise ValueError("--enriched-metadata is required when using --edges-only")
    
    logger.info("=" * 80)
    logger.info("MDL Enriched Indexing (Consolidated LLM Extraction)" if not edges_only else "MDL Enriched — Contextual edges only")
    logger.info("=" * 80)
    logger.info(f"MDL File: {mdl_file_path}")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Product Name: {product_name}")
    if edges_only:
        logger.info("Mode: edges-only (contextual_edges)")
        logger.info(f"Enriched metadata: {enriched_metadata_path}")
    else:
        logger.info(f"Preview Mode: {preview}")
        if preview:
            logger.info(f"Batch size: {batch_size}, Checkpointing: enabled")
    logger.info("")
    
    # Load MDL
    logger.info(f"Loading MDL file: {mdl_path}")
    with open(mdl_path, "r", encoding="utf-8") as f:
        mdl_data = json.load(f)
    
    all_models = mdl_data.get("models", [])
    logger.info(f"Loaded MDL with {len(all_models)} models")
    logger.info("")
    
    if edges_only:
        # Load enriched metadata from file and build enriched_tables
        meta_path = Path(enriched_metadata_path)
        if not meta_path.exists():
            raise FileNotFoundError(f"Enriched metadata file not found: {enriched_metadata_path}")
        enriched_list = _load_enriched_metadata_json(meta_path)
        logger.info(f"Loaded enriched metadata for {len(enriched_list)} tables from {enriched_metadata_path}")
        models_by_name = {m["name"]: m for m in all_models}
        enriched_tables = []
        for e in enriched_list:
            name = e.get("table", "")
            meta = e.get("metadata", e)
            if name in models_by_name:
                try:
                    meta_obj = EnrichedTableMetadata(**meta)
                except Exception:
                    meta_obj = EnrichedTableMetadata(
                        table_name=name,
                        category=meta.get("category", "other"),
                        business_purpose=meta.get("business_purpose", ""),
                        key_insights=meta.get("key_insights", []),
                        common_use_cases=meta.get("common_use_cases", []),
                        time_concepts=[],
                        example_queries=[],
                        features=[],
                        metrics=[],
                        instructions=[],
                        key_relationships=meta.get("key_relationships", []),
                    )
                enriched_tables.append({"model": models_by_name[name], "metadata": meta_obj})
        logger.info("")
        # Skip Phase 1 and 2.1–2.5; run only 2.6
        embeddings = get_embeddings_model()
        results = {}
        logger.info("=" * 80)
        logger.info("Indexing contextual edges only")
        logger.info("=" * 80)
    else:
        # Initialize dependencies (needed for Phase 2 when not preview-only)
        persistent_client = get_chromadb_client()
        embeddings = get_embeddings_model()
        doc_store_provider = get_doc_store_provider()
        llm = get_llm()
        
        # Build relationships map
        relationships_map = {}
        for rel in mdl_data.get("relationships", []):
            models = rel.get("models", [])
            if len(models) >= 2:
                source = models[0]
                target = models[1]
                rel_desc = f"{source} -> {target} ({rel.get('joinType', 'UNKNOWN')})"
                relationships_map.setdefault(source, []).append(rel_desc)
                relationships_map.setdefault(target, []).append(rel_desc)
        
        # Prepare preview directory and checkpoint
        preview_path = None
        checkpoint_path = None
        if preview:
            preview_path = Path(preview_dir or "indexing_preview") / "mdl_enriched"
            preview_path.mkdir(parents=True, exist_ok=True)
            ck_dir = Path(checkpoint_dir) if checkpoint_dir else preview_path / "checkpoints"
            ck_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_path = ck_dir / f"enriched_checkpoint_{(product_name or 'default').replace(' ', '_').strip()}.json"
        
        # ========================================================================
        # PHASE 1: Extract enriched metadata (ONE LLM call per table), with optional checkpointing
        # ========================================================================
        logger.info("=" * 80)
        logger.info("PHASE 1: Extracting Enriched Metadata (ONE LLM call per table)")
        logger.info("=" * 80)
        
        enriched_list: List[Dict[str, Any]] = []
        if preview and checkpoint_path is not None:
            enriched_list = _load_enriched_checkpoint(checkpoint_path)
            if enriched_list:
                completed = {e["table"] for e in enriched_list}
                logger.info("Resuming: %s tables already in checkpoint, skipping those.", len(completed))
        completed = {e["table"] for e in enriched_list}
        todo_models = [m for m in all_models if m.get("name") and m["name"] not in completed]
        total_tables = len(completed) + len(todo_models)
        
        processed_in_run = 0

        async def process_one(model: Dict[str, Any]):
            table_name = model.get("name", "")
            try:
                metadata = await extract_enriched_metadata(
                    table_name=table_name,
                    table_description=model.get("description", ""),
                    columns=model.get("columns", []),
                    relationships=relationships_map.get(table_name, []),
                    product_name=product_name,
                    llm=llm,
                )
                return (table_name, metadata, None)
            except Exception as e:
                return (table_name, None, e)

        for batch_start in range(0, len(todo_models), batch_size):
            batch = todo_models[batch_start : batch_start + batch_size]
            batch_names = [m.get("name", "") for m in batch]
            logger.info("Batch %s–%s: processing %s tables concurrently: %s", batch_start + 1, batch_start + len(batch), len(batch), ", ".join(batch_names[:5]) + ("..." if len(batch_names) > 5 else ""))
            results = await asyncio.gather(*(process_one(model) for model in batch), return_exceptions=False)
            for table_name, metadata, err in results:
                if err is not None:
                    logger.warning("  ✗ %s: %s", table_name, err)
                    continue
                dump = metadata.model_dump()
                enriched_list.append({"table": table_name, "metadata": dump})
                completed.add(table_name)
                processed_in_run += 1
                logger.info("  ✓ [%s/%s] %s — Category: %s, Examples: %s, Metrics: %s", len(completed), total_tables, table_name, metadata.category, len(metadata.example_queries), len(metadata.metrics))
            if preview and checkpoint_path is not None and enriched_list:
                _save_enriched_checkpoint(checkpoint_path, product_name, enriched_list)
        
        # Build enriched_tables for Phase 2 (model + metadata); only used when not preview-only
        models_by_name = {m["name"]: m for m in all_models}
        enriched_tables = []
        for e in enriched_list:
            name = e["table"]
            meta = e["metadata"]
            if name in models_by_name:
                try:
                    meta_obj = EnrichedTableMetadata(**meta)
                except Exception:
                    meta_obj = EnrichedTableMetadata(
                        table_name=name,
                        category=meta.get("category", "other"),
                        business_purpose=meta.get("business_purpose", ""),
                        key_insights=meta.get("key_insights", []),
                        common_use_cases=meta.get("common_use_cases", []),
                        time_concepts=[],
                        example_queries=[],
                        features=[],
                        metrics=[],
                        instructions=[],
                        key_relationships=meta.get("key_relationships", []),
                    )
                enriched_tables.append({"model": models_by_name[name], "metadata": meta_obj})
        
        logger.info("")
        logger.info(f"✓ Extracted metadata for {len(enriched_list)} tables")
        logger.info("")
        
        # Save preview if requested
        if preview and preview_path is not None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            preview_file = preview_path / f"enriched_metadata_{timestamp}_{product_name}.json"
            with open(preview_file, "w", encoding="utf-8") as f:
                json.dump(enriched_list, f, indent=2)
            logger.info(f"✓ Saved enriched metadata preview: {preview_file}")
            logger.info("")
        
        # ========================================================================
        # PHASE 2: Index to ChromaDB Collections
        # ========================================================================
        logger.info("=" * 80)
        logger.info("PHASE 2: Indexing to ChromaDB Collections")
        logger.info("=" * 80)
        
        results = {}
        
        # 2.1: Index table_descriptions with category_name
        logger.info("\n[1/6] Indexing table_descriptions with category_name...")
        try:
            table_store = doc_store_provider.get_store("table_descriptions")
            table_docs = []
            
            for item in enriched_tables:
                model = item["model"]
                metadata = item["metadata"]
                
                # Create document with category in metadata
                table_content = {
                    "name": model["name"],
                    "description": model.get("description", ""),
                    "columns": [col["name"] for col in model.get("columns", [])],
                    "category": metadata.category,
                    "business_purpose": metadata.business_purpose,
                    "key_insights": metadata.key_insights,
                    "relationships": metadata.key_relationships
                }
                
                doc = Document(
                    page_content=json.dumps(table_content, indent=2),
                    metadata={
                        "type": "TABLE_DESCRIPTION",
                        "table_name": model["name"],
                        "project_id": project_id,
                        "product_name": product_name,
                        "category_name": metadata.category,  # ⭐ CATEGORY FOR FILTERING
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                table_docs.append(doc)
            
            table_store.add_documents(table_docs)
            logger.info(f"  ✓ Indexed {len(table_docs)} tables with category metadata")
            results["table_descriptions"] = {"success": True, "count": len(table_docs)}
        
        except Exception as e:
            logger.error(f"  ✗ Error indexing table_descriptions: {e}")
            results["table_descriptions"] = {"success": False, "error": str(e)}
        
        # 2.2: Index column_metadata with time concepts merged in
        logger.info("\n[2/6] Indexing column_metadata with time concepts...")
        try:
            column_store = doc_store_provider.get_store("column_metadata")
            column_docs = []
            
            for item in enriched_tables:
                model = item["model"]
                metadata = item["metadata"]
                table_name = model["name"]
                
                # Build time concepts map
                time_map = {tc.column_name: tc for tc in metadata.time_concepts}
                
                for column in model.get("columns", []):
                    if column.get("isHidden"):
                        continue
                    
                    column_name = column["name"]
                    time_info = time_map.get(column_name)
                    
                    # Column content with time info merged in
                    column_content = {
                        "column_name": column_name,
                        "table_name": table_name,
                        "type": column.get("type", ""),
                        "description": column.get("description", ""),
                        "is_calculated": column.get("isCalculated", False),
                        "is_primary_key": column_name == model.get("primaryKey", ""),
                        "is_foreign_key": bool(column.get("relationship")),
                        # ⭐ TIME CONCEPTS MERGED IN
                        "is_time_dimension": time_info.is_time_dimension if time_info else False,
                        "time_granularity": time_info.time_granularity if time_info else None,
                        "is_event_time": time_info.is_event_time if time_info else False,
                        "is_process_time": time_info.is_process_time if time_info else False,
                    }
                    
                    doc = Document(
                        page_content=json.dumps(column_content, indent=2),
                        metadata={
                            "type": "COLUMN_METADATA",
                            "column_name": column_name,
                            "table_name": table_name,
                            "project_id": project_id,
                            "product_name": product_name,
                            "category_name": metadata.category,  # Inherit category from table
                            "indexed_at": datetime.utcnow().isoformat()
                        }
                    )
                    column_docs.append(doc)
            
            column_store.add_documents(column_docs)
            logger.info(f"  ✓ Indexed {len(column_docs)} columns with time dimensions")
            results["column_metadata"] = {"success": True, "count": len(column_docs)}
        
        except Exception as e:
            logger.error(f"  ✗ Error indexing column_metadata: {e}")
            results["column_metadata"] = {"success": False, "error": str(e)}
        
        # 2.3: Index sql_pairs (examples)
        logger.info("\n[3/6] Indexing sql_pairs (examples)...")
        try:
            sql_pairs_store = doc_store_provider.get_store("sql_pairs")
            example_docs = []
            
            for item in enriched_tables:
                metadata = item["metadata"]
                table_name = item["model"]["name"]
                
                for example in metadata.example_queries:
                    example_content = {
                        "question": example.natural_question,
                        "sql": example.sql_query,
                        "complexity": example.complexity,
                        "description": example.description,
                        "table_name": table_name
                    }
                    
                    doc = Document(
                        page_content=json.dumps(example_content, indent=2),
                        metadata={
                            "type": "SQL_PAIR",
                            "table_name": table_name,
                            "project_id": project_id,
                            "product_name": product_name,
                            "category_name": metadata.category,
                            "complexity": example.complexity,
                            "indexed_at": datetime.utcnow().isoformat()
                        }
                    )
                    example_docs.append(doc)
            
            if example_docs:
                sql_pairs_store.add_documents(example_docs)
                logger.info(f"  ✓ Indexed {len(example_docs)} SQL examples")
                results["sql_pairs"] = {"success": True, "count": len(example_docs)}
            else:
                logger.info(f"  ⚠ No SQL examples to index")
                results["sql_pairs"] = {"success": True, "count": 0}
        
        except Exception as e:
            logger.error(f"  ✗ Error indexing sql_pairs: {e}")
            results["sql_pairs"] = {"success": False, "error": str(e)}
        
        # 2.4: Index instructions
        logger.info("\n[4/6] Indexing instructions...")
        try:
            instructions_store = doc_store_provider.get_store("instructions")
            instruction_docs = []
            
            for item in enriched_tables:
                metadata = item["metadata"]
                table_name = item["model"]["name"]
                
                for instruction in metadata.instructions:
                    instruction_content = {
                        "instruction_type": instruction.instruction_type,
                        "content": instruction.content,
                        "priority": instruction.priority,
                        "table_name": table_name
                    }
                    
                    doc = Document(
                        page_content=json.dumps(instruction_content, indent=2),
                        metadata={
                            "type": "INSTRUCTION",
                            "table_name": table_name,
                            "project_id": project_id,
                            "product_name": product_name,
                            "category_name": metadata.category,
                            "instruction_type": instruction.instruction_type,
                            "priority": instruction.priority,
                            "indexed_at": datetime.utcnow().isoformat()
                        }
                    )
                    instruction_docs.append(doc)
            
            if instruction_docs:
                instructions_store.add_documents(instruction_docs)
                logger.info(f"  ✓ Indexed {len(instruction_docs)} instructions")
                results["instructions"] = {"success": True, "count": len(instruction_docs)}
            else:
                logger.info(f"  ⚠ No instructions to index")
                results["instructions"] = {"success": True, "count": 0}
        
        except Exception as e:
            logger.error(f"  ✗ Error indexing instructions: {e}")
            results["instructions"] = {"success": False, "error": str(e)}
        
        # 2.5: Index entities (features, metrics) with type discriminator
        logger.info("\n[5/6] Indexing entities (features, metrics, categories)...")
        try:
            entities_store = doc_store_provider.get_store("entities")
            entity_docs = []
            
            # Index categories as entities
            categories_seen = set()
            for item in enriched_tables:
                metadata = item["metadata"]
                if metadata.category not in categories_seen:
                    categories_seen.add(metadata.category)
                    category_content = {
                        "entity_type": "category",
                        "name": metadata.category,
                        "product_name": product_name,
                        "tables": [e["model"]["name"] for e in enriched_tables if e["metadata"].category == metadata.category]
                    }
                    doc = Document(
                        page_content=json.dumps(category_content, indent=2),
                        metadata={
                            "type": "ENTITY",
                            "mdl_entity_type": "category",  # ⭐ DISCRIMINATOR
                            "entity_name": metadata.category,
                            "project_id": project_id,
                            "product_name": product_name,
                            "indexed_at": datetime.utcnow().isoformat()
                        }
                    )
                    entity_docs.append(doc)
            
            # Index features
            for item in enriched_tables:
                metadata = item["metadata"]
                table_name = item["model"]["name"]
                
                for feature in metadata.features:
                    feature_content = {
                        "entity_type": "feature",
                        "name": feature.feature_name,
                        "description": feature.description,
                        "calculation_logic": feature.calculation_logic,
                        "use_cases": feature.use_cases,
                        "table_name": table_name
                    }
                    doc = Document(
                        page_content=json.dumps(feature_content, indent=2),
                        metadata={
                            "type": "ENTITY",
                            "mdl_entity_type": "feature",  # ⭐ DISCRIMINATOR
                            "entity_name": feature.feature_name,
                            "table_name": table_name,
                            "project_id": project_id,
                            "product_name": product_name,
                            "category_name": metadata.category,
                            "indexed_at": datetime.utcnow().isoformat()
                        }
                    )
                    entity_docs.append(doc)
            
            # Index metrics
            for item in enriched_tables:
                metadata = item["metadata"]
                table_name = item["model"]["name"]
                
                for metric in metadata.metrics:
                    metric_content = {
                        "entity_type": "metric",
                        "name": metric.metric_name,
                        "description": metric.description,
                        "calculation": metric.calculation,
                        "metric_category": metric.category,
                        "table_name": table_name
                    }
                    doc = Document(
                        page_content=json.dumps(metric_content, indent=2),
                        metadata={
                            "type": "ENTITY",
                            "mdl_entity_type": "metric",  # ⭐ DISCRIMINATOR
                            "entity_name": metric.metric_name,
                            "table_name": table_name,
                            "project_id": project_id,
                            "product_name": product_name,
                            "category_name": metadata.category,
                            "indexed_at": datetime.utcnow().isoformat()
                        }
                    )
                    entity_docs.append(doc)
            
            if entity_docs:
                entities_store.add_documents(entity_docs)
                logger.info(f"  ✓ Indexed {len(entity_docs)} entities (categories, features, metrics)")
                results["entities"] = {"success": True, "count": len(entity_docs)}
            else:
                logger.info(f"  ⚠ No entities to index")
                results["entities"] = {"success": True, "count": 0}
        
        except Exception as e:
            logger.error(f"  ✗ Error indexing entities: {e}")
            results["entities"] = {"success": False, "error": str(e)}
    
    # 2.6: Index contextual_edges (relationships)
    logger.info("\n[6/6] Indexing contextual_edges (relationships)...")
    try:
        contextual_edges_list = _build_contextual_edges(
            mdl_data, enriched_tables, project_id, product_name
        )
        if not contextual_edges_list:
            logger.info(f"  No contextual edges to index (no MDL relationships or key_relationships)")
            results["contextual_edges"] = {"success": True, "count": 0}
        else:
            vector_store_client = await get_vector_store_client(embeddings_model=embeddings)
            contextual_storage = ContextualGraphStorage(
                vector_store_client=vector_store_client,
                embeddings_model=embeddings,
                collection_prefix=project_id or "",
            )
            saved_ids = await contextual_storage.save_contextual_edges(
                contextual_edges_list, batch_size=500
            )
            logger.info(f"  ✓ Indexed {len(saved_ids)} contextual edges")
            results["contextual_edges"] = {"success": True, "count": len(saved_ids)}
    except Exception as e:
        logger.error(f"  ✗ Error indexing contextual_edges: {e}")
        results["contextual_edges"] = {"success": False, "error": str(e)}
    
    # ========================================================================
    # Summary
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("Indexing Summary")
    logger.info("=" * 80)
    for collection, result in results.items():
        if result.get("success"):
            logger.info(f"✓ {collection}: {result.get('count', 0)} documents indexed")
            if "note" in result:
                logger.info(f"  Note: {result['note']}")
        else:
            logger.error(f"✗ {collection}: Error - {result.get('error', 'Unknown error')}")
    logger.info("=" * 80)
    
    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Index MDL files with enriched metadata (ONE LLM call per table)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--mdl-file",
        required=True,
        help="Path to MDL JSON file"
    )
    
    parser.add_argument(
        "--project-id",
        required=True,
        help="Project ID"
    )
    
    parser.add_argument(
        "--product-name",
        help="Product name (defaults to project_id)"
    )
    
    parser.add_argument(
        "--domain",
        help="Domain filter (optional)"
    )
    
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Save preview files of extracted metadata"
    )
    
    parser.add_argument(
        "--preview-dir",
        help="Directory for preview files (defaults to indexing_preview)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Tables per batch when using preview + checkpoint (default: 25). Enables resume for 400+ tables."
    )
    parser.add_argument(
        "--checkpoint-dir",
        help="Checkpoint directory (default: preview_dir/mdl_enriched/checkpoints). Resume from here if interrupted."
    )
    parser.add_argument(
        "--edges-only",
        action="store_true",
        help="Only index contextual_edges (skip LLM and other collections). Requires --enriched-metadata."
    )
    parser.add_argument(
        "--enriched-metadata",
        dest="enriched_metadata_path",
        help="Path to enriched metadata JSON (required when --edges-only). e.g. indexing_preview/mdl_enriched/enriched_metadata_*.json"
    )
    
    args = parser.parse_args()
    
    # Run async indexing
    asyncio.run(index_mdl_enriched(
        mdl_file_path=args.mdl_file,
        project_id=args.project_id,
        product_name=args.product_name,
        domain=args.domain,
        preview=args.preview,
        preview_dir=args.preview_dir,
        batch_size=args.batch_size,
        checkpoint_dir=args.checkpoint_dir,
        edges_only=args.edges_only,
        enriched_metadata_path=args.enriched_metadata_path,
    ))


if __name__ == "__main__":
    main()
