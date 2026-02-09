# Storage and Flags Guide

## Overview

The comprehensive indexing service now supports:
1. **Preview Mode**: Save documents to files before indexing in database
2. **Flag-based Indexing**: Index specific document types with flags
3. **Comprehensive Mode**: Index all document types at once

## Preview Mode

Preview mode allows you to review extracted documents before committing them to the vector database (ChromaDB/Qdrant).

### How It Works

1. Documents are processed through extraction pipelines
2. Instead of storing in vector database, they're saved to JSON files
3. You can review the files to verify extraction quality
4. Once satisfied, disable preview mode to index to database

### File Structure

```
indexing_preview/
├── policy_documents/
│   ├── policy_documents_20240101_120000_compliance_Policy.json
│   └── policy_documents_summary_20240101_120000.txt
├── risk_controls/
│   ├── risk_controls_20240101_120000_compliance_Risk_Management.json
│   └── risk_controls_summary_20240101_120000.txt
└── soc2_controls/
    ├── soc2_controls_20240101_120000_compliance_SOC2.json
    └── soc2_controls_summary_20240101_120000.txt
```

### JSON File Format

```json
{
  "metadata": {
    "content_type": "policy_documents",
    "domain": "compliance",
    "product_name": "Policy",
    "document_count": 10,
    "timestamp": "20240101_120000",
    "indexed_at": "2024-01-01T12:00:00",
    "source_file": "path/to/file.pdf"
  },
  "documents": [
    {
      "index": 0,
      "page_content": "Document content...",
      "metadata": {
        "content_type": "policy",
        "extraction_type": "context",
        ...
      },
      "content_length": 1234,
      "metadata_keys": ["content_type", "extraction_type", ...]
    }
  ]
}
```

## Flag-Based Indexing

### Individual Flags

Index specific document types:

```python
# Index only policies
service = ComprehensiveIndexingService(preview_mode=True)
await service.index_policy_document("path/to/policy.pdf")

# Index only risk controls
await service.index_risk_controls("path/to/risk_controls.xlsx")

# Index only SOC2 controls
await service.index_soc2_controls("path/to/soc2.pdf")
```

### Comprehensive Mode

Index all document types at once:

```python
# Using CLI
python -m indexing_cli.index_compliance \
    --comprehensive \
    --policy-pdf path/to/policy.pdf \
    --risk-controls-excel path/to/risk_controls.xlsx \
    --soc2-pdf path/to/soc2.pdf \
    --preview

# Programmatically
service = ComprehensiveIndexingService(preview_mode=True)
await service.index_policy_document("path/to/policy.pdf")
await service.index_risk_controls("path/to/risk_controls.xlsx")
await service.index_soc2_controls("path/to/soc2.pdf")
```

## Workflow

### Recommended Workflow

1. **Preview Individual Types**
   ```bash
   # Preview policies
   python -m indexing_cli.index_compliance \
       --index-policies \
       --policy-pdf examples/Full\ Policy\ Packet.pdf \
       --preview
   ```

2. **Review Preview Files**
   - Check JSON files in `indexing_preview/`
   - Verify extraction quality
   - Review summary files

3. **Preview All Types**
   ```bash
   # Preview everything
   python -m indexing_cli.index_compliance \
       --comprehensive \
       --policy-pdf examples/Full\ Policy\ Packet.pdf \
       --risk-controls-excel examples/Risk\ and\ Controls.xlsx \
       --preview
   ```

4. **Index to Database**
   ```bash
   # Index everything to database
   python -m indexing_cli.index_compliance \
       --comprehensive \
       --policy-pdf examples/Full\ Policy\ Packet.pdf \
       --risk-controls-excel examples/Risk\ and\ Controls.xlsx
   ```

## Programmatic Usage

### Preview Mode

```python
from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

# Initialize with preview mode
service = ComprehensiveIndexingService(
    vector_store_type="chroma",
    persistent_client=get_chromadb_client(),
    embeddings_model=get_embeddings_model(),
    llm=get_llm(),
    preview_mode=True,  # Enable preview mode
    preview_output_dir="indexing_preview"
)

# Index with preview
result = await service.index_policy_document(
    file_path="path/to/policy.pdf",
    domain="compliance"
)

# Check result
if result.get("preview_mode"):
    print(f"Preview saved to: {result['file_storage']['file_path']}")
```

### Database Mode

```python
# Initialize without preview mode
service = ComprehensiveIndexingService(
    vector_store_type="chroma",
    persistent_client=get_chromadb_client(),
    embeddings_model=get_embeddings_model(),
    llm=get_llm(),
    preview_mode=False  # Disable preview mode
)

# Index to database
result = await service.index_policy_document(
    file_path="path/to/policy.pdf",
    domain="compliance"
)

# Check result
if result.get("success"):
    print(f"Indexed {result['documents_indexed']} documents to {result['store']}")
```

## File Storage API

### Save Documents

```python
from app.indexing.storage.file_storage import FileStorage

storage = FileStorage(output_dir="indexing_preview")

result = storage.save_documents(
    documents=documents,
    content_type="policy_documents",
    domain="compliance",
    product_name="Policy"
)

print(f"Saved to: {result['file_path']}")
```

### List Preview Files

```python
# List all preview files
files = storage.list_preview_files()
for file_info in files:
    print(f"{file_info['content_type']}: {file_info['path']}")

# List files for specific content type
policy_files = storage.list_preview_files(content_type="policy_documents")
```

### Load Preview File

```python
# Load a preview file
data = storage.load_preview_file("indexing_preview/policy_documents/policy_documents_20240101_120000.json")
print(f"Loaded {data['metadata']['document_count']} documents")
```

## Benefits

1. **Quality Assurance**: Review extracted data before indexing
2. **Debugging**: Easier to debug extraction issues
3. **Selective Indexing**: Index only what you need
4. **Incremental Updates**: Update specific document types without re-indexing everything
5. **Backup**: Preview files serve as backups of extracted data

