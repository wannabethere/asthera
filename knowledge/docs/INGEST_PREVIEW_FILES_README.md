# Ingest Preview Files Utility

This utility ingests all preview JSON files from the `indexing_preview` directory into ChromaDB stores **without re-running extraction pipelines**. This is useful when you've already processed documents in preview mode and want to load them into the database for testing contextual reasoning.

## Features

- ✅ Automatically discovers all preview files in the preview directory
- ✅ Maps content types to appropriate ChromaDB stores
- ✅ Handles policy documents splitting by extraction_type (context, entities, requirements, etc.)
- ✅ Dry-run mode to preview what would be ingested
- ✅ Detailed logging and summary reports
- ✅ Skips pipeline processing (documents already processed)

## Usage

### Basic Usage - Ingest All Files

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix comprehensive_index
```

### Ingest Domain Knowledge, Policy Documents, Product, Risk Management, and SOC2 Controls

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix comprehensive_index \
    --content-types domain_knowledge policy_documents product_key_concepts riskmanagement_risk_controls soc2_controls
```

### Dry Run (Preview What Would Be Ingested)

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --dry-run
```

### Ingest Specific Content Types Only

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions column_definitions schema_descriptions
```


python -m indexing_cli.index_mdl_standalone \
    --mdl-file path/to/mdl.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --collections db_schema table_descriptions column_metadata


### Custom Collection Prefix

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix my_custom_prefix
```

### Force Recreate Collections (Fix Dimension Mismatches)

If you encounter embedding dimension mismatch errors, use `--force-recreate` to delete and recreate all collections:

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --force-recreate
```

This will:
1. Delete all existing collections with the specified prefix
2. Recreate them with the correct embedding dimensions
3. Then ingest all preview files

## Content Type to Store Mapping

The utility automatically maps preview file content types to ChromaDB stores:

| Preview Content Type | ChromaDB Store | Notes |
|---------------------|----------------|-------|
| `table_definitions` | `table_definitions` | Direct mapping |
| `table_descriptions` | `table_descriptions` | Direct mapping |
| `column_definitions` | `column_definitions` | Direct mapping |
| `schema_descriptions` | `schema_descriptions` | Direct mapping |
| `policy_documents` | Multiple stores | Split by `extraction_type`:
| | `policy_context` | When `extraction_type: "context"` |
| | `policy_entities` | When `extraction_type: "entities"` |
| | `policy_requirements` | When `extraction_type: "requirement"` |
| | `policy_documents` | When `extraction_type: "full_content"` |
| | `policy_evidence` | When `extraction_type: "evidence"` |
| | `policy_fields` | When `extraction_type: "fields"` |
| `domain_knowledge` | `domain_knowledge` | Direct mapping (use `type` in metadata to filter) |
| `product_key_concepts` | `product_key_concepts` | Routes to entities with `type="product"` in metadata |
| `product_docs_link` | `product_docs` | Routes to domain_knowledge with `type="product"` in metadata |
| `product_purpose` | `product_purpose` | Routes to domain_knowledge with `type="product"` in metadata |
| `riskmanagement_risk_controls` | `domain_knowledge` | Routes to domain_knowledge with `type="risk"` in metadata |
| `risk_controls` | `domain_knowledge` | Routes to domain_knowledge with `type="risk"` in metadata |
| `soc2_controls` | `compliance_controls` | Routes to compliance_controls with `framework="SOC2"` in metadata |
| `compliance_controls` | `compliance_controls` | Direct mapping |

## Example Output

```
================================================================================
Preview File Ingestion
================================================================================
Preview Directory: indexing_preview
Collection Prefix: comprehensive_index
Vector Store: chroma
Dry Run: False

Discovered 6 preview files across 6 content types
  table_definitions: 1 files
  table_descriptions: 1 files
  column_definitions: 1 files
  schema_descriptions: 1 files
  policy_documents: 1 files
  riskmanagement_risk_controls: 1 files

================================================================================
Processing table_definitions (1 files)
================================================================================
Processing file: table_definitions_20260116_023913_Snyk.json (content_type: table_definitions)
  Loaded 494 documents from table_definitions_20260116_023913_Snyk.json
  ✓ Ingested 494 documents to table_definitions

...

================================================================================
Ingestion Summary
================================================================================
Files Processed: 6
Total Documents: 1020
Documents by Store:
  column_definitions: 494
  policy_context: 1
  policy_entities: 1
  policy_requirements: 9
  risk_controls: 494
  schema_descriptions: 1
  table_definitions: 494
  table_descriptions: 494
================================================================================
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--preview-dir` | Directory containing preview files | `indexing_preview` |
| `--collection-prefix` | Prefix for ChromaDB collections | `comprehensive_index` |
| `--vector-store` | Vector store type (`chroma` or `qdrant`) | `chroma` |
| `--content-types` | Specific content types to ingest (space-separated) | All types |
| `--dry-run` | Preview mode: show what would be ingested without actually ingesting | `False` |
| `--force-recreate` | Force recreate collections: delete and recreate all collections before ingesting (fixes dimension mismatches) | `False` |

## Notes

- **Pipeline Processing**: Pipeline processing is **disabled** by default since documents are already processed. The utility loads documents directly into ChromaDB stores.

- **File Discovery**: The utility automatically discovers all JSON files in subdirectories of the preview directory. Summary files (containing "summary" in the filename) are excluded.

- **Content Type Detection**: The utility uses the `content_type` from the file metadata (more accurate) rather than the directory name when available.

- **Error Handling**: If a store is not available, the utility logs a warning and continues processing other files. Individual file errors don't stop the entire ingestion process.

## Troubleshooting

### Embedding Dimension Mismatch

If you encounter errors like:
```
✗ Error ingesting to schema_descriptions: Embedding dimension 9 does not match collection dimensionality 1536
```

This means the ChromaDB collection was created with a different embedding model. To fix:

```bash
# Use --force-recreate to delete and recreate all collections
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --force-recreate
```

This will:
- Delete all existing collections with the specified prefix
- Recreate them with the correct embedding dimensions from your current embedding model
- Then ingest all preview files

**Note**: This will delete all existing data in the collections. Make sure you have backups if needed.

### Store Not Available

If you see warnings like:
```
Store 'policy_entities' not available, skipping 1 documents
```

This means the store wasn't initialized. Check that:
1. The collection prefix matches what was used during indexing
2. The store name exists in `ComprehensiveIndexingService._init_document_stores()`

### No Files Found

If you see:
```
No preview files found to ingest
```

Check that:
1. The `--preview-dir` path is correct
2. Preview files exist in subdirectories
3. Files are JSON format (not summary .txt files)

## Integration with Testing

After ingesting preview files, you can immediately start testing contextual reasoning:

```python
from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

# Initialize service (not in preview mode)
service = ComprehensiveIndexingService(
    vector_store_type="chroma",
    persistent_client=get_chromadb_client(),
    embeddings_model=get_embeddings_model(),
    llm=get_llm(),
    collection_prefix="comprehensive_index",
    preview_mode=False,
    enable_pipeline_processing=False  # Already processed
)

# Search across all stores
results = await service.search(
    query="What are the access control requirements?",
    content_types=["policy_requirements", "policy_documents"],
    framework="policy"
)
```

