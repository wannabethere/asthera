# Data Assistance Assistant

A specialized assistant that retrieves knowledge from contextual retrieval for schemas, metrics, and controls, and helps users answer questions about metrics for compliance controls (e.g., SOC2, GDPR, HIPAA).

## Overview

The Data Assistance Assistant is built using the contextual assistants framework and provides:

- **Schema Retrieval**: Retrieves database schemas from the project
- **Metrics Retrieval**: Retrieves existing metrics from the metrics registry
- **Controls Retrieval**: Retrieves compliance controls from the contextual graph (e.g., SOC2, GDPR, HIPAA)
- **Metric Generation**: Generates new metrics based on schema definitions and control requirements
- **Q&A Capabilities**: Answers questions about metrics, schemas, and how metrics help with compliance controls

## Key Features

1. **Contextual Knowledge Retrieval**
   - Retrieves database schemas using RetrievalHelper
   - Retrieves existing metrics from the metrics registry
   - Retrieves compliance controls from contextual graph service
   - Automatically extracts compliance framework (SOC2, GDPR, HIPAA, etc.) from queries

2. **Metric Generation**
   - Generates new metrics based on:
     - Available database schemas
     - Existing metrics (to avoid duplicates)
     - Compliance control requirements
   - Provides SQL queries for calculated metrics
   - Suggests metrics relevant to compliance monitoring

3. **Compliance-Focused Q&A**
   - Answers questions like "What metrics will help for SOC2 Controls?"
   - Explains how metrics relate to compliance controls
   - Suggests new metrics for compliance monitoring
   - Provides context-aware answers based on available data

## Architecture

The Data Assistance Assistant extends the `ContextualAssistantGraphBuilder` framework, providing:
- **Framework Features**: State management, memory/checkpointing, actor types, routing
- **Data Assistance Extensions**: Schema/metric retrieval, metric generation, compliance-focused Q&A

```
User Query (with project_id)
    ↓
Intent Understanding Node (Framework)
    ↓
Context Retrieval Node (Framework)
    └─→ Retrieves contexts from contextual graph
    ↓
Data Knowledge Retrieval Node (Extension)
    ├─→ Retrieve Database Schemas (RetrievalHelper)
    ├─→ Retrieve Existing Metrics (RetrievalHelper)
    └─→ Retrieve Compliance Controls (uses framework's context_ids)
    ↓
Metric Generation Node (Extension)
    ├─→ Analyze schemas and controls
    └─→ Generate new metrics (if needed)
    ↓
Contextual Reasoning Node (Framework)
    └─→ Performs context-aware reasoning
    ↓
Data Assistance Q&A Node (Extension)
    ├─→ Answer questions using retrieved knowledge
    └─→ Explain metric-control relationships
    ↓
Writer Agent Node (Framework)
    ↓
Finalize Node (Framework)
    ↓
Final Answer
```

## Usage

### Basic Setup

```python
import asyncio
import asyncpg
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.services.contextual_graph_service import ContextualGraphService
from app.pipelines import (
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline
)
from app.assistants import create_data_assistance_factory
from app.streams.graph_registry import get_registry

# Initialize services (framework requirements)
db_pool = await asyncpg.create_pool("postgresql://...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Create contextual graph service
contextual_graph_service = ContextualGraphService(
    db_pool=db_pool,
    chroma_client=chroma_client,
    embeddings_model=OpenAIEmbeddings(),
    llm=ChatOpenAI(model="gpt-4o")
)

# Create pipelines (framework requirements)
retrieval_pipeline = ContextualGraphRetrievalPipeline(
    contextual_graph_service=contextual_graph_service,
    model_name="gpt-4o"
)

reasoning_pipeline = ContextualGraphReasoningPipeline(
    contextual_graph_service=contextual_graph_service,
    model_name="gpt-4o"
)

# Initialize pipelines
await retrieval_pipeline.initialize()
await reasoning_pipeline.initialize()

# Initialize retrieval helper for data assistance
retrieval_helper = RetrievalHelper()

# Create factory (using framework)
factory = create_data_assistance_factory(
    retrieval_helper=retrieval_helper,
    contextual_graph_service=contextual_graph_service,
    retrieval_pipeline=retrieval_pipeline,
    reasoning_pipeline=reasoning_pipeline,
    graph_registry=get_registry(),
    model_name="gpt-4o"
)

# Create and register assistant
graph_config = factory.create_and_register_assistant(
    assistant_id="data_assistance_assistant",
    name="Data Assistance Assistant",
    description="Helps answer questions about metrics, schemas, and compliance controls",
    use_checkpointing=True,
    set_as_default=True
)

print(f"Assistant registered: {graph_config.graph_id}")
```

### Using with Streaming Service

```python
from app.streams.streaming_service import GraphStreamingService
from app.streams.graph_registry import get_registry

# Get streaming service
streaming_service = GraphStreamingService(registry=get_registry())

# Stream query
async def stream_query(query: str, project_id: str, actor_type: str = "consultant"):
    input_data = {
        "query": query,
        "project_id": project_id,  # Required for data assistance
        "actor_type": actor_type,
        "user_context": {
            "framework": "SOC2"  # Optional: specify framework
        }
    }
    
    session_id = "session_123"
    
    async for event in streaming_service.stream_graph_execution(
        assistant_id="data_assistance_assistant",
        graph_id=None,  # Uses default
        input_data=input_data,
        session_id=session_id
    ):
        print(event)  # SSE-formatted event

# Example queries
await stream_query(
    query="What metrics will help for SOC2 Controls from my data source?",
    project_id="my_project_id",
    actor_type="compliance_officer"
)

await stream_query(
    query="Generate new metrics for access control monitoring",
    project_id="my_project_id",
    actor_type="data_scientist"
)
```

