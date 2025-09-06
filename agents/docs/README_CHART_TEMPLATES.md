# Chart Template Generation

This document describes the new chart template generation functionality that allows you to create new charts based on existing chart configurations with new data.

## Overview

The chart template generation feature enables you to:
- Use an existing chart as a template to generate new charts with different data
- Automatically map fields between old and new data columns
- Manually specify field mappings for more control
- Validate chart configurations before generation
- Support multiple chart types (Vega-Lite, Plotly, PowerBI)

## Features

### Automatic Field Mapping
The system automatically maps fields between template and new data using multiple strategies:
- **Exact match**: Case-insensitive exact matching
- **Semantic match**: Pattern-based matching using common field types
- **Fuzzy match**: String similarity matching
- **Partial match**: Substring matching as fallback

### Manual Field Mapping
You can provide explicit field mappings for complete control over how fields are mapped between datasets.

### Validation
Comprehensive validation ensures that:
- All required fields are mapped
- Mapped fields exist in the new data
- No duplicate mappings are created
- Chart configurations are structurally valid

### Multi-Format Support
Works with all supported chart types:
- **Vega-Lite**: For web-based visualizations
- **Plotly**: For interactive charts
- **PowerBI**: For business intelligence dashboards

## Usage

### Basic Usage

```python
from app.agents.nodes.sql.chart_generation import VegaLiteChartGenerationPipeline

# Initialize pipeline
pipeline = VegaLiteChartGenerationPipeline()

# Generate new chart from template
new_chart = await pipeline.generate_chart_from_template(
    existing_chart=original_chart,
    new_data=new_data,
    language="English"
)
```

### Advanced Usage with Manual Mapping

```python
# Specify field mapping manually
field_mapping = {
    "Date": "Timestamp",
    "Sales": "Revenue",
    "Region": "Area"
}

new_chart = await pipeline.generate_chart_from_template(
    existing_chart=original_chart,
    new_data=new_data,
    field_mapping=field_mapping,
    language="English"
)
```

### Using Advanced Features

```python
from app.agents.nodes.sql.chart_generation import AdvancedVegaLiteChartGeneration

# Use advanced pipeline for more features
advanced_pipeline = AdvancedVegaLiteChartGeneration()

# Generate chart with suggestions
result = await advanced_pipeline.run_with_suggestions(
    query="Show sales trends",
    sql="SELECT * FROM sales",
    data=sample_data,
    language="English"
)

# Apply predefined template
template_result = await advanced_pipeline.apply_template(
    template_name="sales_trend",
    data=new_data,
    field_mapping={"date": "timestamp", "sales": "revenue"}
)
```

## API Reference

### VegaLiteChartGenerationPipeline

#### `generate_chart_from_template()`

```python
async def generate_chart_from_template(
    self,
    existing_chart: Dict[str, Any],
    new_data: Dict[str, Any],
    field_mapping: Optional[Dict[str, str]] = None,
    language: str = "English"
) -> Dict[str, Any]
```

**Parameters:**
- `existing_chart`: The existing chart configuration to use as template
- `new_data`: New data to visualize using the template
- `field_mapping`: Optional mapping from old field names to new field names
- `language`: Language for chart titles and labels

**Returns:**
- Dictionary containing the new chart configuration with success status, field mapping, and template info

### PlotlyChartGenerationPipeline

#### `generate_chart_from_template()`

```python
async def generate_chart_from_template(
    self,
    existing_chart: Dict[str, Any],
    new_data: Dict[str, Any],
    field_mapping: Optional[Dict[str, str]] = None,
    language: str = "English"
) -> Dict[str, Any]
```

Same interface as Vega-Lite pipeline but generates Plotly chart configurations.

### PowerBIChartGenerationPipeline

#### `generate_chart_from_template()`

```python
async def generate_chart_from_template(
    self,
    existing_chart: Dict[str, Any],
    new_data: Dict[str, Any],
    field_mapping: Optional[Dict[str, str]] = None,
    language: str = "English"
) -> Dict[str, Any]
```

Same interface as other pipelines but generates PowerBI chart configurations.

## Field Mapping Strategies

### Automatic Mapping

The system uses multiple strategies to automatically map fields:

1. **Exact Match**: Case-insensitive exact string matching
2. **Semantic Match**: Pattern-based matching using common field types:
   - Date fields: `date`, `time`, `timestamp`, `created`, `updated`
   - Sales fields: `sales`, `revenue`, `amount`, `value`
   - Region fields: `region`, `area`, `location`, `country`, `state`
   - Product fields: `product`, `item`, `category`, `type`
   - Count fields: `count`, `number`, `quantity`, `total`
   - Profit fields: `profit`, `margin`, `income`, `earnings`

