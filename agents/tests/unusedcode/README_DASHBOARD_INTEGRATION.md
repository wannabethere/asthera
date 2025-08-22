# Dashboard Pipeline Integration

## Overview

The dashboard pipelines have been successfully integrated into the main `PipelineContainer` initialization, making them available for all services that use the pipeline container. This integration ensures that dashboard functionality is accessible throughout the system without requiring additional setup.

## Integrated Pipelines

### 1. **dashboard_streaming**
- **Purpose**: Basic dashboard streaming pipeline for executing SQL queries and streaming results
- **Access**: `container.get_pipeline("dashboard_streaming")`
- **Use Case**: When you need basic dashboard query execution without conditional formatting

### 2. **conditional_formatting_generation**
- **Purpose**: Generates conditional formatting rules from natural language queries
- **Access**: `container.get_pipeline("conditional_formatting_generation")`
- **Use Case**: When you need to generate formatting rules without applying them

### 3. **enhanced_dashboard_streaming**
- **Purpose**: Applies conditional formatting rules and streams enhanced results
- **Access**: `container.get_pipeline("enhanced_dashboard_streaming")`
- **Use Case**: When you need to apply pre-generated rules to dashboard queries

### 4. **dashboard_orchestrator**
- **Purpose**: Complete workflow orchestration (generation + application + streaming)
- **Access**: `container.get_pipeline("dashboard_orchestrator")`
- **Use Case**: When you need the complete dashboard workflow in one call

## Integration Details

### Automatic Initialization
All dashboard pipelines are automatically initialized when the `PipelineContainer.initialize()` method is called:

```python
# This automatically includes all dashboard pipelines
container = PipelineContainer.initialize()

# Dashboard pipelines are now available
dashboard_orchestrator = container.get_pipeline("dashboard_orchestrator")
```

### Dependencies
The integration handles all necessary dependencies:
- **Engine**: Database engine for SQL execution
- **LLM**: Language model for conditional formatting generation
- **Retrieval Helper**: For data retrieval operations
- **Document Store Provider**: For document-based operations

### Pipeline Dependencies
The pipelines are initialized in the correct order to handle dependencies:
1. `dashboard_streaming` - Base streaming pipeline
2. `conditional_formatting_generation` - Rule generation pipeline
3. `enhanced_dashboard_streaming` - Enhanced streaming with rule application
4. `dashboard_orchestrator` - Orchestrates all pipelines

## Usage Examples

### Complete Workflow (Recommended)
```python
from app.agents.pipelines.pipeline_container import PipelineContainer

# Initialize container (includes all dashboard pipelines)
container = PipelineContainer.initialize()

# Get the dashboard orchestrator
orchestrator = container.get_pipeline("dashboard_orchestrator")

# Execute complete workflow
result = await orchestrator.run(
    dashboard_queries=dashboard_queries,
    natural_language_query="Highlight sales > $10,000 in green",
    dashboard_context=dashboard_context,
    project_id="my_project"
)
```

### Individual Pipeline Usage
```python
# Get individual pipelines
cf_pipeline = container.get_pipeline("conditional_formatting_generation")
streaming_pipeline = container.get_pipeline("enhanced_dashboard_streaming")

# Generate rules first
cf_result = await cf_pipeline.run(
    natural_language_query="Highlight sales > $10,000 in green",
    dashboard_context=dashboard_context,
    project_id="my_project"
)

# Extract enhanced dashboard
enhanced_dashboard = cf_result.get("post_process", {}).get("enhanced_dashboard", {})

# Apply rules and stream results
streaming_result = await streaming_pipeline.run(
    dashboard_queries=dashboard_queries,
    enhanced_dashboard=enhanced_dashboard,
    project_id="my_project"
)
```

### Basic Dashboard Streaming
```python
# For basic dashboard execution without conditional formatting
basic_streaming = container.get_pipeline("dashboard_streaming")

result = await basic_streaming.run(
    queries=dashboard_queries,
    project_id="my_project"
)
```

## Service Integration

### For New Services
New services can easily access dashboard functionality:

```python
class MyDashboardService:
    def __init__(self):
        # Initialize pipeline container (includes all dashboard pipelines)
        self.pipeline_container = PipelineContainer.initialize()
        
        # Get dashboard orchestrator for complete workflow
        self.dashboard_orchestrator = self.pipeline_container.get_pipeline("dashboard_orchestrator")
    
    async def process_dashboard(self, queries, context, formatting_query=None):
        return await self.dashboard_orchestrator.run(
            dashboard_queries=queries,
            natural_language_query=formatting_query,
            dashboard_context=context,
            project_id="my_service_project"
        )
```

### For Existing Services
Existing services can add dashboard functionality:

