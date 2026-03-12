"""
LLM-enrich concept_recommendation_registry and source_concept_map from CSOD table structure.

Uses enriched metadata (projects, tables, categories) and key_concepts to generate:
- concept_recommendation_registry.json — recommendation_areas per concept
- source_concept_map.cornerstone — mdl_table_refs, coverage per concept (optional)

Usage:
    python app/ingestion/enrich_registries_with_llm.py --enriched data/csod_project_metadata_enriched.json
    python app/ingestion/enrich_registries_with_llm.py --enriched data/csod_project_metadata_enriched.json --dry-run
    python app/ingestion/enrich_registries_with_llm.py --enriched data/csod_project_metadata_enriched.json --concepts compliance_training learning_effectiveness
"""

from pathlib import Path as _Path
import sys
_script_dir = _Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPO_ROOT = _Path(__file__).resolve().parent.parent.parent
REGISTRIES_DIR = REPO_ROOT / "registries"
SOURCE_CONCEPT_REGISTRY_PATH = REGISTRIES_DIR / "source_concept_registry.json"
CONCEPT_REC_REGISTRY_PATH = REGISTRIES_DIR / "concept_recommendation_registry.json"


def _get_llm(temperature: float = 0.2):
    """Get LLM from app.core or fallback to env vars."""
    try:
        from app.core.dependencies import get_llm
        from app.core.settings import get_settings
        s = get_settings()
        return get_llm(temperature=temperature, model=s.LLM_MODEL, provider=s.LLM_PROVIDER)
    except Exception as e:
        logger.debug(f"App LLM unavailable: {e}")

    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    model = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
    if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=temperature)
    if (provider == "openai" or not os.getenv("ANTHROPIC_API_KEY")) and os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=temperature)
    logger.warning("No LLM available — set ANTHROPIC_API_KEY or OPENAI_API_KEY")
    return None


def _build_context(enriched_metadata: Dict) -> str:
    """Build context string from projects, tables, categories."""
    projects = enriched_metadata.get("projects", [])
    lines = []
    for p in projects[:20]:  # limit for prompt size
        cat = p.get("category", "")
        sub = p.get("subcategory", "")
        pid = p.get("project_id", "")
        concepts = p.get("concept_ids", [])
        mdl_tables = p.get("mdl_tables", {})
        tables = mdl_tables.get("primary", []) + mdl_tables.get("supporting", []) + mdl_tables.get("optional", [])
        lines.append(f"- {pid}: category={cat}/{sub}, concepts={concepts}, tables={tables[:8]}")
    return "\n".join(lines)


def _parse_recommendation_areas(text: str) -> List[Dict]:
    """Parse LLM JSON response into recommendation_areas list."""
    text = text.strip()
    for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            text = m.group(1).strip()
            break
    start, end = text.find("["), text.rfind("]") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    try:
        areas = json.loads(text)
        return areas if isinstance(areas, list) else []
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return [json.loads(text[start:end])]
        except json.JSONDecodeError:
            pass
    return []


