import asyncio
import logging
from typing import Any, Dict, List, Optional
import json

import orjson
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from app.core.dependencies import get_llm

logger = logging.getLogger("lexy-ai-service")


class VegaLiteToPlotlyConverter:
    """Converter from Vega-Lite to Plotly charts using LLM"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
    
    async def convert(
        self,
        vega_lite_schema: Dict[str, Any],
        language: str = "English",
        target_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Convert Vega-Lite chart schema to Plotly chart configuration
        
        Args:
            vega_lite_schema: Vega-Lite chart schema dictionary
            language: Language for the chart
            target_schema: Optional target Plotly schema template to use as reference
            
        Returns:
            Plotly chart configuration dictionary
        """
        try:
            schema_instruction = ""
            if target_schema:
                target_schema_json = json.dumps(target_schema, indent=2)
                schema_instruction = f"""
            ### TARGET SCHEMA TEMPLATE ###
            
            Use the following Plotly schema template as a reference for the structure and format:
            {target_schema_json}
            
            IMPORTANT: 
            - Follow the structure and format of the target schema
            - Map the Vega-Lite fields to match the target schema's field names and structure
            - Preserve any styling, colors, or layout preferences from the target schema
            - Adapt the target schema to work with the data from the Vega-Lite schema
            """
            
            base_system_prompt = """
            ### TASK ###
            
            You are an expert at converting Vega-Lite charts to Plotly charts! Given a Vega-Lite chart schema, 
            you need to convert it to an equivalent Plotly chart configuration.
            
            ### CONVERSION RULES ###
            
            1. **Chart Type Mapping**:
               - Vega-Lite "bar" → Plotly "bar"
               - Vega-Lite "line" → Plotly "scatter" with mode="lines"
               - Vega-Lite "area" → Plotly "scatter" with mode="lines" and fill="tozeroy"
               - Vega-Lite "pie" → Plotly "pie"
               - Vega-Lite "scatter" → Plotly "scatter" with mode="markers"
               - Vega-Lite "text" → Plotly "indicator" (for KPI charts)
            
            2. **Data Structure**:
               - Vega-Lite uses "data.values" array
               - Plotly uses "data" array with trace objects
               - Extract field mappings from Vega-Lite encoding
            
            3. **Encoding Mapping**:
               - Vega-Lite "x" encoding → Plotly trace "x" field
               - Vega-Lite "y" encoding → Plotly trace "y" field
               - Vega-Lite "color" encoding → Plotly trace "marker.color" or separate traces
               - Vega-Lite "size" encoding → Plotly trace "marker.size"
            
            4. **Mark Properties**:
               - Vega-Lite "mark.type" → Plotly trace "type"
               - Vega-Lite "mark.color" → Plotly trace "marker.color" or "line.color"
               - Preserve other visual properties
            
            5. **Layout**:
               - Vega-Lite "title" → Plotly "layout.title.text"
               - Vega-Lite axis titles → Plotly "layout.xaxis.title" and "layout.yaxis.title"
               - Preserve other layout properties
            
            6. **KPI Charts**:
               - If Vega-Lite uses "text" mark type, convert to Plotly "indicator" type
               - Preserve kpi_metadata if present
            
            ### OUTPUT FORMAT ###
            
            You MUST respond with ONLY a valid JSON object containing the Plotly chart configuration:
            
            {{
                "chart_config": {{
                    "data": [{{
                        "type": "<PLOTLY_TRACE_TYPE>",
                        "x": [<X_VALUES>] or "<FIELD_NAME>",
                        "y": [<Y_VALUES>] or "<FIELD_NAME>",
                        "mode": "<MODE>",
                        "marker": {{<MARKER_PROPERTIES>}},
                        "line": {{<LINE_PROPERTIES>}},
                        "name": "<TRACE_NAME>"
                    }}],
                    "layout": {{
                        "title": {{"text": "<TITLE>"}},
                        "xaxis": {{"title": "<X_AXIS_TITLE>"}},
                        "yaxis": {{"title": "<Y_AXIS_TITLE>"}}
                    }}
                }},
                "chart_type": "<CHART_TYPE>",
                "reasoning": "Explanation of the conversion"
            }}
            
            Do NOT include:
            - Markdown formatting
            - Code blocks
            - Explanations outside the JSON
            - Comments in JSON
            
            Your response should be a single JSON object.
            """
            
            system_prompt = base_system_prompt + schema_instruction
            
            target_schema_str = f'Target Schema Template: {json.dumps(target_schema, indent=2)}' if target_schema else ''
            schema_instruction_str = "Use the target schema template as a reference for structure and format." if target_schema else ""
            
            user_prompt = f"""
            ### INPUT ###
            Vega-Lite Schema: {json.dumps(vega_lite_schema, indent=2)}
            Language: {language}
            {target_schema_str}
            
            Please convert this Vega-Lite chart schema to an equivalent Plotly chart configuration.
            {schema_instruction_str}
            """
            
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=generation_prompt)
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            try:
                parsed = orjson.loads(result_str)
                return parsed.get("chart_config", {})
            except orjson.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
                if json_match:
                    try:
                        parsed = orjson.loads(json_match.group(0))
                        return parsed.get("chart_config", {})
                    except orjson.JSONDecodeError:
                        pass
                logger.error("Failed to parse Plotly conversion response")
                return {}
            
        except Exception as e:
            logger.error(f"Error converting Vega-Lite to Plotly: {e}")
            return {}


