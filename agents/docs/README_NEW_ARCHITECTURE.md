# New Dashboard Architecture

## Overview

The dashboard system has been refactored to use a cleaner, more modular pipeline architecture that eliminates unnecessary intermediaries and provides better separation of concerns.

## Architecture Flow

### Two-Step Architecture

```
DashboardOrchestratorPipeline
    ↓
Step 1: ConditionalFormattingGenerationPipeline
    ↓
ConditionalFormattingAgent → Enhanced Dashboard JSON
    ↓
Step 2: EnhancedDashboardStreamingPipeline
    ↓
DashboardStreamingPipeline → Final Results with Rules Applied
```

**Key**: Clean separation between rule generation and rule application!

## Components

### 1. DashboardOrchestrator
- **Location**: `app/services/writers/dashboard_orchestrator.py`
- **Purpose**: High-level orchestration of dashboard operations
- **Responsibilities**:
  - Coordinate between different services
  - Handle execution history and metrics
  - Provide validation and error handling
  - Manage service lifecycle

### 2. ConditionalFormattingGenerationPipeline
- **Location**: `app/agents/pipelines/conditional_formatting_generation_pipeline.py`
- **Purpose**: Generates conditional formatting configurations without applying them
- **Responsibilities**:
  - Validate dashboard context
  - Process natural language queries via ConditionalFormattingAgent
  - Generate enhanced dashboard JSON with execution instructions
  - Optimize configurations for performance
  - Provide detailed status updates and metrics

### 3. EnhancedDashboardStreamingPipeline
- **Location**: `app/agents/pipelines/enhanced_dashboard_streaming_pipeline.py`
- **Purpose**: Applies conditional formatting rules and streams dashboard results
- **Responsibilities**:
  - Apply SQL expansions to queries
  - Execute enhanced queries using DashboardStreamingPipeline
  - Apply chart adjustments to results
  - Stream intermediate and final results
  - Handle conditional formatting application logic

### 4. DashboardOrchestratorPipeline
- **Location**: `app/agents/pipelines/dashboard_orchestrator_pipeline.py`
- **Purpose**: Coordinates between the two main pipelines
- **Responsibilities**:
  - Orchestrate the complete workflow
  - Handle conditional formatting generation
  - Coordinate enhanced dashboard streaming
  - Provide unified interface for the entire process
  - Manage pipeline lifecycle and error handling

### 5. ConditionalFormattingAgent
- **Location**: `app/agents/nodes/writers/dashboard_agent.py`
- **Purpose**: Core business logic for conditional formatting
- **Responsibilities**:
  - Parse natural language queries
  - Generate SQL expansion rules
  - Create chart adjustment configurations
  - Handle business rule processing

**Note**: The `DashboardConditionalFormattingService` has been removed as it's no longer needed in the pipeline architecture.

## Key Benefits

### 1. **Two-Step Architecture**
- **Step 1**: Rule generation without application (ConditionalFormattingGenerationPipeline)
- **Step 2**: Rule application and streaming (EnhancedDashboardStreamingPipeline)
- Clear separation between rule creation and rule execution
- Easier to debug and test each step independently

### 2. **Cleaner Architecture**
- Removed unnecessary `dashboard_controller.py` intermediary
- Clear separation of concerns between pipelines
- Each component has a single, well-defined responsibility

### 3. **Better Pipeline Management**
- Dedicated conditional formatting generation pipeline
- Dedicated rule application and streaming pipeline
- Consistent pipeline interface across all components
- Better error handling and status reporting

### 4. **Improved Maintainability**
- Single place to modify conditional formatting logic
- Single place to modify rule application logic
- Easier to test individual components
- Clear dependency chain

### 5. **Enhanced Monitoring**
- Detailed metrics at each pipeline level
- Comprehensive status callbacks for each step
- Better execution history tracking
- Step-by-step progress monitoring

## Usage Examples

### Complete Two-Step Workflow

```python
from app.agents.pipelines.dashboard_orchestrator_pipeline import create_dashboard_orchestrator_pipeline
from app.core.engine_provider import EngineProvider

# Initialize
engine = EngineProvider.get_engine()
orchestrator_pipeline = create_dashboard_orchestrator_pipeline(engine=engine)

# Execute complete two-step workflow
result = await orchestrator_pipeline.run(
    dashboard_queries=dashboard_queries,
    natural_language_query=natural_language_query,
    dashboard_context=dashboard_context,
    project_id=project_id
)
```

