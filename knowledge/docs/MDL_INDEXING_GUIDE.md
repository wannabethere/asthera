# MDL Indexing Guide

## Quick Start

This guide walks you through indexing your MDL (Metadata Definition Language) files with full contextual graph support.

## Prerequisites

1. **MDL File**: Your database schema in MDL JSON format
2. **Python Environment**: Python 3.8+
3. **Dependencies**: Install knowledge service dependencies
4. **Optional Files**: Features, metrics, examples, instructions (JSON format)

## Step 1: Prepare Your MDL File

Ensure your MDL file is in valid JSON format:

```json
{
  "catalog": "Snyk",
  "schema": "public",
  "models": [
    {
      "name": "AssetAttributes",
      "description": "Contains asset attributes",
      "primaryKey": "id",
      "columns": [
        {
          "name": "id",
          "type": "varchar",
          "description": "Unique identifier"
        }
      ],
      "relationships": [
        {
          "name": "assetClass",
          "toModel": "AssetClass",
          "joinOn": "asset_class_id"
        }
      ]
    }
  ]
}
```

## Step 2: Basic Indexing (Preview Mode)

Start with preview mode to see what will be indexed:

```bash
cd /path/to/flowharmonicai/knowledge

python -m indexing_cli.index_mdl_contextual \
    --mdl-file /path/to/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --preview
```

**Output**: Preview files in `indexing_preview/mdl_contextual/`

**Files Created**:
- `mdl_full_edges_{timestamp}_Snyk.json`: All edges
- `mdl_full_documents_{timestamp}_Snyk.json`: All documents  
- `mdl_full_summary_{timestamp}.txt`: Statistics

## Step 3: Review Preview Output

### Check the Summary File

```bash
cat indexing_preview/mdl_contextual/mdl_full_summary_*.txt
```

**Example Output**:
```
MDL Contextual Indexing Preview - mdl_full
Product: Snyk
Timestamp: 20260127_153000

Edges: 2547
Documents: 502

Edge Type Distribution:
  BELONGS_TO_TABLE: 850
  HAS_COLUMN: 850
  RELATES_TO_TABLE: 320
  CATEGORY_CONTAINS_TABLE: 180
  HAS_MANY_TABLES: 180
  ...
```

### Inspect Edge Structure

```bash
cat indexing_preview/mdl_contextual/mdl_full_edges_*.json | jq '.[0]'
```

**Example Edge**:
```json
{
  "edge_id": "AssetAttributes_id_belongs",
  "edge_type": "BELONGS_TO_TABLE",
  "source_entity": "id",
  "source_type": "column",
  "target_entity": "AssetAttributes",
  "target_type": "table",
  "document_preview": "Column 'id' belongs to table AssetAttributes...",
  "relevance_score": 0.95,
  "metadata": {
    "product_name": "Snyk",
    "table_name": "AssetAttributes",
    "column_name": "id",
    "data_type": "varchar"
  }
}
```

## Step 4: Prepare Optional Files

### Features File (`features.json`)

```json
[
  {
    "feature_name": "Asset Tracking",
    "description": "Track assets and their attributes",
    "tables": ["AssetAttributes", "AssetClass"],
    "columns": ["id", "asset_name", "severity"],
    "controls": ["CC6.1"]
  },
  {
    "feature_name": "Vulnerability Monitoring",
    "description": "Monitor vulnerabilities across assets",
    "tables": ["VulnerabilityInstances", "AssetAttributes"],
    "columns": ["severity", "cvss_score"],
    "controls": ["CC7.2"]
  }
]
```

### Metrics File (`metrics.json`)

```json
[
  {
    "metric_name": "Total Assets",
    "metric_type": "metric",
    "description": "Total number of assets",
    "calculation_method": "COUNT(id)",
    "tables": ["AssetAttributes"],
    "aggregation_type": "count"
  },
  {
    "metric_name": "Critical Vulnerabilities",
    "metric_type": "metric",
    "description": "Count of critical vulnerabilities",
    "calculation_method": "COUNT(*) WHERE severity = 'Critical'",
    "tables": ["VulnerabilityInstances"],
    "columns": ["severity"],
    "aggregation_type": "count"
  },
  {
    "metric_name": "Security Posture",
    "metric_type": "kpi",
    "description": "Overall security posture score",
    "calculation_method": "Weighted average of metrics",
    "base_metrics": ["Total Assets", "Critical Vulnerabilities"]
  }
]
```

