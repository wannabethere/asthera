import asyncio
import logging
from typing import Any, Dict, List, Optional
import json
from pathlib import Path
from datetime import datetime

import orjson
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

from app.core.dependencies import get_llm

logger = logging.getLogger("lexy-ai-service")


class CommonDataExtractor:
    """Common utility for extracting data tables and rows from thread components"""
    
    @staticmethod
    def extract_table_data(
        component_id: str,
        question: str,
        sql_query: str,
        sample_data: Dict[str, Any],
        sequence_order: int
    ) -> Dict[str, Any]:
        """Extract common table data structure from thread component
        
        Args:
            component_id: Component identifier
            question: Question text
            sql_query: SQL query string
            sample_data: Sample data dictionary with 'columns' and 'data'
            sequence_order: Sequence order of the component
            
        Returns:
            Dictionary with:
            - table_name: Name of the table
            - columns: List of column definitions with name, inferred_type, sample_value
            - rows: List of data rows (limited to 100 for sample)
            - metadata: Component metadata
        """
        columns = sample_data.get("columns", [])
        data_rows = sample_data.get("data", [])
        
        # Extract column definitions with type inference
        column_definitions = []
        if data_rows and len(data_rows) > 0:
            first_row = data_rows[0]
            for col in columns:
                sample_value = first_row.get(col, "")
                inferred_type = CommonDataExtractor._infer_data_type(sample_value)
                
                column_definitions.append({
                    "name": col,
                    "inferred_type": inferred_type,
                    "sample_value": sample_value,
                    "display_name": col
                })
        else:
            # Fallback: create columns from column names
            for col in columns:
                column_definitions.append({
                    "name": col,
                    "inferred_type": "string",
                    "sample_value": None,
                    "display_name": col
                })
        
        # Generate table name
        table_name = f"Table_{sequence_order}"
        if question:
            # Sanitize question for table name
            safe_name = "".join(c for c in question[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            table_name = safe_name.replace(' ', '_') or table_name
        
        # Limit rows for sample data (keep first 100)
        sample_rows = data_rows[:100] if data_rows else []
        
        return {
            "table_name": table_name,
            "columns": column_definitions,
            "rows": sample_rows,
            "row_count": len(data_rows) if data_rows else 0,
            "metadata": {
                "component_id": component_id,
                "sequence_order": sequence_order,
                "source_query": sql_query,
                "display_name": question[:50] if question else table_name,
                "description": question
            }
        }
    
    @staticmethod
    def _infer_data_type(sample_value: Any) -> str:
        """Infer data type from sample value
        
        Returns common type names: 'int', 'float', 'bool', 'datetime', 'string'
        """
        if isinstance(sample_value, bool):
            return "bool"
        elif isinstance(sample_value, int):
            return "int"
        elif isinstance(sample_value, float):
            return "float"
        elif isinstance(sample_value, str):
            # Try to parse as number
            try:
                float(sample_value)
                if '.' in sample_value:
                    return "float"
                else:
                    return "int"
            except ValueError:
                # Check if it's a date/datetime
                try:
                    datetime.strptime(sample_value, "%Y-%m-%d")
                    return "datetime"
                except ValueError:
                    try:
                        datetime.strptime(sample_value, "%Y-%m-%d %H:%M:%S")
                        return "datetime"
                    except ValueError:
                        pass
                # Default to string
                return "string"
        else:
            return "string"


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


class IntelligentPowerBIChartAgent:
    """Intelligent agent for generating PowerBI charts using LLM analysis and Vega-Lite converter"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        self.converter = VegaLiteToPowerBIConverter(llm)
    
    async def generate_chart(
        self,
        question: str,
        sql_query: str,
        data: Dict[str, Any],
        language: str = "English",
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Intelligently generate PowerBI chart configuration
        
        Uses LLM to analyze the question, SQL, and data to determine the best chart type,
        then uses the Vega-Lite converter to create the PowerBI configuration.
        
        Args:
            question: Natural language question
            sql_query: SQL query that generated the data
            data: Data dictionary with 'columns' and 'data'
            language: Language for the chart
            existing_chart_schema: Optional existing chart schema to consider
            
        Returns:
            Dictionary with chart_config, chart_type, reasoning, and success status
        """
        try:
            columns = data.get("columns", [])
            data_rows = data.get("data", [])
            
            # Analyze data and question to determine best chart type
            analysis_prompt = f"""
            ### TASK ###
            
            Analyze the following question, SQL query, and data to determine the most appropriate PowerBI chart type.
            
            ### INPUT ###
            Question: {question}
            SQL Query: {sql_query}
            Columns: {json.dumps(columns, indent=2)}
            Sample Data (first 5 rows): {json.dumps(data_rows[:5], indent=2)}
            Language: {language}
            
            ### ANALYSIS REQUIRED ###
            
            1. **Data Analysis**:
               - What types of data are present? (categorical, numerical, temporal)
               - How many dimensions vs measures?
               - What is the cardinality of categorical fields?
            
            2. **Question Intent**:
               - What is the user trying to understand?
               - Is it a comparison, trend, distribution, or relationship?
               - Is it a KPI/metric display?
            
            3. **Chart Type Recommendation**:
               Based on the analysis, recommend the best PowerBI chart type:
               - columnChart, clusteredColumnChart, stackedColumnChart
               - lineChart, areaChart
               - pieChart, donutChart
               - scatterChart
               - barChart, clusteredBarChart, stackedBarChart
               - comboChart
               - card (for KPI)
            
            4. **Vega-Lite Schema Creation**:
               Create a Vega-Lite schema that represents the recommended chart:
               - Map columns to appropriate encodings (x, y, color, size)
               - Choose appropriate mark type
               - Set up aggregations if needed
            
            ### OUTPUT FORMAT ###
            
            Respond with ONLY a JSON object:
            {{
                "analysis": {{
                    "data_types": {{"column_name": "type"}},
                    "question_intent": "description",
                    "recommended_chart_type": "powerbi_chart_type",
                    "reasoning": "explanation"
                }},
                "vega_lite_schema": {{
                    "data": {{"values": []}},
                    "mark": {{"type": "..."}},
                    "encoding": {{...}},
                    "title": "..."
                }}
            }}
            """
            
            generation_prompt = PromptTemplate(
                input_variables=["analysis_prompt"],
                template="{analysis_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=generation_prompt)
            analysis_result = await chain.arun(analysis_prompt=analysis_prompt)
            
            # Parse analysis result
            if hasattr(analysis_result, 'content'):
                analysis_str = analysis_result.content
            else:
                analysis_str = str(analysis_result)
            
            try:
                analysis_data = orjson.loads(analysis_str)
            except orjson.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', analysis_str, re.DOTALL)
                if json_match:
                    try:
                        analysis_data = orjson.loads(json_match.group(0))
                    except orjson.JSONDecodeError:
                        logger.error("Failed to parse chart analysis")
                        return {
                            "chart_config": {},
                            "chart_type": "",
                            "reasoning": "Failed to analyze data for chart generation",
                            "success": False
                        }
                else:
                    logger.error("No JSON found in analysis result")
                    return {
                        "chart_config": {},
                        "chart_type": "",
                        "reasoning": "Failed to analyze data for chart generation",
                        "success": False
                    }
            
            # Extract Vega-Lite schema from analysis
            vega_lite_schema = analysis_data.get("vega_lite_schema", {})
            if not vega_lite_schema:
                # Fallback: create basic schema
                vega_lite_schema = {
                    "data": {"values": data_rows},
                    "mark": {"type": "bar"},
                    "encoding": {
                        "x": {"field": columns[0] if columns else "x", "type": "nominal"},
                        "y": {"field": columns[1] if len(columns) > 1 else "y", "type": "quantitative"}
                    },
                    "title": question
                }
            
            # Use converter to create PowerBI chart
            powerbi_config = await self.converter.convert(
                vega_lite_schema=vega_lite_schema,
                language=language,
                target_schema=existing_chart_schema
            )
            
            analysis_info = analysis_data.get("analysis", {})
            
            return {
                "chart_config": powerbi_config,
                "chart_type": analysis_info.get("recommended_chart_type", powerbi_config.get("visualType", "")),
                "reasoning": analysis_info.get("reasoning", "Chart generated based on data analysis"),
                "success": True,
                "analysis": analysis_info
            }
            
        except Exception as e:
            logger.error(f"Error in intelligent PowerBI chart generation: {e}")
            return {
                "chart_config": {},
                "chart_type": "",
                "reasoning": f"Error generating chart: {str(e)}",
                "success": False,
                "error": str(e)
            }


class IntelligentTableauChartAgent:
    """Intelligent agent for generating Tableau charts using LLM analysis and Vega-Lite converter"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        self.converter = VegaLiteToTableauConverter(llm)
    
    async def generate_chart(
        self,
        question: str,
        sql_query: str,
        data: Dict[str, Any],
        language: str = "English",
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Intelligently generate Tableau chart configuration
        
        Uses LLM to analyze the question, SQL, and data to determine the best chart type,
        then uses the Vega-Lite converter to create the Tableau configuration.
        
        Args:
            question: Natural language question
            sql_query: SQL query that generated the data
            data: Data dictionary with 'columns' and 'data'
            language: Language for the chart
            existing_chart_schema: Optional existing chart schema to consider
            
        Returns:
            Dictionary with chart_config, chart_type, reasoning, and success status
        """
        try:
            columns = data.get("columns", [])
            data_rows = data.get("data", [])
            
            # Analyze data and question to determine best chart type
            analysis_prompt = f"""
            ### TASK ###
            
            Analyze the following question, SQL query, and data to determine the most appropriate Tableau chart type.
            
            ### INPUT ###
            Question: {question}
            SQL Query: {sql_query}
            Columns: {json.dumps(columns, indent=2)}
            Sample Data (first 5 rows): {json.dumps(data_rows[:5], indent=2)}
            Language: {language}
            
            ### ANALYSIS REQUIRED ###
            
            1. **Data Analysis**:
               - What types of data are present? (categorical, numerical, temporal)
               - How many dimensions vs measures?
               - What is the cardinality of categorical fields?
            
            2. **Question Intent**:
               - What is the user trying to understand?
               - Is it a comparison, trend, distribution, or relationship?
               - Is it a KPI/metric display?
            
            3. **Chart Type Recommendation**:
               Based on the analysis, recommend the best Tableau chart type:
               - bar, line, area
               - pie, scatter
               - treemap, heatmap
               - histogram, box_plot
               - bullet, gantt
               - map, symbol_map, filled_map
               - kpi (for KPI displays)
            
            4. **Vega-Lite Schema Creation**:
               Create a Vega-Lite schema that represents the recommended chart:
               - Map columns to appropriate encodings (x, y, color, size)
               - Choose appropriate mark type
               - Set up aggregations if needed
            
            ### OUTPUT FORMAT ###
            
            Respond with ONLY a JSON object:
            {{
                "analysis": {{
                    "data_types": {{"column_name": "type"}},
                    "question_intent": "description",
                    "recommended_chart_type": "tableau_chart_type",
                    "reasoning": "explanation"
                }},
                "vega_lite_schema": {{
                    "data": {{"values": []}},
                    "mark": {{"type": "..."}},
                    "encoding": {{...}},
                    "title": "..."
                }}
            }}
            """
            
            generation_prompt = PromptTemplate(
                input_variables=["analysis_prompt"],
                template="{analysis_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=generation_prompt)
            analysis_result = await chain.arun(analysis_prompt=analysis_prompt)
            
            # Parse analysis result
            if hasattr(analysis_result, 'content'):
                analysis_str = analysis_result.content
            else:
                analysis_str = str(analysis_result)
            
            try:
                analysis_data = orjson.loads(analysis_str)
            except orjson.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', analysis_str, re.DOTALL)
                if json_match:
                    try:
                        analysis_data = orjson.loads(json_match.group(0))
                    except orjson.JSONDecodeError:
                        logger.error("Failed to parse chart analysis")
                        return {
                            "chart_config": {},
                            "chart_type": "",
                            "reasoning": "Failed to analyze data for chart generation",
                            "success": False
                        }
                else:
                    logger.error("No JSON found in analysis result")
                    return {
                        "chart_config": {},
                        "chart_type": "",
                        "reasoning": "Failed to analyze data for chart generation",
                        "success": False
                    }
            
            # Extract Vega-Lite schema from analysis
            vega_lite_schema = analysis_data.get("vega_lite_schema", {})
            if not vega_lite_schema:
                # Fallback: create basic schema
                vega_lite_schema = {
                    "data": {"values": data_rows},
                    "mark": {"type": "bar"},
                    "encoding": {
                        "x": {"field": columns[0] if columns else "x", "type": "nominal"},
                        "y": {"field": columns[1] if len(columns) > 1 else "y", "type": "quantitative"}
                    },
                    "title": question
                }
            
            # Use converter to create Tableau chart
            tableau_config = await self.converter.convert(
                vega_lite_schema=vega_lite_schema,
                language=language,
                target_schema=existing_chart_schema
            )
            
            analysis_info = analysis_data.get("analysis", {})
            
            return {
                "chart_config": tableau_config,
                "chart_type": analysis_info.get("recommended_chart_type", tableau_config.get("chart_type", "")),
                "reasoning": analysis_info.get("reasoning", "Chart generated based on data analysis"),
                "success": True,
                "analysis": analysis_info
            }
            
        except Exception as e:
            logger.error(f"Error in intelligent Tableau chart generation: {e}")
            return {
                "chart_config": {},
                "chart_type": "",
                "reasoning": f"Error generating chart: {str(e)}",
                "success": False,
                "error": str(e)
            }


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


class DashboardToPowerBIConverter:
    """Converter from Dashboard with thread components to PowerBI dashboard"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        # Use intelligent agent for chart generation
        self.chart_agent = IntelligentPowerBIChartAgent(self.llm)
    
    async def convert(
        self,
        dashboard: Dict[str, Any],
        language: str = "English"
    ) -> Dict[str, Any]:
        """Convert dashboard with thread components to PowerBI dashboard
        
        Args:
            dashboard: Dashboard dictionary with thread_components
            language: Language for the dashboard
            
        Returns:
            PowerBI dashboard configuration with datasets, visuals, and text boxes
        """
        try:
            thread_components = dashboard.get("thread_components", [])
            workflow_metadata = dashboard.get("workflow_metadata", {})
            project_id = dashboard.get("project_id", "default")
            
            powerbi_dashboard = {
                "dashboard_name": workflow_metadata.get("report_title", "Dashboard"),
                "dashboard_description": workflow_metadata.get("report_description", ""),
                "project_id": project_id,
                "datasets": [],
                "visuals": [],
                "text_boxes": [],
                "layout": {
                    "grid_layout": workflow_metadata.get("dashboard_layout", "auto"),
                    "refresh_rate": workflow_metadata.get("refresh_rate", 0)
                }
            }
            
            # Process each thread component
            for component in thread_components:
                component_id = component.get("id", "")
                sequence_order = component.get("sequence_order", 0)
                question = component.get("question", "")
                executive_summary = component.get("executive_summary", "")
                sql_query = component.get("sql_query", "")
                chart_schema = component.get("chart_schema") or component.get("chart_config", {}).get("chart_schema", {})
                sample_data = component.get("sample_data", {})
                thread_metadata = component.get("thread_metadata", {})
                
                # Extract common table data
                table_data = CommonDataExtractor.extract_table_data(
                    component_id=component_id,
                    question=question,
                    sql_query=sql_query,
                    sample_data=sample_data,
                    sequence_order=sequence_order
                )
                
                # Create dataset from extracted table data
                dataset = self._create_powerbi_dataset_from_table_data(
                    table_data=table_data
                )
                powerbi_dashboard["datasets"].append(dataset)
                
                # Create visual/chart from component using LangChain agent
                if chart_schema or sample_data:
                    visual = await self._create_powerbi_visual(
                        component_id=component_id,
                        question=question,
                        chart_schema=chart_schema,
                        dataset_name=dataset["api_payload"]["name"],
                        table_name=dataset["table_name"],
                        sequence_order=sequence_order,
                        language=language,
                        sql_query=sql_query,
                        sample_data=sample_data
                    )
                    if visual:
                        powerbi_dashboard["visuals"].append(visual)
                
                # Create text box from executive summary
                if executive_summary:
                    text_box = self._create_powerbi_text_box(
                        component_id=component_id,
                        question=question,
                        executive_summary=executive_summary,
                        sequence_order=sequence_order
                    )
                    powerbi_dashboard["text_boxes"].append(text_box)
            
            return powerbi_dashboard
            
        except Exception as e:
            logger.error(f"Error converting dashboard to PowerBI: {e}")
            return {}
    
    def save_to_json_files(
        self,
        powerbi_dashboard: Dict[str, Any],
        output_dir: str = "./powerbi_output"
    ) -> Dict[str, str]:
        """Save PowerBI dashboard configuration to JSON files
        
        Args:
            powerbi_dashboard: PowerBI dashboard configuration
            output_dir: Directory to save JSON files
            
        Returns:
            Dictionary mapping file types to file paths
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_files = {}
            
            # Save main dashboard configuration
            dashboard_file = output_path / f"powerbi_dashboard_{timestamp}.json"
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                json.dump(powerbi_dashboard, f, indent=2, ensure_ascii=False)
            saved_files["dashboard"] = str(dashboard_file)
            
            # Save individual dataset API payloads (ready to POST to PowerBI)
            datasets_dir = output_path / "datasets"
            datasets_dir.mkdir(exist_ok=True)
            
            for idx, dataset_info in enumerate(powerbi_dashboard.get("datasets", [])):
                dataset_payload = dataset_info.get("api_payload", {})
                dataset_metadata = dataset_info.get("metadata", {})
                
                # Save API payload (ready to POST to PowerBI REST API)
                dataset_file = datasets_dir / f"dataset_{idx+1}_{dataset_metadata.get('component_id', 'unknown')[:8]}.json"
                with open(dataset_file, 'w', encoding='utf-8') as f:
                    json.dump(dataset_payload, f, indent=2, ensure_ascii=False)
                
                # Save metadata separately
                metadata_file = datasets_dir / f"dataset_{idx+1}_{dataset_metadata.get('component_id', 'unknown')[:8]}_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(dataset_metadata, f, indent=2, ensure_ascii=False)
                
                saved_files[f"dataset_{idx+1}"] = str(dataset_file)
                saved_files[f"dataset_{idx+1}_metadata"] = str(metadata_file)
            
            # Save visuals configuration
            visuals_dir = output_path / "visuals"
            visuals_dir.mkdir(exist_ok=True)
            
            for idx, visual in enumerate(powerbi_dashboard.get("visuals", [])):
                visual_file = visuals_dir / f"visual_{idx+1}_{visual.get('component_id', 'unknown')[:8]}.json"
                with open(visual_file, 'w', encoding='utf-8') as f:
                    json.dump(visual, f, indent=2, ensure_ascii=False)
                saved_files[f"visual_{idx+1}"] = str(visual_file)
            
            # Save text boxes
            textboxes_dir = output_path / "textboxes"
            textboxes_dir.mkdir(exist_ok=True)
            
            for idx, textbox in enumerate(powerbi_dashboard.get("text_boxes", [])):
                textbox_file = textboxes_dir / f"textbox_{idx+1}_{textbox.get('component_id', 'unknown')[:8]}.json"
                with open(textbox_file, 'w', encoding='utf-8') as f:
                    json.dump(textbox, f, indent=2, ensure_ascii=False)
                saved_files[f"textbox_{idx+1}"] = str(textbox_file)
            
            logger.info(f"Saved PowerBI dashboard configuration to {output_dir}")
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving PowerBI dashboard to JSON files: {e}")
            return {}
    
    def _create_powerbi_dataset_from_table_data(
        self,
        table_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create PowerBI dataset configuration in REST API format from common table data
        
        Args:
            table_data: Common table data structure from CommonDataExtractor
            
        Returns dataset in PowerBI REST API format for POST /datasets endpoint:
        https://learn.microsoft.com/en-us/rest/api/power-bi/push-datasets/datasets-post-dataset
        """
        columns = table_data.get("columns", [])
        table_name = table_data.get("table_name", "Table1")
        metadata = table_data.get("metadata", {})
        
        # Map common types to PowerBI data types
        # PowerBI data types: Int64, Double, Bool, DateTime, String, Decimal
        powerbi_columns = []
        for col_def in columns:
            col_name = col_def.get("name", "")
            inferred_type = col_def.get("inferred_type", "string")
            sample_value = col_def.get("sample_value")
            
            # Map to PowerBI data type
            powerbi_type = self._map_to_powerbi_datatype(inferred_type, sample_value)
            
            column_def = {
                "name": col_name,
                "dataType": powerbi_type
            }
            
            # Add formatString for numeric types if appropriate
            if powerbi_type in ["Int64", "Double", "Decimal"]:
                if isinstance(sample_value, str) and "%" in sample_value:
                    column_def["formatString"] = "0.00%"
            
            powerbi_columns.append(column_def)
        
        # Create dataset name from metadata
        component_id = metadata.get("component_id", "")
        sequence_order = metadata.get("sequence_order", 0)
        display_name = metadata.get("display_name", "")
        
        dataset_name = f"Dataset_{sequence_order}_{component_id[:8]}"
        if display_name:
            safe_name = "".join(c for c in display_name[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
            dataset_name = safe_name.replace(' ', '_') or dataset_name
        
        # Create dataset in PowerBI REST API format
        dataset = {
            "name": dataset_name,
            "defaultMode": "Push",  # Can be "Push" or "Streaming" or "Import"
            "tables": [
                {
                    "name": table_name,
                    "columns": powerbi_columns
                }
            ]
        }
        
        return {
            "api_payload": dataset,  # This is what gets POSTed to PowerBI API
            "metadata": metadata,
            "table_name": table_name,
            "table_data": table_data  # Keep reference to original table data
        }
    
    def _map_to_powerbi_datatype(self, inferred_type: str, sample_value: Any = None) -> str:
        """Map common inferred type to PowerBI data type"""
        type_mapping = {
            "int": "Int64",
            "float": "Double",
            "bool": "Bool",
            "datetime": "DateTime",
            "string": "String"
        }
        return type_mapping.get(inferred_type, "String")
    
    
    async def _create_powerbi_visual(
        self,
        component_id: str,
        question: str,
        chart_schema: Dict[str, Any],
        dataset_name: str,
        table_name: str,
        sequence_order: int,
        language: str,
        sql_query: str,
        sample_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create PowerBI visual/chart from component using LangChain agent
        
        Uses PowerBIChartGenerationAgent to intelligently generate the most
        appropriate chart configuration based on the data and question.
        """
        try:
            # Use LangChain agent to generate PowerBI chart configuration
            # This agent analyzes the data, question, and SQL to create the best chart
            chart_result = await self.chart_agent.generate_chart(
                query=question,
                sql=sql_query,
                data=sample_data,
                language=language,
                remove_data_from_chart_config=True,
                existing_chart_schema=chart_schema  # Use existing schema as reference
            )
            
            if not chart_result or not chart_result.get("success", True):
                logger.warning(f"Chart generation failed for component {component_id}: {chart_result.get('error', 'Unknown error')}")
                return None
            
            chart_config = chart_result.get("chart_config", {})
            if not chart_config:
                logger.warning(f"Empty chart config for component {component_id}")
                return None
            
            # Extract title from chart config, chart schema, or question
            title = (
                chart_config.get("title") or 
                chart_schema.get("title") or 
                question or 
                f"Visual {sequence_order}"
            )
            
            visual = {
                "id": f"{component_id}_visual",
                "component_id": component_id,
                "name": title[:100],
                "visualType": chart_config.get("visualType", chart_result.get("chart_type", "columnChart")),
                "dataset": dataset_name,
                "table": table_name,
                "dataRoles": chart_config.get("dataRoles", {}),
                "formatting": chart_config.get("formatting", {}),
                "title": title,
                "reasoning": chart_result.get("reasoning", ""),
                "metadata": {
                    "component_id": component_id,
                    "sequence_order": sequence_order,
                    "question": question,
                    "chart_type": chart_result.get("chart_type", ""),
                    "generated_by": "IntelligentPowerBIChartAgent"
                }
            }
            
            return visual
            
        except Exception as e:
            logger.error(f"Error creating PowerBI visual with agent: {e}")
            return None
    
    def _create_powerbi_text_box(
        self,
        component_id: str,
        question: str,
        executive_summary: str,
        sequence_order: int
    ) -> Dict[str, Any]:
        """Create PowerBI text box from executive summary"""
        return {
            "id": f"{component_id}_textbox",
            "component_id": component_id,
            "name": f"Summary {sequence_order}",
            "visualType": "textbox",
            "content": executive_summary,
            "title": question or f"Summary {sequence_order}",
            "formatting": {
                "fontSize": 12,
                "fontFamily": "Segoe UI",
                "backgroundColor": "#ffffff",
                "textColor": "#000000"
            },
            "metadata": {
                "component_id": component_id,
                "sequence_order": sequence_order,
                "question": question
            }
        }


class DashboardToTableauConverter:
    """Converter from Dashboard with thread components to Tableau dashboard"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        # Use intelligent agent for chart generation
        self.chart_agent = IntelligentTableauChartAgent(self.llm)
    
    async def convert(
        self,
        dashboard: Dict[str, Any],
        language: str = "English"
    ) -> Dict[str, Any]:
        """Convert dashboard with thread components to Tableau dashboard
        
        Args:
            dashboard: Dashboard dictionary with thread_components
            language: Language for the dashboard
            
        Returns:
            Tableau dashboard configuration with datasources, worksheets, and text objects
        """
        try:
            thread_components = dashboard.get("thread_components", [])
            workflow_metadata = dashboard.get("workflow_metadata", {})
            project_id = dashboard.get("project_id", "default")
            
            tableau_dashboard = {
                "workbook_name": workflow_metadata.get("report_title", "Dashboard"),
                "workbook_description": workflow_metadata.get("report_description", ""),
                "project_id": project_id,
                "datasources": [],
                "worksheets": [],
                "text_objects": [],
                "dashboard_layout": {
                    "layout": workflow_metadata.get("dashboard_layout", "auto"),
                    "refresh_rate": workflow_metadata.get("refresh_rate", 0)
                }
            }
            
            # Process each thread component
            for component in thread_components:
                component_id = component.get("id", "")
                sequence_order = component.get("sequence_order", 0)
                question = component.get("question", "")
                executive_summary = component.get("executive_summary", "")
                sql_query = component.get("sql_query", "")
                chart_schema = component.get("chart_schema") or component.get("chart_config", {}).get("chart_schema", {})
                sample_data = component.get("sample_data", {})
                thread_metadata = component.get("thread_metadata", {})
                
                # Extract common table data
                table_data = CommonDataExtractor.extract_table_data(
                    component_id=component_id,
                    question=question,
                    sql_query=sql_query,
                    sample_data=sample_data,
                    sequence_order=sequence_order
                )
                
                # Create datasource from extracted table data
                datasource = self._create_tableau_datasource_from_table_data(
                    table_data=table_data
                )
                tableau_dashboard["datasources"].append(datasource)
                
                # Create worksheet/chart from component using LangChain agent
                if chart_schema or sample_data:
                    worksheet = await self._create_tableau_worksheet(
                        component_id=component_id,
                        question=question,
                        chart_schema=chart_schema,
                        datasource_name=datasource["name"],
                        sequence_order=sequence_order,
                        language=language,
                        sql_query=sql_query,
                        sample_data=sample_data
                    )
                    if worksheet:
                        tableau_dashboard["worksheets"].append(worksheet)
                
                # Create text object from executive summary
                if executive_summary:
                    text_object = self._create_tableau_text_object(
                        component_id=component_id,
                        question=question,
                        executive_summary=executive_summary,
                        sequence_order=sequence_order
                    )
                    tableau_dashboard["text_objects"].append(text_object)
            
            return tableau_dashboard
            
        except Exception as e:
            logger.error(f"Error converting dashboard to Tableau: {e}")
            return {}
    
    def save_to_json_files(
        self,
        tableau_dashboard: Dict[str, Any],
        output_dir: str = "./tableau_output"
    ) -> Dict[str, str]:
        """Save Tableau dashboard configuration to JSON files and Hyper API code
        
        Args:
            tableau_dashboard: Tableau dashboard configuration
            output_dir: Directory to save JSON files and Python code
            
        Returns:
            Dictionary mapping file types to file paths
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_files = {}
            
            # Save main dashboard configuration
            dashboard_file = output_path / f"tableau_dashboard_{timestamp}.json"
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                json.dump(tableau_dashboard, f, indent=2, ensure_ascii=False)
            saved_files["dashboard"] = str(dashboard_file)
            
            # Save individual datasource Hyper API configurations
            datasources_dir = output_path / "datasources"
            datasources_dir.mkdir(exist_ok=True)
            
            hyper_code_dir = output_path / "hyper_api_code"
            hyper_code_dir.mkdir(exist_ok=True)
            
            for idx, datasource_info in enumerate(tableau_dashboard.get("datasources", [])):
                datasource_metadata = datasource_info.get("metadata", {})
                component_id = datasource_metadata.get("component_id", "unknown")
                
                # Save datasource configuration
                datasource_file = datasources_dir / f"datasource_{idx+1}_{component_id[:8]}.json"
                with open(datasource_file, 'w', encoding='utf-8') as f:
                    json.dump(datasource_info, f, indent=2, ensure_ascii=False)
                saved_files[f"datasource_{idx+1}"] = str(datasource_file)
                
                # Save Hyper API Python code if available
                hyper_api = datasource_info.get("hyper_api", {})
                if hyper_api and hyper_api.get("python_code_template"):
                    code_file = hyper_code_dir / f"create_hyper_{idx+1}_{component_id[:8]}.py"
                    with open(code_file, 'w', encoding='utf-8') as f:
                        f.write(hyper_api["python_code_template"])
                    saved_files[f"hyper_code_{idx+1}"] = str(code_file)
            
            # Save worksheets configuration
            worksheets_dir = output_path / "worksheets"
            worksheets_dir.mkdir(exist_ok=True)
            
            for idx, worksheet in enumerate(tableau_dashboard.get("worksheets", [])):
                worksheet_file = worksheets_dir / f"worksheet_{idx+1}_{worksheet.get('component_id', 'unknown')[:8]}.json"
                with open(worksheet_file, 'w', encoding='utf-8') as f:
                    json.dump(worksheet, f, indent=2, ensure_ascii=False)
                saved_files[f"worksheet_{idx+1}"] = str(worksheet_file)
            
            # Save text objects
            text_objects_dir = output_path / "text_objects"
            text_objects_dir.mkdir(exist_ok=True)
            
            for idx, text_obj in enumerate(tableau_dashboard.get("text_objects", [])):
                text_file = text_objects_dir / f"text_object_{idx+1}_{text_obj.get('component_id', 'unknown')[:8]}.json"
                with open(text_file, 'w', encoding='utf-8') as f:
                    json.dump(text_obj, f, indent=2, ensure_ascii=False)
                saved_files[f"text_object_{idx+1}"] = str(text_file)
            
            logger.info(f"Saved Tableau dashboard configuration to {output_dir}")
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving Tableau dashboard to JSON files: {e}")
            return {}
    
    def _create_tableau_datasource_from_table_data(
        self,
        table_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create Tableau datasource configuration in Hyper API format from common table data
        
        Generates TableDefinition compatible with Tableau Hyper API:
        https://github.com/tableau/hyper-api-samples/blob/main/Tableau-Supported/Python/insert_data_into_multiple_tables.py
        
        Args:
            table_data: Common table data structure from CommonDataExtractor
        """
        columns = table_data.get("columns", [])
        table_name = table_data.get("table_name", "Table1")
        metadata = table_data.get("metadata", {})
        rows = table_data.get("rows", [])
        
        # Create Hyper API TableDefinition columns
        hyper_columns = []
        tableau_fields = []
        
        for col_def in columns:
            col_name = col_def.get("name", "")
            inferred_type = col_def.get("inferred_type", "string")
            sample_value = col_def.get("sample_value")
            
            # Map to Hyper API SqlType and nullability
            hyper_type, nullability, tableau_type, role, aggregation = self._map_to_hyper_api_type(
                inferred_type, sample_value, rows, col_name
            )
            
            # Create Hyper API column definition
            hyper_column = {
                "name": col_name,
                "type": hyper_type,  # e.g., "SqlType.text()", "SqlType.double()"
                "nullability": nullability  # "NOT_NULLABLE" or "NULLABLE"
            }
            hyper_columns.append(hyper_column)
            
            # Also create Tableau field metadata
            tableau_field = {
                "name": col_name,
                "type": tableau_type,
                "role": role,
                "datatype": tableau_type
            }
            if aggregation:
                tableau_field["aggregation"] = aggregation
            tableau_fields.append(tableau_field)
        
        # Create datasource name from metadata
        component_id = metadata.get("component_id", "")
        sequence_order = metadata.get("sequence_order", 0)
        display_name = metadata.get("display_name", "")
        
        datasource_name = f"Datasource_{sequence_order}_{component_id[:8]}"
        if display_name:
            safe_name = "".join(c for c in display_name[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
            datasource_name = safe_name.replace(' ', '_') or datasource_name
        
        # Create Hyper API TableDefinition structure
        table_definition = {
            "table_name": table_name,
            "columns": hyper_columns
        }
        
        # Prepare data rows for insertion (limit to reasonable size)
        data_rows = rows[:1000] if rows else []
        
        return {
            "id": component_id,
            "name": datasource_name,
            "displayName": display_name or datasource_name,
            "description": metadata.get("description", ""),
            "connection": "extract",
            "query": metadata.get("source_query", ""),
            "hyper_api": {
                "table_definition": table_definition,
                "data_rows": data_rows,
                "python_code_template": self._generate_hyper_api_code(
                    table_name, hyper_columns, data_rows, datasource_name
                )
            },
            "fields": tableau_fields,  # For Tableau worksheet configuration
            "metadata": metadata,
            "table_data": table_data  # Keep reference to original table data
        }
    
    def _map_to_hyper_api_type(
        self, 
        inferred_type: str, 
        sample_value: Any = None,
        rows: List[Dict[str, Any]] = None,
        col_name: str = ""
    ) -> tuple:
        """Map common inferred type to Hyper API SqlType, nullability, and Tableau field info
        
        Returns:
            Tuple of (hyper_type_str, nullability, tableau_type, role, aggregation)
        """
        # Determine nullability based on sample data
        has_nulls = False
        if rows and len(rows) > 0:
            has_nulls = any(row.get(col_name) is None for row in rows[:100])
        
        nullability = "NULLABLE" if has_nulls else "NOT_NULLABLE"
        
        if inferred_type == "int":
            # Use small_int for small values, big_int for large values
            if sample_value is not None and isinstance(sample_value, int):
                if -32768 <= sample_value <= 32767:
                    hyper_type = "SqlType.small_int()"
                else:
                    hyper_type = "SqlType.big_int()"
            else:
                hyper_type = "SqlType.big_int()"
            return (hyper_type, nullability, "integer", "measure", "sum")
        elif inferred_type == "float":
            hyper_type = "SqlType.double()"
            return (hyper_type, nullability, "real", "measure", "sum")
        elif inferred_type == "bool":
            hyper_type = "SqlType.bool()"
            return (hyper_type, nullability, "boolean", "dimension", None)
        elif inferred_type == "datetime":
            hyper_type = "SqlType.date()"
            return (hyper_type, nullability, "date", "dimension", None)
        else:  # string
            hyper_type = "SqlType.text()"
            return (hyper_type, nullability, "string", "dimension", None)
    
    def _map_to_tableau_field(self, inferred_type: str, sample_value: Any = None) -> tuple:
        """Map common inferred type to Tableau field type, role, and aggregation
        
        Returns:
            Tuple of (tableau_type, role, aggregation)
        """
        _, _, tableau_type, role, aggregation = self._map_to_hyper_api_type(
            inferred_type, sample_value
        )
        return (tableau_type, role, aggregation)
    
    def _generate_hyper_api_code(
        self,
        table_name: str,
        hyper_columns: List[Dict[str, Any]],
        data_rows: List[Any],
        datasource_name: str
    ) -> str:
        """Generate Python code template for creating Hyper file using Tableau Hyper API
        
        Based on: https://github.com/tableau/hyper-api-samples/blob/main/Tableau-Supported/Python/insert_data_into_multiple_tables.py
        """
        # Escape table name for Python
        safe_table_name = table_name.replace(' ', '_').replace('-', '_')
        
        # Generate column definitions
        column_defs = []
        for col in hyper_columns:
            col_name = col["name"]
            col_type = col["type"]
            nullability = col["nullability"]
            column_defs.append(
                f'        TableDefinition.Column(name="{col_name}", type={col_type}, nullability={nullability})'
            )
        
        column_defs_str = ",\n".join(column_defs)
        
        # Generate data insertion code
        data_insertion = ""
        if data_rows and len(data_rows) > 0:
            # Convert rows to Python list format
            # Handle both dict rows and list rows
            row_data = []
            for row in data_rows[:10]:  # Limit to 10 rows for template
                row_values = []
                for col in hyper_columns:
                    col_name = col["name"]
                    # Handle dict or list row format
                    if isinstance(row, dict):
                        value = row.get(col_name)
                    elif isinstance(row, list):
                        # Assume columns are in order
                        col_idx = hyper_columns.index(col)
                        value = row[col_idx] if col_idx < len(row) else None
                    else:
                        value = None
                    
                    # Format value for Python code
                    if value is None:
                        row_values.append("None")
                    elif isinstance(value, str):
                        # Escape quotes in strings
                        escaped_value = value.replace('"', '\\"')
                        row_values.append(f'"{escaped_value}"')
                    elif isinstance(value, (int, float)):
                        row_values.append(str(value))
                    elif isinstance(value, bool):
                        row_values.append(str(value))
                    elif isinstance(value, datetime):
                        row_values.append(f'datetime({value.year}, {value.month}, {value.day})')
                    else:
                        row_values.append(f'"{str(value)}"')
                row_data.append(f"                [{', '.join(row_values)}]")
            
            if row_data:
                data_insertion = f"""
            # Insert data into {safe_table_name} table
            {safe_table_name}_data_to_insert = [
{chr(10).join(row_data)}
            ]
            
            with Inserter(connection, {safe_table_name}_table) as inserter:
                inserter.add_rows(rows={safe_table_name}_data_to_insert)
                inserter.execute()
"""
        
        code_template = f'''from datetime import datetime
from pathlib import Path

from tableauhyperapi import HyperProcess, Telemetry, \\
    Connection, CreateMode, \\
    NOT_NULLABLE, NULLABLE, SqlType, TableDefinition, \\
    Inserter, \\
    escape_name, escape_string_literal, \\
    HyperException

# Table Definition for {table_name}
{safe_table_name}_table = TableDefinition(
    table_name="{table_name}",
    columns=[
{column_defs_str}
    ]
)


def create_{safe_table_name}_hyper_file():
    """
    Create a Hyper file for {datasource_name} with table {table_name}
    """
    path_to_database = Path("{datasource_name}.hyper")
    
    with HyperProcess(telemetry=Telemetry.SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(
            endpoint=hyper.endpoint,
            database=path_to_database,
            create_mode=CreateMode.CREATE_AND_REPLACE
        ) as connection:
            # Create table
            connection.catalog.create_table(table_definition={safe_table_name}_table)
{data_insertion}
            # Verify row count
            row_count = connection.execute_scalar_query(
                query=f"SELECT COUNT(*) FROM {{escape_name({safe_table_name}_table.table_name)}}"
            )
            print(f"The number of rows in table {table_name} is {{row_count}}.")
    
    print(f"Hyper file created: {{path_to_database}}")


if __name__ == '__main__':
    try:
        create_{safe_table_name}_hyper_file()
    except HyperException as ex:
        print(ex)
        exit(1)
'''
        return code_template
    
    async def _create_tableau_worksheet(
        self,
        component_id: str,
        question: str,
        chart_schema: Dict[str, Any],
        datasource_name: str,
        sequence_order: int,
        language: str,
        sql_query: str,
        sample_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create Tableau worksheet/chart from component using LangChain agent
        
        Uses TableauChartGenerationAgent to intelligently generate the most
        appropriate chart configuration based on the data and question.
        """
        try:
            # Use LangChain agent to generate Tableau chart configuration
            # This agent analyzes the data, question, and SQL to create the best chart
            chart_result = await self.chart_agent.generate_chart(
                query=question,
                sql=sql_query,
                data=sample_data,
                language=language,
                remove_data_from_chart_config=True,
                existing_chart_schema=chart_schema  # Use existing schema as reference
            )
            
            if not chart_result or not chart_result.get("success", True):
                logger.warning(f"Chart generation failed for component {component_id}: {chart_result.get('error', 'Unknown error')}")
                return None
            
            chart_config = chart_result.get("chart_config", {})
            if not chart_config:
                logger.warning(f"Empty chart config for component {component_id}")
                return None
            
            # Extract title from chart config, chart schema, or question
            title = (
                chart_config.get("title") or 
                chart_config.get("formatting", {}).get("title") or
                chart_schema.get("title") or 
                question or 
                f"Worksheet {sequence_order}"
            )
            
            # Extract shelf configuration from chart_config
            # Tableau uses a shelf-based structure
            shelf_config = chart_config.get("shelf", {})
            worksheet_config = chart_config.get("worksheet", {})
            view_config = worksheet_config.get("view", {}) if worksheet_config else {}
            
            worksheet = {
                "id": f"{component_id}_worksheet",
                "component_id": component_id,
                "name": title[:100],
                "datasource": datasource_name,
                "chart_type": chart_result.get("chart_type", chart_config.get("chart_type", "bar")),
                "rows": shelf_config.get("rows", view_config.get("shelf", {}).get("rows", [])),
                "columns": shelf_config.get("columns", view_config.get("shelf", {}).get("columns", [])),
                "color": shelf_config.get("color", view_config.get("shelf", {}).get("color", {})),
                "size": shelf_config.get("size", view_config.get("shelf", {}).get("size", {})),
                "label": shelf_config.get("label", view_config.get("shelf", {}).get("label", [])),
                "detail": shelf_config.get("detail", view_config.get("shelf", {}).get("detail", [])),
                "tooltip": shelf_config.get("tooltip", view_config.get("shelf", {}).get("tooltip", [])),
                "filter": view_config.get("filter", chart_config.get("filter", [])),
                "mark": view_config.get("mark", chart_config.get("mark", {"type": "bar"})),
                "axes": chart_config.get("axes", view_config.get("axes", {})),
                "title": title,
                "formatting": chart_config.get("formatting", {}),
                "reasoning": chart_result.get("reasoning", ""),
                "metadata": {
                    "component_id": component_id,
                    "sequence_order": sequence_order,
                    "question": question,
                    "chart_type": chart_result.get("chart_type", ""),
                    "generated_by": "IntelligentTableauChartAgent"
                }
            }
            
            return worksheet
            
        except Exception as e:
            logger.error(f"Error creating Tableau worksheet with agent: {e}")
            return None
    
    def _create_tableau_text_object(
        self,
        component_id: str,
        question: str,
        executive_summary: str,
        sequence_order: int
    ) -> Dict[str, Any]:
        """Create Tableau text object from executive summary"""
        return {
            "id": f"{component_id}_text",
            "component_id": component_id,
            "name": f"Summary {sequence_order}",
            "type": "text",
            "content": executive_summary,
            "title": question or f"Summary {sequence_order}",
            "formatting": {
                "fontSize": 12,
                "fontFamily": "Tableau Book",
                "backgroundColor": "#ffffff",
                "textColor": "#000000"
            },
            "metadata": {
                "component_id": component_id,
                "sequence_order": sequence_order,
                "question": question
            }
        }


# Factory functions for dashboard conversion tools
def create_dashboard_to_powerbi_tool(llm=None) -> Tool:
    """Create LangChain tool for converting dashboard to PowerBI"""
    converter = DashboardToPowerBIConverter(llm)
    
    def convert_func(input_json: str) -> str:
        """Convert dashboard with thread components to PowerBI dashboard
        
        Input: JSON string with dashboard object containing:
        - dashboard: Dashboard dict with thread_components, workflow_metadata, project_id
        - language: Optional language (default: "English")
        - save_to_files: Optional boolean to save JSON files (default: False)
        - output_dir: Optional output directory (default: "./powerbi_output")
        """
        try:
            input_data = orjson.loads(input_json)
            dashboard = input_data.get("dashboard", {})
            language = input_data.get("language", "English")
            save_to_files = input_data.get("save_to_files", False)
            output_dir = input_data.get("output_dir", "./powerbi_output")
            
            result = asyncio.run(converter.convert(dashboard, language))
            
            response = {
                "success": True,
                "powerbi_dashboard": result,
                "target_format": "powerbi"
            }
            
            # Save to JSON files if requested
            if save_to_files and result:
                saved_files = converter.save_to_json_files(result, output_dir)
                response["saved_files"] = saved_files
                response["output_directory"] = output_dir
            
            return orjson.dumps(response).decode()
        except Exception as e:
            logger.error(f"Error in dashboard to PowerBI conversion: {e}")
            return orjson.dumps({
                "success": False,
                "error": str(e),
                "powerbi_dashboard": {},
                "target_format": "powerbi"
            }).decode()
    
    return Tool(
        name="dashboard_to_powerbi_converter",
        description="Converts a dashboard with thread components to PowerBI dashboard format. Input should be a JSON object with 'dashboard' (dict containing thread_components, workflow_metadata, project_id), optional 'language' (string, default: 'English'), optional 'save_to_files' (boolean, default: False), and optional 'output_dir' (string, default: './powerbi_output'). Returns PowerBI dashboard with datasets in REST API format (ready to POST to https://learn.microsoft.com/en-us/rest/api/power-bi/datasets), visuals, and text boxes. If save_to_files is true, saves JSON files to output_dir.",
        func=convert_func
    )


def create_dashboard_to_tableau_tool(llm=None) -> Tool:
    """Create LangChain tool for converting dashboard to Tableau"""
    converter = DashboardToTableauConverter(llm)
    
    def convert_func(input_json: str) -> str:
        """Convert dashboard with thread components to Tableau dashboard
        
        Input: JSON string with dashboard object containing:
        - dashboard: Dashboard dict with thread_components, workflow_metadata, project_id
        - language: Optional language (default: "English")
        - save_to_files: Optional boolean to save JSON files (default: False)
        - output_dir: Optional output directory (default: "./tableau_output")
        """
        try:
            input_data = orjson.loads(input_json)
            dashboard = input_data.get("dashboard", {})
            language = input_data.get("language", "English")
            save_to_files = input_data.get("save_to_files", False)
            output_dir = input_data.get("output_dir", "./tableau_output")
            
            result = asyncio.run(converter.convert(dashboard, language))
            
            response = {
                "success": True,
                "tableau_dashboard": result,
                "target_format": "tableau"
            }
            
            # Save to JSON files if requested
            if save_to_files and result:
                saved_files = converter.save_to_json_files(result, output_dir)
                response["saved_files"] = saved_files
                response["output_directory"] = output_dir
            
            return orjson.dumps(response).decode()
        except Exception as e:
            logger.error(f"Error in dashboard to Tableau conversion: {e}")
            return orjson.dumps({
                "success": False,
                "error": str(e),
                "tableau_dashboard": {},
                "target_format": "tableau"
            }).decode()
    
    return Tool(
        name="dashboard_to_tableau_converter",
        description="Converts a dashboard with thread components to Tableau dashboard format. Input should be a JSON object with 'dashboard' (dict containing thread_components, workflow_metadata, project_id), optional 'language' (string, default: 'English'), optional 'save_to_files' (boolean, default: False), and optional 'output_dir' (string, default: './tableau_output'). Returns Tableau dashboard with datasources in Hyper API format (ready to create .hyper files using tableauhyperapi), worksheets, and text objects. If save_to_files is true, saves JSON files and Python Hyper API code templates to output_dir.",
        func=convert_func
    )

