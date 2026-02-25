"""
Validate SQL from DS RAG demo output against the PostgreSQL connection (cornerstone).

Uses app.settings for Postgres connection. Can:
- Parse demo_output.txt and validate step SQLs + combined SQL per test case
- Validate a single SQL string
- Validate step_sqls dict directly

Run:
  python -m tests.sql_validator_demo
  python -m tests.sql_validator_demo -f demo_output.txt
  python -m tests.sql_validator_demo -f demo_output.txt -o validation_report.txt
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Add agents to path for app imports
agents_dir = Path(__file__).resolve().parent.parent
if str(agents_dir) not in sys.path:
    sys.path.insert(0, str(agents_dir))

from app.utils.sql_validator import (
    ValidationResult,
    validate_combined_sql,
    validate_sql,
    validate_step_pipeline,
)


def _parse_demo_output(path: Path) -> list:
    """
    Parse demo_output.txt and yield test-case blocks with step_sqls and combined_sql.

    Format: # TEST CASE N / # Query: ... then ## STEP: step_N with JSON block,
    then ## STAGE: Combined SQL (from steps) with raw SQL.
    """
    content = path.read_text(encoding="utf-8")
    blocks = []

    # Split by TEST CASE sections
    tc_sections = re.split(r"#+\s*TEST CASE (\d+)\s*#+", content)
    for i in range(1, len(tc_sections), 2):
        test_case_num = int(tc_sections[i])
        section = tc_sections[i + 1] if i + 1 < len(tc_sections) else ""
        query_match = re.search(r"# Query:\s*(.+?)(?=\n#|$)", section, re.DOTALL)
        query = (query_match.group(1).strip() if query_match else "")[:100]

        step_sqls = {}
        for m in re.finditer(r"## STEP:\s*(step_\d+)", section):
            step_key = m.group(1)
            rest = section[m.end() :]
            brace = rest.find("{")
            if brace < 0:
                continue
            depth = 0
            start = brace
            for i, c in enumerate(rest[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            blob = json.loads(rest[start : i + 1])
                            sql = blob.get("sql_generated", "")
                            if sql and sql != "(not available)":
                                step_sqls[step_key] = sql
                        except json.JSONDecodeError:
                            pass
                        break

        combined_match = re.search(
            r"## STAGE: Combined SQL \(from steps\)\s*\n[=\s]*\n([\s\S]*?)(?=\n={50,}|## STAGE:|$)",
            section,
        )
        combined_sql = (combined_match.group(1).strip() if combined_match else "").strip()
        if combined_sql.startswith("{"):
            combined_sql = ""

        blocks.append({
            "test_case": test_case_num,
            "query": query,
            "step_sqls": step_sqls,
            "combined_sql": combined_sql,
        })

    return blocks


def run_validation(
    demo_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> None:
    """Run validation and print/save results."""
    if demo_path and demo_path.exists():
        blocks = _parse_demo_output(demo_path)
        print(f"Parsed {len(blocks)} test cases from {demo_path}")
    else:
        # Single test: validate step_1 only
        blocks = [{
            "test_case": 1,
            "query": "Manual validation",
            "step_sqls": {
                "step_1": "SELECT division, completed_date FROM csod_training_records WHERE is_completed = true LIMIT 5",
            },
            "combined_sql": "",
        }]
        print("No demo file; running single step_1 validation")

    all_results = []
    for block in blocks:
        tc = block.get("test_case", "?")
        query = (block.get("query") or "")[:80]
        step_sqls = block.get("step_sqls", {})
        combined_sql = (block.get("combined_sql") or "").strip()

        step_results = validate_step_pipeline(step_sqls)
        combined_result = None
        if combined_sql:
            combined_result = validate_combined_sql(combined_sql)

        summary = {
            "test_case": tc,
            "query": query,
            "step_results": {k: {"success": v.success, "error": v.error, "row_count": v.row_count} for k, v in step_results.items()},
            "combined_result": {"success": combined_result.success, "error": combined_result.error, "row_count": combined_result.row_count} if combined_result else None,
        }
        all_results.append(summary)

        passed = all(r.success for r in step_results.values())
        if combined_result:
            passed = passed and combined_result.success
        status = "PASS" if passed else "FAIL"
        print(f"\nTC{tc} [{status}] {query}...")
        for k, r in step_results.items():
            sym = "✓" if r.success else "✗"
            err = f" — {r.error[:60]}..." if r.error and len(r.error) > 60 else (f" — {r.error}" if r.error else "")
            print(f"  {sym} {k}: rows={r.row_count or 'N/A'}{err}")
        if combined_result:
            sym = "✓" if combined_result.success else "✗"
            err = f" — {combined_result.error[:60]}..." if combined_result.error and len(combined_result.error) > 60 else (f" — {combined_result.error}" if combined_result.error else "")
            print(f"  {sym} combined_sql: rows={combined_result.row_count or 'N/A'}{err}")

    if output_path:
        output_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
        print(f"\nReport saved to {output_path}")


def main() -> None:
    agents_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Validate DS RAG SQL against PostgreSQL (cornerstone)")
    parser.add_argument(
        "-f", "--file",
        type=Path,
        default=None,
        help="Path to demo_output.txt",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to save validation report JSON",
    )
    args = parser.parse_args()
    demo_path = args.file or (agents_dir / "demo_output.txt")
    run_validation(
        demo_path=demo_path if demo_path.exists() else None,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
