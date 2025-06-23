# SQL Correction Functionality

This document explains how to use the new SQL correction functionality in the SQL RAG Agent.

## Overview

The SQL correction functionality automatically attempts to fix SQL queries when post-processing fails. It uses comprehensive context including:
- Original user query
- Generated SQL that failed
- Reasoning used to generate the SQL
- Database schema contexts
- Error message from post-processing

## Automatic Usage

The correction is automatically triggered when post-processing fails in SQL generation. No additional code is needed.

## Manual Usage

You can also manually trigger SQL correction using the convenience function:

```python
from app.agents.nodes.sql.sql_rag_agent import correct_sql_with_rag

# Example usage
result = await correct_sql_with_rag(
    agent=sql_rag_agent,
    query="Show me active users",
    sql="SELECT * FROM users WHERE active = 1",  # Incorrect SQL
    reasoning="User wants to see active users, so I need to query the users table with active status",
    schema_contexts=["CREATE TABLE users (id INT, name VARCHAR(255), active BOOLEAN)"],
    error_message="Column 'active' not found or invalid boolean comparison"
)

# Check result
if result.get("valid_generation_results"):
    corrected_sql = result["valid_generation_results"][0]["sql"]
    correction_reasoning = result["valid_generation_results"][0]["sql_correction_reasoning"]
    print(f"Corrected SQL: {corrected_sql}")
    print(f"Correction Reasoning: {correction_reasoning}")
else:
    error = result["invalid_generation_results"][0]["error"]
    print(f"Correction failed: {error}")
```

## Response Format

The correction function returns a dictionary with the following structure:

```python
{
    "valid_generation_results": [
        {
            "sql": "SELECT id, name FROM users WHERE active = true",
            "parsed_entities": {},
            "reasoning": "Original reasoning used to generate SQL",
            "sql_correction_reasoning": "Fixed boolean comparison from 'active = 1' to 'active = true' based on schema definition",
            "type": "CORRECTION_SUCCESS",
            "original_error": "Column 'active' not found or invalid boolean comparison"
        }
    ],
    "invalid_generation_results": []
}
```

## Error Types

The correction can fail with different error types:

- `CORRECTION_SUCCESS`: Correction was successful and validated
- `CORRECTION_VALIDATION_ERROR`: Correction succeeded but failed post-processing validation
- `CORRECTION_FAILED`: Correction attempt failed
- `CORRECTION_HANDLER_ERROR`: Error in the correction handler itself

## Context Information

The correction system uses the following context to improve results:

1. **Database Schema**: Table definitions and column information
2. **Original Query**: The user's natural language query
3. **Reasoning Context**: The reasoning used to generate the original SQL
4. **Error Message**: Specific error from post-processing or execution

## Integration with Enhanced Agent

The correction functionality is also available in the `EnhancedSQLRAGAgent` with additional quality scoring:

```python
from app.agents.nodes.sql.sql_rag_agent import EnhancedSQLRAGAgent

enhanced_agent = EnhancedSQLRAGAgent(base_agent)
result = await enhanced_agent.correct_sql_with_scoring(
    sql="SELECT * FROM users WHERE active = 1",
    error_message="Column 'active' not found",
    schema_context=your_schema_context
)
```

## Testing

You can test the functionality using the provided test script:

```bash
python test_sql_correction.py
```

This will demonstrate the correction process with mock data and show the expected output format. 