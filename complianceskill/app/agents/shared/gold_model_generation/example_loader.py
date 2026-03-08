"""
Few-shot example loader for gold model SQL generation.

Loads dbt SQL examples by domain for few-shot prompting.
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_EXAMPLES_DIR = _PROMPTS_DIR / "examples"

# Example pairs: domain -> (name, sql_path, note)
EXAMPLE_PAIRS: List[dict] = [
    {
        "domain": "qualys",
        "name": "gold_qualys_vulnerabilities_weekly_snapshot",
        "sql_path": "gold_qualys_vulnerabilities_weekly_snapshot.sql",
        "note": "Incremental weekly aggregation, composite pk, FILTER for severity counts",
    },
    {
        "domain": "snyk",
        "name": "gold_snyk_issues_daily_snapshot",
        "sql_path": "gold_snyk_issues_daily_snapshot.sql",
        "note": "Incremental daily snapshot, simple row passthrough with snapshot_date",
    },
    {
        "domain": "snyk",
        "name": "gold_snyk_issues_weekly_snapshot",
        "sql_path": "gold_snyk_issues_weekly_snapshot.sql",
        "note": "Incremental weekly aggregation, GROUP BY with severity, avg_days_to_fix",
    },
    {
        "domain": "cornerstone",
        "name": "gold_cornerstone_completions_weekly_snapshot",
        "sql_path": "gold_cornerstone_completions_weekly_snapshot.sql",
        "note": "Table materialization, CSOD/LMS domain, week_start from completed_at",
    },
]


def _load_file(path: Path) -> str:
    """Load file content or return placeholder if not found."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"Could not load example {path}: {e}")
    return f"-- Example file not found: {path.name} --"


def _infer_domain_from_model_name(model_name: str) -> str:
    """Infer domain from gold model name (e.g. gold_qualys_* -> qualys)."""
    name_lower = model_name.lower()
    for domain in ("qualys", "snyk", "cornerstone", "csod"):
        if domain in name_lower:
            return domain
    return "qualys"  # default


def load_examples_for_domain(
    domain: str,
    max_examples: int = 2,
) -> List[dict]:
    """
    Load dbt SQL examples for the given domain.

    Returns list of dicts with keys: name, sql, (optional) note.
    Always includes one same-domain example + one cross-domain for generalization.
    """
    same_domain = [e for e in EXAMPLE_PAIRS if e["domain"] == domain]
    other_domains = [e for e in EXAMPLE_PAIRS if e["domain"] != domain]

    selected: List[dict] = []
    if same_domain:
        selected.append(same_domain[0])
    if other_domains and len(selected) < max_examples:
        selected.append(other_domains[0])
    if len(selected) < max_examples and other_domains and len(other_domains) > 1:
        selected.append(other_domains[1])

    result: List[dict] = []
    for ex in selected[:max_examples]:
        sql_content = _load_file(_EXAMPLES_DIR / ex["sql_path"])
        result.append({
            "name": ex["name"],
            "sql": sql_content,
            "note": ex.get("note", ""),
        })
    return result


def load_examples_for_model(
    model_name: str,
    max_examples: int = 2,
) -> List[dict]:
    """
    Load dbt SQL examples for a gold model, inferring domain from model name.

    Returns list of dicts with keys: name, sql.
    """
    domain = _infer_domain_from_model_name(model_name)
    return load_examples_for_domain(domain, max_examples)
