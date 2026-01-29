# MDL Enriched Preview with Organization Support

## Overview

This document describes the enhanced MDL indexing system that:

1. **Adds Organization Support**: Organization is stored as static configuration (NOT in ChromaDB)
2. **Creates Preview Files**: Generates preview files for all enriched entities
3. **Deferred Ingestion**: Preview files can be ingested later via `ingest_preview_files.py`

## Key Concepts

### Organization Configuration

Organization is a **static configuration** that belongs to the application layer, not the data layer:

- ✅ **Stored in**: `app/config/organization_config.py` (application config)
- ✅ **Included in**: Document metadata (for reference only)
- ❌ **NOT stored in**: ChromaDB or PostgreSQL
- ❌ **NOT queryable**: Cannot filter by organization in vector search

**Why?** Organization is a deployment/configuration concern, not a data concern. A Snyk product always belongs to the Snyk organization—this is not data that changes or needs to be searched.

### Preview Files

Preview files are JSON files containing processed documents ready for ingestion:

```
indexing_preview/
├── table_definitions/
│   ├── table_definitions_20260128_120000_Snyk.json
│   └── table_definitions_summary_20260128_120000.txt
├── table_descriptions/
│   ├── table_descriptions_20260128_120000_Snyk.json
│   └── table_descriptions_summary_20260128_120000.txt
├── column_definitions/
│   ├── column_definitions_20260128_120000_Snyk.json
│   └── column_definitions_summary_20260128_120000.txt
└── knowledgebase/
    ├── knowledgebase_20260128_120000_Snyk.json
    └── knowledgebase_summary_20260128_120000.txt
```

## Preview File Types

### 1. `table_definitions`

Table schemas with enriched metadata:

```json
{
  "metadata": {
    "content_type": "table_definitions",
    "product_name": "Snyk",
    "organization_id": "snyk_org",
    "organization_name": "Snyk Organization",
    "document_count": 494,
    "timestamp": "20260128_120000"
  },
  "documents": [
    {
      "index": 0,
      "page_content": "{'name': 'Vulnerability', 'description': '...', ...}",
      "metadata": {
        "content_type": "table_definition",
        "table_name": "Vulnerability",
        "product_name": "Snyk",
        "categories": ["vulnerabilities"],
        "organization_id": "snyk_org",
        "organization_name": "Snyk Organization"
      }
    }
  ]
}
```

**Used for**: Schema discovery, table lookup, data catalog

### 2. `table_descriptions`

Table descriptions with categories:

```json
{
  "metadata": {
    "content_type": "table_descriptions",
    "product_name": "Snyk",
    "organization_id": "snyk_org",
    "document_count": 494
  },
  "documents": [
    {
      "metadata": {
        "type": "TABLE_DESCRIPTION",
        "table_name": "Vulnerability",
        "category_name": "vulnerabilities",
        "organization_id": "snyk_org"
      }
    }
  ]
}
```

**Used for**: Semantic search, category filtering, context retrieval

### 3. `column_definitions`

Column metadata with time concepts:

```json
{
  "metadata": {
    "content_type": "column_definitions",
    "product_name": "Snyk",
    "organization_id": "snyk_org",
    "document_count": 1571
  },
  "documents": [
    {
      "page_content": "{'column_name': 'created_at', 'is_time_dimension': true, ...}",
      "metadata": {
        "column_name": "created_at",
        "table_name": "Vulnerability",
        "is_time_dimension": true,
        "time_granularity": "day",
        "organization_id": "snyk_org"
      }
    }
  ]
}
```

**Used for**: Column search, time series analysis, data type discovery

### 4. `knowledgebase`

Features, metrics, instructions, examples:

```json
{
  "metadata": {
    "content_type": "knowledgebase",
    "product_name": "Snyk",
    "organization_id": "snyk_org",
    "document_count": 250,
    "description": "Knowledge base entities: features, metrics, instructions, examples"
  },
  "documents": [
    {
      "page_content": "{'entity_type': 'feature', 'name': 'vulnerability_count_by_severity', ...}",
      "metadata": {
        "content_type": "knowledgebase",
        "entity_type": "feature",
        "mdl_entity_type": "feature",
        "entity_name": "vulnerability_count_by_severity",
        "table_name": "Vulnerability",
        "category_name": "vulnerabilities",
        "organization_id": "snyk_org"
      }
    },
    {
      "metadata": {
        "entity_type": "metric",
        "mdl_entity_type": "metric",
        "entity_name": "critical_vulnerability_rate"
      }
    },
    {
      "metadata": {
        "entity_type": "instruction",
        "instruction_type": "best_practice",
        "priority": "high"
      }
    },
    {
      "metadata": {
        "entity_type": "example",
        "complexity": "simple"
      }
    }
  ]
}
```

