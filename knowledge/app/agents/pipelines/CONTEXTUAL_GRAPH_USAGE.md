# Contextual Graph Retrieval and Reasoning Usage

This document shows how to use the Contextual Graph Retrieval and Reasoning agents and pipelines.

## Architecture Overview

The implementation follows a clear separation of concerns:

- **Agents**: Contain the core logic for context retrieval and reasoning
- **Pipelines**: Orchestrate the agents and provide a consistent interface

## Components

### Agents

1. **ContextualGraphRetrievalAgent**: Handles context retrieval and reasoning plan creation
2. **ContextualGraphReasoningAgent**: Performs context-aware reasoning using retrieved contexts

### Pipelines

1. **ContextualGraphRetrievalPipeline**: Orchestrates context retrieval
2. **ContextualGraphReasoningPipeline**: Orchestrates reasoning with context

## Usage Examples

### Example 1: Retrieve Contexts and Create Reasoning Plan

```python
import asyncio
from langchain_openai import ChatOpenAI
from app.services.contextual_graph_service import ContextualGraphService
from app.agents.pipelines import ContextualGraphRetrievalPipeline

# Initialize service (requires db_pool and chroma_client)
service = ContextualGraphService(
    db_pool=db_pool,
    chroma_client=chroma_client,
    llm=ChatOpenAI(model="gpt-4o")
)

# Create pipeline
pipeline = ContextualGraphRetrievalPipeline(
    contextual_graph_service=service,
    model_name="gpt-4o"
)

# Initialize
await pipeline.initialize()

# Run retrieval
result = await pipeline.run(
    inputs={
        "query": "What access control measures should I prioritize for a healthcare organization preparing for HIPAA audit?",
        "include_all_contexts": True,
        "top_k": 5,
        "target_domain": "healthcare"
    }
)

# Access results
contexts = result["data"]["contexts"]
reasoning_plan = result["data"]["reasoning_plan"]

print(f"Retrieved {len(contexts)} contexts")
print(f"Reasoning plan has {len(reasoning_plan.get('reasoning_steps', []))} steps")
```

### Example 2: Perform Context-Aware Reasoning

```python
from app.agents.pipelines import ContextualGraphReasoningPipeline

# Create reasoning pipeline
reasoning_pipeline = ContextualGraphReasoningPipeline(
    contextual_graph_service=service,
    model_name="gpt-4o"
)

await reasoning_pipeline.initialize()

# Multi-hop reasoning
result = await reasoning_pipeline.run(
    inputs={
        "query": "What evidence do I need for access controls?",
        "context_id": "ctx_healthcare_001",
        "reasoning_type": "multi_hop",
        "max_hops": 3
    }
)

reasoning_path = result["data"]["reasoning_path"]
final_answer = result["data"]["final_answer"]

print(f"Reasoning path: {len(reasoning_path)} hops")
print(f"Final answer: {final_answer}")
```

### Example 3: Get Priority Controls for Context

```python
# Get priority controls
result = await reasoning_pipeline.run(
    inputs={
        "query": "access control compliance",
        "context_id": "ctx_healthcare_001",
        "reasoning_type": "priority_controls",
        "top_k": 10
    }
)

controls = result["data"]["controls"]
for control in controls:
    print(f"Control: {control.get('control', {}).get('control_name')}")
    print(f"Priority reasoning: {control.get('context_reasoning')}")
```

### Example 4: Multi-Context Synthesis

```python
# First retrieve multiple contexts
retrieval_result = await pipeline.run(
    inputs={
        "query": "What are the highest-risk controls?",
        "include_all_contexts": True,
        "top_k": 3
    }
)

contexts = retrieval_result["data"]["contexts"]

# Then synthesize reasoning across contexts
synthesis_result = await reasoning_pipeline.run(
    inputs={
        "query": "What are the highest-risk controls?",
        "contexts": contexts,
        "reasoning_type": "synthesis",
        "max_hops": 2
    }
)

synthesis = synthesis_result["data"]["synthesis"]
print(f"Synthesized answer: {synthesis.get('synthesized_answer')}")
print(f"Common patterns: {synthesis.get('common_patterns')}")
```

