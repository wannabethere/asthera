# Enhanced Chart Generation System

## Overview

The Enhanced Chart Generation System extends the existing Vega-Lite chart generation capabilities to support additional chart types beyond the baseline templates. This system provides intelligent chart selection, enhanced data analysis, and robust error handling for creating sophisticated data visualizations.

## Key Features

### Extended Chart Types
- **Scatter Charts**: Show relationships between two continuous variables
- **Heatmaps**: Display correlation or density between two variables
- **Boxplots**: Show distribution and outliers across categories
- **Histograms**: Display distribution of continuous variables
- **Bubble Charts**: Show relationships between three variables with size encoding
- **Text Charts**: Display text labels with positioning
- **Tick Charts**: Show distribution of values with simple frequency plots
- **Rule Charts**: Draw reference lines and thresholds

### Enhanced Capabilities
- **Intelligent Chart Selection**: Automatic selection of the most appropriate chart type based on data structure
- **Data Analysis**: Comprehensive analysis of data types and structure
- **Alternative Suggestions**: Provide alternative chart types for the same data
- **Enhanced Metadata**: Rich metadata about chart selection reasoning
- **Template-Based Generation**: Support for template-based chart generation
- **Robust Error Handling**: Comprehensive error handling and validation

## Architecture

### Core Components

1. **EnhancedChartDataPreprocessor**
   - Analyzes data structure and types
   - Suggests appropriate chart types
   - Provides data analysis metadata

2. **EnhancedChartGenerationPostProcessor**
   - Fixes common Vega-Lite schema errors
   - Validates chart schemas
   - Optimizes configurations for enhanced chart types

3. **EnhancedVegaLiteChartGenerationAgent**
   - Main agent for chart generation
   - Uses enhanced instructions and examples
   - Supports reasoning and alternative options

4. **EnhancedVegaLiteChartGenerationPipeline**
   - Orchestrates the entire chart generation process
   - Provides high-level interface for chart generation
   - Supports multiple export formats

### File Structure

```
genieml/agents/app/agents/nodes/sql/
├── utils/
│   ├── enhanced_chart_generation.py      # Enhanced utilities and instructions
│   └── chart_models.py                   # Pydantic models for chart types
├── enhanced_chart_generation.py          # Main enhanced chart generation agent
├── test_enhanced_chart_generation.py     # Test script with examples
└── README_enhanced_chart_generation.md   # This documentation
```

## Usage Examples

### Basic Chart Generation

```python
from app.agents.nodes.sql.enhanced_chart_generation import generate_enhanced_chart

# Generate a scatter chart
result = await generate_enhanced_chart(
    query="Show the relationship between sales and profit by region",
    sql="SELECT Sales, Profit, Region FROM sales_data",
    data={
        "columns": ["Sales", "Profit", "Region"],
        "data": [
            {"Sales": 100000, "Profit": 25000, "Region": "North"},
            {"Sales": 150000, "Profit": 30000, "Region": "South"}
        ]
    },
    language="English",
    include_reasoning=True
)

print(f"Chart Type: {result['chart_type']}")
print(f"Reasoning: {result['reasoning']}")
print(f"Chart Schema: {result['chart_schema']}")
```

### Using the Pipeline

```python
from app.agents.nodes.sql.enhanced_chart_generation import EnhancedVegaLiteChartGenerationPipeline

# Create pipeline
pipeline = EnhancedVegaLiteChartGenerationPipeline()

# Generate chart
result = await pipeline.run(
    query="Show sales intensity across months and regions",
    sql="SELECT Month, Region, Sales FROM sales_data",
    data=data,
    language="English",
    remove_data_from_chart_schema=True
)
```

### Template-Based Generation

```python
from app.agents.nodes.sql.enhanced_chart_generation import generate_chart_with_template

# Generate chart using template
result = await generate_chart_with_template(
    query="Create a time series chart showing sales trends",
    sql="SELECT Date, Sales FROM sales_data ORDER BY Date",
    data=data,
    template_name="time_series",
    language="English"
)
```

