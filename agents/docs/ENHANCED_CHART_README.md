# Enhanced Chart Generation System

## Overview

The Enhanced Chart Generation System extends the existing Vega-Lite chart generation capabilities to support additional chart types and provide more intelligent chart selection based on data analysis and user queries.

## Key Features

### 🎯 **Extended Chart Types**
- **Basic Charts**: Bar, Line, Area, Pie, Grouped Bar, Stacked Bar, Multi Line
- **Advanced Charts**: Scatter, Heatmap, Box Plot, Histogram, Bubble, Text, Tick, Rule
- **Total Support**: 15+ chart types using Vega-Lite mark types

### 🧠 **Intelligent Chart Selection**
- **Data Analysis**: Automatic column type detection (temporal, quantitative, nominal)
- **Query Analysis**: Keyword-based chart type suggestions
- **Template Matching**: Predefined analysis templates for common use cases

### 🔧 **Enhanced Processing**
- **Advanced Preprocessing**: Column analysis, data shape detection, chart type suggestions
- **Smart Post-processing**: Automatic schema fixing, validation, and optimization
- **Error Handling**: Robust error handling with detailed logging

### 📊 **Analysis Templates**
- **Correlation Analysis**: For relationship visualization
- **Distribution Analysis**: For statistical distributions
- **Statistical Comparison**: For outlier and distribution analysis
- **Density Visualization**: For heatmaps and matrices
- **Multi-dimensional Analysis**: For 3-variable relationships
- **Time Series Analysis**: For temporal data
- **Composition Analysis**: For part-to-whole relationships

## Architecture

### Core Components

1. **EnhancedChartDataPreprocessor**
   - Analyzes data structure and column types
   - Suggests appropriate chart types
   - Provides enhanced metadata

2. **EnhancedChartGenerationPostProcessor**
   - Fixes common Vega-Lite configuration errors
   - Validates schemas against Vega-Lite specification
   - Optimizes chart configurations

3. **EnhancedVegaLiteChartGenerationAgent**
   - Main chart generation agent
   - Uses enhanced prompts and instructions
   - Supports multiple chart types

4. **EnhancedChartGenerationPipeline**
   - Orchestrates the chart generation process
   - Provides template-based generation
   - Offers analysis suggestions

5. **EnhancedChartGenerationWithReasoning**
   - Generates detailed reasoning for chart choices
   - Provides alternative chart options
   - Explains chart selection logic

## Usage Examples

### Basic Chart Generation

```python
from agents.app.agents.nodes.sql.enhanced_chart_generation import generate_enhanced_chart

# Generate a chart with reasoning
result = await generate_enhanced_chart(
    query="Show the relationship between sales and profit by region",
    sql="SELECT Sales, Profit, Region FROM sales_data",
    data={
        "columns": ["Sales", "Profit", "Region"],
        "data": [
            [100000, 25000, "North"],
            [150000, 30000, "South"],
            [120000, 20000, "East"]
        ]
    },
    language="English",
    include_reasoning=True
)

print(f"Chart type: {result['primary_chart']['chart_type']}")
print(f"Reasoning: {result['reasoning']}")
```

### Template-Based Generation

```python
from agents.app.agents.nodes.sql.enhanced_chart_generation import generate_chart_with_template

# Generate using a specific template
result = await generate_chart_with_template(
    query="Analyze sales data",
    sql="SELECT Sales, Profit FROM sales_data",
    data=data,
    template_name="correlation_analysis",
    language="English"
)
```

### Direct Schema Creation

```python
from agents.app.agents.nodes.sql.utils.enhanced_chart import create_enhanced_chart_from_existing_schema

# Create chart from existing schema
result = create_enhanced_chart_from_existing_schema(
    chart_schema={
        "mark": {"type": "circle"},
        "encoding": {
            "x": {"field": "Sales", "type": "quantitative"},
            "y": {"field": "Profit", "type": "quantitative"}
        }
    },
    data=data,
    language="English"
)
```

## Chart Type Guidelines

### When to Use Each Chart Type

