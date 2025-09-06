# Feed Management Pipeline Documentation

## Overview

The **Feed Management Pipeline** is a comprehensive solution for managing multiple sets of alerts with feed IDs and configurations. It provides a structured approach to process, validate, and orchestrate multiple alert configurations within a single feed, enabling efficient management of complex alert scenarios without requiring database calls.

## Key Features

- **Multi-Alert Processing**: Handle multiple alert combinations within a single feed configuration
- **Array Structure Support**: Process arrays of `[alert_request, sql, natural_language_query]` combinations
- **Feed ID Management**: Unique identification and tracking of feed configurations
- **Parallel Processing**: Concurrent processing of multiple alerts for improved performance
- **Configuration Management**: Global and alert-specific configuration merging
- **Status Tracking**: Real-time status updates and progress monitoring
- **Priority Management**: Alert prioritization with configurable priority levels
- **Validation & Filtering**: Confidence-based validation and result filtering
- **In-Memory Registry**: Feed registration and tracking without database dependencies
- **Backward Compatibility**: Support for both new alert combinations and legacy alert sets

## Architecture

### Core Components

1. **FeedManagementPipeline**: Main pipeline class extending AgentPipeline
2. **FeedConfiguration**: Pydantic model for feed structure and settings
3. **AlertCombination**: New array structure for `[alert_request, sql, natural_language_query]` combinations
4. **AlertSet**: Legacy individual alert configuration within a feed
5. **FeedProcessingResult**: Result of processing individual alerts
6. **FeedManagementResult**: Complete feed processing results

### Data Models

#### FeedConfiguration
```python
class FeedConfiguration(BaseModel):
    feed_id: str                    # Unique feed identifier
    feed_name: str                  # Human-readable feed name
    description: Optional[str]      # Feed description
    project_id: str                 # Project identifier
    data_description: Optional[str] # Data description
    alert_sets: List[AlertSet]      # List of alert configurations (legacy)
    alert_combinations: List[AlertCombination] # List of alert combinations [alert_request, sql, natural_language_query]
    global_configuration: Optional[Dict[str, Any]]  # Global settings
    notification_settings: Optional[Dict[str, Any]] # Notification config
    schedule_settings: Optional[Dict[str, Any]]     # Schedule config
    status: FeedStatus              # Current feed status
    priority: FeedPriority          # Overall feed priority
    tags: List[str]                 # Categorization tags
    metadata: Optional[Dict[str, Any]] # Additional metadata
```

#### AlertSet (Legacy)
```python
class AlertSet(BaseModel):
    alert_id: str                   # Unique alert identifier
    alert_name: str                 # Human-readable alert name
    sql_query: str                  # SQL query for the alert
    natural_language_query: str     # Natural language description
    alert_request: str              # Alert requirements description
    configuration: Optional[Dict[str, Any]] # Alert-specific config
    priority: FeedPriority          # Alert priority level
    tags: List[str]                 # Alert categorization tags
```

#### AlertCombination (New Array Structure)
```python
class AlertCombination(BaseModel):
    alert_request: str              # Natural language description of the alert requirements
    sql_query: str                  # SQL query for the alert
    natural_language_query: str     # Natural language description of the query
    alert_id: Optional[str]         # Optional unique identifier for the alert
    alert_name: Optional[str]       # Optional human-readable name for the alert
    configuration: Optional[Dict[str, Any]] # Additional configuration for the alert
    priority: FeedPriority          # Priority level of the alert
    tags: List[str]                 # Tags for categorizing the alert
```

#### FeedProcessingResult
```python
class FeedProcessingResult(BaseModel):
    alert_id: str                   # Alert identifier
    alert_name: str                 # Alert name
    success: bool                   # Processing success status
    feed_configuration: Optional[Dict[str, Any]] # Generated config
    sql_analysis: Optional[Dict[str, Any]]       # SQL analysis
    confidence_score: Optional[float]            # Confidence score
    critique_notes: List[str]       # Critique feedback
    suggestions: List[str]          # Improvement suggestions
    error_message: Optional[str]    # Error details if failed
    processing_time: Optional[float] # Processing duration
    priority: FeedPriority          # Alert priority
```

## Usage Guide

### Basic Usage with Alert Combinations (New Array Structure)

