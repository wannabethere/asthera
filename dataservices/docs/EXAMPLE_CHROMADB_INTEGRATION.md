# Example ChromaDB Integration

## Overview

This implementation adds automatic ChromaDB indexing for examples with definition types "sql_pair" or "instruction". When a user example is persisted to the database, it is automatically indexed to the appropriate ChromaDB collection based on its definition type.

## Architecture

### Components

1. **Dependency Providers** (`app/core/dependencies.py`)
   - `get_sql_pairs_processor()`: Provides SQL pairs processor instance
   - `get_instructions_processor()`: Provides instructions processor instance
   - `get_persistence_factory()`: Updated to inject processors into factory

2. **Updated Persistence Service** (`app/service/persistence_service.py`)
   - `UserExamplePersistenceService`: Enhanced with ChromaDB indexing
   - `PersistenceServiceFactory`: Updated to accept and pass processors

3. **ChromaDB Processors**
   - `SqlPairs`: Handles SQL pair indexing (from `app/agents/indexing/sql_pairs.py`)
   - `Instructions`: Handles instruction indexing (from `app/agents/indexing/instructions.py`)

## Implementation Details

### 1. Database Schema Updates

The `Example` table has been enhanced with new fields to match the `UserExample` dataclass:

```sql
-- New fields added to the examples table
definition_type VARCHAR(50) NOT NULL DEFAULT 'sql_pair'
name VARCHAR(100) NOT NULL
additional_context JSONB
user_id VARCHAR(100) DEFAULT 'system'

-- Constraints and indexes
CHECK (definition_type IN ('metric', 'view', 'calculated_column', 'sql_pair', 'instruction'))
INDEX idx_examples_definition_type (definition_type)
```

### 2. Pydantic Model Updates

The API models have been updated to include the new fields:

- `ExampleCreate`: Added `definition_type`, `name`, `additional_context`, `user_id`
- `ExampleUpdate`: Added optional fields for updates
- `ExampleRead`: Added new fields to response model

### 3. Dependency Injection

Providers are created in `app/core/dependencies.py`:

```python
def get_sql_pairs_processor() -> SqlPairs:
    """Get SQL pairs processor instance"""
    chroma_client = get_chromadb_client()
    embeddings = get_embeddings()
    
    doc_store = DocumentChromaStore(
        persistent_client=chroma_client,
        collection_name="sql_pairs"
    )
    
    return SqlPairs(
        document_store=doc_store,
        embedder=embeddings
    )

def get_instructions_processor() -> Instructions:
    """Get instructions processor instance"""
    chroma_client = get_chromadb_client()
    embeddings = get_embeddings()
    
    doc_store = DocumentChromaStore(
        persistent_client=chroma_client,
        collection_name="instructions"
    )
    
    return Instructions(
        document_store=doc_store,
        embedder=embeddings
    )
```

### 4. Persistence Service Enhancement

The `UserExamplePersistenceService` has been enhanced with ChromaDB indexing:

```python
class UserExamplePersistenceService:
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager,
                 sql_pairs_processor=None, instructions_processor=None):
        self.session_manager = session_manager
        self.project_manager = project_manager
        self.sql_pairs_processor = sql_pairs_processor
        self.instructions_processor = instructions_processor

    async def persist_user_example(self, user_example: UserExample, project_id: str) -> str:
        """Persist user example to database and optionally index to ChromaDB"""
        # ... database persistence logic ...
        
        # Index to ChromaDB if definition type is sql_pair or instruction
        if user_example.definition_type in [DefinitionType.SQL_PAIR, DefinitionType.INSTRUCTION]:
            await self._index_to_chromadb(example, user_example)
        
        return str(example.example_id)

    async def _index_to_chromadb(self, example: Example, user_example: UserExample):
        """Index example to ChromaDB based on definition type"""
        try:
            if user_example.definition_type == DefinitionType.SQL_PAIR and self.sql_pairs_processor:
                # Convert to SqlPair format and index
                sql_pair_data = {
                    "question": example.question,
                    "sql": example.sql_query,
                    "instructions": example.instructions,
                    "chain_of_thought": example.json_metadata.get('chain_of_thought')
                }
                
                await self.sql_pairs_processor.run(
                    sql_pairs=[sql_pair_data],
                    project_id=example.project_id
                )
                
            elif user_example.definition_type == DefinitionType.INSTRUCTION and self.instructions_processor:
                # Convert to Instruction format and index
                instruction = ChromaInstruction(
                    instruction=example.instructions or example.question,
                    question=example.question,
                    sql=example.sql_query,
                    chain_of_thought=example.json_metadata.get('chain_of_thought'),
                    is_default=False
                )
                
                await self.instructions_processor.run(
                    instructions=[instruction],
                    project_id=example.project_id
                )
                
        except Exception as e:
            logger.error(f"Failed to index example to ChromaDB: {str(e)}")
            # Don't raise the exception to avoid failing the database transaction
```