class VegaLiteToPowerBIConverter:
    """Converter from Vega-Lite to PowerBI charts using LLM"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
    
    async def convert(
        self,
        vega_lite_schema: Dict[str, Any],
        language: str = "English",
        target_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Convert Vega-Lite chart schema to PowerBI chart configuration
        
        Args:
            vega_lite_schema: Vega-Lite chart schema dictionary
            language: Language for the chart
            target_schema: Optional target PowerBI schema template to use as reference
            
        Returns:
            PowerBI chart configuration dictionary
        """
        try:
            schema_instruction = ""
            if target_schema:
                target_schema_json = json.dumps(target_schema, indent=2)
                schema_instruction = f"""
            ### TARGET SCHEMA TEMPLATE ###
            
            Use the following PowerBI schema template as a reference for the structure and format:
            {target_schema_json}
            
            IMPORTANT: 
            - Follow the structure and format of the target schema
            - Map the Vega-Lite fields to match the target schema's field names and structure
            - Preserve any styling, colors, or layout preferences from the target schema
            - Adapt the target schema to work with the data from the Vega-Lite schema
            """
            
            base_system_prompt = """
            ### TASK ###
            
            You are an expert at converting Vega-Lite charts to PowerBI charts! Given a Vega-Lite chart schema, 
            you need to convert it to an equivalent PowerBI chart configuration.
            
            ### CONVERSION RULES ###
            
            1. **Visual Type Mapping**:
               - Vega-Lite "bar" → PowerBI "columnChart" or "clusteredColumnChart"
               - Vega-Lite "line" → PowerBI "lineChart"
               - Vega-Lite "area" → PowerBI "areaChart"
               - Vega-Lite "pie" → PowerBI "pieChart"
               - Vega-Lite "scatter" → PowerBI "scatterChart"
               - Vega-Lite "text" → PowerBI "card" (for KPI charts)
            
            2. **Data Roles**:
               - PowerBI uses "dataRoles" to define field mappings
               - Vega-Lite "x" encoding → PowerBI "Category" or "Axis" data role
               - Vega-Lite "y" encoding → PowerBI "Values" data role
               - Vega-Lite "color" encoding → PowerBI "Legend" data role
            
            3. **Aggregation**:
               - Determine appropriate aggregation (Sum, Average, Count) based on data type
               - Use "sum" for quantitative values
               - Use "count" for categorical values
            
            4. **KPI Charts**:
               - If Vega-Lite uses "text" mark type, convert to PowerBI "card" visualType
               - Preserve kpi_metadata if present
            
            ### OUTPUT FORMAT ###
            
            You MUST respond with ONLY a valid JSON object containing the PowerBI chart configuration:
            
            {
                "chart_config": {
                    "visualType": "<POWERBI_VISUAL_TYPE>",
                    "dataRoles": {
                        "Values": [{
                            "field": "<FIELD_NAME>",
                            "aggregation": "<AGGREGATION_TYPE>"
                        }],
                        "Category": [{
                            "field": "<FIELD_NAME>"
                        }]
                    },
                    "title": "<TITLE>"
                },
                "chart_type": "<CHART_TYPE>",
                "reasoning": "Explanation of the conversion"
            }
            
            Do NOT include:
            - Markdown formatting
            - Code blocks
            - Explanations outside the JSON
            
            Your response should be a single JSON object.
            """
            
            system_prompt = base_system_prompt + schema_instruction
            
            target_schema_str = f'Target Schema Template: {json.dumps(target_schema, indent=2)}' if target_schema else ''
            schema_instruction_str = "Use the target schema template as a reference for structure and format." if target_schema else ""
            
            user_prompt = f"""
            ### INPUT ###
            Vega-Lite Schema: {json.dumps(vega_lite_schema, indent=2)}
            Language: {language}
            {target_schema_str}
            
            Please convert this Vega-Lite chart schema to an equivalent PowerBI chart configuration.
            {schema_instruction_str}
            """
            
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=generation_prompt)
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            try:
                parsed = orjson.loads(result_str)
                return parsed.get("chart_config", {})
            except orjson.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
                if json_match:
                    try:
                        parsed = orjson.loads(json_match.group(0))
                        return parsed.get("chart_config", {})
                    except orjson.JSONDecodeError:
                        pass
                logger.error("Failed to parse PowerBI conversion response")
                return {}
            
        except Exception as e:
            logger.error(f"Error converting Vega-Lite to PowerBI: {e}")
            return {}


