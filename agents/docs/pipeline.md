# SQL RAG System Documentation

A comprehensive self-correcting RAG (Retrieval-Augmented Generation) system for SQL operations using Langchain agents, replacing the original Haystack implementation.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation & Setup](#installation--setup)
4. [Quick Start](#quick-start)
5. [Core Components](#core-components)
6. [Usage Examples](#usage-examples)
7. [API Reference](#api-reference)
8. [Advanced Features](#advanced-features)
9. [Migration Guide](#migration-guide)

## Overview

The SQL RAG System provides a unified interface for all SQL-related operations:

- **SQL Generation**: Convert natural language to SQL
- **SQL Breakdown**: Break complex SQL into understandable steps
- **SQL Reasoning**: Generate step-by-step reasoning plans
- **SQL Answer**: Convert SQL results to natural language
- **SQL Correction**: Auto-correct invalid SQL queries
- **SQL Expansion**: Modify SQL based on user requests
- **SQL Question**: Convert SQL to natural language questions
- **SQL Summary**: Summarize SQL queries

### Key Features

- ✅ **Self-Correcting**: Automatically detects and fixes SQL errors
- ✅ **RAG-Enabled**: Uses vector search for relevant schema and examples
- ✅ **Modular Design**: Use individual tools or complete workflows
- ✅ **Langchain Integration**: Full Langchain agent ecosystem support
- ✅ **No Haystack Dependencies**: Pure Langchain implementation
- ✅ **Production Ready**: Comprehensive error handling and logging

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SQL RAG System                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │   SQL Interface │  │        SQL RAG Agent             │  │
│  │   (Simplified)  │  │     (Self-Correcting)            │  │
│  └─────────────────┘  └──────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  Individual     │  │   Vector Stores │  │   Post      │  │
│  │  SQL Tools      │  │   (Schema/      │  │ Processors  │  │
│  │                 │  │    Samples)     │  │             │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │   SQL Utils     │  │    Langchain    │                   │
│  │  (Processors)   │  │     Agents      │                   │
│  └─────────────────┘  └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Installation & Setup

### Prerequisites

```bash
pip install langchain
pip install openai  # or your preferred LLM provider
pip install faiss-cpu  # for vector search
pip install orjson
pip install pydantic
pip install aiohttp
```

### Basic Setup

```python
from langchain.llms import OpenAI
from src.pipelines.generation.utils.sql_interface import SQLPipelineFactory
from src.core.engine import Engine  # Your existing engine

# Initialize components
llm = OpenAI(temperature=0.1)
engine = Engine()  # Your database engine

# Create pipeline
pipeline = SQLPipelineFactory.create_rag_pipeline(engine)
```

## Quick Start

### 1. Simple SQL Generation

```python
import asyncio
from src.pipelines.generation.utils.sql_interface import quick_sql_generation

async def main():
    schema_docs = [
        "CREATE TABLE users (id INT, name VARCHAR, email VARCHAR)",
        "CREATE TABLE orders (id INT, user_id INT, total DECIMAL)"
    ]
    
    result = await quick_sql_generation(
        query="Show me all users with their order count",
        schema_documents=schema_docs,
        engine=engine,
        language="English"
    )
    
    print(f"Generated SQL: {result.get('sql')}")

asyncio.run(main())
```

### 2. Complete Workflow

```python
from src.pipelines.generation.utils.sql_interface import complete_sql_analysis

async def complete_example():
    schema_docs = ["CREATE TABLE products (id INT, name VARCHAR, price DECIMAL)"]
    
    results = await complete_sql_analysis(
        query="What are the most expensive products?",
        schema_documents=schema_docs,
        engine=engine,
        language="English"
    )
    
    print("Reasoning:", results.get('reasoning'))
    print("SQL:", results.get('generation'))
    print("Breakdown:", results.get('breakdown'))

asyncio.run(complete_example())
```

## Core Components

### 1. SQL Pipeline (`sql_interface.py`)

The main interface providing all SQL operations:

```python
from src.pipelines.generation.utils.sql_interface import SQLPipeline, SQLRequest

pipeline = SQLPipeline(llm=llm, engine=engine, use_rag=True)

# Initialize knowledge base
pipeline.initialize_knowledge_base(
    schema_documents=["CREATE TABLE ..."],
    sql_samples=[{"question": "...", "sql": "..."}]
)

# Create request
request = SQLRequest(
    query="Your natural language query",
    language="English",
    contexts=["Additional context"]
)

# Generate SQL
result = await pipeline.generate_sql(request)
```

### 2. SQL RAG Agent (`sql_rag_agent.py`)

Self-correcting agent with full RAG capabilities:

```python
from src.pipelines.generation.utils.sql_rag_agent import create_sql_rag_agent, SQLOperationType

agent = create_sql_rag_agent(llm, engine)

# Process different operations
result = await agent.process_sql_request(
    SQLOperationType.GENERATION,
    "Show me customer orders",
    language="English"
)
```

### 3. Individual Tools (`sql_tools.py`)

Modular tools for specific operations:

```python
from src.pipelines.generation.utils.sql_tools import SQLGenerationTool

sql_gen = SQLGenerationTool(llm, engine)
result = await sql_gen.run(
    query="Get all customers",
    contexts=["CREATE TABLE customers ..."]
)
```

### 4. Utilities (`sql.py`)

Core utilities and processors:

```python
from src.pipelines.generation.utils.sql import (
    SQLGenPostProcessor,
    SQLBreakdownGenPostProcessor,
    TEXT_TO_SQL_RULES
)
```

## Usage Examples

### Example 1: End-to-End SQL Generation with Validation

```python
import asyncio
from src.pipelines.generation.utils.sql_interface import SQLPipeline, SQLRequest
from src.web.v1.services import Configuration

async def sql_generation_example():
    # Setup
    pipeline = SQLPipeline(llm=llm, engine=engine, use_rag=True)
    
    # Initialize with your schema
    schema_docs = [
        """
        CREATE TABLE customers (
            id INT PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100),
            created_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE orders (
            id INT PRIMARY KEY,
            customer_id INT,
            total DECIMAL(10,2),
            order_date TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
        """
    ]
    
    sql_samples = [
        {
            "question": "How many customers do we have?",
            "sql": "SELECT COUNT(*) FROM customers"
        },
        {
            "question": "What's the total revenue?",
            "sql": "SELECT SUM(total) FROM orders"
        }
    ]
    
    pipeline.initialize_knowledge_base(schema_docs, sql_samples)
    
    # Create request
    request = SQLRequest(
        query="Show me customers who have spent more than $1000 total",
        language="English",
        configuration=Configuration()
    )
    
    # Generate SQL with self-correction
    result = await pipeline.generate_sql(request)
    
    if result.success:
        print(f"✅ Generated SQL: {result.data['sql']}")
        print(f"🧠 Reasoning: {result.data.get('reasoning', 'N/A')}")
        
        if result.data.get('corrected'):
            print(f"🔧 Auto-corrected from error: {result.data['original_error']}")
    else:
        print(f"❌ Error: {result.error}")

asyncio.run(sql_generation_example())
```

### Example 2: SQL Breakdown and Explanation

```python
async def sql_breakdown_example():
    pipeline = SQLPipeline(llm=llm, engine=engine)
    
    complex_sql = """
    WITH customer_totals AS (
        SELECT 
            c.id,
            c.name,
            SUM(o.total) as total_spent
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        WHERE o.order_date >= '2023-01-01'
        GROUP BY c.id, c.name
    )
    SELECT * FROM customer_totals 
    WHERE total_spent > 1000 
    ORDER BY total_spent DESC
    """
    
    request = SQLRequest(
        query="Explain this complex query",
        language="English"
    )
    
    breakdown_result = await pipeline.breakdown_sql(request, complex_sql)
    
    if breakdown_result.success:
        breakdown = breakdown_result.data
        print(f"📝 Description: {breakdown['description']}")
        print("🔍 Steps:")
        for i, step in enumerate(breakdown['steps'], 1):
            print(f"  {i}. {step['summary']}")
            print(f"     SQL: {step['sql']}")

asyncio.run(sql_breakdown_example())
```

### Example 3: Error Correction Workflow

```python
async def error_correction_example():
    pipeline = SQLPipeline(llm=llm, engine=engine, use_rag=True)
    
    # Simulate invalid SQL
    invalid_sql = "SELECT * FROM non_existent_table WHERE invalid_column = 'value'"
    error_msg = "Table 'non_existent_table' doesn't exist"
    
    contexts = ["CREATE TABLE customers (id INT, name VARCHAR)"]
    
    correction_result = await pipeline.correct_sql(
        sql=invalid_sql,
        error_message=error_msg,
        contexts=contexts
    )
    
    if correction_result.success:
        print(f"🔧 Corrected SQL: {correction_result.data['sql']}")
    else:
        print(f"❌ Correction failed: {correction_result.error}")

asyncio.run(error_correction_example())
```

### Example 4: Complete Analysis Workflow

```python
async def complete_workflow_example():
    """Demonstrates the complete SQL analysis workflow"""
    
    pipeline = SQLPipeline(llm=llm, engine=engine, use_rag=True)
    
    # Setup knowledge base
    schema_docs = [
        "CREATE TABLE products (id INT, name VARCHAR, category VARCHAR, price DECIMAL)",
        "CREATE TABLE sales (id INT, product_id INT, quantity INT, sale_date DATE)"
    ]
    
    pipeline.initialize_knowledge_base(schema_documents=schema_docs)
    
    request = SQLRequest(
        query="What are the top-selling products by category in the last quarter?",
        language="English"
    )
    
    # Run complete workflow
    results = await pipeline.complete_sql_workflow(request)
    
    # Display results
    for step, result in results.items():
        print(f"\n=== {step.upper()} ===")
        if result.success:
            if step == "reasoning":
                print(result.data.get("reasoning", ""))
            elif step == "generation":
                print(f"SQL: {result.data.get('sql', '')}")
            elif step == "breakdown":
                breakdown = result.data
                print(f"Description: {breakdown.get('description', '')}")
                for i, s in enumerate(breakdown.get('steps', []), 1):
                    print(f"{i}. {s.get('summary', '')}")
            elif step == "answer":
                print(f"Answer: {result.data.get('answer', '')}")
        else:
            print(f"Error: {result.error}")

asyncio.run(complete_workflow_example())
```

## API Reference

### SQLPipeline Class

#### Methods:

- `initialize_knowledge_base(schema_documents, sql_samples)`: Initialize RAG knowledge base
- `generate_sql(request)`: Generate SQL from natural language
- `breakdown_sql(request, sql)`: Break down SQL into steps
- `generate_reasoning(request)`: Generate reasoning plan
- `generate_answer(request, sql, sql_data)`: Generate natural language answer
- `correct_sql(sql, error_message, contexts)`: Correct invalid SQL
- `expand_sql(adjustment_request, original_sql, contexts)`: Expand SQL
- `sql_to_questions(sqls, language)`: Convert SQL to questions
- `summarize_sqls(query, sqls, language)`: Summarize SQL queries
- `complete_sql_workflow(request)`: Run complete workflow

### SQLRequest Class

```python
@dataclass
class SQLRequest:
    query: str
    language: str = "English"
    contexts: List[str] = None
    sql_samples: List[Dict[str, str]] = None
    configuration: Configuration = None
    project_id: str = None
    timeout: float = 30.0
```

### SQLResult Class

```python
@dataclass
class SQLResult:
    success: bool
    data: Dict[str, Any] = None
    error: str = None
    metadata: Dict[str, Any] = None
```

## Advanced Features

### 1. Custom LLM Providers

```python
from langchain.llms import HuggingFacePipeline

# Use custom LLM
custom_llm = HuggingFacePipeline.from_model_id(
    model_id="codellama/CodeLlama-7b-Python-hf",
    task="text-generation"
)

pipeline = SQLPipeline(llm=custom_llm, engine=engine)
```

### 2. Custom Embeddings

```python
from langchain.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

pipeline = SQLPipeline(
    llm=llm,
    engine=engine,
    embeddings=embeddings,
    use_rag=True
)
```

### 3. Streaming Support

```python
# For real-time responses (available in some tools)
async def streaming_example():
    # This would be implemented in individual tools that support streaming
    pass
```

### 4. Configuration Options

```python
from src.web.v1.services import Configuration

config = Configuration(
    language="English",
    fiscal_year={"start": "2023-04-01", "end": "2024-03-31"}
)

request = SQLRequest(
    query="Show quarterly revenue",
    configuration=config
)
```

## Migration Guide

### From Haystack to Langchain

#### Old Haystack Implementation:

```python
# OLD - Haystack
from haystack import component
from haystack.components.builders.prompt_builder import PromptBuilder

@component
class SQLGenerator:
    @component.output_types(sql=str)
    def run(self, query: str) -> dict:
        # Haystack component logic
        pass
```

#### New Langchain Implementation:

```python
# NEW - Langchain
from langchain.agents import Tool
from langchain.chains import LLMChain

class SQLGenerationTool:
    def __init__(self, llm, engine):
        self.llm = llm
        self.engine = engine
    
    async def run(self, query: str, **kwargs) -> Dict[str, Any]:
        # Langchain tool logic
        pass
```

### Migration Steps:

1. **Replace Imports**:
   ```python
   # Remove
   from haystack import component
   from haystack.components.builders.prompt_builder import PromptBuilder
   
   # Add
   from langchain.agents import Tool
   from langchain.chains import LLMChain
   from langchain.prompts import PromptTemplate
   ```

2. **Update Component Structure**:
   ```python
   # Old component
   @component
   class MyComponent:
       @component.output_types(result=str)
       def run(self, input: str) -> dict:
           return {"result": "output"}
   
   # New tool
   class MyTool:
       async def run(self, input: str, **kwargs) -> Dict[str, Any]:
           return {"result": "output", "success": True}
   ```

3. **Replace Pipeline Execution**:
   ```python
   # Old Hamilton pipeline
   result = await driver.execute(["final_step"], inputs={...})
   
   # New direct execution
   result = await tool.run(input_data)
   ```

### Key Differences:

| Aspect | Haystack | Langchain |
|--------|----------|-----------|
| Components | `@component` decorator | Tool classes |
| Pipeline | Hamilton driver | Agent execution |
| Prompts | `PromptBuilder` | `PromptTemplate` |
| Async | Limited support | Full async support |
| Error Handling | Basic | Comprehensive |
| Extensibility | Moderate | High |

## Performance Considerations

### 1. Vector Store Optimization

```python
# Use appropriate vector store for your scale
from langchain.vectorstores import FAISS, Chroma, Pinecone

# For small datasets
vectorstore = FAISS.from_documents(docs, embeddings)

# For larger datasets
vectorstore = Pinecone.from_documents(docs, embeddings, index_name="sql-schema")
```

### 2. Caching

```python
# Implement caching for repeated queries
from functools import lru_cache

@lru_cache(maxsize=128)
def cached_sql_generation(query_hash):
    # Cache SQL generation results
    pass
```

### 3. Batch Processing

```python
# Process multiple SQL operations in parallel
import asyncio

async def batch_sql_generation(queries):
    tasks = [pipeline.generate_sql(SQLRequest(query=q)) for q in queries]
    return await asyncio.gather(*tasks)
```

## Troubleshooting

### Common Issues:

1. **Vector Store Not Initialized**
   ```python
   # Solution: Initialize before use
   pipeline.initialize_knowledge_base(schema_documents=docs)
   ```

2. **LLM Rate Limits**
   ```python
   # Solution: Add delays or use different models
   await asyncio.sleep(0.1)  # Add delay
   ```

3. **SQL Validation Errors**
   ```python
   # Solution: Enable auto-correction
   pipeline = SQLPipeline(llm=llm, engine=engine, use_rag=True)
   ```

### Debug Mode:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show detailed execution logs
```

## Contributing

The system is designed to be modular and extensible. To add new SQL operations:

1. Create a new tool class in `sql_tools.py`
2. Add the operation type to `SQLOperationType` enum
3. Implement the handler in `SQLRAGAgent`
4. Add the interface method to `SQLPipeline`

## License

This implementation follows the same license as your existing codebase.

---

For more examples and advanced usage, see the example files and test cases in the repository.