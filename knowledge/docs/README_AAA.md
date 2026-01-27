# Contextual Assistants

LangGraph-based assistants that use contextual graph reasoning to provide context-aware answers and content generation.

## Overview

Contextual Assistants are intelligent agents built using LangGraph that:
- **Understand user intent** using LLM analysis
- **Retrieve relevant contexts** from contextual graphs
- **Perform context-aware reasoning** using multi-hop reasoning
- **Answer questions** with context-specific information
- **Generate written content** (reports, analyses, summaries)
- **Route to other graphs** when needed
- **Support actor types** for personalized responses

## Architecture

```
User Query
    ↓
Intent Understanding Node
    ↓
Context Retrieval Node (uses ContextualGraphRetrievalPipeline)
    ↓
Contextual Reasoning Node (uses ContextualGraphReasoningPipeline)
    ↓
    ├─→ Q&A Agent Node (if intent is question/analysis)
    │       ↓
    └─→ Executor Node (if intent is execution)
            ↓
    Writer Agent Node (receives results from Q&A or Executor)
    - Decides: summary or return_result based on intent reasoning
            ↓
    Finalize Node
            ↓
    Final Answer
```

## Key Features

### 1. Actor Types

All responses are personalized based on actor type:
- **data_scientist**: Technical, data-driven, high detail
- **business_analyst**: Business-focused, ROI-oriented, medium detail
- **product_manager**: User-focused, outcome-oriented, medium detail
- **executive**: Strategic, concise, high-level
- **consultant**: Expert advice, best practices, medium-high detail
- **compliance_officer**: Regulatory-focused, risk-aware, high detail
- **technical_lead**: Implementation-focused, architecture-oriented, high detail

### 2. Context-Aware Reasoning

Every action uses context from the contextual graph:
- Retrieves relevant organizational/situational contexts
- Performs multi-hop reasoning within contexts
- Provides context-specific answers and recommendations

### 3. Integration with Streaming Service

Assistants are registered with the graph registry and work seamlessly with the streaming service for real-time updates.

## Usage

### Basic Setup

```python
import asyncio
import asyncpg
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.services.contextual_graph_service import ContextualGraphService
from app.pipelines import (
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline
)
from app.assistants import create_contextual_assistant_factory
from app.streams.graph_registry import get_registry

# Initialize services
db_pool = await asyncpg.create_pool("postgresql://...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Create contextual graph service
contextual_graph_service = ContextualGraphService(
    db_pool=db_pool,
    chroma_client=chroma_client,
    embeddings_model=OpenAIEmbeddings(),
    llm=ChatOpenAI(model="gpt-4o")
)

# Create pipelines
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

# Create assistant factory
factory = create_contextual_assistant_factory(
    contextual_graph_service=contextual_graph_service,
    retrieval_pipeline=retrieval_pipeline,
    reasoning_pipeline=reasoning_pipeline,
    graph_registry=get_registry(),
    model_name="gpt-4o"
)

# Create and register assistant
graph_config = factory.create_and_register_assistant(
    assistant_id="compliance_assistant",
    name="Compliance Assistant",
    description="Context-aware compliance assistant",
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

# Stream graph execution
async def stream_query(query: str, actor_type: str = "consultant"):
    input_data = {
        "query": query,
        "actor_type": actor_type,
        "user_context": {
            "industry": "healthcare",
            "organization_size": "large"
        }
    }
    
    session_id = "session_123"
    
    async for event in streaming_service.stream_graph_execution(
        assistant_id="compliance_assistant",
        graph_id=None,  # Uses default
        input_data=input_data,
        session_id=session_id
    ):
        print(event)  # SSE-formatted event
        # Process event (node_started, node_completed, state_update, result, etc.)

# Run query
await stream_query(
    query="What access control measures should I prioritize for HIPAA compliance?",
    actor_type="compliance_officer"
)
```

### Direct Graph Invocation

```python
# Get graph from registry
registry = get_registry()
graph_config = registry.get_assistant_graph("compliance_assistant")

# Invoke graph
result = await graph_config.graph.ainvoke({
    "query": "What are the highest-risk controls for my organization?",
    "actor_type": "executive",
    "user_context": {
        "context_ids": ["context_123"],  # Optional: specific contexts
        "filters": {
            "industry": "healthcare",
            "maturity_level": "developing"
        }
    }
})

print(result["final_answer"])
```

### Using via API (Streaming Router)

The assistants work automatically with the streaming router:

```bash
# POST /api/streams/invoke
curl -X POST http://localhost:8000/api/streams/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "compliance_assistant",
    "query": "What access control measures should I prioritize?",
    "input_data": {
      "actor_type": "compliance_officer",
      "user_context": {
        "industry": "healthcare"
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
    "session_id": "session_123",
    "user_context": {
        "context_ids": ["context_1"],
        "filters": {"industry": "healthcare"}
    },
    "intent": "question",  # Determined by intent understanding
    "intent_confidence": 0.95,
    "actor_type": "compliance_officer",
    "context_ids": ["context_1", "context_2"],  # Retrieved contexts
    "reasoning_result": {...},  # From contextual reasoning
    "qa_answer": "...",  # From Q&A agent (if intent was question)
    "executor_result": {...},  # From executor agent (if intent was execution)
    "executor_output": "...",  # Formatted executor output
    "written_content": "...",  # From writer agent
    "writer_decision": "summary" or "return_result",  # Writer's decision
    "final_answer": "...",  # Final response
    "messages": [...]  # Conversation history
}
```