class VegaLiteToTableauConverter:
    """Converter from Vega-Lite to Tableau charts using LLM"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
    
    async def convert(
        self,
        vega_lite_schema: Dict[str, Any],
        language: str = "English",
        target_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Convert Vega-Lite chart schema to Tableau chart configuration
        
        Args:
            vega_lite_schema: Vega-Lite chart schema dictionary
            language: Language for the chart
            target_schema: Optional target Tableau schema template to use as reference
            
        Returns:
            Tableau chart configuration dictionary
        """
        try:
            schema_instruction = ""
            if target_schema:
                target_schema_json = json.dumps(target_schema, indent=2)
                schema_instruction = f"""
            ### TARGET SCHEMA TEMPLATE ###
            
            Use the following Tableau schema template as a reference for the structure and format:
            {target_schema_json}
            
            IMPORTANT: 
            - Follow the structure and format of the target schema
            - Map the Vega-Lite fields to match the target schema's field names and structure
            - Preserve any styling, colors, or layout preferences from the target schema
            - Adapt the target schema to work with the data from the Vega-Lite schema
            """
            
            base_system_prompt = """
            ### TASK ###
            
            You are an expert at converting Vega-Lite charts to Tableau charts! Given a Vega-Lite chart schema, 
            you need to convert it to an equivalent Tableau visualization configuration.
            
            ### CONVERSION RULES ###
            
            1. **Chart Type Mapping**:
               - Vega-Lite "bar" → Tableau "bar"
               - Vega-Lite "line" → Tableau "line"
               - Vega-Lite "area" → Tableau "area"
               - Vega-Lite "pie" → Tableau "pie"
               - Vega-Lite "scatter" → Tableau "scatter"
               - Vega-Lite "text" → Tableau "kpi" (for KPI charts)
            
            2. **Shelves**:
               - Tableau uses "shelves" to organize fields
               - Vega-Lite "x" encoding → Tableau "columns" shelf
               - Vega-Lite "y" encoding → Tableau "rows" shelf
               - Vega-Lite "color" encoding → Tableau "color" shelf
               - Vega-Lite "size" encoding → Tableau "size" shelf
            
            3. **Field Types**:
               - Determine if fields are dimensions or measures
               - Quantitative fields → measures with aggregation
               - Nominal/Ordinal fields → dimensions
            
            4. **Aggregation**:
               - Use appropriate aggregation (SUM, AVG, COUNT) based on data type
               - Default to SUM for quantitative measures
            
            5. **KPI Charts**:
               - If Vega-Lite uses "text" mark type, convert to Tableau "kpi" chart_type
               - Use empty rows/columns and text marks
               - Preserve kpi_metadata if present
            
            ### OUTPUT FORMAT ###
            
            You MUST respond with ONLY a valid JSON object containing the Tableau chart configuration:
            
            {
                "chart_config": {
                    "chart_type": "<TABLEAU_CHART_TYPE>",
                    "rows": [{
                        "field": "<FIELD_NAME>",
                        "type": "dimension" | "measure",
                        "aggregation": "<AGGREGATION_TYPE>"
                    }],
                    "columns": [{
                        "field": "<FIELD_NAME>",
                        "type": "dimension" | "measure",
                        "aggregation": "<AGGREGATION_TYPE>"
                    }],
                    "color": [{
                        "field": "<FIELD_NAME>",
                        "type": "dimension" | "measure"
                    }],
                    "title": "<TITLE>"
                },
                "chart_type": "<CHART_TYPE>",
                "reasoning": "Explanation of the conversion"
            }
            
            Do NOT include:
            - Markdown formatting
            - Code blocks
            - Explanations outside the JSON
            
            Your response should be a single JSON object.
            """
            
            system_prompt = base_system_prompt + schema_instruction
            
            target_schema_str = f'Target Schema Template: {json.dumps(target_schema, indent=2)}' if target_schema else ''
            schema_instruction_str = "Use the target schema template as a reference for structure and format." if target_schema else ""
            
            user_prompt = f"""
            ### INPUT ###
            Vega-Lite Schema: {json.dumps(vega_lite_schema, indent=2)}
            Language: {language}
            {target_schema_str}
            
            Please convert this Vega-Lite chart schema to an equivalent Tableau chart configuration.
            {schema_instruction_str}
            """
            
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=generation_prompt)
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            try:
                parsed = orjson.loads(result_str)
                return parsed.get("chart_config", {})
            except orjson.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
                if json_match:
                    try:
                        parsed = orjson.loads(json_match.group(0))
                        return parsed.get("chart_config", {})
                    except orjson.JSONDecodeError:
                        pass
                logger.error("Failed to parse Tableau conversion response")
                return {}
            
        except Exception as e:
            logger.error(f"Error converting Vega-Lite to Tableau: {e}")
            return {}