### Direct Graph Invocation

```python
# Get graph from registry
registry = get_registry()
graph_config = registry.get_assistant_graph("data_assistance_assistant")

# Invoke graph
result = await graph_config.graph.ainvoke({
    "query": "What metrics help with SOC2 CC6.1 control?",
    "project_id": "my_project_id",
    "actor_type": "compliance_officer",
    "user_context": {
        "framework": "SOC2"
    }
})

print(result["final_answer"])
```

### Using via API (Streaming Router)

```bash
# POST /api/streams/invoke
curl -X POST http://localhost:8000/api/streams/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "data_assistance_assistant",
    "query": "What metrics will help for SOC2 Controls?",
    "input_data": {
      "project_id": "my_project_id",
      "actor_type": "compliance_officer",
      "user_context": {
        "framework": "SOC2"
      }
    },
    "session_id": "session_123"
  }'
```

## State Structure

The assistant state includes:

```python
{
    "query": "User's question",
    "project_id": "project_123",  # Required
    "session_id": "session_123",
    "user_context": {
        "framework": "SOC2",  # Optional: specify framework
        "context_ids": ["context_1"]  # Optional: specific contexts
    },
    "actor_type": "compliance_officer",
    "intent": "question",  # Determined by intent understanding
    "data_knowledge": {
        "schemas": [...],  # Retrieved database schemas
        "metrics": [...],  # Existing metrics
        "controls": [...],  # Compliance controls
        "framework": "SOC2",
        "project_id": "project_123"
    },
    "generated_metrics": [...],  # Newly generated metrics
    "qa_answer": "...",  # Answer from Q&A node
    "final_answer": "...",  # Final response
    "messages": [...]  # Conversation history
}
```

## Example Queries

### Compliance-Focused Questions

1. **"What metrics will help for SOC2 Controls from my data source?"**
   - Retrieves schemas, metrics, and SOC2 controls
   - Maps metrics to controls
   - Suggests new metrics if needed

2. **"How can I monitor access control compliance with my current data?"**
   - Analyzes schemas for access control data
   - Retrieves relevant controls
   - Suggests metrics for monitoring

3. **"Generate metrics for GDPR compliance monitoring"**
   - Retrieves GDPR controls
   - Analyzes schemas
   - Generates new metrics

### Schema and Metric Questions

4. **"What tables and columns are available in my database?"**
   - Retrieves and formats schema information
   - Shows relationships between tables

5. **"What metrics are available for user activity analysis?"**
   - Retrieves relevant metrics
   - Explains how to use them

6. **"Create a new metric for calculating daily active users"**
   - Analyzes schema
   - Generates metric definition with SQL

## Node Details

### 1. Data Knowledge Retrieval Node
- Retrieves database schemas using RetrievalHelper
- Retrieves existing metrics from metrics registry
- Retrieves compliance controls from contextual graph service
- Extracts compliance framework from query or user context
- Stores all knowledge in state for use by other nodes

### 2. Metric Generation Node
- Analyzes schemas, existing metrics, and controls
- Determines if metric generation is needed
- Generates new metrics with:
  - Name, display name, description
  - SQL query for calculation
  - Metric type and aggregation
  - Relevance to compliance controls
- Only generates if explicitly requested or if controls need metrics

### 3. Data Assistance Q&A Node
- Answers questions using retrieved knowledge
- Explains relationships between metrics and controls
- Provides context-aware answers
- Formats responses in Markdown
- Uses actor type for personalized responses

## Integration with Existing Systems

The assistant integrates with:
- **RetrievalHelper**: For schema and metric retrieval
- **ContextualGraphService**: For compliance control retrieval
- **Graph Registry**: Automatic registration and lookup
- **Streaming Service**: Real-time SSE updates
- **Actor Types**: Personalized responses based on user role

## Best Practices

1. **Always provide project_id**
   ```python
   input_data = {
       "query": "...",
       "project_id": "required_project_id"
   }
   ```

2. **Specify framework when asking about compliance**
   ```python
   input_data = {
       "query": "What metrics help with access control?",
       "project_id": "project_id",
       "user_context": {
           "framework": "SOC2"
       }
   }
   ```

3. **Use appropriate actor types**
   - `compliance_officer`: For compliance-focused questions
   - `data_scientist`: For technical metric questions
   - `business_analyst`: For business-focused questions

4. **Use checkpointing for conversations**
   ```python
   factory.create_and_register_assistant(
       ...,
       use_checkpointing=True  # Enables state persistence
   )
   ```

## Troubleshooting

### No schemas retrieved
- Verify project_id is correct
- Check that RetrievalHelper is properly initialized
- Ensure database schemas are indexed

### No controls retrieved
- Verify ContextualGraphService is provided
- Check that controls are saved in contextual graph
- Ensure framework is specified (SOC2, GDPR, etc.)

### Metric generation not working
- Check that schemas are available
- Verify query explicitly requests metric generation
- Check LLM model is accessible

## Example: Full Workflow

```python
# 1. Setup (one-time)
factory = create_data_assistance_factory(
    retrieval_helper=retrieval_helper,
    contextual_graph_service=contextual_graph_service
)
graph_config = factory.create_and_register_assistant(
    assistant_id="data_assistance_assistant",
    name="Data Assistance Assistant"
)

# 2. Use via streaming
async for event in streaming_service.stream_graph_execution(
    assistant_id="data_assistance_assistant",
    input_data={
        "query": "What metrics will help for SOC2 Controls?",
        "project_id": "my_project_id",
        "actor_type": "compliance_officer"
    },
    session_id="session_1"
):
    if "result" in event:
        final_result = parse_result(event)
        print(final_result["final_answer"])
```

