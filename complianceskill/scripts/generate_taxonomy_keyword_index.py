#!/usr/bin/env python3
"""
Generate taxonomy_keyword_index.json from dashboard domain taxonomy.

Builds a compact keyword -> [domain_ids] index for fast domain lookup.
Reduces taxonomy slice size when matching or including in prompts.

Usage (from complianceskill/ with venv active):
    python scripts/generate_taxonomy_keyword_index.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def main() -> int:
    from app.agents.dashboard_agent.taxonomy_matcher import build_and_save_keyword_index
    path = build_and_save_keyword_index()
    print(f"Built taxonomy_keyword_index.json: {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