3. **Fuzzy Match**: String similarity using SequenceMatcher
4. **Partial Match**: Substring matching as fallback

### Manual Mapping

You can provide explicit field mappings for complete control:

```python
field_mapping = {
    "old_field_name": "new_field_name",
    "Date": "Timestamp",
    "Sales": "Revenue"
}
```

## Validation

The system validates:
- All template fields are mapped
- Mapped fields exist in new data
- No duplicate mappings
- Chart configuration structure is valid

## Error Handling

The system provides comprehensive error handling:
- Invalid template charts
- Missing field mappings
- Incompatible data structures
- Validation failures

## Examples

### Example 1: Basic Template Generation

```python
# Original chart data
original_data = {
    "columns": ["Date", "Sales", "Region"],
    "data": [
        ["2023-01-01", 100000, "North"],
        ["2023-02-01", 120000, "North"]
    ]
}

# Create original chart
pipeline = VegaLiteChartGenerationPipeline()
original_chart = await pipeline.run(
    query="Show sales by region over time",
    sql="SELECT Date, Sales, Region FROM sales",
    data=original_data,
    language="English"
)

# New data with different column names
new_data = {
    "columns": ["Timestamp", "Revenue", "Area"],
    "data": [
        ["2024-01-01", 150000, "East"],
        ["2024-02-01", 170000, "East"]
    ]
}

# Generate new chart using template
new_chart = await pipeline.generate_chart_from_template(
    existing_chart=original_chart,
    new_data=new_data,
    language="English"
)

print(f"Success: {new_chart['success']}")
print(f"Field mapping: {new_chart['field_mapping']}")
print(f"Chart type: {new_chart['chart_type']}")
```

### Example 2: Manual Field Mapping

```python
# Specify exact field mapping
field_mapping = {
    "Date": "Timestamp",
    "Sales": "Revenue",
    "Region": "Area"
}

new_chart = await pipeline.generate_chart_from_template(
    existing_chart=original_chart,
    new_data=new_data,
    field_mapping=field_mapping,
    language="English"
)
```

### Example 3: Using Advanced Features

```python
from app.agents.nodes.sql.chart_generation import AdvancedVegaLiteChartGeneration

advanced_pipeline = AdvancedVegaLiteChartGeneration()

# Get field mapping suggestions
suggestions = advanced_pipeline.suggest_field_mappings(template_fields, new_columns)

# Apply predefined template
template_result = await advanced_pipeline.apply_template(
    template_name="sales_trend",
    data=new_data,
    field_mapping={"date": "timestamp", "sales": "revenue"}
)
```

## Utility Functions

### ChartTemplateUtils

The `ChartTemplateUtils` class provides utility functions for field mapping and validation:

```python
from app.agents.nodes.sql.utils.chart_template_utils import ChartTemplateUtils

utils = ChartTemplateUtils()

# Create field mapping
mapping = utils.create_field_mapping(template_fields, new_columns)

# Validate mapping
is_valid, errors = utils.validate_field_mapping(mapping, template_fields, new_columns)

# Get suggestions
suggestions = utils.suggest_field_mappings(template_fields, new_columns)

# Create mapping report
report = utils.create_mapping_report(mapping, template_fields, new_columns)
```

## Running Examples

To run the comprehensive examples:

```bash
cd agents/app/agents/nodes/sql
python chart_template_example.py
```

This will demonstrate:
- Vega-Lite chart template generation
- Plotly chart template generation
- PowerBI chart template generation
- Advanced template features
- Field mapping strategies
- Error handling

## Best Practices

1. **Use Automatic Mapping First**: Try automatic field mapping before manual mapping
2. **Validate Results**: Always check the success status and validation results
3. **Handle Errors Gracefully**: Implement proper error handling for edge cases
4. **Test with Sample Data**: Test template generation with sample data before production use
5. **Monitor Field Mappings**: Review field mappings to ensure they make sense for your data

## Troubleshooting

### Common Issues

1. **No Field Mapping Found**: Check if column names are too different from template fields
2. **Validation Failures**: Ensure all required fields are mapped and exist in new data
3. **Incompatible Data**: Verify that new data has compatible structure with template
4. **Missing Fields**: Check that template chart has valid configuration

### Debug Tips

1. Use the mapping report to understand field mappings
2. Check suggestions for alternative field mappings
3. Validate data structure before template generation
4. Review error messages for specific issues

## Future Enhancements

Planned enhancements include:
- Machine learning-based field mapping
- Support for more chart types
- Advanced validation rules
- Template sharing and versioning
- Performance optimizations