### Examples File (`examples.json`)

```json
[
  {
    "example_id": "ex001",
    "example_type": "query_example",
    "title": "Get all assets",
    "description": "Retrieve all assets with their attributes",
    "query": "SELECT * FROM AssetAttributes",
    "tables": ["AssetAttributes"],
    "use_case": "Asset inventory"
  },
  {
    "example_id": "ex002",
    "example_type": "natural_question",
    "title": "How many assets do we have?",
    "description": "Count total number of assets",
    "tables": ["AssetAttributes"],
    "use_case": "Asset count"
  },
  {
    "example_id": "ex003",
    "example_type": "query_pattern",
    "title": "Asset with vulnerabilities pattern",
    "description": "Common pattern for joining assets with vulnerabilities",
    "query": "SELECT a.*, v.* FROM AssetAttributes a JOIN VulnerabilityInstances v ON a.id = v.asset_id",
    "tables": ["AssetAttributes", "VulnerabilityInstances"],
    "use_case": "Risk assessment"
  }
]
```

### Instructions File (`instructions.json`)

```json
[
  {
    "instruction_id": "inst001",
    "instruction_type": "best_practice",
    "title": "Always filter by active status",
    "content": "When querying assets, always filter by active=true to exclude archived assets",
    "applies_to_tables": ["AssetAttributes"],
    "priority": "high"
  },
  {
    "instruction_id": "inst002",
    "instruction_type": "usage_guide",
    "title": "Use API v3",
    "content": "Always use API v3 endpoints for Snyk queries. v1 and v2 are deprecated.",
    "applies_to_tables": [],
    "priority": "medium"
  },
  {
    "instruction_id": "inst003",
    "instruction_type": "warning",
    "title": "Large result sets warning",
    "content": "Projects table can contain millions of rows. Always use LIMIT or WHERE clauses.",
    "applies_to_tables": ["Projects"],
    "priority": "high"
  }
]
```

### Relationships Config (`relationships.json`)

```json
[
  {
    "source_table": "AssetAttributes",
    "target_table": "AssetClass",
    "relationship_name": "belongsToClass",
    "relationship_type": "many_to_one",
    "join_column": "asset_class_id",
    "description": "Assets belong to asset classes for categorization",
    "bidirectional": true
  },
  {
    "source_table": "VulnerabilityInstances",
    "target_table": "AssetAttributes",
    "relationship_name": "affectsAsset",
    "relationship_type": "many_to_one",
    "join_column": "asset_id",
    "description": "Vulnerabilities affect specific assets",
    "bidirectional": true
  }
]
```

## Step 5: Full Indexing with All Components

Index with all optional files:

```bash
python -m indexing_cli.index_mdl_contextual \
    --mdl-file /path/to/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --features-file /path/to/features.json \
    --metrics-file /path/to/metrics.json \
    --examples-file /path/to/examples.json \
    --instructions-file /path/to/instructions.json \
    --relationships-config /path/to/relationships.json \
    --preview
```

## Step 6: Review Full Preview

Check the summary to see all components:

```
Edges Created: 3250
  - Table Edges: 1700
  - Relationship Edges: 420
  - Category Edges: 195
  - Feature Edges: 350
  - Metric Edges: 280
  - Example Edges: 205
  - Instruction Edges: 100
```

## Step 7: Production Indexing

Once satisfied with preview, remove `--preview` flag:

```bash
python -m indexing_cli.index_mdl_contextual \
    --mdl-file /path/to/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --features-file /path/to/features.json \
    --metrics-file /path/to/metrics.json \
    --examples-file /path/to/examples.json \
    --instructions-file /path/to/instructions.json
```

**Note**: This will index to actual vector stores and may take 10-30 minutes depending on size.

## Step 8: Verify Indexing

### Check Collections

```python
from app.core.dependencies import get_chromadb_client

client = get_chromadb_client()
collections = client.list_collections()

print(f"Collections: {[c.name for c in collections]}")
```

### Query Test