| Chart Type | Use Case | Data Requirements | Example |
|------------|----------|-------------------|---------|
| **Bar** | Compare categories | 1 categorical + 1 quantitative | Sales by region |
| **Line** | Show trends over time | 1 temporal + 1 quantitative | Revenue over months |
| **Scatter** | Show correlation | 2 quantitative | Sales vs profit |
| **Heatmap** | Show density/correlation | 2 categorical + 1 quantitative | Sales by month/region |
| **Box Plot** | Show distribution | 1 quantitative + 1 categorical (optional) | Salary by department |
| **Histogram** | Show frequency distribution | 1 quantitative | Age distribution |
| **Bubble** | Show 3-variable relationship | 2 quantitative + 1 quantitative (size) | Sales vs profit vs market size |
| **Pie** | Show proportions | 1 categorical + 1 quantitative | Market share |
| **Area** | Show volume over time | 1 temporal + 1 quantitative | Cumulative sales |
| **Grouped Bar** | Compare sub-categories | 2 categorical + 1 quantitative | Sales by product/region |
| **Stacked Bar** | Show composition | 2 categorical + 1 quantitative | Sales breakdown by type |

### Vega-Lite Mark Types

The system supports all Vega-Lite mark types:
- `bar` - Bar charts
- `line` - Line charts
- `area` - Area charts
- `arc` - Pie charts
- `point` / `circle` - Scatter plots
- `rect` - Heatmaps
- `boxplot` - Box plots
- `text` - Text plots
- `tick` - Tick plots
- `rule` - Rule plots

## Configuration

### Enhanced Instructions

The system uses enhanced chart generation instructions that include:
- Detailed chart type selection guidelines
- Vega-Lite specific configuration rules
- Data transformation guidelines
- Comprehensive examples for each chart type

### Schema Validation

All generated charts are validated against the Vega-Lite v5 schema to ensure:
- Proper mark type usage
- Correct encoding configurations
- Valid data transformations
- Appropriate field mappings

### Error Handling

The system includes robust error handling:
- Graceful degradation when schema validation fails
- Detailed error logging
- Fallback chart types
- Data preprocessing error recovery

## Testing

Run the test suite to verify functionality:

```bash
python test_enhanced_chart_generation.py
```

The test suite includes:
- Chart type generation tests
- Template-based generation tests
- Schema fixing tests
- Error handling tests

## Integration

### With Existing Systems

The enhanced system is designed to work alongside existing chart generation:
- Compatible with current chart generation APIs
- Extends existing functionality without breaking changes
- Provides enhanced metadata for better integration

### API Compatibility

```python
# Existing API still works
from agents.app.agents.nodes.sql.chart_generation import VegaLiteChartGenerationAgent

# Enhanced API provides additional features
from agents.app.agents.nodes.sql.enhanced_chart_generation import EnhancedVegaLiteChartGenerationAgent
```

## Performance Considerations

### Optimization Features
- **Caching**: Chart suggestions and analysis results
- **Lazy Loading**: Schema validation only when needed
- **Efficient Processing**: Optimized data preprocessing
- **Memory Management**: Proper cleanup of large schemas

### Scalability
- **Async Support**: All operations are async-compatible
- **Batch Processing**: Support for multiple chart generation
- **Resource Management**: Efficient use of system resources

## Future Enhancements

### Planned Features
- **Interactive Charts**: Support for interactive Vega-Lite features
- **Custom Templates**: User-defined chart templates
- **Advanced Analytics**: Integration with statistical analysis
- **Real-time Updates**: Support for streaming data visualization

### Extensibility
- **Plugin System**: Easy addition of new chart types
- **Custom Mark Types**: Support for custom Vega-Lite marks
- **Template Marketplace**: Community-driven template sharing

## Troubleshooting

### Common Issues

1. **Schema Validation Errors**
   - Check field names match data columns
   - Verify data types are correct
   - Ensure required encodings are present

2. **Chart Type Selection Issues**
   - Review data structure analysis
   - Check query keywords
   - Verify template requirements

3. **Performance Issues**
   - Monitor data size and preprocessing time
   - Check schema complexity
   - Review caching configuration

### Debug Mode

Enable debug logging for detailed information:

```python
import logging
logging.getLogger("lexy-ai-service").setLevel(logging.DEBUG)
```

## Contributing

### Adding New Chart Types

1. Update `chart_models.py` with new schema definitions
2. Add chart type to `enhanced_chart_generation_instructions`
3. Update post-processor with specific fixes
4. Add test cases to test suite

### Adding New Templates

1. Define template in `EnhancedChartGenerationPipeline._load_enhanced_chart_templates()`
2. Add template-specific logic
3. Update documentation
4. Add test cases

## License

This enhanced chart generation system is part of the GenieML project and follows the same licensing terms. 