"""Loader for SQL function appendix - restricted function set for DS RAG."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from app.settings import get_settings

logger = logging.getLogger("genieml-agents")

DEFAULT_APPENDIX_PATH = "data/sql_functions/sql_function_appendix.json"


def load_appendix_functions(path=None) -> List[Dict[str, Any]]:
    """
    Load the SQL function appendix from sql_function_appendix.json.
    Returns list of {function, primary_source, summary}.
    Accepts Path, str, or None (uses default under project BASE_DIR).
    """
    settings = get_settings()
    if path is None:
        path = settings.BASE_DIR / DEFAULT_APPENDIX_PATH
    else:
        path = Path(path)
        if not path.is_absolute():
            path = settings.BASE_DIR / path

    if not path.exists():
        logger.warning(f"Appendix file not found: {path}")
        return []

    try:
        with open(path, "r") as f:
            data = json.load(f)
        functions = data.get("functions", [])
        logger.info(f"Loaded {len(functions)} functions from appendix at {path}")
        return functions
    except Exception as e:
        logger.error(f"Error loading appendix: {e}")
        return []


def format_appendix_for_prompt(functions: List[Dict[str, Any]]) -> str:
    """Format appendix functions with full calling contracts for LLM prompts."""
    if not functions:
        return ""

    lines = [
        "### AVAILABLE SQL FUNCTIONS (APPENDIX - USE ONLY THESE) ###",
        "You may ONLY use the following SQL functions.",
        "CRITICAL: Each function requires JSONB array input — NOT raw arrays or scalars.",
        "You MUST format source data as JSONB before calling any function.",
        "",
    ]
    for fn in functions:
        name = fn.get("function", "")
        source = fn.get("primary_source", "")
        summary = fn.get("summary", "")
        contract = fn.get("input_contract", "")
        signature = fn.get("call_signature", "")
        jsonb_example = fn.get("jsonb_format_example", "")

        lines.append(f"**{name}**")
        lines.append(f"  Source: {source}")
        lines.append(f"  What it does: {summary}")
        if contract:
            lines.append(f"  Input JSONB keys required: {contract}")
        if signature:
            lines.append(f"  Signature: {signature}")
        if jsonb_example:
            lines.append(f"  Format input with: {jsonb_example}")
        lines.append("")

    return "\n".join(lines)
