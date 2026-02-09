# MDL Reasoning Graph Setup Guide

## Overview

This guide explains how to set up data for the MDL Reasoning and Planning Graph using data from `indexing_preview/` and other data sources.

## Architecture

The MDL Reasoning Graph follows this workflow:

```
User Question
    ↓
[Context Breakdown Node] - Breaks down question using MDLContextBreakdownAgent
    ↓
[Entity Identification Node] - Identifies tables and entities
    ↓
[Context Retrieval Node] - Retrieves contexts and edges
    ↓
[Planning Node] - Creates reasoning plan
    ↓
Final Result (entities, questions, plan)
```

## Data Setup

### Step 1: Index MDL Schema Files

Index MDL schema files to create table definitions, descriptions, and schema descriptions:

```bash
# Preview mode (saves to files)
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk \
    --preview

# Review preview files in indexing_preview/
# Then index to database
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk
```

This creates:
- `table_definitions` collection
- `table_descriptions` collection
- `schema_descriptions` collection
- `column_definitions` collection

### Step 2: Ingest MDL to Contextual Graph

Ingest MDL definitions into contextual graph to create entity contexts and relationships:

```bash
# Ingest MDL file to contextual graph
python -m indexing_cli.ingest_mdl_contextual_graph \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk

# Or use dry-run to preview
python -m indexing_cli.ingest_mdl_contextual_graph \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk \
    --dry-run
```

This creates:
- `context_definitions` collection (table entity contexts)
- `contextual_edges` collection (table relationships, compliance relationships)
- `fields` collection (table columns/fields)

### Step 3: Index Preview Files (Alternative)

If you have preview files in `indexing_preview/`, you can ingest them directly:

```bash
# Ingest preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions schema_descriptions column_definitions
```

### Step 4: Index Compliance Controls (Optional)

For compliance-related queries, index compliance controls:

```bash
# Index compliance controls from preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types soc2_controls policy_documents riskmanagement_risk_controls
```

## Data Sources

### From `indexing_preview/` Directory

The `indexing_preview/` directory contains preview files from indexing:

```
indexing_preview/
├── table_definitions/
│   ├── table_definitions_20260123_180157_Snyk.json
│   └── table_definitions_summary_20260123_180157.txt
├── table_descriptions/
│   ├── table_descriptions_20260123_180157_Snyk.json
│   └── table_descriptions_summary_20260123_180157.txt
├── schema_descriptions/
│   ├── schema_descriptions_20260123_180900_Snyk.json
│   └── schema_descriptions_summary_20260123_180900.txt
├── column_definitions/
│   ├── column_definitions_20260123_180157_Snyk.json
│   └── column_definitions_summary_20260123_180157.txt
├── soc2_controls/
│   ├── soc2_controls_20260121_184841_compliance_SOC2.json
│   └── soc2_controls_summary_20260121_184841.txt
└── ...
```

### Collections Created

After indexing, these collections are available in ChromaDB:

1. **Schema Collections** (no prefix):
   - `table_definitions` - Table structure definitions
   - `table_descriptions` - Table descriptions with business context
   - `schema_descriptions` - Schema-level descriptions with categories
   - `column_definitions` - Column definitions
   - `db_schema` - Complete database schema documents

2. **Contextual Graph Collections** (no prefix):
   - `context_definitions` - Table entity contexts
   - `contextual_edges` - Table relationships and compliance relationships
   - `fields` - Table columns/fields

3. **Compliance Collections** (no prefix):
   - `compliance_controls` - Compliance control definitions
   - `domain_knowledge` - Policy documents, risk controls

## Testing the Graph

### Run the Test

```bash
# Set environment variables
export OPENAI_API_KEY="your-openai-api-key"

# Run test
cd knowledge
python tests/test_mdl_reasoning_graph.py
```

### Expected Output

The test will:
1. Break down the user question
2. Identify tables and entities
3. Retrieve contexts and edges
4. Create a reasoning plan

Example output:
```
Context Breakdown:
  Identified Entities: 3
  Search Questions: 3
    - context_definitions
    - contextual_edges
    - schema_descriptions

Entity Identification:
  Tables Found: 2
    - AccessRequest (context_id: entity_Snyk_AccessRequest)
    - Project (context_id: entity_Snyk_Project)
  Entities Found: 5

Context Retrieval:
  Contexts Retrieved: 2
  Edges Discovered: 5
  Related Entities: 4

Planning:
  Reasoning Plan: Yes
  Plan Components: ['product_plan', 'mdl_entities_plan', 'compliance_controls_plan', 'risks_plan', 'metrics_plan']
  Natural Language Questions: 8
```

## Usage Example

```python
from app.agents.mdl_reasoning_nodes import create_mdl_reasoning_graph
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory

# Initialize services
contextual_graph_storage = ContextualGraphStorage(...)
collection_factory = CollectionFactory(...)

# Create graph
graph = create_mdl_reasoning_graph(
    contextual_graph_storage=contextual_graph_storage,
    collection_factory=collection_factory,
    llm=llm
)

# Run graph
initial_state = {
    "user_question": "What tables are related to AccessRequest in Snyk?",
    "product_name": "Snyk",
    "identified_entities": [],
    "search_questions": [],
    "tables_found": [],
    "entities_found": [],
    "entity_questions": [],
    "contexts_retrieved": [],
    "edges_discovered": [],
    "related_entities": [],
    "natural_language_questions": [],
    "current_step": "start",
    "status": "processing",
    "messages": []
}

result = await graph.ainvoke(initial_state)

# Access results
print(f"Tables found: {len(result['tables_found'])}")
print(f"Entities found: {len(result['entities_found'])}")
print(f"Reasoning plan: {result['reasoning_plan']}")
print(f"Natural language questions: {result['natural_language_questions']}")
```

## Troubleshooting

### No Tables Found

**Problem**: Graph doesn't find any tables.

**Solutions**:
1. Verify MDL files are indexed: Check `indexing_preview/table_definitions/`
2. Verify contextual graph ingestion: Check `context_definitions` collection
3. Check product name matches: Use exact product name (e.g., "Snyk" not "snyk")
4. Verify collections exist: Check ChromaDB collections

### No Edges Discovered

**Problem**: Graph doesn't discover any edges.

**Solutions**:
1. Verify MDL ingestion created edges: Run `ingest_mdl_contextual_graph.py`
2. Check edge types: Verify `BELONGS_TO_TABLE`, `HAS_MANY_TABLES` edges exist
3. Check context IDs: Verify table entity IDs follow format `entity_{product}_{table}`

### Planning Fails

**Problem**: Planning node fails or returns empty plan.

**Solutions**:
1. Check LLM API key: Verify `OPENAI_API_KEY` is set
2. Check input data: Verify tables_found, entities_found are populated
3. Check prompt size: Reduce number of entities if prompt is too large

## Next Steps

After successful setup:
1. Test with different queries
2. Extend planning node to include more components
3. Add metrics generation
4. Integrate with compliance controls retrieval
5. Add risk assessment

