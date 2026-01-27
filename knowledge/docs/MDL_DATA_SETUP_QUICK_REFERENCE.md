# MDL Data Setup Quick Reference

## Quick Start

### 1. Check Available Preview Files

```bash
ls -la knowledge/indexing_preview/
```

You should see:
- `table_definitions/` - Table structure definitions
- `table_descriptions/` - Table descriptions
- `schema_descriptions/` - Schema categories
- `column_definitions/` - Column definitions

### 2. Ingest Preview Files

```bash
cd knowledge

# Ingest all preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions schema_descriptions column_definitions
```

### 3. Ingest MDL to Contextual Graph

If you have MDL JSON files:

```bash
# Ingest MDL to contextual graph
python -m indexing_cli.ingest_mdl_contextual_graph \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk
```

### 4. Test the Graph

```bash
# Test with a question
python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to AccessRequest in Snyk?" \
    --product-name Snyk
```

## Data Sources

### From `indexing_preview/` Directory

The `indexing_preview/` directory contains preview files from indexing operations:

```
indexing_preview/
├── table_definitions/
│   └── table_definitions_20260123_180157_Snyk.json
├── table_descriptions/
│   └── table_descriptions_20260123_180157_Snyk.json
├── schema_descriptions/
│   └── schema_descriptions_20260123_180900_Snyk.json
└── column_definitions/
    └── column_definitions_20260123_180157_Snyk.json
```

### From MDL JSON Files

If you have MDL JSON files (e.g., `snyk_mdl1.json`):

1. **Index MDL** (creates table definitions):
   ```bash
   python -m indexing_cli.index_mdl \
       --mdl-file path/to/snyk_mdl1.json \
       --product-name Snyk
   ```

2. **Ingest to Contextual Graph** (creates entity contexts and edges):
   ```bash
   python -m indexing_cli.ingest_mdl_contextual_graph \
       --mdl-file path/to/snyk_mdl1.json \
       --product-name Snyk
   ```

## Collections Created

After setup, these collections are available in ChromaDB:

### Schema Collections (no prefix)
- `table_definitions` - Table structures
- `table_descriptions` - Table descriptions
- `schema_descriptions` - Schema categories
- `column_definitions` - Column definitions
- `db_schema` - Complete schemas

### Contextual Graph Collections (no prefix)
- `context_definitions` - Table entity contexts
- `contextual_edges` - Table relationships, compliance relationships
- `fields` - Table columns/fields

### Compliance Collections (no prefix)
- `compliance_controls` - Compliance controls
- `domain_knowledge` - Policy documents, risk controls

## Verification

### Check Collections

```python
from app.core.dependencies import get_chromadb_client

client = get_chromadb_client()
collections = client.list_collections()

print("Available collections:")
for coll in collections:
    count = coll.count()
    print(f"  - {coll.name}: {count} documents")
```

### Check Specific Collection

```python
from app.core.dependencies import get_chromadb_client

client = get_chromadb_client()
collection = client.get_collection("context_definitions")
count = collection.count()
print(f"context_definitions: {count} documents")
```

## Common Issues

### Issue: No data in collections

**Solution**: Run ingestion scripts first:
```bash
# Ingest preview files
python -m indexing_cli.ingest_preview_files --preview-dir indexing_preview

# Or ingest MDL files
python -m indexing_cli.ingest_mdl_contextual_graph --mdl-file <path> --product-name Snyk
```

### Issue: Graph finds no tables

**Solution**: 
1. Verify `context_definitions` collection has table entities
2. Check product name matches exactly (e.g., "Snyk" not "snyk")
3. Verify table entity IDs follow format: `entity_{product}_{table}`

### Issue: No edges discovered

**Solution**:
1. Run `ingest_mdl_contextual_graph.py` to create edges
2. Verify `contextual_edges` collection exists
3. Check edge types: BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.

## Testing Checklist

Before testing the graph, verify:

- [ ] ChromaDB is running and accessible
- [ ] Collections exist (check with `client.list_collections()`)
- [ ] `context_definitions` has table entities
- [ ] `contextual_edges` has relationship edges
- [ ] `table_descriptions` or `table_definitions` has table data
- [ ] `OPENAI_API_KEY` is set
- [ ] Product name matches indexed data

## Example Workflow

```bash
# 1. Index MDL (if you have MDL files)
python -m indexing_cli.index_mdl \
    --mdl-file data/snyk_mdl1.json \
    --product-name Snyk \
    --preview  # Preview first

# 2. Review preview files
ls indexing_preview/table_definitions/

# 3. Index to database
python -m indexing_cli.index_mdl \
    --mdl-file data/snyk_mdl1.json \
    --product-name Snyk

# 4. Ingest to contextual graph
python -m indexing_cli.ingest_mdl_contextual_graph \
    --mdl-file data/snyk_mdl1.json \
    --product-name Snyk

# 5. Test the graph
python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to AccessRequest in Snyk?" \
    --product-name Snyk
```

## Using Preview Files Directly

If you only have preview files (no MDL JSON):

```bash
# Ingest preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions schema_descriptions

# Note: This won't create contextual graph edges
# You'll need MDL files for that, or manually create edges
```

## Next Steps After Setup

1. **Test Basic Query**: Test with a simple table relationship query
2. **Test Compliance Query**: Test with a compliance-related query
3. **Extend Planning**: Add more detailed planning components
4. **Add Execution**: Execute the plan to retrieve actual data

