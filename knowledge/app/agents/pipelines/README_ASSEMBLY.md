# Pipeline Assembly Architecture

A general-purpose pipeline orchestration system that allows composing multiple pipelines together in a reusable way.

## Overview

The `PipelineAssembly` class provides a flexible architecture for:
- **Chaining pipelines** together in sequence
- **Parallel execution** of pipelines
- **Conditional routing** based on results
- **Pipeline composition** for integration/assembly

This architecture can be used by any service that needs to orchestrate multiple pipelines, such as:
- Contextual assistants
- Integration services
- Workflow orchestrators
- Multi-step processing systems

## Key Concepts

### PipelineAssembly

The main orchestration class that manages multiple pipeline steps.

### PipelineStep

Represents a single pipeline in the assembly with:
- Pipeline instance
- Input/output mappers
- Conditions for execution
- Retry logic
- Timeout handling

### PipelineAssemblyConfig

Configuration for the assembly:
- Execution mode (sequential, parallel, conditional)
- Error handling strategy
- Result aggregation
- Concurrency limits

## Usage Examples

### Example 1: Sequential Assembly (Context Retrieval → Reasoning)

```python
from app.agents.pipelines import (
    PipelineAssembly,
    PipelineStep,
    PipelineAssemblyConfig,
    PipelineExecutionMode,
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline
)

# Create assembly
config = PipelineAssemblyConfig(
    assembly_id="contextual_reasoning",
    assembly_name="Contextual Reasoning Assembly",
    execution_mode=PipelineExecutionMode.SEQUENTIAL
)

assembly = PipelineAssembly(config=config)

# Add context retrieval step
assembly.add_step(
    PipelineStep(
        pipeline=retrieval_pipeline,
        step_id="retrieve_context",
        step_name="Context Retrieval",
        input_mapper=lambda state: {
            "query": state.get("query"),
            "include_all_contexts": True,
            "top_k": 5
        },
        output_mapper=lambda result: {
            "context_ids": result.get("data", {}).get("context_ids", []),
            "context_metadata": result.get("data", {}).get("contexts", [])
        }
    )
)

# Add reasoning step
assembly.add_step(
    PipelineStep(
        pipeline=reasoning_pipeline,
        step_id="reason",
        step_name="Contextual Reasoning",
        input_mapper=lambda state: {
            "query": state.get("query"),
            "context_id": state.get("context_ids", [None])[0],
            "reasoning_type": "multi_hop",
            "max_hops": 3
        },
        output_mapper=lambda result: {
            "reasoning_result": result.get("data", {}),
            "reasoning_path": result.get("data", {}).get("reasoning_path", [])
        },
        condition=lambda state: bool(state.get("context_ids"))  # Only if contexts found
    )
)

# Initialize and run
await assembly.initialize()

result = await assembly.run(
    inputs={
        "query": "What access control measures should I prioritize?"
    }
)
```

### Example 2: Using Factory Function

```python
from app.agents.pipelines import create_contextual_reasoning_assembly

# Create pre-configured assembly
assembly = create_contextual_reasoning_assembly(
    retrieval_pipeline=retrieval_pipeline,
    reasoning_pipeline=reasoning_pipeline,
    assembly_id="my_reasoning_assembly"
)

await assembly.initialize()

result = await assembly.run(
    inputs={
        "query": "What are the highest-risk controls?",
        "filters": {"industry": "healthcare"}
    }
)
```

### Example 3: Parallel Execution

```python
config = PipelineAssemblyConfig(
    assembly_id="parallel_analysis",
    assembly_name="Parallel Analysis Assembly",
    execution_mode=PipelineExecutionMode.PARALLEL,
    max_concurrent=3
)

assembly = PipelineAssembly(config=config)

# Add multiple pipelines that can run in parallel
assembly.add_step(
    PipelineStep(
        pipeline=priority_controls_pipeline,
        step_id="priority_controls",
        step_name="Priority Controls Analysis"
    )
)

assembly.add_step(
    PipelineStep(
        pipeline=risk_analysis_pipeline,
        step_id="risk_analysis",
        step_name="Risk Analysis"
    )
)

assembly.add_step(
    PipelineStep(
        pipeline=compliance_gap_pipeline,
        step_id="compliance_gaps",
        step_name="Compliance Gap Analysis"
    )
)

# All three run in parallel
result = await assembly.run(inputs={"query": "..."})
```

### Example 4: Conditional Execution

```python
config = PipelineAssemblyConfig(
    assembly_id="conditional_workflow",
    assembly_name="Conditional Workflow",
    execution_mode=PipelineExecutionMode.CONDITIONAL
)

assembly = PipelineAssembly(config=config)

# Step 1: Always execute
assembly.add_step(
    PipelineStep(
        pipeline=retrieval_pipeline,
        step_id="retrieve",
        step_name="Retrieve Contexts"
    )
)

# Step 2: Only if contexts found
assembly.add_step(
    PipelineStep(
        pipeline=reasoning_pipeline,
        step_id="reason",
        step_name="Reason",
        condition=lambda state: len(state.get("context_ids", [])) > 0
    )
)

# Step 3: Only if reasoning succeeded
assembly.add_step(
    PipelineStep(
        pipeline=qa_pipeline,
        step_id="answer",
        step_name="Generate Answer",
        condition=lambda state: bool(state.get("reasoning_result"))
    )
)
```

