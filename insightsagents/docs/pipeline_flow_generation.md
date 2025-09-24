# Pipeline Flow Generation

This document describes the new pipeline flow generation functionality that creates separate code for each step and generates comprehensive flow graphs.

## Overview

The pipeline flow generation system consists of three main components:

1. **SelfCorrectingPipelineCodeGenerator** (Modified) - Generates separate code for each step
2. **FlowGraphGenerator** - Creates comprehensive flow graphs with analysis
3. **PipelineFlowIntegrationAgent** - Integrates both components for complete solution

## Key Features

### Separate Step Code Generation
- Each step in the reasoning plan generates individual, executable code
- Steps maintain their dependencies and execution order
- Each step has its own input/output dataframes
- Backward compatibility with combined code generation

### Flow Graph Generation
- **Nodes**: Represent individual processing steps with metadata
- **Edges**: Represent data flow and dependencies between steps
- **Analysis**: Execution order, dependencies, data flow, and optimization opportunities
- **Visualization**: Data for rendering flow graphs in UI tools

### Enhanced Metadata
- **Execution Analysis**: Critical path, parallel opportunities, execution order
- **Dependency Analysis**: Circular dependencies, orphaned nodes, dependency depth
- **Data Flow Analysis**: Data transformations, bottlenecks, volume estimates
- **Complexity Metrics**: Step complexity, execution time, memory usage

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                PipelineFlowIntegrationAgent                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐    ┌─────────────────────────┐ │
│  │ SelfCorrectingPipeline  │    │    FlowGraphGenerator   │ │
│  │     CodeGenerator       │    │                         │ │
│  │                         │    │                         │ │
│  │ • Generate step codes   │    │ • Create flow graph     │ │
│  │ • Maintain dependencies │    │ • Analyze execution     │ │
│  │ • Backward compatibility│    │ • Identify optimizations│ │
│  └─────────────────────────┘    └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage

```python
from app.agents.nodes.mlagents.pipeline_flow_integration import PipelineFlowIntegrationAgent

# Initialize the agent
agent = PipelineFlowIntegrationAgent(
    llm=llm,
    usage_examples_store=usage_examples_store,
    code_examples_store=code_examples_store,
    function_definition_store=function_definition_store
)

# Generate pipeline with flow graph
result = await agent.generate_pipeline_with_flow_graph(
    context="Analyze variance over time with moving averages",
    function_name=["variance", "moving_apply_by_group"],
    function_inputs={"variable": "value", "group_column": "group"},
    dataframe_name="df",
    classification=classification_result
)
```

### Accessing Results

```python
# Pipeline result with separate step codes
pipeline_result = result["pipeline_result"]
step_codes = pipeline_result["step_codes"]
combined_code = pipeline_result["generated_code"]

# Flow graph with analysis
flow_graph_result = result["flow_graph_result"]
execution_analysis = flow_graph_result["execution_analysis"]
dependency_analysis = flow_graph_result["dependency_analysis"]
data_flow_analysis = flow_graph_result["data_flow_analysis"]

# Integration metadata
integration_metadata = result["integration_metadata"]
```

## Data Structures

### Step Code Structure

```python
{
    "step_number": 1,
    "code": "# Calculate Basic Variance\nstep_1_result = (\n    MetricsPipe.from_dataframe(df)\n    | variance(variable='value')\n    ).to_df()",
    "title": "Calculate Basic Variance",
    "function": "variance",
    "pipeline_type": "MetricsPipe",
    "input_dataframe": "df",
    "output_dataframe": "step_1_result",
    "dependencies": []
}
```

### Flow Graph Node Structure

```python
{
    "id": "step_1",
    "title": "Calculate Basic Variance",
    "node_type": "processing",
    "function": "variance",
    "pipeline_type": "MetricsPipe",
    "input_dataframe": "df",
    "output_dataframe": "step_1_result",
    "dependencies": [],
    "input_columns": ["value"],
    "output_columns": ["variance_value"],
    "code": "...",
    "metadata": {
        "execution_order": 1,
        "complexity_score": 0.3,
        "estimated_execution_time": "fast",
        "memory_usage": "medium"
    }
}
```

### Flow Graph Edge Structure

```python
{
    "from_node": "step_1",
    "to_node": "step_2",
    "edge_type": "data_flow",
    "data_flow": "step_1_result -> step_2_input",
    "metadata": {
        "flow_type": "sequential",
        "is_critical": True
    }
}
```

## Analysis Features

### Execution Analysis
- **Execution Order**: Sequential order of step execution
- **Critical Path**: Longest dependency chain through the pipeline
- **Parallel Opportunities**: Steps that can be executed in parallel
- **Execution Complexity**: Assessment of overall execution complexity

### Dependency Analysis
- **Dependency Graph**: Complete dependency relationships
- **Circular Dependencies**: Detection of circular dependencies
- **Orphaned Nodes**: Steps with no dependencies or dependents
- **Dependency Depth**: Maximum depth of dependency chains

### Data Flow Analysis
- **Data Transformations**: Tracking of data transformations at each step
- **Bottlenecks**: Identification of potential performance bottlenecks
- **Volume Estimates**: Estimation of data volumes at each step
- **Memory Usage**: Assessment of memory requirements

### Optimization Opportunities
- **Parallel Execution**: Steps that can run in parallel
- **Bottleneck Optimization**: High-complexity or high-memory steps
- **Dependency Optimization**: Circular dependencies and orphaned nodes
- **Cleanup**: Unnecessary or redundant steps

## Visualization

The flow graph generator provides visualization data for rendering in UI tools:

```python
visualization_data = flow_graph_result["visualization_data"]
node_positions = visualization_data["node_positions"]
edge_paths = visualization_data["edge_paths"]
canvas_size = visualization_data["canvas_size"]
```

## Benefits

### For Developers
- **Modularity**: Each step is independently executable
- **Debugging**: Easier to debug individual steps
- **Testing**: Can test individual steps in isolation
- **Maintenance**: Easier to modify or replace individual steps

### For Users
- **Transparency**: Clear understanding of pipeline structure
- **Optimization**: Identified opportunities for performance improvement
- **Visualization**: Visual representation of data flow
- **Analysis**: Comprehensive analysis of pipeline characteristics

### For System
- **Scalability**: Better handling of complex pipelines
- **Parallelization**: Opportunities for parallel execution
- **Resource Management**: Better understanding of resource requirements
- **Monitoring**: Enhanced monitoring and debugging capabilities

## Migration Guide

### From Combined Code to Separate Steps

The system maintains backward compatibility:

```python
# Old way (still works)
combined_code = pipeline_result["generated_code"]

# New way (recommended)
step_codes = pipeline_result["step_codes"]
for step in step_codes:
    print(f"Step {step['step_number']}: {step['code']}")
```

### Integration with Existing Code

```python
# Existing pipeline generation
pipeline_result = await pipeline_generator.generate_pipeline_code(...)

# New flow graph generation
flow_graph_result = flow_graph_generator.generate_flow_graph(pipeline_result)

# Combined approach
integration_result = await integration_agent.generate_pipeline_with_flow_graph(...)
```

## Examples

See `insightsagents/examples/pipeline_flow_example.py` for a complete working example.

## Future Enhancements

- **Dynamic Execution**: Runtime execution of individual steps
- **Step Caching**: Caching of step results for reuse
- **Conditional Execution**: Support for conditional step execution
- **Parallel Execution**: Automatic parallel execution of independent steps
- **Step Monitoring**: Real-time monitoring of step execution
- **Performance Profiling**: Detailed performance analysis of each step