## Node Details

### 1. Intent Understanding Node
- Analyzes user query
- Determines intent (question, analysis, writing, graph_query)
- Sets confidence and required actions
- Routes to appropriate next node

### 2. Context Retrieval Node
- Uses `ContextualGraphRetrievalPipeline`
- Retrieves relevant contexts from contextual graph
- Creates reasoning plan
- Filters contexts based on user context

### 3. Contextual Reasoning Node
- Uses `ContextualGraphReasoningPipeline`
- Performs multi-hop reasoning within contexts
- Generates context-specific insights
- Provides reasoning path

### 4. Q&A Agent Node
- Answers questions using contextual information
- Used when intent is "question" or "analysis"
- Uses actor type for personalized responses
- Includes sources from reasoning path
- Provides confidence scores
- Routes to Writer node

### 5. Executor Agent Node
- Executes actions/operations based on user intent
- Used when intent is "execution"
- Performs context-aware actions using reasoning results
- Returns structured results with actions performed
- Uses actor type for output formatting
- Routes to Writer node

### 6. Writer Agent Node
- Receives results from either Q&A or Executor
- **Decides** whether to create a summary or return result directly
- Decision based on:
  - User intent and intent details
  - Complexity of results
  - Number of sources
  - Actor type preferences
- If summary: Creates comprehensive summary synthesizing all information
- If return_result: Formats the result nicely and returns it
- Uses actor type for style and detail level

### 7. Graph Router Node
- Routes to other graphs if needed
- Prepares input for sub-graphs
- Handles graph execution results

### 8. Finalize Node
- Combines all results
- Creates final output structure
- Sets completion status

## Actor Type Examples

### Executive Actor
```python
input_data = {
    "query": "What are our compliance risks?",
    "actor_type": "executive"
}
# Response: Concise, high-level, strategic, focuses on business impact
```

### Compliance Officer Actor
```python
input_data = {
    "query": "What are our compliance risks?",
    "actor_type": "compliance_officer"
}
# Response: Detailed, regulatory-focused, includes specific controls and requirements
```

### Data Scientist Actor
```python
input_data = {
    "query": "What are our compliance risks?",
    "actor_type": "data_scientist"
}
# Response: Technical, data-driven, includes metrics and statistical measures
```

## Error Handling

The assistants handle errors gracefully:
- If context retrieval fails, falls back to Q&A with available information
- If reasoning fails, uses basic Q&A
- Errors are captured in state and included in final output
- Status is set to "error" with error message

## Best Practices

1. **Initialize pipelines before creating assistants**
   ```python
   await retrieval_pipeline.initialize()
   await reasoning_pipeline.initialize()
   ```

2. **Use appropriate actor types**
   - Match actor type to user role/needs
   - Executive: Use for high-level questions
   - Compliance Officer: Use for detailed compliance questions

3. **Provide user context when available**
   ```python
   input_data = {
       "query": "...",
       "user_context": {
           "context_ids": ["specific_context_id"],  # If known
           "filters": {
               "industry": "healthcare",
               "maturity_level": "developing"
           }
       }
   }
   ```

4. **Use checkpointing for long conversations**
   ```python
   factory.create_and_register_assistant(
       ...,
       use_checkpointing=True  # Enables state persistence
   )
   ```

5. **Monitor streaming events**
   - Listen for `node_started`, `node_completed` for progress
   - Check `state_update` for intermediate results
   - Use `result` event for final output

## Integration with Existing Systems

The assistants integrate seamlessly with:
- **Graph Registry**: Automatic registration and lookup
- **Streaming Service**: Real-time SSE updates
- **Contextual Graph Service**: Context retrieval and reasoning
- **Pipelines**: Reuses existing pipeline infrastructure

## Example: Full Workflow

```python
# 1. Setup (one-time)
factory = create_contextual_assistant_factory(...)
graph_config = factory.create_and_register_assistant(
    assistant_id="my_assistant",
    name="My Assistant"
)

# 2. Use via streaming
async for event in streaming_service.stream_graph_execution(
    assistant_id="my_assistant",
    input_data={
        "query": "What should I prioritize?",
        "actor_type": "executive"
    },
    session_id="session_1"
):
    # Process events
    if "result" in event:
        final_result = parse_result(event)
        print(final_result["final_answer"])
```

## Troubleshooting

### Assistant not found
- Ensure assistant is registered: `factory.create_and_register_assistant(...)`
- Check assistant_id matches: `registry.get_assistant(assistant_id)`

### No contexts retrieved
- Check contextual graph has contexts: `contextual_graph_service.search_contexts(...)`
- Verify user_context filters are correct

### Reasoning fails
- Check context_ids are valid
- Verify contextual graph service is properly initialized
- Check database connection

### Actor type not working
- Verify actor type is in `ACTOR_TYPE_CONFIGS`
- Check actor_type is passed in input_data
- Default is "consultant" if not specified