# Factory functions to create LangChain tools
def create_vega_lite_to_plotly_tool(llm=None) -> Tool:
    """Create LangChain tool for converting Vega-Lite to Plotly"""
    converter = VegaLiteToPlotlyConverter(llm)
    
    def convert_func(input_json: str) -> str:
        """Convert Vega-Lite chart(s) to Plotly chart configuration(s)
        
        Accepts either:
        - Single chart: {"vega_lite_schema": {...}, "language": "English", "target_schema": {...}}
        - List of charts: [{"vega_lite_schema": {...}, "language": "English", "target_schema": {...}}, ...]
        """
        try:
            input_data = orjson.loads(input_json)
            
            # Handle list of inputs (thread components)
            if isinstance(input_data, list):
                results = []
                for item in input_data:
                    vega_lite_schema = item.get("vega_lite_schema", {})
                    language = item.get("language", "English")
                    target_schema = item.get("target_schema")
                    result = asyncio.run(converter.convert(vega_lite_schema, language, target_schema))
                    results.append({
                        "success": True,
                        "chart_config": result,
                        "chart_type": result.get("chart_type", ""),
                        "target_format": "plotly"
                    })
                return orjson.dumps(results).decode()
            
            # Handle single input
            else:
                vega_lite_schema = input_data.get("vega_lite_schema", {})
                language = input_data.get("language", "English")
                target_schema = input_data.get("target_schema")
                
                result = asyncio.run(converter.convert(vega_lite_schema, language, target_schema))
                
                return orjson.dumps({
                    "success": True,
                    "chart_config": result,
                    "chart_type": result.get("chart_type", ""),
                    "target_format": "plotly"
                }).decode()
        except Exception as e:
            logger.error(f"Error in Vega-Lite to Plotly conversion: {e}")
            return orjson.dumps({
                "success": False,
                "error": str(e),
                "chart_config": {},
                "target_format": "plotly"
            }).decode()
    
    return Tool(
        name="vega_lite_to_plotly_converter",
        description="Converts Vega-Lite chart schema(s) to Plotly chart configuration(s). Input can be a single JSON object with 'vega_lite_schema' (dict), optional 'language' (string), and optional 'target_schema' (dict) for schema-based generation, or a list of such objects for batch conversion.",
        func=convert_func
    )


