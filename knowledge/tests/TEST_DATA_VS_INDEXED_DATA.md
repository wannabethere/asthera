# Test Data vs Indexed Data Discrepancy

## Problem Statement

The integration tests (`test_integration_document_ingestion.py`, `test_integration_contextual_graph_reasoning.py`, `test_integration_contextual_assistants.py`) use **synthetic test data** from `test_data.py`, but the actual system indexes **real data** from the `indexing_preview/` directory. This creates a mismatch where:

1. **Tests create data** using hardcoded test strings (HIPAA_CONTROL_TEXT, SOC2_CONTROL_TEXT, etc.)
2. **System indexes data** from `indexing_preview/` directory (table_definitions, policy_documents, etc.)
3. **Tests expect data** that matches what's indexed, but the test data is different from indexed data

## Current Test Data (`test_data.py`)

The tests use synthetic sample data:

- `HIPAA_CONTROL_TEXT` - Sample HIPAA access control requirement
- `SOC2_CONTROL_TEXT` - Sample SOC2 logical access control requirement
- `API_DEFINITION_DOC` - API security specification
- `METRICS_REGISTRY_DOC` - Metrics registry with SOC2 mappings
- `BUSINESS_PROCESS_WIKI` - Employee onboarding process
- `HEALTHCARE_CONTEXT_DESCRIPTION` - Healthcare organization context
- `TECH_COMPANY_CONTEXT_DESCRIPTION` - Technology company context

## Actual Indexed Data (`indexing_preview/`)

The indexing service processes real data from:

- `table_definitions/` - Database table definitions
- `table_descriptions/` - Table descriptions
- `column_definitions/` - Column definitions
- `schema_descriptions/` - Schema descriptions
- `policy_documents/` - Policy documents (split by extraction_type: context, entities, requirements, etc.)
- `riskmanagement_risk_controls/` - Risk controls

## Impact

1. **Test Isolation**: Tests create their own data, which is good for isolation but doesn't test against real indexed data
2. **Data Mismatch**: When tests run after indexing real data, they may not find the expected test data
3. **Collection Prefix**: Tests use `collection_prefix="comprehensive_index"` which matches indexing, but the content is different

## Solutions

### Option 1: Use Actual Indexed Data in Tests (Recommended)

Modify tests to:
1. Load data from `indexing_preview/` directory
2. Use the same data that's actually indexed
3. Query for data that exists in the indexed collections

**Pros:**
- Tests against real data
- Validates actual indexing pipeline
- Ensures tests work with production data

**Cons:**
- Tests depend on indexed data existing
- May need to run indexing first
- Less isolated (tests depend on external data)

### Option 2: Create Test Data in Indexed Format

Create a utility to:
1. Convert test data from `test_data.py` into indexed format
2. Save to `indexing_preview/` directory
3. Use `ingest_preview_files.py` to index test data
4. Run tests against indexed test data

**Pros:**
- Tests remain isolated
- Uses same indexing pipeline
- Predictable test data

**Cons:**
- Requires additional setup step
- Test data must be converted to indexed format

### Option 3: Hybrid Approach

1. Keep test data for unit tests
2. Use indexed data for integration tests
3. Add a flag to tests to choose data source

**Pros:**
- Flexible
- Supports both isolated and integration testing

**Cons:**
- More complex
- Requires maintaining both paths

## Recommended Approach

**✅ IMPLEMENTED: Option 1** - Use Actual Indexed Data in Tests

The tests have been updated to use actual indexed data from `indexing_preview/` directory:

1. **Created `tests/test_indexed_data_loader.py`**:
   - Discovers indexed data from `indexing_preview/` directory
   - Extracts context IDs, metadata, controls, and entities
   - Provides helper methods to access indexed data

2. **Updated test setup**:
   - Tests now discover indexed contexts during setup
   - Use actual context IDs from indexed data
   - Query for data that exists in indexed collections

3. **Updated test queries**:
   - Use general queries that match indexed policy/compliance data
   - Query for actual indexed contexts instead of creating synthetic ones
   - Use actual context IDs from indexed data

4. **Benefits**:
   - Tests against real indexed data
   - Validates actual indexing pipeline
   - Ensures tests work with production-like data
   - Tests are more realistic and catch real-world issues

## Implementation Status

✅ **COMPLETED** - Option 1 has been implemented:

1. **Created `tests/test_indexed_data_loader.py`**:
   - Discovers indexed data from `indexing_preview/` directory
   - Extracts context IDs, metadata, controls, and entities from JSON files
   - Provides helper methods: `get_context_ids()`, `get_context_metadata()`, `find_contexts_by_query()`

2. **Updated test setup** in all three integration tests:
   - `test_integration_contextual_graph_reasoning.py`
   - `test_integration_document_ingestion.py`
   - `test_integration_contextual_assistants.py`
   - All tests now discover indexed contexts during setup
   - Log discovered contexts for visibility

3. **Updated test queries**:
   - Changed from hardcoded context IDs (`healthcare_ctx`, `tech_company_ctx`) to actual indexed context IDs
   - Updated queries to match indexed policy/compliance data
   - Changed filters from `industry: "healthcare"` to `domain: "compliance"` to match indexed metadata

4. **Test behavior**:
   - Tests now query for actual indexed contexts
   - If no indexed data found, tests log warnings but continue
   - Tests are more realistic and validate against real indexed data

## Usage

To run tests with actual indexed data:

1. **Index data first** (if not already indexed):
   ```bash
   # Set ChromaDB path
   export CHROMA_STORE_PATH=/Users/sameermangalampalli/data/chroma_db
   export CHROMA_USE_LOCAL=true
   
   # Index data
   python -m app.indexing.cli.ingest_preview_files \
     --preview-dir indexing_preview \
     --collection-prefix comprehensive_index
   ```

2. **Run tests** (tests will use the same ChromaDB path):
   ```bash
   # Set test environment (same path as indexing)
   export CHROMA_STORE_PATH=/Users/sameermangalampalli/data/chroma_db
   export CHROMA_USE_LOCAL=true
   export VECTOR_STORE_TYPE=chroma
   
   # Run tests
   python -m tests.test_integration_contextual_graph_reasoning
   python -m tests.test_integration_document_ingestion
   python -m tests.test_integration_contextual_assistants
   ```
   
   **Note**: Tests automatically use `/Users/sameermangalampalli/data/chroma_db` as the ChromaDB path.

3. **Tests will**:
   - Discover indexed contexts from `indexing_preview/` directory
   - Use actual context IDs from indexed data
   - Query for contexts/controls that exist in indexed collections
   - Log discovered contexts for visibility

## Test Data Discovery

The `IndexedDataLoader` automatically discovers:
- **Contexts**: All `context_id` values from indexed documents
- **Context Metadata**: Extraction type, domain, framework, source file
- **Controls/Entities**: Entities with type "control" or "policy"
- **Content Types**: Count of files per content type

This allows tests to:
- Use actual indexed context IDs
- Query for data that exists in indexed collections
- Validate against real indexed data structure

## Next Steps

1. ✅ Document the discrepancy (this file)
2. ⏳ Create test data generator script
3. ⏳ Update test setup to use indexed test data
4. ⏳ Update test documentation
5. ⏳ Add CI/CD step to generate test data before running tests

