import asyncio
import logging
import os
from typing import Any, Dict, Literal, Optional

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

# Import LLMChain using modern LangChain paths
try:
    from langchain.chains import LLMChain
except ImportError:
    LLMChain = None

# Import RunnablePassthrough using modern LangChain paths
try:
    from langchain_core.runnables import RunnablePassthrough
except ImportError:
    try:
        from langchain.schema.runnable import RunnablePassthrough
    except ImportError:
        RunnablePassthrough = None

from langfuse.decorators import observe
from app.core.dependencies import get_llm
from app.agents.nodes.sql.utils.chart_models import ChartAdjustmentOption,ChartGenerationResults
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider
from app.agents.nodes.sql.utils.chart import create_chart_from_existing_schema

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()

# Get the absolute path to the schema file
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "utils", "vega-lite-schema-v5.json")

# Move the chart_generation_instructions import inside the class where it's used
chart_adjustment_system_prompt = """
### TASK ###

You are a data analyst great at visualizing data using vega-lite! Given the user's question, SQL, original vega-lite schema and adjustment options, 
you need to analyze whether the request is for:
1. **Chart Adjustment**: Modifying the chart appearance, type, or encoding
2. **Chart Annotation**: Adding text labels, callouts, reference lines, or other annotations
3. **Both**: Combining chart adjustments with annotations

### REASONING STEP ###

First, analyze the user's request and determine the type:
- **Chart Adjustment**: Requests like "make bars blue", "change to line chart", "add color encoding"
- **Chart Annotation**: Requests like "add labels", "highlight this point", "add a reference line", "put text here"
- **Both**: Requests that combine both adjustments and annotations

### CHART ADJUSTMENT CAPABILITIES ###

For chart adjustments, you can:
- Change chart type (bar, line, pie, etc.)
- Modify colors, sizes, and visual properties
- Adjust encoding channels (x, y, color, size, etc.)
- Change mark types and properties

### ANNOTATION CAPABILITIES ###

For annotations, you can add:
- **Text annotations**: Labels, titles, descriptions
- **Reference lines**: Horizontal/vertical lines for thresholds
- **Highlights**: Color overlays for specific data points
- **Callouts**: Arrows or lines pointing to specific areas
- **Markers**: Special symbols or indicators

### IMPORTANT ###
You MUST include the data block in your chart_schema response. Copy the data from the input chart schema and include it in your generated chart schema.

{chart_generation_instructions}
- If you think the adjustment options are not suitable for the data, you can return an empty string for the schema and chart type and give reasoning to explain why.

### CRITICAL INSTRUCTION ###

You MUST respond with ONLY a valid JSON object. Do NOT include:
- Any text before the JSON
- Any text after the JSON  
- Markdown formatting
- Code blocks
- Explanations outside the JSON
- Comments in the JSON (no // or /* */ comments)
- Trailing commas

Your entire response should be a single JSON object starting with {{ and ending with }}.

### VEGA-LITE SCHEMA RULES ###

1. Encoding channels must be at the top level of the encoding object:
   - Valid: {{"x": {{"field": "x_field"}}, "y": {{"field": "y_field"}}, "color": {{"field": "color_field"}}}}
   - Invalid: {{"x": {{"field": "x_field", "xOffset": {{"field": "offset_field"}}}}}}

2. Color scales must be valid JSON:
   - Valid: {{"scale": {{"domain": ["A", "B"], "range": ["red", "blue"]}}}}
   - Invalid: {{"scale": {{"domain": ["A", "B"], "range": ["red", "blue"] // comment}}}}

3. xOffset is a separate encoding channel, not nested within other channels

### OUTPUT FORMAT ###

{{
    "reasoning": "Your reasoning here in plain text - explain whether this is chart adjustment, annotation, or both",
    "chart_type": "line" | "multi_line" | "bar" | "pie" | "grouped_bar" | "stacked_bar" | "area" | "",
    "adjustment_type": "chart_adjustment" | "annotation" | "both",
    "chart_schema": {{
        "mark": {{"type": "bar"}},
        "encoding": {{
            "x": {{"field": "field_name", "type": "nominal"}},
            "y": {{"field": "field_name", "type": "quantitative"}},
            "color": {{"field": "field_name", "type": "nominal"}}
        }},
        "data": {{
            "values": [
                {{"field1": "value1", "field2": "value2"}},
                {{"field1": "value3", "field2": "value4"}}
            ]
        }}
    }},
    "annotation_config": {{
        "annotations": [
            {{
                "annotation_id": "ann_1",
                "annotation_type": "text",
                "position": {{"x": 100, "y": 200}},
                "content": "Important note",
                "style": {{"color": "red", "fontSize": 14}},
                "description": "Highlight important data point"
            }}
        ],
        "annotation_layer": {{
            "mark": {{"type": "text"}},
            "encoding": {{
                "x": {{"field": "x_pos", "type": "quantitative"}},
                "y": {{"field": "y_pos", "type": "quantitative"}},
                "text": {{"field": "label", "type": "nominal"}}
            }}
        }}
    }}
}}

### EXAMPLES ###

For a chart adjustment:
{{
    "reasoning": "I will change the bar color to orange as requested",
    "chart_type": "bar",
    "adjustment_type": "chart_adjustment",
    "chart_schema": {{
        "mark": {{"type": "bar"}},
        "encoding": {{
            "x": {{"field": "Division", "type": "nominal"}},
            "y": {{"field": "Completed_Trainings", "type": "quantitative"}},
            "color": {{"field": "Division", "type": "nominal", "scale": {{"range": ["orange"]}}}}
        }},
        "data": {{
            "values": [
                {{"Division": "Administration", "Completed_Trainings": 2495}},
                {{"Division": "Sales", "Completed_Trainings": 2482}}
            ]
        }}
    }}
}}

For an annotation request:
{{
    "reasoning": "I will add text labels to highlight the highest value",
    "chart_type": "bar",
    "adjustment_type": "annotation",
    "chart_schema": {{
        "mark": {{"type": "bar"}},
        "encoding": {{
            "x": {{"field": "Division", "type": "nominal"}},
            "y": {{"field": "Completed_Trainings", "type": "quantitative"}}
        }},
        "data": {{
            "values": [
                {{"Division": "Administration", "Completed_Trainings": 2495}},
                {{"Division": "Sales", "Completed_Trainings": 2482}}
            ]
        }}
    }},
    "annotation_config": {{
        "annotations": [
            {{
                "annotation_id": "highlight_max",
                "annotation_type": "text",
                "position": {{"x": "Administration", "y": 2495}},
                "content": "Highest",
                "style": {{"color": "red", "fontWeight": "bold"}},
                "description": "Highlight the highest training completion count"
            }}
        ]
    }}
}}

For no suitable adjustment:
{{
    "reasoning": "The requested adjustment is not suitable for this data type",
    "chart_type": "",
    "adjustment_type": "chart_adjustment",
    "chart_schema": {{}}
}}
"""

