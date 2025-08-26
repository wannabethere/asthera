"""
Example script demonstrating chart adjustment and annotation capabilities.

This script shows how to use the enhanced ChartAdjustment class to:
1. Adjust chart properties (colors, types, encoding)
2. Add annotations (labels, callouts, reference lines)
3. Combine both adjustments and annotations
"""

import asyncio
import json
from typing import Dict, Any

# Example usage of the enhanced ChartAdjustment class
async def demonstrate_annotations():
    """Demonstrate annotation capabilities"""
    
    # Sample chart schema
    sample_chart_schema = {
        "title": "Sales Performance by Region",
        "mark": {"type": "bar"},
        "encoding": {
            "x": {"field": "region", "type": "nominal", "title": "Region"},
            "y": {"field": "sales", "type": "quantitative", "title": "Sales ($)"}
        }
    }
    
    # Sample data
    sample_data = {
        "data": [
            {"region": "North", "sales": 150000},
            {"region": "South", "sales": 200000},
            {"region": "East", "sales": 120000},
            {"region": "West", "sales": 180000}
        ]
    }
    
    print("=== Chart Adjustment and Annotation Examples ===\n")
    
    # Example 1: Pure chart adjustment
    print("1. Chart Adjustment Example:")
    print("   Request: 'Change the bars to blue and make them wider'")
    print("   Expected: Chart schema with blue bars and adjusted width")
    print("   Adjustment Type: chart_adjustment\n")
    
    # Example 2: Pure annotation
    print("2. Annotation Example:")
    print("   Request: 'Add value labels on top of each bar'")
    print("   Expected: Chart schema + annotation_config with text labels")
    print("   Adjustment Type: annotation\n")
    
    # Example 3: Combined request
    print("3. Combined Example:")
    print("   Request: 'Change bars to green and add a reference line at $150k'")
    print("   Expected: Modified chart schema + annotation_config with reference line")
    print("   Adjustment Type: both\n")
    
    # Example 4: Complex annotation
    print("4. Complex Annotation Example:")
    print("   Request: 'Highlight the highest performing region and add a callout'")
    print("   Expected: Chart schema + annotation_config with highlight and callout")
    print("   Adjustment Type: annotation\n")
    
    print("=== Expected Output Structure ===")
    print("""
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
""")

def show_annotation_types():
    """Show available annotation types"""
    print("=== Available Annotation Types ===")
    
    annotation_types = {
        "text": "Text labels, titles, or descriptions",
        "line": "Reference lines, thresholds, or guides",
        "arrow": "Pointing arrows or directional indicators",
        "highlight": "Color overlays or emphasis on specific areas",
        "callout": "Connected callouts with leader lines",
        "reference": "Reference markers or symbols"
    }
    
    for ann_type, description in annotation_types.items():
        print(f"  {ann_type}: {description}")
    
    print("\n=== Annotation Positioning ===")
    print("  - Absolute coordinates: {'x': 100, 'y': 200}")
    print("  - Data-based positioning: {'x': 'North', 'y': 150000}")
    print("  - Relative positioning: {'x': '50%', 'y': 'top'}")
    
    print("\n=== Annotation Styling ===")
    print("  - Colors: 'red', '#FF0000', 'rgb(255,0,0)'")
    print("  - Font properties: fontSize, fontWeight, fontFamily")
    print("  - Visual effects: opacity, strokeWidth, fillOpacity")

if __name__ == "__main__":
    print("Chart Adjustment and Annotation Examples")
    print("=" * 50)
    
    # Show examples
    asyncio.run(demonstrate_annotations())
    
    # Show annotation types
    show_annotation_types()
    
    print("\n=== Usage Notes ===")
    print("1. The system automatically detects whether a request is for:")
    print("   - Chart adjustment (colors, types, encoding)")
    print("   - Annotation (labels, callouts, reference lines)")
    print("   - Both (combined adjustments and annotations)")
    print("\n2. Annotation configurations are returned in the 'annotation_config' field")
    print("3. The 'adjustment_type' field indicates the classification")
    print("4. All existing chart adjustment functionality is preserved")
    print("5. Annotations can be applied to any chart type")