### Example 5: Complete Workflow - Retrieve and Reason

```python
async def complete_contextual_reasoning(query: str):
    """Complete workflow: retrieve contexts and perform reasoning"""
    
    # Step 1: Retrieve contexts
    retrieval_result = await pipeline.run(
        inputs={
            "query": query,
            "include_all_contexts": True,
            "top_k": 3
        }
    )
    
    if not retrieval_result["success"]:
        return {"error": "Context retrieval failed"}
    
    contexts = retrieval_result["data"]["contexts"]
    reasoning_plan = retrieval_result["data"]["reasoning_plan"]
    
    # Step 2: Perform reasoning for primary context
    primary_context = contexts[0] if contexts else None
    if primary_context:
        reasoning_result = await reasoning_pipeline.run(
            inputs={
                "query": query,
                "context_id": primary_context["context_id"],
                "reasoning_plan": reasoning_plan,
                "reasoning_type": "multi_hop",
                "max_hops": 3
            }
        )
        
        return {
            "contexts": contexts,
            "reasoning_plan": reasoning_plan,
            "reasoning_result": reasoning_result
        }
    
    return {"error": "No contexts found"}

# Usage
result = await complete_contextual_reasoning(
    "What access control measures should I prioritize?"
)
```

### Example 6: Using Agents Directly (Without Pipelines)

```python
from app.agents import ContextualGraphRetrievalAgent, ContextualGraphReasoningAgent

# Create agents directly
retrieval_agent = ContextualGraphRetrievalAgent(
    contextual_graph_service=service
)

reasoning_agent = ContextualGraphReasoningAgent(
    contextual_graph_service=service
)

# Use agents
contexts_result = await retrieval_agent.retrieve_contexts(
    query="healthcare compliance context",
    top_k=5
)

contexts = contexts_result["contexts"]

# Create reasoning plan
plan_result = await retrieval_agent.create_reasoning_plan(
    user_action="Generate metadata for HIPAA controls",
    retrieved_contexts=contexts,
    target_domain="healthcare"
)

# Perform reasoning
reasoning_result = await reasoning_agent.reason_with_context(
    query="What evidence is needed for access controls?",
    context_id=contexts[0]["context_id"],
    max_hops=3,
    reasoning_plan=plan_result.get("reasoning_plan")
)
```

## Integration with Other Pipelines

The contextual graph pipelines can work together with other extraction pipelines:

```python
from app.agents.pipelines import (
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline,
    ControlExtractionPipeline,
    ContextExtractionPipeline
)

# 1. Extract context from description
context_pipeline = ContextExtractionPipeline()
context_result = await context_pipeline.run(
    inputs={
        "description": "Large healthcare organization with Epic EHR, preparing for HIPAA audit"
    }
)

context_id = context_result["data"]["context_id"]

# 2. Retrieve related contexts
retrieval_pipeline = ContextualGraphRetrievalPipeline(
    contextual_graph_service=service
)
retrieval_result = await retrieval_pipeline.run(
    inputs={
        "query": "HIPAA access control requirements",
        "context_ids": [context_id],
        "top_k": 5
    }
)

# 3. Perform reasoning
reasoning_pipeline = ContextualGraphReasoningPipeline(
    contextual_graph_service=service
)
reasoning_result = await reasoning_pipeline.run(
    inputs={
        "query": "What controls should I prioritize?",
        "context_id": context_id,
        "reasoning_type": "priority_controls"
    }
)

# 4. Extract controls based on reasoning
controls = reasoning_result["data"]["controls"]
for control_info in controls:
    control = control_info.get("control")
    if control:
        # Use control extraction pipeline if needed
        # control_pipeline = ControlExtractionPipeline()
        # ...
```

## Reasoning Types

The `ContextualGraphReasoningPipeline` supports different reasoning types:

1. **multi_hop**: Multi-hop reasoning through the contextual graph
2. **priority_controls**: Get priority controls for a context
3. **synthesis**: Synthesize reasoning across multiple contexts
4. **infer_properties**: Infer context-dependent properties for an entity

## Status Callbacks

Both pipelines support status callbacks for progress tracking:

