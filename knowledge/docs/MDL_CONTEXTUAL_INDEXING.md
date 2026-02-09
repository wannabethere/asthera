# MDL Contextual Indexing

## Overview

The MDL Contextual Indexing system provides a comprehensive framework for indexing Metadata Definition Language (MDL) schemas into a contextual graph. This enables rich semantic search and intelligent query answering over database schemas, tables, columns, and their relationships.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MDL Contextual Indexing                      │
└──────────────────────────────────────┬──────────────────────────┘
                                      │
                  ┌───────────────────┼───────────────────┐
                  │                   │                   │
           ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
           │  Extractors  │    │  Edge Types │    │ Pruning Agent│
           └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
                  │                   │                   │
      ┌───────────┼───────────┐       │       ┌───────────┼───────────┐
      │           │           │       │       │           │           │
┌─────▼──┐  ┌────▼───┐  ┌────▼───┐  │  ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
│ Table  │  │Relation│  │Category│  │  │Feature │  │ Metric │  │Example │
│Extract │  │Extract │  │Extract │  │  │Extract │  │Extract │  │Extract │
└────────┘  └────────┘  └────────┘  │  └────────┘  └────────┘  └────────┘
                                     │
                        ┌────────────▼────────────┐
                        │   Contextual Edges      │
                        │  - BELONGS_TO_TABLE     │
                        │  - RELATES_TO_TABLE     │
                        │  - CATEGORY_CONTAINS    │
                        │  - TABLE_HAS_FEATURE    │
                        │  - METRIC_FROM_TABLE    │
                        │  - And 20+ more...      │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  Vector Store + Graph   │
                        │  - Documents            │
                        │  - Contextual Edges     │
                        │  - Metadata             │
                        └─────────────────────────┘
```

## Key Components

### 1. MDL Edge Types (`mdl_edge_types.py`)

Defines 25+ edge types for representing relationships in the MDL contextual graph:

**Structural Edges**:
- `BELONGS_TO_TABLE`: Column belongs to table
- `HAS_COLUMN`: Table has column  
- `HAS_MANY_TABLES`: Schema has many tables
- `RELATES_TO_TABLE`: Table-to-table relationships

**Category Edges**:
- `CATEGORY_CONTAINS_TABLE`: Category groups tables
- `TABLE_IN_CATEGORY`: Table belongs to category
- `PRODUCT_HAS_CATEGORY`: Product has category

**Feature Edges**:
- `TABLE_HAS_FEATURE`: Table provides feature
- `FEATURE_SUPPORTS_CONTROL`: Feature supports compliance control

**Metric Edges**:
- `METRIC_FROM_TABLE`: Metric calculated from table
- `KPI_FROM_METRIC`: KPI composed from metrics

**Example Edges**:
- `EXAMPLE_USES_TABLE`: Example query uses table
- `QUESTION_ANSWERED_BY_TABLE`: Natural question answered by table

### 2. Extractors

Seven specialized extractors create documents and edges:

- **MDLTableExtractor**: Extracts table metadata and creates table/column edges
- **MDLRelationshipExtractor**: Extracts relationships and creates RELATES_TO edges
- **MDLCategoryExtractor**: Creates category definitions and category edges
- **MDLFeatureExtractor**: Extracts features and maps to tables/columns
- **MDLMetricExtractor**: Extracts metrics/KPIs and maps to data sources
- **MDLExampleExtractor**: Extracts examples and natural questions
- **MDLInstructionExtractor**: Extracts product-specific instructions

### 3. MDL Edge Pruning Agent

Intelligently selects the most relevant edges for a given query using:

- **Priority-based ranking**: Critical edges (structure) ranked higher
- **Query-aware selection**: Tailors edge selection to query type
- **LLM-based pruning**: Uses GPT-4 to select contextually relevant edges
- **Domain scoring**: Applies MDL-specific scoring rules

### 4. Contextual Indexing CLI

Command-line interface for indexing MDL files:

```bash
python -m indexing_cli.index_mdl_contextual \
    --mdl-file path/to/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --preview  # Optional: save to files instead of indexing
```

## MDL Context Dimensions

The system supports 12 contextual dimensions:

1. **Product to Categories**: Map products to business categories
2. **Tables**: Table schemas, descriptions, metadata
3. **Relationships**: Table joins and foreign keys
4. **Categories**: 15 business categories (assets, projects, etc.)
5. **Semantic Descriptions**: Rich semantic information
6. **Column Meta Edges**: Column-level metadata
7. **Features**: Business capabilities from data
8. **Feature to Controls**: Compliance mappings
9. **Metrics & KPIs**: Calculated business metrics
10. **Natural Questions**: User questions mapped to tables
11. **Examples**: Query examples and patterns
12. **Product Instructions**: Best practices and usage guides

## Data Flow

```
MDL JSON File
    │
    ▼
