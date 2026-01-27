# Data Assistance Assistant - Contextual Graph Integration

## Overview

The Data Assistance Assistant can now access the ChromaDB collections and contextual graph created by the ingestion scripts (`ingest_mdl_contextual_graph.py` and `ingest_preview_files.py`). This integration allows the assistant to:

- Retrieve contexts (entities, policies, domain knowledge) created by ingestion scripts
- Access compliance controls and control profiles
- Use contextual edges to understand relationships
- Query fields and schema information

## Collection Prefix Configuration

Both the ingestion scripts and the data assistance assistant use **empty collection prefix** (`""`) to match `collection_factory.py` collections. This ensures they access the same ChromaDB collections:

### Shared Collections (Unprefixed)

- `context_definitions` - Context definitions (entities, policies, domain knowledge)
- `contextual_edges` - Relationships between contexts, entities, and controls
- `control_context_profiles` - Control implementation profiles
- `compliance_controls` - Compliance control documents
- `fields` - Schema fields and metadata
- Other collections as defined in `collection_factory.py`

### Configuration

The data assistance assistant is initialized in `app/core/startup.py` with:

```python
collection_prefix = getattr(settings, 'DATA_ASSISTANCE_COLLECTION_PREFIX', "")
contextual_graph_service = ContextualGraphService(
    db_pool=db_pool,
    vector_store_client=vector_store_client,
    embeddings_model=embeddings,
    llm=llm,
    collection_prefix=collection_prefix  # Empty string to match ingestion scripts
)
```

You can override this by setting `DATA_ASSISTANCE_COLLECTION_PREFIX` in your settings, but it defaults to `""` to match the ingestion scripts.

## How It Works

### 1. Context Retrieval

The `ContextRetrievalNode` (in the framework) retrieves relevant contexts using:
- `ContextualGraphService.search_contexts()` - Searches `context_definitions` collection
- `ContextualGraphQueryEngine.find_relevant_contexts()` - Also searches indexed collections via `CollectionFactory`

### 2. Table Suggestion (NEW)

The `ContextualReasoningNode` suggests relevant database tables before retrieving data:
- `ContextualGraphReasoningAgent.suggest_relevant_tables()` - Analyzes query and context to suggest tables
- Searches `entities` and `table_definitions` collections for relevant tables
- Uses LLM to analyze query intent and context to suggest the most relevant tables
- Stores suggested tables in state for use by data retrieval

### 3. Data Retrieval (Uses Suggested Tables)

The `DataKnowledgeRetrievalNode` retrieves data using the suggested tables:
- **Database schemas**: Uses `RetrievalHelper.get_database_schemas()` with suggested table names
- **Metrics**: Uses `RetrievalHelper.get_metrics()` for existing metrics
- **Controls**: Uses `ContextualGraphService.search_controls()` for compliance controls

### 4. Control Retrieval

The `DataKnowledgeRetrievalNode` retrieves controls using:
- `ContextualGraphService.search_controls()` - Searches controls for a context
- Uses `context_ids` from framework's context retrieval
- Searches `compliance_controls` collection and `control_context_profiles`

## Usage Example

After ingesting MDL files or preview files:

```python
# 1. Ingest MDL file (creates contexts, edges, controls)
python -m indexing_cli.ingest_mdl_contextual_graph \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk

# 2. Ingest preview files (creates additional contexts, controls, etc.)
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview

# 3. Start the application - Data Assistance Assistant will automatically
#    use the same collections and can retrieve the ingested data
```

## Verification

To verify the integration is working:

1. **Check collections exist:**
   ```python
   from app.core.dependencies import get_chromadb_client
   client = get_chromadb_client()
   collections = client.list_collections()
   # Should include: context_definitions, contextual_edges, control_context_profiles, etc.
   ```

2. **Test context retrieval:**
   ```python
   # Query the data assistance assistant
   # It should be able to find contexts created by ingestion scripts
   ```

3. **Check logs:**
   - Look for: `"Created ContextualGraphService for Data Assistance Assistant (collection_prefix: 'none')"`
   - This confirms empty prefix is being used

## Troubleshooting

### Issue: Assistant can't find contexts created by ingestion scripts

**Solution:**
1. Verify both use the same `collection_prefix` (should be `""`)
2. Check that collections exist in ChromaDB:
   ```python
   client = get_chromadb_client()
   collection = client.get_collection("context_definitions")
   print(f"Documents: {collection.count()}")
   ```
3. Verify the ChromaDB path is the same for both ingestion and runtime

### Issue: Controls not found

**Solution:**
1. Ensure controls were ingested to `compliance_controls` collection
2. Check that `context_id` is correctly passed when searching controls
3. Verify framework name matches (e.g., "SOC2", "HIPAA")

## Architecture

```
┌─────────────────────────────────────┐
│  Ingestion Scripts                  │
│  (ingest_mdl_contextual_graph.py)    │
│  (ingest_preview_files.py)          │
└──────────────┬──────────────────────┘
               │
               │ Uses collection_prefix=""
               │
               ▼
┌─────────────────────────────────────┐
│  ChromaDB Collections               │
│  - context_definitions              │
│  - contextual_edges                │
│  - control_context_profiles         │
│  - compliance_controls              │
│  - fields                            │
│  - entities                          │
│  - table_definitions                │
└──────────────┬──────────────────────┘
               │
               │ Uses collection_prefix=""
               │
               ▼
┌─────────────────────────────────────┐
│  Data Assistance Assistant Flow      │
│                                       │
│  1. ContextRetrievalNode             │
│     → Retrieves relevant contexts    │
│                                       │
│  2. ContextualReasoningNode          │
│     → Suggests relevant tables       │
│     → Uses contextual graph          │
│                                       │
│  3. DataKnowledgeRetrievalNode       │
│     → Uses suggested tables          │
│     → Retrieves schemas, metrics,    │
│       and controls                    │
│                                       │
│  4. MetricGenerationNode             │
│     → Generates new metrics          │
│                                       │
│  5. DataAssistanceQANode             │
│     → Answers questions              │
└─────────────────────────────────────┘
```

## Related Files

- `app/core/startup.py` - Initializes data assistance assistant with correct collection prefix
- `app/agents/assistants/data_assistance_factory.py` - Factory for creating assistants
- `app/agents/assistants/data_assistance_nodes.py` - Nodes that retrieve from contextual graph
- `app/indexing/cli/ingest_mdl_contextual_graph.py` - MDL ingestion script
- `app/indexing/cli/ingest_preview_files.py` - Preview file ingestion script
- `app/services/contextual_graph_service.py` - Service for accessing contextual graph
- `app/storage/query/collection_factory.py` - Defines collection names (unprefixed)

