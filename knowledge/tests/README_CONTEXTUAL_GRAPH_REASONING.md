# Contextual Graph Reasoning Integration Test

## Overview

This integration test (`test_integration_contextual_graph_reasoning.py`) demonstrates the full contextual graph reasoning pipeline using existing data in PostgreSQL and ChromaDB.

## Prerequisites

### 1. Database Setup

**PostgreSQL must be running with tables created.** Run these migration scripts:

```bash
# Base schema
psql -U postgres -d knowledge_db -f migrations/create_contextual_graph_schema.sql

# Contextual graph extension
psql -U postgres -d knowledge_db -f migrations/add_contextual_graph_tables.sql
```

### 2. Data Population

**IMPORTANT**: This test assumes data is already stored in PostgreSQL and ChromaDB.

Run the document ingestion test first to populate data:

```bash
python tests/test_integration_document_ingestion.py
```

This will:
- Extract and store contexts (healthcare, tech company)
- Extract and store controls (HIPAA, SOC2)
- Create contextual edges
- Store control profiles

### 3. Environment Variables

```bash
export OPENAI_API_KEY="your-openai-api-key"
export POSTGRES_HOST="localhost"      # Optional
export POSTGRES_PORT="5432"           # Optional
export POSTGRES_USER="postgres"       # Optional
export POSTGRES_PASSWORD="postgres"   # Optional
export POSTGRES_DB="knowledge_db"     # Optional
```

## Running the Test

### Run the Integration Test

```bash
cd knowledge
python tests/test_integration_contextual_graph_reasoning.py
```

Or with pytest:

```bash
pytest tests/test_integration_contextual_graph_reasoning.py -v -s
```

## What the Test Demonstrates

### Test 1: Context Retrieval and Reasoning Plan Creation
- Retrieves relevant contexts using `ContextualGraphRetrievalPipeline`
- Creates reasoning plans based on user queries
- Prioritizes contexts based on relevance
- Enriches contexts with metadata (edge counts, control counts, entity types)

**Example Query**: "What access control measures should I prioritize for a healthcare organization preparing for HIPAA audit?"

### Test 2: Multi-Hop Contextual Reasoning (with Retrieval)
- **Step 1**: Retrieves contexts using `ContextualGraphRetrievalPipeline`
- **Step 2**: Performs multi-hop reasoning through the contextual graph
- Traverses: Controls → Requirements → Evidence
- Uses reasoning plan from retrieval step
- Enriches reasoning path with entity information
- Generates context-specific insights

**Example Query**: "What evidence do I need for access controls?"

### Test 3: Priority Controls Reasoning (with Retrieval)
- **Step 1**: Retrieves contexts using `ContextualGraphRetrievalPipeline`
- **Step 2**: Gets priority controls for retrieved context
- Enriches with **all data stores**:
  - Requirements for each control
  - Evidence types
  - Measurements and compliance history
  - Risk analytics (trends, scores, failures)
  - Contextual edges (relationships)

**Example Query**: "access control compliance for healthcare organization"

### Test 4: Multi-Context Synthesis (with Retrieval)
- **Step 1**: Retrieves multiple contexts using `ContextualGraphRetrievalPipeline`
- **Step 2**: Synthesizes reasoning across retrieved contexts
- Identifies common patterns
- Highlights context-specific differences
- Provides actionable recommendations

**Example Query**: "What are the highest-risk controls?"

### Test 5: Infer Context Properties (with Retrieval)
- **Step 1**: Retrieves context using `ContextualGraphRetrievalPipeline`
- **Step 2**: Infers context-dependent properties for entities
- Uses comprehensive entity information from all stores
- LLM-enhanced inference with actual data

**Example**: Infers risk score, complexity, priority for a control in a specific context

### Test 6: Complete Workflow (Retrieval → Reasoning)
- **Complete end-to-end workflow**:
  1. Retrieve contexts and create reasoning plan
  2. Use reasoning plan for multi-hop reasoning
  3. Get priority controls using retrieved context
- Demonstrates how retrieval and reasoning work together
- Shows the full pipeline from query to actionable results

**Example Query**: "What access control measures should I prioritize for a healthcare organization preparing for HIPAA audit?"

### Test 7: Comprehensive Entity Information (with Retrieval)
- **Step 1**: Retrieves context using `ContextualGraphRetrievalPipeline`
- **Step 2**: Gets all available information about an entity
- Includes: control details, requirements, evidence, measurements, analytics
- Shows outgoing and incoming edges (relationships)

## Expected Output

The test will:

1. **Setup**: Connect to PostgreSQL and ChromaDB, initialize services and pipelines
2. **Context Retrieval**: Retrieve and prioritize contexts, create reasoning plans
3. **Multi-Hop Reasoning**: Perform reasoning through the graph
4. **Priority Controls**: Get enriched priority controls with all data
5. **Multi-Context Synthesis**: Synthesize across multiple contexts
6. **Property Inference**: Infer context-dependent properties
7. **Comprehensive Info**: Get full entity information
8. **Summary**: Display test results summary