┌─────────────────────────┐
│  Parse MDL Models       │
│  - Tables               │
│  - Columns              │
│  - Relationships        │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Categorize Tables      │
│  - Pattern matching     │
│  - 15 categories        │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Extract Documents      │
│  - Table descriptions   │
│  - Category definitions │
│  - Features/Metrics     │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Extract Edges          │
│  - Structure edges      │
│  - Relationship edges   │
│  - Category edges       │
│  - Feature edges        │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Store or Preview       │
│  - Vector stores        │
│  - Graph storage        │
│  - Preview files        │
└─────────────────────────┘
```

## Categories

15 business categories for organizing tables:

1. **access requests**: Access request management
2. **application data**: Application resources
3. **assets**: Asset management and tracking
4. **projects**: Project management
5. **vulnerabilities**: Vulnerability and CVE tracking
6. **integrations**: Integration and connectors
7. **configuration**: Configuration and settings
8. **audit logs**: Audit logs and activity tracking
9. **risk management**: Risk assessment and scoring
10. **deployment**: Deployment processes
11. **groups**: Group management
12. **organizations**: Organization structures
13. **memberships and roles**: Role assignments
14. **issues**: Issue tracking
15. **artifacts**: Artifact repositories

## Usage Examples

### Basic Indexing

```bash
# Index Snyk MDL with preview
python -m indexing_cli.index_mdl_contextual \
    --mdl-file /path/to/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --preview
```

### Full Indexing with Features

```bash
# Index with features, metrics, examples, and instructions
python -m indexing_cli.index_mdl_contextual \
    --mdl-file /path/to/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --features-file /path/to/features.json \
    --metrics-file /path/to/metrics.json \
    --examples-file /path/to/examples.json \
    --instructions-file /path/to/instructions.json
```

### With External Relationships

```bash
# Include external relationship configuration
python -m indexing_cli.index_mdl_contextual \
    --mdl-file /path/to/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --relationships-config /path/to/relationships.json
```

## Preview Mode

Preview mode saves extracted data to files instead of indexing:

**Output Location**: `knowledge/indexing_preview/mdl_contextual/`

**Files Generated**:
- `mdl_full_edges_{timestamp}_{product}.json`: All extracted edges
- `mdl_full_documents_{timestamp}_{product}.json`: All documents
- `mdl_full_summary_{timestamp}.txt`: Statistics and summary

## Benefits

1. **Rich Semantic Search**: Find tables by business purpose, not just name
2. **Intelligent Query Understanding**: Map natural questions to tables
3. **Relationship Discovery**: Understand table joins and dependencies
4. **Category-Based Navigation**: Browse tables by business domain
5. **Feature Mapping**: Link data to business capabilities
6. **Compliance Support**: Map data to controls and frameworks
7. **Best Practices**: Access product-specific usage guidelines

## Integration Points

### With MDL Context Breakdown Agent

The indexing system works with `mdl_context_breakdown_agent.py` to:
- Break down user questions into MDL queries
- Identify relevant tables and categories
- Plan hybrid search strategies

### With Hybrid Search

Indexed data powers hybrid search combining:
- Vector similarity search (semantic)
- Graph traversal (relationships)
- Metadata filtering (categories, products)

### With Compliance System

Feature-to-control mappings enable:
- Compliance evidence gathering
- Control-to-data mapping
- Audit trail generation

## Next Steps

1. **Run Tests**: `pytest tests/test_mdl_contextual_indexing.py -v`
2. **Index Sample Data**: Use preview mode with Snyk MDL
3. **Review Edge Types**: See `MDL_EDGE_TYPES.md`
4. **Configure Features**: See `MDL_INDEXING_GUIDE.md`
5. **Test Queries**: See `MDL_HYBRID_SEARCH.md`

## References

- [MDL Edge Types Documentation](./MDL_EDGE_TYPES.md)
- [MDL Extractors Documentation](./MDL_EXTRACTORS.md)
- [MDL Indexing Guide](./MDL_INDEXING_GUIDE.md)
- [MDL Hybrid Search](./MDL_HYBRID_SEARCH.md)
- [Snyk Playbook](../data/cvedata/playbooks/snyk_silver_tables.md)
