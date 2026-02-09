import asyncio
import logging
import os
from typing import Any, Dict, Literal, Optional, List

import orjson
# Import Tool using modern LangChain paths
try:
    from langchain_core.tools import Tool
except ImportError:
    try:
        from langchain.tools import Tool
    except ImportError:
        from langchain.agents import Tool
# Import PromptTemplate using modern LangChain paths
try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate

# Import RunnablePassthrough using modern LangChain paths
try:
    from langchain_core.runnables import RunnablePassthrough
except ImportError:
    try:
        from langchain.schema.runnable import RunnablePassthrough
    except ImportError:
        RunnablePassthrough = None
from langfuse.decorators import observe
from pydantic import BaseModel, Field

from app.core.dependencies import get_llm
from app.agents.nodes.sql.utils.plotly_chart import (
    PlotlyChartDataPreprocessor,
    PlotlyChartGenerationPostProcessor,
    plotly_chart_generation_instructions,
    PlotlyChartGenerationResults
)
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()


# Plotly Chart Adjustment Option Model
class PlotlyChartAdjustmentOption(BaseModel):
    chart_type: Literal[
        "scatter", "line", "bar", "horizontal_bar", "pie", "histogram", 
        "box", "heatmap", "area", "violin", "bubble", "sunburst", 
        "treemap", "waterfall", "funnel"
    ]
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    z_axis: Optional[str] = None  # For 3D plots and heatmaps
    color: Optional[str] = None
    size: Optional[str] = None  # For scatter/bubble plots
    labels: Optional[str] = None  # For pie charts
    values: Optional[str] = None  # For pie charts
    text: Optional[str] = None
    hover_data: Optional[List[str]] = None
    facet_col: Optional[str] = None  # For subplot creation
    facet_row: Optional[str] = None
    animation_frame: Optional[str] = None  # For animated plots
    color_scale: Optional[str] = None
    title: Optional[str] = None
    template: Optional[str] = None  # Plotly theme


plotly_chart_adjustment_system_prompt = """
### TASK ###

You are a data analyst expert at visualizing data using Plotly! Given the user's question, SQL, sample data, sample column values, original Plotly chart configuration and adjustment options, 
you need to re-generate Plotly chart configuration in JSON and provide suitable chart type.
Besides, you need to give a concise and easy-to-understand reasoning to describe why you provide such Plotly chart configuration based on the question, SQL, sample data, sample column values, original chart configuration and adjustment options.

{plotly_chart_generation_instructions}
- If you think the adjustment options are not suitable for the data, you can return an empty string for the config and chart type and give reasoning to explain why.

### OUTPUT FORMAT ###

Please provide your chain of thought reasoning, chart type and the Plotly chart configuration in JSON format.

{{
    "reasoning": <REASON_TO_CHOOSE_THE_CONFIGURATION_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>,
    "chart_type": "scatter" | "line" | "bar" | "horizontal_bar" | "pie" | "histogram" | "box" | "heatmap" | "area" | "violin" | "bubble" | "sunburst" | "treemap" | "waterfall" | "funnel" | "",
    "chart_config": <PLOTLY_CHART_JSON_CONFIGURATION>
}}
"""

plotly_chart_adjustment_user_prompt_template = """
### INPUT ###
Original Question: {query}
Original SQL: {sql}
Original Plotly Chart Configuration: {chart_config}
Sample Data: {sample_data}
Sample Column Values: {sample_column_values}
Language: {language}

Adjustment Options:
- Chart Type: {chart_type}
{conditional_x_axis}
{conditional_y_axis}
{conditional_z_axis}
{conditional_color}
{conditional_size}
{conditional_labels}
{conditional_values}
{conditional_text}
{conditional_hover_data}
{conditional_facet_col}
{conditional_facet_row}
{conditional_animation_frame}
{conditional_color_scale}
{conditional_title}
{conditional_template}

Please think step by step and adjust the chart configuration based on the provided options.
"""