**Used for**: Business logic, KPI definitions, query examples, best practices

## Usage

### Step 1: Configure Organization

Edit `app/config/organization_config.py`:

```python
PRODUCT_ORGANIZATION_MAPPING: Dict[str, OrganizationConfig] = {
    "Snyk": OrganizationConfig(
        organization_id="snyk_org",
        organization_name="Snyk Organization",
        description="Snyk security platform organization",
        metadata={"domain": "security", "industry": "cybersecurity"}
    ),
    "YourProduct": OrganizationConfig(
        organization_id="your_org",
        organization_name="Your Organization",
        description="Your product description",
        metadata={"domain": "your_domain"}
    ),
}
```

### Step 2: Generate Preview Files

```bash
# Generate preview files for Snyk product (all at once)
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview

# Generate with batching (recommended for large files)
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview \
    --batch-size 50  # Process 50 tables at a time

# Generate for another product
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/yourproduct/mdl.json \
    --product-name "YourProduct" \
    --project-id "your_project_id" \
    --preview-dir indexing_preview \
    --batch-size 25  # Smaller batches for rate limit safety
```

**Output:**
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
PHASE 1: Extracting Enriched Metadata
==================================================================================
[1/494] Processing AccessRequest...
  ✓ Category: access requests
  ✓ Examples: 2
  ✓ Features: 3
  ✓ Metrics: 2
[2/494] Processing Vulnerability...
  ...

✓ Extracted metadata for 494 tables

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

[4/4] Generating knowledgebase preview...
  ✓ Generated 250 knowledgebase entities
  ✓ Entity breakdown:
    - example: 98
    - feature: 74
    - instruction: 41
    - metric: 37
  ✓ Saved to: indexing_preview/knowledgebase/knowledgebase_20260128_120000_Snyk.json

==================================================================================
Preview Generation Summary
==================================================================================
✓ table_definitions: 494 documents → indexing_preview/table_definitions/...
✓ table_descriptions: 494 documents → indexing_preview/table_descriptions/...
✓ column_definitions: 1571 documents → indexing_preview/column_definitions/...
✓ knowledgebase: 250 documents → indexing_preview/knowledgebase/...
==================================================================================
```

### Step 3: Ingest Preview Files

```bash
# Ingest all preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase

# Dry run (see what would be ingested)
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --dry-run

# Ingest only specific types
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions
```

## Collection Mapping

Preview files are ingested into ChromaDB collections:

| Preview File | ChromaDB Collection | Description |
|-------------|-------------------|-------------|
| `table_definitions` | `table_definitions` | Table schemas |
| `table_descriptions` | `table_descriptions` | Table descriptions with categories |
| `column_definitions` | `column_definitions` | Column metadata with time concepts |
| `knowledgebase` (features) | `entities` | Features with `mdl_entity_type="feature"` |
| `knowledgebase` (metrics) | `entities` | Metrics with `mdl_entity_type="metric"` |
| `knowledgebase` (instructions) | `instructions` | Product instructions |
| `knowledgebase` (examples) | `sql_pairs` | SQL examples |

## Querying with Organization Context

Organization is included in metadata but NOT used for filtering:

```python
# ✅ CORRECT: Query by product (organization implicit)
results = await hybrid_search(
    query="vulnerability tables",
    collection_name="table_descriptions",
    where={
        "product_name": "Snyk",  # Product implies organization
        "category_name": "vulnerabilities"
    },
    top_k=5
)

# ❌ INCORRECT: Cannot filter by organization
results = await hybrid_search(
    query="vulnerability tables",
    where={
        "organization_id": "snyk_org"  # NOT queryable
    }
)

# ✅ Access organization info from results
for result in results:
    product = result.metadata["product_name"]
    org = get_product_organization(product)
    print(f"Product: {product}, Organization: {org.organization_name}")
```

## Batch Processing

The preview generator supports batched parallel processing for LLM extraction:

### Without Batching (Default)

```bash
# Processes all tables in parallel at once
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk"
```

**Pros:**
- Fastest execution (all tables processed simultaneously)
- No waiting between batches

**Cons:**
- May hit API rate limits with large MDL files
- Higher memory usage
- Risk of rate limit errors

### With Batching (Recommended)

```bash
# Processes 50 tables at a time
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --batch-size 50
```

**Pros:**
- Avoids rate limits
- More predictable execution
- Better for large MDL files (500+ tables)
- Graceful error handling per batch

**Cons:**
- Slightly slower (but still much faster than sequential)

### Recommended Batch Sizes

| LLM Provider | Rate Limit Tier | Recommended Batch Size |
|-------------|-----------------|----------------------|
| OpenAI | Tier 1 (Basic) | 10-20 |
| OpenAI | Tier 2 | 30-50 |
| OpenAI | Tier 3+ | 50-100 |
| Anthropic Claude | All tiers | 50-100 |
| Azure OpenAI | Standard | 25-50 |
| Local/Self-hosted | N/A | 100+ or omit |

### Example Output with Batching

```
==================================================================================
PHASE 1: Extracting Enriched Metadata (BATCHED)
==================================================================================
Created 494 extraction tasks
Running LLM extraction in batches of 50...
Processing batch 1/10 (50 tables)...
  ✓ Completed batch 1