chart_adjustment_user_prompt_template = """
### INPUT ###
Original Question: {query}
Original SQL: {sql}
Original Vega-Lite Schema: {chart_schema}
Data: {data}
Language: {language}

Adjustment Option: {adjustment_option}

### ANALYSIS REQUEST ###
Please analyze whether this request is for:
1. **Chart Adjustment**: Modifying chart appearance, type, or encoding
2. **Chart Annotation**: Adding labels, callouts, reference lines, or highlights
3. **Both**: Combining chart adjustments with annotations

Then provide the appropriate response including:
- Reasoning for your classification
- Updated chart schema (if adjustments are needed)
- Annotation configuration (if annotations are requested)
- The adjustment_type field indicating your classification

Please think step by step and provide a comprehensive response.
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
        # Handle case where data might be a list instead of a dictionary
        if isinstance(data, list):
            # Convert list to expected dictionary format
            data = {
                "data": data,
                "columns": list(range(len(data[0]))) if data else []
            }
        elif not isinstance(data, dict):
            # Handle other unexpected data types
            logger.warning(f"Unexpected data type: {type(data)}. Converting to empty structure.")
            data = {"data": [], "columns": []}
        
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
            
            # Use modern LangChain approach instead of deprecated LLMChain
            chain = full_prompt | self.llm
            
            # Generate response
            result = await chain.ainvoke({
                "system_prompt": self.system_prompt,
                "user_prompt": prompt_input
            })
            
            # Extract content from AIMessage
            if hasattr(result, 'content'):
                result_content = result.content
            else:
                result_content = str(result)
            print("result_content",result_content)
            print("result_content type:", type(result_content))
            print("result_content length:", len(result_content))
            # Ensure the result is a properly formatted JSON string
            try:
                # First try to parse the raw result
                parsed_result = orjson.loads(result_content)
                return {"replies": [orjson.dumps(parsed_result).decode('utf-8')]}
            except orjson.JSONDecodeError:
                # If parsing fails, try to clean and parse the JSON
                import re
                
                # Clean the JSON string by removing comments and fixing common issues
                cleaned_json = result_content
                
                # Remove JavaScript-style comments (// and /* */)
                cleaned_json = re.sub(r'//.*?$', '', cleaned_json, flags=re.MULTILINE)  # Remove // comments
                cleaned_json = re.sub(r'/\*.*?\*/', '', cleaned_json, flags=re.DOTALL)  # Remove /* */ comments
                
                # Remove trailing commas before closing braces/brackets
                cleaned_json = re.sub(r',(\s*[}\]])', r'\1', cleaned_json)
                
                # Fix specific invalid Vega-Lite syntax patterns
                # Remove invalid nested xOffset within other encodings
                cleaned_json = re.sub(r'"xOffset":\s*\{[^}]*\}(?=\s*,\s*"[^"]*":)', '', cleaned_json)
                
                # Fix invalid color scale syntax with comments
                cleaned_json = re.sub(r'//\s*[^"]*?(?=\s*[}\]])', '', cleaned_json)
                
                # Remove any remaining invalid nested structures
                cleaned_json = re.sub(r'"xOffset":\s*\{[^}]*\}(?=\s*,\s*"[^"]*":)', '', cleaned_json)
                
                # Try to parse the cleaned JSON
                try:
                    parsed_result = orjson.loads(cleaned_json)
                    logger.info("Successfully parsed JSON after cleaning")
                    return {"replies": [orjson.dumps(parsed_result).decode('utf-8')]}
                except orjson.JSONDecodeError:
                    pass
                
                # If cleaning didn't work, try to extract JSON from the text
                json_patterns = [
                    r'\{.*\}',  # Basic JSON object
                    r'```json\s*(\{.*?\})\s*```',  # JSON in code block
                    r'```\s*(\{.*?\})\s*```',  # JSON in generic code block
                ]
                
                for pattern in json_patterns:
                    json_match = re.search(pattern, result_content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1) if len(json_match.groups()) > 0 else json_match.group(0)
                        
                        # Clean the extracted JSON
                        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                        
                        # Fix specific invalid Vega-Lite syntax patterns
                        json_str = re.sub(r'"xOffset":\s*\{[^}]*\}(?=\s*,\s*"[^"]*":)', '', json_str)
                        json_str = re.sub(r'//\s*[^"]*?(?=\s*[}\]])', '', json_str)
                        
                        try:
                            # Validate the extracted JSON
                            parsed_result = orjson.loads(json_str)
                            logger.info(f"Successfully extracted and cleaned JSON using pattern: {pattern}")
                            return {"replies": [orjson.dumps(parsed_result).decode('utf-8')]}
                        except orjson.JSONDecodeError:
                            continue
                
                # If all parsing attempts fail, try to create a structured response from the text
                logger.warning(f"Failed to parse JSON from LLM response: {result_content}")
                
                # Try to extract reasoning from the text (remove markdown and code blocks)
                cleaned_content = re.sub(r'```.*?```', '', result_content, flags=re.DOTALL)
                cleaned_content = re.sub(r'#+\s*', '', cleaned_content)  # Remove markdown headers
                cleaned_content = re.sub(r'\*\*.*?\*\*', '', cleaned_content)  # Remove bold text
                cleaned_content = re.sub(r'\*.*?\*', '', cleaned_content)  # Remove italic text
                cleaned_content = re.sub(r'`.*?`', '', cleaned_content)  # Remove inline code
                
                reasoning = cleaned_content.strip()
                if len(reasoning) > 500:  # Truncate if too long
                    reasoning = reasoning[:500] + "..."
                
                # Create a structured response
                structured_result = {
                    "reasoning": reasoning,
                    "chart_type": "",
                    "chart_schema": {}
                }
                return {"replies": [orjson.dumps(structured_result).decode('utf-8')]}
                
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
        try:
            # Get the raw result from LLM
            raw_result = generate_result.get("replies", [""])[0]
            parsed_result = orjson.loads(raw_result)
            
            # Extract annotation configuration if present
            annotation_config = parsed_result.get("annotation_config")
            adjustment_type = parsed_result.get("adjustment_type", "chart_adjustment")
            
            # Process the chart schema through the existing post-processor
            processed_result = self.post_processor.run(
                generate_result.get("replies"),
                vega_schema,
                sample_data,
                remove_data_from_chart_schema=False  # Preserve the original data
            )
            
            # Add annotation configuration and adjustment type to the result
            if annotation_config:
                processed_result["annotation_config"] = annotation_config
                processed_result["adjustment_type"] = adjustment_type
            
            # Ensure the reasoning is preserved
            if "reasoning" not in processed_result and "reasoning" in parsed_result:
                processed_result["reasoning"] = parsed_result["reasoning"]
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Error in post-processing: {e}")
            # Fall back to original post-processing if annotation handling fails
            return self.post_processor.run(
                generate_result.get("replies"),
                vega_schema,
                sample_data,
                remove_data_from_chart_schema=False
            )

    async def run(
        self,
        query: str,
        sql: str,
        adjustment_option: str,
        chart_schema: dict,
        data: dict,
        language: str,
    ) -> dict:
        """Main execution method for chart adjustment"""
        try:
            logger.info("Chart Adjustment pipeline is running...")
            logger.info(f"Data type: {type(data)}")
            logger.info(f"Data structure: {data}")
            
            # Step 1: Preprocess data
            #preprocess_result = self.preprocess_data(data)
            #sample_data = preprocess_result.get("sample_data", [])
            #sample_column_values = preprocess_result.get("sample_column_values", {})
            
            # Step 2: Create prompt
            prompt_template = PromptTemplate(
                input_variables=[
                    "query", "sql", "chart_schema", 
                    "language", "adjustment_option"
                ],
                template=chart_adjustment_user_prompt_template
            )
            
            user_prompt = prompt_template.format(
                query=query,
                sql=sql,
                chart_schema=chart_schema,
                data=data,
                language=language,
                adjustment_option=adjustment_option
            )
            
            # Step 3: Generate chart adjustment
            generate_result = await self.generate_chart_adjustment(user_prompt)
            print("generate_result",generate_result)
            
            # Step 4: Post-process results
            # Extract data from the LLM-generated chart schema
            parsed_result = orjson.loads(generate_result.get("replies", [""])[0])
            llm_chart_schema = parsed_result.get("chart_schema", {})
            llm_chart_data = llm_chart_schema.get("data", {}).get("values", []) if llm_chart_schema else []
            
            logger.info(f"Using data from LLM-generated chart schema: {len(llm_chart_data)} rows")
            logger.info(f"LLM chart schema data sample: {llm_chart_data[:2] if llm_chart_data else 'No data'}")
            logger.info(f"LLM chart schema transform: {llm_chart_schema.get('transform', 'No transform')}")
            logger.info(f"LLM chart schema encoding: {llm_chart_schema.get('encoding', 'No encoding')}")
            
            # Check if this is an annotation request
            adjustment_type = parsed_result.get("adjustment_type", "chart_adjustment")
            annotation_config = parsed_result.get("annotation_config")
            
            logger.info(f"Adjustment type detected: {adjustment_type}")
            if annotation_config:
                logger.info(f"Annotation configuration found with {len(annotation_config.get('annotations', []))} annotations")
            
            final_result = self.post_process(
                generate_result,
                self.vega_schema,
                llm_chart_data
            )
            
            # Ensure backward compatibility by maintaining the existing structure
            # while adding new annotation fields
            if annotation_config and "annotation_config" not in final_result:
                final_result["annotation_config"] = annotation_config
            
            if "adjustment_type" not in final_result:
                final_result["adjustment_type"] = adjustment_type
            
            # Add reasoning if not present
            if "reasoning" not in final_result and "reasoning" in parsed_result:
                final_result["reasoning"] = parsed_result["reasoning"]
            
            print("final_result",final_result)
            return final_result
            
        except Exception as e:
            logger.error(f"Error in chart adjustment: {e}")
            return {
                "error": str(e),
                "success": False,
                "adjustment_type": "chart_adjustment"
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
        adjustment: str,
        chart_schema: dict,
        data: dict,
        language: str,
    ) -> dict:
        """
        Run chart adjustment with original interface
        
        This method now supports both chart adjustments and annotations:
        - Chart adjustments: modify chart appearance, type, or encoding
        - Annotations: add labels, callouts, reference lines, or highlights
        - Combined: both adjustments and annotations
        
        Returns:
            dict: Result containing chart_schema, annotation_config (if applicable), 
                  adjustment_type, and other metadata
        """
        return await self.tool.run(
            query=query,
            sql=sql,
            adjustment_option=adjustment,
            chart_schema=chart_schema,
            data=data,
            language=language
        )


def create_chart_adjustment_tool(llm_provider=None) -> Tool:
    """Create Langchain tool for chart adjustment and annotation"""
    chart_adj = ChartAdjustmentTool(get_llm() if llm_provider is None else llm_provider)
    
    def adjust_chart_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(chart_adj.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False, "adjustment_type": "chart_adjustment"}).decode()
    
    return Tool(
        name="chart_adjuster",
        description="Adjusts chart visualizations and adds annotations based on user preferences. Supports chart adjustments (colors, types, encoding) and annotations (labels, callouts, reference lines, highlights). Input should be JSON with 'query', 'sql', 'adjustment', 'chart_schema', 'data', and 'language' fields.",
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
        
        # Test 1: Chart adjustment
        print("=== Testing Chart Adjustment ===")
        result1 = await chart_adj.run(
            query="Show me the data as a bar chart with categories on x-axis and values on y-axis",
            sql="SELECT category, value FROM table",
            adjustment="Make the bars blue",
            chart_schema=sample_chart_schema,
            data=sample_data,
            language="English"
        )
        
        print("Chart Adjustment Result:")
        print(orjson.dumps(result1, option=orjson.OPT_INDENT_2).decode())
        
        # Test 2: Annotation request
        print("\n=== Testing Annotation Request ===")
        result2 = await chart_adj.run(
            query="Add labels to show the values on top of each bar",
            sql="SELECT category, value FROM table",
            adjustment="Add value labels on top of bars",
            chart_schema=sample_chart_schema,
            data=sample_data,
            language="English"
        )
        
        print("Annotation Result:")
        print(orjson.dumps(result2, option=orjson.OPT_INDENT_2).decode())
        
        # Test 3: Combined request
        print("\n=== Testing Combined Request ===")
        result3 = await chart_adj.run(
            query="Change the bars to green and add a reference line at value 15",
            sql="SELECT category, value FROM table",
            adjustment="Change color to green and add reference line",
            chart_schema=sample_chart_schema,
            data=sample_data,
            language="English"
        )
        
        print("Combined Result:")
        print(orjson.dumps(result3, option=orjson.OPT_INDENT_2).decode())

    asyncio.run(test_chart_adjustment())

__all__ = ["ChartAdjustment", "create_chart_adjustment_tool", "ChartAdjustmentTool"]