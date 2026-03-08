"""
Few-shot example loader for CubeJS schema generation.
"""
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Prompt directory for cubejs
_CUBEJS_PROMPTS = Path(__file__).parent / "prompts"
_EXAMPLES_DIR = _CUBEJS_PROMPTS / "examples"

# Example pairs: domain -> (sql_name, sql_path, cube_path)
# When examples don't exist, we return a minimal placeholder
EXAMPLE_PAIRS: List[dict] = [
    {
        "domain": "qualys",
        "sql_name": "gold_qualys_vulnerabilities_weekly_snapshot",
        "sql_path": "gold_qualys_vulnerabilities_weekly_snapshot.sql",
        "cube_path": "QualysVulnerabilities.js",
        "note": "Shows: composite PK, criticalVulnCount, openVulnCount, avgDaysOpen, pre-agg with timeDimension",
    },
    {
        "domain": "snyk",
        "sql_name": "gold_snyk_issues_weekly_snapshot",
        "sql_path": "gold_snyk_issues_weekly_snapshot.sql",
        "cube_path": "SnykIssues.js",
        "note": "Shows: JSON CVSS extraction pattern, ->>'key'::numeric, standalone cube (no joins)",
    },
    {
        "domain": "qualys",
        "sql_name": "gold_qualys_hosts_weekly_snapshot",
        "sql_path": "gold_qualys_hosts_weekly_snapshot.sql",
        "cube_path": "QualysHosts.js",
        "note": "Shows: MAX-type aggregate measures on pre-summed rows, agentCoveragePct derived measure",
    },
    {
        "domain": "cornerstone",
        "sql_name": "gold_cornerstone_completions_weekly_snapshot",
        "sql_path": "gold_cornerstone_completions_weekly_snapshot.sql",
        "cube_path": "CornerstoneCompletions.js",
        "note": "Shows: CSOD/LMS domain cube structure",
    },
]


def load_examples_for_domain(domain: str, max_examples: int = 2) -> str:
    """
    Returns formatted few-shot block for the given domain.

    Always includes one same-domain example + one cross-domain example for generalization.
    If example files don't exist, returns a minimal placeholder with structure hints.
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

    blocks: List[str] = []
    for i, ex in enumerate(selected[:max_examples], 1):
        sql_content = _load_file(_EXAMPLES_DIR / ex["sql_path"])
        cube_content = _load_file(_EXAMPLES_DIR / ex["cube_path"])

        blocks.append(
            f"### Example {i} — {ex['domain']} domain\n"
            f"-- INPUT SQL --\n{sql_content}\n\n"
            f"-- OUTPUT CUBE.JS --\n{cube_content}"
        )

    if not blocks:
        return (
            "### No examples available\n"
            "Generate valid Cube.js schema following the system prompt rules. "
            "Include connectionId as first dimension, composite pk, and pre-aggregations."
        )

    return "\n\n".join(blocks)


def _load_file(path: Path) -> str:
    """Load file content or return placeholder if not found."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not load example {path}: {e}")
    return f"-- Example file not found: {path.name} --"