class PlotlyChartAdjustmentTool:
    """Langchain tool for Plotly chart adjustment"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "plotly_chart_adjustment"
        self.description = "Adjusts Plotly chart configurations based on user feedback"
        
        # Import here to avoid circular dependency
        self.chart_data_preprocessor = PlotlyChartDataPreprocessor()
        self.post_processor = PlotlyChartGenerationPostProcessor()
        
        # Update system prompt with instructions
        self.system_prompt = plotly_chart_adjustment_system_prompt.format(
            plotly_chart_generation_instructions=plotly_chart_generation_instructions
        )

    @observe(capture_input=False)
    def preprocess_data(self, data: Dict[str, Any]) -> dict:
        """Preprocess chart data"""
        return self.chart_data_preprocessor.run(data)

    @observe(as_type="generation", capture_input=False) 
    async def generate_chart_adjustment(self, prompt_input: str) -> dict:
        """Generate chart adjustment using LLM"""
        try:
            # Create the prompt template
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Create chain using pipe operator
            chain = (
                {"system_prompt": lambda x: self.system_prompt, "user_prompt": lambda x: x}
                | full_prompt
                | self.llm
            )
            
            # Generate response
            result = await chain.ainvoke(prompt_input)
            
            # Ensure the result is a properly formatted JSON string
            try:
                # First try to parse the raw result
                parsed_result = orjson.loads(result)
                return {"replies": [orjson.dumps(parsed_result).decode('utf-8')]}
            except orjson.JSONDecodeError:
                # If parsing fails, try to extract JSON from the text
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        # Validate the extracted JSON
                        parsed_result = orjson.loads(json_str)
                        return {"replies": [orjson.dumps(parsed_result).decode('utf-8')]}
                    except orjson.JSONDecodeError:
                        pass
                
                # If all parsing attempts fail, return a default structure
                default_result = {
                    "reasoning": "Failed to parse LLM response into valid JSON format.",
                    "chart_type": "",
                    "chart_schema": {}
                }
                return {"replies": [orjson.dumps(default_result).decode('utf-8')]}
                
        except Exception as e:
            logger.error(f"Error in chart adjustment generation: {e}")
            default_result = {
                "reasoning": f"Error in chart adjustment generation: {str(e)}",
                "chart_type": "",
                "chart_schema": {}
            }
            return {"replies": [orjson.dumps(default_result).decode('utf-8')]}

    @observe(capture_input=False)
    def post_process(
        self, 
        generate_result: dict, 
        sample_data: dict
    ) -> dict:
        """Post-process chart adjustment results"""
        return self.post_processor.run(
            generate_result.get("replies"),
            sample_data,
        )

    async def run(
        self,
        query: str,
        sql: str,
        adjustment_option: PlotlyChartAdjustmentOption,
        chart_config: dict,
        data: dict,
        language: str,
    ) -> dict:
        """Main execution method for chart adjustment"""
        try:
            logger.info("Plotly Chart Adjustment pipeline is running...")
            
            # Step 1: Preprocess data
            preprocess_result = self.preprocess_data(data)
            sample_data = preprocess_result.get("sample_data")
            sample_column_values = preprocess_result.get("sample_column_values")
            
            # Step 2: Create prompt
            prompt_template = PromptTemplate(
                input_variables=[
                    "query", "sql", "chart_config", "sample_data", 
                    "sample_column_values", "language", "chart_type",
                    "conditional_x_axis", "conditional_y_axis", "conditional_z_axis",
                    "conditional_color", "conditional_size", "conditional_labels",
                    "conditional_values", "conditional_text", "conditional_hover_data",
                    "conditional_facet_col", "conditional_facet_row", 
                    "conditional_animation_frame", "conditional_color_scale",
                    "conditional_title", "conditional_template"
                ],
                template=plotly_chart_adjustment_user_prompt_template
            )
            
            # Prepare conditional fields based on chart type and provided options
            conditional_fields = {}
            
            # Basic fields applicable to most chart types
            conditional_fields["conditional_x_axis"] = f"- X Axis: {adjustment_option.x_axis}" if adjustment_option.x_axis else ""
            conditional_fields["conditional_y_axis"] = f"- Y Axis: {adjustment_option.y_axis}" if adjustment_option.y_axis else ""
            conditional_fields["conditional_color"] = f"- Color: {adjustment_option.color}" if adjustment_option.color else ""
            conditional_fields["conditional_title"] = f"- Title: {adjustment_option.title}" if adjustment_option.title else ""
            conditional_fields["conditional_template"] = f"- Template: {adjustment_option.template}" if adjustment_option.template else ""
            
            # Chart type specific fields
            if adjustment_option.chart_type in ["scatter", "bubble"]:
                conditional_fields["conditional_size"] = f"- Size: {adjustment_option.size}" if adjustment_option.size else ""
            else:
                conditional_fields["conditional_size"] = ""
            
            if adjustment_option.chart_type == "pie":
                conditional_fields["conditional_labels"] = f"- Labels: {adjustment_option.labels}" if adjustment_option.labels else ""
                conditional_fields["conditional_values"] = f"- Values: {adjustment_option.values}" if adjustment_option.values else ""
            else:
                conditional_fields["conditional_labels"] = ""
                conditional_fields["conditional_values"] = ""
            
            if adjustment_option.chart_type in ["heatmap", "surface"]:
                conditional_fields["conditional_z_axis"] = f"- Z Axis: {adjustment_option.z_axis}" if adjustment_option.z_axis else ""
            else:
                conditional_fields["conditional_z_axis"] = ""
            
            # Advanced options
            conditional_fields["conditional_text"] = f"- Text: {adjustment_option.text}" if adjustment_option.text else ""
            conditional_fields["conditional_hover_data"] = f"- Hover Data: {', '.join(adjustment_option.hover_data)}" if adjustment_option.hover_data else ""
            conditional_fields["conditional_facet_col"] = f"- Facet Column: {adjustment_option.facet_col}" if adjustment_option.facet_col else ""
            conditional_fields["conditional_facet_row"] = f"- Facet Row: {adjustment_option.facet_row}" if adjustment_option.facet_row else ""
            conditional_fields["conditional_animation_frame"] = f"- Animation Frame: {adjustment_option.animation_frame}" if adjustment_option.animation_frame else ""
            conditional_fields["conditional_color_scale"] = f"- Color Scale: {adjustment_option.color_scale}" if adjustment_option.color_scale else ""
            
            user_prompt = prompt_template.format(
                query=query,
                sql=sql,
                chart_config=chart_config,
                sample_data=sample_data,
                sample_column_values=sample_column_values,
                language=language,
                chart_type=adjustment_option.chart_type,
                **conditional_fields
            )
            
            # Step 3: Generate chart adjustment
            generate_result = await self.generate_chart_adjustment(user_prompt)
            
            # Step 4: Post-process results
            final_result = self.post_process(
                generate_result,
                sample_data
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in chart adjustment: {e}")
            return {
                "error": str(e),
                "success": False
            }


class PlotlyChartAdjustment:
    """Main PlotlyChartAdjustment class maintaining original interface"""
    
    def __init__(self, llm_provider=None, **kwargs):
        self.tool = PlotlyChartAdjustmentTool(get_llm() if llm_provider is None else llm_provider)

    @observe(name="Plotly Chart Adjustment")
    async def run(
        self,
        query: str,
        sql: str,
        adjustment_option: PlotlyChartAdjustmentOption,
        chart_config: dict,
        data: dict,
        language: str,
    ) -> dict:
        """Run chart adjustment with original interface"""
        return await self.tool.run(
            query=query,
            sql=sql,
            adjustment_option=adjustment_option,
            chart_config=chart_config,
            data=data,
            language=language
        )


def create_plotly_chart_adjustment_tool(llm_provider=None) -> Tool:
    """Create Langchain tool for Plotly chart adjustment"""
    chart_adj = PlotlyChartAdjustmentTool(get_llm() if llm_provider is None else llm_provider)
    
    def adjust_chart_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(chart_adj.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="plotly_chart_adjuster",
        description="Adjusts Plotly chart visualizations based on user preferences. Input should be JSON with 'query', 'sql', 'adjustment_option', 'chart_config', 'data', and 'language' fields.",
        func=adjust_chart_func
    )


# Helper functions for common adjustments
class PlotlyChartAdjustmentHelper:
    """Helper class for common Plotly chart adjustments"""
    
    @staticmethod
    def change_chart_type(chart_config: dict, new_type: str) -> dict:
        """Change the chart type while preserving compatible settings"""
        adjusted_config = chart_config.copy()
        
        if "data" in adjusted_config:
            for trace in adjusted_config["data"]:
                trace["type"] = new_type
                
                # Adjust trace properties based on new type
                if new_type == "scatter":
                    trace["mode"] = trace.get("mode", "markers")
                elif new_type == "line":
                    trace["mode"] = "lines+markers"
                elif new_type == "bar":
                    trace.pop("mode", None)
                elif new_type == "pie":
                    # Convert x,y to labels,values for pie charts
                    if "x" in trace and "y" in trace:
                        trace["labels"] = trace.pop("x")
                        trace["values"] = trace.pop("y")
                    trace.pop("mode", None)
        
        adjusted_config["chart_type"] = new_type
        return adjusted_config
    
    @staticmethod
    def update_axes(chart_config: dict, x_field: str = None, y_field: str = None) -> dict:
        """Update axis field mappings"""
        adjusted_config = chart_config.copy()
        
        if "data" in adjusted_config:
            for trace in adjusted_config["data"]:
                if x_field:
                    trace["x"] = x_field
                if y_field:
                    trace["y"] = y_field
        
        return adjusted_config
    
    @staticmethod
    def update_styling(chart_config: dict, 
                      color_scale: str = None,
                      template: str = None,
                      title: str = None) -> dict:
        """Update chart styling options"""
        adjusted_config = chart_config.copy()
        
        # Update traces
        if "data" in adjusted_config and color_scale:
            for trace in adjusted_config["data"]:
                if "marker" in trace:
                    trace["marker"]["colorscale"] = color_scale
                else:
                    trace["colorscale"] = color_scale
        
        # Update layout
        if "layout" not in adjusted_config:
            adjusted_config["layout"] = {}
        
        if template:
            adjusted_config["layout"]["template"] = template
        
        if title:
            adjusted_config["layout"]["title"] = title
        
        return adjusted_config
    
    @staticmethod
    def add_faceting(chart_config: dict, 
                    facet_col: str = None, 
                    facet_row: str = None) -> dict:
        """Add subplot faceting to the chart"""
        adjusted_config = chart_config.copy()
        
        # This would typically require restructuring the data
        # For now, just add the facet information to metadata
        if "metadata" not in adjusted_config:
            adjusted_config["metadata"] = {}
        
        if facet_col:
            adjusted_config["metadata"]["facet_col"] = facet_col
        if facet_row:
            adjusted_config["metadata"]["facet_row"] = facet_row
        
        return adjusted_config


PLOTLY_CHART_ADJUSTMENT_MODEL_KWARGS = {
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "plotly_chart_adjustment_results",
            "schema": PlotlyChartGenerationResults.model_json_schema(),
        },
    }
}


if __name__ == "__main__":
    # Test the Plotly chart adjustment tool
    async def test_plotly_chart_adjustment():
        chart_adj = PlotlyChartAdjustment()
        
        # Create a proper PlotlyChartAdjustmentOption with required fields
        adjustment_option = PlotlyChartAdjustmentOption(
            chart_type="scatter",  # Required field
            x_axis="sales",
            y_axis="profit",
            color="region",
            size="market_size"
        )
        
        # Sample chart configuration
        sample_chart_config = {
            "chart_type": "bar",
            "data": [
                {
                    "type": "bar",
                    "x": "category",
                    "y": "value",
                    "marker": {"color": "lightblue"},
                    "name": "Sample Bar Chart"
                }
            ],
            "layout": {
                "title": "Sample Bar Chart",
                "xaxis": {"title": "Category"},
                "yaxis": {"title": "Value"},
                "showlegend": False
            }
        }
        
        # Sample data with proper structure
        sample_data = {
            "data": [
                {"sales": 100000, "profit": 25000, "region": "North", "market_size": 1000},
                {"sales": 150000, "profit": 30000, "region": "South", "market_size": 1200},
                {"sales": 120000, "profit": 20000, "region": "East", "market_size": 800},
                {"sales": 180000, "profit": 35000, "region": "West", "market_size": 1500}
            ],
            "columns": {
                "sales": [100000, 150000, 120000, 180000],
                "profit": [25000, 30000, 20000, 35000],
                "region": ["North", "South", "East", "West"],
                "market_size": [1000, 1200, 800, 1500]
            }
        }
        
        result = await chart_adj.run(
            query="Show me the relationship between sales and profit with region as color and market size as bubble size",
            sql="SELECT sales, profit, region, market_size FROM table",
            adjustment_option=adjustment_option,
            chart_config=sample_chart_config,
            data=sample_data,
            language="English"
        )
        
        print("Plotly Chart Adjustment Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
        
        # Test helper functions
        helper = PlotlyChartAdjustmentHelper()
        
        # Test chart type change
        changed_config = helper.change_chart_type(sample_chart_config, "scatter")
        print("\nChart Type Changed to Scatter:")
        print(orjson.dumps(changed_config, option=orjson.OPT_INDENT_2).decode())
        
        # Test styling update
        styled_config = helper.update_styling(
            sample_chart_config, 
            color_scale="viridis", 
            template="plotly_dark",
            title="Updated Chart Title"
        )
        print("\nStyling Updated:")
        print(orjson.dumps(styled_config, option=orjson.OPT_INDENT_2).decode())

    asyncio.run(test_plotly_chart_adjustment())

__all__ = ["PlotlyChartAdjustment", "PlotlyChartAdjustmentOption", "create_plotly_chart_adjustment_tool", "PlotlyChartAdjustmentHelper"]