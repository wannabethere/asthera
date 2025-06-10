import asyncio
import logging
from typing import Any, Dict

import orjson
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langfuse.decorators import observe

from app.core.dependencies import get_llm
from app.agents.nodes.sql.utils.chart import (
    ChartDataPreprocessor,
    ChartGenerationPostProcessor,
    ChartGenerationResults,
    chart_generation_instructions,
)
from app.agents.nodes.sql.utils.chart_models import ChartAdjustmentOption

logger = logging.getLogger("wren-ai-service")

chart_adjustment_system_prompt = f"""
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
Original Question: {{ query }}
Original SQL: {{ sql }}
Original Vega-Lite Schema: {{ chart_schema }}
Sample Data: {{ sample_data }}
Sample Column Values: {{ sample_column_values }}
Language: {{ language }}

Adjustment Options:
- Chart Type: {{ adjustment_option.chart_type }}
{% if adjustment_option.chart_type != "pie" %}
{% if adjustment_option.x_axis %}
- X Axis: {{ adjustment_option.x_axis }}
{% endif %}
{% if adjustment_option.y_axis %}
- Y Axis: {{ adjustment_option.y_axis }}
{% endif %}
{% endif %}
{% if adjustment_option.x_offset and adjustment_option.chart_type == "grouped_bar" %}
- X Offset: {{ adjustment_option.x_offset }}
{% endif %}
{% if adjustment_option.color and adjustment_option.chart_type != "area" %}
- Color: {{ adjustment_option.color }}
{% endif %}
{% if adjustment_option.theta and adjustment_option.chart_type == "pie" %}
- Theta: {{ adjustment_option.theta }}
{% endif %}

Please think step by step
"""


class ChartAdjustmentTool:
    """Langchain tool for chart adjustment"""
    
    def __init__(self, llm):
        self.llm = llm
        self.chart_data_preprocessor = ChartDataPreprocessor()
        self.post_processor = ChartGenerationPostProcessor()
        
        # Load vega schema
        with open("app/agents/nodes/sql/utils/vega-lite-schema-v5.json", "r") as f:
            self.vega_schema = orjson.loads(f.read())
        
        self.name = "chart_adjustment"
        self.description = "Adjusts chart visualizations based on user preferences"

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
                system_prompt=chart_adjustment_system_prompt,
                user_prompt=prompt_input
            )
            
            return {"replies": [result]}
        except Exception as e:
            logger.error(f"Error in chart adjustment generation: {e}")
            return {"replies": [""]}

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
                    "query", "sql", "adjustment_option", "chart_schema", 
                    "sample_data", "sample_column_values", "language"
                ],
                template=chart_adjustment_user_prompt_template
            )
            
            user_prompt = prompt_template.format(
                query=query,
                sql=sql,
                adjustment_option=adjustment_option,
                chart_schema=chart_schema,
                sample_data=sample_data,
                sample_column_values=sample_column_values,
                language=language
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


def create_chart_adjustment_tool() -> Tool:
    """Create Langchain tool for chart adjustment"""
    chart_adj = ChartAdjustmentTool(get_llm())
    
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