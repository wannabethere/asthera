#!/usr/bin/env python3
"""
Standalone script to split policy documents JSON file by extraction_type.

This script takes a policy documents JSON file and splits it into separate files
based on extraction_type, so each file can be ingested individually into the
appropriate ChromaDB stores.

Usage:
    python3 split_policy_documents.py \
        --input-file indexing_preview/policy_documents/policy_documents_20260121_175908_compliance_Policy.json \
        --output-dir indexing_preview/policy_documents

    # Or with custom output directory
    python3 split_policy_documents.py \
        --input-file path/to/policy_documents.json \
        --output-dir path/to/output
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def split_policy_documents(
    input_file: Path,
    output_dir: Path,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Split a policy documents JSON file by extraction_type.
    
    Args:
        input_file: Path to input JSON file
        output_dir: Directory to write split files
        dry_run: If True, only show what would be created without actually creating files
        
    Returns:
        Dictionary with split results
    """
    logger.info(f"Loading policy documents from: {input_file}")
    
    # Load input file
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading input file: {e}")
        raise
    
    # Get metadata and documents
    metadata = data.get("metadata", {})
    documents = data.get("documents", [])
    
    logger.info(f"Loaded {len(documents)} documents from {input_file.name}")
    
    # Group documents by extraction_type
    documents_by_type = defaultdict(list)
    for doc in documents:
        extraction_type = doc.get("metadata", {}).get("extraction_type", "unknown")
        documents_by_type[extraction_type].append(doc)
    
    logger.info(f"Documents grouped by extraction_type:")
    for ext_type, docs in documents_by_type.items():
        logger.info(f"  {ext_type}: {len(docs)} documents")
    
    # Create output directory if it doesn't exist
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate base filename from input file
    input_stem = input_file.stem  # e.g., "policy_documents_20260121_175908_compliance_Policy"
    
    # Create split files
    split_files = {}
    results = {
        "input_file": str(input_file),
        "output_dir": str(output_dir),
        "total_documents": len(documents),
        "split_files": {},
        "dry_run": dry_run
    }
    
    for extraction_type, docs in documents_by_type.items():
        # Create new filename with extraction_type suffix
        output_filename = f"{input_stem}_{extraction_type}.json"
        output_path = output_dir / output_filename
        
        # Create new metadata for split file
        split_metadata = metadata.copy()
        split_metadata["split"] = True
        split_metadata["original_file"] = input_file.name
        split_metadata["extraction_type"] = extraction_type
        split_metadata["document_count"] = len(docs)
        split_metadata["original_document_count"] = len(documents)
        split_metadata["split_at"] = datetime.now().isoformat()
        
        # Create split file data
        split_data = {
            "metadata": split_metadata,
            "documents": docs
        }
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would create: {output_path.name} ({len(docs)} documents)")
            results["split_files"][extraction_type] = {
                "path": str(output_path),
                "document_count": len(docs),
                "dry_run": True
            }
        else:
            # Write split file
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(split_data, f, indent=2, ensure_ascii=False)
                logger.info(f"  ✓ Created: {output_path.name} ({len(docs)} documents)")
                split_files[extraction_type] = str(output_path)
                results["split_files"][extraction_type] = {
                    "path": str(output_path),
                    "document_count": len(docs),
                    "success": True
                }
            except Exception as e:
                logger.error(f"  ✗ Error creating {output_path.name}: {e}")
                results["split_files"][extraction_type] = {
                    "path": str(output_path),
                    "document_count": len(docs),
                    "success": False,
                    "error": str(e)
                }
    
    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Split policy documents JSON file by extraction_type",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--input-file",
        type=str,
        required=True,
        help="Path to input policy documents JSON file"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory to write split files (default: same directory as input file)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode: show what would be created without actually creating files"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    input_file = Path(args.input_file).resolve()
    if not input_file.exists():
        logger.error(f"Input file does not exist: {input_file}")
        return 1
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        # Default to same directory as input file
        output_dir = input_file.parent
    
    logger.info("=" * 80)
    logger.info("Split Policy Documents")
    logger.info("=" * 80)
    logger.info(f"Input File: {input_file}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("")
    
    # Split documents
    try:
        results = split_policy_documents(
            input_file=input_file,
            output_dir=output_dir,
            dry_run=args.dry_run
        )
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("Split Summary")
        logger.info("=" * 80)
        logger.info(f"Total Documents: {results['total_documents']}")
        logger.info(f"Split Files Created: {len(results['split_files'])}")
        for ext_type, file_info in results["split_files"].items():
            status = "✓" if file_info.get("success") or file_info.get("dry_run") else "✗"
            logger.info(f"  {status} {ext_type}: {file_info['document_count']} documents → {Path(file_info['path']).name}")
        logger.info("=" * 80)
        
        if not args.dry_run:
            logger.info("")
            logger.info("Next steps:")
            logger.info("  You can now ingest each split file individually using:")
            logger.info("  python -m indexing_cli.ingest_preview_files \\")
            logger.info("      --preview-dir <output_dir> \\")
            logger.info("      --content-types policy_documents")
        
        return 0
    except Exception as e:
        logger.error(f"Error splitting policy documents: {e}")
        logger.debug("", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

