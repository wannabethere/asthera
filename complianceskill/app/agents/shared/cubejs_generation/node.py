"""
CubeJS Schema Generation Node

Single-step node: given gold SQL files + metric recommendations,
generate Cube.js schema files via LLM with few-shot prompting.

Can be wired into CSOD or DT workflow after gold model generation.
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import EnhancedCompliancePipelineState
from app.core.dependencies import get_llm

from .example_loader import load_examples_for_domain
from .parser import parse_cube_js_response, validate_cube_schema, CubeSchemaFile

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

LLM_CONFIG = {
    "temperature": 0.1,
    "max_tokens": 8192,
    "timeout": 120,
}


def _load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    path = _PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _infer_domain_from_name(model_name: str) -> str:
    """Infer domain from gold model name (e.g. gold_qualys_vulnerabilities_weekly -> qualys)."""
    name_lower = model_name.lower()
    for domain in ("qualys", "snyk", "cornerstone", "workday", "okta", "wiz"):
        if domain in name_lower:
            return domain
    # Fallback: use first segment after gold_
    m = re.match(r"gold_([a-z0-9]+)", name_lower)
    return m.group(1) if m else "default"


def _infer_granularity_from_name(model_name: str) -> str:
    """Infer granularity from gold model name."""
    name_lower = model_name.lower()
    if "weekly" in name_lower or "_week_" in name_lower:
        return "weekly"
    if "monthly" in name_lower or "_month_" in name_lower:
        return "monthly"
    if "daily" in name_lower or "_day_" in name_lower:
        return "daily"
    return "weekly"  # Default to weekly as primary grain


def _gold_sql_from_state(state: EnhancedCompliancePipelineState) -> List[Dict[str, Any]]:
    """
    Extract gold SQL files from state (CSOD or DT).
    Returns list of {name, sql_text, domain, granularity}.
    """
    gold_sql_files: List[Dict[str, Any]] = []

    # CSOD
    csod_sql = state.get("csod_generated_gold_model_sql", [])
    for m in csod_sql:
        if isinstance(m, dict) and m.get("sql_query"):
            gold_sql_files.append({
                "name": m.get("name", "unknown"),
                "sql_text": m.get("sql_query", ""),
                "domain": _infer_domain_from_name(m.get("name", "")),
                "granularity": _infer_granularity_from_name(m.get("name", "")),
            })

    # DT
    dt_sql = state.get("dt_generated_gold_model_sql", [])
    for m in dt_sql:
        if isinstance(m, dict) and m.get("sql_query"):
            gold_sql_files.append({
                "name": m.get("name", "unknown"),
                "sql_text": m.get("sql_query", ""),
                "domain": _infer_domain_from_name(m.get("name", "")),
                "granularity": _infer_granularity_from_name(m.get("name", "")),
            })

    return gold_sql_files


def _metric_recommendations_from_state(state: EnhancedCompliancePipelineState) -> List[Dict[str, Any]]:
    """Extract metric recommendations from state (CSOD or DT)."""
    # CSOD
    csod = state.get("csod_metric_recommendations", [])
    if csod:
        return csod
    # DT
    dt = state.get("dt_metric_recommendations", [])
    if dt:
        return dt
    planner = state.get("planner_metric_recommendations", [])
    if planner:
        return planner
    return []


def _connection_id_from_state(state: EnhancedCompliancePipelineState) -> str:
    """Get connection/tenant ID for cube isolation."""
    return (
        state.get("active_project_id")
        or state.get("session_id", "")
        or "default"
    )


def _build_gold_sql_block(gold_sql_files: List[Dict], domain: str) -> str:
    """Build gold SQL block for a given domain (weekly tables only for primary grain)."""
    # Prefer weekly; include daily/monthly only if no weekly
    weekly = [f for f in gold_sql_files if f.get("granularity") == "weekly" and f.get("domain") == domain]
    others = [f for f in gold_sql_files if f.get("domain") == domain and f not in weekly]
    files_to_use = weekly if weekly else others

    if not files_to_use:
        return "(No gold SQL for this domain)"

    blocks = []
    for f in files_to_use:
        blocks.append(f"-- {f['name']} ({f['granularity']})\n{f['sql_text']}")
    return "\n\n---\n\n".join(blocks)


def _filter_metrics_for_domain(metrics: List[Dict], domain: str) -> List[Dict]:
    """Filter metrics to those relevant to the domain."""
    # Simple filter: include all if we can't determine domain-specific metrics
    return metrics


def cubejs_schema_generation_node(
    state: EnhancedCompliancePipelineState,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Generate Cube.js schema files from gold SQL and metric recommendations.

    Reads from state:
      - csod_generated_gold_model_sql / dt_generated_gold_model_sql
      - csod_metric_recommendations / dt_metric_recommendations
      - output_format (optional gate: skip if not "cubejs")
      - active_project_id (for connectionId)

    Writes to state:
      - cubejs_schema_files
      - cubejs_generation_errors
    """
    output_format = state.get("output_format", "cubejs")
    if output_format and output_format != "cubejs":
        logger.info(f"cubejs_schema_generation: Skipping — output_format={output_format}")
        return {
            "cubejs_schema_files": [],
            "cubejs_generation_errors": [],
        }

    gold_sql_files = _gold_sql_from_state(state)
    metric_recommendations = _metric_recommendations_from_state(state)
    connection_id = _connection_id_from_state(state)

    if not gold_sql_files:
        logger.info("cubejs_schema_generation: No gold SQL files, skipping")
        return {
            "cubejs_schema_files": [],
            "cubejs_generation_errors": ["No gold SQL files in state"],
        }

    # Group by domain
    domains = list({f["domain"] for f in gold_sql_files})
    connection_id_note = f"Tenant isolation key — always filter by connectionId (value: {connection_id})"

    system_prompt = _load_prompt("cubejs_system_prompt")
    instructions = _load_prompt("cubejs_instructions")
    user_template = _load_prompt("cubejs_user_template")

    if not system_prompt or not user_template:
        return {
            "cubejs_schema_files": [],
            "cubejs_generation_errors": ["Missing cubejs prompts"],
        }

    all_schema_files: List[CubeSchemaFile] = []
    all_errors: List[str] = []

    llm = get_llm(
        temperature=LLM_CONFIG["temperature"],
    )
    if hasattr(llm, "max_tokens"):
        llm.max_tokens = LLM_CONFIG["max_tokens"]
    elif hasattr(llm, "max_output_tokens"):
        llm.max_output_tokens = LLM_CONFIG["max_tokens"]

    for domain in domains:
        gold_sql_block = _build_gold_sql_block(gold_sql_files, domain)
        metrics_for_domain = _filter_metrics_for_domain(metric_recommendations, domain)
        metric_block = json.dumps(metrics_for_domain[:50], indent=2) if metrics_for_domain else "[]"
        example_block = load_examples_for_domain(domain, max_examples=2)

        instructions_with_note = (instructions or "") + f"\n\n{connection_id_note}"
        user_content = user_template.format(
            gold_sql_block=gold_sql_block,
            metric_block=metric_block,
            example_block=example_block,
            instructions_block=instructions_with_note,
            domain=domain,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        try:
            response = llm.invoke(messages)
            raw_content = response.content if hasattr(response, "content") else str(response)

            parsed = parse_cube_js_response(raw_content)
            for cube_file in parsed:
                errs = validate_cube_schema(cube_file["content"], cube_file["cube_name"])
                if errs:
                    all_errors.extend(errs)
                    logger.warning(f"cubejs validation for {cube_file['cube_name']}: {errs}")
                all_schema_files.append(cube_file)

            logger.info(f"cubejs_schema_generation: Generated {len(parsed)} cubes for domain {domain}")

        except Exception as e:
            logger.exception(f"cubejs_schema_generation: LLM error for domain {domain}: {e}")
            all_errors.append(f"Domain {domain}: {str(e)}")

    # Dedup by cube_name (keep last)
    seen = {}
    for f in all_schema_files:
        seen[f["cube_name"]] = f
    final_files = list(seen.values())

    return {
        "cubejs_schema_files": [
            {
                "cube_name": f["cube_name"],
                "filename": f["filename"],
                "content": f["content"],
                "source_tables": f.get("source_tables", []),
                "measures": f.get("measures", []),
                "dimensions": f.get("dimensions", []),
            }
            for f in final_files
        ],
        "cubejs_generation_errors": all_errors,
    }
