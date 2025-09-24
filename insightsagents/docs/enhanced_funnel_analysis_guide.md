# Enhanced Funnel Analysis Tool Guide

This guide explains how to use the enhanced funnel analysis tool with pipeline flow integration, separate step codes, and clean visual representations.

## Overview

The enhanced funnel analysis tool provides:
- **Separate Step Code Generation**: Each step generates individual, executable code
- **Flow Graph Visualization**: Clean visual representation of the pipeline flow
- **Comprehensive Analysis**: Execution analysis, dependency analysis, and optimization recommendations
- **Single File Output**: All flow information consolidated into comprehensive Python files

## Key Features

### 🔧 Pipeline Flow Integration
- Uses the new `PipelineFlowIntegrationAgent` for complete pipeline generation
- Generates separate code for each step with unique input/output dataframes
- Creates comprehensive flow graphs with nodes, edges, and metadata

### 🎨 Visual Representations
- **Flow Graph Visualization**: Clean PNG images showing the pipeline structure
- **Color-coded Nodes**: Different colors for different pipeline types
- **Edge Types**: Different styles for data flow, dependencies, and other relationships
- **Metadata Display**: Execution order, complexity scores, and optimization opportunities

### 📄 Comprehensive Files
- **Individual Step Functions**: Each step as a separate Python function
- **Combined Pipeline**: Complete pipeline execution function
- **Parallel Execution**: Support for parallel execution where possible
- **Metadata Integration**: All analysis results embedded in the code

## Usage

### Basic Usage

```python
from insightsagents.tests.mlagents.funnelanalysistoolusage_enhanced import analyze_question_with_pipeline_flow

# Analyze a question with pipeline flow
result = analyze_question_with_pipeline_flow(
    question="How does the 5-day rolling variance of flux change over time?",
    dataframe=your_dataframe,
    dataframe_description="Your dataset description",
    dataframe_summary="Your dataset summary",
    columns_description=your_columns_description,
    context="Additional context for analysis",
    dataframe_name="Your Dataset"
)
```

### Running the Enhanced Tool

```bash
# Run the enhanced funnel analysis tool
python insightsagents/tests/mlagents/funnelanalysistoolusage_enhanced.py
```

### Running the Demo

```bash
# Run the demonstration
python insightsagents/examples/enhanced_funnel_analysis_demo.py
```

## Output Files

### 1. Flow Graph Visualizations
- **Location**: `analysis_results/flow_visualizations/`
- **Format**: PNG images
- **Content**: Visual representation of the pipeline flow
- **Features**: Color-coded nodes, different edge types, metadata display

### 2. Comprehensive Flow Files
- **Location**: `analysis_results/`
- **Format**: Python files (e.g., `analysis_name_comprehensive_flow.py`)
- **Content**: Complete pipeline with all steps, metadata, and execution functions
- **Features**: Individual step functions, combined pipeline, parallel execution support

### 3. JSON Results
- **Location**: `analysis_results/`
- **Format**: JSON files
- **Content**: Complete analysis results with metadata
- **Features**: Intent classification, pipeline flow results, integration metadata

## File Structure

```
analysis_results/
├── enhanced_funnel_analysis_results_20240101_120000.json
├── flow_visualizations/
│   ├── rolling_variance_analysis_flow_graph_20240101_120000.png
│   ├── anomaly_detection_flow_graph_20240101_120000.png
│   └── ...
├── rolling_variance_analysis_comprehensive_flow_20240101_120000.py
├── anomaly_detection_comprehensive_flow_20240101_120000.py
└── ...
```

## Comprehensive Flow File Contents

Each comprehensive flow file contains:

### 1. Header and Imports
```python
"""
Comprehensive Pipeline Flow Analysis
Analysis: rolling_variance_analysis
Generated: 2024-01-01 12:00:00
Status: success
"""

# Required imports
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Pipeline imports
from app.tools.mltools import (
    # All necessary pipeline imports
)
```

### 2. Flow Graph Metadata
```python
# Flow Graph Metadata
TOTAL_NODES = 3
TOTAL_EDGES = 2
PIPELINE_TYPES = ['MetricsPipe', 'TimeSeriesPipe']
FUNCTIONS_USED = ['variance', 'moving_apply_by_group']
CAN_PARALLELIZE = False
HAS_CONDITIONAL_LOGIC = False
```

### 3. Execution Analysis
```python
# Execution Analysis
EXECUTION_ORDER = ['step_1', 'step_2', 'step_3']
CRITICAL_PATH = ['step_1', 'step_2', 'step_3']
PARALLEL_OPPORTUNITIES = []
TOTAL_EXECUTION_STEPS = 3
```

### 4. Individual Step Functions
```python
def step_1_variance(df):
    """
    Step 1: Calculate Basic Variance
    Function: variance
    Pipeline Type: MetricsPipe
    Input: df -> Output: step_1_result
    Dependencies: []
    """
    try:
        # Generated code here
        return step_1_result
    except Exception as e:
        print(f"Error in step 1: {e}")
        return None
```

