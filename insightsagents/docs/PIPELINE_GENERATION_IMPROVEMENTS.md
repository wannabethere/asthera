# Pipeline Generation Improvements

## Overview

The self-correcting pipeline generator has been updated to properly group functions by pipeline type and chain them together, instead of creating separate pipeline steps for each function.

## Problem

Previously, the generator was creating separate pipeline steps like this:

```python
# Step 1: Data Selection
result = (
    MetricsPipe.from_dataframe(financial_data)
    | select_strings()
    ).to_df()

# Step 2: Aggregate Daily Transaction Amounts
result = (
    TrendPipe.from_dataframe(result)
    | aggregate_by_time(date_column='Date', metric_columns=['Transactional value'], time_period='D', aggregation='sum')
    ).to_df()

# Step 3: Calculate Growth Rates
result = (
    TrendPipe.from_dataframe(result)
    | calculate_growth_rates(window=None, annualize=False, method='percentage')
    ).to_df()

# Step 4: Calculate Moving Averages
result = (
    TrendPipe.from_dataframe(result)
    | calculate_moving_average(window=7, method='simple')
    ).to_df()
```

This approach:
- Creates unnecessary intermediate DataFrames
- Is less efficient
- Doesn't follow the intended pipeline chaining pattern

## Solution

The updated generator now groups functions by pipeline type and chains them together within each pipeline type, but keeps different pipeline types separate:

```python
# Step 1: Data Selection
result = (
    MetricsPipe.from_dataframe(financial_data)
    | select_strings()
    ).to_df()

# Step 2: Aggregate Daily Transaction Amounts
# Step 3: Calculate Growth Rates
# Step 4: Calculate Moving Averages
result = (
    TrendPipe.from_dataframe(financial_data)
    | aggregate_by_time(date_column='Date', metric_columns=['Transactional value'], time_period='D', aggregation='sum')
    | calculate_growth_rates(window=None, annualize=False, method='percentage')
    | calculate_moving_average(window=7, method='simple')
    ).to_df()
```

**Key Points:**
- Each pipeline type gets its own `result = ...` statement
- Functions within the same pipeline type are chained together
- Different pipeline types remain separate (no chaining between MetricsPipe and TrendPipe)
- **First pipeline** uses the original dataframe (`financial_data`)
- **Subsequent pipelines** use `result` from the previous pipeline

## Key Changes

### 1. Dynamic Pipeline Type Detection

The system now uses the `FunctionRetrieval` system to dynamically determine pipeline types instead of hardcoded mappings:

- **FunctionRetrieval**: Primary source for function-to-pipeline mapping
- **ChromaDB Store**: Fallback for function definitions
- **Context Analysis**: Last resort for pipeline type detection
- **No Hardcoded Mappings**: All function mappings are determined dynamically

### 2. Pipeline Grouping

Functions are now grouped by their dynamically detected pipeline type (e.g., `MetricsPipe`, `TrendPipe`, `TimeSeriesPipe`):

```python
pipeline_groups = {}  # Group steps by pipeline type

for step in reasoning_plan:
    pipeline_type = await self._detect_pipeline_type(function_name, step_title)
    pipeline_type_key = pipeline_type.value
    
    if pipeline_type_key not in pipeline_groups:
        pipeline_groups[pipeline_type_key] = {
            "pipeline_type": pipeline_type,
            "steps": [],
            "dataframe": current_dataframe
        }
    
    # Add step to the appropriate pipeline group
    pipeline_groups[pipeline_type_key]["steps"].append({
        "function": function_name,
        "params": param_str,
        "title": step_title,
        "step_num": i+1
    })
```

### 2. Chained Pipeline Generation

For each pipeline group, functions are chained together:

```python
for group_key, group_info in pipeline_groups.items():
    pipeline_type = group_info["pipeline_type"]
    steps = group_info["steps"]
    dataframe = group_info["dataframe"]
    
    if len(steps) == 1:
        # Single step - simple pipeline
        step_code = f"""# {step['title']}
result = (
    {pipeline_type.value}.from_dataframe({dataframe})
    | {step['function']}({step['params']})
    ).to_df()"""
    else:
        # Multiple steps - chained pipeline
        step_comments = []
        step_chain = []
        
        for step in steps:
            step_comments.append(f"# {step['title']}")
            step_chain.append(f"    | {step['function']}({step['params']})")
        
        # Join all steps into a single chained pipeline
        step_code = f"""{chr(10).join(step_comments)}
result = (
    {pipeline_type.value}.from_dataframe({dataframe})
{chr(10).join(step_chain)}
    ).to_df()"""
```

## Benefits

1. **Efficiency**: Functions from the same pipeline type are executed in a single chain
2. **Readability**: Code is cleaner and easier to understand
3. **Performance**: Fewer intermediate DataFrame operations
4. **Maintainability**: Easier to modify and extend pipeline logic

## Example Output

### Before (Separate Steps)
```python
# Step 1: Data Selection
result = (
    MetricsPipe.from_dataframe(financial_data)
    | select_strings()
    ).to_df()

# Step 2: Aggregate Daily Transaction Amounts
result = (
    TrendPipe.from_dataframe(result)
    | aggregate_by_time(date_column='Date', metric_columns=['Transactional value'], time_period='D', aggregation='sum')
    ).to_df()

# Step 3: Calculate Growth Rates
result = (
    TrendPipe.from_dataframe(result)
    | calculate_growth_rates(window=None, annualize=False, method='percentage')
    ).to_df()

# Step 4: Calculate Moving Averages
result = (
    TrendPipe.from_dataframe(result)
    | calculate_moving_average(window=7, method='simple')
    ).to_df()
```

### After (Grouped by Pipeline Type)
```python
# Step 1: Data Selection
result = (
    MetricsPipe.from_dataframe(financial_data)
    | select_strings()
    ).to_df()

# Step 2: Aggregate Daily Transaction Amounts
# Step 3: Calculate Growth Rates
# Step 4: Calculate Moving Averages
result = (
    TrendPipe.from_dataframe(financial_data)
    | aggregate_by_time(date_column='Date', metric_columns=['Transactional value'], time_period='D', aggregation='sum')
    | calculate_growth_rates(window=None, annualize=False, method='percentage')
    | calculate_moving_average(window=7, method='simple')
    ).to_df()
```

**Note**: Each pipeline type gets its own `result` statement, and functions within the same pipeline type are chained together. The first pipeline uses the original dataframe, and subsequent pipelines use the result from previous pipelines.

## Testing

A test script has been created at `insightsagents/tests/mlagents/test_pipeline_generation.py` to verify that:

1. Functions are properly grouped by pipeline type
2. Chained pipelines are generated correctly
3. The output matches the expected format

Run the test with:
```bash
cd insightsagents/tests/mlagents
python test_pipeline_generation.py
```

## Dynamic Function Detection

The system now uses a completely dynamic approach:

1. **FunctionRetrieval System**: Queries the ChromaDB function library to find function definitions
2. **Automatic Pipeline Mapping**: Maps functions to pipeline types based on their actual definitions
3. **No Hardcoded Rules**: All function mappings are determined at runtime
4. **LLM-Powered Analysis**: Uses the reasoning plan and context to determine appropriate functions

## Future Enhancements

1. **Smart DataFrame Passing**: Automatically pass results between different pipeline types
2. **Enhanced Function Discovery**: Improve function discovery using semantic search
3. **Error Handling**: Better error handling for invalid pipeline combinations
4. **Performance Optimization**: Further optimize the pipeline execution order
5. **Dynamic Tool Selection**: Automatically determine which tools to use based on function definitions
