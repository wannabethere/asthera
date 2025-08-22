# Instruction Router Documentation

## Overview

The Instruction Router provides a comprehensive API for managing instructions in domains. Instructions contain questions, SQL queries, detailed instructions, and chain of thought reasoning that help users understand how to perform specific data operations.

## Features

- **CRUD Operations**: Create, read, update, and delete instructions
- **Batch Operations**: Create multiple instructions at once
- **Search & Filtering**: Find instructions by content or type
- **Domain Management**: Organize instructions by domain
- **Analytics**: Get summaries and insights about instructions
- **Authentication**: User-based access control

## API Endpoints

### Base URL
```
/instructions
```

### 1. Health Check
**GET** `/instructions/health`

Returns the health status of the instruction service and lists all available endpoints.

**Response:**
```json
{
  "status": "healthy",
  "service": "instruction_service",
  "endpoints": [
    "POST / - Create instruction",
    "GET /{id} - Get instruction",
    "PUT /{id} - Update instruction",
    "DELETE /{id} - Delete instruction",
    "GET / - List instructions",
    "POST /batch - Create instructions batch",
    "GET /domain/{id}/summary - Get domain summary",
    "GET /search/ - Search instructions",
    "GET /types/{type} - Get by type"
  ]
}
```

### 2. Create Instruction
**POST** `/instructions/`

Creates a new instruction with question, instructions, SQL query, and optional chain of thought.

**Request Body:**
```json
{
  "domain_id": "sales_analytics_001",
  "question": "How to calculate customer lifetime value?",
  "instructions": "Use the customer_orders table and aggregate by customer_id to calculate total spend per customer",
  "sql_query": "SELECT customer_id, SUM(order_amount) as clv FROM customer_orders GROUP BY customer_id",
  "chain_of_thought": "CLV is calculated by summing all order amounts per customer over their lifetime",
  "json_metadata": {
    "business_unit": "sales",
    "priority": "high",
    "tags": ["customer", "analytics", "clv"]
  }
}
```

**Response:**
```json
{
  "instruction_id": "uuid-string",
  "domain_id": "sales_analytics_001",
  "question": "How to calculate customer lifetime value?",
  "instructions": "Use the customer_orders table and aggregate by customer_id to calculate total spend per customer",
  "sql_query": "SELECT customer_id, SUM(order_amount) as clv FROM customer_orders GROUP BY customer_id",
  "chain_of_thought": "CLV is calculated by summing all order amounts per customer over their lifetime",
  "json_metadata": {
    "business_unit": "sales",
    "priority": "high",
    "tags": ["customer", "analytics", "clv"]
  },
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "entity_version": 1,
  "modified_by": "user123"
}
```

### 3. Get Instruction
**GET** `/instructions/{instruction_id}`

Retrieves a specific instruction by its ID.

**Response:** Same as create response above.

### 4. Update Instruction
**PUT** `/instructions/{instruction_id}`

Updates an existing instruction. Only provide the fields you want to update.

**Request Body:**
```json
{
  "question": "Updated question about customer lifetime value",
  "instructions": "Updated instructions for CLV calculation",
  "json_metadata": {
    "business_unit": "sales",
    "priority": "critical",
    "tags": ["customer", "analytics", "clv", "updated"]
  }
}
```

**Response:** Updated instruction object.

### 5. Delete Instruction
**DELETE** `/instructions/{instruction_id}`

Permanently removes an instruction from the system.

**Response:** 204 No Content

### 6. List Instructions
**GET** `/instructions/`

Retrieves a list of instructions, optionally filtered by domain.

**Query Parameters:**
- `domain_id` (optional): Filter instructions by domain

**Examples:**
```
GET /instructions/                           # Get all instructions
GET /instructions/?domain_id=sales_001      # Get instructions for specific domain
```

**Response:**
```json
[
  {
    "instruction_id": "uuid-1",
    "domain_id": "sales_001",
    "question": "How to calculate customer lifetime value?",
    "instructions": "...",
    "sql_query": "...",
    "chain_of_thought": "...",
    "json_metadata": {...},
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "entity_version": 1,
    "modified_by": "user123"
  },
  {
    "instruction_id": "uuid-2",
    "domain_id": "sales_001",
    "question": "How to analyze order patterns?",
    "instructions": "...",
    "sql_query": "...",
    "chain_of_thought": "...",
    "json_metadata": {...},
    "created_at": "2024-01-01T13:00:00Z",
    "updated_at": "2024-01-01T13:00:00Z",
    "entity_version": 1,
    "modified_by": "user123"
  }
]
```

