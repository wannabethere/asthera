# Plan for Reindexing Table Schemas, Descriptions, and Column Metadata

## Overview
This plan outlines the steps to reindex table schemas, table descriptions, and column metadata from preview files in the `indexing_preview` directory. The semantic search capabilities will ensure that queries for "assets" return asset-related tables and queries for "vulnerabilities" return vulnerability-related tables based on content similarity, not category filtering.

## Current State Analysis

### Preview Files Available
The `indexing_preview` directory contains the following schema-related preview files:
- `table_definitions/table_definitions_20260123_180157_Snyk.json` (494 documents)
- `table_descriptions/table_descriptions_20260123_180157_Snyk.json` (495 documents)
- `column_definitions/column_definitions_20260123_180157_Snyk.json` (1571 documents)

### Key Observations
1. **Categories in Metadata**: Preview files contain `categories` arrays in metadata (e.g., `["asset", "compliance", "integration", "user"]`). Note: Categories are used by LLM for question identification, not for database filtering.
2. **Collections Used**: 
   - `table_definitions` → maps to `table_definitions` collection (unprefixed)
   - `table_descriptions` → maps to `table_descriptions` collection (unprefixed)
   - `column_definitions` → maps to `column_metadata` collection (unprefixed)
3. **Indexing Scripts**:
   - `index_mdl_standalone.py`: Indexes MDL files directly (not preview files)
   - `ingest_preview_files.py`: Ingests preview JSON files into ChromaDB stores

## Plan Steps

### Phase 1: Preparation and Verification

#### Step 1.1: Verify Preview File Structure
- [ ] Confirm all preview files are present in `indexing_preview/` directory
- [ ] Verify that preview files contain:
  - Proper metadata structure for table_definitions
  - Proper metadata structure for table_descriptions
  - Column metadata with table_name references for column_definitions

#### Step 1.2: Verify Current Database State
- [ ] Check existing collections in ChromaDB:
  - `table_definitions` (or `db_schema` if used)
  - `table_descriptions`
  - `column_metadata`
- [ ] Document current document counts in each collection

#### Step 1.3: Backup Current State (Optional but Recommended)
- [ ] Export current collection data if needed for rollback
- [ ] Document current collection configurations

### Phase 2: Reindexing Strategy

#### Step 2.1: Determine Reindexing Approach

**Option A: Use `ingest_preview_files.py` (Recommended)**
- This script is designed to ingest preview files directly
- Handles routing to correct collections
- Supports metadata preservation
- Can use `--content-types` to target specific content types

**Option B: Use `index_mdl_standalone.py`**
- Would require converting preview files back to MDL format
- Not recommended as preview files are already processed

#### Step 2.2: Reindexing Command Strategy

**For table_definitions:**
```bash
python -m indexing_cli.ingest_preview_files \
  --preview-dir indexing_preview \
  --content-types table_definitions \
  --collection-prefix "" \
  --force-recreate  # Only if needed to fix dimension mismatches
```

**For table_descriptions:**
```bash
python -m indexing_cli.ingest_preview_files \
  --preview-dir indexing_preview \
  --content-types table_descriptions table_descriptions column_definitions \
  --collection-prefix ""
  --force-recreate
```

**For column_definitions:**
```bash
python -m indexing_cli.ingest_preview_files \
  --preview-dir indexing_preview \
  --content-types column_definitions \
  --collection-prefix ""
```

**For all schema-related content types at once:**
```bash
python -m indexing_cli.ingest_preview_files \
  --preview-dir indexing_preview \
  --content-types table_definitions table_descriptions column_definitions \
  --collection-prefix ""
```

### Phase 3: Testing and Validation

#### Step 3.1: Dry Run First
```bash
python -m indexing_cli.ingest_preview_files \
  --preview-dir indexing_preview \
  --content-types table_definitions table_descriptions column_definitions \
  --collection-prefix "" \
  --dry-run
```
- [ ] Review dry-run output to verify:
  - Correct routing to collections
  - Metadata preservation
  - Document counts match preview files

#### Step 3.2: Execute Reindexing
- [ ] Run actual ingestion (without `--dry-run`)
- [ ] Monitor for errors (dimension mismatches, collection creation issues)
- [ ] Verify document counts after ingestion

#### Step 3.3: Test Asset Queries
- [ ] Query for asset-related tables using semantic search:
  ```python
  # Example query structure - semantic search without category filters
  results = await retriever.retrieve_table_descriptions(
      query="asset tables",
      top_k=10
  )
  ```
- [ ] Verify results contain asset-related tables based on semantic similarity
- [ ] Check that asset-related tables are returned (e.g., Asset, AssetAttributes, etc.)

#### Step 3.4: Test Vulnerability Queries
- [ ] Query for vulnerability-related tables using semantic search:
  ```python
  results = await retriever.retrieve_table_descriptions(
      query="vulnerability tables",
      top_k=10
  )
  ```
- [ ] Verify results contain vulnerability-related tables based on semantic similarity
- [ ] Check that vulnerability-related tables are returned

#### Step 3.5: Test General Queries
- [ ] Test general queries to ensure all tables are accessible
- [ ] Verify semantic search returns relevant results based on query content

### Phase 4: Documentation and Cleanup

#### Step 4.1: Document Changes
- [ ] Document which collections were reindexed
- [ ] Record document counts before and after
- [ ] Note any issues encountered and resolutions

#### Step 4.2: Update Retrieval Documentation
- [ ] Document semantic search capabilities for asset and vulnerability queries
- [ ] Provide examples for asset and vulnerability queries
- [ ] Note that categories are for LLM guidance only, not database filtering

## Implementation Notes

### Collection Naming
- Schema collections are **unprefixed** (empty `--collection-prefix ""`)
- This matches `project_reader.py` and `index_mdl_standalone.py` behavior
- Collections: `table_definitions`, `table_descriptions`, `column_metadata`

### Potential Issues and Solutions

#### Issue 1: Dimension Mismatch
- **Symptom**: Error about embedding dimension mismatch
- **Solution**: Use `--force-recreate` flag to delete and recreate collections

#### Issue 2: Semantic Search Not Returning Expected Results
- **Symptom**: Queries for "assets" or "vulnerabilities" return irrelevant tables
- **Solution**: 
  - Verify embeddings are properly generated from table descriptions
  - Check that table descriptions contain relevant keywords
  - Ensure query text is specific enough (e.g., "asset tables" vs "asset")

## Success Criteria

1. ✅ All preview files successfully ingested into correct collections
2. ✅ Document counts match preview file counts
3. ✅ Metadata preserved in all documents
4. ✅ Asset queries return asset-related tables based on semantic similarity
5. ✅ Vulnerability queries return vulnerability-related tables based on semantic similarity
6. ✅ Semantic search provides relevant results with minimal false positives
7. ✅ General queries work correctly and return appropriate results

## Rollback Plan

If reindexing causes issues:
1. Restore from backup (if created)
2. Or delete affected collections and re-run with corrected parameters
3. Collections can be recreated from preview files at any time

## Next Steps After Reindexing

1. Monitor retrieval performance with semantic search
2. Fine-tune embeddings or query processing if needed
3. Update agent prompts to leverage semantic search capabilities
4. Consider query optimization if retrieval performance needs improvement