def _enrich_concept_recommendations(
    concept: Dict,
    context: str,
    llm,
    existing_areas: List[Dict],
) -> List[Dict]:
    """Use LLM to generate recommendation_areas for a concept."""
    cid = concept.get("concept_id", "")
    display = concept.get("display_name", "")
    desc = concept.get("description", "")
    questions = concept.get("business_questions", [])

    prompt = f"""You are a data architect for an LMS analytics platform. Generate 2-4 recommendation areas for the concept "{display}" ({cid}).

Concept: {desc}
Business questions: {questions}

CSOD table structure (concept -> tables):
{context}

For each recommendation area, output JSON with:
- area_id: snake_case (e.g. overdue_risk, assessment_quality)
- display_name: short title
- description: what this area answers
- metrics: 2-4 metric names (snake_case)
- kpis: 2-3 KPI names
- filters: 2-4 filterable field names (e.g. org_unit, due_date, status)
- causal_paths: 1-2 "A → B" causal chain strings
- dashboard_axes: 2-3 chart/section titles
- natural_language_questions: 2-3 business questions this area answers
- data_requirements: 2-4 table names from the context that serve this area

Output a JSON array only, no markdown:
[{{"area_id": "...", "display_name": "...", ...}}, ...]"""

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        msg = SystemMessage(content="Return only a valid JSON array. No explanation.")
        resp = llm.invoke([msg, HumanMessage(content=prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)
        areas = _parse_recommendation_areas(text)
        for a in areas:
            if not a.get("area_id"):
                a["area_id"] = (a.get("display_name", "area") or "area").lower().replace(" ", "_").replace("-", "_")[:40]
        return areas
    except Exception as e:
        logger.warning(f"LLM failed for {cid}: {e}")
        return existing_areas


def enrich_concept_recommendation_registry(
    enriched_metadata_path: Path,
    source_concept_registry_path: Path,
    output_path: Path,
    concept_filter: Optional[Set[str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Generate concept_recommendation_registry.json using LLM."""
    with open(enriched_metadata_path, "r", encoding="utf-8") as f:
        enriched = json.load(f)
    with open(source_concept_registry_path, "r", encoding="utf-8") as f:
        src_reg = json.load(f)

    key_concepts = src_reg.get("key_concepts", [])
    if concept_filter:
        key_concepts = [c for c in key_concepts if c.get("concept_id") in concept_filter]

    context = _build_context(enriched)
    llm = _get_llm()
    if not llm:
        logger.error("LLM unavailable — set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        return {}

    concept_recommendations = {}
    for concept in key_concepts:
        cid = concept.get("concept_id", "")
        logger.info(f"Enriching concept: {cid}")
        areas = _enrich_concept_recommendations(concept, context, llm, [])
        concept_recommendations[cid] = {"recommendation_areas": areas}
        logger.info(f"  -> {len(areas)} recommendation areas")

    result = {
        "_meta": {
            "version": "1.0",
            "description": "LLM-enriched from CSOD table structure",
            "inputs": [str(enriched_metadata_path)],
        },
        "concept_recommendations": concept_recommendations,
    }

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Wrote {output_path}")

    return result


def print_registry_preview(
    concept_recommendations: Dict[str, Any],
    source_concept_map: Optional[Dict[str, Dict]] = None,
) -> None:
    """Print formatted preview of registry enrichment output."""
    print("\n" + "=" * 60)
    print("Registry Enrichment Preview")
    print("=" * 60)
    print("\nconcept_recommendation_registry.json:")
    for cid, data in concept_recommendations.items():
        areas = data.get("recommendation_areas", [])
        print(f"  {cid}: {len(areas)} recommendation areas")
        for a in areas[:3]:
            print(f"    - {a.get('area_id', '?')}: {a.get('display_name', '')}")
            qs = a.get("natural_language_questions", [])
            if qs:
                print(f"      Questions: {qs[0][:60]}...")
        if len(areas) > 3:
            print(f"    ... +{len(areas) - 3} more")

    if source_concept_map:
        print("\nsource_concept_map.cornerstone:")
        for cid, entry in list(source_concept_map.get("cornerstone", {}).items())[:8]:
            refs = entry.get("mdl_table_refs", [])
            projs = entry.get("project_ids", [])
            print(f"  {cid}: {len(refs)} tables, {len(projs)} projects")
            if refs:
                print(f"    Tables: {', '.join(refs[:5])}{'...' if len(refs) > 5 else ''}")

    print("\n" + "=" * 60)


def enrich_source_concept_map(
    enriched_metadata: Dict,
    source_concept_registry: Dict,
    source_id: str = "cornerstone",
) -> Dict[str, Any]:
    """Build source_concept_map from enriched metadata (concept -> mdl_table_refs, project_ids)."""
    cornerstone = source_concept_registry.setdefault("source_concept_map", {}).setdefault(source_id, {})

    for project in enriched_metadata.get("projects", []):
        pid = project.get("project_id", "")
        concept_ids = project.get("concept_ids", [])
        mdl_tables = project.get("mdl_tables", {})
        table_refs = (
            mdl_tables.get("primary", [])
            + mdl_tables.get("supporting", [])
            + mdl_tables.get("optional", [])
        )
        for cid in concept_ids:
            entry = cornerstone.get(cid) or {
                "api_categories": [],
                "mdl_table_refs": [],
                "project_ids": [],
                "coverage_confidence": 0.85,
                "coverage_notes": "",
            }
            entry["mdl_table_refs"] = list(set(entry.get("mdl_table_refs", [])) | set(table_refs))
            entry["project_ids"] = list(set(entry.get("project_ids", [])) | {pid})
            if not entry.get("coverage_notes"):
                entry["coverage_notes"] = f"CSOD MDL projects: {', '.join(entry['project_ids'][:3])}{'...' if len(entry['project_ids']) > 3 else ''}"
            cornerstone[cid] = entry

    return source_concept_registry


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="LLM-enrich concept_recommendation_registry and source_concept_map from CSOD tables"
    )
    parser.add_argument(
        "--enriched",
        type=str,
        required=True,
        help="Path to csod_project_metadata_enriched.json",
    )
    parser.add_argument(
        "--source-registry",
        type=str,
        default=None,
        help="Path to source_concept_registry.json (default: registries/source_concept_registry.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for concept_recommendation_registry.json",
    )
    parser.add_argument(
        "--concepts",
        type=str,
        nargs="*",
        default=None,
        help="Limit to specific concept_ids (default: all)",
    )
    parser.add_argument(
        "--enrich-source-map",
        action="store_true",
        help="Also update source_concept_map (mdl_table_refs, project_ids) in source_concept_registry.json",
    )
    parser.add_argument(
        "--source-map-only",
        action="store_true",
        help="Only update source_concept_map, skip LLM (no API key needed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate without writing files",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Print formatted preview of generated registries",
    )
    args = parser.parse_args()

    enriched_path = Path(args.enriched).resolve()
    if not enriched_path.exists():
        logger.error(f"Enriched metadata not found: {enriched_path}")
        return 1

    src_reg_path = Path(args.source_registry or str(SOURCE_CONCEPT_REGISTRY_PATH)).resolve()
    if not src_reg_path.exists():
        logger.error(f"Source concept registry not found: {src_reg_path}")
        return 1

    output_path = Path(args.output or str(CONCEPT_REC_REGISTRY_PATH)).resolve()
    concept_filter = set(args.concepts) if args.concepts else None

    if args.source_map_only:
        with open(enriched_path, "r", encoding="utf-8") as f:
            enriched = json.load(f)
        with open(src_reg_path, "r", encoding="utf-8") as f:
            src_reg = json.load(f)
        src_reg = enrich_source_concept_map(enriched, src_reg)
        if args.preview:
            print_registry_preview({}, src_reg.get("source_concept_map"))
        if not args.dry_run:
            with open(src_reg_path, "w", encoding="utf-8") as f:
                json.dump(src_reg, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated source_concept_map in {src_reg_path}")
        return 0

    result = enrich_concept_recommendation_registry(
        enriched_path,
        src_reg_path,
        output_path,
        concept_filter=concept_filter,
        dry_run=args.dry_run,
    )
    if not result and not args.dry_run:
        return 1

    if args.preview and result:
        src_map = None
        if args.enrich_source_map:
            with open(enriched_path, "r", encoding="utf-8") as f:
                enriched = json.load(f)
            with open(src_reg_path, "r", encoding="utf-8") as f:
                src_reg = json.load(f)
            src_map = enrich_source_concept_map(enriched, src_reg).get("source_concept_map")
        print_registry_preview(result.get("concept_recommendations", {}), src_map)

    if args.enrich_source_map and not args.dry_run:
        with open(enriched_path, "r", encoding="utf-8") as f:
            enriched = json.load(f)
        with open(src_reg_path, "r", encoding="utf-8") as f:
            src_reg = json.load(f)
        src_reg = enrich_source_concept_map(enriched, src_reg)
        with open(src_reg_path, "w", encoding="utf-8") as f:
            json.dump(src_reg, f, indent=2, ensure_ascii=False)
        logger.info(f"Updated source_concept_map in {src_reg_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
