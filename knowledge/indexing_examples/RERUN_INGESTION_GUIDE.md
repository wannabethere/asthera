# How to Rerun Partial Ingestion

## Safe to Rerun

**Yes, you can safely rerun the ingestion command even if it was stopped partially.** The system is designed to be idempotent:

### 1. **PostgreSQL (Safe)**
- Uses `ON CONFLICT ... DO UPDATE` 
- Existing edges are updated, not duplicated
- Safe to rerun multiple times

### 2. **ChromaDB Vector Store (Safe)**
- ChromaDB's `add_documents()` with IDs will **overwrite** existing documents with the same ID
- No duplicates will be created
- Safe to rerun multiple times

## Simple Rerun (Recommended)

Just run the same command again:

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix comprehensive_index \
    --content-types contextual_edges
```

**What happens:**
- Already-ingested edges will be **updated** (not duplicated)
- Missing edges will be **added**
- The process will complete successfully

## Options for Rerunning

### Option 1: Simple Rerun (Default - Recommended)
```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix comprehensive_index \
    --content-types contextual_edges
```

**Pros:**
- Simple and safe
- Updates existing edges
- Adds missing edges
- No data loss

**Cons:**
- May take some time (but faster with batching now)
- Updates existing edges even if unchanged

### Option 2: Force Recreate (Nuclear Option)
If you want to completely start fresh:

```bash
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --collection-prefix comprehensive_index \
    --content-types contextual_edges \
    --force-recreate
```

**⚠️ Warning:** This will:
- **Delete** the entire collection
- **Recreate** it from scratch
- **Lose** any other data in that collection

**Use only if:**
- You want a completely fresh start
- You're sure no other data is in the collection
- You're okay with losing existing data

### Option 3: Skip PostgreSQL (If Only Vector Store Failed)
If only the PostgreSQL save failed but vector store succeeded:

```bash
# This will skip PostgreSQL saves
# (Not directly supported, but you can modify the code or just rerun normally)
```

Actually, just rerun normally - PostgreSQL will handle conflicts correctly.

## Monitoring Progress

The ingestion script provides progress logging:

```
Saving 30535 contextual edges in batches of 500
  ✓ Saved batch 1/62 (500 edges)
  ✓ Saved batch 2/62 (500 edges)
  ...
Successfully saved 30535/30535 contextual edges
```

If you see it continuing from where it left off, that's normal - it's processing all edges but updating existing ones.

## Checking What Was Already Ingested

### Check Vector Store
You can query ChromaDB to see how many edges are already stored:

```python
# Example Python code to check
from app.core.dependencies import get_chromadb_client, get_embeddings_model
from app.services.hybrid_search_service import HybridSearchService

client = get_chromadb_client()
embeddings = get_embeddings_model()

collection_name = "comprehensive_index_contextual_edges"  # Adjust prefix as needed
edges_service = HybridSearchService(
    vector_store_client=client,
    collection_name=collection_name,
    embeddings_model=embeddings
)

# Count documents (this is approximate)
# ChromaDB doesn't have a direct count, but you can query with a large top_k
results = await edges_service.hybrid_search(query="edge", top_k=10000)
print(f"Found approximately {len(results)} edges in vector store")
```

### Check PostgreSQL
```sql
SELECT COUNT(*) FROM contextual_relationships;
```

## Troubleshooting

### If Rerun Seems Slow
- This is normal - it's processing all edges
- Existing edges are being updated (which takes time)
- Consider using larger batch sizes if you have memory:
  ```bash
  --edge-batch-size 1000 --edge-postgres-batch-size 2000
  ```

### If You See Errors
- Check the logs for specific error messages
- Most errors are non-fatal and the process continues
- Individual edge failures don't stop the entire process

### If You Want to Skip Already-Processed Edges
Currently, there's no built-in "skip existing" option. The system updates existing edges instead. If you need this feature, you would need to:
1. Query existing edge IDs before ingestion
2. Filter them out from the ingestion list
3. This would require code modifications

## Best Practice

**Recommended approach:**
1. Just rerun the same command
2. Let it complete (it will update existing and add missing)
3. Monitor the logs to see progress
4. The batching optimizations make this much faster now

## Summary

✅ **Safe to rerun** - No duplicates will be created  
✅ **Idempotent** - Multiple runs produce the same result  
✅ **Updates existing** - Existing edges are refreshed  
✅ **Adds missing** - Missing edges are added  
✅ **No data loss** - Existing data is preserved (unless using --force-recreate)

Just run the same command again!
