# Follow-up SQL API Request Example

This document provides example API requests for follow-up SQL queries using the `/ask/query` endpoint.

## Endpoint
```
POST /ask/query
```

## Required Fields

- `query` (string): The follow-up question
- `histories` (array): List of previous questions and their SQL results (required for follow-up queries)

## Optional Fields

- `query_id` (string): Unique identifier for the query (auto-generated if not provided)
- `project_id` (string): Project identifier
- `mdl_hash` (string): MDL schema hash
- `thread_id` (string): Thread identifier for grouping related queries
- `configurations` (object): Configuration settings
  - `language` (string): Language for responses (default: "English")
  - `timezone` (object): Timezone settings
    - `name` (string): Timezone name (default: "UTC")
  - `fiscal_year` (object): Fiscal year settings
    - `start` (string): Fiscal year start date
    - `end` (string): Fiscal year end date
- `enable_scoring` (boolean): Enable quality scoring (default: true)
- `previous_questions` (array): List of previous question strings

## Example 1: Basic Follow-up Query

```json
{
  "query": "What about the average for each region?",
  "project_id": "project-123",
  "histories": [
    {
      "question": "Show me total sales by product",
      "sql": "SELECT product_name, SUM(sales_amount) as total_sales FROM sales_table GROUP BY product_name"
    }
  ],
  "configurations": {
    "language": "English",
    "timezone": {
      "name": "UTC"
    }
  },
  "enable_scoring": true
}
```

## Example 2: Follow-up with Multiple History Entries

```json
{
  "query": "Now show me the top 5 products by sales",
  "project_id": "project-123",
  "thread_id": "thread-abc-123",
  "histories": [
    {
      "question": "Show me total sales by product",
      "sql": "SELECT product_name, SUM(sales_amount) as total_sales FROM sales_table GROUP BY product_name"
    },
    {
      "question": "What about the average for each region?",
      "sql": "SELECT region, AVG(sales_amount) as avg_sales FROM sales_table GROUP BY region"
    }
  ],
  "configurations": {
    "language": "English",
    "timezone": {
      "name": "America/New_York"
    }
  },
  "enable_scoring": true
}
```

## Example 3: Follow-up with Fiscal Year Configuration

```json
{
  "query": "Compare this year's sales to last year",
  "project_id": "project-123",
  "mdl_hash": "mdl-hash-abc123",
  "histories": [
    {
      "question": "What are the total sales for this fiscal year?",
      "sql": "SELECT SUM(sales_amount) as total_sales FROM sales_table WHERE fiscal_year = '2024'"
    }
  ],
  "configurations": {
    "language": "English",
    "timezone": {
      "name": "UTC"
    },
    "fiscal_year": {
      "start": "2024-04-01",
      "end": "2025-03-31"
    }
  },
  "enable_scoring": true,
  "previous_questions": [
    "What are the total sales for this fiscal year?"
  ]
}
```

## Example 4: Minimal Follow-up Request

```json
{
  "query": "And what about the breakdown by month?",
  "histories": [
    {
      "question": "Show me total sales",
      "sql": "SELECT SUM(sales_amount) as total_sales FROM sales_table"
    }
  ]
}
```

## cURL Example

```bash
curl -X POST "http://localhost:8000/ask/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What about the average for each region?",
    "project_id": "project-123",
    "histories": [
      {
        "question": "Show me total sales by product",
        "sql": "SELECT product_name, SUM(sales_amount) as total_sales FROM sales_table GROUP BY product_name"
      }
    ],
    "configurations": {
      "language": "English",
      "timezone": {
        "name": "UTC"
      }
    },
    "enable_scoring": true
  }'
```

## Python Example

```python
import requests

url = "http://localhost:8000/ask/query"

payload = {
    "query": "What about the average for each region?",
    "project_id": "project-123",
    "histories": [
        {
            "question": "Show me total sales by product",
            "sql": "SELECT product_name, SUM(sales_amount) as total_sales FROM sales_table GROUP BY product_name"
        }
    ],
    "configurations": {
        "language": "English",
        "timezone": {
            "name": "UTC"
        }
    },
    "enable_scoring": True
}

response = requests.post(url, json=payload)
result = response.json()
print(result)
```

## Response Structure

The API returns an `AskResultResponse` with the following structure:

```json
{
  "status": "finished",
  "type": "TEXT_TO_SQL",
  "response": [
    {
      "sql": "SELECT region, AVG(sales_amount) as avg_sales FROM sales_table GROUP BY region",
      "type": "llm"
    }
  ],
  "sql_generation_reasoning": "Step-by-step reasoning about the query...",
  "retrieved_tables": ["sales_table"],
  "is_followup": true,
  "quality_scoring": {
    "final_score": 0.85,
    "quality_level": "good",
    "improvement_recommendations": [],
    "processing_time_seconds": 2.5
  },
  "answer": "The average sales for each region is...",
  "explanation": "This query calculates the average sales amount grouped by region...",
  "metadata": {
    "operation_type": "generation",
    "reasoning": "...",
    "parsed_entities": {}
  }
}
```

## Key Points for Follow-up Queries

1. **Histories Array**: Must contain at least one entry with `question` and `sql` fields
2. **Context Preservation**: The system uses the history to understand context and generate appropriate follow-up SQL
3. **Follow-up Reasoning**: When histories are present, the system automatically uses `followup_sql_reasoning` and `followup_sql_generation` pipelines
4. **Thread ID**: Use `thread_id` to group related queries in a conversation
5. **Query ID**: Can be manually set or auto-generated for tracking purposes

## Status Values

The response `status` field can be one of:
- `"understanding"`: Processing intent
- `"searching"`: Retrieving relevant data
- `"planning"`: Generating SQL reasoning
- `"generating"`: Generating SQL
- `"correcting"`: Correcting SQL errors
- `"executing_sql"`: Executing SQL query
- `"generating_answer"`: Generating human-readable answer
- `"finished"`: Request completed successfully
- `"failed"`: Request failed