```python
def status_callback(status: str, info: dict):
    print(f"Status: {status}, Info: {info}")

result = await pipeline.run(
    inputs={"query": "..."},
    status_callback=status_callback
)
```

## Error Handling

All methods return dictionaries with `success` and `error` fields:

```python
result = await pipeline.run(inputs={...})

if not result["success"]:
    print(f"Error: {result.get('error')}")
    # Handle error
else:
    # Process successful result
    data = result["data"]
```

## Data Store Integration

The agents now use **all available data stores** from the knowledge base:

### Available Data Stores

1. **Controls** - From `control_service`
   - Control definitions, frameworks, categories
   - Vector document IDs for semantic search

2. **Requirements** - From `requirement_service`
   - Requirements for each control
   - Requirement types and text

3. **Evidence Types** - From `evidence_service`
   - Evidence categories and collection methods
   - Evidence-to-requirement mappings

4. **Measurements** - From `measurement_service`
   - Compliance measurements with context
   - Risk analytics (trends, scores, failure counts)
   - Historical measurement data

5. **Contextual Edges** - From `vector_storage`
   - Context-aware relationships between entities
   - Edge types (REQUIRES, PROVED_BY, etc.)
   - Relevance scores and priorities

6. **Control Profiles** - From `vector_storage`
   - Context-specific control implementation profiles
   - Risk scores, complexity, effort estimates

### Enriched Results

When you retrieve controls or perform reasoning, results are automatically enriched with:

- **Requirements** for each control
- **Evidence types** that prove requirements
- **Measurements** and compliance history
- **Risk analytics** (trends, scores, failure counts)
- **Contextual edges** showing relationships
- **Entity counts** and metadata

### Example: Get Enriched Control Information

```python
# Get priority controls with all data
result = await reasoning_pipeline.run(
    inputs={
        "query": "access control compliance",
        "context_id": "ctx_healthcare_001",
        "reasoning_type": "priority_controls",
        "top_k": 10,
        "include_requirements": True,  # Include requirements
        "include_evidence": True,      # Include evidence types
        "include_measurements": True    # Include measurements
    }
)

# Each control now includes:
for control in result["data"]["controls"]:
    print(f"Control: {control['control']['control_name']}")
    print(f"  Requirements: {control['requirements_count']}")
    print(f"  Evidence types: {control['evidence_count']}")
    print(f"  Measurements: {control['measurements_count']}")
    print(f"  Risk level: {control.get('risk_analytics', {}).get('risk_level')}")
    print(f"  Contextual edges: {control['edges_count']}")
```

### Example: Get Comprehensive Entity Information

```python
# Get all information about an entity
entity_info = await reasoning_agent.get_comprehensive_entity_info(
    entity_id="HIPAA-AC-001",
    entity_type="control",
    context_id="ctx_healthcare_001"
)

# Returns:
# - Control details
# - Requirements
# - Evidence types
# - Measurements
# - Risk analytics
# - Outgoing edges (relationships)
# - Incoming edges (what relates to it)
```

### Example: Enriched Reasoning Path

When performing multi-hop reasoning, the reasoning path is enriched with:

```python
result = await reasoning_pipeline.run(
    inputs={
        "query": "What evidence do I need?",
        "context_id": "ctx_healthcare_001",
        "reasoning_type": "multi_hop"
    }
)

# Each hop in reasoning_path includes:
for hop in result["data"]["reasoning_path"]:
    print(f"Hop {hop['hop']}: {hop['entity_type']}")
    print(f"  Entities found: {hop['entities_found']}")
    if "entities_enriched" in hop:
        for entity in hop["entities_enriched"]:
            print(f"    - {entity}")  # Includes requirements, edges, analytics
```

## Best Practices

1. **Always initialize pipelines** before use
2. **Use reasoning plans** when available for better results
3. **Prioritize contexts** before multi-context synthesis
4. **Handle errors gracefully** - check `success` field
5. **Use appropriate reasoning types** for your use case
6. **Enable data enrichment** - use `include_requirements`, `include_evidence`, `include_measurements`
7. **Use comprehensive entity info** for detailed analysis
8. **Clean up resources** when done (optional but recommended)

```python
# Clean up
await pipeline.cleanup()
```