## Usage

### Creating Examples with ChromaDB Indexing

```python
from app.service.models import UserExample, DefinitionType

# Create a SQL pair example (will be indexed to ChromaDB)
sql_pair_example = UserExample(
    definition_type=DefinitionType.SQL_PAIR,
    name="find_french_customers",
    description="Find all customers from France",
    sql="SELECT * FROM customers WHERE country = 'France'",
    additional_context={
        "context": "Customer analysis",
        "instructions": "Filter customers by country"
    },
    user_id="user_123"
)

# Create an instruction example (will be indexed to ChromaDB)
instruction_example = UserExample(
    definition_type=DefinitionType.INSTRUCTION,
    name="revenue_by_country",
    description="How to calculate total revenue by country",
    sql="SELECT country, SUM(revenue) as total_revenue FROM sales GROUP BY country",
    additional_context={
        "context": "Revenue analysis",
        "chain_of_thought": "1. Group by country\n2. Sum the revenue column"
    },
    user_id="user_123"
)

# Create a metric example (will NOT be indexed to ChromaDB)
metric_example = UserExample(
    definition_type=DefinitionType.METRIC,
    name="total_revenue",
    description="Total revenue metric",
    sql="SELECT SUM(revenue) FROM sales",
    user_id="user_123"
)

# Persist examples (ChromaDB indexing happens automatically)
example_id = await user_example_service.persist_user_example(
    sql_pair_example, 
    project_id="project_123"
)
```

## Configuration

### Required Environment Variables

```bash
# OpenAI API Key for embeddings
OPENAI_API_KEY=your_openai_api_key

# ChromaDB storage path
CHROMA_STORE_PATH=/path/to/chromadb

# Database connection
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
```

### ChromaDB Collections

The system uses two separate ChromaDB collections:

1. **sql_pairs**: Stores SQL pair examples with embeddings
2. **instructions**: Stores instruction examples with embeddings

Each collection is managed by its respective processor and maintains separate embeddings for optimal search performance.

## Error Handling

### Graceful Degradation

- ChromaDB indexing failures do not prevent database persistence
- Errors are logged but don't cause the main operation to fail
- Examples are still saved to the database even if ChromaDB indexing fails

### Error Recovery

- Failed ChromaDB indexing can be retried manually
- Database transactions are not affected by ChromaDB issues
- Comprehensive error logging for debugging

## Testing

### Test Script

A test script is provided at `test_example_chromadb_integration.py` that demonstrates:

1. Creating SQL pair examples (indexed to ChromaDB)
2. Creating instruction examples (indexed to ChromaDB)
3. Creating metric examples (not indexed to ChromaDB)
4. Retrieving examples from the database

### Running Tests

```bash
# Set environment variables
export OPENAI_API_KEY="your_key"
export CHROMA_STORE_PATH="./test_chroma_db"
export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/testdb"

# Run the test
python test_example_chromadb_integration.py
```

## Benefits

### 1. Automatic Indexing
- Examples are automatically indexed to ChromaDB based on their type
- No manual intervention required
- Consistent with existing ChromaDB indexing patterns

### 2. Type-Specific Processing
- SQL pairs and instructions are processed by their respective specialized processors
- Optimal embedding generation for each type
- Separate collections for better search performance

### 3. Shared Infrastructure
- Uses existing ChromaDB processors and infrastructure
- Consistent with the overall system architecture
- Leverages existing dependency injection patterns

### 4. Data Consistency
- Database and ChromaDB are kept in sync
- All examples are stored in the database regardless of ChromaDB status
- Proper error handling ensures data integrity

## Future Enhancements

### Potential Improvements

1. **Batch Processing**: Support for bulk ChromaDB indexing
2. **Incremental Updates**: Only re-index changed examples
3. **Search API**: REST endpoints for searching indexed examples
4. **Analytics**: Track indexing performance and usage statistics
5. **Custom Embeddings**: Support for different embedding models

### Integration Opportunities

1. **Real-time Search**: WebSocket-based real-time search capabilities
2. **Advanced Filtering**: Filter examples by project, user, or definition type
3. **Example Recommendations**: Suggest similar examples based on embeddings
4. **Quality Scoring**: Rate example quality based on usage and feedback

## Troubleshooting

### Common Issues

1. **ChromaDB Connection**: Verify ChromaDB is running and accessible
2. **OpenAI API**: Check API key and rate limits
3. **Database Schema**: Ensure the Example table has been updated with new fields
4. **Dependencies**: Verify all required packages are installed

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger("genieml-agents").setLevel(logging.DEBUG)
logging.getLogger("app.service.persistence_service").setLevel(logging.DEBUG)
```

## Support

For issues and questions:
1. Check error logs and ChromaDB status
2. Verify configuration settings
3. Test with the provided test script
4. Review this documentation
5. Contact the development team

---

*This implementation provides seamless ChromaDB integration for examples while maintaining data consistency and system reliability.* 