def create_vega_lite_to_powerbi_tool(llm=None) -> Tool:
    """Create LangChain tool for converting Vega-Lite to PowerBI"""
    converter = VegaLiteToPowerBIConverter(llm)
    
    def convert_func(input_json: str) -> str:
        """Convert Vega-Lite chart(s) to PowerBI chart configuration(s)
        
        Accepts either:
        - Single chart: {"vega_lite_schema": {...}, "language": "English", "target_schema": {...}}
        - List of charts: [{"vega_lite_schema": {...}, "language": "English", "target_schema": {...}}, ...]
        """
        try:
            input_data = orjson.loads(input_json)
            
            # Handle list of inputs (thread components)
            if isinstance(input_data, list):
                results = []
                for item in input_data:
                    vega_lite_schema = item.get("vega_lite_schema", {})
                    language = item.get("language", "English")
                    target_schema = item.get("target_schema")
                    result = asyncio.run(converter.convert(vega_lite_schema, language, target_schema))
                    results.append({
                        "success": True,
                        "chart_config": result,
                        "chart_type": result.get("chart_type", ""),
                        "target_format": "powerbi"
                    })
                return orjson.dumps(results).decode()
            
            # Handle single input
            else:
                vega_lite_schema = input_data.get("vega_lite_schema", {})
                language = input_data.get("language", "English")
                target_schema = input_data.get("target_schema")
                
                result = asyncio.run(converter.convert(vega_lite_schema, language, target_schema))
                
                return orjson.dumps({
                    "success": True,
                    "chart_config": result,
                    "chart_type": result.get("chart_type", ""),
                    "target_format": "powerbi"
                }).decode()
        except Exception as e:
            logger.error(f"Error in Vega-Lite to PowerBI conversion: {e}")
            return orjson.dumps({
                "success": False,
                "error": str(e),
                "chart_config": {},
                "target_format": "powerbi"
            }).decode()
    
    return Tool(
        name="vega_lite_to_powerbi_converter",
        description="Converts Vega-Lite chart schema(s) to PowerBI chart configuration(s). Input can be a single JSON object with 'vega_lite_schema' (dict), optional 'language' (string), and optional 'target_schema' (dict) for schema-based generation, or a list of such objects for batch conversion.",
        func=convert_func
    )


def create_vega_lite_to_tableau_tool(llm=None) -> Tool:
    """Create LangChain tool for converting Vega-Lite to Tableau"""
    converter = VegaLiteToTableauConverter(llm)
    
    def convert_func(input_json: str) -> str:
        """Convert Vega-Lite chart(s) to Tableau chart configuration(s)
        
        Accepts either:
        - Single chart: {"vega_lite_schema": {...}, "language": "English", "target_schema": {...}}
        - List of charts: [{"vega_lite_schema": {...}, "language": "English", "target_schema": {...}}, ...]
        """
        try:
            input_data = orjson.loads(input_json)
            
            # Handle list of inputs (thread components)
            if isinstance(input_data, list):
                results = []
                for item in input_data:
                    vega_lite_schema = item.get("vega_lite_schema", {})
                    language = item.get("language", "English")
                    target_schema = item.get("target_schema")
                    result = asyncio.run(converter.convert(vega_lite_schema, language, target_schema))
                    results.append({
                        "success": True,
                        "chart_config": result,
                        "chart_type": result.get("chart_type", ""),
                        "target_format": "tableau"
                    })
                return orjson.dumps(results).decode()
            
            # Handle single input
            else:
                vega_lite_schema = input_data.get("vega_lite_schema", {})
                language = input_data.get("language", "English")
                target_schema = input_data.get("target_schema")
                
                result = asyncio.run(converter.convert(vega_lite_schema, language, target_schema))
                
                return orjson.dumps({
                    "success": True,
                    "chart_config": result,
                    "chart_type": result.get("chart_type", ""),
                    "target_format": "tableau"
                }).decode()
        except Exception as e:
            logger.error(f"Error in Vega-Lite to Tableau conversion: {e}")
            return orjson.dumps({
                "success": False,
                "error": str(e),
                "chart_config": {},
                "target_format": "tableau"
            }).decode()
    
    return Tool(
        name="vega_lite_to_tableau_converter",
        description="Converts Vega-Lite chart schema(s) to Tableau chart configuration(s). Input can be a single JSON object with 'vega_lite_schema' (dict), optional 'language' (string), and optional 'target_schema' (dict) for schema-based generation, or a list of such objects for batch conversion.",
        func=convert_func
    )