```python
from app.agents.pipelines.writers.feed_management_pipeline import (
    FeedManagementPipeline,
    create_feed_management_pipeline,
    FeedConfiguration,
    AlertCombination,
    FeedPriority,
    FeedStatus
)

# Create pipeline
pipeline = create_feed_management_pipeline(
    engine=engine,
    llm=llm,
    retrieval_helper=retrieval_helper
)

# Define alert combinations - each is [alert_request, sql, natural_language_query]
alert_combinations = [
    AlertCombination(
        alert_request="Alert when training completion rate falls below 90%",
        sql_query="SELECT training_type, COUNT(*) FROM training_records GROUP BY training_type",
        natural_language_query="Show training completion rates by training type",
        alert_id="alert_001",
        alert_name="Training Completion Alert",
        priority=FeedPriority.HIGH,
        tags=["training", "compliance"]
    ),
    AlertCombination(
        alert_request="Alert when expiry rate exceeds 10%",
        sql_query="SELECT department, AVG(expiry_rate) FROM training_metrics GROUP BY department",
        natural_language_query="Show expiry rates by department",
        alert_id="alert_002",
        alert_name="Expiry Rate Alert",
        priority=FeedPriority.MEDIUM,
        tags=["training", "expiry"]
    )
]

# Create feed configuration
feed_config = FeedConfiguration(
    feed_id="training_feed_001",
    feed_name="Training Compliance Feed",
    description="Comprehensive training compliance monitoring",
    project_id="training_project",
    data_description="Training completion and compliance data",
    alert_combinations=alert_combinations,
    global_configuration={
        "confidence_threshold": 0.8,
        "enable_critique": True
    },
    notification_settings={
        "email_addresses": ["admin@company.com"],
        "include_feed_report": True
    },
    priority=FeedPriority.HIGH,
    tags=["training", "compliance", "monitoring"]
)

# Process the feed
result = await pipeline.run(feed_configuration=feed_config)
```

### Legacy Usage with Alert Sets

```python
from app.agents.pipelines.writers.feed_management_pipeline import (
    FeedConfiguration,
    AlertSet,
    FeedPriority
)

# Define alert sets (legacy format)
alert_sets = [
    AlertSet(
        alert_id="alert_001",
        alert_name="Training Completion Alert",
        sql_query="SELECT training_type, COUNT(*) FROM training_records GROUP BY training_type",
        natural_language_query="Show training completion by type",
        alert_request="Alert when completion rate < 90%",
        priority=FeedPriority.HIGH,
        tags=["training", "compliance"]
    )
]

# Create feed configuration with legacy alert sets
feed_config = FeedConfiguration(
    feed_id="training_feed_001",
    feed_name="Training Compliance Feed",
    project_id="training_project",
    alert_sets=alert_sets,  # Legacy format
    priority=FeedPriority.HIGH
)
```

### Advanced Configuration

```python
# Custom pipeline configuration
pipeline.update_configuration({
    "enable_parallel_processing": True,
    "max_concurrent_alerts": 5,
    "default_confidence_threshold": 0.85,
    "enable_validation": True,
    "enable_global_configuration": True
})

# Status callback for monitoring
def status_callback(status: str, details: Dict[str, Any]):
    print(f"Status: {status} - {details}")

# Process with status monitoring
result = await pipeline.run(
    feed_configuration=feed_config,
    status_callback=status_callback
)
```

## Configuration Options

### Pipeline Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_parallel_processing` | bool | True | Enable concurrent alert processing |
| `enable_validation` | bool | True | Enable result validation |
| `enable_metrics` | bool | True | Enable metrics collection |
| `max_concurrent_alerts` | int | 10 | Maximum concurrent alerts |
| `default_confidence_threshold` | float | 0.8 | Confidence threshold for validation |
| `enable_global_configuration` | bool | True | Enable global config merging |
| `enable_notification_aggregation` | bool | True | Enable notification aggregation |

### Feed Status Options

- **PENDING**: Feed is queued for processing
- **ACTIVE**: Feed is actively processing alerts
- **INACTIVE**: Feed processing is disabled
- **PAUSED**: Feed processing is temporarily paused
- **ERROR**: Feed processing encountered errors

### Priority Levels

- **LOW**: Low priority alerts
- **MEDIUM**: Standard priority alerts (default)
- **HIGH**: High priority alerts requiring attention
- **CRITICAL**: Critical alerts requiring immediate action

## Processing Flow

### 1. Feed Registration
- Feed configuration is registered in the in-memory registry
- Initial status is set to PENDING
- Validation of feed structure and alert sets

### 2. Alert Processing
- **Parallel Mode**: Multiple alerts processed concurrently (default)
- **Sequential Mode**: Alerts processed one at a time
- Each alert goes through the SQL-to-Alert generation pipeline
- Individual results are collected and validated

### 3. Result Aggregation
- Successful and failed alerts are categorized
- Combined feed configurations are generated
- Global metadata is compiled
- Priority-based grouping is performed

### 4. Final Output
- Complete feed management result is generated
- Status is updated to ACTIVE (success) or ERROR (failure)
- Metrics are updated and execution statistics are compiled

## Status Callbacks

The pipeline provides real-time status updates through callback functions:

### Status Types

- `feed_processing_started`: Feed processing initiated
- `alert_processing_started`: Individual alert processing started
- `alert_processing_completed`: Individual alert processing completed
- `alert_processing_failed`: Individual alert processing failed
- `feed_processing_completed`: Feed processing completed successfully
- `feed_processing_error`: Feed processing encountered errors

### Callback Example

```python
def status_callback(status: str, details: Dict[str, Any]):
    if status == "feed_processing_started":
        print(f"Starting feed {details['feed_id']} with {details['total_alerts']} alerts")
    elif status == "alert_processing_completed":
        print(f"Alert {details['alert_id']} completed with confidence {details['confidence_score']}")
    elif status == "feed_processing_completed":
        print(f"Feed processing completed: {details['successful_alerts']} successful, {details['failed_alerts']} failed")
```

