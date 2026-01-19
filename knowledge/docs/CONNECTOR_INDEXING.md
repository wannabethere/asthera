# Connector/Product Configuration Indexing

This guide explains how to index connector and product configurations (like Snyk) into ChromaDB or Qdrant stores for use in contextual reasoning, planning, and other AI assistants.

## Overview

The connector indexing system allows you to:
1. **Index product definitions** - Product purpose, documentation links, key concepts
2. **Index extendable entities** - APIs, integrations, data sources, endpoints
3. **Index extendable documentation** - Reference docs, guides, API documentation
4. **Preview before indexing** - Dump configurations to files for review
5. **Support multiple vector stores** - ChromaDB and Qdrant

## Workflow

### Step 1: Create Product Configuration

Create a Python file or JSON file with product configuration. Example structure:

```python
# snyk_product_config.py
SNYK_PRODUCT_CONFIG = {
    "product_name": "Snyk",
    "product_purpose": "Developer-first security platform...",
    "product_docs_link": "https://docs.snyk.io",
    "key_concepts": [
        "Vulnerability Database - Snyk maintains...",
        "CVE (Common Vulnerabilities and Exposures)...",
        # ... more concepts
    ],
    "extendable_entities": [
        {
            "name": "Projects",
            "type": "entity",
            "description": "Projects represent applications...",
            "api": "https://api.snyk.io/v1/orgs/{orgId}/projects",
            "endpoints": [
                "GET /orgs/{orgId}/projects",
                # ... more endpoints
            ],
            "examples": [
                {
                    "name": "my-node-app",
                    "type": "npm",
                    # ... example data
                }
            ]
        },
        # ... more entities
    ],
    "extendable_docs": [
        {
            "title": "Snyk REST API Documentation",
            "type": "api_reference",
            "link": "https://docs.snyk.io/api",
            "description": "Complete REST API reference...",
            "sections": [
                "Authentication - API tokens and OAuth",
                # ... more sections
            ],
            "content": "The Snyk REST API allows..."
        },
        # ... more docs
    ]
}
```

### Step 2: Preview Mode (Dump to Files)

Run the indexing script in preview mode to dump configurations to files:

```bash
python -m app.indexing.cli.index_connectors \
    --config-file knowledge/app/indexing/examples/snyk_product_config.py \
    --product-name Snyk \
    --domain security \
    --preview \
    --preview-dir indexing_preview \
    --vector-store chroma \
    --collection-prefix connector_index
```

This will:
- Load the product configuration
- Process it through pipelines (entity extraction, etc.)
- Save documents to preview files in `indexing_preview/` directory
- **NOT** index to database (preview mode)

### Step 3: Review Preview Files

Check the preview files in `indexing_preview/`:

```
indexing_preview/
├── product_purpose/
│   └── product_purpose_*.json
├── product_docs/
│   └── product_docs_*.json
├── product_key_concepts/
│   └── product_key_concepts_*.json
├── extendable_entities/
│   └── extendable_entities_*.json
└── extendable_docs/
    └── extendable_docs_*.json
```

Each JSON file contains:
- `metadata`: Document metadata (content_type, product_name, domain, etc.)
- `documents`: List of processed documents ready for indexing

### Step 4: Ingest Preview Files

Once you've reviewed the preview files, ingest them into the database:

```bash
python -m app.indexing.cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix connector_index \
    --vector-store chroma
```

This will:
- Load all preview files
- Route documents to appropriate stores based on content_type
- Index documents to ChromaDB or Qdrant
- Skip pipeline processing (already done in preview mode)

### Alternative: Direct Indexing

If you don't need preview mode, you can index directly:

```bash
python -m app.indexing.cli.index_connectors \
    --config-file knowledge/app/indexing/examples/snyk_product_config.py \
    --product-name Snyk \
    --domain security \
    --vector-store chroma \
    --collection-prefix connector_index
```

This will:
- Load configuration
- Process through pipelines
- Index directly to database (no preview files)

## Configuration Formats

### Python Module

```python
# product_config.py
PRODUCT_CONFIG = {
    "product_name": "MyProduct",
    # ... configuration
}
```

Or with product-specific name:
```python
# snyk_product_config.py
SNYK_PRODUCT_CONFIG = {
    "product_name": "Snyk",
    # ... configuration
}
```

### JSON File

