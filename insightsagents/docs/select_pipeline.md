# SelectPipe Integration with Analysis Intent Classification

This module provides an integrated approach to data analysis that combines **Analysis Intent Classification** with **SelectPipe Code Generation** for intelligent column selection and data preparation.

## Overview

The integration follows this workflow:

1. **Analysis Intent Classification**: Understand what type of analysis the user wants to perform
2. **SelectPipe Generation**: Generate appropriate column selection code based on the analysis intent
3. **Combined Result**: Provide both the data selection code and analysis guidance

## Key Components

### 1. SelfCorrectingSelectPipeGenerator

A self-correcting RAG-based generator that creates SelectPipe code with:
- **Column Selection**: Uses intelligent selectors based on analysis type
- **Column Renaming**: Renames columns for clarity and consistency
- **Column Reordering**: Organizes columns in a logical order
- **Self-Correction**: Iteratively improves code quality through validation

### 2. AnalysisIntentWithSelectPipe

An integration class that orchestrates the complete workflow:
- Runs analysis intent classification first
- Uses classification results to generate SelectPipe code
- Combines results with recommendations and next steps

## Usage

### Basic Usage

```python
from your_module import analyze_intent_and_generate_select_pipe

# Your data and question
question = "Analyze customer retention by region over time"
dataframe_description = "Customer transaction data with demographics"
dataframe_summary = "Contains 50,000 customer records from 2023-2024"
available_columns = [
    "customer_id", "customer_name", "region", "signup_date", 
    "last_purchase_date", "total_purchases", "customer_segment"
]

# Run the integrated analysis
result = await analyze_intent_and_generate_select_pipe(
    question=question,
    dataframe_description=dataframe_description,
    dataframe_summary=dataframe_summary,
    available_columns=available_columns,
    llm=your_llm_instance,
    function_collection=your_function_store,
    example_collection=your_examples_store,
    insights_collection=your_insights_store,
    engine_name="engine",
    table_name="customers"
)
```

### Advanced Usage with Custom Stores

```python
from your_module import AnalysisIntentWithSelectPipe

# Initialize with separate stores for SelectPipe
analyzer = AnalysisIntentWithSelectPipe(
    llm=your_llm,
    # Intent classification stores
    function_collection=intent_function_store,
    example_collection=intent_examples_store,
    insights_collection=intent_insights_store,
    # SelectPipe specific stores
    select_usage_examples_store=select_instructions_store,
    select_code_examples_store=select_code_store,
    select_function_definition_store=select_function_store
)

# Run analysis
result = await analyzer.analyze_and_generate_select_code(
    question="Calculate monthly revenue trends by product category",
    dataframe_description="E-commerce sales data",
    dataframe_summary="Daily sales records for 2023-2024",
    available_columns=your_columns_list,
    project_id="ecommerce_analysis_project"
)
```

## Result Structure

The integration returns a comprehensive result dictionary:

```python
{
    "status": "success",  # success | partial_success | error
    "analysis_summary": {
        "question": "Original user question",
        "can_be_analyzed": True,
        "intent_confidence": 0.92,
        "data_feasibility": 0.85,
        "analysis_complexity": "medium"
    },
    "intent_classification": {
        "intent_type": "time_series_analysis",
        "confidence_score": 0.92,
        "rephrased_question": "Clear, specific question",
        "suggested_functions": ["aggregate_by_time", "trend_analysis"],
        "reasoning_plan": [...]  # Step-by-step analysis plan
    },
    "select_pipe_generation": {
        "status": "success",
        "generated_code": "SelectPipe code string",
        "selection_strategy": "time_series",
        "data_selection_steps": [...],
        "iterations": 1
    },
    "recommendations": [
        "High confidence analysis - proceed with generated approach",
        "Consider additional time-based features for better accuracy"
    ],
    "next_steps": [
        "Execute the generated SelectPipe code to prepare data",
        "Run the analysis pipeline with suggested functions"
    ],
    "combined_code": "# Complete code example with SelectPipe + Analysis"
}
```

## Generated SelectPipe Code Examples

### Basic Column Selection
```python
result = (
    SelectPipe.from_engine(engine, 'customers')
    | Select(
        # Customer identifiers
        cols('customer_id', 'customer_name') |
        # Temporal columns for time series
        temporal() |
        # Business metrics
        numeric() & ~contains('id')
    )
).to_df()
```

### Complex Selection with Renaming and Reordering
```python
result = (
    SelectPipe.from_engine(engine, 'sales_data')
    | Select(
        # Core identifiers
        cols('customer_id', 'order_id') |
        # Order information
        startswith('order') |
        # Product details
        contains('product') |
        # Financial metrics
        contains('amount') | contains('revenue')
    )
    | Rename({
        'order_amount': 'revenue',
        'order_quantity': 'units_sold',
        'customer_segment': 'segment'
    })
    | Reorder(
        'customer_id', 'order_id', 'order_date',
        'product_name', 'revenue', 'units_sold', 'segment'
    )
).to_df()
```