## Result Structure

### FeedManagementResult

```python
{
    "feed_id": "training_feed_001",
    "feed_name": "Training Compliance Feed", 
    "project_id": "training_project",
    "total_alerts": 2,
    "successful_alerts": 2,
    "failed_alerts": 0,
    "processing_results": [
        {
            "alert_id": "alert_001",
            "alert_name": "Training Completion Alert",
            "success": True,
            "confidence_score": 0.92,
            "processing_time": 2.5,
            "priority": "high"
        }
    ],
    "combined_feed_configurations": {
        "feeds": [...],  # Generated feed configurations
        "summary": {
            "total_feeds": 2,
            "successful_feeds": 2,
            "priority_distribution": {"high": 1, "medium": 1},
            "average_confidence": 0.89
        }
    },
    "global_metadata": {
        "feed_metadata": {...},
        "processing_metadata": {...},
        "alert_metadata": [...]
    },
    "execution_time": 5.2,
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:05Z"
}
```

## Error Handling

### Common Error Scenarios

1. **Invalid Feed Configuration**: Missing required fields or invalid structure
2. **Alert Processing Failures**: Individual alert generation failures
3. **Configuration Conflicts**: Conflicting global and alert-specific settings
4. **Resource Limitations**: Exceeding maximum concurrent alerts

### Error Response Structure

```python
{
    "post_process": {
        "success": False,
        "error": "Error message",
        "error_type": "ConfigurationError",
        "feed_id": "training_feed_001"
    }
}
```

## Performance Considerations

### Parallel Processing
- Default: 10 concurrent alerts
- Configurable via `max_concurrent_alerts`
- Memory usage scales with concurrency level
- Recommended: 5-15 concurrent alerts for optimal performance

### Memory Management
- In-memory feed registry for tracking
- No database persistence (as requested)
- Automatic cleanup of completed feeds
- Configurable retention policies

### Optimization Tips
1. Use appropriate confidence thresholds
2. Enable parallel processing for large feeds
3. Implement proper error handling
4. Monitor memory usage with large alert sets
5. Use status callbacks for progress tracking

## Integration Points

### With Alert Orchestrator Pipeline
- Can be used as a higher-level orchestrator
- Manages multiple alert orchestrator instances
- Provides feed-level coordination

### With Existing Alert Agent
- Integrates with SQLToAlertAgent
- Leverages existing alert generation capabilities
- Maintains compatibility with current alert models

### With Notification Systems
- Supports global notification settings
- Enables feed-level notification aggregation
- Provides alert-specific notification customization

## Best Practices

### Feed Design
1. **Logical Grouping**: Group related alerts in the same feed
2. **Clear Naming**: Use descriptive feed and alert names
3. **Appropriate Priorities**: Set realistic priority levels
4. **Comprehensive Tags**: Use tags for easy categorization

### Configuration Management
1. **Global Settings**: Use global configuration for common settings
2. **Alert-Specific Overrides**: Override global settings when needed
3. **Validation**: Always validate configurations before processing
4. **Documentation**: Document custom configurations

### Monitoring and Maintenance
1. **Status Monitoring**: Implement status callbacks for monitoring
2. **Error Handling**: Implement comprehensive error handling
3. **Metrics Tracking**: Monitor execution statistics
4. **Regular Cleanup**: Clean up completed feeds periodically

## Troubleshooting

### Common Issues

1. **Low Confidence Scores**
   - Review SQL queries for clarity
   - Adjust confidence thresholds
   - Check alert request specificity

2. **Processing Failures**
   - Validate SQL query syntax
   - Check alert configuration completeness
   - Review error messages in processing results

3. **Performance Issues**
   - Reduce concurrent alert count
   - Optimize SQL queries
   - Check system resource availability

4. **Configuration Conflicts**
   - Review global vs alert-specific settings
   - Validate configuration merging logic
   - Check for conflicting parameters

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.getLogger("lexy-ai-service").setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
1. **Feed Templates**: Predefined feed configurations
2. **Conditional Processing**: Dynamic alert processing based on conditions
3. **Feed Dependencies**: Alert dependencies within feeds
4. **Advanced Scheduling**: Complex scheduling configurations
5. **Feed Versioning**: Version control for feed configurations

### Extension Points
1. **Custom Processors**: Plugin architecture for custom alert processors
2. **External Integrations**: Integration with external monitoring systems
3. **Advanced Analytics**: Feed performance analytics and insights
4. **Automated Optimization**: Self-optimizing feed configurations

## Conclusion

The Feed Management Pipeline provides a robust, scalable solution for managing multiple alert sets within a unified feed structure. It offers comprehensive configuration management, parallel processing capabilities, and detailed monitoring without requiring database dependencies. The pipeline is designed to integrate seamlessly with existing alert generation systems while providing advanced orchestration capabilities for complex alert scenarios.