## Chart Type Guidelines

### Scatter Chart
- **Use When**: Showing relationship between two continuous variables
- **Data Requirements**: Two quantitative variables (x, y)
- **Optional**: Color encoding for categorical data, size encoding for third variable
- **Example**: Sales vs. profit by region

### Heatmap
- **Use When**: Showing correlation or density between two variables
- **Data Requirements**: Two categorical/temporal variables (x, y) and one quantitative (color)
- **Example**: Sales by month and region

### Boxplot
- **Use When**: Showing distribution and outliers across categories
- **Data Requirements**: One quantitative variable (y) and optional categorical (x)
- **Example**: Sales distribution by region

### Histogram
- **Use When**: Showing distribution of a continuous variable
- **Data Requirements**: One quantitative variable (x) with binning and count aggregation (y)
- **Example**: Sales amount distribution

### Bubble Chart
- **Use When**: Showing relationship between three variables
- **Data Requirements**: Three quantitative variables (x, y, size)
- **Optional**: Color encoding for categorical data
- **Example**: Sales vs. profit vs. market size by region

### Text Chart
- **Use When**: Displaying text labels with positioning
- **Data Requirements**: Text field and positioning variables (x, y)
- **Example**: Product names positioned by sales and profit

### Tick Chart
- **Use When**: Showing distribution of values
- **Data Requirements**: One quantitative variable (x or y)
- **Example**: Distribution of customer ratings

### Rule Chart
- **Use When**: Drawing reference lines or thresholds
- **Data Requirements**: Positioning variable (x or y)
- **Example**: Sales thresholds by category

## Configuration

### Enhanced Chart Generation Settings

```python
# Enhanced chart generation configuration
enhanced_config = {
    "include_reasoning": True,           # Include detailed reasoning
    "include_alternatives": True,        # Suggest alternative charts
    "enhanced_metadata": True,           # Include enhanced metadata
    "template_based": False,             # Use template-based generation
    "data_analysis": True,               # Perform data analysis
    "validation": True,                  # Validate chart schemas
    "error_handling": "strict"           # Error handling mode
}
```

### Vega-Lite Schema Configuration

```python
# Load custom Vega-Lite schema
with open("path/to/vega-lite-schema.json", "r") as f:
    vega_schema = json.load(f)

pipeline = EnhancedVegaLiteChartGenerationPipeline(vega_schema=vega_schema)
```

## Testing

### Running Tests

```bash
# Run the test script
python genieml/agents/app/agents/nodes/sql/test_enhanced_chart_generation.py
```

### Test Coverage

The test script covers:
- All enhanced chart types (scatter, heatmap, boxplot, histogram, bubble, text, tick, rule)
- Pipeline functionality
- Template-based generation
- Error handling
- Data analysis capabilities

### Example Test Output

```
==================================================
TESTING SCATTER CHART
==================================================
Chart Type: scatter
Reasoning: A scatter chart is chosen to show the relationship between sales and profit across different regions
Success: True
Data Analysis: Two quantitative variables (Sales, Profit) and one categorical variable (Region)
Alternative Charts: ['bubble', 'line', 'bar']
Chart Selection Reasoning: Scatter chart best shows correlation between continuous variables
Chart Schema:
{
  "title": "Sales vs Profit by Region",
  "mark": {"type": "circle"},
  "encoding": {
    "x": {"field": "Sales", "type": "quantitative", "title": "Sales"},
    "y": {"field": "Profit", "type": "quantitative", "title": "Profit"},
    "color": {"field": "Region", "type": "nominal", "title": "Region"}
  }
}
```

## Integration

### With Existing Chart Generation System

The enhanced system is designed to work alongside the existing chart generation system:

