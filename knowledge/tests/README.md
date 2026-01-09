# Integration Tests for Document Ingestion

This directory contains integration tests for ingesting and storing various types of compliance documents into PostgreSQL and ChromaDB.

## Test Overview

The integration test (`test_integration_document_ingestion.py`) demonstrates:

1. **HIPAA/SOC2 Control Extraction**: Extracts control information from regulatory text (PDF content as text)
2. **Context Extraction**: Extracts organizational context from descriptions
3. **API Definition Storage**: Stores API security definitions as knowledge context
4. **Metrics Registry Storage**: Stores metrics registry with SOC2 compliance mappings
5. **Business Process Storage**: Stores business process wiki content
6. **Query Operations**: Searches and retrieves stored contexts and controls

## Prerequisites

### 1. Database Setup

**PostgreSQL must be running with tables created.** The test uses the database configuration from `app/core/settings.py`.

You need to manually create the database tables using the migration scripts:
- `migrations/create_contextual_graph_schema.sql`
- `migrations/create_universal_metadata_schema.sql`

Example:
```bash
psql -U postgres -d knowledge_db -f migrations/create_contextual_graph_schema.sql
psql -U postgres -d knowledge_db -f migrations/create_universal_metadata_schema.sql
```

### 2. Environment Variables

Set the following environment variables:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export POSTGRES_HOST="localhost"  # Optional, defaults to localhost
export POSTGRES_PORT="5432"       # Optional, defaults to 5432
export POSTGRES_USER="postgres"   # Optional, defaults to postgres
export POSTGRES_PASSWORD="postgres"  # Optional, defaults to postgres
export POSTGRES_DB="knowledge_db"   # Optional, defaults to knowledge_db
```

### 3. Python Dependencies

Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

## Running the Tests

### Run the Integration Test

```bash
cd knowledge
python -m pytest tests/test_integration_document_ingestion.py -v -s
```

Or run directly:
```bash
python tests/test_integration_document_ingestion.py
```

### Expected Output

The test will:
1. Connect to PostgreSQL and ChromaDB
2. Extract and save 2 organizational contexts (healthcare and tech company)
3. Extract and save 2 controls (HIPAA and SOC2)
4. Save API definition as context
5. Save metrics registry as context
6. Save business process as context
7. Query and display search results
8. Display a summary of all ingested data

## Test Data

Test data is defined in `test_data.py` and includes:

- **HIPAA_CONTROL_TEXT**: Sample HIPAA access control requirement
- **SOC2_CONTROL_TEXT**: Sample SOC2 logical access control requirement
- **API_DEFINITION_DOC**: API security and access control specification
- **METRICS_REGISTRY_DOC**: Metrics registry with SOC2 compliance mappings
- **BUSINESS_PROCESS_WIKI**: Employee onboarding process documentation
- **HEALTHCARE_CONTEXT_DESCRIPTION**: Healthcare organization context
- **TECH_COMPANY_CONTEXT_DESCRIPTION**: Technology company context

## Test Structure

The test follows this flow:

1. **Setup**: Initialize database connections, ChromaDB, embeddings, LLM, and services
2. **Extraction**: Use `ExtractionService` to extract structured data from documents
3. **Storage**: Use `ContextualGraphService` to store data in PostgreSQL and ChromaDB
4. **Query**: Search and retrieve stored data
5. **Display**: Show summary of ingested data

## ChromaDB Storage

ChromaDB data is stored locally in `./test_chroma_db` directory (created automatically).

## Troubleshooting

### Database Connection Errors

- Verify PostgreSQL is running: `pg_isready`
- Check database credentials in `app/core/settings.py`
- Ensure database exists: `createdb knowledge_db`

### OpenAI API Errors

- Verify `OPENAI_API_KEY` is set correctly
- Check API key has sufficient credits
- Verify network connectivity

### Import Errors

- Ensure you're running from the `knowledge` directory
- Check that all dependencies are installed
- Verify Python path includes the project root

## Next Steps

After running the test, you can:

1. Query the database directly to see stored data
2. Use ChromaDB client to explore vector embeddings
3. Extend the test with additional document types
4. Add more complex query scenarios

