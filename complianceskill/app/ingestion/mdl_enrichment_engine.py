"""
MDL Enrichment Engine — LLM-driven metadata enrichment for MDL projects.

Extracts schema from MDL files and project_metadata.json dynamically (no hardcoded tables).
Uses LLM to infer: concept_ids, table_to_category, mdl_tables, key_columns.
Designed to handle new MDLs as they arrive — no manual mapping updates required.

Uses app.core.dependencies.get_llm and app.core.settings for LLM configuration,
keeping alignment with the complianceskill environment (orchestrator, ingest, etc.).

Usage (as library):
    from app.ingestion.mdl_enrichment_engine import MDLEnrichmentEngine, enrich_project_with_llm

    engine = MDLEnrichmentEngine(llm=...)
    enriched = engine.enrich_project(project, folder_path=Path(...))
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Reference taxonomy for LLM — LMS concepts from lexy_metadata_registry_design
# LLM selects from these; can extend without code changes via config
LMS_CONCEPT_TAXONOMY = [
    "compliance_training",
    "learning_effectiveness",
    "training_roi",
    "workforce_capability",
    "lms_health",
    "certification_tracking",
    "training_completion",
    "knowledge_retention",
    "user_context",
    "localization",
    "extensible",
]

CATEGORY_TAXONOMY = [
    "training_completion",
    "compliance_training",
    "mandatory_training",
    "overdue_tracking",
    "certification_tracking",
    "learning_effectiveness",
    "knowledge_retention",
    "training_roi",
    "cost_efficiency",
    "vendor_efficiency",
    "no_shows",
    "ilt_utilization",
    "kpi_recommendations",
    "user_context",
    "localization",
    "extensible",
]


def _get_llm(temperature: Optional[float] = None):
    """
    Get LLM from app.core.dependencies, using settings for provider/model/temperature.
    Aligns with complianceskill environment (orchestrator, enrich_metric_registry, etc.).
    Requires app to be properly configured (settings, dependencies).
    """
    from app.core.dependencies import get_llm
    from app.core.settings import get_settings
    s = get_settings()
    temp = temperature if temperature is not None else s.LLM_TEMPERATURE
    return get_llm(temperature=temp, model=s.LLM_MODEL, provider=s.LLM_PROVIDER)


def extract_schema_from_mdl(mdl_path: Path, max_cols: int = 15) -> Optional[Dict[str, Any]]:
    """
    Extract compact schema from MDL file for LLM context.
    Returns {name, primaryKey, columns, column_count, catalog, schema}.
    catalog/schema come from MDL root or model.tableReference (per lexy_metadata_registry_design).
    """
    if not mdl_path.exists():
        return None
    try:
        with open(mdl_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read MDL {mdl_path}: {e}")
        return None
    models = data.get("models", [])
    if not models:
        return None
    model = models[0]
    columns = model.get("columns", [])
    col_summaries = []
    for c in columns[:max_cols]:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "")
        if not name:
            continue
        props = c.get("properties") or {}
        desc = (props.get("description") or props.get("businessMeaning") or "")[:120]
        col_summaries.append({
            "name": name,
            "type": c.get("type", "unknown"),
            "description": desc.strip() or None,
        })
    # catalog/schema from MDL root or model.tableReference (table_schemas, db_schemas)
    catalog = data.get("catalog")
    schema = data.get("schema")
    tr = model.get("tableReference") or {}
    if not catalog and tr.get("catalog"):
        catalog = tr["catalog"]
    if not schema and tr.get("schema"):
        schema = tr["schema"]
    result = {
        "name": model.get("name", ""),
        "primaryKey": model.get("primaryKey"),
        "columns": col_summaries,
        "column_count": len(columns),
    }
    if catalog is not None:
        result["catalog"] = catalog
    if schema is not None:
        result["schema"] = schema
    return result


def build_table_summaries(
    project: Dict[str, Any],
    folder_path: Path,
) -> List[Dict[str, Any]]:
    """Build schema summary for each table from MDL files."""
    tables = project.get("tables", [])
    summaries = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        name = t.get("name", "")
        mdl_file = t.get("mdl_file", f"{name}.mdl.json")
        mdl_path = folder_path / mdl_file
        schema = extract_schema_from_mdl(mdl_path)
        if schema:
            schema["display_name"] = t.get("display_name", name)
            schema["table_description"] = (t.get("description") or "")[:200]
            summaries.append(schema)
        else:
            summaries.append({
                "name": name,
                "display_name": t.get("display_name", name),
                "table_description": (t.get("description") or "")[:200],
                "primaryKey": None,
                "columns": [],
                "column_count": 0,
            })
    return summaries


def extract_table_schemas_from_folder(
    project: Dict[str, Any],
    folder_path: Path,
) -> Dict[str, Dict[str, str]]:
    """
    Extract table_schemas (catalog, schema) from MDL files per table.
    Returns {table_name: {"catalog": "...", "schema": "..."}}.
    Aligns with lexy_metadata_registry_design db_schemas / table_schemas.
    """
    table_schemas: Dict[str, Dict[str, str]] = {}
    tables = project.get("tables", [])
    for t in tables:
        if not isinstance(t, dict):
            continue
        name = t.get("name", "")
        if not name:
            continue
        mdl_file = t.get("mdl_file", f"{name}.mdl.json")
        mdl_path = folder_path / mdl_file
        if not mdl_path.exists():
            continue
        try:
            with open(mdl_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        catalog = data.get("catalog")
        schema = data.get("schema")
        models = data.get("models", [])
        if models:
            tr = models[0].get("tableReference") or {}
            catalog = catalog or tr.get("catalog")
            schema = schema or tr.get("schema")
        if catalog or schema:
            table_schemas[name] = {
                "catalog": catalog or "",
                "schema": schema or "",
            }
    return table_schemas


def build_enrichment_prompt(
    project_id: str,
    title: str,
    description: str,
    table_summaries: List[Dict[str, Any]],
) -> str:
    """Build LLM prompt for project enrichment."""
    tables_json = json.dumps(table_summaries, indent=2)
    concepts_ref = ", ".join(LMS_CONCEPT_TAXONOMY)
    categories_ref = ", ".join(CATEGORY_TAXONOMY)

    return f"""You are a data architect enriching MDL (Model Definition Language) metadata for an LMS/learning analytics platform.

