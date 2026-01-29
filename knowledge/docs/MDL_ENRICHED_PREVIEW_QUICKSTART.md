# MDL Enriched Preview - Quick Start Guide

## Overview

This guide will walk you through creating and ingesting MDL enriched preview files with organization support in under 5 minutes.

## Prerequisites

- MDL JSON file (e.g., `snyk_mdl1.json`)
- Python environment with dependencies installed
- Access to LLM for metadata extraction

## Step-by-Step Guide

### Step 1: Configure Organization (Optional)

By default, products use a default organization. To customize:

```bash
# Edit organization config
vi knowledge/app/config/organization_config.py
```

Add your product-organization mapping:

```python
PRODUCT_ORGANIZATION_MAPPING: Dict[str, OrganizationConfig] = {
    "Snyk": OrganizationConfig(
        organization_id="snyk_org",
        organization_name="Snyk Organization",
        description="Snyk security platform",
        metadata={"domain": "security"}
    ),
    # Add your product here
    "MyProduct": OrganizationConfig(
        organization_id="my_org",
        organization_name="My Organization",
        description="My product description",
        metadata={"domain": "my_domain"}
    ),
}
```

### Step 2: Generate Preview Files

Navigate to the knowledge directory:

```bash
cd knowledge
```

Generate preview files for Snyk product:

```bash
# Option 1: Process all tables in parallel (fastest, may hit rate limits)
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview

# Option 2: Process in batches (recommended for large MDL files)
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview \
    --batch-size 50  # Process 50 tables at a time
```

**Expected Output:**

```
==================================================================================
MDL Enriched Preview Generation
==================================================================================
MDL File: ../data/cvedata/snyk_mdl1.json
Product: Snyk
Project ID: Snyk
Organization: Snyk Organization
Preview Dir: indexing_preview

Organization: Snyk Organization (snyk_org)
Organization metadata will be included but NOT stored in chroma

==================================================================================
PHASE 1: Extracting Enriched Metadata (BATCHED)
==================================================================================
Created 494 extraction tasks
Running LLM extraction in batches of 50...
Processing batch 1/10 (50 tables)...
  ✓ Completed batch 1
Processing batch 2/10 (50 tables)...
  ✓ Completed batch 2
...
[1/494] ✓ Extracted metadata for AccessRequest (category: access requests)
[2/494] ✓ Extracted metadata for Vulnerability (category: vulnerabilities)
...

✓ Extracted metadata for 494 tables
  Success: 494, Errors: 0 (using fallback)

==================================================================================
PHASE 2: Generating Preview Files
==================================================================================

[1/4] Generating table_definitions preview...
  ✓ Generated 494 table definitions
  ✓ Saved to: indexing_preview/table_definitions/table_definitions_20260128_120000_Snyk.json

[2/4] Generating table_descriptions preview...
  ✓ Generated 494 table descriptions
  ✓ Saved to: indexing_preview/table_descriptions/table_descriptions_20260128_120000_Snyk.json

[3/4] Generating column_definitions preview...
  ✓ Generated 1571 column definitions
  ✓ Saved to: indexing_preview/column_definitions/column_definitions_20260128_120000_Snyk.json

[4/5] Generating knowledgebase preview...
  ✓ Generated 250 knowledgebase entities
  ✓ Entity breakdown:
    - example: 98
    - feature: 74
    - instruction: 41
    - metric: 37
  ✓ Saved to: indexing_preview/knowledgebase/knowledgebase_20260128_120000_Snyk.json

[5/5] Generating contextual_edges preview...
  ✓ Generated 3500 contextual edges
  ✓ Edge type breakdown:
    - CATEGORY_HAS_TABLE: 494
    - TABLE_BELONGS_TO_CATEGORY: 494
    - TABLE_HAS_COLUMN: 1571
    - TABLE_HAS_FEATURE: 74
    - TABLE_HAS_METRIC: 37
    - EXAMPLE_USES_TABLE: 98
    - ... (and more)
  ✓ Saved to: indexing_preview/contextual_edges/contextual_edges_20260128_120000_Snyk.json

==================================================================================
Preview Generation Summary
==================================================================================
✓ table_definitions: 494 documents
✓ table_descriptions: 494 documents
✓ column_definitions: 1571 documents
✓ knowledgebase: 250 documents
✓ contextual_edges: 3500 documents
==================================================================================
```

### Step 3: Inspect Preview Files (Optional)

Check what was generated:

```bash
# List all preview files
ls -lh indexing_preview/*/

# View summaries
cat indexing_preview/table_definitions/table_definitions_summary_*.txt
cat indexing_preview/knowledgebase/knowledgebase_summary_*.txt

# Inspect a preview file (first 50 lines)
head -50 indexing_preview/table_definitions/table_definitions_20260128_120000_Snyk.json
```

### Step 4: Dry Run Ingestion (Optional)

See what would be ingested without actually ingesting:

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase contextual_edges \
    --dry-run
```

**Expected Output:**

```
[DRY RUN] Would ingest to stores:
  table_definitions: 494 documents
  table_descriptions: 494 documents
  column_definitions: 1571 documents
  entities: 111 documents (features, metrics)
  instructions: 41 documents
  sql_pairs: 98 documents (examples)
```

### Step 5: Ingest Preview Files

Ingest all preview files into ChromaDB:

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase contextual_edges
```

**Expected Output:**

