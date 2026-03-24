"""
Ingest LMS causal seed JSON files into four Qdrant collections (settings-driven).

Uses app.storage.vector_store (Qdrant via DocumentQdrantStore) and paths from
app.core.settings (CONFIG_DIR + LMS_*_PATH).

Collections:
    lms_causal_nodes, lms_causal_edges, lms_focus_area_taxonomy, lms_use_case_groups
    (names overridable via LMS_CAUSAL_*_COLLECTION env / Settings)

Usage (from complianceskill repo root, PYTHONPATH set):
    python -m app.ingestion.ingest_lms_causal_qdrant

    python -m app.ingestion.ingest_lms_causal_qdrant --skip-edges
    python -m app.ingestion.ingest_lms_causal_qdrant \\
        --nodes /path/to/lms_causal_nodes_seed.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.agents.causalgraph.vector_causal_graph_builder import ingest_lms_causal_seed_bundle
from app.core.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest LMS causal JSON seeds into Qdrant")
    parser.add_argument("--nodes", type=Path, default=None, help="Override path to nodes seed JSON")
    parser.add_argument("--edges", type=Path, default=None, help="Override path to edges JSON")
    parser.add_argument("--focus-areas", type=Path, default=None, help="Override path to focus area taxonomy JSON")
    parser.add_argument("--use-cases", type=Path, default=None, help="Override path to use case groups JSON")
    parser.add_argument("--skip-nodes", action="store_true")
    parser.add_argument("--skip-edges", action="store_true")
    parser.add_argument("--skip-focus-areas", action="store_true")
    parser.add_argument("--skip-use-case-groups", action="store_true")
    args = parser.parse_args()

    s = get_settings()
    logger.info(
        "Qdrant target: %s:%s (VECTOR_STORE_TYPE=%s)",
        s.QDRANT_HOST or "localhost",
        s.QDRANT_PORT,
        s.VECTOR_STORE_TYPE,
    )
    logger.info("CONFIG_DIR=%s", s.CONFIG_DIR)

    counts = asyncio.run(
        ingest_lms_causal_seed_bundle(
            nodes_path=args.nodes,
            edges_path=args.edges,
            focus_areas_path=args.focus_areas,
            use_case_groups_path=args.use_cases,
            skip_nodes=args.skip_nodes,
            skip_edges=args.skip_edges,
            skip_focus_areas=args.skip_focus_areas,
            skip_use_case_groups=args.skip_use_case_groups,
        )
    )
    logger.info("Done: %s", counts)


if __name__ == "__main__":
    main()