### Sample Output

```
================================================================================
TEST 1: Context Retrieval and Reasoning Plan Creation
================================================================================

--- Test 1.1: Retrieve contexts for healthcare compliance ---
✓ Retrieved 3 contexts
  1. ctx_healthcare_001 - Priority: 0.95
     Edges: 45, Controls: 12
  2. ctx_tech_001 - Priority: 0.78
     Edges: 32, Controls: 8
✓ Created reasoning plan with 5 steps
  Step 1: context_analysis - Analyze healthcare context and regulatory requirements...
  Step 2: control_retrieval - Retrieve relevant controls for HIPAA access control...

================================================================================
TEST 2: Multi-Hop Contextual Reasoning
================================================================================

--- Using context: ctx_healthcare_001 ---
✓ Multi-hop reasoning completed
  Reasoning path: 3 hops
  Hop 1: controls - 3 entities
    Enriched with: 3 entities
  Hop 2: requirements - 5 entities
  Hop 3: evidence - 8 entities

  Final Answer:
  For access controls in your healthcare context, you need the following evidence...

================================================================================
TEST 3: Priority Controls Reasoning
================================================================================

✓ Retrieved 5 priority controls

  Control 1: HIPAA Access Control (164.312(a)(1))
    Requirements: 6
    Evidence types: 4
    Measurements: 12
    Contextual edges: 8
    Risk level: HIGH
    Risk score: 15.5

...
```

## Data Store Integration

The test verifies that all data stores are being used:

- ✅ **Controls** from `control_service`
- ✅ **Requirements** from `requirement_service`
- ✅ **Evidence Types** from `evidence_service`
- ✅ **Measurements** from `measurement_service`
- ✅ **Contextual Edges** from `vector_storage`
- ✅ **Control Profiles** from `vector_storage`

## Troubleshooting

### No Contexts Found

If you see "No contexts retrieved", make sure you've run the document ingestion test first:

```bash
python tests/test_integration_document_ingestion.py
```

### No Controls Found

If controls are not found, verify:
1. Controls were extracted and saved in the ingestion test
2. Database connection is working
3. Tables exist (run migrations)

### ChromaDB Errors

- Check that ChromaDB path is accessible
- Verify `./test_chroma_db` directory exists (created by ingestion test)
- Check ChromaDB version compatibility

### OpenAI API Errors

- Verify `OPENAI_API_KEY` is set correctly
- Check API key has sufficient credits
- Verify network connectivity

## Test Structure

```
ContextualGraphReasoningTest
├── setup()                    # Initialize connections and services
├── test_context_retrieval()   # Test retrieval pipeline (standalone)
├── test_multi_hop_reasoning()  # Test multi-hop reasoning (with integrated retrieval)
├── test_priority_controls()    # Test priority controls (with integrated retrieval)
├── test_multi_context_synthesis() # Test multi-context synthesis (with integrated retrieval)
├── test_infer_properties()     # Test property inference (with integrated retrieval)
├── test_complete_workflow()    # Test complete workflow (retrieval → reasoning)
├── test_comprehensive_entity_info() # Test comprehensive entity info (with integrated retrieval)
├── display_summary()           # Display test results
└── cleanup()                   # Clean up resources
```

## Integration Pattern

All reasoning tests now follow this pattern:

1. **Retrieve Contexts First**: Each reasoning test uses `ContextualGraphRetrievalPipeline` to retrieve relevant contexts
2. **Use Retrieved Contexts**: Reasoning is performed using the retrieved contexts
3. **Fallback Support**: If retrieval fails, tests fall back to previously retrieved contexts
4. **Complete Workflow**: Test 6 demonstrates the full retrieval → reasoning workflow

This ensures:
- ✅ Tests are self-contained (don't depend on Test 1)
- ✅ Demonstrates the full pipeline integration
- ✅ Shows how retrieval and reasoning work together
- ✅ Each test can run independently

## Next Steps

After running this test successfully:

1. **Verify Results**: Check that all reasoning types work correctly
2. **Review Enrichment**: Verify that all data stores are being used
3. **Check Performance**: Monitor query times and resource usage
4. **Extend Tests**: Add more test cases for edge cases

## Related Tests

- `test_integration_document_ingestion.py` - Populates data (run first)
- `test_data.py` - Test data definitions

## Related Documentation

- `app/agents/pipelines/CONTEXTUAL_GRAPH_USAGE.md` - Usage examples
- `app/agents/ENHANCEMENTS_SUMMARY.md` - Data store integration details
- `docs/contextual_graph_reasoning_agent.md` - Architecture documentation