```
==================================================================================
Ingesting Preview Files
==================================================================================
Preview Directory: indexing_preview
Content Types: table_definitions, table_descriptions, column_definitions, knowledgebase

Processing file: table_definitions_20260128_120000_Snyk.json (content_type: table_definitions)
  Loaded 494 documents
  ✓ Ingested 494 documents to table_definitions

Processing file: table_descriptions_20260128_120000_Snyk.json (content_type: table_descriptions)
  Loaded 494 documents
  ✓ Ingested 494 documents to table_descriptions

Processing file: column_definitions_20260128_120000_Snyk.json (content_type: column_definitions)
  Loaded 1571 documents
  ✓ Ingested 1571 documents to column_definitions

Processing file: knowledgebase_20260128_120000_Snyk.json (content_type: knowledgebase)
  Loaded 250 documents
  Routing knowledgebase documents to 4 stores:
    entities: 111 documents (feature:74, metric:37)
    instructions: 41 documents
    sql_pairs: 98 documents
  ✓ Ingested to 4 stores

==================================================================================
Ingestion Summary
==================================================================================
✓ Total Files: 4
✓ Total Documents: 2809
✓ Stores Used: 6 (table_definitions, table_descriptions, column_definitions, entities, instructions, sql_pairs)
==================================================================================
```

### Step 6: Query the Data

Test your ingested data:

```python
from app.agents.data.retrieval import hybrid_search

# Query table descriptions
results = await hybrid_search(
    query="vulnerability tables",
    collection_name="table_descriptions",
    where={
        "product_name": "Snyk",
        "category_name": "vulnerabilities"
    },
    top_k=5
)

# Query features
results = await hybrid_search(
    query="vulnerability analysis features",
    collection_name="entities",
    where={
        "product_name": "Snyk",
        "mdl_entity_type": "feature",
        "category_name": "vulnerabilities"
    },
    top_k=5
)

# Query examples
results = await hybrid_search(
    query="vulnerability SQL examples",
    collection_name="sql_pairs",
    where={
        "product_name": "Snyk",
        "category_name": "vulnerabilities"
    },
    top_k=5
)
```

## Common Scenarios

### Scenario 1: Re-generate Previews (No LLM Cost!)

If you want to change the preview format without re-extracting metadata:

```bash
# Just re-run the preview generation
# (This is fast because metadata is already extracted)
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview
```

**Note:** If you've already extracted metadata once, subsequent runs will be much faster because the LLM extraction is cached.

### Scenario 2: Ingest Only Specific Types

```bash
# Ingest only table definitions and descriptions
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions

# Ingest only knowledgebase
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types knowledgebase
```

### Scenario 3: Multiple Products

```bash
# Generate for Snyk
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview

# Generate for another product
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/myproduct/mdl.json \
    --product-name "MyProduct" \
    --preview-dir indexing_preview

# Ingest all at once (including contextual edges)
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase contextual_edges
```

### Scenario 4: Large MDL Files with Rate Limits

```bash
# For large MDL files (500+ tables), use batching to avoid rate limits
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/large_mdl.json \
    --product-name "LargeProduct" \
    --preview-dir indexing_preview \
    --batch-size 25  # Conservative batch size

# For OpenAI with tier limits:
# - Tier 1: Use batch-size 10-20
# - Tier 2: Use batch-size 30-50
# - Tier 3+: Use batch-size 50-100 or omit for all-at-once

# For Claude/Anthropic:
# - Use batch-size 50-100 (higher rate limits)
```

### Scenario 5: Re-ingest After Changes

```bash
# Make changes to preview files manually (if needed)
vi indexing_preview/knowledgebase/knowledgebase_20260128_120000_Snyk.json

# Re-ingest (will update ChromaDB)
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types knowledgebase \
    --force-recreate  # Optional: delete and recreate collections
```

## Troubleshooting

### Issue: "Organization not found"

**Solution:** Add your product to `organization_config.py`:

```python
PRODUCT_ORGANIZATION_MAPPING["MyProduct"] = OrganizationConfig(
    organization_id="my_org",
    organization_name="My Organization"
)
```

### Issue: "Preview file not found"

**Solution:** Make sure you generated preview files first:

```bash
# List what's in preview directory
ls -R indexing_preview/

# Generate if missing
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview
```

### Issue: "LLM extraction failed"

**Solution:** Check your LLM configuration:

```bash
# Make sure you have a valid LLM configured
# Check environment variables for API keys
echo $OPENAI_API_KEY
# or
echo $ANTHROPIC_API_KEY

# Try with a simpler MDL file first
```

### Issue: "ChromaDB collection not found"

**Solution:** Make sure ChromaDB is initialized:

```bash
# Check ChromaDB path
ls -la ~/.chroma_data/

# Or check your CHROMA_STORE_PATH environment variable
```

## Next Steps

- **Read Full Documentation**: [MDL_ENRICHED_PREVIEW_WITH_ORGANIZATION.md](MDL_ENRICHED_PREVIEW_WITH_ORGANIZATION.md)
- **Understand Organization Config**: [organization_config.py](../app/config/organization_config.py)
- **Query Best Practices**: [MDL_HYBRID_SEARCH.md](MDL_HYBRID_SEARCH.md)
- **Contextual Indexing**: [MDL_CONSOLIDATED_EXTRACTION.md](MDL_CONSOLIDATED_EXTRACTION.md)

## Summary

✅ **3 Simple Commands:**
1. `create_mdl_enriched_preview.py` - Generate preview files (ONE LLM call per table)
2. `ingest_preview_files.py --dry-run` - Preview what will be ingested
3. `ingest_preview_files.py` - Ingest into ChromaDB

✅ **Organization is configuration**, not data  
✅ **Preview files can be inspected** before ingestion  
✅ **Re-ingest anytime** without re-extraction  
✅ **Cost efficient**: One LLM call per table  

🚀 **You're ready to go!**