### 7. List Instructions by Domain
**GET** `/instructions/domain/{domain_id}`

Retrieves all instructions for a specific domain.

**Response:** Same as list instructions above.

### 8. Create Instructions Batch
**POST** `/instructions/batch`

Creates multiple instructions at once for efficient bulk operations.

**Request Body:**
```json
{
  "instructions_data": [
    {
      "question": "How to calculate customer lifetime value?",
      "instructions": "Use customer_orders table and aggregate by customer_id",
      "sql_query": "SELECT customer_id, SUM(order_amount) as clv FROM customer_orders GROUP BY customer_id",
      "chain_of_thought": "CLV is calculated by summing all order amounts per customer",
      "metadata": {"business_unit": "sales", "priority": "high"}
    },
    {
      "question": "How to analyze order patterns?",
      "instructions": "Group orders by date and analyze trends",
      "sql_query": "SELECT DATE(order_date) as order_date, COUNT(*) as order_count FROM orders GROUP BY DATE(order_date)",
      "chain_of_thought": "Order patterns are analyzed by grouping orders by date",
      "metadata": {"business_unit": "operations", "priority": "medium"}
    }
  ],
  "domain_id": "sales_analytics_001"
}
```

**Response:**
```json
{
  "message": "Successfully created 2 instructions",
  "instruction_ids": ["uuid-1", "uuid-2"],
  "domain_id": "sales_analytics_001",
  "created_by": "user123"
}
```

### 9. Get Instruction Summary
**GET** `/instructions/domain/{domain_id}/summary`

Provides analytics and summary information about instructions in a domain.

**Response:**
```json
{
  "total_instructions": 15,
  "recent_instructions": [
    {
      "instruction_id": "uuid-1",
      "question": "How to calculate customer lifetime value?",
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "instruction_id": "uuid-2",
      "question": "How to analyze order patterns?",
      "created_at": "2024-01-01T13:00:00Z"
    }
  ],
  "instruction_types": {
    "calculation": 8,
    "query": 5,
    "creation": 2
  },
  "total_sql_queries": 15,
  "instructions_with_chain_of_thought": 12
}
```

### 10. Search Instructions
**GET** `/instructions/search/`

Searches through instruction questions and content for matching text.

**Query Parameters:**
- `query` (required): Search query text
- `domain_id` (optional): Filter by domain

**Example:**
```
GET /instructions/search/?query=customer&domain_id=sales_001
```

**Response:** List of matching instructions.

### 11. Get Instructions by Type
**GET** `/instructions/types/{instruction_type}`

Retrieves instructions filtered by their type.

**Query Parameters:**
- `domain_id` (optional): Filter by domain

**Examples:**
```
GET /instructions/types/sql_query
GET /instructions/types/instructions?domain_id=sales_001
```

**Response:** List of instructions of the specified type.

## Data Models

### InstructionCreate
```python
class InstructionCreate(BaseModel):
    domain_id: str                    # Domain ID
    question: str                     # Question or instruction title
    instructions: str                 # Detailed instructions
    sql_query: str                   # SQL query
    chain_of_thought: Optional[str]  # Chain of thought reasoning
    json_metadata: Optional[Dict[str, Any]]  # Additional metadata
```

### InstructionUpdate
```python
class InstructionUpdate(BaseModel):
    question: Optional[str]           # Question or instruction title
    instructions: Optional[str]       # Detailed instructions
    sql_query: Optional[str]         # SQL query
    chain_of_thought: Optional[str]  # Chain of thought reasoning
    json_metadata: Optional[Dict[str, Any]]  # Additional metadata
```

### InstructionRead
```python
class InstructionRead(BaseModel):
    instruction_id: str               # Unique identifier
    domain_id: str                   # Domain ID
    question: str                     # Question or instruction title
    instructions: str                 # Detailed instructions
    sql_query: str                   # SQL query
    chain_of_thought: Optional[str]  # Chain of thought reasoning
    json_metadata: Optional[Dict[str, Any]]  # Additional metadata
    created_at: datetime             # Creation timestamp
    updated_at: datetime             # Last update timestamp
    entity_version: int              # Version number
    modified_by: Optional[str]       # User who last modified
```

