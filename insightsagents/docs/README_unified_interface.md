# Unified Interface for ML Tools

This document describes the unified interface that all ML tools pipe classes now share through the `BasePipe` abstract base class.

## Overview

All pipe classes in the ML tools module now inherit from `BasePipe`, providing a consistent interface across different analysis types. This ensures:

- **Consistent API**: All pipes have the same core methods
- **Type Safety**: All pipes are instances of `BasePipe`
- **Easy Extension**: New pipe types can easily implement the interface
- **Unified Error Handling**: Common error patterns across all pipes

## Pipe Classes

The following pipe classes now implement the unified interface:

1. **AnomalyPipe** - Anomaly detection and outlier analysis
2. **MetricsPipe** - Basic statistical metrics and aggregations
3. **CohortPipe** - Cohort analysis and retention calculations
4. **MovingAggrPipe** - Moving averages and rolling aggregations
5. **OperationsPipe** - A/B testing and experimental analysis
6. **RiskPipe** - Risk analysis and financial metrics
7. **SegmentationPipe** - Customer segmentation and clustering
8. **TimeSeriesPipe** - Time series analysis and transformations
9. **TrendPipe** - Trend analysis and forecasting
10. **FunnelPipe** - Funnel analysis and conversion tracking

## Unified Interface Methods

All pipe classes implement the following methods from `BasePipe`:

### Core Methods

#### `from_dataframe(df: pd.DataFrame) -> BasePipe`
Create a pipe instance from a pandas DataFrame.

```python
pipe = AnomalyPipe.from_dataframe(df)
```

#### `has_data() -> bool`
Check if the pipe has data loaded.

```python
if pipe.has_data():
    print("Pipe has data")
```

#### `get_data() -> Optional[pd.DataFrame]`
Get the current data in the pipe.

```python
data = pipe.get_data()
```

#### `set_data(data: pd.DataFrame)`
Set the data for the pipe.

```python
pipe.set_data(new_data)
```

#### `get_data_info() -> Dict[str, Any]`
Get information about the current data.

```python
info = pipe.get_data_info()
# Returns: {"has_data": True, "shape": (100, 5), "columns": [...], ...}
```

#### `copy() -> BasePipe`
Create a copy of the pipe with its data and results.

```python
copied_pipe = pipe.copy()
```

### Analysis Methods

#### `to_df(**kwargs) -> pd.DataFrame`
Convert analysis results to a DataFrame. Parameters vary by pipe type.

```python
# AnomalyPipe
results_df = pipe.to_df(include_metadata=True, include_original=True)

# MetricsPipe
results_df = pipe.to_df(include_metadata=False, include_pivot_tables=True)
```

#### `get_summary(**kwargs) -> Dict[str, Any]`
Get a summary of the analysis results. Returns a dictionary with analysis information.

```python
summary = pipe.get_summary()
# Returns: {"analysis_name": "...", "total_analyses": 3, ...}
```

## Usage Examples

### Basic Usage Pattern

```python
import pandas as pd
from anomalydetection import AnomalyPipe, detect_statistical_outliers
from metrics_tools import MetricsPipe, Sum, Mean

# Create data
df = pd.DataFrame({
    'value': [1, 2, 3, 100, 4, 5],  # 100 is an outlier
    'date': pd.date_range('2023-01-01', periods=6)
})

# Anomaly detection with unified interface
anomaly_pipe = AnomalyPipe.from_dataframe(df)
print(f"Has data: {anomaly_pipe.has_data()}")
print(f"Data shape: {anomaly_pipe.get_data_info()['shape']}")

# Run analysis
anomaly_pipe = anomaly_pipe | detect_statistical_outliers('value', 'zscore', 2.0)

# Get results
results = anomaly_pipe.to_df()
summary = anomaly_pipe.get_summary()
print(f"Found {summary['summary_dataframe'][0]['anomaly_count']} anomalies")
```

### Metrics Analysis

```python
# Metrics analysis with unified interface
metrics_pipe = MetricsPipe.from_dataframe(df)
print(f"Pipe type: {type(metrics_pipe).__name__}")
print(f"Is BasePipe: {isinstance(metrics_pipe, BasePipe)}")

# Calculate metrics
metrics_pipe = (metrics_pipe 
               | Sum('value') 
               | Mean('value'))

# Get summary
summary = metrics_pipe.get_summary()
print(f"Calculated {summary['total_metrics']} metrics")
print(f"Metrics: {list(summary['metrics_values'].keys())}")
```

### Working with Multiple Pipe Types

```python
# All pipes share the same interface
pipes = [
    AnomalyPipe.from_dataframe(df),
    MetricsPipe.from_dataframe(df),
    CohortPipe.from_dataframe(df),
    MovingAggrPipe.from_dataframe(df)
]

# Common operations work on all pipes
for pipe in pipes:
    print(f"{type(pipe).__name__}:")
    print(f"  Has data: {pipe.has_data()}")
    print(f"  Data shape: {pipe.get_data_info()['shape']}")
    print(f"  Is BasePipe: {isinstance(pipe, BasePipe)}")
```

## Benefits of Unified Interface

### 1. Consistent API
All pipes follow the same patterns for data loading, analysis, and result retrieval.

### 2. Type Safety
All pipes inherit from `BasePipe`, enabling type checking and IDE support.

### 3. Easy Extension
New pipe types can be created by implementing the required abstract methods:

```python
class CustomPipe(BasePipe):
    def _initialize_results(self):
        self.custom_results = {}
    
    def _copy_results(self, source_pipe):
        if hasattr(source_pipe, 'custom_results'):
            self.custom_results = source_pipe.custom_results.copy()
    
    def to_df(self, **kwargs):
        # Implementation specific to this pipe type
        pass
    
    def get_summary(self, **kwargs):
        # Implementation specific to this pipe type
        pass
```

### 4. Unified Error Handling
Common error patterns are handled consistently across all pipes.

### 5. Consistent Documentation
All pipes have similar documentation patterns and usage examples.

## Migration Guide

If you have existing code using the old pipe classes, the migration is straightforward:

### Before (Old Interface)
```python
pipe = AnomalyPipe(data=df)
pipe.data  # Direct access to data
pipe.copy()  # Custom copy method
```

### After (Unified Interface)
```python
pipe = AnomalyPipe.from_dataframe(df)
pipe.get_data()  # Method to get data
pipe.copy()  # Standardized copy method
pipe.has_data()  # Check if data exists
pipe.get_data_info()  # Get data information
```

The core functionality remains the same, but now you have access to additional standardized methods and better type safety.

## Testing the Unified Interface

Run the demonstration script to see the unified interface in action:

```python
from unified_interface_demo import demonstrate_unified_interface
demonstrate_unified_interface()
```

This will test all pipe classes and verify that they implement the unified interface correctly. 