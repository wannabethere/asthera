# MDL Schema Indexing Guide

This guide explains how to ingest MDL (Model Definition Language) JSON files using the indexing processors with preview/run options.

## Quick Start

### Option 1: Direct Script for Snyk MDL

The simplest way to index `snyk_mdl1.json`:

```bash
# Preview mode (recommended first - saves to files)
python -m indexing_examples.index_snyk_mdl --preview

# Index to database
python -m indexing_examples.index_snyk_mdl
```

### Option 2: Generic MDL Indexing CLI

For any MDL file:

```bash
# Preview mode
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk \
    --preview

# Index to database
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk

# Use DB schema processor instead
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk \
    --processor db_schema \
    --preview
```

## Processor Types

### 1. Schema Processor (`--processor schema`)

Uses `index_schema_from_mdl` which:
- Creates table descriptions using `TableDescriptionProcessor`
- Indexes table definitions with columns
- Indexes individual column definitions
- Indexes schema-level descriptions

**Best for**: Comprehensive schema indexing with table descriptions

### 2. DB Schema Processor (`--processor db_schema`)

Uses `index_db_schema_from_mdl` which:
- Uses `DBSchemaProcessor` to create DDL-style documents
- Processes models, views, and metrics
- Creates documents in DBSchema format

**Best for**: DDL-style schema documentation

## Preview Mode

Preview mode saves documents to JSON files instead of indexing to the database. This allows you to:

1. **Review extracted content** before committing to database
2. **Validate data quality** and extraction pipelines
3. **Debug processing issues** without affecting the database
4. **Test different configurations** safely

### Preview Output Structure

```
indexing_preview/
├── table_descriptions/
│   ├── table_descriptions_20240101_120000_security_Snyk.json
│   └── table_descriptions_summary_20240101_120000.txt
├── schema_descriptions/
│   ├── schema_descriptions_20240101_120000_security_Snyk.json
│   └── schema_descriptions_summary_20240101_120000.txt
└── db_schema/
    ├── db_schema_20240101_120000_security_Snyk.json
    └── db_schema_summary_20240101_120000.txt
```

### Preview File Format

Each JSON file contains:
- **Metadata**: Content type, domain, product name, document count, timestamp
- **Documents**: Array of document objects with:
  - `page_content`: The document content
  - `metadata`: Document metadata
  - `content_length`: Character count
  - `metadata_keys`: List of metadata keys

## Using in Python Code

### Preview Mode Example

```python
import asyncio
from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm
import json

async def index_mdl_preview():
    # Load MDL file
    with open("path/to/snyk_mdl1.json", "r") as f:
        mdl_data = json.load(f)
    
    # Initialize service with preview mode
    service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=get_chromadb_client(),
        embeddings_model=get_embeddings_model(),
        llm=get_llm(temperature=0.2),
        preview_mode=True,  # Enable preview mode
        preview_output_dir="indexing_preview"
    )
    
    # Index schema
    result = await service.index_schema_from_mdl(
        mdl_data=mdl_data,
        product_name="Snyk",
        domain="security",
        use_table_description_structure=True
    )
    
    print(f"Preview saved to: indexing_preview/")
    return result

asyncio.run(index_mdl_preview())
```

### Database Mode Example

```python
import asyncio
from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm
import json

async def index_mdl_to_database():
    # Load MDL file
    with open("path/to/snyk_mdl1.json", "r") as f:
        mdl_data = json.load(f)
    
    # Initialize service (preview_mode=False by default)
    service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=get_chromadb_client(),
        embeddings_model=get_embeddings_model(),
        llm=get_llm(temperature=0.2),
        preview_mode=False  # Index to database
    )
    
    # Index schema
    result = await service.index_schema_from_mdl(
        mdl_data=mdl_data,
        product_name="Snyk",
        domain="security",
        use_table_description_structure=True
    )
    
    print(f"Indexed {result['tables_indexed']} tables")
    return result

asyncio.run(index_mdl_to_database())
```

## Using Processors Directly

You can also use the processors directly without the service:

```python
from app.indexing.processors import TableDescriptionProcessor, DBSchemaProcessor
import json

# Load MDL
with open("path/to/snyk_mdl1.json", "r") as f:
    mdl_data = json.load(f)

# Use TableDescriptionProcessor
processor = TableDescriptionProcessor()
documents = await processor.process_mdl(
    mdl=mdl_data,
    project_id="Snyk",
    product_name="Snyk",
    domain="security"
)

# Use DBSchemaProcessor
db_processor = DBSchemaProcessor()
db_documents = await db_processor.process_mdl(
    mdl=mdl_data,
    project_id="Snyk",
    product_name="Snyk",
    domain="security"
)
```

## Command Line Options

### index_mdl.py (CLI)

```
--mdl-file PATH          Path to MDL JSON file (required)
--product-name NAME      Product name (required)
--domain DOMAIN          Domain filter (optional)
--processor TYPE         Processor type: 'schema' or 'db_schema' (default: schema)
--preview                Enable preview mode
--preview-dir DIR        Preview output directory (default: indexing_preview)
--vector-store TYPE      Vector store: 'chroma' or 'qdrant' (default: chroma)
```

Usage: `python -m indexing_cli.index_mdl [options]`

### index_snyk_mdl.py

```
--preview                Enable preview mode
```

## Workflow Recommendation

1. **First Run**: Use preview mode to review extracted documents
   ```bash
   python -m indexing_examples.index_snyk_mdl --preview
   ```

2. **Review**: Check the JSON files in `indexing_preview/` to verify:
   - Documents are extracted correctly
   - Metadata is accurate
   - Content quality is good

3. **Index to Database**: Once satisfied, run without preview mode
   ```bash
   python -m indexing_examples.index_snyk_mdl
   ```

## Troubleshooting

### File Not Found

If the script can't find `snyk_mdl1.json`, update the path in `index_snyk_mdl.py` or use the CLI:

```bash
python -m indexing_cli.index_mdl \
    --mdl-file /full/path/to/snyk_mdl1.json \
    --product-name Snyk \
    --preview
```

### Preview Files Not Appearing

- Check the `preview_output_dir` path
- Ensure `preview_mode=True` is set
- Check file permissions

### Processing Errors

- Verify the MDL file is valid JSON
- Check that the MDL has the expected structure (models, columns, etc.)
- Review logs for specific error messages

## Related Files

- `comprehensive_indexing_service.py`: Main indexing service with preview mode support
- `processors/table_description_processor.py`: TableDescription processor
- `processors/db_schema_processor.py`: DBSchema processor
- `storage/file_storage.py`: File storage for preview mode