## Authentication

All endpoints require authentication via the `Authorization` header:

```
Authorization: Bearer <your_token>
```

For development/testing, the system will use a default user if no token is provided.

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- **400 Bad Request**: Invalid input data
- **401 Unauthorized**: Missing or invalid authentication
- **404 Not Found**: Instruction not found
- **500 Internal Server Error**: Server-side error

**Error Response Format:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Usage Examples

### Python Example
```python
import requests

# Create an instruction
instruction_data = {
    "domain_id": "sales_analytics_001",
    "question": "How to calculate customer lifetime value?",
    "instructions": "Use the customer_orders table and aggregate by customer_id",
    "sql_query": "SELECT customer_id, SUM(order_amount) as clv FROM customer_orders GROUP BY customer_id",
    "chain_of_thought": "CLV is calculated by summing all order amounts per customer",
    "json_metadata": {"business_unit": "sales", "priority": "high"}
}

headers = {"Authorization": "Bearer your_token"}
response = requests.post(
    "http://localhost:8000/instructions/",
    json=instruction_data,
    headers=headers
)

if response.status_code == 201:
    instruction = response.json()
    print(f"Created instruction: {instruction['instruction_id']}")
```

### cURL Example
```bash
# Create an instruction
curl -X POST "http://localhost:8000/instructions/" \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "domain_id": "sales_analytics_001",
    "question": "How to calculate customer lifetime value?",
    "instructions": "Use the customer_orders table and aggregate by customer_id",
    "sql_query": "SELECT customer_id, SUM(order_amount) as clv FROM customer_orders GROUP BY customer_id",
    "chain_of_thought": "CLV is calculated by summing all order amounts per customer",
    "json_metadata": {"business_unit": "sales", "priority": "high"}
  }'

# Get all instructions for a domain
curl -X GET "http://localhost:8000/instructions/domain/sales_analytics_001" \
  -H "Authorization: Bearer your_token"

# Search instructions
curl -X GET "http://localhost:8000/instructions/search/?query=customer&domain_id=sales_analytics_001" \
  -H "Authorization: Bearer your_token"
```

## Best Practices

### 1. **Question Design**
- Make questions clear and specific
- Use business terminology
- Include context about what the user is trying to achieve

### 2. **Instructions**
- Provide step-by-step guidance
- Include examples where helpful
- Explain the reasoning behind the approach

### 3. **SQL Queries**
- Use clear, readable SQL
- Include comments for complex queries
- Consider performance implications

### 4. **Chain of Thought**
- Explain the logical reasoning
- Break down complex concepts
- Help users understand the "why" behind the approach

### 5. **Metadata**
- Use consistent tags and categories
- Include business context
- Add priority levels for important instructions

## Performance Considerations

- **Batch Operations**: Use batch endpoints for creating multiple instructions
- **Domain Filtering**: Always filter by domain when possible
- **Search Optimization**: Use specific search terms for better results
- **Pagination**: For large datasets, consider implementing pagination

## Security Considerations

- **Authentication**: Implement proper JWT validation in production
- **Authorization**: Add domain-level access control
- **Input Validation**: Validate all input data
- **SQL Injection**: Ensure SQL queries are properly sanitized

## Testing

Use the provided test script to verify the router functionality:

```bash
python test_instruction_router.py
```

The test script will:
1. Check the health endpoint
2. Test CRUD operations
3. Test search and filtering
4. Test batch operations
5. Test summary endpoints

## Troubleshooting

### Common Issues

1. **Connection Errors**: Ensure the API server is running
2. **Authentication Errors**: Check your authorization header
3. **Database Errors**: Verify database connectivity and schema
4. **Validation Errors**: Check required fields in your requests

### Debug Mode

Enable debug logging by setting the log level to DEBUG in your application configuration.

## Support

For issues or questions:
1. Check the API documentation at `/docs`
2. Review the error messages in the response
3. Check the application logs for detailed error information
4. Verify your request format matches the expected schema
