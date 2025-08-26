# Chart Adjustment and Annotation System

This document describes the enhanced chart adjustment system that now supports both chart modifications and annotations.

## Overview

The chart adjustment system has been enhanced to automatically detect and handle three types of requests:

1. **Chart Adjustment**: Modifying chart appearance, type, or encoding
2. **Chart Annotation**: Adding labels, callouts, reference lines, or highlights
3. **Combined**: Both adjustments and annotations

## Key Features

### Automatic Request Classification
The system uses intelligent reasoning to determine whether a user request is for:
- Chart adjustments (colors, types, encoding changes)
- Annotations (labels, callouts, reference lines)
- Both adjustments and annotations

### Annotation Types Supported
- **Text**: Labels, titles, descriptions
- **Line**: Reference lines, thresholds, guides
- **Arrow**: Pointing arrows, directional indicators
- **Highlight**: Color overlays, emphasis areas
- **Callout**: Connected callouts with leader lines
- **Reference**: Reference markers, symbols

### Positioning Options
- Absolute coordinates: `{"x": 100, "y": 200}`
- Data-based positioning: `{"x": "North", "y": 150000}`
- Relative positioning: `{"x": "50%", "y": "top"}`

### Styling Capabilities
- Colors: Named colors, hex codes, RGB values
- Font properties: Size, weight, family
- Visual effects: Opacity, stroke width, fill opacity

## Usage Examples

### Basic Chart Adjustment
```python
from app.agents.nodes.sql.chart_adjustment import ChartAdjustment

chart_adj = ChartAdjustment()
result = await chart_adj.run(
    query="Make the bars blue",
    sql="SELECT category, value FROM table",
    adjustment="Change bar color to blue",
    chart_schema=chart_schema,
    data=data,
    language="English"
)
```

### Adding Annotations
```python
result = await chart_adj.run(
    query="Add value labels on top of each bar",
    sql="SELECT category, value FROM table",
    adjustment="Add value labels",
    chart_schema=chart_schema,
    data=data,
    language="English"
)

# Check if annotations were added
if result.get("annotation_config"):
    annotations = result["annotation_config"]["annotations"]
    print(f"Added {len(annotations)} annotations")
```

### Combined Request
```python
result = await chart_adj.run(
    query="Change bars to green and add a reference line at 1000",
    sql="SELECT category, value FROM table",
    adjustment="Change color and add reference line",
    chart_schema=chart_schema,
    data=data,
    language="English"
)

# Check the type of adjustment
adjustment_type = result.get("adjustment_type")  # "both"
```

## Output Structure

The system returns a structured response with the following fields:

```json
{
    "reasoning": "Explanation of what was done",
    "chart_type": "bar",
    "adjustment_type": "annotation|chart_adjustment|both",
    "chart_schema": {
        // Vega-Lite chart specification
    },
    "annotation_config": {
        "annotations": [
            {
                "annotation_id": "label_1",
                "annotation_type": "text",
                "position": {"x": "North", "y": 150000},
                "content": "$150,000",
                "style": {"color": "black", "fontSize": 12},
                "description": "Value label on top of bar"
            }
        ],
        "annotation_layer": {
            // Optional Vega-Lite layer configuration
        }
    }
}
```

## Backward Compatibility

The enhanced system maintains full backward compatibility:
- All existing chart adjustment functionality works unchanged
- The `adjustment_type` field defaults to "chart_adjustment" for existing code
- Existing interfaces and method signatures remain the same
- New annotation fields are optional and won't break existing implementations

## Integration with Existing Pipelines

The enhanced system integrates seamlessly with existing chart generation pipelines:
- The `ChartAdjustment` class maintains the same interface
- The `create_chart_adjustment_tool` function works with existing LangChain workflows
- Post-processing preserves all existing functionality while adding annotation support

## Error Handling

The system gracefully handles errors:
- Falls back to basic chart adjustment if annotation processing fails
- Provides detailed error messages for debugging
- Maintains the existing error response structure
- Adds `adjustment_type` to error responses for consistency

## Testing

Run the test examples to see the system in action:

```bash
# Test basic functionality
python -m agents.app.agents.nodes.sql.chart_adjustment

# View examples and documentation
python -m agents.app.agents.nodes.sql.chart_adjustment_example
```

## Future Enhancements

Potential future improvements:
- More sophisticated annotation positioning algorithms
- Template-based annotation styles
- Interactive annotation editing
- Annotation persistence and sharing
- Advanced annotation types (heatmaps, trend lines)
