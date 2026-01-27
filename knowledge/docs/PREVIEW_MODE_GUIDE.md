# Preview Mode Quick Guide

## Overview

Preview mode allows you to generate preview files instead of indexing directly to the vector database. This is useful for:
- Reviewing extracted documents before committing
- Testing extraction pipelines
- Debugging document processing
- Validating data quality

## Quick Start

### Method 1: Using Python Script

```python
import asyncio
from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

async def main():
    # Initialize service with preview_mode=True
    service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=get_chromadb_client(),
        embeddings_model=get_embeddings_model(),
        llm=get_llm(temperature=0.2),
        preview_mode=True,  # Enable preview mode
        preview_output_dir="indexing_preview"  # Output directory
    )
    
    # Index a policy document
    result = await service.index_policy_document(
        file_path="path/to/policy.pdf",
        framework="SOC2",
        domain="compliance"
    )
    
    # Check where files were saved
    if result.get("preview_mode"):
        file_path = result.get("file_storage", {}).get("file_path")
        print(f"Preview saved to: {file_path}")

asyncio.run(main())
```

### Method 2: Using CLI

```bash
# Preview a policy document
python -m indexing_cli.index_compliance \
    --index-policies \
    --policy-pdf path/to/Full\ Policy\ Packet.pdf \
    --preview \
    --preview-dir indexing_preview

# Preview all document types
python -m indexing_cli.index_compliance \
    --comprehensive \
    --policy-pdf path/to/policy.pdf \
    --risk-controls-excel path/to/risk_controls.xlsx \
    --preview
```

### Method 3: Run Example Script

```bash
# From the indexing directory
python -m indexing_examples.run_preview_mode
```

## Output Structure

Preview files are saved to `indexing_preview/` (or your custom directory):

```
indexing_preview/
├── policy_documents/
│   ├── policy_documents_20240101_120000_compliance_Policy.json
│   └── policy_documents_summary_20240101_120000.txt
├── risk_controls/
│   ├── risk_controls_20240101_120000_compliance_Risk_Management.json
│   └── risk_controls_summary_20240101_120000.txt
└── compliance_controls/
    └── ...
```

## What Gets Saved

Each JSON file contains:
- **Metadata**: Content type, domain, product name, timestamp, document count
- **Documents**: Full document content with all metadata
- **Extraction Results**: Results from extraction pipelines (entities, fields, evidence, etc.)

The summary `.txt` file provides a human-readable overview.

## Common Use Cases

### 1. Preview Policy Documents

```python
result = await service.index_policy_document(
    file_path="policy.pdf",
    framework="SOC2",
    domain="compliance"
)
```

### 2. Preview Risk Controls

```python
result = await service.index_risk_controls(
    file_path="risk_controls.xlsx",
    framework="Risk Management",
    domain="compliance"
)
```

### 3. Preview Compliance Controls

```python
result = await service.index_compliance_controls(
    file_path="controls.pdf",
    framework="SOC2",
    domain="compliance"
)
```

### 4. Preview API Documentation

```python
result = await service.index_api_docs(
    api_docs=[...],
    product_name="My Product",
    domain="Assets"
)
```

### 5. Preview Product Information

```python
result = await service.index_product_info(
    product_name="Snyk",
    product_purpose="Developer security platform",
    product_docs_link="https://docs.snyk.io",
    key_concepts=["Vulnerability Scanning", "Container Security"],
    domain="Security"
)
```

## After Reviewing Preview Files

Once you've reviewed the preview files and confirmed everything looks good:

1. **Disable preview mode** and run again to index to database:

```python
service = ComprehensiveIndexingService(
    # ... other params ...
    preview_mode=False  # Disable preview mode
)

# Now documents will be indexed to ChromaDB/Qdrant
result = await service.index_policy_document(...)
```

2. **Or use CLI without --preview flag**:

```bash
python -m indexing_cli.index_compliance \
    --index-policies \
    --policy-pdf path/to/policy.pdf
```

## Custom Output Directory

```python
service = ComprehensiveIndexingService(
    preview_mode=True,
    preview_output_dir="my_custom_preview_dir"  # Custom directory
)
```

## Key Points

- **Preview mode saves to files, not database**: Documents are saved as JSON files
- **All extraction pipelines still run**: You get the same extracted content as database mode
- **Easy to review**: JSON files are human-readable and include summaries
- **No database changes**: Safe to test without affecting your vector database
- **Switch easily**: Just change `preview_mode=False` to index to database

## Example Workflow

1. **Run in preview mode** to generate files
2. **Review JSON files** in `indexing_preview/`
3. **Check summary files** for quick overview
4. **Verify extraction quality** (entities, fields, evidence, etc.)
5. **Run again with preview_mode=False** to index to database

## Troubleshooting

- **Files not appearing?** Check the `preview_output_dir` path
- **Preview mode not working?** Ensure `preview_mode=True` in constructor
- **Want to see what would be indexed?** Check the JSON files - they contain exactly what would be stored