### 5. Combined Pipeline Function
```python
def run_combined_pipeline(df):
    """Execute the complete pipeline with all steps"""
    try:
        result = df.copy()
        
        # Step 1: Calculate Basic Variance
        result = step_1_variance(result)
        if result is None:
            print("Pipeline failed at step 1")
            return None
        
        # Step 2: Apply Moving Variance by Group
        result = step_2_moving_apply_by_group(result)
        if result is None:
            print("Pipeline failed at step 2")
            return None
        
        return result
    except Exception as e:
        print(f"Error running combined pipeline: {e}")
        return None
```

### 6. Parallel Execution Support
```python
def run_parallel_pipeline(df):
    """Execute independent steps in parallel where possible"""
    # Implementation for parallel execution
    pass
```

### 7. Main Execution Block
```python
if __name__ == "__main__":
    # Load your data here
    # df = pd.read_csv("your_data.csv")
    
    print("🚀 Running Pipeline Flow Analysis...")
    print(f"Total Steps: {len(step_codes)}")
    print(f"Pipeline Types: {PIPELINE_TYPES}")
    print(f"Can Parallelize: {CAN_PARALLELIZE}")
    
    # Run individual steps
    for i in range(1, len(step_codes) + 1):
        print(f"\n🔧 Executing Step {i}...")
        # result = step_i_function(df)
    
    # Run combined pipeline
    print("\n🔄 Running Combined Pipeline...")
    # final_result = run_combined_pipeline(df)
    
    print("\n✅ Pipeline execution complete!")
```

## Configuration

### Output Configuration
```python
OUTPUT_CONFIG = {
    "save_to_json": True,                    # Save results to JSON files
    "save_individual_files": True,           # Save individual analysis files
    "output_directory": "analysis_results",   # Directory to save files
    "include_timestamp": True,               # Include timestamp in filenames
    "create_summary": True,                  # Create summary text file
    "console_output": True,                  # Also show results in console
    "file_encoding": "utf-8",               # File encoding for output files
    "extract_generated_code": True,          # Extract generated code to Python files
    "code_output_directory": "generated_code", # Directory for generated Python code
    "create_flow_visualization": True,       # Create flow graph visualization
    "visualization_output_directory": "flow_visualizations" # Directory for flow visualizations
}
```

## Benefits

### For Developers
- **Modularity**: Each step is independently executable and testable
- **Debugging**: Easier to debug individual steps
- **Maintenance**: Easier to modify or replace individual steps
- **Testing**: Can test individual steps in isolation

### For Users
- **Transparency**: Clear understanding of pipeline structure and data flow
- **Visualization**: Visual representation of the pipeline flow
- **Optimization**: Identified opportunities for performance improvement
- **Analysis**: Comprehensive analysis of pipeline characteristics

### For System
- **Scalability**: Better handling of complex pipelines
- **Parallelization**: Opportunities for parallel execution
- **Resource Management**: Better understanding of resource requirements
- **Monitoring**: Enhanced monitoring and debugging capabilities

## Examples

### Example 1: Rolling Variance Analysis
```python
result = analyze_question_with_pipeline_flow(
    question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
    dataframe=po_df,
    dataframe_description="Financial flux data with project, cost center, and department information",
    dataframe_summary="Dataset contains flux values over time with grouping dimensions",
    columns_description=columns_description,
    context="Analyze the flux values over time for each group of projects, cost centers, and departments for making better decisions of investment",
    dataframe_name="Purchase Orders Data"
)
```

### Example 2: Anomaly Detection
```python
result = analyze_question_with_pipeline_flow(
    question="Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns week by week by region and project",
    dataframe=po_df,
    dataframe_description="Financial flux data with project, cost center, and department information",
    dataframe_summary="Dataset contains flux values over time with grouping dimensions",
    columns_description=columns_description,
    context="Find anomalies in daily spending patterns",
    dataframe_name="Purchase Orders Data"
)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure all required modules are installed
2. **Data Format Issues**: Ensure your dataframe has the expected columns
3. **Memory Issues**: For large datasets, consider processing in chunks
4. **Visualization Issues**: Ensure matplotlib and networkx are installed

### Debug Mode

Enable debug mode by setting environment variables:
```bash
export DEBUG=1
export LOG_LEVEL=DEBUG
```

## Advanced Usage

### Custom Pipeline Types
You can extend the system to support custom pipeline types by modifying the `PipelineType` enum and adding corresponding visualization colors.

### Custom Visualization
You can customize the flow graph visualization by modifying the `create_flow_visualization` function in the enhanced tool.

### Integration with Other Tools
The comprehensive flow files can be easily integrated with other data analysis tools and workflows.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the example files
3. Check the generated comprehensive flow files for detailed error information
4. Enable debug mode for detailed logging
