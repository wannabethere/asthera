# Alert Service Compatibility Layer

This document explains how to integrate your existing `main.py` application with the `alert_service.py` functionality while maintaining minimal changes to your codebase.

## Overview

The compatibility layer provides:
- **Identical model structures** that match your `main.py` models exactly
- **Automatic conversion** between different model formats
- **Seamless integration** with the alert service pipeline
- **Backward compatibility** with your existing API endpoints

## Files Created

1. **`alert_service.py`** - Now contains both the original alert service functionality AND compatibility models and wrapper classes
2. **`main_integration_example.py`** - Shows how to modify your main.py with minimal changes

## Key Components

### Compatibility Models

These models exactly match your `main.py` structure:

```python
class Condition(BaseModel):
    conditionType: str
    metricselected: str
    schedule: str
    timecolumn: str
    value: Optional[str] = None

class AlertResponseCompatibility(BaseModel):
    type: str
    question: str
    alertname: str
    summary: str
    reasoning: str
    conditions: List[Condition]
    notificationgroup: str

class Configs(BaseModel):
    conditionTypes: List[str]
    notificationgroups: List[str]  
    schedule: List[str]
    timecolumn: List[str]
    availableMetrics: List[str]
    question: str

class AlertCreate(BaseModel):
    input: str
    config: Optional[Configs] = None
    session_id: Optional[str] = None
```

### Compatibility Wrapper

The `AlertServiceCompatibility` class provides:

- **`convert_condition_to_alert_set()`** - Converts your Condition models to AlertSet format
- **`create_alerts_from_response()`** - Creates alerts in the service from your AlertResponse
- **`convert_service_response_to_compatibility()`** - Converts service responses back to your format

## Integration Steps

### Step 1: Import the Compatibility Layer

```python
from .alert_service import (
    Condition, AlertResponseCompatibility, Configs, AlertCreate,
    AlertServiceCompatibility, create_alert_service_with_compatibility
)
```

### Step 2: Initialize in Your AIAlertsService

```python
class AIAlertsService:
    def __init__(self):
        # ... your existing initialization ...
        
        # Add these lines
        self.alert_service, self.compatibility_wrapper = create_alert_service_with_compatibility()
```

### Step 3: Enhance Your createAlerts Method

Add this code after parsing the JSON response in your `createAlerts` method:

```python
# After parsing json_response and validating with AlertResponseCompatibility
if json_response.get("type") == "finished":
    alert_response = AlertResponseCompatibility(**json_response)
    
    # Convert to alert service format and create the alert
    try:
        service_response = await self.compatibility_wrapper.create_alerts_from_response(
            alert_response=alert_response,
            project_id="your_project_id",  # Pass your project ID
            session_id=getattr(self, 'current_session_id', None)
        )
        
        # Add service response info to the JSON response
        json_response["service_created"] = service_response.success
        json_response["service_metadata"] = service_response.metadata
        
        # Update the AI response with the enhanced information
        ai_response = json.dumps(json_response, indent=2)
        
    except Exception as service_error:
        print(f"Warning: Could not create alert in service: {service_error}")
        # Continue with the original response even if service creation fails
```

## Benefits

1. **Zero Breaking Changes** - Your existing API endpoints work exactly the same
2. **Automatic Alert Creation** - Alerts are automatically created in the service when valid
3. **Enhanced Responses** - Your responses now include service metadata
4. **Graceful Degradation** - If service creation fails, your original functionality continues
5. **Future-Proof** - Easy to extend with additional service features

## Usage Examples

### Basic Usage (No Changes Required)

Your existing code continues to work:

```python
# This still works exactly as before
alert = AlertCreate(
    input="Create an alert for high dropout rates",
    config=Configs(
        conditionTypes=["greaterthan"],
        availableMetrics=["dropout_rate"],
        schedule=["weekly"],
        timecolumn=["rolling"],
        notificationgroups=["slack team"],
        question="What is the dropout rate?"
    )
)

response = await ai_alert_create(alert)
```

### Enhanced Response

The response now includes additional service information:

```json
{
  "response": {
    "type": "finished",
    "question": "What is the dropout rate?",
    "alertname": "High Dropout Rate Alert",
    "summary": "Monitors dropout rate weekly",
    "reasoning": "User requested weekly monitoring",
    "conditions": [...],
    "notificationgroup": "slack team",
    "service_created": true,
    "service_metadata": {
      "event_id": "uuid-here",
      "pipeline_name": "alert_orchestrator",
      "execution_timestamp": "2024-01-01T00:00:00"
    }
  },
  "session_id": "session-uuid",
  "conversation_history": {...},
  "has_stored_configs": true
}
```

## Configuration

### Project ID

You'll need to provide a project ID for alert creation. You can:

1. **Hardcode it** (for single-project applications)
2. **Pass it in the request** (modify AlertCreate to include project_id)
3. **Use environment variables** (recommended for production)

### Error Handling

The integration includes comprehensive error handling:

- **Validation errors** are caught and logged
- **Service creation failures** don't break your existing functionality
- **Graceful degradation** ensures your API remains stable

## Advanced Features

### Custom SQL Query Generation

The `convert_condition_to_alert_set()` method generates basic SQL queries. You can enhance this by:

1. **Overriding the method** in a subclass
2. **Providing custom SQL templates** based on your data schema
3. **Using your existing query generation logic**

### Custom Metadata

You can add custom metadata to the service responses by modifying the `global_configuration` parameter in `create_alerts_from_response()`.

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the alert_service.py is in the correct path
2. **Project ID Missing**: Make sure to provide a valid project_id
3. **Service Not Available**: Check that the alert service pipeline is properly configured

### Debug Mode

Enable debug logging by adding:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Migration Path

1. **Phase 1**: Add compatibility layer (no breaking changes)
2. **Phase 2**: Gradually enhance with service features
3. **Phase 3**: Migrate to full service integration when ready

This approach ensures you can adopt the new functionality incrementally while maintaining full backward compatibility.