```python
from app.services.contextual_graph_storage import ContextualGraphStorageService

service = ContextualGraphStorageService(...)

# Search for table
results = await service.search_edges(
    query="AssetAttributes table",
    edge_types=["BELONGS_TO_TABLE", "HAS_COLUMN"],
    limit=5
)

print(f"Found {len(results)} edges")
```

## Troubleshooting

### Issue: "MDL file not found"

**Solution**: Provide absolute path or verify file exists:
```bash
ls -la /path/to/snyk_mdl1.json
```

### Issue: "No edges created"

**Solution**: Check MDL file structure. Must have `models` array:
```bash
cat snyk_mdl1.json | jq '.models | length'
```

### Issue: "LLM timeout"

**Solution**: Process smaller batches or increase timeout:
```bash
# Set environment variable
export OPENAI_TIMEOUT=300

# Then run indexing
python -m indexing_cli.index_mdl_contextual ...
```

### Issue: "ChromaDB dimension mismatch"

**Solution**: Clear and recreate collections:
```python
from app.core.dependencies import get_chromadb_client

client = get_chromadb_client()
client.delete_collection("contextual_edges")
```

## Best Practices

1. **Always Preview First**: Use `--preview` to validate before production indexing

2. **Incremental Indexing**: Start with MDL only, then add features/metrics

3. **Validate JSON Files**: Use `jq` to validate JSON before indexing:
   ```bash
   jq '.' features.json > /dev/null && echo "Valid JSON"
   ```

4. **Monitor Progress**: Watch logs for errors:
   ```bash
   python -m indexing_cli.index_mdl_contextual ... 2>&1 | tee indexing.log
   ```

5. **Backup Preview Files**: Keep preview files for reference

6. **Test Queries**: After indexing, test with simple queries

## Advanced Usage

### Custom Context ID

Use custom context for multi-tenant scenarios:

```bash
python -m indexing_cli.index_mdl_contextual \
    --mdl-file snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --context-id "tenant_123"
```

### Batch Processing

Process multiple products:

```bash
for product in Snyk Cornerstone DataDog; do
    python -m indexing_cli.index_mdl_contextual \
        --mdl-file "${product}_mdl.json" \
        --project-id "$product" \
        --product-name "$product" \
        --preview
done
```

## Performance Tips

1. **Parallel Processing**: Extractors run async internally
2. **Batch Size**: Default is optimized for most cases
3. **LLM Model**: Use `gpt-4o-mini` for faster processing (default)
4. **Preview First**: Avoid wasting time on errors

## What Gets Indexed

### Collections

- `table_descriptions`: Table metadata
- `column_metadata`: Column definitions
- `db_schema`: Schema structure
- `contextual_edges`: All edges
- `category_mapping`: Category information
- `domain_knowledge`: Features/metrics/examples/instructions

### Edge Distribution

For a typical 500-table schema:

- **Structure**: ~40% (BELONGS_TO, HAS_COLUMN, HAS_MANY)
- **Relationships**: ~20% (RELATES_TO, DERIVED_FROM)
- **Categories**: ~15% (CATEGORY_CONTAINS, TABLE_IN)
- **Features**: ~10% (TABLE_HAS_FEATURE, etc.)
- **Metrics**: ~8% (METRIC_FROM_TABLE, etc.)
- **Examples**: ~5% (EXAMPLE_USES, QUESTION_ANSWERED)
- **Instructions**: ~2% (INSTRUCTION_APPLIES)

## Next Steps

1. **Test Queries**: See [MDL Hybrid Search](./MDL_HYBRID_SEARCH.md)
2. **Understand Edges**: See [MDL Edge Types](./MDL_EDGE_TYPES.md)
3. **Run Tests**: `pytest tests/test_mdl_contextual_indexing.py`
4. **Integrate**: Use with MDL Context Breakdown Agent

## See Also

- [MDL Contextual Indexing Overview](./MDL_CONTEXTUAL_INDEXING.md)
- [MDL Edge Types Reference](./MDL_EDGE_TYPES.md)
- [MDL Extractors Documentation](./MDL_EXTRACTORS.md)
- [MDL Hybrid Search Guide](./MDL_HYBRID_SEARCH.md)
