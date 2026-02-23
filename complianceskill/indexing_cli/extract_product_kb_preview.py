"""
Extract Product KB entities and contextual edges, then write a new preview directory.

Uses the same CollectionFactory store names as ingest_preview_files:
- product_purpose -> domain_knowledge (type=product)
- product_key_concepts -> entities (type=product)
- contextual_edges -> contextual_edges

Run this on kb-dump-utility preview (enriched + enriched_vendor), then point
ingest_preview_files at the output preview dir to ingest product entities and edges.

Usage:
  # From flowharmonicai/knowledge (or PYTHONPATH including knowledge)
  python -m indexing_cli.extract_product_kb_preview \
    --preview-dir /path/to/kb-dump-utility/preview \
    --output-dir /path/to/kb-dump-utility/preview_product_kb \
    [--enriched-subdirs enriched enriched_vendor] \
    [--product-key-concepts /path/to/product_key_concepts.json]
"""

import argparse
import json
import logging
from pathlib import Path

try:
    from app.indexing.product_kb_extraction import run_extraction
except Exception:
    from indexing_cli.product_kb_extraction_impl import run_extraction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def write_preview(
    output_dir: Path,
    product_info_documents: list,
    product_key_concept_documents: list,
    contextual_edge_documents: list,
) -> None:
    """
    Write preview JSON files in the format ingest_preview_files expects.

    Structure:
      output_dir/product_purpose/product_kb_info.json   -> documents
      output_dir/product_key_concepts/product_kb_concepts.json -> documents
      output_dir/contextual_edges/product_kb_edges.json -> documents
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # product_purpose -> domain_knowledge (type=product)
    (output_dir / "product_purpose").mkdir(parents=True, exist_ok=True)
    path_info = output_dir / "product_purpose" / "product_kb_info.json"
    with open(path_info, "w", encoding="utf-8") as f:
        json.dump({"documents": product_info_documents}, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {len(product_info_documents)} product info docs -> {path_info}")

    # product_key_concepts -> entities (type=product)
    (output_dir / "product_key_concepts").mkdir(parents=True, exist_ok=True)
    path_concepts = output_dir / "product_key_concepts" / "product_kb_concepts.json"
    with open(path_concepts, "w", encoding="utf-8") as f:
        json.dump({"documents": product_key_concept_documents}, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {len(product_key_concept_documents)} key concept docs -> {path_concepts}")

    # contextual_edges -> contextual_edges collection
    (output_dir / "contextual_edges").mkdir(parents=True, exist_ok=True)
    path_edges = output_dir / "contextual_edges" / "product_kb_edges.json"
    with open(path_edges, "w", encoding="utf-8") as f:
        json.dump({"documents": contextual_edge_documents}, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {len(contextual_edge_documents)} contextual edges -> {path_edges}")

    # index.json for the new preview (self-describing for ingest_preview_files)
    index = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "source": "extract_product_kb_preview",
        "content_types": {
            "product_purpose": {"files": 1, "documents": len(product_info_documents)},
            "product_key_concepts": {"files": 1, "documents": len(product_key_concept_documents)},
            "contextual_edges": {"files": 1, "documents": len(contextual_edge_documents)},
        },
        "ingest_command": "python -m indexing_cli.ingest_preview_files --preview-dir " + str(output_dir),
    }
    with open(output_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    logger.info("Wrote index.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract product KB entities and contextual edges; write new preview for ingest_preview_files."
    )
    parser.add_argument(
        "--preview-dir",
        type=Path,
        required=True,
        help="Preview directory (e.g. kb-dump-utility/preview) containing enriched/ and optionally enriched_vendor/",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output preview directory (e.g. preview_product_kb). ingest_preview_files can use this as --preview-dir.",
    )
    parser.add_argument(
        "--enriched-subdirs",
        nargs="*",
        default=["enriched", "enriched_vendor"],
        help="Subdirs under preview-dir to load enriched JSON from (default: enriched enriched_vendor)",
    )
    parser.add_argument(
        "--product-key-concepts",
        type=Path,
        default=None,
        help="Optional JSON path: product name -> list of key concepts. Default uses built-in Snyk concepts.",
    )
    args = parser.parse_args()

    preview_dir = Path(args.preview_dir)
    if not preview_dir.exists() or not preview_dir.is_dir():
        logger.error(f"Preview dir does not exist or is not a directory: {preview_dir}")
        return

    result = run_extraction(
        preview_dir=preview_dir,
        enriched_subdirs=args.enriched_subdirs or None,
        product_key_concepts_path=Path(args.product_key_concepts) if args.product_key_concepts else None,
    )

    stats = result.get("stats", {})
    logger.info("Extraction stats: %s", stats)

    write_preview(
        output_dir=Path(args.output_dir),
        product_info_documents=result.get("product_info_documents", []),
        product_key_concept_documents=result.get("product_key_concept_documents", []),
        contextual_edge_documents=result.get("contextual_edge_documents", []),
    )

    logger.info("Done. Ingest with: python -m indexing_cli.ingest_preview_files --preview-dir %s", args.output_dir)


if __name__ == "__main__":
    main()