```json
{
    "product_name": "MyProduct",
    "product_purpose": "...",
    "key_concepts": [...],
    "extendable_entities": [...],
    "extendable_docs": [...]
}
```

## Content Types and Stores

The system automatically routes documents to appropriate stores:

| Content Type | Store Name | Description |
|-------------|------------|-------------|
| `product_purpose` | `product_purpose` | Product purpose/description |
| `product_docs_link` | `product_docs` | Documentation links |
| `product_key_concepts` | `product_key_concepts` | Combined key concepts |
| `product_key_concept` | `product_key_concepts` | Individual concepts |
| `extendable_entity` | `extendable_entities` | API entities, integrations |
| `extendable_doc` | `extendable_docs` | Reference documentation |

## Command-Line Options

### index_connectors.py

```
--config-file          Path to config file (Python or JSON) or directory (required)
--product-name         Product name (overrides config if provided)
--domain               Domain filter (e.g., 'security', 'compliance')
--config-format        Format: auto, python, json, directory (default: auto)
--preview              Preview mode: save to files instead of database
--preview-dir          Directory for preview files (default: indexing_preview)
--vector-store         Vector store type: chroma or qdrant (default: chroma)
--collection-prefix    Prefix for collection names (default: connector_index)
```

### ingest_preview_files.py

```
--preview-dir          Directory containing preview files (default: indexing_preview)
--collection-prefix    Prefix for ChromaDB collections (default: comprehensive_index)
--vector-store         Vector store type: chroma or qdrant (default: chroma)
--content-types        Specific content types to ingest (default: all)
--dry-run              Dry run mode: show what would be ingested
--force-recreate       Force recreate collections (fixes dimension mismatches)
```

## Use Cases

### 1. Contextual Reasoning

Indexed connector configurations can be used by AI assistants to:
- Understand available data sources
- Plan data extraction strategies
- Generate API calls based on entity definitions
- Reference documentation for implementation details

### 2. Multi-Connector Support

Index multiple connectors/products:
```bash
# Index Snyk
python -m app.indexing.cli.index_connectors \
    --config-file configs/snyk_product_config.py \
    --product-name Snyk \
    --domain security \
    --preview

# Index another product
python -m app.indexing.cli.index_connectors \
    --config-file configs/other_product_config.py \
    --product-name OtherProduct \
    --domain analytics \
    --preview

# Ingest all
python -m app.indexing.cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix connector_index
```

### 3. Domain-Specific Indexing

Use domain filters to organize connectors:
```bash
# Security domain
python -m app.indexing.cli.index_connectors \
    --config-file snyk_config.py \
    --domain security \
    --collection-prefix security_connectors

# Compliance domain
python -m app.indexing.cli.index_connectors \
    --config-file compliance_tool_config.py \
    --domain compliance \
    --collection-prefix compliance_connectors
```

## Integration with Existing Systems

The connector indexing system integrates with:
- **ComprehensiveIndexingService** - Uses existing indexing infrastructure
- **ProductProcessor** - Processes product configurations
- **Extraction Pipelines** - Entity extraction, field extraction, etc.
- **FileStorage** - Preview file management
- **Vector Stores** - ChromaDB and Qdrant support

## Example: Indexing Snyk Configuration

```bash
# 1. Preview mode
python -m app.indexing.cli.index_connectors \
    --config-file knowledge/app/indexing/examples/snyk_product_config.py \
    --product-name Snyk \
    --domain security \
    --preview \
    --preview-dir indexing_preview \
    --collection-prefix connector_index

# 2. Review files in indexing_preview/

# 3. Ingest to database
python -m app.indexing.cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix connector_index \
    --vector-store chroma
```

## Troubleshooting

### Dimension Mismatch Errors

If you get dimension mismatch errors when ingesting:
```bash
python -m app.indexing.cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix connector_index \
    --force-recreate
```

### Preview Files Not Found

Ensure preview mode was run first:
```bash
# Check preview directory
ls -la indexing_preview/
```

### Config File Not Loading

Check file format and variable names:
- Python files: Must have variable ending with `_PRODUCT_CONFIG` or `PRODUCT_CONFIG`
- JSON files: Must have valid JSON structure with `product_name` field

## Related Documentation

- [Comprehensive Indexing Service](../README.md)
- [Product Processor](../processors/product_processor.py)
- [Preview File Ingestion](../cli/ingest_preview_files.py)

