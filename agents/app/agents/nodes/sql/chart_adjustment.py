import asyncio
import logging
import os
from typing import Any, Dict, Literal, Optional

import orjson
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema.runnable import RunnablePassthrough
from langfuse.decorators import observe

from app.core.dependencies import get_llm
from app.agents.nodes.sql.utils.chart_models import ChartAdjustmentOption,ChartGenerationResults
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()

# Get the absolute path to the schema file
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "utils", "vega-lite-schema-v5.json")

# Move the chart_generation_instructions import inside the class where it's used
chart_adjustment_system_prompt = """
### TASK ###

You are a data analyst great at visualizing data using vega-lite! Given the user's question, SQL, sample data, sample column values, original vega-lite schema and adjustment options, 
you need to re-generate vega-lite schema in JSON and provide suitable chart type.
Besides, you need to give a concise and easy-to-understand reasoning to describe why you provide such vega-lite schema based on the question, SQL, sample data, sample column values, original vega-lite schema and adjustment options.

{chart_generation_instructions}
- If you think the adjustment options are not suitable for the data, you can return an empty string for the schema and chart type and give reasoning to explain why.

### OUTPUT FORMAT ###

Please provide your chain of thought reasoning, chart type and the vega-lite schema in JSON format.

{{
    "reasoning": <REASON_TO_CHOOSE_THE_SCHEMA_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>,
    "chart_type": "line" | "multi_line" | "bar" | "pie" | "grouped_bar" | "stacked_bar" | "area" | "",
    "chart_schema": <VEGA_LITE_JSON_SCHEMA>
}}
"""

chart_adjustment_user_prompt_template = """
### INPUT ###
Original Question: {query}
Original SQL: {sql}
Original Vega-Lite Schema: {chart_schema}
Sample Data: {sample_data}
Sample Column Values: {sample_column_values}
Language: {language}

Adjustment Options:
- Chart Type: {chart_type}
{conditional_x_axis}
{conditional_y_axis}
{conditional_x_offset}
{conditional_color}
{conditional_theta}

Please think step by step
"""


