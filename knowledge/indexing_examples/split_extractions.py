"""
Example: Split extraction results from indexed documents.

This script demonstrates how to use the ExtractionSplitter utility to split
documents containing combined extraction results into separate documents.
"""
import asyncio
import json
import logging
from pathlib import Path

from app.indexing.utils import ExtractionSplitter
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def split_extractions_from_preview_file(preview_file_path: str):
    """
    Load a preview JSON file and split extraction results into separate documents.
    
    Args:
        preview_file_path: Path to the preview JSON file
    """
    preview_path = Path(preview_file_path)
    
    if not preview_path.exists():
        logger.error(f"Preview file not found: {preview_path}")
        return
    
    logger.info(f"Loading preview file: {preview_path}")
    
    # Load the preview file
    with open(preview_path, 'r') as f:
        preview_data = json.load(f)
    
    documents_data = preview_data.get("documents", [])
    logger.info(f"Found {len(documents_data)} documents in preview file")
    
    # Convert to Document objects
    original_docs = []
    for doc_data in documents_data:
        doc = Document(
            page_content=doc_data.get("page_content", ""),
            metadata=doc_data.get("metadata", {})
        )
        original_docs.append(doc)
    
    # Initialize splitter
    splitter = ExtractionSplitter()
    
    # Split documents
    logger.info("Splitting extraction results...")
    split_docs = splitter.split_documents(original_docs)
    
    logger.info(f"Split {len(original_docs)} documents into {len(split_docs)} separate documents")
    
    # Group by extraction type
    by_type = {}
    for doc in split_docs:
        extraction_type = doc.metadata.get("extraction_type", "unknown")
        if extraction_type not in by_type:
            by_type[extraction_type] = []
        by_type[extraction_type].append(doc)
    
    # Print summary
    logger.info("\n" + "="*50)
    logger.info("Extraction Split Summary")
    logger.info("="*50)
    for extraction_type, docs in by_type.items():
        logger.info(f"{extraction_type}: {len(docs)} documents")
    
    # Save split documents to a new file
    output_file = preview_path.parent / f"{preview_path.stem}_split.json"
    
    split_documents_data = []
    for i, doc in enumerate(split_docs):
        split_documents_data.append({
            "index": i,
            "page_content": doc.page_content,
            "metadata": doc.metadata,
            "content_length": len(doc.page_content),
            "metadata_keys": list(doc.metadata.keys())
        })
    
    output_data = {
        "metadata": {
            **preview_data.get("metadata", {}),
            "split": True,
            "original_document_count": len(original_docs),
            "split_document_count": len(split_docs)
        },
        "documents": split_documents_data
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    logger.info(f"\nSplit documents saved to: {output_file}")
    logger.info(f"Total documents: {len(split_docs)}")
    
    return split_docs


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python split_extractions.py <preview_json_file>")
        print("\nExample:")
        print("  python split_extractions.py indexing_preview/riskmanagement_risk_controls/riskmanagement_risk_controls_20260121_013801_compliance_Risk_Management.json")
        sys.exit(1)
    
    preview_file = sys.argv[1]
    asyncio.run(split_extractions_from_preview_file(preview_file))