**Project context:**
- project_id: {project_id}
- title: {title}
- description: {description}

**Tables and schemas (from MDL files):**
{tables_json}

**Task:** Infer enrichment metadata. Use ONLY concepts and categories from the reference lists below.

**Reference concept_ids (pick 1–4 that best fit):** {concepts_ref}

**Reference categories (pick 0–3 per table for table_to_category):** {categories_ref}

**Output JSON only, no markdown:**
{{
  "concept_ids": ["concept1", "concept2"],
  "table_to_category": {{
    "table_name": ["category1", "category2"]
  }},
  "mdl_tables": {{
    "primary": ["table1", "table2"],
    "supporting": ["table3"],
    "optional": ["table4"]
  }},
  "key_columns": {{
    "table_name": ["pk_col", "user_id", "completed_date", ...]
  }}
}}

Rules:
- primary: core entity tables for main analytics
- supporting: lookup tables, localizations, user/org context
- optional: rarely used or auxiliary tables
- key_columns: primaryKey + columns important for metrics (dates, status, user/object refs)
- concept_ids: high-level business concepts this project supports
- table_to_category: analytics categories each table contributes to
"""


def parse_llm_enrichment_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse LLM JSON response, handling markdown fences."""
    text = text.strip()
    for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            text = m.group(1).strip()
            break
    start, end = text.find("{"), text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"LLM response parse error: {e}")
        return None


def validate_and_merge_enrichment(
    raw: Dict[str, Any],
    table_names: List[str],
) -> Dict[str, Any]:
    """Validate LLM output and merge into safe structure."""
    valid_concepts = set(LMS_CONCEPT_TAXONOMY)
    valid_categories = set(CATEGORY_TAXONOMY)

    concept_ids = [c for c in raw.get("concept_ids", []) if c in valid_concepts]
    if not concept_ids:
        concept_ids = ["user_context"]  # safe default

    table_to_category = {}
    for t in table_names:
        cats = raw.get("table_to_category", {}).get(t, [])
        table_to_category[t] = [c for c in cats if c in valid_categories]

    mdl_tables = raw.get("mdl_tables", {})
    primary = [x for x in mdl_tables.get("primary", []) if x in table_names]
    supporting = [x for x in mdl_tables.get("supporting", []) if x in table_names]
    optional = [x for x in mdl_tables.get("optional", []) if x in table_names]
    # Ensure all tables are classified
    classified = set(primary + supporting + optional)
    for t in table_names:
        if t not in classified:
            optional.append(t)

    key_columns = {
        t: [c for c in cols if isinstance(c, str)]
        for t, cols in raw.get("key_columns", {}).items()
        if t in table_names and isinstance(cols, list)
    }

    return {
        "concept_ids": concept_ids,
        "table_to_category": table_to_category,
        "mdl_tables": {
            "primary": primary,
            "supporting": supporting,
            "optional": optional,
        },
        "key_columns": key_columns,
    }


class MDLEnrichmentEngine:
    """
    LLM-driven enrichment engine for MDL projects.
    No hardcoded table or concept mappings — infers from MDL content.
    """

    def __init__(self, llm=None, temperature: float = 0.0):
        self._llm = llm or _get_llm(temperature=temperature)

    def enrich_project(
        self,
        project: Dict[str, Any],
        folder_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Enrich a single project using LLM.
        Reads MDL files from folder_path to build schema context.
        """
        enriched = dict(project)
        folder = folder_path or Path(project.get("folder_path", ""))
        if not folder or not Path(folder).exists():
            logger.warning(f"No valid folder_path for {project.get('project_id')}, skipping LLM enrichment")
            return enriched

        folder_path = Path(folder)
        table_summaries = build_table_summaries(project, folder_path)
        if not table_summaries:
            return enriched

        prompt = build_enrichment_prompt(
            project_id=project.get("project_id", "unknown"),
            title=project.get("title", ""),
            description=project.get("description", ""),
            table_summaries=table_summaries,
        )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            msg = SystemMessage(content="Return only valid JSON. No explanation.")
            resp = self._llm.invoke([msg, HumanMessage(content=prompt)])
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            logger.error(f"LLM enrichment failed for {project.get('project_id')}: {e}")
            return enriched

        raw = parse_llm_enrichment_response(text)
        if not raw:
            return enriched

        table_names = [t.get("name", "") for t in project.get("tables", []) if isinstance(t, dict) and t.get("name")]
        merged = validate_and_merge_enrichment(raw, table_names)

        enriched["concept_ids"] = merged["concept_ids"]
        enriched["table_to_category"] = merged["table_to_category"]
        enriched["mdl_tables"] = merged["mdl_tables"]
        enriched["key_columns"] = merged["key_columns"]
        return enriched


def enrich_project_with_llm(
    project: Dict[str, Any],
    folder_path: Optional[Path] = None,
    llm=None,
) -> Dict[str, Any]:
    """Convenience: enrich a single project with LLM."""
    engine = MDLEnrichmentEngine(llm=llm)
    return engine.enrich_project(project, folder_path=folder_path)