### Step 1: Generate Conditional Formatting Only

```python
from app.agents.pipelines.conditional_formatting_generation_pipeline import create_conditional_formatting_generation_pipeline

# Create generation pipeline
generation_pipeline = create_conditional_formatting_generation_pipeline(engine=engine)

# Generate enhanced dashboard JSON
result = await generation_pipeline.run(
    natural_language_query=query,
    dashboard_context=context,
    project_id=project_id
)

# Extract enhanced dashboard
enhanced_dashboard = result.get("post_process", {}).get("enhanced_dashboard", {})
```

### Step 2: Apply Rules and Stream Results

```python
from app.agents.pipelines.enhanced_dashboard_streaming_pipeline import create_enhanced_dashboard_streaming_pipeline

# Create streaming pipeline
streaming_pipeline = create_enhanced_dashboard_streaming_pipeline(engine=engine)

# Apply rules and stream results
result = await streaming_pipeline.run(
    dashboard_queries=dashboard_queries,
    enhanced_dashboard=enhanced_dashboard,
    project_id=project_id
)
```

## Migration Guide

### What Changed

1. **Removed**: `dashboard_controller.py` - No longer needed
2. **Removed**: `dashboard_pipeline.py` - Functionality moved to dedicated pipeline
3. **Removed**: `DashboardConditionalFormattingService` - No longer needed in pipeline architecture
4. **Replaced**: `dashboard_integration_pipeline.py` with new two-step architecture
5. **New**: `conditional_formatting_generation_pipeline.py` - Step 1: Rule generation
6. **New**: `enhanced_dashboard_streaming_pipeline.py` - Step 2: Rule application
7. **New**: `dashboard_orchestrator_pipeline.py` - Coordinates the two steps

### What to Update

1. **Import statements**: Update imports to use new pipeline structure
2. **Service initialization**: Use the new factory functions
3. **Status callbacks**: Handle the new pipeline response format

### Response Format Changes

The conditional formatting pipeline now returns responses in this format:

```python
{
    "post_process": {
        "success": bool,
        "configuration": DashboardConfiguration,
        "chart_configurations": Dict,
        "metadata": Dict,
        "execution_metadata": Dict
    },
    "metadata": {
        "pipeline_name": str,
        "pipeline_version": str,
        "execution_timestamp": str,
        "configuration_used": Dict
    }
}
```

## Testing

Run the test script to verify the new architecture:

```bash
cd agents/app/agents/pipelines
python test_new_architecture.py
```

## Configuration

### Pipeline Configuration

```python
# Conditional formatting pipeline configuration
pipeline_config = {
    "max_retry_attempts": 3,
    "timeout_seconds": 60,
    "enable_caching": True,
    "cache_ttl_seconds": 3600,
    "enable_validation": True,
    "enable_optimization": True
}
```

### Service Configuration

```python
# Enhanced dashboard service configuration
service_config = {
    "concurrent_execution": True,
    "max_concurrent_queries": 5,
    "continue_on_error": True,
    "stream_intermediate_results": True
}
```

## Error Handling

The new architecture provides comprehensive error handling:

1. **Validation errors**: Dashboard context and query validation
2. **Processing errors**: Conditional formatting processing failures
3. **Execution errors**: Dashboard query execution failures
4. **Pipeline errors**: Pipeline-level failures with detailed logging

## Performance Considerations

1. **Concurrent execution**: Dashboard queries can run in parallel
2. **Caching**: Conditional formatting results can be cached
3. **Optimization**: Configurations are automatically optimized
4. **Streaming**: Intermediate results are streamed for better UX

## Future Enhancements

1. **Pipeline composition**: Ability to compose multiple pipelines
2. **Advanced caching**: Redis-based caching for better performance
3. **Metrics aggregation**: Centralized metrics collection
4. **Pipeline versioning**: Support for multiple pipeline versions
5. **Dynamic configuration**: Runtime pipeline configuration updates
