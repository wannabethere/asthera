# SQL Alert Condition Validator

The SQL validation system consists of two main components:

1. **`SQLValidationService`** (in `app.core.sql_validation`) - Core validation service that can be used by any agent
2. **`SQLAlertConditionValidator`** (in `app.agents.nodes.writers.alerts_agent`) - Convenience wrapper with LexyFeedCondition support

The core `SQLValidationService` validates SQL alert conditions by executing SQL queries and checking threshold conditions using the existing `execute_sql` methods from `PandasEngine`.

## Features

- **Threshold Validation**: Validate simple threshold conditions (>, <, >=, <=, =, !=)
- **Percentage Validation**: Validate percentage-based conditions (0-100%)
- **Change Validation**: Validate absolute change conditions between current and previous periods
- **Percent Change Validation**: Validate percentage change conditions between periods
- **Flexible Integration**: Works with any engine that implements `execute_sql` methods
- **Caching Support**: Optional caching for improved performance
- **Error Handling**: Comprehensive error handling and validation result reporting

## Usage

### Using Core Service Directly (Recommended for new agents)

```python
from app.core.pandas_engine import PandasEngine
from app.core.sql_validation import (
    SQLValidationService, 
    AlertConditionType, 
    ThresholdOperator
)

# Create engine with data
engine = PandasEngine()
engine.add_data_source('my_table', dataframe)

# Create validation service
validation_service = SQLValidationService(engine)

# Validate threshold condition
result = await validation_service.validate_threshold_condition(
    sql_query="SELECT completion_rate FROM my_table WHERE department = 'Engineering'",
    condition_type=AlertConditionType.THRESHOLD_VALUE,
    operator=ThresholdOperator.GREATER_THAN,
    threshold_value=90.0,
    metric_column='completion_rate'
)

print(f"Condition met: {result.condition_met}")
print(f"Current value: {result.current_value}")
```

### Using Alert-Specific Wrapper (For backward compatibility)

```python
from app.core.pandas_engine import PandasEngine
from app.agents.nodes.writers.alerts_agent import (
    SQLAlertConditionValidator, 
    AlertConditionType, 
    ThresholdOperator
)

# Create engine with data
engine = PandasEngine()
engine.add_data_source('my_table', dataframe)

# Create validator (wrapper around core service)
validator = SQLAlertConditionValidator(engine)

# Validate threshold condition
result = await validator.validate_threshold_condition(
    sql_query="SELECT completion_rate FROM my_table WHERE department = 'Engineering'",
    condition_type=AlertConditionType.THRESHOLD_VALUE,
    operator=ThresholdOperator.GREATER_THAN,
    threshold_value=90.0,
    metric_column='completion_rate'
)

print(f"Condition met: {result.condition_met}")
print(f"Current value: {result.current_value}")
```

### Using LexyFeedCondition Objects

```python
from app.agents.nodes.writers.alerts_agent import LexyFeedCondition

# Create condition object
condition = LexyFeedCondition(
    condition_type=AlertConditionType.THRESHOLD_VALUE,
    operator=ThresholdOperator.LESS_THAN,
    value=80.0
)

# Validate using condition object
result = await validator.validate_condition(
    sql_query="SELECT completion_rate FROM my_table",
    condition=condition,
    metric_column='completion_rate'
)
```

### Percentage Validation

```python
# Validate percentage condition (0-100%)
result = await validator.validate_percentage_condition(
    sql_query="SELECT budget_utilization FROM department_data",
    operator=ThresholdOperator.LESS_THAN,
    threshold_percentage=85.0,
    metric_column='budget_utilization'
)
```

### Change Validation

```python
# Validate absolute change condition
result = await validator.validate_change_condition(
    current_sql="SELECT sales FROM current_metrics",
    previous_sql="SELECT sales FROM previous_metrics",
    operator=ThresholdOperator.GREATER_THAN,
    change_threshold=2000.0
)
```

### Percent Change Validation

```python
# Validate percentage change condition
result = await validator.validate_percent_change_condition(
    current_sql="SELECT conversion_rate FROM current_metrics",
    previous_sql="SELECT conversion_rate FROM previous_metrics",
    operator=ThresholdOperator.GREATER_THAN,
    percent_change_threshold=10.0
)
```

## API Endpoints

### POST /alerts/validate-condition

Validate an alert condition using a full condition object.

**Request Body:**
```json
{
    "sql_query": "SELECT completion_rate FROM training_data",
    "condition_type": "threshold_value",
    "operator": ">",
    "threshold_value": 90.0,
    "metric_column": "completion_rate",
    "use_cache": true
}
```

**Response:**
```json
{
    "is_valid": true,
    "current_value": 85.5,
    "threshold_value": 90.0,
    "condition_met": false,
    "error_message": null,
    "validation_timestamp": "2025-01-07T14:39:16.614254",
    "execution_time_ms": 25.4
}
```

### POST /alerts/validate-threshold

Validate a simple threshold condition.

**Parameters:**
- `sql_query`: SQL query to execute
- `operator`: Threshold operator (>, <, >=, <=, =, !=)
- `threshold_value`: Threshold value to compare against
- `metric_column`: Optional specific column to extract value from
- `use_cache`: Whether to use caching (default: true)

## ValidationResult Model

The `ValidationResult` model contains the following fields:

- `is_valid`: Whether the validation was successful
- `current_value`: Current value from the SQL query
- `threshold_value`: Threshold value used for comparison
- `condition_met`: Whether the condition is currently met
- `error_message`: Error message if validation failed
- `validation_timestamp`: Timestamp when validation was performed
- `execution_time_ms`: Execution time in milliseconds

## Supported Condition Types

- `THRESHOLD_VALUE`: Simple value-based threshold alerts
- `THRESHOLD_CHANGE`: Absolute change from previous period
- `THRESHOLD_PERCENT_CHANGE`: Percentage change from previous period
- `THRESHOLD_ABSOLUTE_CHANGE`: Alias for THRESHOLD_CHANGE
- `INTELLIGENT_ARIMA`: Not supported (requires historical analysis)

## Supported Operators

- `GREATER_THAN`: >
- `LESS_THAN`: <
- `GREATER_EQUAL`: >=
- `LESS_EQUAL`: <=
- `EQUALS`: =
- `NOT_EQUALS`: !=

## Error Handling

The validator provides comprehensive error handling for:

- SQL execution failures
- Missing or invalid data
- Invalid numeric values
- Unsupported condition types
- Missing required parameters

All errors are captured in the `ValidationResult.error_message` field.

## Performance Considerations

- Use caching (`use_cache=True`) for repeated validations with the same SQL queries
- The validator automatically detects and uses the appropriate `execute_sql` method (async or sync)
- Execution time is tracked and reported in the `ValidationResult`

## Integration with Existing Code

The validator is designed to work seamlessly with existing `PandasEngine` instances and can be easily integrated into:

- Alert service validation workflows
- Feed management pipelines
- Real-time monitoring systems
- Batch validation processes

## Example Integration

```python
# In your alert service
class AlertService:
    def __init__(self, engine):
        self.engine = engine
        self.validator = SQLAlertConditionValidator(engine)
    
    async def validate_alert_condition(self, sql_query, condition):
        return await self.validator.validate_condition(
            sql_query=sql_query,
            condition=condition
        )
```

This validator provides a robust foundation for validating SQL alert conditions while leveraging the existing database engine infrastructure.