## Selection Strategies

The system uses different selection strategies based on analysis intent:

| Intent Type | Selection Strategy | Focus Areas |
|-------------|-------------------|-------------|
| `time_series_analysis` | TIME_SERIES | Temporal columns, metrics, identifiers |
| `cohort_analysis` | COHORT_ANALYSIS | User IDs, dates, behavioral metrics |
| `segmentation_analysis` | SEGMENTATION | Categorical features, numeric metrics |
| `funnel_analysis` | FUNNEL_ANALYSIS | User IDs, events, timestamps |
| `risk_analysis` | RISK_ANALYSIS | Numeric metrics, risk indicators |
| `anomaly_detection` | ANOMALY_DETECTION | Metrics to analyze, time indicators |
| `metrics_calculation` | METRICS_CALCULATION | Business metrics, grouping dimensions |

## Configuration

### ChromaDB Stores

You need the following ChromaDB stores:

1. **Function Collection**: Contains function definitions for intent classification
2. **Example Collection**: Contains usage examples and instructions
3. **Insights Collection**: Contains function insights and patterns
4. **SelectPipe Stores** (optional, separate):
   - Usage Examples Store: SelectPipe usage instructions
   - Code Examples Store: SelectPipe code examples
   - Function Definition Store: SelectPipe function definitions

### Parameters

- `max_functions_to_retrieve`: Number of functions to retrieve for intent classification (default: 10)
- `max_select_iterations`: Maximum iterations for SelectPipe generation (default: 3)
- `relevance_threshold`: Threshold for document relevance (default: 0.7)

## Integration with Existing Pipeline

This SelectPipe integration is designed to run **before** your existing pipeline generation:

```python
# 1. Run integrated analysis (Intent + SelectPipe)
result = await analyze_intent_and_generate_select_pipe(...)

# 2. Extract SelectPipe code and execute it
select_code = result['select_pipe_generation']['generated_code']
selected_data = execute_select_pipe_code(select_code)

# 3. Use selected data with your existing pipeline generator
pipeline_result = await your_pipeline_generator.generate_pipeline_code(
    context=result['intent_classification']['rephrased_question'],
    function_name=result['intent_classification']['suggested_functions'],
    function_inputs=extracted_inputs,
    dataframe_name="selected_data",  # Use the SelectPipe result
    classification=result['intent_classification']
)
```

## Error Handling

The system provides robust error handling:

- **Syntax Validation**: Generated SelectPipe code is validated for syntax errors
- **Self-Correction**: Multiple iterations with quality grading
- **Fallback Generation**: Basic fallback code when generation fails
- **Graceful Degradation**: Partial results when some components fail

## Best Practices

1. **Column Descriptions**: Provide detailed column descriptions for better selection
2. **Project IDs**: Use project IDs to leverage historical analysis patterns
3. **Store Separation**: Use separate ChromaDB stores for SelectPipe if you have specific examples
4. **Validation**: Always validate generated code before execution
5. **Iteration**: Use the recommendations and next steps for iterative improvement

## Example Complete Workflow

```python
import asyncio
from your_module import AnalysisIntentWithSelectPipe

async def complete_analysis_workflow():
    # Initialize the analyzer
    analyzer = AnalysisIntentWithSelectPipe(
        llm=your_llm,
        function_collection=function_store,
        example_collection=examples_store,
        insights_collection=insights_store
    )
    
    # Define your analysis question and data
    question = "Find anomalies in daily sales by region"
    available_columns = [
        "date", "region", "sales_amount", "units_sold", 
        "customer_count", "avg_order_value", "store_id"
    ]
    
    # Run the integrated analysis
    result = await analyzer.analyze_and_generate_select_code(
        question=question,
        dataframe_description="Daily sales aggregated by region",
        dataframe_summary="2 years of daily sales data across 50 regions",
        available_columns=available_columns,
        engine_name="sales_engine",
        table_name="daily_sales_by_region"
    )
    
    # Check if analysis can proceed
    if result['analysis_summary']['can_be_analyzed']:
        print("✓ Analysis is feasible")
        print(f"Intent: {result['intent_classification']['intent_type']}")
        print(f"Strategy: {result['select_pipe_generation']['selection_strategy']}")
        
        # Execute SelectPipe code (you would implement this)
        # selected_data = execute_code(result['select_pipe_generation']['generated_code'])
        
        # Proceed with main analysis pipeline
        # analysis_result = run_analysis_pipeline(selected_data, result['intent_classification'])
        
    else:
        print("✗ Analysis needs attention")
        for recommendation in result['recommendations']:
            print(f"  - {recommendation}")
    
    return result

# Run the workflow
result = asyncio.run(complete_analysis_workflow())
```

This integration provides a seamless way to combine intelligent column selection with analysis intent classification, ensuring that your data analysis pipelines start with the most relevant data subset for the intended analysis.