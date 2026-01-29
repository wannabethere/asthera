# Async Pipeline Architecture - Complete Guide

**Version:** 1.0.0  
**Last Updated:** January 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Core Components](#core-components)
5. [Standard Pipelines](#standard-pipelines)
6. [Usage Patterns](#usage-patterns)
7. [API Reference](#api-reference)
8. [Creating Custom Pipelines](#creating-custom-pipelines)
9. [Pipeline Assembly](#pipeline-assembly)
10. [Integration Patterns](#integration-patterns)
11. [Examples](#examples)
12. [Testing](#testing)
13. [Performance & Best Practices](#performance--best-practices)
14. [Troubleshooting](#troubleshooting)
15. [Implementation Details](#implementation-details)

---

## Overview

The async pipeline architecture provides a registry-based system for managing reusable, composable pipelines that handle user questions and return data. Pipelines are initialized at startup and available throughout the application lifecycle through a centralized registry.

### Key Benefits

- ✅ **Reusability** - Pipelines can be reused across different parts of the application
- ✅ **Composability** - Combine pipelines using PipelineAssembly
- ✅ **Centralized Management** - Registry provides single point of access
- ✅ **Type Safety** - Structured inputs/outputs with validation
- ✅ **Monitoring** - Built-in status callbacks and metrics
- ✅ **Extensibility** - Easy to create custom pipelines
- ✅ **Async by Default** - Full async support for performance
- ✅ **Category Organization** - Logical grouping of related pipelines
- ✅ **Follows Existing Patterns** - Same architecture as ContextualGraph pipelines
- ✅ **Production Ready** - Comprehensive error handling and logging

### Architecture Philosophy

The async pipeline system follows the same architectural patterns as `ContextualGraphRetrievalPipeline` and `ContextualGraphReasoningPipeline`, ensuring consistency and familiar patterns for developers already working with the codebase.

---

## Quick Start

### 30-Second Start

```python
from app.pipelines import get_pipeline_registry

# Get pipeline
registry = get_pipeline_registry()
pipeline = registry.get_pipeline("general_query")

# Execute
result = await pipeline.run(inputs={"query": "Your question here"})
print(result["data"])
```

### Using via API

```bash
# List available pipelines
curl http://localhost:8000/api/pipelines/

# Execute pipeline
curl -X POST http://localhost:8000/api/pipelines/general_query/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the compliance requirements?",
    "context": {"domain": "compliance"},
    "options": {"include_details": true}
  }'
```

### Running Examples

```bash
cd knowledge
python examples/async_pipeline_usage.py
```

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────┐
│                Application Startup                   │
│  (main.py lifespan: initialize_pipeline_registry)   │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              Pipeline Registry                       │
│  - Category-based organization                       │
│  - Pipeline lifecycle management                     │
│  - Default pipelines per category                    │
└────────┬────────────────────────────────────────────┘
         │
         ├─────► query category
         │       └─► general_query (default)
         │
         ├─────► data category
         │       └─► data_retrieval (default)
         │
         ├─────► contextual category
         │       ├─► contextual_retrieval
         │       └─► contextual_reasoning (default)
         │
         ├─────► analysis category
         └─────► integration category
```

### Component Hierarchy

1. **AsyncQueryPipeline** - Base class for general query processing
2. **AsyncDataRetrievalPipeline** - Specialized for data retrieval
3. **PipelineRegistry** - Centralized pipeline management
4. **PipelineAssembly** - Pipeline composition and orchestration

### Data Flow

```
User Request
    │
    ▼
API Endpoint / Direct Call
    │
    ▼
Pipeline Registry
    │
    ▼
Pipeline Selection (by ID or category)
    │
    ▼
Pipeline.run(inputs)
    │
    ├─► Status Callback (optional, for monitoring)
    │
    ├─► Query Processing
    │   ├─► Input Validation
    │   ├─► Query Processor (custom or default)
    │   └─► Result Formatting
    │
    ▼
Result (success/failure with data)
```

---

## Core Components

### 1. AsyncQueryPipeline

**File:** `app/pipelines/async_query_pipeline.py`

Base class for general-purpose async query processing.

**Key Features:**
- Async by default
- Configurable timeout (default: 30s)
- Custom query processor support
- Result formatting support
- Status callbacks for monitoring
- Comprehensive error handling

**Basic Usage:**

```python
from app.pipelines import AsyncQueryPipeline

pipeline = AsyncQueryPipeline(
    name="my_query_pipeline",
    query_processor=custom_processor,  # Optional
    result_formatter=custom_formatter,  # Optional
    timeout=30.0
)

await pipeline.initialize()

result = await pipeline.run(
    inputs={
        "query": "User question",
        "context": {"domain": "security"},
        "options": {"include_details": True}
    }
)
```

**Constructor Parameters:**

- `name` (str): Pipeline name
- `version` (str): Pipeline version (default: "1.0.0")
- `description` (str): Pipeline description
- `llm` (ChatOpenAI, optional): LLM instance
- `model_name` (str): Model name if llm not provided (default: "gpt-4o")
- `query_processor` (Callable, optional): Custom query processing function
- `result_formatter` (Callable, optional): Custom result formatting function
- `max_retries` (int): Maximum retries on failure (default: 3)
- `timeout` (float, optional): Query timeout in seconds (default: 30.0)

### 2. AsyncDataRetrievalPipeline

**File:** `app/pipelines/async_query_pipeline.py`

Specialized pipeline for data retrieval with schema awareness.

**Key Features:**
- Database schema retrieval
- Contextual graph integration
- Automatic schema/context correlation
- Pagination support
- Filter support

**Basic Usage:**

```python
from app.pipelines import AsyncDataRetrievalPipeline

pipeline = AsyncDataRetrievalPipeline(
    data_source=db_pool,
    schema_registry=schema_registry,
    retrieval_helper=retrieval_helper,
    contextual_graph_service=contextual_graph_service
)

await pipeline.initialize()

result = await pipeline.run(
    inputs={
        "query": "Get high-severity vulnerabilities",
        "context": {"project_id": "my_project_123"},
        "options": {
            "schema_limit": 10,
            "column_limit": 50,
            "context_limit": 5
        },
        "filters": {"severity": "high", "status": "open"}
    }
)
```

### 3. PipelineRegistry

**File:** `app/pipelines/pipeline_registry.py`

Centralized registry for managing pipelines.

**Key Features:**
- Category-based organization
- Default pipeline per category
- Pipeline activation/deactivation
- Batch initialization/cleanup
- Pipeline metadata management

**Basic Usage:**

```python
from app.pipelines import get_pipeline_registry

registry = get_pipeline_registry()

# Get pipeline by ID
pipeline = registry.get_pipeline("general_query")

# Get default pipeline for category
pipeline = registry.get_category_pipeline("data")

# List pipelines
pipelines = registry.list_pipelines(category="query")

# List categories
categories = registry.list_categories()
```

**Registry Methods:**

- `register_pipeline()` - Register a new pipeline
- `get_pipeline(pipeline_id)` - Get pipeline by ID
- `get_category_pipeline(category, pipeline_id=None)` - Get pipeline from category
- `list_pipelines(category=None, active_only=True)` - List pipelines
- `list_categories()` - List categories
- `unregister_pipeline(pipeline_id)` - Remove pipeline
- `set_pipeline_active(pipeline_id, is_active)` - Activate/deactivate
- `initialize_all()` - Initialize all pipelines
- `cleanup_all()` - Clean up all pipelines

### 4. Pipeline Startup

**File:** `app/core/pipeline_startup.py`

Handles pipeline initialization at application startup.

**Registered at Startup:**

1. **general_query** (query category) - General query processing
2. **data_retrieval** (data category) - Schema-aware data retrieval
3. **contextual_retrieval** (contextual category) - Context retrieval
4. **contextual_reasoning** (contextual category) - Context-aware reasoning

**Integration:**

```python
# In main.py lifespan
from app.core.pipeline_startup import initialize_pipeline_registry

pipeline_result = await initialize_pipeline_registry(dependencies)
app.state.pipeline_registry = pipeline_result["registry"]
```

---

## Standard Pipelines

### Overview Table

| Pipeline ID | Category | Purpose | Default |
|------------|----------|---------|---------|
| `general_query` | query | General-purpose query processing | ✓ |
| `data_retrieval` | data | Schema-aware data retrieval | ✓ |
| `contextual_retrieval` | contextual | Context retrieval from graphs | |
| `contextual_reasoning` | contextual | Context-aware reasoning | ✓ |

### general_query

**Category:** query  
**Default:** Yes

General-purpose async pipeline for processing user queries.

```python
pipeline = registry.get_pipeline("general_query")

result = await pipeline.run(
    inputs={
        "query": "What are the SOC2 requirements?",
        "context": {"framework": "SOC2"},
        "options": {"include_details": True}
    }
)
```

### data_retrieval

**Category:** data  
**Default:** Yes

Schema-aware data retrieval with contextual information.

```python
pipeline = registry.get_pipeline("data_retrieval")

result = await pipeline.run(
    inputs={
        "query": "Get open vulnerabilities",
        "context": {"project_id": "123"},
        "options": {
            "schema_limit": 10,
            "context_limit": 5
        },
        "filters": {"status": "open"}
    }
)

# Result includes:
# - schemas: Retrieved database schemas
# - contexts: Contextual information
# - data: Actual data records
```

### contextual_retrieval

**Category:** contextual

Retrieves relevant contexts and creates reasoning plans.

```python
pipeline = registry.get_pipeline("contextual_retrieval")

result = await pipeline.run(
    inputs={
        "query": "What controls are needed for encryption?",
        "top_k": 5
    }
)

# Result includes:
# - contexts: Retrieved contexts
# - reasoning_plan: Generated reasoning plan
```

### contextual_reasoning

**Category:** contextual  
**Default:** Yes

Performs context-aware reasoning using contextual graphs.

```python
pipeline = registry.get_pipeline("contextual_reasoning")

result = await pipeline.run(
    inputs={
        "query": "What controls are needed?",
        "context_id": "context_123",
        "reasoning_type": "multi_hop",
        "max_hops": 3
    }
)

# Result includes:
# - final_answer: Reasoning result
# - reasoning_path: Step-by-step reasoning
```

---

## Usage Patterns

### Pattern 1: Direct Pipeline Access

Simple, direct access to a specific pipeline.

```python
from app.pipelines import get_pipeline_registry

async def process_query(query: str):
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("general_query")
    
    result = await pipeline.run(inputs={"query": query})
    return result.get("data")
```

**When to use:**
- You know exactly which pipeline you need
- Single pipeline execution
- Simple query processing

### Pattern 2: Category-Based Selection

Use default pipeline for a category, allowing flexibility.

```python
async def retrieve_data(query: str, project_id: str):
    registry = get_pipeline_registry()
    
    # Get default data pipeline (currently: data_retrieval)
    pipeline = registry.get_category_pipeline("data")
    
    result = await pipeline.run(
        inputs={
            "query": query,
            "context": {"project_id": project_id}
        }
    )
    return result
```

**When to use:**
- You want flexibility to change default pipelines
- Category defines the type of operation
- Don't need specific pipeline implementation

### Pattern 3: Sequential Pipeline Execution

Execute multiple pipelines in sequence, passing results forward.

```python
async def contextual_query(query: str):
    registry = get_pipeline_registry()
    
    # Step 1: Retrieve contexts
    retrieval = registry.get_pipeline("contextual_retrieval")
    contexts_result = await retrieval.run(
        inputs={"query": query, "top_k": 5}
    )
    
    contexts = contexts_result.get("data", {}).get("contexts", [])
    
    if not contexts:
        return {"error": "No contexts found"}
    
    # Step 2: Reason with contexts
    reasoning = registry.get_pipeline("contextual_reasoning")
    result = await reasoning.run(
        inputs={
            "query": query,
            "context_id": contexts[0]["context_id"],
            "reasoning_type": "multi_hop"
        }
    )
    
    return result
```

**When to use:**
- Multi-step workflows
- Results from one pipeline feed into another
- Sequential dependencies

### Pattern 4: Pipeline Assembly

Compose pipelines using PipelineAssembly for complex workflows.

```python
from app.pipelines import (
    PipelineAssembly,
    PipelineStep,
    PipelineAssemblyConfig,
    PipelineExecutionMode,
    get_pipeline_registry
)

async def create_qa_workflow():
    registry = get_pipeline_registry()
    
    # Create assembly configuration
    config = PipelineAssemblyConfig(
        assembly_id="qa_workflow",
        assembly_name="Q&A Workflow",
        description="Retrieves contexts and performs reasoning",
        execution_mode=PipelineExecutionMode.SEQUENTIAL
    )
    
    assembly = PipelineAssembly(config=config)
    
    # Step 1: Retrieve contexts
    assembly.add_step(
        PipelineStep(
            pipeline=registry.get_pipeline("contextual_retrieval"),
            step_id="retrieve",
            step_name="Retrieve Contexts",
            input_mapper=lambda state: {
                "query": state.get("query"),
                "top_k": 5
            }
        )
    )
    
    # Step 2: Reason with contexts
    assembly.add_step(
        PipelineStep(
            pipeline=registry.get_pipeline("contextual_reasoning"),
            step_id="reason",
            step_name="Reason with Contexts",
            input_mapper=lambda state: {
                "query": state.get("query"),
                "context_id": state.get("contexts", [{}])[0].get("context_id"),
                "reasoning_type": "multi_hop"
            },
            condition=lambda state: bool(state.get("contexts"))
        )
    )
    
    # Initialize and execute
    await assembly.initialize()
    
    result = await assembly.run(
        inputs={"query": "What are the requirements?"}
    )
    
    return result
```

**When to use:**
- Complex multi-step workflows
- Conditional execution
- Need input/output mapping between steps
- Want reusable workflow definitions

### Pattern 5: Parallel Pipeline Execution

Execute multiple pipelines in parallel.

```python
from app.pipelines import PipelineExecutionMode

async def parallel_retrieval(query: str):
    registry = get_pipeline_registry()
    
    config = PipelineAssemblyConfig(
        assembly_id="parallel_workflow",
        assembly_name="Parallel Workflow",
        execution_mode=PipelineExecutionMode.PARALLEL,
        max_concurrent=3
    )
    
    assembly = PipelineAssembly(config=config)
    
    # Add multiple independent steps
    assembly.add_step(PipelineStep(
        pipeline=registry.get_pipeline("contextual_retrieval"),
        step_id="retrieve1",
        step_name="Retrieve from SOC2"
    ))
    
    assembly.add_step(PipelineStep(
        pipeline=registry.get_pipeline("data_retrieval"),
        step_id="retrieve2",
        step_name="Retrieve Data"
    ))
    
    await assembly.initialize()
    result = await assembly.run(inputs={"query": query})
    
    return result
```

**When to use:**
- Independent operations that can run concurrently
- Performance optimization
- Aggregating results from multiple sources

### Pattern 6: Custom Pipeline

Create and register custom pipelines.

```python
from app.pipelines import AsyncQueryPipeline, get_pipeline_registry

async def custom_processor(query: str, params: dict) -> dict:
    """Custom query processing logic"""
    context = params.get("context", {})
    
    # Your custom processing
    processed_result = {
        "processed_query": query.upper(),
        "context": context,
        "custom_data": "custom_value"
    }
    
    return processed_result

# Create custom pipeline
pipeline = AsyncQueryPipeline(
    name="custom_pipeline",
    description="My custom query processor",
    query_processor=custom_processor,
    timeout=60.0
)

await pipeline.initialize()

# Register in registry
registry = get_pipeline_registry()
registry.register_pipeline(
    pipeline_id="my_custom",
    pipeline=pipeline,
    name="My Custom Pipeline",
    category="query"
)

# Use custom pipeline
result = await pipeline.run(
    inputs={
        "query": "test query",
        "context": {"test": True}
    }
)
```

**When to use:**
- Need specialized query processing
- Custom business logic
- Integration with external systems
- Domain-specific requirements

---

## API Reference

### REST API Endpoints

Base URL: `http://localhost:8000/api/pipelines`

#### GET /api/pipelines/

List all available pipelines.

**Query Parameters:**
- `category` (optional): Filter by category
- `active_only` (boolean, default: true): Only return active pipelines

**Response:**
```json
{
  "success": true,
  "pipelines": [
    {
      "pipeline_id": "general_query",
      "name": "General Query Pipeline",
      "description": "General-purpose async pipeline",
      "category": "query",
      "version": "1.0.0",
      "is_active": true,
      "metadata": {}
    }
  ],
  "count": 4
}
```

**Example:**
```bash
curl http://localhost:8000/api/pipelines/
curl http://localhost:8000/api/pipelines/?category=data
```

#### GET /api/pipelines/categories

List all pipeline categories.

**Response:**
```json
{
  "success": true,
  "categories": [
    {
      "category_id": "query",
      "name": "Query Pipelines",
      "description": "Pipelines for processing user queries",
      "pipeline_count": 2,
      "default_pipeline_id": "general_query",
      "metadata": {}
    }
  ],
  "count": 5
}
```

#### GET /api/pipelines/{pipeline_id}

Get information about a specific pipeline.

**Path Parameters:**
- `pipeline_id`: Pipeline identifier

**Response:**
```json
{
  "success": true,
  "pipeline": {
    "pipeline_id": "general_query",
    "name": "General Query Pipeline",
    "description": "...",
    "category": "query",
    "version": "1.0.0",
    "is_active": true,
    "metadata": {},
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
}
```

#### POST /api/pipelines/{pipeline_id}/execute

Execute a specific pipeline.

**Path Parameters:**
- `pipeline_id`: Pipeline identifier

**Request Body:**
```json
{
  "query": "What are the compliance requirements?",
  "context": {
    "domain": "compliance",
    "framework": "SOC2"
  },
  "options": {
    "include_details": true,
    "max_results": 10
  },
  "filters": {},
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "...",
    "result": "..."
  },
  "metadata": {
    "query": "...",
    "processing_time": 1.23,
    "pipeline": "general_query"
  },
  "pipeline_id": "general_query",
  "processing_time": 1.23
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/pipelines/general_query/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the requirements?",
    "context": {"domain": "compliance"}
  }'
```

#### POST /api/pipelines/category/{category}/execute

Execute default pipeline for a category.

**Path Parameters:**
- `category`: Category identifier

**Query Parameters:**
- `pipeline_id` (optional): Specific pipeline ID to use instead of default

**Request/Response:** Same format as pipeline execute

**Example:**
```bash
curl -X POST http://localhost:8000/api/pipelines/category/data/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Get issues",
    "context": {"project_id": "123"},
    "filters": {"severity": "high"}
  }'
```

#### GET /api/pipelines/health/status

Get health status of pipeline registry.

**Response:**
```json
{
  "success": true,
  "status": "operational",
  "statistics": {
    "total_pipelines": 4,
    "active_pipelines": 4,
    "inactive_pipelines": 0,
    "categories": 5
  },
  "initialization": {
    "initialized": 4,
    "failed": 0,
    "skipped": 0
  },
  "categories": [
    {
      "category": "query",
      "name": "Query Pipelines",
      "pipeline_count": 2,
      "default_pipeline": "general_query"
    }
  ]
}
```

### Input Structure

All pipeline inputs follow this structure:

```python
inputs = {
    "query": str,              # Required: User query
    "context": dict,           # Optional: Query context
    "options": dict,           # Optional: Processing options
    "filters": dict,           # Optional: Data filters
    "metadata": dict           # Optional: Additional metadata
}
```

### Result Structure

All pipeline results follow this structure:

```python
result = {
    "success": bool,           # True if successful
    "data": dict,              # Query results
    "error": str,              # Error message (if failed)
    "metadata": dict           # Result metadata
}
```

### Status Callbacks

Pipelines support status callbacks for monitoring:

```python
def status_callback(status: str, data: dict):
    print(f"Status: {status}")
    print(f"Data: {data}")

result = await pipeline.run(
    inputs={"query": "..."},
    status_callback=status_callback
)
```

**Status Events:**
- `query_started` - Pipeline execution started
- `processing` - Processing stage update
- `completed` - Pipeline execution completed
- `error` - Error occurred

---

## Creating Custom Pipelines

### Method 1: Custom Query Processor

Simplest way to create custom logic:

```python
from app.pipelines import AsyncQueryPipeline, get_pipeline_registry

async def my_processor(query: str, params: dict) -> dict:
    """
    Custom processor function
    
    Args:
        query: User query string
        params: Dictionary with context, options, filters, metadata
        
    Returns:
        Dictionary with processed results
    """
    context = params.get("context", {})
    options = params.get("options", {})
    
    # Your custom logic here
    result = {
        "processed_query": query,
        "context": context,
        "custom_field": "value"
    }
    
    return result

# Create pipeline with custom processor
pipeline = AsyncQueryPipeline(
    name="my_custom_pipeline",
    description="Pipeline with custom processor",
    query_processor=my_processor
)

await pipeline.initialize()

# Register
registry = get_pipeline_registry()
registry.register_pipeline(
    pipeline_id="my_custom",
    pipeline=pipeline,
    category="query"
)
```

### Method 2: Subclass AsyncQueryPipeline

For more control, subclass the base pipeline:

```python
from app.pipelines import AsyncQueryPipeline
from typing import Dict, Any

class CustomQueryPipeline(AsyncQueryPipeline):
    def __init__(self, **kwargs):
        super().__init__(
            name="custom_query_pipeline",
            description="Custom pipeline implementation",
            **kwargs
        )
        # Custom initialization
        self.custom_config = {}
    
    async def _default_query_processing(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any],
        filters: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Override default processing"""
        
        # Your custom logic
        result = {
            "query": query,
            "result": "custom processing",
            "context": context
        }
        
        return result

# Create and register
pipeline = CustomQueryPipeline()
await pipeline.initialize()

registry.register_pipeline(
    pipeline_id="custom_query",
    pipeline=pipeline,
    category="query"
)
```

### Method 3: Subclass AsyncDataRetrievalPipeline

For data-specific custom logic:

```python
from app.pipelines import AsyncDataRetrievalPipeline
from typing import Dict, Any, List

class CustomDataPipeline(AsyncDataRetrievalPipeline):
    
    async def _execute_data_retrieval(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any],
        filters: Dict[str, Any],
        schemas: List[Dict[str, Any]],
        contexts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Custom data retrieval implementation
        
        This method has access to:
        - schemas: Retrieved database schemas
        - contexts: Contextual information
        - filters: User-specified filters
        """
        results = []
        
        # Your custom data retrieval logic
        for schema in schemas:
            table_name = schema.get("table_name")
            # Query database, API, etc.
            
        return results

# Create and register
pipeline = CustomDataPipeline(
    data_source=db_pool,
    retrieval_helper=retrieval_helper
)

await pipeline.initialize()

registry.register_pipeline(
    pipeline_id="custom_data",
    pipeline=pipeline,
    category="data"
)
```

### Result Formatters

Add custom result formatting:

```python
def custom_formatter(result: dict) -> dict:
    """Format pipeline results"""
    return {
        "formatted_result": result,
        "timestamp": datetime.now().isoformat(),
        "custom_formatting": True
    }

pipeline = AsyncQueryPipeline(
    name="formatted_pipeline",
    query_processor=my_processor,
    result_formatter=custom_formatter
)
```

---

## Pipeline Assembly

Pipeline assembly allows combining multiple pipelines into complex workflows.

### Assembly Modes

#### Sequential Mode

Execute pipelines one after another, passing results forward:

```python
from app.pipelines import (
    PipelineAssembly,
    PipelineStep,
    PipelineAssemblyConfig,
    PipelineExecutionMode
)

config = PipelineAssemblyConfig(
    assembly_id="sequential_workflow",
    assembly_name="Sequential Workflow",
    execution_mode=PipelineExecutionMode.SEQUENTIAL
)

assembly = PipelineAssembly(config=config)

assembly.add_step(PipelineStep(
    pipeline=pipeline1,
    step_id="step1",
    step_name="First Step"
))

assembly.add_step(PipelineStep(
    pipeline=pipeline2,
    step_id="step2",
    step_name="Second Step"
))

await assembly.initialize()
result = await assembly.run(inputs={"query": "..."})
```

#### Parallel Mode

Execute pipelines simultaneously:

```python
config = PipelineAssemblyConfig(
    assembly_id="parallel_workflow",
    assembly_name="Parallel Workflow",
    execution_mode=PipelineExecutionMode.PARALLEL,
    max_concurrent=5  # Maximum concurrent executions
)

assembly = PipelineAssembly(config=config)

# Add independent steps that can run in parallel
assembly.add_step(PipelineStep(...))
assembly.add_step(PipelineStep(...))
assembly.add_step(PipelineStep(...))

result = await assembly.run(inputs={"query": "..."})
```

#### Conditional Mode

Execute pipelines based on conditions:

```python
config = PipelineAssemblyConfig(
    assembly_id="conditional_workflow",
    assembly_name="Conditional Workflow",
    execution_mode=PipelineExecutionMode.CONDITIONAL
)

assembly = PipelineAssembly(config=config)

assembly.add_step(
    PipelineStep(
        pipeline=pipeline1,
        step_id="step1",
        step_name="Always Execute"
    )
)

assembly.add_step(
    PipelineStep(
        pipeline=pipeline2,
        step_id="step2",
        step_name="Conditional Step",
        condition=lambda state: state.get("contexts") is not None
    )
)

result = await assembly.run(inputs={"query": "..."})
```

### Input/Output Mapping

Map data between pipeline steps:

```python
assembly.add_step(
    PipelineStep(
        pipeline=retrieval_pipeline,
        step_id="retrieve",
        step_name="Retrieve Contexts",
        # Map assembly state to pipeline inputs
        input_mapper=lambda state: {
            "query": state.get("query"),
            "top_k": 5
        },
        # Map pipeline outputs back to state
        output_mapper=lambda result: {
            "contexts": result.get("data", {}).get("contexts", []),
            "reasoning_plan": result.get("data", {}).get("reasoning_plan")
        }
    )
)
```

### Error Handling

Configure error handling strategy:

```python
config = PipelineAssemblyConfig(
    assembly_id="workflow",
    assembly_name="Workflow",
    error_handling="stop"  # "stop", "continue", or "skip"
)
```

- **stop**: Stop execution on first error (default)
- **continue**: Continue execution, mark step as failed
- **skip**: Skip failed steps, continue with next

### Retries and Timeouts

Configure retries and timeouts per step:

```python
assembly.add_step(
    PipelineStep(
        pipeline=pipeline,
        step_id="step1",
        step_name="Step with Retry",
        retry_count=3,      # Retry 3 times on failure
        timeout=60.0,       # 60 second timeout
        required=False      # Not required, can fail
    )
)
```

### Result Aggregation

Aggregate results from multiple steps:

```python
def aggregate_results(step_results: list) -> dict:
    """Aggregate results from all steps"""
    all_data = []
    for result in step_results:
        if result.get("success"):
            all_data.append(result.get("result"))
    
    return {
        "aggregated_data": all_data,
        "total_steps": len(step_results),
        "successful_steps": sum(1 for r in step_results if r.get("success"))
    }

config = PipelineAssemblyConfig(
    assembly_id="workflow",
    assembly_name="Workflow",
    result_aggregator=aggregate_results
)
```

---

## Integration Patterns

### With Assistants

Use pipelines in assistant nodes:

```python
from app.pipelines import get_pipeline_registry

class DataRetrievalNode:
    """Assistant node that uses pipeline"""
    
    async def __call__(self, state: dict) -> dict:
        registry = get_pipeline_registry()
        pipeline = registry.get_pipeline("data_retrieval")
        
        result = await pipeline.run(
            inputs={
                "query": state.get("query"),
                "context": state.get("context"),
                "options": state.get("options", {})
            }
        )
        
        # Update state with results
        state["data_result"] = result.get("data")
        state["schemas"] = result.get("data", {}).get("schemas", [])
        state["contexts"] = result.get("data", {}).get("contexts", [])
        
        return state
```

### With Streaming Service

Stream pipeline execution updates:

```python
async def stream_pipeline_execution(query: str):
    """Stream pipeline execution with updates"""
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("contextual_reasoning")
    
    # Status callback that yields updates
    def callback(status: str, data: dict):
        return {"event": status, "data": data}
    
    # Execute with streaming callback
    result = await pipeline.run(
        inputs={"query": query},
        status_callback=callback
    )
    
    yield {"event": "complete", "data": result}
```

### With FastAPI Dependencies

Use as FastAPI dependency:

```python
from fastapi import Depends
from app.pipelines import get_pipeline_registry, PipelineRegistry

def get_query_pipeline(registry: PipelineRegistry = Depends(get_pipeline_registry)):
    """FastAPI dependency for query pipeline"""
    return registry.get_pipeline("general_query")

@app.post("/query")
async def query_endpoint(
    request: QueryRequest,
    pipeline = Depends(get_query_pipeline)
):
    result = await pipeline.run(inputs={
        "query": request.query,
        "context": request.context
    })
    return result
```

### With Existing ContextualGraph Pipelines

Compose with existing pipelines:

```python
from app.pipelines import (
    create_contextual_reasoning_assembly,
    get_pipeline_registry
)

registry = get_pipeline_registry()

# Create assembly using both new and existing pipelines
assembly = create_contextual_reasoning_assembly(
    retrieval_pipeline=registry.get_pipeline("contextual_retrieval"),
    reasoning_pipeline=registry.get_pipeline("contextual_reasoning")
)

result = await assembly.run(inputs={"query": "..."})
```

---

## Examples

### Example 1: Simple Query Processing

```python
from app.pipelines import get_pipeline_registry

async def simple_query():
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("general_query")
    
    result = await pipeline.run(
        inputs={
            "query": "What are the SOC2 requirements?",
            "context": {"framework": "SOC2"}
        }
    )
    
    if result["success"]:
        print(result["data"])
    else:
        print(f"Error: {result['error']}")
```

### Example 2: Data Retrieval with Filters

```python
async def retrieve_filtered_data():
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("data_retrieval")
    
    result = await pipeline.run(
        inputs={
            "query": "Get high-severity vulnerabilities",
            "context": {
                "project_id": "my_project_123"
            },
            "options": {
                "schema_limit": 10,
                "column_limit": 50,
                "context_limit": 5,
                "include_metadata": True
            },
            "filters": {
                "severity": "high",
                "status": "open"
            }
        }
    )
    
    if result["success"]:
        data = result["data"]
        schemas = data.get("schemas", [])
        contexts = data.get("contexts", [])
        records = data.get("data", [])
        
        print(f"Found {len(schemas)} relevant schemas")
        print(f"Found {len(contexts)} contexts")
        print(f"Retrieved {len(records)} records")
```

### Example 3: Contextual Reasoning Workflow

```python
async def contextual_reasoning_workflow():
    registry = get_pipeline_registry()
    
    query = "What controls are needed for data encryption?"
    
    # Step 1: Retrieve contexts
    retrieval = registry.get_pipeline("contextual_retrieval")
    retrieval_result = await retrieval.run(
        inputs={
            "query": query,
            "context": {"framework": "SOC2"},
            "top_k": 5
        }
    )
    
    if not retrieval_result["success"]:
        print(f"Retrieval failed: {retrieval_result['error']}")
        return
    
    contexts = retrieval_result["data"]["contexts"]
    reasoning_plan = retrieval_result["data"]["reasoning_plan"]
    
    print(f"Retrieved {len(contexts)} contexts")
    
    # Step 2: Perform reasoning
    reasoning = registry.get_pipeline("contextual_reasoning")
    reasoning_result = await reasoning.run(
        inputs={
            "query": query,
            "context_id": contexts[0]["context_id"],
            "reasoning_plan": reasoning_plan,
            "max_hops": 3,
            "reasoning_type": "multi_hop"
        }
    )
    
    if reasoning_result["success"]:
        data = reasoning_result["data"]
        print(f"Answer: {data['final_answer']}")
        print(f"Reasoning steps: {len(data['reasoning_path'])}")
```

### Example 4: Custom Pipeline with Processor

```python
from app.pipelines import AsyncQueryPipeline, get_pipeline_registry
import aiohttp

async def api_query_processor(query: str, params: dict) -> dict:
    """Custom processor that calls external API"""
    context = params.get("context", {})
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.example.com/query",
            json={"query": query, "context": context}
        ) as response:
            api_result = await response.json()
    
    return {
        "query": query,
        "api_result": api_result,
        "context": context
    }

# Create and register
pipeline = AsyncQueryPipeline(
    name="api_query_pipeline",
    description="Pipeline that queries external API",
    query_processor=api_query_processor,
    timeout=60.0
)

await pipeline.initialize()

registry = get_pipeline_registry()
registry.register_pipeline(
    pipeline_id="api_query",
    pipeline=pipeline,
    category="integration"
)

# Use it
result = await pipeline.run(
    inputs={
        "query": "external query",
        "context": {"api_key": "..."}
    }
)
```

### Example 5: Pipeline Assembly

```python
from app.pipelines import (
    PipelineAssembly,
    PipelineStep,
    PipelineAssemblyConfig,
    PipelineExecutionMode
)

async def create_comprehensive_workflow():
    registry = get_pipeline_registry()
    
    # Create assembly
    config = PipelineAssemblyConfig(
        assembly_id="comprehensive_qa",
        assembly_name="Comprehensive Q&A Workflow",
        description="Full workflow: retrieval -> reasoning -> formatting",
        execution_mode=PipelineExecutionMode.SEQUENTIAL
    )
    
    assembly = PipelineAssembly(config=config)
    
    # Step 1: Retrieve contexts
    assembly.add_step(
        PipelineStep(
            pipeline=registry.get_pipeline("contextual_retrieval"),
            step_id="retrieve",
            step_name="Retrieve Contexts",
            description="Get relevant contexts for query",
            input_mapper=lambda state: {
                "query": state.get("query"),
                "top_k": state.get("top_k", 5)
            },
            output_mapper=lambda result: {
                "contexts": result.get("data", {}).get("contexts", []),
                "reasoning_plan": result.get("data", {}).get("reasoning_plan")
            }
        )
    )
    
    # Step 2: Perform reasoning (conditional)
    assembly.add_step(
        PipelineStep(
            pipeline=registry.get_pipeline("contextual_reasoning"),
            step_id="reason",
            step_name="Contextual Reasoning",
            description="Reason using retrieved contexts",
            input_mapper=lambda state: {
                "query": state.get("query"),
                "context_id": state.get("contexts", [{}])[0].get("context_id"),
                "reasoning_plan": state.get("reasoning_plan"),
                "reasoning_type": "multi_hop",
                "max_hops": 3
            },
            output_mapper=lambda result: {
                "reasoning_result": result.get("data", {}),
                "final_answer": result.get("data", {}).get("final_answer"),
                "reasoning_path": result.get("data", {}).get("reasoning_path", [])
            },
            condition=lambda state: bool(state.get("contexts")),
            retry_count=2,
            timeout=60.0
        )
    )
    
    # Initialize
    await assembly.initialize()
    
    # Execute
    result = await assembly.run(
        inputs={
            "query": "What are the encryption requirements?",
            "top_k": 5
        }
    )
    
    return result
```

### Example 6: Monitoring with Status Callbacks

```python
import asyncio

async def monitored_execution():
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("data_retrieval")
    
    # Track progress
    progress = {
        "started": False,
        "processing_stages": [],
        "completed": False,
        "error": None
    }
    
    def status_callback(status: str, data: dict):
        if status == "query_started":
            progress["started"] = True
            print("Query started")
        elif status == "processing":
            stage = data.get("stage")
            progress["processing_stages"].append(stage)
            print(f"Processing: {stage}")
        elif status == "completed":
            progress["completed"] = True
            processing_time = data.get("processing_time")
            print(f"Completed in {processing_time:.2f}s")
        elif status == "error":
            progress["error"] = data.get("error")
            print(f"Error: {data.get('error')}")
    
    # Execute with monitoring
    result = await pipeline.run(
        inputs={
            "query": "Get data",
            "context": {"project_id": "123"}
        },
        status_callback=status_callback
    )
    
    print(f"\nProgress summary:")
    print(f"  Started: {progress['started']}")
    print(f"  Stages: {len(progress['processing_stages'])}")
    print(f"  Completed: {progress['completed']}")
    
    return result
```

---

## Testing

### Unit Testing Pipelines

```python
import pytest
from app.pipelines import AsyncQueryPipeline

@pytest.mark.asyncio
async def test_query_pipeline():
    """Test basic pipeline execution"""
    pipeline = AsyncQueryPipeline(name="test_pipeline")
    await pipeline.initialize()
    
    result = await pipeline.run(inputs={"query": "test query"})
    
    assert result["success"]
    assert "data" in result
    assert result["data"]["query"] == "test query"
    
    await pipeline.cleanup()

@pytest.mark.asyncio
async def test_custom_processor():
    """Test pipeline with custom processor"""
    async def test_processor(query: str, params: dict) -> dict:
        return {"processed": query.upper()}
    
    pipeline = AsyncQueryPipeline(
        name="test",
        query_processor=test_processor
    )
    await pipeline.initialize()
    
    result = await pipeline.run(inputs={"query": "test"})
    
    assert result["success"]
    assert result["data"]["processed"] == "TEST"
    
    await pipeline.cleanup()

@pytest.mark.asyncio
async def test_pipeline_timeout():
    """Test pipeline timeout handling"""
    import asyncio
    
    async def slow_processor(query: str, params: dict) -> dict:
        await asyncio.sleep(5)  # Slow processing
        return {"result": "done"}
    
    pipeline = AsyncQueryPipeline(
        name="test",
        query_processor=slow_processor,
        timeout=1.0  # 1 second timeout
    )
    await pipeline.initialize()
    
    result = await pipeline.run(inputs={"query": "test"})
    
    assert not result["success"]
    assert "timeout" in result["error"].lower()
    
    await pipeline.cleanup()
```

### Integration Testing

```python
import pytest
from app.pipelines import get_pipeline_registry
from app.core.dependencies import get_dependencies
from app.core.pipeline_startup import initialize_pipeline_registry

@pytest.mark.asyncio
async def test_registry_initialization():
    """Test pipeline registry initialization"""
    dependencies = await get_dependencies()
    
    result = await initialize_pipeline_registry(dependencies)
    
    assert result["registry"] is not None
    assert result["registration_results"]["total_pipelines"] > 0
    assert result["initialization_results"]["initialized"] > 0

@pytest.mark.asyncio
async def test_standard_pipelines():
    """Test all standard pipelines are registered"""
    registry = get_pipeline_registry()
    
    # Check standard pipelines
    assert registry.get_pipeline("general_query") is not None
    assert registry.get_pipeline("data_retrieval") is not None
    assert registry.get_pipeline("contextual_retrieval") is not None
    assert registry.get_pipeline("contextual_reasoning") is not None
    
    # Check categories
    categories = registry.list_categories()
    category_ids = [c["category_id"] for c in categories]
    
    assert "query" in category_ids
    assert "data" in category_ids
    assert "contextual" in category_ids

@pytest.mark.asyncio
async def test_pipeline_execution():
    """Test actual pipeline execution"""
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("general_query")
    
    result = await pipeline.run(
        inputs={
            "query": "test query",
            "context": {"test": True}
        }
    )
    
    assert result["success"]
    assert "data" in result
    assert "metadata" in result
```

### API Testing

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_pipelines():
    """Test listing pipelines endpoint"""
    response = client.get("/api/pipelines/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"]
    assert "pipelines" in data
    assert data["count"] > 0

def test_execute_pipeline():
    """Test pipeline execution endpoint"""
    response = client.post(
        "/api/pipelines/general_query/execute",
        json={
            "query": "test query",
            "context": {"test": True},
            "options": {}
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"]
    assert "data" in data
    assert data["pipeline_id"] == "general_query"

def test_health_status():
    """Test health status endpoint"""
    response = client.get("/api/pipelines/health/status")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"]
    assert data["status"] == "operational"
    assert "statistics" in data
```

---

## Performance & Best Practices

### Performance Considerations

#### Timeouts

Set appropriate timeouts based on query complexity:

```python
# Quick queries
pipeline = AsyncQueryPipeline(timeout=10.0)

# Complex queries
pipeline = AsyncQueryPipeline(timeout=60.0)

# Long-running analysis
pipeline = AsyncQueryPipeline(timeout=300.0)
```

#### Concurrency

Use parallel mode for independent operations:

```python
config = PipelineAssemblyConfig(
    execution_mode=PipelineExecutionMode.PARALLEL,
    max_concurrent=5  # Adjust based on resources
)
```

#### Caching

Implement caching in custom processors:

```python
from functools import lru_cache

class CachedPipeline(AsyncQueryPipeline):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache = {}
    
    async def _default_query_processing(self, query, context, options, filters, metadata):
        cache_key = f"{query}:{hash(str(context))}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        result = await self._process_query(query, context, options, filters, metadata)
        self.cache[cache_key] = result
        
        return result
```

#### Resource Limits

Configure schema/context limits:

```python
result = await pipeline.run(
    inputs={
        "query": "...",
        "options": {
            "schema_limit": 10,      # Limit schemas retrieved
            "column_limit": 50,      # Limit columns per schema
            "context_limit": 5,      # Limit contexts retrieved
            "max_results": 100       # Limit data records
        }
    }
)
```

#### Connection Pooling

Pipelines automatically use existing connection pools from dependencies:
- Database pool (`db_pool`)
- Vector store client
- Embeddings model

### Best Practices

#### 1. Use Registry for Access

Always access pipelines through the registry:

```python
# Good
registry = get_pipeline_registry()
pipeline = registry.get_pipeline("general_query")

# Avoid: Creating pipelines directly
pipeline = AsyncQueryPipeline(...)  # Only for custom pipelines
```

#### 2. Check Success Status

Always check the success field:

```python
result = await pipeline.run(inputs={"query": "..."})

if result["success"]:
    data = result["data"]
    # Process data
else:
    error = result["error"]
    # Handle error
```

#### 3. Use Category Pipelines for Flexibility

Use category-based access for flexibility:

```python
# Good: Flexible, uses default pipeline for category
pipeline = registry.get_category_pipeline("data")

# Less flexible: Tied to specific implementation
pipeline = registry.get_pipeline("data_retrieval")
```

#### 4. Leverage Status Callbacks

Use status callbacks for monitoring:

```python
def callback(status: str, data: dict):
    logger.info(f"Pipeline status: {status}")
    # Track metrics, log progress, etc.

result = await pipeline.run(
    inputs={"query": "..."},
    status_callback=callback
)
```

#### 5. Use Pipeline Assembly for Complex Workflows

For multi-step workflows, use assembly:

```python
# Good: Clear workflow definition
assembly = PipelineAssembly(config=...)
assembly.add_step(...)
assembly.add_step(...)

# Avoid: Manual orchestration
result1 = await pipeline1.run(...)
result2 = await pipeline2.run(...)
# ... manual state management
```

#### 6. Register Custom Pipelines at Startup

Register custom pipelines during initialization:

```python
# In pipeline_startup.py
async def _initialize_custom_pipelines(registry, ...):
    pipeline = CustomPipeline(...)
    await pipeline.initialize()
    registry.register_pipeline(...)
```

#### 7. Handle Timeouts Gracefully

Set timeouts and handle timeout errors:

```python
pipeline = AsyncQueryPipeline(timeout=30.0)

result = await pipeline.run(inputs={"query": "..."})

if not result["success"]:
    if "timeout" in result.get("error", "").lower():
        # Handle timeout specifically
        logger.warning("Query timed out, retrying with simpler query...")
```

#### 8. Use Filters to Narrow Results

Always use filters when possible:

```python
result = await pipeline.run(
    inputs={
        "query": "Get issues",
        "filters": {
            "severity": "high",
            "status": "open",
            "assigned_to": "team_1"
        }
    }
)
```

#### 9. Log Pipeline Usage

Log pipeline usage for monitoring:

```python
logger.info(f"Executing pipeline: {pipeline_id}")
logger.info(f"Query: {query[:100]}")

result = await pipeline.run(...)

logger.info(f"Pipeline completed: success={result['success']}, "
           f"time={result.get('metadata', {}).get('processing_time', 0):.2f}s")
```

#### 10. Clean Up Resources

Ensure proper cleanup:

```python
# At application shutdown
from app.core.pipeline_startup import cleanup_pipeline_registry

await cleanup_pipeline_registry()
```

---

## Troubleshooting

### Common Issues

#### Pipeline Not Found

**Symptoms:**
```python
pipeline = registry.get_pipeline("my_pipeline")
# Returns None
```

**Solutions:**
1. Check if pipeline is registered:
   ```python
   pipelines = registry.list_pipelines()
   print([p["pipeline_id"] for p in pipelines])
   ```

2. Verify pipeline is active:
   ```python
   config = registry.get_pipeline_config("my_pipeline")
   if config:
       print(f"Active: {config.is_active}")
   ```

3. Check initialization logs for errors

#### Timeout Errors

**Symptoms:**
```
Error: Query processing timed out after 30.0s
```

**Solutions:**
1. Increase timeout:
   ```python
   pipeline = AsyncQueryPipeline(timeout=60.0)
   ```

2. Simplify query or use filters:
   ```python
   result = await pipeline.run(
       inputs={
           "query": "...",
           "filters": {"limit": 10}
       }
   )
   ```

3. Check for slow queries in logs

#### No Data Returned

**Symptoms:**
```python
result["success"] == True
result["data"] == {} or []
```

**Solutions:**
1. Verify input structure:
   ```python
   # Correct structure
   inputs = {
       "query": "...",
       "context": {},
       "options": {},
       "filters": {}
   }
   ```

2. Check filters aren't too restrictive:
   ```python
   # Too restrictive
   filters = {"status": "closed", "severity": "critical", "date": "2020-01-01"}
   
   # More reasonable
   filters = {"status": "open"}
   ```

3. Review query for typos or incorrect syntax

#### Integration Issues

**Symptoms:**
- Pipeline registry not initialized
- Dependencies missing
- Vector store or database errors

**Solutions:**
1. Check startup logs:
   ```bash
   python -m uvicorn app.main:app --reload | grep -i "pipeline\|error"
   ```

2. Verify dependencies are initialized:
   ```python
   # In startup code
   if not hasattr(app.state, "pipeline_registry"):
       logger.error("Pipeline registry not initialized!")
   ```

3. Check vector_store_client and db_pool availability:
   ```python
   dependencies = await get_dependencies()
   print(f"DB Pool: {dependencies.get('db_pool')}")
   print(f"Vector Store: {dependencies.get('vector_store_client')}")
   ```

#### Memory Issues

**Symptoms:**
- High memory usage
- Out of memory errors

**Solutions:**
1. Limit result sizes:
   ```python
   options = {
       "schema_limit": 5,
       "context_limit": 3,
       "max_results": 50
   }
   ```

2. Use pagination for large datasets

3. Clean up pipelines after use:
   ```python
   await pipeline.cleanup()
   ```

### Debugging

#### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.pipelines")
logger.setLevel(logging.DEBUG)
```

#### Inspect Pipeline State

```python
# Get pipeline config
config = registry.get_pipeline_config("pipeline_id")
print(f"Name: {config.name}")
print(f"Category: {config.category}")
print(f"Active: {config.is_active}")
print(f"Metadata: {config.metadata}")

# List all pipelines
for p in registry.list_pipelines(active_only=False):
    print(f"{p['pipeline_id']}: {p['is_active']}")
```

#### Test Pipeline Directly

```python
# Direct test
pipeline = registry.get_pipeline("general_query")

# Simple test
result = await pipeline.run(inputs={"query": "test"})
print(f"Success: {result['success']}")
print(f"Data: {result.get('data')}")
print(f"Error: {result.get('error')}")
```

#### Check API Health

```bash
curl http://localhost:8000/api/pipelines/health/status | jq
```

---

## Implementation Details

### Files Structure

```
knowledge/
├── app/
│   ├── pipelines/
│   │   ├── __init__.py                    # Exports
│   │   ├── async_query_pipeline.py        # Core pipeline classes
│   │   └── pipeline_registry.py           # Registry implementation
│   ├── core/
│   │   └── pipeline_startup.py            # Startup initialization
│   ├── routers/
│   │   └── pipelines.py                   # API endpoints
│   └── main.py                            # Updated with pipeline init
├── examples/
│   └── async_pipeline_usage.py           # Usage examples
└── docs/
    └── ASYNC_PIPELINES.md                # This comprehensive guide
```

### Standard Pipelines Registration

During startup (`pipeline_startup.py`):

1. **Pipeline Categories** are registered:
   - query, data, contextual, analysis, integration

2. **Standard Pipelines** are created and registered:
   - general_query → AsyncQueryPipeline
   - data_retrieval → AsyncDataRetrievalPipeline
   - contextual_retrieval → ContextualGraphRetrievalPipeline
   - contextual_reasoning → ContextualGraphReasoningPipeline

3. **All pipelines** are initialized via `registry.initialize_all()`

4. **Registry** is stored in `app.state.pipeline_registry`

### Lifecycle Management

```
Application Start
    │
    ├─► initialize_pipeline_registry()
    │   ├─► Register categories
    │   ├─► Register standard pipelines
    │   └─► Initialize all pipelines
    │
    ├─► Store registry in app.state
    │
    ▼
Application Running
    │
    ├─► Pipelines accessible via registry
    ├─► API endpoints available
    └─► Can register custom pipelines
    │
    ▼
Application Shutdown
    │
    └─► cleanup_pipeline_registry()
        └─► Cleanup all pipelines
```

### Architecture Patterns Used

1. **Registry Pattern**: Centralized pipeline management
2. **Factory Pattern**: Pipeline creation and initialization
3. **Strategy Pattern**: Custom query processors
4. **Template Method**: Base pipeline classes with hooks
5. **Composite Pattern**: Pipeline assembly
6. **Observer Pattern**: Status callbacks

### Design Decisions

1. **Why Registry?**
   - Single source of truth
   - Consistent access pattern
   - Easy to extend
   - Follows GraphRegistry pattern

2. **Why Categories?**
   - Logical organization
   - Flexible pipeline selection
   - Easy to add new types
   - Clear purpose separation

3. **Why Startup Initialization?**
   - Pipelines ready immediately
   - Consistent state
   - Fail fast if issues
   - Follows graph initialization pattern

4. **Why ExtractionPipeline Base?**
   - Consistent with existing pipelines
   - Familiar patterns
   - Built-in batch processing
   - Standard interface

---

## Summary

The async pipeline architecture provides a comprehensive, production-ready system for handling user queries and returning data. Key highlights:

### What You Get

- ✅ **4 Standard Pipelines** ready to use immediately
- ✅ **Registry-Based Access** for consistent pipeline management
- ✅ **REST API** with complete endpoint coverage
- ✅ **Pipeline Assembly** for complex workflow composition
- ✅ **Custom Pipeline Support** with multiple extension points
- ✅ **Status Monitoring** via callbacks and health endpoints
- ✅ **Comprehensive Documentation** with examples and guides
- ✅ **Production Ready** with error handling and logging

### Quick Commands

```bash
# Run examples
python examples/async_pipeline_usage.py

# Start server
python -m uvicorn app.main:app --reload

# Test API
curl http://localhost:8000/api/pipelines/health/status

# Access docs
open http://localhost:8000/docs
```

### Next Steps

1. Run the examples
2. Try the API endpoints
3. Create custom pipelines for your use case
4. Integrate with your assistants
5. Monitor performance and optimize

---

**For support or questions:**
- Check this guide
- Review examples in `examples/async_pipeline_usage.py`
- Test via API docs at `/docs`
- Check startup logs for initialization status

**Version:** 1.0.0  
**Last Updated:** January 2026