```python
# Use enhanced system for complex charts
if complex_chart_needed:
    result = await generate_enhanced_chart(query, sql, data)
else:
    # Use existing system for basic charts
    result = await generate_basic_chart(query, sql, data)
```

### With Pipeline Container

```python
from app.agents.pipelines.pipeline_container import PipelineContainer

# Get pipeline container
container = PipelineContainer.get_instance()

# Use enhanced chart generation
result = await container.get_pipeline("enhanced_chart_generation").run(
    query=query,
    sql=sql,
    data=data
)
```

## Performance Considerations

### Optimization Strategies

1. **Data Sampling**: Uses sample data for schema generation to improve performance
2. **Caching**: Implements caching for frequently used chart schemas
3. **Lazy Loading**: Loads Vega-Lite schema only when needed
4. **Parallel Processing**: Supports parallel chart generation for multiple datasets

### Memory Usage

- **Data Preprocessing**: Processes only sample data for analysis
- **Schema Validation**: Validates schemas without loading full datasets
- **Garbage Collection**: Proper cleanup of temporary objects

## Error Handling

### Common Errors and Solutions

1. **Invalid Chart Type**
   - Error: Chart type not supported
   - Solution: Use supported chart types or fallback to basic types

2. **Data Type Mismatch**
   - Error: Data types don't match chart requirements
   - Solution: Automatic data type conversion or chart type suggestion

3. **Schema Validation Error**
   - Error: Vega-Lite schema validation fails
   - Solution: Automatic schema fixing and validation

4. **Missing Data**
   - Error: Insufficient data for visualization
   - Solution: Return empty chart with appropriate reasoning

### Error Recovery

```python
try:
    result = await generate_enhanced_chart(query, sql, data)
except ChartGenerationError as e:
    # Fallback to basic chart generation
    result = await generate_basic_chart(query, sql, data)
except ValidationError as e:
    # Fix schema and retry
    result = await fix_and_retry_chart_generation(query, sql, data, e)
```

## Future Enhancements

### Planned Features

1. **3D Charts**: Support for 3D scatter plots and surface plots
2. **Interactive Charts**: Enhanced interactivity and animations
3. **Custom Templates**: User-defined chart templates
4. **Machine Learning Integration**: ML-based chart type selection
5. **Real-time Updates**: Support for real-time data visualization

### Extension Points

1. **Custom Chart Types**: Framework for adding new chart types
2. **Custom Validators**: User-defined validation rules
3. **Custom Exporters**: Additional export formats
4. **Custom Preprocessors**: User-defined data preprocessing

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all dependencies are installed
   - Check import paths in your environment

2. **Schema Validation Failures**
   - Verify Vega-Lite schema version compatibility
   - Check data types match chart requirements

3. **Performance Issues**
   - Reduce sample data size
   - Enable caching for repeated operations
   - Use appropriate chart types for data size

4. **Memory Issues**
   - Process data in chunks
   - Clear cache periodically
   - Use lazy loading for large datasets

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Generate chart with debug information
result = await generate_enhanced_chart(
    query, sql, data,
    debug=True  # Enable debug mode
)
```

## Contributing

### Adding New Chart Types

1. **Update Chart Models**: Add new chart type to `chart_models.py`
2. **Update Instructions**: Add instructions to `enhanced_chart_generation_instructions`
3. **Add Examples**: Include examples in the instructions
4. **Update Preprocessor**: Add data type detection for new chart types
5. **Update Postprocessor**: Add error fixing for new chart types
6. **Add Tests**: Include test cases for new chart type

### Code Style

- Follow PEP 8 guidelines
- Include type hints
- Add comprehensive docstrings
- Write unit tests for new features

### Testing

- Run existing tests: `python -m pytest tests/`
- Add new tests for new features
- Ensure test coverage for error cases

## License

This enhanced chart generation system is part of the GenieML project and follows the same licensing terms.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the test examples
3. Check the existing chart generation documentation
4. Create an issue with detailed error information 