```python
class ExistingService:
    def __init__(self):
        # ... existing initialization ...
        
        # Add dashboard capability
        self.pipeline_container = PipelineContainer.initialize()
        self.dashboard_orchestrator = self.pipeline_container.get_pipeline("dashboard_orchestrator")
    
    async def enhanced_method(self, queries, context, formatting_query=None):
        # ... existing logic ...
        
        # Add dashboard processing
        if formatting_query:
            dashboard_result = await self.dashboard_orchestrator.run(
                dashboard_queries=queries,
                natural_language_query=formatting_query,
                dashboard_context=context,
                project_id="enhanced_method_project"
            )
            # ... process dashboard result ...
```

## Configuration

### Pipeline Configuration
Each pipeline can be configured individually:

```python
# Get pipeline
orchestrator = container.get_pipeline("dashboard_orchestrator")

# Update configuration
orchestrator.update_configuration({
    "enable_conditional_formatting": True,
    "enable_streaming": True,
    "enable_validation": True
})

# Get current configuration
config = orchestrator.get_configuration()
```

### Available Configuration Options

#### Dashboard Orchestrator
- `enable_conditional_formatting`: Enable/disable conditional formatting
- `enable_streaming`: Enable/disable streaming
- `enable_validation`: Enable/disable validation
- `enable_metrics`: Enable/disable metrics collection

#### Conditional Formatting Generation
- `enable_validation`: Enable/disable dashboard context validation
- `enable_optimization`: Enable/disable configuration optimization
- `generate_sql_expansions`: Enable/disable SQL expansion generation
- `generate_chart_adjustments`: Enable/disable chart adjustment generation

#### Enhanced Dashboard Streaming
- `apply_sql_expansions`: Enable/disable SQL expansion application
- `apply_chart_adjustments`: Enable/disable chart adjustment application
- `apply_conditional_formats`: Enable/disable conditional format application
- `concurrent_execution`: Enable/disable concurrent query execution

## Testing

### Integration Test
Run the integration test to verify all pipelines are working:

```bash
cd agents/app/agents/pipelines
python test_dashboard_integration.py
```

### Usage Example
Run the usage example to see how services can use the integrated pipelines:

```bash
cd agents/app/agents/pipelines
python example_service_usage.py
```

## Benefits of Integration

### 1. **Centralized Access**
- All dashboard pipelines available through single container
- No need to import or initialize pipelines separately
- Consistent interface across all services

### 2. **Automatic Dependency Management**
- Dependencies automatically resolved during initialization
- Proper initialization order maintained
- No manual dependency setup required

### 3. **Service Consistency**
- All services use the same pipeline instances
- Consistent configuration and behavior
- Shared metrics and monitoring

### 4. **Easy Maintenance**
- Single place to update pipeline configurations
- Centralized error handling and logging
- Simplified testing and debugging

## Troubleshooting

### Common Issues

#### Pipeline Not Found
```python
# Error: Pipeline 'dashboard_orchestrator' not found
# Solution: Ensure PipelineContainer.initialize() was called
container = PipelineContainer.initialize()
```

#### Import Errors
```python
# Error: Module not found
# Solution: Check that all dashboard pipeline files are in the correct location
# They should be in: agents/app/agents/pipelines/writers/
```

#### Initialization Errors
```python
# Error: Pipeline initialization failed
# Solution: Check that all dependencies are available
# - Database engine
# - Language model
# - Retrieval helper
# - Document store provider
```

### Debug Information
Get debug information about available pipelines:

```python
container = PipelineContainer.initialize()

# List all available pipelines
all_pipelines = container.get_all_pipelines()
print("Available pipelines:", list(all_pipelines.keys()))

# Check specific pipeline
try:
    pipeline = container.get_pipeline("dashboard_orchestrator")
    print("Pipeline found:", pipeline.__class__.__name__)
    print("Initialized:", pipeline.is_initialized)
except KeyError as e:
    print("Pipeline not found:", e)
```

## Future Enhancements

### Planned Improvements
1. **Pipeline Versioning**: Support for multiple pipeline versions
2. **Dynamic Configuration**: Runtime configuration updates
3. **Pipeline Composition**: Ability to compose custom pipeline workflows
4. **Advanced Metrics**: Enhanced monitoring and analytics
5. **Pipeline Hot-swapping**: Ability to swap pipelines without restart

### Extension Points
The integration is designed to be easily extensible:
- Add new dashboard pipelines by updating the container initialization
- Modify pipeline configurations through the configuration system
- Add new pipeline types by extending the base pipeline classes
- Integrate with external monitoring and logging systems

## Conclusion

The dashboard pipeline integration provides a robust, maintainable, and easy-to-use system for dashboard functionality. All services can now access advanced dashboard capabilities through a simple, consistent interface, while maintaining the flexibility to use individual pipelines when needed.

The integration follows best practices for dependency management, error handling, and configuration, making it suitable for production use in complex systems.