class ChartAdjustmentTool:
    """Langchain tool for chart adjustment"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "chart_adjustment"
        self.description = "Adjusts chart configurations based on user feedback"
        
        # Load Vega-Lite schema
        try:
            with open(SCHEMA_PATH, "r") as f:
                self.vega_schema = orjson.loads(f.read())
        except Exception as e:
            logger.error(f"Error loading Vega-Lite schema: {e}")
            raise RuntimeError(f"Failed to load Vega-Lite schema from {SCHEMA_PATH}: {str(e)}")
        
        # Import here to avoid circular dependency
        from app.agents.nodes.sql.utils.chart import (
            ChartDataPreprocessor,
            ChartGenerationPostProcessor,
            chart_generation_instructions
        )
        self.chart_data_preprocessor = ChartDataPreprocessor()
        self.post_processor = ChartGenerationPostProcessor()
        
        # Update system prompt with instructions
        self.system_prompt = chart_adjustment_system_prompt.format(
            chart_generation_instructions=chart_generation_instructions
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
            
            # Create LLM chain
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            # Generate response
            result = await chain.arun(
                system_prompt=self.system_prompt,
                user_prompt=prompt_input
            )
            
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
        vega_schema: Dict[str, Any], 
        sample_data: dict
    ) -> dict:
        """Post-process chart adjustment results"""
        return self.post_processor.run(
            generate_result.get("replies"),
            vega_schema,
            sample_data,
        )

    async def run(
        self,
        query: str,
        sql: str,
        adjustment_option: ChartAdjustmentOption,
        chart_schema: dict,
        data: dict,
        language: str,
    ) -> dict:
        """Main execution method for chart adjustment"""
        try:
            logger.info("Chart Adjustment pipeline is running...")
            
            # Step 1: Preprocess data
            preprocess_result = self.preprocess_data(data)
            sample_data = preprocess_result.get("sample_data")
            sample_column_values = preprocess_result.get("sample_column_values")
            
            # Step 2: Create prompt
            prompt_template = PromptTemplate(
                input_variables=[
                    "query", "sql", "chart_schema", "sample_data", 
                    "sample_column_values", "language", "chart_type",
                    "conditional_x_axis", "conditional_y_axis",
                    "conditional_x_offset", "conditional_color",
                    "conditional_theta"
                ],
                template=chart_adjustment_user_prompt_template
            )
            
            # Prepare conditional fields
            conditional_x_axis = f"- X Axis: {adjustment_option.x_axis}" if adjustment_option.x_axis and adjustment_option.chart_type != "pie" else ""
            conditional_y_axis = f"- Y Axis: {adjustment_option.y_axis}" if adjustment_option.y_axis and adjustment_option.chart_type != "pie" else ""
            conditional_x_offset = f"- X Offset: {adjustment_option.x_offset}" if adjustment_option.x_offset and adjustment_option.chart_type == "grouped_bar" else ""
            conditional_color = f"- Color: {adjustment_option.color}" if adjustment_option.color and adjustment_option.chart_type != "area" else ""
            conditional_theta = f"- Theta: {adjustment_option.theta}" if adjustment_option.theta and adjustment_option.chart_type == "pie" else ""
            
            user_prompt = prompt_template.format(
                query=query,
                sql=sql,
                chart_schema=chart_schema,
                sample_data=sample_data,
                sample_column_values=sample_column_values,
                language=language,
                chart_type=adjustment_option.chart_type,
                conditional_x_axis=conditional_x_axis,
                conditional_y_axis=conditional_y_axis,
                conditional_x_offset=conditional_x_offset,
                conditional_color=conditional_color,
                conditional_theta=conditional_theta
            )
            
            # Step 3: Generate chart adjustment
            generate_result = await self.generate_chart_adjustment(user_prompt)
            
            # Step 4: Post-process results
            final_result = self.post_process(
                generate_result,
                self.vega_schema,
                sample_data
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in chart adjustment: {e}")
            return {
                "error": str(e),
                "success": False
            }


class ChartAdjustment:
    """Main ChartAdjustment class maintaining original interface"""
    
    def __init__(self, llm_provider=None, **kwargs):
        self.tool = ChartAdjustmentTool(get_llm() if llm_provider is None else llm_provider)

    @observe(name="Chart Adjustment")
    async def run(
        self,
        query: str,
        sql: str,
        adjustment_option: ChartAdjustmentOption,
        chart_schema: dict,
        data: dict,
        language: str,
    ) -> dict:
        """Run chart adjustment with original interface"""
        return await self.tool.run(
            query=query,
            sql=sql,
            adjustment_option=adjustment_option,
            chart_schema=chart_schema,
            data=data,
            language=language
        )


def create_chart_adjustment_tool(llm_provider=None) -> Tool:
    """Create Langchain tool for chart adjustment"""
    chart_adj = ChartAdjustmentTool(get_llm() if llm_provider is None else llm_provider)
    
    def adjust_chart_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(chart_adj.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="chart_adjuster",
        description="Adjusts chart visualizations based on user preferences. Input should be JSON with 'query', 'sql', 'adjustment_option', 'chart_schema', 'data', and 'language' fields.",
        func=adjust_chart_func
    )


CHART_ADJUSTMENT_MODEL_KWARGS = {
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "chart_adjustment_results",
            "schema": ChartGenerationResults.model_json_schema(),
        },
    }
}


if __name__ == "__main__":
    # Test the chart adjustment tool
    async def test_chart_adjustment():
        from app.core.dependencies import get_llm
        llm_provider = get_llm()  # Initialize with your config
        chart_adj = ChartAdjustment()
        
        # Create a proper ChartAdjustmentOption with required fields
        adjustment_option = ChartAdjustmentOption(
            chart_type="bar",  # Required field
            x_axis="category",
            y_axis="value"
        )
        
        # Sample chart schema
        sample_chart_schema = {
            "title": "Sample Bar Chart",
            "mark": {"type": "bar"},
            "encoding": {
                "x": {"field": "category", "type": "nominal", "title": "Category"},
                "y": {"field": "value", "type": "quantitative", "title": "Value"}
            }
        }
        
        # Sample data with proper structure
        sample_data = {
            "data": [
                {"category": "A", "value": 10},
                {"category": "B", "value": 20},
                {"category": "C", "value": 30}
            ],
            "columns": {
                "category": ["A", "B", "C"],
                "value": [10, 20, 30]
            }
        }
        
        result = await chart_adj.run(
            query="Show me the data as a bar chart with categories on x-axis and values on y-axis",
            sql="SELECT category, value FROM table",
            adjustment_option=adjustment_option,
            chart_schema=sample_chart_schema,
            data=sample_data,
            language="English"
        )
        
        print("Chart Adjustment Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    asyncio.run(test_chart_adjustment())

__all__ = ["ChartAdjustment", "create_chart_adjustment_tool"]