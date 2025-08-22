# Dashboard Controller Refactor

The dashboard controller has been refactored into separate, focused classes for better maintainability and organization.

## New Structure

### 1. `dashboard_models.py`
Contains all data models and enums:
- `FilterOperator`: Enum for filter operations (equals, greater_than, contains, etc.)
- `FilterType`: Enum for filter types (column_filter, time_filter, etc.)
- `ActionType`: Enum for action types (sql_expansion, chart_adjustment, both)
- `ControlFilter`: Dataclass for individual filter configurations
- `ConditionalFormat`: Dataclass for conditional formatting rules
- `DashboardConfiguration`: Main configuration class that combines all filters and formats

### 2. `dashboard_retriever.py`
Contains the `ConditionalFormattingRetriever` class:
- Retrieves similar historical configurations
- Gets examples of specific filter types
- Integrates with the retrieval helper for RAG functionality

### 3. `dashboard_agent.py`
Contains the `ConditionalFormattingAgent` class:
- LangChain agent for translating natural language to configurations
- Uses tools for retrieving examples and validating configurations
- Processes queries and generates structured configurations

### 4. `dashboard_service.py`
Contains the `DashboardConditionalFormattingService` class:
- Main service that orchestrates the agent and retriever
- Handles configuration caching and history
- Stores configurations for future retrieval
- Provides the main API for processing requests

### 5. `dashboard_pipeline.py`
Contains the `ConditionalFormattingPipeline` class:
- Integrates with the existing AgentPipeline architecture
- Wraps the service for pipeline execution
- Handles pipeline-specific configuration and execution

### 6. `dashboard_factory.py`
Contains factory functions:
- `create_conditional_formatting_service()`: Creates service instances
- `create_conditional_formatting_pipeline()`: Creates pipeline instances
- Example usage and demonstration code

### 7. `dashboard_controller.py` (Updated)
- Now serves as a thin wrapper that imports and re-exports all classes
- Maintains backward compatibility
- Contains the main factory function and example usage

## Benefits of the Refactor

1. **Separation of Concerns**: Each class has a single, focused responsibility
2. **Maintainability**: Easier to modify individual components without affecting others
3. **Testability**: Each class can be tested independently
4. **Reusability**: Components can be used in different combinations
5. **Readability**: Smaller, focused files are easier to understand
6. **Extensibility**: New features can be added to specific components

## Usage Examples

### Using the Service Directly
```python
from agents.app.agents.nodes.sql.dashboard_service import DashboardConditionalFormattingService

service = DashboardConditionalFormattingService(llm, retrieval_helper, doc_store_provider)
result = await service.process_conditional_formatting_request(
    query="Highlight sales > $1000 in green",
    dashboard_context={...},
    project_id="my_project"
)
```

### Using the Pipeline
```python
from agents.app.agents.nodes.sql.dashboard_pipeline import ConditionalFormattingPipeline

pipeline = ConditionalFormattingPipeline(llm, retrieval_helper, doc_store_provider)
result = await pipeline.run(
    query="Highlight sales > $1000 in green",
    dashboard_context={...},
    project_id="my_project"
)
```

### Using Factory Functions
```python
from agents.app.agents.nodes.sql.dashboard_factory import create_conditional_formatting_service

service = create_conditional_formatting_service()
result = await service.process_conditional_formatting_request(...)
```

## Migration Notes

- All existing functionality is preserved
- The original `dashboard_controller.py` still works as before
- New imports are available for more granular control
- Backward compatibility is maintained through the `__all__` exports

## File Dependencies

```
dashboard_models.py (no dependencies)
    ↓
dashboard_retriever.py (depends on models)
    ↓
dashboard_agent.py (depends on models, retriever)
    ↓
dashboard_service.py (depends on models, agent, retriever)
    ↓
dashboard_pipeline.py (depends on service)
    ↓
dashboard_controller.py (depends on all)
```

This structure ensures clean separation while maintaining the ability to use any level of abstraction needed.