Processing batch 2/10 (50 tables)...
  ✓ Completed batch 2
Processing batch 3/10 (50 tables)...
  ✓ Completed batch 3
...

✓ Extracted metadata for 494 tables
  Success: 493, Errors: 1 (using fallback)
```

## Benefits

### 1. **Separation of Concerns**
- **Configuration**: Organization lives in application config
- **Data**: Product data lives in ChromaDB
- **Clean**: No mixing of deployment concerns with data

### 2. **Preview & Validate**
- **Preview**: Generate preview files without touching ChromaDB
- **Validate**: Inspect preview files before ingestion
- **Iterate**: Regenerate previews quickly during development

### 3. **Flexible Ingestion**
- **Selective**: Ingest only specific content types
- **Re-ingest**: Re-run ingestion without re-extraction
- **Batch**: Ingest multiple products in one batch

### 4. **Cost Efficiency**
- **One LLM call per table**: Extract all metadata in one pass
- **Reuse**: Generate previews once, ingest multiple times
- **Fast**: No re-extraction for re-ingestion

## File Structure

```
knowledge/
├── app/
│   └── config/
│       ├── organization_config.py          ⭐ NEW: Organization config
│       └── mdl_store_mapping_simplified.py
├── indexing_cli/
│   ├── create_mdl_enriched_preview.py     ⭐ NEW: Preview generator
│   ├── index_mdl_enriched.py              (existing)
│   └── ingest_preview_files.py            (existing, supports new types)
├── indexing_preview/
│   ├── table_definitions/                  ⭐ NEW: Preview files
│   ├── table_descriptions/                 ⭐ NEW: Preview files
│   ├── column_definitions/                 ⭐ NEW: Preview files
│   └── knowledgebase/                      ⭐ NEW: Preview files
└── docs/
    └── MDL_ENRICHED_PREVIEW_WITH_ORGANIZATION.md  ⭐ NEW: This doc
```

## Example: Full Workflow

```bash
# 1. Configure organization
# Edit app/config/organization_config.py to add your product

# 2. Generate preview files
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview

# 3. Inspect preview files (optional)
ls -lh indexing_preview/table_definitions/
cat indexing_preview/knowledgebase/knowledgebase_summary_*.txt

# 4. Ingest preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase

# 5. Query the data
python
>>> from app.agents.data.retrieval import hybrid_search
>>> results = await hybrid_search(
...     query="vulnerability tables",
...     collection_name="table_descriptions",
...     where={"product_name": "Snyk", "category_name": "vulnerabilities"},
...     top_k=5
... )
```

## FAQ

### Q: Why not store organization in ChromaDB?

**A:** Organization is a configuration concern, not a data concern. It doesn't change per document and doesn't need to be searched. Keeping it in application config keeps the architecture clean.

### Q: Can I filter by organization?

**A:** No. Filter by `product_name` instead. Organization is implicit in the product.

### Q: What if I need to change organization?

**A:** Edit `app/config/organization_config.py` and re-generate preview files. No need to re-extract metadata.

### Q: Can I have multiple organizations?

**A:** Yes! Add them to `PRODUCT_ORGANIZATION_MAPPING` in `organization_config.py`.

### Q: What's in the knowledgebase collection?

**A:** Features, metrics, instructions, and SQL examples—all the contextual entities extracted from MDL.

## Summary

✅ **Organization**: Static config, NOT in ChromaDB  
✅ **Preview Files**: table_definitions, table_descriptions, column_definitions, knowledgebase  
✅ **Deferred Ingestion**: Generate once, ingest multiple times  
✅ **Type Discriminators**: knowledgebase entities use `entity_type` field  
✅ **Cost Efficient**: One LLM call per table  
✅ **Flexible**: Selective ingestion, easy re-ingestion  

**Next Steps**:
1. Configure organization in `organization_config.py`
2. Generate preview files with `create_mdl_enriched_preview.py`
3. Ingest preview files with `ingest_preview_files.py`
4. Query with product-based filtering 🚀