### Example 5: Error Handling and Retries

```python
assembly.add_step(
    PipelineStep(
        pipeline=external_api_pipeline,
        step_id="external_api",
        step_name="External API Call",
        required=False,  # Can skip if fails
        retry_count=3,  # Retry up to 3 times
        timeout=30.0,  # 30 second timeout
        error_handling="continue"  # Continue even if fails
    )
)
```

### Example 6: Result Aggregation

```python
def aggregate_results(step_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Custom result aggregator"""
    aggregated = {
        "all_contexts": [],
        "all_reasoning_paths": [],
        "combined_insights": []
    }
    
    for step_result in step_results:
        if step_result.get("success"):
            result = step_result.get("result", {})
            if "context_ids" in result:
                aggregated["all_contexts"].extend(result["context_ids"])
            if "reasoning_path" in result:
                aggregated["all_reasoning_paths"].append(result["reasoning_path"])
    
    return aggregated

config = PipelineAssemblyConfig(
    assembly_id="aggregated_analysis",
    assembly_name="Aggregated Analysis",
    execution_mode=PipelineExecutionMode.PARALLEL,
    result_aggregator=aggregate_results
)
```

## Integration with Services

### Using in Contextual Assistants

```python
from app.agents.assistants.nodes import ContextRetrievalNode

class ContextRetrievalNode:
    def __init__(self, assembly: PipelineAssembly):
        self.assembly = assembly
    
    async def __call__(self, state):
        result = await self.assembly.run(
            inputs={
                "query": state.get("query"),
                "user_context": state.get("user_context")
            }
        )
        
        if result.get("success"):
            data = result.get("data", {})
            state["context_ids"] = data.get("final_state", {}).get("context_ids", [])
            state["reasoning_result"] = data.get("final_state", {}).get("reasoning_result")
        
        return state
```

### Using in Integration Services

```python
class IntegrationService:
    def __init__(self):
        # Create assembly for integration workflow
        self.assembly = PipelineAssembly(
            config=PipelineAssemblyConfig(
                assembly_id="integration_workflow",
                execution_mode=PipelineExecutionMode.SEQUENTIAL
            )
        )
        
        # Add integration steps
        self.assembly.add_step(...)
        self.assembly.add_step(...)
    
    async def process(self, data):
        return await self.assembly.run(inputs=data)
```

## Advanced Features

### Custom Input/Output Mappers

```python
def map_retrieval_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """Custom input mapping"""
    return {
        "query": state.get("query"),
        "context_ids": state.get("user_context", {}).get("context_ids"),
        "filters": {
            "industry": state.get("user_context", {}).get("industry"),
            "maturity_level": state.get("user_context", {}).get("maturity_level")
        }
    }

def map_reasoning_output(result: Dict[str, Any]) -> Dict[str, Any]:
    """Custom output mapping"""
    data = result.get("data", {})
    return {
        "reasoning_result": data,
        "reasoning_path": data.get("reasoning_path", []),
        "final_answer": data.get("final_answer", "")
    }

assembly.add_step(
    PipelineStep(
        pipeline=reasoning_pipeline,
        step_id="reason",
        input_mapper=map_retrieval_input,
        output_mapper=map_reasoning_output
    )
)
```

### Status Callbacks

```python
def status_callback(status: str, data: Dict[str, Any]):
    """Handle status updates"""
    if status == "assembly_started":
        print(f"Assembly started: {data['assembly_id']}")
    elif status == "step_started":
        print(f"Step started: {data['step_name']}")
    elif status == "step_completed":
        print(f"Step completed: {data['step_name']}")

result = await assembly.run(
    inputs={...},
    status_callback=status_callback
)
```

## Best Practices

1. **Use factory functions** for common patterns (like `create_contextual_reasoning_assembly`)

2. **Map inputs/outputs** to decouple pipeline interfaces from assembly state

3. **Use conditions** to make assemblies flexible and avoid unnecessary execution

4. **Set appropriate timeouts** for external API calls or long-running pipelines

5. **Use retries** for transient failures, but set reasonable limits

6. **Mark optional steps** as `required=False` if they can be skipped

7. **Aggregate results** when using parallel execution to combine outputs

8. **Handle errors gracefully** using error_handling strategies

## Architecture Benefits

- **Reusable**: Same assembly architecture works for any pipeline combination
- **Flexible**: Supports sequential, parallel, and conditional execution
- **Composable**: Easy to add/remove steps
- **Testable**: Each step can be tested independently
- **Observable**: Status callbacks provide visibility into execution
- **Robust**: Built-in retry, timeout, and error handling

