import logging
from typing import Any, Dict, Optional, List
import asyncio
import os
import json

import orjson

# Use centralized agent creation utility (imports AgentExecutor from there)
from app.agents.utils.agent_utils import create_agent_with_executor, AgentExecutor

# Import Tool using modern LangChain paths
try:
    from langchain_core.tools import Tool
except ImportError:
    try:
        from langchain.tools import Tool
    except ImportError:
        from langchain.agents import Tool

# Import prompts using modern LangChain paths
try:
    from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate, ChatPromptTemplate
# Import messages using modern LangChain paths
try:
    from langchain_core.messages import SystemMessage, HumanMessage
except ImportError:
    from langchain.schema import SystemMessage, HumanMessage


from app.agents.nodes.sql.utils.chart import (
    ChartDataPreprocessor,
    ChartGenerationPostProcessor,
    ChartGenerationResults,
    chart_generation_instructions,
    create_chart_data_preprocessor_tool,
    create_chart_postprocessor_tool,
    VegaLiteChartExporter,
    ChartExecutor,
    ChartExecutionConfig,
    execute_chart_with_sql,
)

from app.core.dependencies import get_llm
from app.settings import get_settings

logger = logging.getLogger("lexy-ai-service")


class VegaLiteChartGenerationAgent:
    """Langchain agent for Vega-Lite chart generation"""
    
    def __init__(self, vega_schema: Optional[Dict[str, Any]] = None, **kwargs):
        self.llm = get_llm()
        self.vega_schema = vega_schema or {}
        self.data_preprocessor = ChartDataPreprocessor()
        self.post_processor = ChartGenerationPostProcessor()
        self.exporter = VegaLiteChartExporter()
        
        # Create tools
        self.tools = [
            create_chart_data_preprocessor_tool(),
            create_chart_postprocessor_tool(),
        ]
        
        # Initialize agent
        self.agent = self._create_agent()
        
        # System prompt for Vega-Lite chart generation
        self.system_prompt = f"""
        ### TASK ###
        
        You are a data analyst great at visualizing data using vega-lite! Given the user's question, SQL, sample data and sample column values, you need to generate vega-lite schema in JSON and provide suitable chart type.
        Besides, you need to give a concise and easy-to-understand reasoning to describe why you provide such vega-lite schema based on the question, SQL, sample data and sample column values.
        
        {chart_generation_instructions}
        
        ### EXISTING CHART SCHEMA CONSIDERATION ###
        
        If an existing chart schema is provided, you should:
        1. FIRST evaluate if the existing chart schema is suitable for the current data and query
        2. If the existing schema is appropriate, REUSE it with minimal modifications (like updating field names to match current data)
        3. If the existing schema is not suitable, generate a new one that better fits the current requirements
        4. In your reasoning, explain whether you reused the existing schema or generated a new one and why
        
        When reusing an existing schema:
        - Keep the same chart type and overall structure
        - Update field names to match the current data columns
        - Preserve styling, colors, and layout preferences
        - Only modify what's necessary for the new data
        
        ### DATA SIZE CONSIDERATIONS ###
        
        IMPORTANT: Before selecting a chart type, check the data size (number of rows in the sample data):
        - If the data has MORE than 5 rows, you MUST NOT recommend KPI charts (also known as metric cards, gauge charts, or single-value visualizations)
        - KPI charts are only suitable for datasets with 5 or fewer rows, as they display individual metrics that cannot effectively render when there are many data points
        - For datasets with more than 5 rows, choose from other appropriate chart types such as:
          * Line charts for trends over time
          * Bar charts for categorical comparisons
          * Pie charts for part-to-whole relationships
          * Area charts for cumulative trends
          * Scatter plots for correlations
          * And other suitable visualization types based on the data structure
        
        Always count the rows in the sample data before making your chart type recommendation.
        
        ### CRITICAL INSTRUCTION ###
        
        You MUST respond with ONLY a valid JSON object. Do NOT include:
        - Any text before the JSON
        - Any text after the JSON  
        - Markdown formatting
        - Code blocks
        - Explanations outside the JSON
        
        Your entire response should be a single JSON object starting with {{ and ending with }}.
        
        ### OUTPUT FORMAT ###
        
        {{
            "reasoning": "<REASON_TO_CHOOSE_THE_SCHEMA_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>",
            "chart_type": "line" | "multi_line" | "bar" | "pie" | "grouped_bar" | "stacked_bar" | "area" | "",
            "chart_schema": <VEGA_LITE_JSON_SCHEMA>
        }}
        
        ### EXAMPLES ###
        
        For a bar chart:
        {{
            "reasoning": "A bar chart is chosen to compare sales across different regions",
            "chart_type": "bar",
            "chart_schema": {{
                "title": "Sales by Region",
                "mark": {{"type": "bar"}},
                "encoding": {{
                    "x": {{"field": "Region", "type": "nominal", "title": "Region"}},
                    "y": {{"field": "Sales", "type": "quantitative", "title": "Sales"}}
                }}
            }}
        }}
        
        For no suitable chart:
        {{
            "reasoning": "The data is not suitable for visualization",
            "chart_type": "",
            "chart_schema": {{}}
        }}
        """
        
        # User prompt template
        self.user_prompt_template = PromptTemplate(
            input_variables=["query", "sql", "sample_data", "sample_column_values", "language", "existing_chart_schema"],
            template="""
            ### INPUT ###
            Question: {query}
            SQL: {sql}
            Sample Data: {sample_data}
            Sample Column Values: {sample_column_values}
            Language: {language}
            Existing Chart Schema: {existing_chart_schema}
            
            Please think step by step
            """
        )
    
    def _create_agent(self) -> Optional[AgentExecutor]:
        """Create and configure the Langchain agent"""
        try:
            # Create tools with proper function definitions
            tools = [
                Tool(
                    name="preprocess_data",
                    func=lambda x: self.data_preprocessor.run(orjson.loads(x)),
                    description="Preprocess the input data for chart generation"
                ),
                Tool(
                    name="postprocess_chart",
                    func=lambda x: self.post_processor.run(
                        x,
                        self.vega_schema,
                        [],  # Empty sample data as it will be provided in the actual call
                        True  # Default to removing data from chart schema
                    ),
                    description="Post-process the generated chart schema"
                )
            ]
            
            if not tools:
                logger.warning("No tools available for agent initialization")
                return None
            
            # Use centralized utility to create agent
            return create_agent_with_executor(
                llm=self.llm,
                tools=tools,
                use_react_agent=True,
                executor_kwargs={
                    "max_iterations": 3,
                    "early_stopping_method": "generate"
                }
            )
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise
    
    async def generate_chart(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_schema: bool = True,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate Vega-Lite chart schema using the agent
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_schema: Whether to remove data from schema
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        try:
            # Preprocess data
            preprocessed_data = self.data_preprocessor.run(data)
            
            # Create the prompt with existing chart schema if provided
            prompt = self.user_prompt_template.format(
                query=query,
                sql=sql,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                language=language,
                existing_chart_schema=json.dumps(existing_chart_schema) if existing_chart_schema else "None"
            )
            
            # Generate chart using LLM directly (more controlled approach)
            chart_result = await self._generate_chart_direct(prompt)
            
            # Post-process the result
            final_result = self.post_processor.run(
                chart_result,
                self.vega_schema,
                preprocessed_data["sample_data"],
                remove_data_from_chart_schema
            )
            print("final_result for vega lite chart generation", final_result)
            return final_result
            
        except Exception as e:
            logger.error(f"Error in chart generation: {e}")
            return {
                "chart_schema": {},
                "reasoning": f"Error generating chart: {str(e)}",
                "chart_type": "",
                "success": False,
                "error": str(e)
            }
    
    async def _generate_chart_direct(self, prompt: str) -> str:
        """Generate chart using LLM directly with structured output"""
        try:
            # Create a chain for structured output using piping operator
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Use piping operator for more concise chaining
            result = (
                generation_prompt
                | self.llm
            ).invoke({
                "system_prompt": self.system_prompt,
                "user_prompt": prompt
            })
            
            # Extract content from the response
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            logger.info(f"Raw LLM response: {result_str}")
            
            # Try to parse as JSON to validate
            try:
                # First try to parse the raw result
                parsed = orjson.loads(result_str)
                logger.info(f"Successfully parsed JSON directly: {parsed}")
                return orjson.dumps(parsed).decode('utf-8')
            except orjson.JSONDecodeError:
                # If parsing fails, try to extract JSON from the text
                import re
                
                # Look for JSON blocks in the text
                json_patterns = [
                    r'```json\s*(\{.*?\})\s*```',  # JSON code blocks
                    r'```\s*(\{.*?\})\s*```',      # Generic code blocks
                    r'(\{.*?\})',                  # Any JSON object
                ]
                
                for pattern in json_patterns:
                    json_matches = re.findall(pattern, result_str, re.DOTALL)
                    for match in json_matches:
                        try:
                            parsed = orjson.loads(match)
                            logger.info(f"Successfully parsed JSON from pattern {pattern}: {parsed}")
                            return orjson.dumps(parsed).decode('utf-8')
                        except orjson.JSONDecodeError:
                            continue
                
                # If still no success, try to extract the final output section
                final_output_match = re.search(r'### Final Output:\s*(\{.*?\})', result_str, re.DOTALL)
                if final_output_match:
                    try:
                        parsed = orjson.loads(final_output_match.group(1))
                        logger.info(f"Successfully parsed JSON from final output: {parsed}")
                        return orjson.dumps(parsed).decode('utf-8')
                    except orjson.JSONDecodeError:
                        pass
                
                # If all parsing attempts fail, try to construct a result from the reasoning
                logger.warning("Failed to parse JSON from LLM response, constructing from reasoning")
                
                # Extract chart type from reasoning
                chart_type = ""
                if "grouped bar" in result_str.lower():
                    chart_type = "grouped_bar"
                elif "bar" in result_str.lower():
                    chart_type = "bar"
                elif "line" in result_str.lower():
                    chart_type = "line"
                elif "pie" in result_str.lower():
                    chart_type = "pie"
                elif "area" in result_str.lower():
                    chart_type = "area"
                
                # Try to extract chart schema from the reasoning
                chart_schema = {}
                schema_match = re.search(r'"chart_schema":\s*(\{.*?\})', result_str, re.DOTALL)
                if schema_match:
                    try:
                        chart_schema = orjson.loads(schema_match.group(1))
                    except orjson.JSONDecodeError:
                        pass
                
                # Clean up reasoning text
                reasoning = result_str
                # Remove markdown formatting
                reasoning = re.sub(r'###.*?###', '', reasoning, flags=re.DOTALL)
                reasoning = re.sub(r'\*\*.*?\*\*', '', reasoning)
                reasoning = re.sub(r'\*.*?\*', '', reasoning)
                reasoning = re.sub(r'`.*?`', '', reasoning)
                reasoning = re.sub(r'```.*?```', '', reasoning, flags=re.DOTALL)
                reasoning = re.sub(r'\{.*?\}', '', reasoning, flags=re.DOTALL)
                reasoning = re.sub(r'\s+', ' ', reasoning).strip()
                
                # Truncate if too long
                if len(reasoning) > 1000:
                    reasoning = reasoning[:1000] + "..."
                
                default_result = {
                    "reasoning": reasoning,
                    "chart_type": chart_type,
                    "chart_schema": chart_schema
                }
                logger.info(f"Constructed result from reasoning: {default_result}")
                return orjson.dumps(default_result).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error in direct chart generation: {e}")
            default_result = {
                "reasoning": f"Error: {str(e)}",
                "chart_type": "",
                "chart_schema": {}
            }
            return orjson.dumps(default_result).decode('utf-8')


class VegaLiteChartGenerationPipeline:
    """Main pipeline for Vega-Lite chart generation using Langchain
    
    This pipeline supports both sample data processing and full data execution.
    When execute_on_full_data=True, the chart will be generated using sample data
    for schema validation and then executed on the complete dataset.
    
    Key Features:
    - Sample data processing for efficient chart schema generation
    - Full data execution for complete dataset visualization
    - Schema validation against Vega-Lite specifications
    - Multiple export formats (JSON, Observable, Altair, Summary)
    - Chart type suggestions based on data structure
    - Comprehensive error handling and validation
    
    Usage:
        pipeline = VegaLiteChartGenerationPipeline()
        result = await pipeline.run(
            query="Show sales trends",
            sql="SELECT * FROM sales",
            data={"columns": [...], "data": [...]},
            execute_on_full_data=True  # Execute on full dataset
        )
    """
    
    def __init__(self,  vega_schema: Optional[Dict[str, Any]] = None, **kwargs):
        self.agent = VegaLiteChartGenerationAgent(vega_schema, **kwargs)
        self.exporter = VegaLiteChartExporter()
        self.vega_schema = vega_schema or self._load_default_vega_schema()
    
    def _load_default_vega_schema(self) -> Dict[str, Any]:
        """Load default Vega-Lite schema"""
        try:
            # Get the directory of the current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(current_dir, "utils", "vega-lite-schema-v5.json")
            
            with open(schema_path, "r") as f:
                return orjson.loads(f.read())
        except FileNotFoundError:
            logger.warning("Vega-Lite schema file not found, using empty schema")
            return {}
        except Exception as e:
            logger.error(f"Error loading Vega-Lite schema: {e}")
            return {}
    
    async def _process_kpi_chart(
        self,
        data: Dict[str, Any],
        chart_schema: Dict[str, Any],
        query: str,
        language: str = "English"
    ) -> Dict[str, Any]:
        """Process KPI chart generation using LLM
        
        This method is ONLY called when a KPI chart has been detected.
        All logic within this method assumes we're working with a KPI chart.
        
        Args:
            data: Data dictionary with columns and data
            chart_schema: Initial chart schema from LLM
            query: Natural language query
            language: Language for the chart
            
        Returns:
            Updated chart schema with KPI-specific configuration
        """
        try:
            # Verify this is indeed a KPI chart
            kpi_metadata = chart_schema.get("kpi_metadata", {})
            chart_type = chart_schema.get("chart_type", "").lower() if isinstance(chart_schema.get("chart_type"), str) else ""
            mark_type = chart_schema.get("mark", {}).get("type", "") if isinstance(chart_schema.get("mark"), dict) else ""
            
            is_kpi = (
                "kpi" in chart_type or
                "metric" in chart_type or
                kpi_metadata is not None and kpi_metadata != {} or
                mark_type == "text"
            )
            
            if not is_kpi:
                logger.warning("_process_kpi_chart called but chart is not a KPI, returning original schema")
                return chart_schema
            
            columns = data.get("columns", [])
            data_rows = data.get("data", [])
            
            if not data_rows or len(data_rows) == 0:
                logger.warning("No data available for KPI chart")
                return chart_schema
            
            # CRITICAL: Check if data shape is suitable for KPI chart
            # KPI charts should ONLY be used for:
            # - Data with at most 5 rows
            # - Data with at most 2 columns (1 for single value, 2 for key-value pairs)
            # If data has >5 rows OR >2 columns, KPI is not appropriate
            num_rows = len(data_rows)
            num_columns = len(columns)
            
            if num_columns > 2:
                logger.warning(f"KPI chart not suitable: data has {num_columns} columns (>2). Returning original schema.")
                return chart_schema
            
            if num_rows > 5 and num_columns > 1:
                logger.warning(f"KPI chart not suitable: data has {num_rows} rows and {num_columns} columns. Returning original schema.")
                return chart_schema
            
            # Normalize data format - handle both list of lists and list of dicts
            # If data_rows contains dictionaries, extract columns from first row
            if data_rows and isinstance(data_rows[0], dict):
                if not columns:
                    columns = list(data_rows[0].keys())
                # Convert list of dicts to list of lists for preprocessor
                normalized_data = {
                    "columns": columns,
                    "data": [[row.get(col) for col in columns] for row in data_rows]
                }
            else:
                normalized_data = data
            
            # Preprocess data for KPI generation
            preprocessed_data = self.agent.data_preprocessor.run(normalized_data)
            
            # First, use LLM to analyze the KPI structure and decide on generation strategy
            kpi_analysis = await self._analyze_kpi_structure_with_llm(
                query=query,
                columns=columns,
                data_rows=data_rows,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                language=language,
                existing_schema=chart_schema
            )
            
            # Based on LLM analysis, call the appropriate generation function
            if kpi_analysis.get("generation_strategy") == "multiple_fields":
                # Multiple numeric fields in a single row - generate one KPI per field
                logger.info(f"LLM detected multiple fields KPI strategy: {kpi_analysis.get('numeric_fields', [])}")
                numeric_fields = kpi_analysis.get("numeric_fields", self._get_numeric_fields(data_rows, columns))
                kpi_schema = await self._generate_multiple_kpi_charts(
                    query=query,
                    data_rows=data_rows,
                    columns=columns,
                    numeric_fields=numeric_fields,
                    kpi_metadata=kpi_analysis.get("kpi_metadata", {}),
                    existing_schema=chart_schema
                )
                # Update chart schema with generated multiple KPIs
                # For multiple KPIs with hconcat, replace the entire schema (don't merge)
                # and ensure no root-level data field exists
                if kpi_schema:
                    chart_schema = kpi_schema.copy()
                    # Remove root-level data field if present (each chart in hconcat has its own data)
                    chart_schema.pop("data", None)
                    # Also remove mark if it's at root level (should only be in individual charts)
                    if "hconcat" in chart_schema and "mark" in chart_schema:
                        chart_schema.pop("mark", None)
            elif kpi_analysis.get("generation_strategy") == "multiple_rows":
                # Multiple rows - generate one KPI per row (can be comparison or metric KPIs)
                logger.info(f"LLM detected multiple rows KPI strategy: {len(data_rows)} rows")
                numeric_fields = kpi_analysis.get("numeric_fields", self._get_numeric_fields(data_rows, columns))
                kpi_schema = await self._generate_multiple_kpi_charts_from_rows(
                    query=query,
                    data_rows=data_rows,
                    columns=columns,
                    numeric_fields=numeric_fields,
                    kpi_metadata=kpi_analysis.get("kpi_metadata", {}),
                    existing_schema=chart_schema
                )
                # Update chart schema with generated multiple KPIs
                # For multiple KPIs with hconcat, replace the entire schema (don't merge)
                # and ensure no root-level data field exists
                if kpi_schema:
                    chart_schema = kpi_schema.copy()
                    # Remove root-level data field if present (each chart in hconcat has its own data)
                    chart_schema.pop("data", None)
                    # Also remove mark if it's at root level (should only be in individual charts)
                    if "hconcat" in chart_schema and "mark" in chart_schema:
                        chart_schema.pop("mark", None)
            else:
                # Single KPI - use the standard LLM generation
                logger.info("LLM detected single KPI strategy")
                kpi_schema = await self._generate_kpi_chart_with_llm(
                    query=query,
                    columns=columns,
                    sample_data=preprocessed_data["sample_data"],
                    sample_column_values=preprocessed_data["sample_column_values"],
                    language=language,
                    existing_schema=chart_schema
                )
                
                # Merge with existing schema, preserving any customizations
                if kpi_schema:
                    # Preserve title from original schema if it exists
                    if "title" in chart_schema:
                        kpi_schema["title"] = chart_schema["title"]
                    
                    # Explicitly remove dummy flags from kpi_metadata
                    kpi_metadata = kpi_schema.get("kpi_metadata", {})
                    if kpi_metadata:
                        kpi_metadata.pop("is_dummy", None)
                        kpi_metadata.pop("vega_lite_compatible", None)
                        kpi_metadata.pop("requires_custom_template", None)
                        kpi_metadata["vega_lite_compatible"] = True
                        kpi_schema["kpi_metadata"] = kpi_metadata
                        logger.info("Cleaned up dummy flags from kpi_metadata")
                    
                    # Check if LLM generated comparison KPI structure
                    llm_data = kpi_schema.get("data", {}).get("values", [])
                    if llm_data and len(llm_data) > 0:
                        first_item = llm_data[0]
                        if isinstance(first_item, dict) and "current" in first_item and "previous" in first_item:
                            logger.info("LLM generated comparison KPI structure detected in data")
                            kpi_schema = self._fix_kpi_encoding_for_data(
                                kpi_schema=kpi_schema,
                                transformed_data=llm_data
                            )
                        else:
                            # Single value KPI - ensure data is set and encoding matches
                            kpi_schema = self._handle_single_kpi_with_data(
                                kpi_schema, data_rows, columns, kpi_metadata
                            )
                
                # Update the chart schema
                chart_schema.update(kpi_schema)
                
                # CRITICAL: Ensure encoding always exists - if LLM didn't generate it, create it
                if "encoding" not in chart_schema or not chart_schema["encoding"]:
                    logger.warning("Encoding missing from LLM-generated schema, creating default encoding")
                    chart_schema["encoding"] = {}
                
                # CRITICAL: Ensure data values are numbers (not strings) but keep original column names
                # For comparison KPIs, we keep original column names and use them in the transform
                if "data" in chart_schema and "values" in chart_schema["data"]:
                    data_values = chart_schema["data"]["values"]
                    if data_values and len(data_values) > 0:
                        first_item = data_values[0]
                        
                        # Check if we have comparison column patterns
                        has_comparison_cols = any(
                            any(kw in str(k).lower() for kw in ["this_year", "current", "completed_this", "learners_this"]) 
                            for k in first_item.keys()
                        ) and any(
                            any(kw in str(k).lower() for kw in ["last_year", "previous", "completed_last", "learners_last"]) 
                            for k in first_item.keys()
                        )
                        
                        # If we have comparison columns, ensure values are numbers (not strings) but keep column names
                        if has_comparison_cols:
                            logger.info("Ensuring comparison KPI data values are numbers (keeping original column names)")
                            normalized_values = []
                            for item in data_values:
                                normalized_item = {}
                                for col, val in item.items():
                                    # Convert string values to numbers, but keep original column names
                                    try:
                                        if isinstance(val, str):
                                            normalized_item[col] = float(val)
                                        else:
                                            normalized_item[col] = val
                                    except (ValueError, TypeError):
                                        normalized_item[col] = val  # Keep original if conversion fails
                                normalized_values.append(normalized_item)
                            
                            chart_schema["data"]["values"] = normalized_values
                            logger.info(f"Normalized {len(normalized_values)} data items (converted strings to numbers, kept original column names)")
                
                # Final verification: ensure encoding matches data structure
                # Check if we have comparison KPI data (with original column names)
                if "data" in chart_schema and "values" in chart_schema["data"]:
                    data_values = chart_schema["data"]["values"]
                    if data_values and len(data_values) > 0:
                        first_item = data_values[0]
                        
                        # Check if this is a comparison KPI by looking for comparison column patterns
                        has_current_col = any(any(kw in str(k).lower() for kw in ["this_year", "current", "completed_this", "learners_this"]) for k in first_item.keys())
                        has_previous_col = any(any(kw in str(k).lower() for kw in ["last_year", "previous", "completed_last", "learners_last"]) for k in first_item.keys())
                        has_percentage_change_col = any("percentage_change" in str(k).lower() or "percent_change" in str(k).lower() for k in first_item.keys())
                        
                        # Check if we have a single value + percentage_change (no separate previous column)
                        # This is different from full comparison KPIs which have both current and previous columns
                        # Filter out percentage_change columns to find numeric value columns
                        numeric_cols = [k for k in first_item.keys() if "percentage_change" not in str(k).lower() and "percent_change" not in str(k).lower()]
                        single_value_with_pct = (has_percentage_change_col and len(numeric_cols) == 1 and not (has_current_col and has_previous_col))
                        
                        if has_current_col and has_previous_col:
                            # Full comparison KPI with both current and previous columns - show "X vs Y (Z%)"
                            encoding = chart_schema.get("encoding", {})
                            
                            # Find the actual column names
                            current_col_name = None
                            previous_col_name = None
                            percentage_change_col_name = None
                            
                            for col in first_item.keys():
                                col_lower = str(col).lower()
                                if not current_col_name and any(kw in col_lower for kw in ["this_year", "current", "completed_this", "learners_this"]):
                                    current_col_name = col
                                elif not previous_col_name and any(kw in col_lower for kw in ["last_year", "previous", "completed_last", "learners_last"]):
                                    previous_col_name = col
                                elif not percentage_change_col_name and ("percentage_change" in col_lower or "percent_change" in col_lower):
                                    percentage_change_col_name = col
                            
                            # Force correct encoding for comparison KPI
                            if not encoding.get("text") or encoding.get("text", {}).get("field") != "display_text":
                                encoding["text"] = {"field": "display_text", "type": "nominal"}
                                logger.info("Final fix: Updated encoding.text.field to display_text")
                            
                            # Ensure transform exists with correct column names
                            if "transform" not in chart_schema:
                                chart_schema["transform"] = []
                            
                            has_display_text = any(t.get("as") == "display_text" for t in chart_schema["transform"])
                            if not has_display_text and current_col_name and previous_col_name and percentage_change_col_name:
                                # Generate transform using original column names - show "X vs Y (Z%)"
                                transform_expr = f"format(datum.{current_col_name}, ',.0f') + ' vs ' + format(datum.{previous_col_name}, ',.0f') + ' (' + format(datum.{percentage_change_col_name} / 100, '+.1%') + ')'"
                                chart_schema["transform"] = [{
                                    "calculate": transform_expr,
                                    "as": "display_text"
                                }]
                                logger.info(f"Final fix: Added display_text transform using original column names: {current_col_name}, {previous_col_name}, {percentage_change_col_name}")
                            
                            # Ensure color encoding is correct
                            if "color" not in encoding or (isinstance(encoding.get("color"), dict) and encoding.get("color", {}).get("field") == "metric"):
                                color_test_field = percentage_change_col_name if percentage_change_col_name else "percentage_change"
                                encoding["color"] = {
                                    "condition": {
                                        "test": f"datum.{color_test_field} > 0",
                                        "value": "#16a34a"
                                    },
                                    "value": "#ef4444"
                                }
                                logger.info("Final fix: Updated encoding.color for comparison KPI")
                            
                            chart_schema["encoding"] = encoding
                        elif single_value_with_pct:
                            # Single value with percentage change - show "X (Z%)" not "X vs Y"
                            encoding = chart_schema.get("encoding", {})
                            
                            # Find the value column and percentage_change column
                            value_col_name = numeric_cols[0] if numeric_cols else None
                            percentage_change_col_name = None
                            
                            for col in first_item.keys():
                                col_lower = str(col).lower()
                                if "percentage_change" in col_lower or "percent_change" in col_lower:
                                    percentage_change_col_name = col
                                    break
                            
                            if value_col_name and percentage_change_col_name:
                                # Force correct encoding
                                if not encoding.get("text") or encoding.get("text", {}).get("field") != "display_text":
                                    encoding["text"] = {"field": "display_text", "type": "nominal"}
                                    logger.info("Final fix: Updated encoding.text.field to display_text for single value with percentage")
                                
                                # Ensure transform exists
                                if "transform" not in chart_schema:
                                    chart_schema["transform"] = []
                                
                                has_display_text = any(t.get("as") == "display_text" for t in chart_schema["transform"])
                                if not has_display_text:
                                    # Generate transform: "X (Z%)" format
                                    transform_expr = f"format(datum.{value_col_name}, ',.0f') + ' (' + format(datum.{percentage_change_col_name} / 100, '+.1%') + ')'"
                                    chart_schema["transform"] = [{
                                        "calculate": transform_expr,
                                        "as": "display_text"
                                    }]
                                    logger.info(f"Final fix: Added display_text transform for single value with percentage: {value_col_name}, {percentage_change_col_name}")
                                
                                # Ensure color encoding (can use percentage_change for conditional color)
                                if "color" not in encoding or (isinstance(encoding.get("color"), dict) and encoding.get("color", {}).get("field") == "metric"):
                                    encoding["color"] = {
                                        "condition": {
                                            "test": f"datum.{percentage_change_col_name} > 0",
                                            "value": "#16a34a"
                                        },
                                        "value": "#ef4444"
                                    }
                                    logger.info("Final fix: Updated encoding.color for single value with percentage")
                                
                                chart_schema["encoding"] = encoding
                        elif has_percentage_change_col and len(numeric_cols) == 0:
                            # ONLY percentage_change exists (no other value column) - show just the percentage
                            encoding = chart_schema.get("encoding", {})
                            
                            # Find the percentage_change column
                            percentage_change_col_name = None
                            for col in first_item.keys():
                                col_lower = str(col).lower()
                                if "percentage_change" in col_lower or "percent_change" in col_lower:
                                    percentage_change_col_name = col
                                    break
                            
                            if percentage_change_col_name:
                                # Force correct encoding
                                if not encoding.get("text") or encoding.get("text", {}).get("field") != "display_text":
                                    encoding["text"] = {"field": "display_text", "type": "nominal"}
                                    logger.info("Final fix: Updated encoding.text.field to display_text for percentage_change only")
                                
                                # Ensure transform exists
                                if "transform" not in chart_schema:
                                    chart_schema["transform"] = []
                                
                                has_display_text = any(t.get("as") == "display_text" for t in chart_schema["transform"])
                                if not has_display_text:
                                    # Generate transform: just show the percentage change formatted correctly
                                    transform_expr = f"format(datum.{percentage_change_col_name} / 100, '+.1%')"
                                    chart_schema["transform"] = [{
                                        "calculate": transform_expr,
                                        "as": "display_text"
                                    }]
                                    logger.info(f"Final fix: Added display_text transform for percentage_change only: {percentage_change_col_name}")
                                
                                # Ensure color encoding (can use percentage_change for conditional color)
                                if "color" not in encoding or (isinstance(encoding.get("color"), dict) and encoding.get("color", {}).get("field") == "metric"):
                                    encoding["color"] = {
                                        "condition": {
                                            "test": f"datum.{percentage_change_col_name} > 0",
                                            "value": "#16a34a"
                                        },
                                        "value": "#ef4444"
                                    }
                                    logger.info("Final fix: Updated encoding.color for percentage_change only")
                                
                                chart_schema["encoding"] = encoding
                        else:
                            # Not a comparison KPI - ensure encoding exists for single value KPI
                            encoding = chart_schema.get("encoding", {})
                            
                            # Check if there's a transform that creates display_text
                            has_display_text_transform = False
                            if "transform" in chart_schema and isinstance(chart_schema["transform"], list):
                                has_display_text_transform = any(
                                    t.get("as") == "display_text" for t in chart_schema["transform"]
                                )
                            
                            # If transform creates display_text, encoding should use it
                            if has_display_text_transform:
                                if not encoding.get("text") or encoding.get("text", {}).get("field") != "display_text":
                                    encoding["text"] = {"field": "display_text", "type": "nominal"}
                                    logger.info("Final fix: Updated encoding.text.field to display_text (transform creates it)")
                                
                                if "color" not in encoding:
                                    encoding["color"] = {"value": "#2563eb"}
                                
                                chart_schema["encoding"] = encoding
                            else:
                                # No display_text transform - use original field
                                if not encoding.get("text"):
                                    # Find the primary numeric field (handle string numbers and None values)
                                    numeric_fields = []
                                    for k, v in first_item.items():
                                        if v is None or (isinstance(v, str) and v.lower() in ["none", "null", ""]):
                                            continue
                                        try:
                                            if isinstance(v, (int, float)):
                                                numeric_fields.append(k)
                                            elif isinstance(v, str):
                                                # Try to parse as float (handle strings like "1.0517241379310345")
                                                clean_val = v.replace(',', '').replace('$', '').replace('%', '').strip()
                                                if clean_val and clean_val.lower() not in ["none", "null", ""]:
                                                    float(clean_val)  # Test if it's a number
                                                    numeric_fields.append(k)
                                        except (ValueError, TypeError):
                                            continue
                                    
                                    if numeric_fields:
                                        primary_field = numeric_fields[0]
                                        encoding["text"] = {"field": primary_field, "type": "quantitative"}
                                        logger.info(f"Final fix: Added encoding.text.field = {primary_field} for single value KPI")
                                    else:
                                        # Fallback to first non-None field or "value"
                                        fallback_field = None
                                        for k, v in first_item.items():
                                            if v is not None and (not isinstance(v, str) or v.lower() not in ["none", "null", ""]):
                                                fallback_field = k
                                                break
                                        encoding["text"] = {"field": fallback_field or "value", "type": "quantitative"}
                                        logger.warning(f"Final fix: Using fallback encoding.text.field = {fallback_field or 'value'}")
                                    
                                    if "color" not in encoding:
                                        encoding["color"] = {"value": "#2563eb"}
                                    
                                    chart_schema["encoding"] = encoding
                else:
                    # No data values - ensure basic encoding exists
                    encoding = chart_schema.get("encoding", {})
                    if not encoding.get("text"):
                        encoding["text"] = {"field": "value", "type": "quantitative"}
                        encoding["color"] = {"value": "#2563eb"}
                        chart_schema["encoding"] = encoding
                        logger.warning("No data values found, added default encoding")
                
                # CRITICAL: Final safety check - ensure encoding always exists and is valid
                if "encoding" not in chart_schema or not chart_schema.get("encoding") or not chart_schema["encoding"].get("text"):
                    logger.warning("Encoding missing or incomplete after processing, creating default encoding")
                    encoding = chart_schema.get("encoding", {})
                    
                    # Try to find a numeric field from data
                    if "data" in chart_schema and "values" in chart_schema["data"]:
                        data_values = chart_schema["data"].get("values", [])
                        if data_values and len(data_values) > 0:
                            first_item = data_values[0]
                            # Find numeric fields (handle string numbers and "None" values)
                            numeric_fields = []
                            for k, v in first_item.items():
                                if v is None or (isinstance(v, str) and v.lower() in ["none", "null", ""]):
                                    continue
                                try:
                                    if isinstance(v, (int, float)):
                                        numeric_fields.append(k)
                                    elif isinstance(v, str):
                                        # Try to parse as float
                                        clean_val = v.replace(',', '').replace('$', '').replace('%', '').strip()
                                        if clean_val and clean_val.lower() not in ["none", "null", ""]:
                                            float(clean_val)  # Test if it's a number
                                            numeric_fields.append(k)
                                except (ValueError, TypeError):
                                    continue
                            
                            if numeric_fields:
                                primary_field = numeric_fields[0]
                                encoding["text"] = {"field": primary_field, "type": "quantitative"}
                                logger.info(f"Final safety check: Added encoding.text.field = {primary_field}")
                            else:
                                # Fallback to first field in data
                                first_key = list(first_item.keys())[0] if first_item else "value"
                                encoding["text"] = {"field": first_key, "type": "quantitative"}
                                logger.warning(f"Final safety check: Using fallback encoding.text.field = {first_key}")
                        else:
                            # No data values - use default
                            encoding["text"] = {"field": "value", "type": "quantitative"}
                            logger.warning("Final safety check: No data values, using default encoding")
                    else:
                        # No data section - use default
                        encoding["text"] = {"field": "value", "type": "quantitative"}
                        logger.warning("Final safety check: No data section, using default encoding")
                    
                    # Ensure color is set
                    if "color" not in encoding:
                        encoding["color"] = {"value": "#2563eb"}
                    
                    chart_schema["encoding"] = encoding
                    logger.info("Final safety check: Encoding ensured in chart_schema")
                
                # Final cleanup: ensure dummy flags are removed from final schema
                final_kpi_metadata = chart_schema.get("kpi_metadata", {})
                if final_kpi_metadata:
                    final_kpi_metadata.pop("is_dummy", None)
                    final_kpi_metadata.pop("requires_custom_template", None)
                    final_kpi_metadata["vega_lite_compatible"] = True
                    chart_schema["kpi_metadata"] = final_kpi_metadata
                    logger.info("Final cleanup: Removed dummy flags from chart_schema kpi_metadata")
                
                logger.info("Generated KPI chart schema using LLM")
            
            # Final safety check: ensure dummy flags are never returned
            if "kpi_metadata" in chart_schema:
                chart_schema["kpi_metadata"].pop("is_dummy", None)
                chart_schema["kpi_metadata"].pop("requires_custom_template", None)
                if "kpi_metadata" in chart_schema and chart_schema["kpi_metadata"]:
                    chart_schema["kpi_metadata"]["vega_lite_compatible"] = True
            
            # ABSOLUTE FINAL CHECK: Ensure encoding exists before returning
            if "encoding" not in chart_schema or not chart_schema.get("encoding") or not chart_schema["encoding"].get("text"):
                logger.error("CRITICAL: Encoding still missing after all processing - creating emergency encoding")
                # Get data to find a field
                field_name = "value"
                if "data" in chart_schema and "values" in chart_schema["data"]:
                    data_values = chart_schema["data"].get("values", [])
                    if data_values and len(data_values) > 0:
                        first_item = data_values[0]
                        # Get first key that's not None
                        for k, v in first_item.items():
                            if v is not None and (not isinstance(v, str) or v.lower() not in ["none", "null", ""]):
                                field_name = k
                                break
                
                chart_schema["encoding"] = {
                    "text": {"field": field_name, "type": "quantitative"},
                    "color": {"value": "#2563eb"}
                }
                logger.error(f"CRITICAL: Created emergency encoding with field = {field_name}")
            
            # CRITICAL VALIDATION: Ensure encoding field matches actual data fields
            # This fixes the issue where encoding has "field": "value" but data has "count"
            chart_schema = self._validate_and_fix_encoding_field(chart_schema)
            
            return chart_schema
            
        except Exception as e:
            logger.error(f"Error processing KPI chart: {e}")
            return chart_schema
    
    def _validate_and_fix_encoding_field(self, chart_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix encoding field to match actual data fields.
        
        This fixes the common issue where encoding has "field": "value" but the actual
        data has different field names like "count", "total", etc.
        
        Args:
            chart_schema: The chart schema to validate
            
        Returns:
            Fixed chart schema with encoding field matching actual data fields
        """
        try:
            # Get encoding and data
            encoding = chart_schema.get("encoding", {})
            text_encoding = encoding.get("text", {})
            encoding_field = text_encoding.get("field")
            
            if not encoding_field:
                return chart_schema
            
            # Get data values
            data = chart_schema.get("data", {})
            data_values = data.get("values", [])
            
            if not data_values or len(data_values) == 0:
                return chart_schema
            
            first_item = data_values[0]
            if not isinstance(first_item, dict):
                return chart_schema
            
            available_fields = list(first_item.keys())
            
            # Check if encoding field exists in data
            if encoding_field in available_fields:
                # Field exists, no fix needed
                return chart_schema
            
            # Field doesn't exist - need to fix it
            logger.warning(f"Encoding field '{encoding_field}' not found in data fields: {available_fields}")
            
            # Find the best numeric field to use
            numeric_fields = []
            for field_name in available_fields:
                val = first_item.get(field_name)
                if val is not None:
                    try:
                        if isinstance(val, (int, float)):
                            numeric_fields.append(field_name)
                        elif isinstance(val, str):
                            # Try to parse as number
                            clean_val = val.replace(',', '').replace('$', '').replace('%', '').strip()
                            if clean_val and clean_val.lower() not in ["none", "null", ""]:
                                float(clean_val)  # Test if numeric
                                numeric_fields.append(field_name)
                    except (ValueError, TypeError):
                        continue
            
            # Pick the best field
            if numeric_fields:
                # Prioritize fields with keywords like count, total, value, amount
                def get_priority(field_name):
                    field_lower = field_name.lower()
                    if any(kw in field_lower for kw in ["count", "total", "sum", "amount", "value"]):
                        return 1
                    elif any(kw in field_lower for kw in ["rate", "percentage", "percent"]):
                        return 2
                    return 3
                
                numeric_fields.sort(key=get_priority)
                correct_field = numeric_fields[0]
            else:
                # No numeric fields found, use first available field
                correct_field = available_fields[0] if available_fields else encoding_field
            
            # Fix the encoding
            logger.info(f"Fixing encoding field from '{encoding_field}' to '{correct_field}'")
            text_encoding["field"] = correct_field
            encoding["text"] = text_encoding
            chart_schema["encoding"] = encoding
            
            return chart_schema
            
        except Exception as e:
            logger.error(f"Error in _validate_and_fix_encoding_field: {e}")
            return chart_schema
    
    def _handle_single_kpi_with_data(
        self,
        kpi_schema: Dict[str, Any],
        data_rows: List[Any],
        columns: List[str],
        kpi_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle single KPI with data - ensure data is set and encoding matches"""
        if "data" not in kpi_schema:
            kpi_schema["data"] = {}
        if "values" not in kpi_schema["data"] or not kpi_schema["data"]["values"]:
            # Use original data format if LLM didn't generate data
            if data_rows and isinstance(data_rows[0], dict):
                kpi_schema["data"]["values"] = data_rows
            elif data_rows:
                kpi_schema["data"]["values"] = [
                    dict(zip(columns, row)) for row in data_rows
                ]
        
        # Fix encoding to use actual field names from data
        kpi_schema = self._fix_encoding_for_original_data(
            kpi_schema=kpi_schema,
            columns=columns,
            data_values=kpi_schema["data"]["values"],
            kpi_metadata=kpi_metadata
        )
        
        return kpi_schema
    
    async def _analyze_kpi_structure_with_llm(
        self,
        query: str,
        columns: List[str],
        data_rows: List[Any],
        sample_data: Dict[str, Any],
        sample_column_values: Dict[str, Any],
        language: str,
        existing_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze KPI structure using LLM to determine generation strategy
        
        This method uses LLM to analyze the data and determine:
        1. KPI type (counter, percentage, score, comparison)
        2. Generation strategy (single, multiple_fields, multiple_rows)
        3. Numeric fields to use
        
        Args:
            query: Natural language query
            columns: Column names
            data_rows: Data rows
            sample_data: Preprocessed sample data
            sample_column_values: Sample column values
            language: Language for the chart
            existing_schema: Existing chart schema
            
        Returns:
            Analysis dict with generation_strategy, kpi_type, numeric_fields, kpi_metadata
        """
        try:
            # Prepare data summary for LLM analysis
            row_count = len(data_rows)
            numeric_fields = self._get_numeric_fields(data_rows, columns)
            
            # Check for comparison patterns
            col_names_lower = [col.lower() if isinstance(col, str) else str(col).lower() for col in columns]
            has_current = any(any(kw in col for kw in ["this_year", "current", "this_month", "completed_this", "learners_this"]) for col in col_names_lower)
            has_previous = any(any(kw in col for kw in ["last_year", "previous", "last_month", "prior", "completed_last", "learners_last"]) for col in col_names_lower)
            has_percentage_change = any("percentage_change" in col or "percent_change" in col for col in col_names_lower)
            
            # Create analysis prompt
            analysis_prompt = f"""
            ### TASK ###
            
            Analyze the following KPI data structure and determine the best generation strategy.
            
            ### INPUT ###
            Question: {query}
            Columns: {json.dumps(columns)}
            Row Count: {row_count}
            Numeric Fields: {json.dumps(numeric_fields)}
            Sample Data: {json.dumps(sample_data)}
            Has Current/Previous Columns: {has_current and has_previous}
            Has Percentage Change: {has_percentage_change}
            
            ### ANALYSIS REQUIRED ###
            
            Determine:
            1. **KPI Type**: "counter", "percentage", "score", or "comparison"
            2. **Generation Strategy**: 
               - "single": Single KPI chart (one chart for all data)
               - "multiple_fields": Multiple KPIs, one per numeric field (single row with multiple fields)
               - "multiple_rows": Multiple KPIs, one per row (multiple rows with same field structure)
            3. **Numeric Fields**: List of numeric field names to use
            
            ### DECISION RULES ###
            
            **Generation Strategy:**
            - Use "multiple_fields" if: Single row with 2+ numeric fields (different metrics)
            - Use "multiple_rows" if: Multiple rows (2+) with same field structure (each row is a separate KPI)
              - This applies to BOTH metric KPIs (counter, percentage, score) AND comparison KPIs
              - Example: 3 rows each with "not_logged_in" → 3 separate KPI charts
              - Example: 3 rows each with "completed_this_year", "completed_last_year", "percentage_change" → 3 separate comparison KPI charts
            - Use "single" otherwise: Single row with one field, or aggregated data
            
            **KPI Type:**
            - "comparison": If has current/previous columns OR percentage_change column
            - "counter": Single count/total value
            - "percentage": Percentage/rate value (0-1 or 0-100)
            - "score": Score value (0-100 with thresholds)
            
            ### OUTPUT FORMAT ###
            
            Respond with ONLY valid JSON:
            {{
                "generation_strategy": "single" | "multiple_fields" | "multiple_rows",
                "kpi_type": "counter" | "percentage" | "score" | "comparison",
                "numeric_fields": ["<field1>", "<field2>", ...],
                "kpi_metadata": {{
                    "chart_type": "metric_kpi" | "comparison_kpi",
                    "chart_subtype": "counter" | "percentage" | "score" | "current_vs_percentage",
                    "description": "<description>"
                }},
                "reasoning": "<brief explanation of decision>"
            }}
            
            **CRITICAL: Respond with ONLY JSON. No text before or after.**
            """
            
            # Use LLM to analyze
            generation_prompt = PromptTemplate(
                input_variables=["analysis_prompt"],
                template="{analysis_prompt}"
            )
            
            result = (
                generation_prompt
                | self.agent.llm
            ).invoke({
                "analysis_prompt": analysis_prompt
            })
            
            # Extract content
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            logger.info(f"Raw LLM KPI analysis response: {result_str}")
            
            # Parse JSON response
            try:
                parsed = orjson.loads(result_str)
                logger.info(f"Successfully parsed KPI analysis: {parsed}")
                return parsed
            except orjson.JSONDecodeError:
                # Try to extract JSON from text
                import re
                json_patterns = [
                    r'```json\s*(\{.*?\})\s*```',
                    r'```\s*(\{.*?\})\s*```',
                    r'(\{.*?\})',
                ]
                
                for pattern in json_patterns:
                    json_matches = re.findall(pattern, result_str, re.DOTALL)
                    for match in json_matches:
                        try:
                            parsed = orjson.loads(match)
                            logger.info(f"Successfully parsed KPI analysis from pattern: {parsed}")
                            return parsed
                        except orjson.JSONDecodeError:
                            continue
                
                # Fallback: use heuristics
                logger.warning("Failed to parse LLM analysis, using heuristic fallback")
                return self._analyze_kpi_structure_heuristic(
                    columns, data_rows, numeric_fields, has_current, has_previous, has_percentage_change
                )
            
        except Exception as e:
            logger.error(f"Error analyzing KPI structure with LLM: {e}")
            # Fallback to heuristics
            numeric_fields = self._get_numeric_fields(data_rows, columns)
            return self._analyze_kpi_structure_heuristic(
                columns, data_rows, numeric_fields, has_current, has_previous, has_percentage_change
            )
    
    def _analyze_kpi_structure_heuristic(
        self,
        columns: List[str],
        data_rows: List[Any],
        numeric_fields: List[str],
        has_current: bool,
        has_previous: bool,
        has_percentage_change: bool
    ) -> Dict[str, Any]:
        """Heuristic fallback for KPI structure analysis"""
        row_count = len(data_rows)
        
        # Determine KPI type
        if has_current and has_previous:
            kpi_type = "comparison"
            chart_type = "comparison_kpi"
            chart_subtype = "current_vs_percentage"
        elif has_percentage_change:
            kpi_type = "comparison"
            chart_type = "comparison_kpi"
            chart_subtype = "current_vs_percentage"
        else:
            kpi_type = "counter"
            chart_type = "metric_kpi"
            chart_subtype = "counter"
        
        # Determine generation strategy
        if len(numeric_fields) > 1 and row_count == 1:
            generation_strategy = "multiple_fields"
        elif row_count > 1:
            # Check if all rows have same structure
            if data_rows:
                first_row_dict = data_rows[0] if isinstance(data_rows[0], dict) else dict(zip(columns, data_rows[0]))
                first_row_keys = set(first_row_dict.keys())
                all_rows_same_structure = all(
                    set(row.keys() if isinstance(row, dict) else dict(zip(columns, row)).keys()) == first_row_keys
                    for row in data_rows[:5]
                )
                if all_rows_same_structure:
                    generation_strategy = "multiple_rows"
                else:
                    generation_strategy = "single"
            else:
                generation_strategy = "single"
        else:
            generation_strategy = "single"
        
        return {
            "generation_strategy": generation_strategy,
            "kpi_type": kpi_type,
            "numeric_fields": numeric_fields,
            "kpi_metadata": {
                "chart_type": chart_type,
                "chart_subtype": chart_subtype,
                "description": f"{kpi_type} KPI chart"
            },
            "reasoning": f"Heuristic analysis: {generation_strategy} strategy for {kpi_type} KPI"
        }
    
    def _get_numeric_fields(self, data_rows: List[Any], columns: List[str]) -> List[str]:
        """Get list of numeric field names from data
        
        NOTE: This method is ONLY used within KPI chart processing context.
        It should not be called for non-KPI charts.
        
        Args:
            data_rows: Data rows
            columns: Column names
            
        Returns:
            List of numeric field names (excluding percentage_change which is part of comparison KPIs)
        """
        numeric_fields = []
        if not data_rows:
            return numeric_fields
        
        first_row = data_rows[0]
        if isinstance(first_row, list):
            row_dict = dict(zip(columns, first_row))
        else:
            row_dict = first_row
        
        for col in columns:
            val = row_dict.get(col)
            if val is not None:
                try:
                    float_val = float(val) if isinstance(val, str) else val
                    if isinstance(float_val, (int, float)):
                        # Skip percentage_change as it's usually part of comparison KPI
                        if "percentage_change" not in col.lower() and "percent_change" not in col.lower():
                            numeric_fields.append(col)
                except (ValueError, TypeError):
                    pass
        
        return numeric_fields
    
    async def _generate_multiple_kpi_charts_from_rows(
        self,
        query: str,
        data_rows: List[Any],
        columns: List[str],
        numeric_fields: List[str],
        kpi_metadata: Dict[str, Any],
        existing_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate multiple KPI charts from multiple rows (one KPI per row)
        
        This is different from _generate_multiple_kpi_charts which handles multiple columns.
        This method creates one KPI chart for each row of data.
        
        Args:
            query: Natural language query
            data_rows: Data rows (multiple rows with same field structure)
            columns: Column names
            numeric_fields: List of numeric field names
            kpi_metadata: KPI metadata
            existing_schema: Existing chart schema
            
        Returns:
            Combined KPI schema with hconcat
        """
        try:
            if not data_rows or len(data_rows) == 0:
                logger.warning("_generate_multiple_kpi_charts_from_rows called with no data rows")
                return existing_schema
            
            # SAFETY CHECK: Limit multiple row KPI generation to max 5 rows
            # Data with >5 rows should not be rendered as KPI charts
            if len(data_rows) > 5:
                logger.warning(f"_generate_multiple_kpi_charts_from_rows: Too many rows ({len(data_rows)} > 5). Returning original schema.")
                return existing_schema
            
            # Also check column count - KPI is not suitable for >2 columns
            if len(columns) > 2:
                logger.warning(f"_generate_multiple_kpi_charts_from_rows: Too many columns ({len(columns)} > 2). Returning original schema.")
                return existing_schema
            
            # Try using LLM first - adapt the existing method for multiple rows
            # Convert rows to a format suitable for the LLM method
            # Create a list of sample data dicts, one per row
            rows_sample_data = []
            for row in data_rows:
                if isinstance(row, dict):
                    row_dict = row
                else:
                    row_dict = dict(zip(columns, row))
                
                # Extract numeric field values for this row
                row_sample = {}
                for field in numeric_fields:
                    if field in row_dict:
                        value = row_dict.get(field)
                        try:
                            if isinstance(value, str):
                                row_sample[field] = float(value)
                            else:
                                row_sample[field] = float(value) if value is not None else 0
                        except (ValueError, TypeError):
                            row_sample[field] = 0
                
                if row_sample:
                    rows_sample_data.append(row_sample)
            
            # Try using LLM to generate charts for multiple rows
            # We'll pass all rows as sample data and let LLM generate one chart per row
            if rows_sample_data and numeric_fields:
                # Use the first row's data structure for LLM
                first_row_sample = rows_sample_data[0]
                
                # Try LLM generation - adapt the existing method
                # Create a combined sample data showing all rows
                combined_sample_data = {
                    "rows": rows_sample_data,
                    "row_count": len(rows_sample_data),
                    "fields": numeric_fields
                }
                
                # Try calling the LLM method with adapted data
                # Note: The existing method expects one row with multiple fields,
                # but we can adapt it by passing all rows
                try:
                    kpi_charts = await self._generate_kpi_charts_list_with_llm(
                        query=query,
                        numeric_fields=numeric_fields,
                        sample_data=first_row_sample,  # Use first row as template
                        kpi_metadata=kpi_metadata
                    )
                    
                    # If LLM returned charts, we need to adapt them for multiple rows
                    # The LLM method generates one chart per field, but we need one per row
                    if kpi_charts and len(kpi_charts) > 0:
                        # LLM generated charts for fields, but we need charts for rows
                        # So we'll use the fallback approach instead
                        logger.info("LLM generated charts for fields, but we need charts for rows - using fallback")
                        kpi_charts = []
                except Exception as e:
                    logger.warning(f"LLM generation failed for multiple rows: {e}, using fallback")
                    kpi_charts = []
            else:
                kpi_charts = []
            
            # Fallback: generate charts programmatically (one per row)
            if not kpi_charts:
                logger.info("Generating KPI charts programmatically for multiple rows")
                kpi_charts = []
                
                # Check if this is a comparison KPI based on metadata or column patterns
                chart_type_meta = kpi_metadata.get("chart_type", "").lower() if kpi_metadata else ""
                is_comparison_kpi = "comparison" in chart_type_meta
                
                # Also check column patterns for comparison KPIs
                if not is_comparison_kpi and data_rows:
                    first_row_dict = data_rows[0] if isinstance(data_rows[0], dict) else dict(zip(columns, data_rows[0]))
                    col_names = list(first_row_dict.keys())
                    col_names_lower = [col.lower() if isinstance(col, str) else str(col).lower() for col in col_names]
                    has_current = any(any(kw in col for kw in ["this_year", "current", "this_month", "completed_this", "learners_this"]) for col in col_names_lower)
                    has_previous = any(any(kw in col for kw in ["last_year", "previous", "last_month", "prior", "completed_last", "learners_last"]) for col in col_names_lower)
                    has_percentage_change = any("percentage_change" in col or "percent_change" in col for col in col_names_lower)
                    is_comparison_kpi = (has_current and has_previous) or has_percentage_change
                
                # Generate one KPI chart for each row
                for idx, row in enumerate(data_rows):
                    # Convert row to dict if needed
                    if isinstance(row, dict):
                        row_dict = row
                    else:
                        row_dict = dict(zip(columns, row))
                    
                    if is_comparison_kpi:
                        # Generate comparison KPI chart for this row
                        # Find current, previous, and percentage_change columns
                        current_col = None
                        previous_col = None
                        percentage_change_col = None
                        
                        for col in columns:
                            col_lower = str(col).lower()
                            if not current_col and any(kw in col_lower for kw in ["this_year", "current", "this_month", "completed_this", "learners_this"]):
                                current_col = col
                            elif not previous_col and any(kw in col_lower for kw in ["last_year", "previous", "last_month", "prior", "completed_last", "learners_last"]):
                                previous_col = col
                            elif not percentage_change_col and ("percentage_change" in col_lower or "percent_change" in col_lower):
                                percentage_change_col = col
                        
                        if current_col and previous_col:
                            # Full comparison KPI
                            current_val = float(row_dict.get(current_col, 0)) if isinstance(row_dict.get(current_col), (str, int, float)) else 0
                            previous_val = float(row_dict.get(previous_col, 0)) if isinstance(row_dict.get(previous_col), (str, int, float)) else 0
                            
                            if percentage_change_col and percentage_change_col in row_dict:
                                pct_change = float(row_dict[percentage_change_col]) if isinstance(row_dict[percentage_change_col], (str, int, float)) else 0
                            else:
                                pct_change = ((current_val - previous_val) / previous_val * 100) if previous_val != 0 else 0
                            
                            # Generate title
                            title = current_col.replace("_", " ").title() if current_col else "Comparison"
                            
                            # Create comparison KPI chart
                            pct_col_name = percentage_change_col if percentage_change_col else "percentage_change"
                            data_dict = {
                                current_col: current_val,
                                previous_col: previous_val,
                                pct_col_name: pct_change
                            }
                            
                            kpi_chart = {
                                "title": title,
                                "data": {
                                    "values": [data_dict]
                                },
                                "transform": [{
                                    "calculate": f"format(datum.{current_col}, ',.0f') + ' vs ' + format(datum.{previous_col}, ',.0f') + ' (' + format(datum.{pct_col_name} / 100, '+.1%') + ')'",
                                    "as": "display_text"
                                }],
                                "mark": {
                                    "type": "text",
                                    "fontSize": 36,
                                    "fontWeight": "bold",
                                    "align": "center",
                                    "baseline": "middle"
                                },
                                "encoding": {
                                    "text": {
                                        "field": "display_text",
                                        "type": "nominal"
                                    },
                                    "color": {
                                        "condition": {
                                            "test": f"datum.{pct_col_name} > 0",
                                            "value": "#16a34a"
                                        },
                                        "value": "#ef4444"
                                    }
                                },
                                "width": 150,
                                "height": 100
                            }
                        elif percentage_change_col:
                            # Single value with percentage change
                            # Find the value column (not percentage_change)
                            value_col = None
                            for col in columns:
                                if col != percentage_change_col and col in row_dict:
                                    val = row_dict.get(col)
                                    try:
                                        float(val) if isinstance(val, str) else val
                                        value_col = col
                                        break
                                    except (ValueError, TypeError):
                                        continue
                            
                            if value_col:
                                value_val = float(row_dict.get(value_col, 0)) if isinstance(row_dict.get(value_col), (str, int, float)) else 0
                                pct_change = float(row_dict.get(percentage_change_col, 0)) if isinstance(row_dict.get(percentage_change_col), (str, int, float)) else 0
                                
                                # Generate title from query context if available
                                title = self._extract_title_from_query(query, value_col)
                                if "percentage" in query.lower() or "change" in query.lower():
                                    if not title.endswith("Change"):
                                        title += " Change"
                                
                                kpi_chart = {
                                    "title": title,
                                    "data": {
                                        "values": [{
                                            value_col: value_val,
                                            percentage_change_col: pct_change
                                        }]
                                    },
                                    "transform": [{
                                        "calculate": f"format(datum.{value_col}, ',.0f') + ' (' + format(datum.{percentage_change_col} / 100, '+.1%') + ')'",
                                        "as": "display_text"
                                    }],
                                    "mark": {
                                        "type": "text",
                                        "fontSize": 36,
                                        "fontWeight": "bold",
                                        "align": "center",
                                        "baseline": "middle"
                                    },
                                    "encoding": {
                                        "text": {
                                            "field": "display_text",
                                            "type": "nominal"
                                        },
                                        "color": {
                                            "condition": {
                                                "test": f"datum.{percentage_change_col} > 0",
                                                "value": "#16a34a"
                                            },
                                            "value": "#ef4444"
                                        }
                                    },
                                    "width": 150,
                                    "height": 100
                                }
                            else:
                                logger.warning(f"Skipping row {idx} - no value column found for comparison KPI")
                                continue
                        else:
                            logger.warning(f"Skipping row {idx} - incomplete comparison KPI data")
                            continue
                    else:
                        # Generate metric KPI chart (counter, percentage, score)
                        # Find the primary numeric field to display
                        primary_field = None
                        if numeric_fields:
                            # Use the first numeric field found in the row
                            for field in numeric_fields:
                                if field in row_dict:
                                    primary_field = field
                                    break
                        
                        if not primary_field:
                            # Fallback: find first numeric value in row
                            for key, val in row_dict.items():
                                try:
                                    float_val = float(val) if isinstance(val, str) else val
                                    if isinstance(float_val, (int, float)):
                                        primary_field = key
                                        break
                                except (ValueError, TypeError):
                                    continue
                        
                        if not primary_field:
                            logger.warning(f"Skipping row {idx} - no numeric field found")
                            continue
                        
                        # Get the value
                        value = row_dict.get(primary_field)
                        try:
                            if isinstance(value, str):
                                num_value = float(value)
                            else:
                                num_value = float(value) if value is not None else 0
                        except (ValueError, TypeError):
                            num_value = 0
                        
                        # Generate title from query context if available, otherwise use field name
                        title = self._extract_title_from_query(query, primary_field)
                        
                        # Determine format based on field type
                        field_lower = primary_field.lower()
                        if any(kw in field_lower for kw in ["rate", "percentage", "percent", "ratio"]):
                            format_str = ".1%"
                        elif any(kw in field_lower for kw in ["count", "total", "sum"]):
                            format_str = ","
                        else:
                            format_str = ",.0f"
                        
                        # Select color based on field type
                        if any(kw in field_lower for kw in ["drop_off", "failure", "error"]):
                            color = "#ef4444"  # Red
                        elif any(kw in field_lower for kw in ["completed", "success"]):
                            color = "#10b981"  # Green
                        else:
                            color = "#2563eb"  # Blue (default)
                        
                        # Create KPI chart for this row
                        kpi_chart = {
                            "title": title,
                            "data": {
                                "values": [{primary_field: num_value}]
                            },
                            "mark": {
                                "type": "text",
                                "fontSize": 36,
                                "fontWeight": "bold",
                                "align": "center",
                                "baseline": "middle"
                            },
                            "encoding": {
                                "text": {
                                    "field": primary_field,
                                    "type": "quantitative",
                                    "format": format_str
                                },
                                "color": {
                                    "value": color
                                }
                            },
                            "width": 150,
                            "height": 100
                        }
                    
                    kpi_charts.append(kpi_chart)
            
            if not kpi_charts:
                logger.warning("No KPI charts generated from rows, returning original schema")
                return existing_schema
            
            # Combine charts using hconcat
            combined_schema = {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "hconcat": kpi_charts,
                "kpi_metadata": {
                    **kpi_metadata,
                    "chart_type": "multiple_kpi",
                    "chart_subtype": "hconcat_rows",
                    "kpi_count": len(kpi_charts)
                }
            }
            
            # Preserve title from existing schema
            if "title" in existing_schema:
                combined_schema["title"] = existing_schema["title"]
            
            logger.info(f"Generated {len(kpi_charts)} KPI charts from {len(data_rows)} rows")
            return combined_schema
            
        except Exception as e:
            logger.error(f"Error generating multiple KPI charts from rows: {e}")
            # Fallback to single KPI
            return existing_schema
    
    async def _generate_multiple_kpi_charts(
        self,
        query: str,
        data_rows: List[Any],
        columns: List[str],
        numeric_fields: List[str],
        kpi_metadata: Dict[str, Any],
        existing_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate multiple KPI charts and combine them using hconcat
        
        This method is ONLY called from _process_kpi_chart when multiple KPIs are detected.
        It assumes we're already in a KPI chart context.
        
        Args:
            query: Natural language query
            data_rows: Data rows
            columns: Column names
            numeric_fields: List of numeric field names to create KPIs for
            kpi_metadata: KPI metadata
            existing_schema: Existing chart schema
            
        Returns:
            Combined KPI schema with hconcat
        """
        try:
            # Additional safety check: ensure we have numeric fields
            if not numeric_fields or len(numeric_fields) < 2:
                logger.warning("_generate_multiple_kpi_charts called but insufficient numeric fields, returning original schema")
                return existing_schema
            # Prepare data for LLM
            first_row = data_rows[0] if data_rows else {}
            if isinstance(first_row, list):
                row_dict = dict(zip(columns, first_row))
            else:
                row_dict = first_row
            
            # Create sample data with just the numeric fields, converting strings to numbers
            sample_data = {}
            for field in numeric_fields:
                if field in row_dict:
                    value = row_dict.get(field)
                    try:
                        if isinstance(value, str):
                            sample_data[field] = float(value)
                        else:
                            sample_data[field] = value
                    except (ValueError, TypeError):
                        sample_data[field] = value  # Keep original if conversion fails
            
            # Generate multiple KPI charts using LLM
            kpi_charts = await self._generate_kpi_charts_list_with_llm(
                query=query,
                numeric_fields=numeric_fields,
                sample_data=sample_data,
                kpi_metadata=kpi_metadata
            )
            
            if not kpi_charts:
                # Fallback: generate charts programmatically
                kpi_charts = self._generate_kpi_charts_fallback(
                    numeric_fields=numeric_fields,
                    row_dict=row_dict
                )
            
            # Combine charts using hconcat
            combined_schema = {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "hconcat": kpi_charts,
                "kpi_metadata": {
                    **kpi_metadata,
                    "chart_type": "multiple_kpi",
                    "chart_subtype": "hconcat",
                    "kpi_count": len(kpi_charts)
                }
            }
            
            # Preserve title from existing schema
            if "title" in existing_schema:
                combined_schema["title"] = existing_schema["title"]
            
            return combined_schema
            
        except Exception as e:
            logger.error(f"Error generating multiple KPI charts: {e}")
            # Fallback to single KPI
            return existing_schema
    
    async def _generate_kpi_charts_list_with_llm(
        self,
        query: str,
        numeric_fields: List[str],
        sample_data: Dict[str, Any],
        kpi_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate list of individual KPI charts using LLM
        
        NOTE: This method is ONLY called from _generate_multiple_kpi_charts,
        which is only called when a KPI chart has been detected and multiple
        numeric fields are present.
        
        Args:
            query: Natural language query
            numeric_fields: List of numeric field names
            sample_data: Sample data values
            kpi_metadata: KPI metadata
            
        Returns:
            List of individual KPI chart schemas
        """
        try:
            system_prompt = """
            ### TASK ###
            
            You are an expert at creating multiple KPI (Key Performance Indicator) charts! Given a list of numeric fields and their values, you need to generate a list of individual KPI chart schemas.
            
            Each KPI chart should be a separate Vega-Lite chart configuration that displays a single metric.
            
            ### KPI CHART STRUCTURE ###
            
            Each KPI chart should follow this structure:
            {
                "title": "<DESCRIPTIVE_TITLE_FOR_THIS_METRIC>",
                "data": {
                    "values": [
                        {"<FIELD_NAME>": <NUMERIC_VALUE>}
                    ]
                },
                "mark": {
                    "type": "text",
                    "fontSize": 36,
                    "align": "center",
                    "baseline": "middle"
                },
                "encoding": {
                    "text": {
                        "field": "<FIELD_NAME>",
                        "type": "quantitative",
                        "format": "<APPROPRIATE_FORMAT>"
                    },
                    "color": {
                        "value": "<APPROPRIATE_COLOR>"
                    }
                },
                "width": 150,
                "height": 100
            }
            
            ### FORMATTING RULES ###
            
            1. **Format Selection**:
               - For rates, percentages, ratios: use ".1%" or ".0%" format
               - For counts, totals, sums: use "," format (thousands separator)
               - For other numeric values: use ",.0f" format
               
            2. **Color Selection**:
               - Use semantic colors based on metric type:
                 * Red (#ef4444) for negative metrics (drop-off, failure, error rates)
                 * Orange (#f59e0b) for warning metrics (counts, totals)
                 * Green (#10b981) for positive metrics (completion, success rates)
                 * Blue (#2563eb) for neutral/informational metrics (totals, registrations)
               
            3. **Title Generation**:
               - Create descriptive titles from field names
               - Convert snake_case to Title Case
               - Make titles concise and clear
               
            ### OUTPUT FORMAT ###
            
            You MUST respond with ONLY a valid JSON array containing KPI chart schemas. Each element should be a complete KPI chart configuration.
            
            [
                {
                    "title": "<TITLE_1>",
                    "data": {"values": [{"<FIELD_1>": <VALUE_1>}]},
                    "mark": {...},
                    "encoding": {...},
                    "width": 150,
                    "height": 100
                },
                {
                    "title": "<TITLE_2>",
                    "data": {"values": [{"<FIELD_2>": <VALUE_2>}]},
                    "mark": {...},
                    "encoding": {...},
                    "width": 150,
                    "height": 100
                }
            ]
            
            Do NOT include:
            - Markdown formatting
            - Code blocks
            - Explanations outside the JSON
            - Comments in JSON
            
            Your response should be a single JSON array.
            """
            
            user_prompt = f"""
            ### INPUT ###
            Question: {query}
            Numeric Fields: {json.dumps(numeric_fields)}
            Sample Data: {json.dumps(sample_data)}
            KPI Metadata: {json.dumps(kpi_metadata)}
            
            Generate a list of individual KPI chart schemas, one for each numeric field. Each chart should display a single metric with appropriate formatting and color.
            """
            
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{{system_prompt}}\n\n{{user_prompt}}"
            )
            
            result = (
                generation_prompt
                | self.agent.llm
            ).invoke({
                "system_prompt": system_prompt,
                "user_prompt": user_prompt
            })
            
            # Extract content from the response
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            logger.info(f"Raw LLM multiple KPI response: {result_str}")
            
            # Parse JSON response
            try:
                # First try to parse the raw result
                parsed = orjson.loads(result_str)
                if isinstance(parsed, list):
                    logger.info(f"Successfully parsed {len(parsed)} KPI charts from LLM")
                    return parsed
                else:
                    logger.warning("LLM response is not a list, using fallback")
                    return []
            except orjson.JSONDecodeError:
                # If parsing fails, try to extract JSON from the text
                import re
                json_patterns = [
                    r'```json\s*(\[.*?\])',  # JSON array in code blocks
                    r'```\s*(\[.*?\])',      # Generic code blocks
                    r'(\[.*?\])',            # Any JSON array
                ]
                
                for pattern in json_patterns:
                    json_matches = re.findall(pattern, result_str, re.DOTALL)
                    for match in json_matches:
                        try:
                            parsed = orjson.loads(match)
                            if isinstance(parsed, list):
                                logger.info(f"Successfully parsed {len(parsed)} KPI charts from pattern")
                                return parsed
                        except orjson.JSONDecodeError:
                            continue
                
                logger.warning("Failed to parse JSON from LLM multiple KPI response")
                return []
            
        except Exception as e:
            logger.error(f"Error generating KPI charts list with LLM: {e}")
            return []
    
    def _generate_kpi_charts_fallback(
        self,
        numeric_fields: List[str],
        row_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate KPI charts programmatically as fallback
        
        NOTE: This method is ONLY called from _generate_multiple_kpi_charts
        when LLM generation fails. It assumes we're in a KPI chart context.
        
        Args:
            numeric_fields: List of numeric field names
            row_dict: Data row dictionary
            
        Returns:
            List of KPI chart schemas
        """
        kpi_charts = []
        color_schemes = ["#ef4444", "#f59e0b", "#10b981", "#2563eb", "#8b5cf6", "#ec4899"]
        
        for idx, field in enumerate(numeric_fields):
            value = row_dict.get(field)
            try:
                if isinstance(value, str):
                    # Try to convert string to number
                    num_value = float(value)
                elif isinstance(value, (int, float)):
                    num_value = value
                else:
                    num_value = 0
            except (ValueError, TypeError):
                num_value = 0
            
            # Generate title from field name
            title = field.replace("_", " ").title()
            
            # Determine format
            field_lower = field.lower()
            if any(kw in field_lower for kw in ["rate", "percentage", "percent", "ratio", "drop_off"]):
                format_str = ".1%"
            elif any(kw in field_lower for kw in ["count", "total", "sum"]):
                format_str = ","
            else:
                format_str = ",.0f"
            
            # Select color based on field type
            if any(kw in field_lower for kw in ["drop_off", "failure", "error"]):
                color = "#ef4444"  # Red
            elif any(kw in field_lower for kw in ["count", "total"]):
                color = color_schemes[idx % len(color_schemes)]  # Rotate colors
            elif any(kw in field_lower for kw in ["completed", "success"]):
                color = "#10b981"  # Green
            else:
                color = color_schemes[idx % len(color_schemes)]
            
            kpi_chart = {
                "title": title,
                "data": {
                    "values": [{field: num_value}]
                },
                "mark": {
                    "type": "text",
                    "fontSize": 36,
                    "align": "center",
                    "baseline": "middle"
                },
                "encoding": {
                    "text": {
                        "field": field,
                        "type": "quantitative",
                        "format": format_str
                    },
                    "color": {
                        "value": color
                    }
                },
                "width": 150,
                "height": 100
            }
            
            kpi_charts.append(kpi_chart)
        
        return kpi_charts
    
    def _extract_title_from_query(self, query: str, field_name: str = None) -> str:
        """Extract meaningful title from query, avoiding generic terms like 'count'
        
        Args:
            query: User's natural language query
            field_name: Optional field name to use as fallback
            
        Returns:
            Meaningful title extracted from query
        """
        if not query:
            return field_name.replace("_", " ").title() if field_name else "KPI"
        
        query_lower = query.lower()
        field_lower = field_name.lower() if field_name else ""
        
        # Extract key concepts from query
        if "activit" in query_lower:
            if "average" in query_lower:
                if "per learner" in query_lower or "per user" in query_lower:
                    return "Average Activities per Learner"
                return "Average Activities"
            elif "number" in query_lower or "count" in query_lower or "total" in query_lower:
                if "per learner" in query_lower or "per user" in query_lower:
                    return "Number of Activities per Learner"
                return "Number of Activities"
            else:
                return "Activities"
        elif "learner" in query_lower:
            if "average" in query_lower:
                return "Average Learners"
            elif "number" in query_lower or "count" in query_lower or "total" in query_lower:
                return "Number of Learners"
            else:
                return "Learners"
        elif "completion" in query_lower or "complete" in query_lower:
            if "average" in query_lower:
                return "Average Completions"
            elif "rate" in query_lower:
                return "Completion Rate"
            else:
                return "Completions"
        elif "training" in query_lower or "course" in query_lower:
            if "average" in query_lower:
                return "Average Trainings"
            else:
                return "Trainings"
        else:
            # Fallback: use field name or first meaningful words from query
            if field_name:
                return field_name.replace("_", " ").title()
            # Extract first few words from query as title
            words = [w for w in query.split() if w.lower() not in ["show", "me", "the", "a", "an", "what", "is", "are", "how", "many"]]
            if words:
                return " ".join(words[:4]).title()
            return "KPI"
    
    def _is_comparison_kpi(self, columns: List[str], kpi_metadata: Dict[str, Any]) -> bool:
        """Check if this is a comparison KPI based on column names and metadata"""
        chart_subtype = kpi_metadata.get("chart_subtype", "")
        chart_type = kpi_metadata.get("chart_type", "")
        
        # Check metadata first
        if chart_subtype == "current_vs_percentage" or "comparison" in chart_type:
            return True
        
        # Check column names for comparison patterns
        # Need to check ALL columns independently, not use elif
        has_current = False
        has_previous = False
        
        for col in columns:
            col_lower = col.lower()
            # Check for current/this year patterns
            if any(keyword in col_lower for keyword in ["this_year", "current", "this_month", "now", "completed_this", "learners_this"]):
                has_current = True
            # Check for previous/last year patterns (separate check, not elif)
            if any(keyword in col_lower for keyword in ["last_year", "previous", "last_month", "prior", "before", "completed_last", "learners_last"]):
                has_previous = True
        
        return has_current and has_previous
    
    def _fix_encoding_for_original_data(
        self,
        kpi_schema: Dict[str, Any],
        columns: List[str],
        data_values: List[Dict[str, Any]],
        kpi_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fix encoding to use actual field names from original data
        
        Args:
            kpi_schema: KPI schema dictionary
            columns: Column names
            data_values: Original data values
            kpi_metadata: KPI metadata
            
        Returns:
            Fixed KPI schema with encoding using actual field names
        """
        try:
            if not data_values:
                return kpi_schema
            
            encoding = kpi_schema.get("encoding", {})
            first_item = data_values[0] if data_values else {}
            available_fields = list(first_item.keys()) if first_item else columns
            
            # Find the primary numeric field to display
            numeric_fields = []
            label_fields = []
            
            for field in available_fields:
                val = first_item.get(field)
                if val is not None:
                    try:
                        float_val = float(val) if isinstance(val, str) else val
                        if isinstance(float_val, (int, float)):
                            numeric_fields.append(field)
                    except (ValueError, TypeError):
                        # Non-numeric field, likely a label
                        if any(keyword in field.lower() for keyword in ["title", "name", "label", "category", "training"]):
                            label_fields.append(field)
            
            # Determine primary field to display
            if numeric_fields:
                # Prioritize: rate/percentage > count > other numeric
                def get_priority(field_name):
                    field_lower = field_name.lower()
                    if any(kw in field_lower for kw in ["rate", "percentage", "percent", "ratio", "drop_off"]):
                        return 1
                    elif any(kw in field_lower for kw in ["count", "total", "sum", "completed"]):
                        return 2
                    else:
                        return 3
                
                numeric_fields.sort(key=get_priority)
                primary_field = numeric_fields[0]
            else:
                # Fallback to first available field
                primary_field = available_fields[0] if available_fields else "value"
            
            # Set text encoding to use actual field name
            encoding["text"] = {
                "field": primary_field,
                "type": "quantitative"
            }
            
            # Add format based on field type
            if "rate" in primary_field.lower() or "percentage" in primary_field.lower() or "percent" in primary_field.lower():
                encoding["text"]["format"] = ".1%"
            elif "count" in primary_field.lower() or "total" in primary_field.lower():
                encoding["text"]["format"] = ","
            else:
                encoding["text"]["format"] = ",.0f"
            
            # Set color encoding
            if len(data_values) > 1 and label_fields:
                # Multiple rows with labels: use label field for color
                color_field = label_fields[0]
                encoding["color"] = {
                    "field": color_field,
                    "type": "nominal"
                }
            else:
                # Single value: use color from metadata or default
                color_scheme = kpi_metadata.get("color_scheme", "#2563eb")
                if isinstance(color_scheme, dict):
                    # Score KPI with thresholds
                    conditions = []
                    if "high" in color_scheme:
                        conditions.append({
                            "test": f"datum.{primary_field} >= 80",
                            "value": color_scheme["high"]
                        })
                    if "medium" in color_scheme:
                        conditions.append({
                            "test": f"datum.{primary_field} >= 50",
                            "value": color_scheme["medium"]
                        })
                    if conditions:
                        encoding["color"] = {
                            "condition": conditions,
                            "value": color_scheme.get("low", "#ef4444")
                        }
                    else:
                        encoding["color"] = {"value": color_scheme.get("high", "#2563eb")}
                else:
                    encoding["color"] = {"value": color_scheme}
            
            # Update mark properties
            if "mark" not in kpi_schema:
                kpi_schema["mark"] = {}
            if kpi_schema["mark"].get("type") != "text":
                kpi_schema["mark"]["type"] = "text"
            if "fontSize" not in kpi_schema["mark"]:
                kpi_schema["mark"]["fontSize"] = 36
            if "fontWeight" not in kpi_schema["mark"]:
                kpi_schema["mark"]["fontWeight"] = "bold"
            
            # Update encoding in schema
            kpi_schema["encoding"] = encoding
            
            return kpi_schema
            
        except Exception as e:
            logger.error(f"Error fixing encoding for original data: {e}")
            return kpi_schema
    
    def _transform_data_for_kpi_encoding(
        self,
        data_rows: List[Any],
        columns: List[str],
        encoding: Dict[str, Any],
        kpi_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Transform data rows to match KPI encoding field requirements
        
        Args:
            data_rows: List of data rows (can be list of lists or list of dicts)
            columns: Column names
            encoding: Encoding configuration from KPI schema
            kpi_metadata: KPI metadata
            
        Returns:
            Transformed data values list
        """
        try:
            if not data_rows or len(data_rows) == 0:
                return []
            
            # Get encoding field names
            text_field = encoding.get("text", {}).get("field", "value")
            color_field = encoding.get("color", {}).get("field")
            
            # Determine KPI subtype
            chart_subtype = kpi_metadata.get("chart_subtype", "")
            
            transformed = []
            
            # Handle all rows (KPI charts can have single or multiple metrics)
            if not data_rows:
                return []
            
            # Determine KPI subtype first to know what transformation to apply
            # Check if this is a comparison KPI by looking at column names
            has_current_prev_cols = False
            for col in columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ["this_year", "current", "this_month", "now", "completed_this"]):
                    if any(keyword in col_lower for keyword in ["last_year", "previous", "last_month", "prior", "before", "completed_last"]):
                        has_current_prev_cols = True
                        break
            
            is_comparison_kpi = (
                chart_subtype == "current_vs_percentage" or 
                "comparison" in kpi_metadata.get("chart_type", "") or
                has_current_prev_cols
            )
            
            # Process each row
            for row in data_rows:
                # Convert row to dict if it's a list
                if isinstance(row, list):
                    row_dict = dict(zip(columns, row))
                else:
                    row_dict = row
                
                # Transform based on KPI subtype
                if is_comparison_kpi:
                    # Comparison KPI: need current, previous, percentage_change
                    # Find current and previous columns
                    current_col = None
                    previous_col = None
                    percentage_change_col = None
                    
                    for col in columns:
                        col_lower = col.lower()
                        # Check for current/this year patterns (separate checks, not elif)
                        if any(keyword in col_lower for keyword in ["this_year", "current", "this_month", "now", "completed_this", "learners_this"]):
                            if not current_col:  # Only set if not already found
                                current_col = col
                        # Check for previous/last year patterns (separate check)
                        if any(keyword in col_lower for keyword in ["last_year", "previous", "last_month", "prior", "before", "completed_last", "learners_last"]):
                            if not previous_col:  # Only set if not already found
                                previous_col = col
                        # Check for percentage_change (separate check)
                        if "percentage_change" in col_lower or "percent_change" in col_lower:
                            if not percentage_change_col:  # Only set if not already found
                                percentage_change_col = col
                    
                    logger.info(f"Comparison KPI column detection: current_col={current_col}, previous_col={previous_col}, percentage_change_col={percentage_change_col}")
                    
                    if current_col and previous_col:
                        current_val = float(row_dict.get(current_col, 0)) if isinstance(row_dict.get(current_col), (str, int, float)) else 0
                        previous_val = float(row_dict.get(previous_col, 0)) if isinstance(row_dict.get(previous_col), (str, int, float)) else 0
                        
                        if percentage_change_col and percentage_change_col in row_dict:
                            pct_change = float(row_dict[percentage_change_col]) if isinstance(row_dict[percentage_change_col], (str, int, float)) else 0
                            logger.info(f"Using existing percentage_change value: {pct_change}")
                        else:
                            # Calculate percentage change
                            pct_change = ((current_val - previous_val) / previous_val * 100) if previous_val != 0 else 0
                            logger.info(f"Calculated percentage_change: {pct_change}")
                        
                        # Add label if available (e.g., training_title)
                        label_col = None
                        for col in columns:
                            if any(keyword in col.lower() for keyword in ["title", "name", "label", "category"]):
                                label_col = col
                                break
                        
                        transformed_item = {
                            "current": current_val,
                            "previous": previous_val,
                            "percentage_change": pct_change
                        }
                        if label_col and label_col in row_dict:
                            transformed_item["label"] = str(row_dict[label_col])
                        
                        transformed.append(transformed_item)
                
                elif chart_subtype in ["counter", "percentage", "score"] or not chart_subtype:
                    # Single value KPI: need value field
                    # Try to find the most appropriate numeric column
                    numeric_cols = []
                    for col in columns:
                        val = row_dict.get(col)
                        if val is not None:
                            try:
                                float_val = float(val) if isinstance(val, str) else val
                                if isinstance(float_val, (int, float)):
                                    numeric_cols.append((col, float_val))
                            except (ValueError, TypeError):
                                pass
                    
                    if numeric_cols:
                        # For single value KPIs, prefer rate/percentage columns, then count columns
                        # Sort by priority: rate/percentage > count > other numeric
                        def get_priority(col_name):
                            col_lower = col_name.lower()
                            if any(kw in col_lower for kw in ["rate", "percentage", "percent", "ratio"]):
                                return 1
                            elif any(kw in col_lower for kw in ["count", "total", "sum"]):
                                return 2
                            else:
                                return 3
                        
                        numeric_cols.sort(key=lambda x: (get_priority(x[0]), -x[1]))  # Sort by priority, then by value (desc)
                        
                        # Use the highest priority numeric column as the main value
                        primary_col_name, primary_col_value = numeric_cols[0]
                        
                        # Check if there's a label/category column
                        label_col = None
                        for col in columns:
                            if any(keyword in col.lower() for keyword in ["title", "name", "label", "category", "training"]):
                                label_col = col
                                break
                        
                        # For single value KPIs, add label from query or use column name
                        # The correct format should have "label" and "value" fields
                        transformed_item = {"value": primary_col_value}
                        
                        # Add label - prefer from data, then use column name or default
                        if label_col and label_col in row_dict:
                            transformed_item["label"] = str(row_dict[label_col])
                        else:
                            # Use a descriptive label based on column name
                            label_name = primary_col_name.replace("_", " ").title()
                            transformed_item["label"] = label_name
                        
                        # Add metric only if multiple rows (for multi-metric KPIs)
                        if len(data_rows) > 1:
                            if label_col and label_col in row_dict:
                                transformed_item["metric"] = str(row_dict[label_col])
                            elif len(numeric_cols) > 1:
                                # Use column name as metric
                                transformed_item["metric"] = primary_col_name
                        
                        transformed.append(transformed_item)
                    else:
                        # Fallback: use first column as value
                        first_val = row_dict.get(columns[0] if columns else "", 0)
                        try:
                            num_val = float(first_val) if isinstance(first_val, str) else first_val
                            label_name = (columns[0].replace("_", " ").title() if columns else "Value")
                            transformed.append({"value": num_val, "label": label_name})
                        except (ValueError, TypeError):
                            transformed.append({"value": 0, "label": "Value"})
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming data for KPI encoding: {e}")
            return []
    
    def _fix_kpi_encoding_for_data(
        self,
        kpi_schema: Dict[str, Any],
        transformed_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fix encoding to match the transformed data structure
        
        Args:
            kpi_schema: KPI schema dictionary
            transformed_data: Transformed data values
            
        Returns:
            Fixed KPI schema with correct encoding
        """
        try:
            if not transformed_data:
                return kpi_schema
            
            encoding = kpi_schema.get("encoding", {})
            kpi_metadata = kpi_schema.get("kpi_metadata", {})
            chart_subtype = kpi_metadata.get("chart_subtype", "")
            
            # Check what fields are in the transformed data
            first_item = transformed_data[0] if transformed_data else {}
            has_metric = "metric" in first_item
            has_label = "label" in first_item
            
            # Fix encoding based on actual data structure (check for comparison KPI fields)
            if isinstance(first_item, dict) and "current" in first_item and "previous" in first_item:
                # Comparison KPI: encoding should use display_text (calculated)
                logger.info("Fixing encoding for comparison KPI with transformed data")
                
                # Ensure transform exists to calculate display_text
                if "transform" not in kpi_schema:
                    kpi_schema["transform"] = []
                
                # Check if display_text transform exists
                has_display_text_transform = any(
                    t.get("as") == "display_text" for t in kpi_schema.get("transform", [])
                )
                
                if not has_display_text_transform:
                    # Add transform to calculate display_text
                    # percentage_change is already a percentage value (e.g., 7.83 means 7.83%)
                    # So we divide by 100 to get decimal form for percentage formatting
                    kpi_schema["transform"] = [
                        {
                            "calculate": "format(datum.current, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'",
                            "as": "display_text"
                        }
                    ]
                    logger.info("Added display_text transform for comparison KPI")
                
                # Force encoding to use display_text
                encoding["text"] = {"field": "display_text", "type": "nominal"}
                
                # Color should be based on percentage_change (condition, not field)
                encoding["color"] = {
                    "condition": {
                        "test": "datum.percentage_change > 0",
                        "value": "#16a34a"
                    },
                    "value": "#ef4444"
                }
                
                logger.info(f"Fixed encoding for comparison KPI: text.field=display_text, color based on percentage_change")
            else:
                # Single value KPI: encoding should use "value" field
                if "text" not in encoding or encoding.get("text", {}).get("field") != "value":
                    encoding["text"] = {"field": "value", "type": "quantitative"}
                
                # Fix color encoding
                if has_metric:
                    # Multiple metrics: use metric field for color
                    if "color" not in encoding or encoding.get("color", {}).get("field") != "metric":
                        encoding["color"] = {"field": "metric", "type": "nominal"}
                else:
                    # Single value: use color value from metadata or default
                    color_scheme = kpi_metadata.get("color_scheme", "#2563eb")
                    if isinstance(color_scheme, dict):
                        # Score KPI with thresholds
                        conditions = []
                        if "high" in color_scheme:
                            conditions.append({
                                "test": "datum.value >= 80",
                                "value": color_scheme["high"]
                            })
                        if "medium" in color_scheme:
                            conditions.append({
                                "test": "datum.value >= 50",
                                "value": color_scheme["medium"]
                            })
                        if conditions:
                            encoding["color"] = {
                                "condition": conditions,
                                "value": color_scheme.get("low", "#ef4444")
                            }
                        else:
                            encoding["color"] = {"value": color_scheme.get("high", "#2563eb")}
                    else:
                        # Single color value
                        encoding["color"] = {"value": color_scheme}
            
            # Update mark properties if needed
            if "mark" not in kpi_schema:
                kpi_schema["mark"] = {}
            if kpi_schema["mark"].get("type") != "text":
                kpi_schema["mark"]["type"] = "text"
            if "fontSize" not in kpi_schema["mark"]:
                kpi_schema["mark"]["fontSize"] = 36
            if "fontWeight" not in kpi_schema["mark"]:
                kpi_schema["mark"]["fontWeight"] = "bold"
            
            # Apply formatting to all KPI charts based on subtype (for quantitative text fields)
            text_encoding = encoding.get("text", {})
            if text_encoding.get("type") == "quantitative" and "format" not in text_encoding:
                # Add format based on chart subtype
                if chart_subtype == "percentage":
                    text_encoding["format"] = ".0%"
                elif chart_subtype == "score":
                    text_encoding["format"] = ".0f"
                else:
                    text_encoding["format"] = ","
                encoding["text"] = text_encoding
                logger.info(f"Applied format '{text_encoding.get('format')}' to KPI chart based on subtype '{chart_subtype}'")
            
            # Update encoding in schema
            kpi_schema["encoding"] = encoding
            
            return kpi_schema
            
        except Exception as e:
            logger.error(f"Error fixing KPI encoding: {e}")
            return kpi_schema
    
    async def _generate_kpi_chart_with_llm(
        self,
        query: str,
        columns: List[str],
        sample_data: Dict[str, Any],
        sample_column_values: Dict[str, Any],
        language: str,
        existing_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate KPI chart schema using LLM with specialized KPI prompt
        
        Args:
            query: Natural language query
            columns: Column names
            sample_data: Preprocessed sample data
            sample_column_values: Sample column values
            language: Language for the chart
            existing_schema: Existing chart schema
            
        Returns:
            KPI chart schema dictionary
        """
        try:
            kpi_system_prompt = f"""
            ### CRITICAL: JSON-ONLY RESPONSE REQUIRED ###
            
            **YOU MUST RESPOND WITH ONLY VALID JSON. NO TEXT BEFORE OR AFTER. NO MARKDOWN. NO CODE BLOCKS. NO EXPLANATIONS.**
            
            Your response must start with {{ and end with }}. Nothing else.
            
            If you include any text, markdown, or explanations, your response will be rejected.
            
            ### TASK ###
            
            You are an expert at creating KPI (Key Performance Indicator) charts using Vega-Lite! Given the user's question, data columns, sample data, and sample column values, you need to generate a specialized KPI chart schema.
            
            KPI charts are single-value visualizations that display important metrics. There are four main types of KPI charts:
            
            ### 1. COUNTER KPI ###
            Purpose: Displays a single numeric count or total value.
            
            Schema Structure:
            {{
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "data": {{
                    "values": [{{ "label": "<LABEL>", "value": <NUMERIC_VALUE> }}]
                }},
                "mark": {{ "type": "text", "fontSize": 36, "fontWeight": "bold" }},
                "encoding": {{
                    "text": {{ "field": "value", "type": "quantitative", "format": "," }},
                    "color": {{ "value": "#2563eb" }}
                }},
                "title": "<TITLE>",
                "kpi_metadata": {{
                    "chart_type": "metric_kpi",
                    "chart_subtype": "counter",
                    "format": ",",
                    "color_scheme": "#2563eb",
                    "description": "Displays a single numeric count or total value"
                }}
            }}
            
            ### 2. PERCENTAGE KPI ###
            Purpose: Displays a metric as a percentage (0–1 scaled value).
            
            Schema Structure:
            {{
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "data": {{
                    "values": [{{ "label": "<LABEL>", "value": <0_TO_1_VALUE> }}]
                }},
                "mark": {{ "type": "text", "fontSize": 36, "fontWeight": "bold" }},
                "encoding": {{
                    "text": {{ "field": "value", "type": "quantitative", "format": ".0%" }},
                    "color": {{ "value": "#10b981" }}
                }},
                "title": "<TITLE>",
                "kpi_metadata": {{
                    "chart_type": "metric_kpi",
                    "chart_subtype": "percentage",
                    "format": ".0%",
                    "color_scheme": "#10b981",
                    "description": "Displays a metric as a percentage (0–1 scaled value)"
                }}
            }}
            
            ### 3. SCORE KPI ###
            Purpose: Displays a score (0–100) with color thresholds for high, medium, and low values.
            
            Schema Structure:
            {{
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "data": {{
                    "values": [{{ "label": "<LABEL>", "value": <0_TO_100_VALUE> }}]
                }},
                "mark": {{ "type": "text", "fontSize": 36, "fontWeight": "bold" }},
                "encoding": {{
                    "text": {{ "field": "value", "type": "quantitative", "format": ".0f" }},
                    "color": {{
                        "condition": [
                            {{ "test": "datum.value >= 80", "value": "#16a34a" }},
                            {{ "test": "datum.value >= 50", "value": "#f59e0b" }}
                        ],
                        "value": "#ef4444"
                    }}
                }},
                "title": "<TITLE>",
                "kpi_metadata": {{
                    "chart_type": "metric_kpi",
                    "chart_subtype": "score",
                    "format": ".0f",
                    "color_scheme": {{
                        "high": "#16a34a",
                        "medium": "#f59e0b",
                        "low": "#ef4444"
                    }},
                    "description": "Displays a score (0–100) with color thresholds"
                }}
            }}
            
            ### 4. COMPARISON KPI ###
            Purpose: Shows current value with percentage increase or decrease compared to a previous value.
            
            Schema Structure (when percentage_change column exists in data):
            {{
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "data": {{
                    "values": [
                        {{ "label": "<LABEL>", "current": <CURRENT_VALUE>, "previous": <PREVIOUS_VALUE>, "percentage_change": <PERCENTAGE_CHANGE_VALUE> }}
                    ]
                }},
                "transform": [
                    {{
                        "calculate": "format(datum.current, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'",
                        "as": "display_text"
                    }}
                ],
                "mark": {{ "type": "text", "fontSize": 36, "fontWeight": "bold" }},
                "encoding": {{
                    "text": {{ "field": "display_text", "type": "nominal" }},
                    "color": {{
                        "condition": {{
                            "test": "datum.percentage_change > 0",
                            "value": "#16a34a"
                        }},
                        "value": "#ef4444"
                    }}
                }},
                "title": "<TITLE> vs Previous",
                "kpi_metadata": {{
                    "chart_type": "comparison_kpi",
                    "chart_subtype": "current_vs_percentage",
                    "columns": ["label", "current", "previous", "percentage_change"],
                    "comparison_logic": {{
                        "positive": "current > previous",
                        "negative": "current < previous",
                        "neutral": "current == previous"
                    }},
                    "format": "+.1%",
                    "positive_color": "#16a34a",
                    "negative_color": "#ef4444",
                    "description": "Shows current value with percentage increase or decrease compared to a previous value"
                }}
            }}
            
            Schema Structure (when percentage_change needs to be calculated):
            {{
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "data": {{
                    "values": [
                        {{ "label": "<LABEL>", "current": <CURRENT_VALUE>, "previous": <PREVIOUS_VALUE> }}
                    ]
                }},
                "transform": [
                    {{
                        "calculate": "(datum.current - datum.previous) / datum.previous",
                        "as": "percentage_change"
                    }},
                    {{
                        "calculate": "format(datum.current, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'",
                        "as": "display_text"
                    }}
                ],
                "mark": {{ "type": "text", "fontSize": 36, "fontWeight": "bold" }},
                "encoding": {{
                    "text": {{ "field": "display_text", "type": "nominal" }},
                    "color": {{
                        "condition": {{
                            "test": "datum.percentage_change > 0",
                            "value": "#16a34a"
                        }},
                        "value": "#ef4444"
                    }}
                }},
                "title": "<TITLE> vs Previous",
                "kpi_metadata": {{
                    "chart_type": "comparison_kpi",
                    "chart_subtype": "current_vs_percentage",
                    "columns": ["label", "current", "previous", "percentage_change"],
                    "comparison_logic": {{
                        "positive": "current > previous",
                        "negative": "current < previous",
                        "neutral": "current == previous"
                    }},
                    "format": "+.1%",
                    "positive_color": "#16a34a",
                    "negative_color": "#ef4444",
                    "description": "Shows current value with percentage increase or decrease compared to a previous value"
                }}
            }}
            
            ### DECISION CRITERIA ###
            
            Choose the appropriate KPI subtype based on:
            
            1. **Counter KPI**: Use when displaying a single count, total, sum, or aggregate value. The value can be any positive number.
            
            2. **Percentage KPI**: Use when:
               - Column names contain words like "percent", "rate", "ratio", "completion"
               - The value is between 0 and 1 (or can be normalized to 0-1)
               - The query mentions percentages, rates, or ratios
            
            3. **Score KPI**: Use when:
               - The query mentions "score", "rating", "satisfaction", "performance", "quality"
               - The value is typically between 0 and 100
               - You want to show performance with color-coded thresholds
            
            4. **Comparison KPI**: Use when:
               - There are two numeric columns (current vs previous, this month vs last month, etc.)
               - Column names contain "current", "previous", "prior", "last", "this_year", "last_year", "this_month", "last_month"
               - There is a "percentage_change" or similar column indicating change
               - The query mentions comparison, change, increase, decrease, growth, vs, versus, compare
               - You want to show both the current value and the percentage change
               - Example column patterns: "learners_this_year" and "learners_last_year" with "percentage_change"
            
            ### OUTPUT FORMAT - CRITICAL ###
            
            **REMINDER: YOU MUST RESPOND WITH ONLY VALID JSON. NO TEXT. NO MARKDOWN. NO CODE BLOCKS.**
            
            Your response must be a single JSON object starting with {{ and ending with }}.
            
            DO NOT include:
            - Any text before the JSON
            - Any text after the JSON
            - Markdown formatting (```json or ```)
            - Code blocks
            - Explanations
            - Conversational responses
            - Questions
            
            If you respond with anything other than pure JSON, your response will fail.
            
            ### CRITICAL REQUIREMENTS - READ CAREFULLY ###
            
            **NEVER CREATE DUMMY CHARTS:**
            - DO NOT set `is_dummy: true` in kpi_metadata
            - DO NOT set `vega_lite_compatible: false`
            - DO NOT set `requires_custom_template: true`
            - ALWAYS generate a complete, functional KPI chart schema
            - The chart MUST be ready to render without post-processing
            
            **ALWAYS DETECT COMPARISON KPIs CORRECTLY:**
            - If columns contain patterns like "this_year", "last_year", "current", "previous", "completed_this", "completed_last", "learners_this", "learners_last"
            - AND there are two numeric columns representing current vs previous values
            - THEN you MUST generate a Comparison KPI (chart_type: "comparison_kpi")
            - DO NOT generate a Counter or other KPI type for comparison data
            
            **CRITICAL DATA TRANSFORMATION REQUIREMENTS:**
            
            **CRITICAL: ENCODING FIELD MUST MATCH DATA FIELD**
            
            The most important rule: The field name in `encoding.text.field` MUST EXACTLY match a field name that exists in `data.values`.
            
            **WRONG (will fail):**
            - data.values: [{{"count": 37642}}]
            - encoding.text.field: "value"  <-- ERROR: "value" doesn't exist in data!
            
            **CORRECT:**
            - data.values: [{{"count": 37642}}]
            - encoding.text.field: "count"  <-- CORRECT: matches the data field
            
            **For Counter/Percentage/Score KPIs:**
            - ALWAYS use the actual field name from the sample_data in encoding.text.field
            - If sample_data has {{"count": 123}}, use encoding.text.field: "count"
            - If sample_data has {{"total_users": 456}}, use encoding.text.field: "total_users"
            - If sample_data has {{"completion_rate": 0.85}}, use encoding.text.field: "completion_rate"
            - NEVER use generic field names like "value" or "metric" unless the actual data has those exact field names
            - Extract numeric values from sample_data and keep the original field names
            - If multiple metrics, create separate data objects with their original field names
            
            **For Comparison KPIs (MOST IMPORTANT):**
            - Encoding MUST use: `text.field: "display_text"` (NOT "value" or any other field)
            - Encoding MUST use: `color.condition` based on `percentage_change` (NOT `color.field: "metric"`)
            
            **Two types of Comparison KPIs:**
            
            1. **Full Comparison KPI** (has both current and previous columns):
               - Data: `{{"completed_this_year": <CURRENT_VALUE>, "completed_last_year": <PREVIOUS_VALUE>, "percentage_change": <PERCENTAGE_CHANGE>}}`
               - Transform: `format(datum.completed_this_year, ',.0f') + ' vs ' + format(datum.completed_last_year, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'`
               - Display: "X vs Y (Z%)"
            
            2. **Single Value with Percentage Change** (has one value column + percentage_change, no separate previous column):
               - Data: `{{"total_time_spent": <VALUE>, "percentage_change": <PERCENTAGE_CHANGE>}}`
               - Transform: `format(datum.total_time_spent, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'`
               - Display: "X (Z%)" (NOT "X vs X (Z%)")
            
            3. **Only Percentage Change** (has ONLY percentage_change column, no other value columns):
               - Data: `{{"percentage_change": <PERCENTAGE_CHANGE>}}`
               - Transform: `format(datum.percentage_change / 100, '+.1%')`
               - Display: "+Z%" or "-Z%" (just the percentage change)
               - CRITICAL: Always divide by 100 when formatting percentage_change (e.g., `format(datum.percentage_change / 100, '+.1%')`)
            
            - DO NOT transform column names - keep them as they are in the original data
            - Convert string values to numbers: "17035.0" → 17035.0 (keep as float)
            - percentage_change is typically already a percentage value (e.g., 7.83 means 7.83%), so ALWAYS divide by 100 in the format expression
            - If you only have ONE value column + percentage_change (no separate previous column), use format "X (Z%)" NOT "X vs Y (Z%)"
            - If you ONLY have percentage_change (no other columns), display just the formatted percentage: "+Z%" or "-Z%"
            
            **IMPORTANT RULES:**
            - DO NOT use the original column names in encoding if they don't match the expected field names
            - ALWAYS transform the data to have the fields that the encoding expects
            - Extract actual numeric values from the sample data and convert strings to numbers
            - For percentage KPI, normalize values > 1 by dividing by 100
            - For comparison KPI with percentage_change already calculated:
              * Use the percentage_change value directly from the data
              * In the transform, divide by 100 when formatting (e.g., `format(datum.percentage_change / 100, '+.1%')`)
              * Display as: "current_value (+percentage_change%)" or "current_value (-percentage_change%)"
            **CRITICAL: TITLE AND LABEL GENERATION:**
            - ALWAYS use the user's query/question to determine meaningful titles and labels
            - DO NOT use generic terms like "count", "value", "metric" - use specific terms from the query
            - If the query mentions "activities", use "Activities" not "Count"
            - If the query mentions "learners", use "Learners" not "Count"
            - Extract meaningful nouns and concepts from the query to create descriptive titles
            - Example: Query "average activities per learner" → Title: "Average Activities per Learner" (NOT "Count" or "Average Count")
            - Example: Query "number of learners" → Title: "Number of Learners" (NOT "Count")
            - Preserve any existing title from the existing_schema if provided
            - The data.values array MUST contain transformed data with the correct field names
            - The encoding MUST reference the transformed field names, NOT the original column names
            
            **STEP-BY-STEP CHECKLIST FOR COMPARISON KPIs:**
            
            1. Check if columns contain comparison patterns (this_year/last_year, current/previous, etc.)
            2. If YES, you MUST generate a Comparison KPI (NOT Counter or other type)
            3. Transform data.values:
               - Map "completed_this_year" or "learners_this_year" → "current" (convert string to number)
               - Map "completed_last_year" or "learners_last_year" → "previous" (convert string to number)
               - Keep "percentage_change" if it exists (convert string to number)
            4. Add transform array with display_text calculation
            5. Set encoding.text.field to "display_text" (NOT "value")
            6. Set encoding.color to condition based on percentage_change (NOT field: "metric")
            7. Set kpi_metadata.chart_type to "comparison_kpi"
            8. DO NOT set is_dummy, vega_lite_compatible, or requires_custom_template
            
            **EXAMPLE TRANSFORMATIONS:**
            
            Example 1 - Comparison KPI (CORRECT):
            Input columns: ["completed_this_year", "completed_last_year", "percentage_change"]
            Input sample_data: {{"completed_this_year": "17035.0", "completed_last_year": "15798.0", "percentage_change": "7.830105076591973"}}
            
            Output schema:
            {{
                "data": {{
                    "values": [{{
                        "completed_this_year": 17035.0,
                        "completed_last_year": 15798.0,
                        "percentage_change": 7.830105076591973
                    }}]
                }},
                "transform": [{{
                    "calculate": "format(datum.completed_this_year, ',.0f') + ' vs ' + format(datum.completed_last_year, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'",
                    "as": "display_text"
                }}],
                "encoding": {{
                    "text": {{"field": "display_text", "type": "nominal"}},
                    "color": {{
                        "condition": {{"test": "datum.percentage_change > 0", "value": "#16a34a"}},
                        "value": "#ef4444"
                    }}
                }},
                "kpi_metadata": {{
                    "chart_type": "comparison_kpi",
                    "chart_subtype": "current_vs_percentage"
                }}
            }}
            
            Example 2 - Comparison KPI (WRONG - DO NOT DO THIS):
            DO NOT generate schemas like this:
            - encoding.text.field = "value" (WRONG: should be "display_text")
            - encoding.color.field = "metric" (WRONG: should be condition based on percentage_change)
            - data.values with original column names like "completed_this_year" (WRONG: should be "current")
            - kpi_metadata.is_dummy = true (WRONG: never set this)
            - kpi_metadata.vega_lite_compatible = false (WRONG: never set this)
            
            Example 3 - Counter KPI with actual data:
            Input data: {{"total_learners": "24215"}}
            Transformed data.values: [{{"value": 24215}}]
            Encoding uses: "value" field
            
            Example 4 - Multiple metrics KPI:
            Input data: [{{"metric_name": "Sales", "value": 1000}}, {{"metric_name": "Revenue", "value": 2000}}]
            Transformed data.values: [{{"metric": "Sales", "value": 1000}}, {{"metric": "Revenue", "value": 2000}}]
            Encoding uses: "value" for text, "metric" for color
            
            Example 5 - Only Percentage Change KPI (CORRECT):
            Input columns: ["percentage_change"]
            Input sample_data: {{"percentage_change": "7.071776413296633"}}
            
            Output schema:
            {{
                "data": {{
                    "values": [{{
                        "percentage_change": 7.071776413296633
                    }}]
                }},
                "transform": [{{
                    "calculate": "format(datum.percentage_change / 100, '+.1%')",
                    "as": "display_text"
                }}],
                "encoding": {{
                    "text": {{"field": "display_text", "type": "nominal"}},
                    "color": {{
                        "condition": {{"test": "datum.percentage_change > 0", "value": "#16a34a"}},
                        "value": "#ef4444"
                    }}
                }},
                "kpi_metadata": {{
                    "chart_type": "comparison_kpi",
                    "chart_subtype": "current_vs_percentage"
                }}
            }}
            
            Example 6 - Only Percentage Change KPI (WRONG - DO NOT DO THIS):
            DO NOT generate transforms like:
            - "format(datum.percentage_change, '+.1%')" (WRONG: missing / 100 division)
            - This would show "+707.2%" instead of "+7.1%" for a value of 7.07
            """
            
            kpi_user_prompt = f"""
            ### INPUT ###
            Question: {query}
            Columns: {json.dumps(columns)}
            Sample Data: {json.dumps(sample_data)}
            Sample Column Values: {json.dumps(sample_column_values)}
            Language: {language}
            Existing Schema: {json.dumps(existing_schema) if existing_schema else "None"}
            
            ### YOUR TASK ###
            
            Please analyze the data and generate the most appropriate KPI chart schema based on the question and data structure.
            
            **CRITICAL REMINDERS:**
            0. **TITLE AND LABEL GENERATION (MOST IMPORTANT):**
               - Use the user's query/question to create meaningful titles - DO NOT use generic terms
               - Extract key concepts from the query (e.g., "activities", "learners", "completions")
               - If query says "activities", title should say "Activities" NOT "Count"
               - If query says "learners", title should say "Learners" NOT "Count"
               - Example: Query "average activities per learner" → Title: "Average Activities per Learner"
               - Example: Query "number of learners" → Title: "Number of Learners"
               - NEVER use generic terms like "Count", "Value", "Metric" when the query has specific terms
            1. Check if this is a comparison KPI (look for "this_year"/"last_year", "current"/"previous" patterns in column names OR percentage_change column)
            2. If comparison KPI:
               - Check if you have BOTH current and previous columns (e.g., "completed_this_year" AND "completed_last_year")
                 * If YES: Use format "X vs Y (Z%)" - transform: "format(datum.completed_this_year, ',.0f') + ' vs ' + format(datum.completed_last_year, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'"
                 * If NO (only one value column + percentage_change): Use format "X (Z%)" - transform: "format(datum.total_time_spent, ',.0f') + ' (' + format(datum.percentage_change / 100, '+.1%') + ')'"
                 * If ONLY percentage_change (no other columns): Use format "+Z%" or "-Z%" - transform: "format(datum.percentage_change / 100, '+.1%')"
               - CRITICAL: ALWAYS divide percentage_change by 100 when formatting (e.g., `format(datum.percentage_change / 100, '+.1%')`)
               - Keep original column names in data (DO NOT transform to "current"/"previous")
               - Convert string values to numbers (e.g., "17035.0" → 17035.0, "7.07" → 7.07)
               - Use encoding.text.field = "display_text" (NOT "value" or "percentage_change")
               - Use encoding.text.type = "nominal" (NOT "quantitative")
               - Use encoding.color.condition based on percentage_change (NOT color.field = "metric")
               - Set chart_type = "comparison_kpi"
            3. NEVER set is_dummy, vega_lite_compatible: false, or requires_custom_template
            4. Generate a complete, functional chart schema ready to render
            
            ### CRITICAL OUTPUT REQUIREMENT ###
            
            **YOU MUST RESPOND WITH ONLY VALID JSON.**
            
            - Start your response with {{ (opening brace)
            - End your response with }} (closing brace)
            - Do NOT include any text before or after the JSON
            - Do NOT use markdown code blocks
            - Do NOT include explanations or conversational text
            - Do NOT say "I'm here to help" or ask questions
            
            Your response must be pure JSON that can be parsed directly.
            
            Generate the KPI chart schema now as JSON:
            """
            
            # Generate KPI schema using LLM
            # Use ChatPromptTemplate with SystemMessage and HumanMessage, then pipe to LLM
            # This ensures the LLM recognizes the system prompt as instructions, not conversation
            logger.info("Generating KPI chart schema with LLM using pipe pattern with SystemMessage")
            
            # Create messages with SystemMessage and HumanMessage
            messages = [
                SystemMessage(content=kpi_system_prompt),
                HumanMessage(content=kpi_user_prompt)
            ]
            
            # Create ChatPromptTemplate from messages
            chat_prompt = ChatPromptTemplate.from_messages(messages)
            
            # Use pipe pattern: ChatPromptTemplate -> LLM
            chain = chat_prompt | self.agent.llm
            
            # Invoke the chain
            result = chain.invoke({})
            
            # Extract content from the response
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            logger.info(f"Raw LLM KPI response: {result_str}")
            
            # Parse JSON response
            try:
                # First try to parse the raw result
                parsed = orjson.loads(result_str)
                logger.info(f"Successfully parsed KPI JSON directly: {parsed}")
                return parsed
            except orjson.JSONDecodeError:
                # If parsing fails, try to extract JSON from the text
                import re
                
                # Look for JSON blocks in the text
                json_patterns = [
                    r'```json\s*(\{{.*?\}})\s*```',  # JSON code blocks
                    r'```\s*(\{{.*?\}})\s*```',      # Generic code blocks
                    r'(\{{.*?\}})',                  # Any JSON object
                ]
                
                for pattern in json_patterns:
                    json_matches = re.findall(pattern, result_str, re.DOTALL)
                    for match in json_matches:
                        try:
                            parsed = orjson.loads(match)
                            logger.info(f"Successfully parsed KPI JSON from pattern {pattern}: {parsed}")
                            return parsed
                        except orjson.JSONDecodeError:
                            continue
                
                # If all parsing attempts fail, generate a fallback schema based on data
                logger.warning("Failed to parse JSON from LLM KPI response. Generating fallback schema.")
                
                # Generate a fallback comparison KPI schema if we have comparison patterns
                # Use original column names (not lowercase) for data access
                col_names_lower = [col.lower() if isinstance(col, str) else str(col).lower() for col in columns]
                has_current = any(any(kw in col for kw in ["this_year", "current", "this_month", "completed_this", "learners_this"]) for col in col_names_lower)
                has_previous = any(any(kw in col for kw in ["last_year", "previous", "last_month", "prior", "completed_last", "learners_last"]) for col in col_names_lower)
                has_percentage_change = any("percentage_change" in col or "percent_change" in col for col in col_names_lower)
                
                if has_current and has_previous:
                    # Generate comparison KPI fallback
                    logger.info("Generating fallback comparison KPI schema")
                    fallback_schema = self._generate_fallback_comparison_kpi_schema(
                        columns, sample_data, query, language
                    )
                    return fallback_schema
                else:
                    # Generate simple counter KPI fallback
                    logger.info("Generating fallback counter KPI schema")
                    fallback_schema = self._generate_fallback_counter_kpi_schema(
                        columns, sample_data, query, language
                    )
                    return fallback_schema
            
        except Exception as e:
            logger.error(f"Error generating KPI chart with LLM: {e}")
            return {}
    
    def _generate_fallback_comparison_kpi_schema(
        self,
        columns: List[str],
        sample_data: Any,
        query: str,
        language: str
    ) -> Dict[str, Any]:
        """Generate a fallback comparison KPI schema when LLM fails"""
        try:
            # Find current and previous columns
            current_col = None
            previous_col = None
            percentage_change_col = None
            
            for col in columns:
                col_lower = str(col).lower()
                if not current_col and any(kw in col_lower for kw in ["this_year", "current", "this_month", "completed_this", "learners_this"]):
                    current_col = col
                elif not previous_col and any(kw in col_lower for kw in ["last_year", "previous", "last_month", "prior", "completed_last", "learners_last"]):
                    previous_col = col
                elif not percentage_change_col and ("percentage_change" in col_lower or "percent_change" in col_lower):
                    percentage_change_col = col
            
            # Extract values from sample data - handle both dict and list formats
            data_values = []
            if isinstance(sample_data, list):
                # sample_data is a list directly
                data_values = sample_data
            elif isinstance(sample_data, dict):
                # sample_data is a dict - check for "data" or "values" keys
                data_values = sample_data.get("data", sample_data.get("values", []))
                # If still empty, check if sample_data itself contains the data
                if not data_values and sample_data:
                    # Check if sample_data has column names as keys
                    if any(col in sample_data for col in columns):
                        data_values = [sample_data]
            else:
                logger.warning(f"Unexpected sample_data type: {type(sample_data)}")
                return {}
            
            if not data_values or len(data_values) == 0:
                logger.warning("No data values found in sample_data for fallback comparison KPI")
                return {}
            
            # Get first row - handle both dict and list formats
            first_row = {}
            if isinstance(data_values[0], dict):
                first_row = data_values[0]
            elif isinstance(data_values[0], list) and columns:
                first_row = dict(zip(columns, data_values[0]))
            else:
                logger.warning(f"Unexpected data_values[0] type: {type(data_values[0])}")
                return {}
            
            # Transform values
            current_val = 0
            previous_val = 0
            percentage_change_val = 0
            
            if current_col and current_col in first_row:
                try:
                    current_val = float(str(first_row[current_col]).replace(',', ''))
                except (ValueError, TypeError):
                    pass
            
            if previous_col and previous_col in first_row:
                try:
                    previous_val = float(str(first_row[previous_col]).replace(',', ''))
                except (ValueError, TypeError):
                    pass
            
            if percentage_change_col and percentage_change_col in first_row:
                try:
                    percentage_change_val = float(str(first_row[percentage_change_col]).replace(',', ''))
                except (ValueError, TypeError):
                    pass
            elif current_val != 0 and previous_val != 0:
                # Calculate percentage change
                percentage_change_val = ((current_val - previous_val) / previous_val) * 100
                # If percentage_change_col wasn't found, use a default name
                if not percentage_change_col:
                    percentage_change_col = "percentage_change"
            
            # Ensure we have all required columns
            if not current_col or not previous_col:
                logger.warning("Missing required columns for comparison KPI fallback")
                return {}
            
            # Use default percentage_change if not found
            if not percentage_change_col:
                percentage_change_col = "percentage_change"
            
            # Generate schema with original column names
            data_item = {
                current_col: current_val,
                previous_col: previous_val
            }
            if percentage_change_col:
                data_item[percentage_change_col] = percentage_change_val
            
            schema = {
                "data": {
                    "values": [data_item]
                },
                "transform": [{
                    "calculate": f"format(datum.{current_col}, ',.0f') + ' vs ' + format(datum.{previous_col}, ',.0f') + ' (' + format(datum.{percentage_change_col} / 100, '+.1%') + ')'",
                    "as": "display_text"
                }],
                "mark": {"type": "text", "fontSize": 36, "fontWeight": "bold"},
                "encoding": {
                    "text": {"field": "display_text", "type": "nominal"},
                    "color": {
                        "condition": {"test": f"datum.{percentage_change_col} > 0", "value": "#16a34a"},
                        "value": "#ef4444"
                    }
                },
                "title": query[:50] if len(query) > 50 else query,
                "kpi_metadata": {
                    "chart_type": "comparison_kpi",
                    "chart_subtype": "current_vs_percentage"
                }
            }
            
            logger.info("Generated fallback comparison KPI schema")
            return schema
            
        except Exception as e:
            logger.error(f"Error generating fallback comparison KPI schema: {e}")
            return {}
    
    def _generate_fallback_counter_kpi_schema(
        self,
        columns: List[str],
        sample_data: Any,
        query: str,
        language: str
    ) -> Dict[str, Any]:
        """Generate a fallback counter KPI schema when LLM fails"""
        try:
            # Extract values from sample data - handle both dict and list formats
            data_values = []
            if isinstance(sample_data, list):
                # sample_data is a list directly
                data_values = sample_data
            elif isinstance(sample_data, dict):
                # sample_data is a dict - check for "data" or "values" keys
                data_values = sample_data.get("data", sample_data.get("values", []))
                # If still empty, check if sample_data itself contains the data
                if not data_values and sample_data:
                    # Check if sample_data has column names as keys
                    if any(col in sample_data for col in columns):
                        data_values = [sample_data]
            else:
                logger.warning(f"Unexpected sample_data type: {type(sample_data)}")
                return {}
            
            if not data_values or len(data_values) == 0:
                logger.warning("No data values found in sample_data for fallback counter KPI")
                return {}
            
            # Get first row - handle both dict and list formats
            first_row = {}
            if isinstance(data_values[0], dict):
                first_row = data_values[0]
            elif isinstance(data_values[0], list) and columns:
                first_row = dict(zip(columns, data_values[0]))
            else:
                logger.warning(f"Unexpected data_values[0] type: {type(data_values[0])}")
                return {}
            
            # Find first numeric value
            value = 0
            for col in columns:
                if col in first_row:
                    try:
                        value = float(str(first_row[col]).replace(',', ''))
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Generate schema
            schema = {
                "data": {
                    "values": [{"value": value}]
                },
                "mark": {"type": "text", "fontSize": 36, "fontWeight": "bold"},
                "encoding": {
                    "text": {"field": "value", "type": "quantitative", "format": ","},
                    "color": {"value": "#2563eb"}
                },
                "title": query[:50] if len(query) > 50 else query,
                "kpi_metadata": {
                    "chart_type": "metric_kpi",
                    "chart_subtype": "counter"
                }
            }
            
            logger.info("Generated fallback counter KPI schema")
            return schema
            
        except Exception as e:
            logger.error(f"Error generating fallback counter KPI schema: {e}")
            return {}
    
    async def run(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_schema: bool = True,
        export_format: Optional[str] = None,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the complete Vega-Lite chart generation pipeline
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_schema: Whether to remove data from schema
            export_format: Optional export format
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        logger.info("Vega-Lite Chart Generation pipeline is running...")
        
        try:
            # Update agent's vega schema
            self.agent.vega_schema = self.vega_schema
            
            # Generate chart
            result = await self.agent.generate_chart(
                query=query,
                sql=sql,
                data=data,
                language=language,
                remove_data_from_chart_schema=remove_data_from_chart_schema,
                existing_chart_schema=existing_chart_schema
            )
            print("result for vega lite chart generation pipeline", result)
            
            # Check if chart type is KPI and process accordingly
            chart_type = result.get("chart_type", "").lower()
            chart_schema = result.get("chart_schema", {})
            
            # Early detection: Check data structure for comparison KPI patterns
            # This helps catch comparison KPIs before the LLM might generate dummy schemas
            columns = data.get("columns", [])
            data_rows = data.get("data", [])
            
            # Check for comparison KPI patterns in column names
            has_comparison_patterns = False
            if columns:
                col_names_lower = [col.lower() if isinstance(col, str) else str(col).lower() for col in columns]
                has_current = any(any(kw in col for kw in ["this_year", "current", "this_month", "completed_this", "learners_this"]) for col in col_names_lower)
                has_previous = any(any(kw in col for kw in ["last_year", "previous", "last_month", "prior", "completed_last", "learners_last"]) for col in col_names_lower)
                has_percentage_change = any("percentage_change" in col or "percent_change" in col for col in col_names_lower)
                has_comparison_patterns = (has_current and has_previous) or has_percentage_change
            
            # Check for KPI chart indicators
            kpi_metadata = chart_schema.get("kpi_metadata", {})
            has_kpi_metadata = kpi_metadata is not None and kpi_metadata != {}
            is_dummy_kpi = kpi_metadata.get("is_dummy", False) if isinstance(kpi_metadata, dict) else False
            
            # Detect KPI charts - including dummy ones that need to be replaced
            # KPI charts are ONLY appropriate for:
            # - Data with 1 column (single metric)
            # - Data with 2 columns where one is a key/identifier (e.g., metric name + value)
            # - Very few rows (<=5) with limited columns
            # KPI charts are NOT appropriate for data with more than 2 columns
            num_rows = len(data_rows)
            num_columns = len(columns)
            
            # Check if data shape is suitable for KPI (max 5 rows, max 2 columns)
            is_kpi_suitable_shape = (
                num_columns <= 2 and num_rows <= 5
            )
            
            is_kpi_chart = (
                "kpi" in chart_type or
                "metric" in chart_type or
                "counter" in chart_type or
                "gauge" in chart_type or
                has_kpi_metadata or  # Process even if is_dummy is true
                has_comparison_patterns or  # Early detection for comparison KPIs
                (isinstance(chart_schema.get("mark"), dict) and 
                 chart_schema.get("mark", {}).get("type") == "text" and
                 is_kpi_suitable_shape) or
                (num_rows == 1 and num_columns <= 2)  # Single row with 1-2 columns likely a KPI
            )
            
            # IMPORTANT: Override KPI detection if data has more than 2 columns
            # Data with >2 columns should use a more appropriate chart type
            if num_columns > 2 and not ("kpi" in chart_type and has_kpi_metadata):
                # Only force non-KPI if the LLM didn't explicitly choose KPI with metadata
                if is_kpi_chart and not has_kpi_metadata and not has_comparison_patterns:
                    logger.info(f"Overriding KPI detection - data has {num_columns} columns (>2), selecting better chart type")
                    is_kpi_chart = False
            
            if is_kpi_chart and chart_schema:
                logger.info(f"Detected KPI chart, processing with KPI-specific logic... (chart_type={chart_type}, has_kpi_metadata={has_kpi_metadata}, is_dummy={is_dummy_kpi}, has_comparison_patterns={has_comparison_patterns})")
                
                # If this is a dummy KPI, we MUST replace it with a proper KPI schema
                if is_dummy_kpi:
                    logger.warning(f"Detected dummy KPI schema - replacing with proper KPI generation. Original schema had is_dummy={is_dummy_kpi}")
                    # Clear the dummy schema and let _process_kpi_chart generate a new one
                    # Keep only essential fields that might be useful
                    chart_schema = {
                        "title": chart_schema.get("title", ""),
                        "mark": {"type": "text"}  # Minimal schema to indicate KPI
                    }
                
                # Process KPI chart with specialized logic using LLM
                # This will always generate a proper, functional KPI schema
                processed_schema = await self._process_kpi_chart(
                    data=data,
                    chart_schema=chart_schema,
                    query=query,
                    language=language
                )
                
                # CRITICAL: Always ensure dummy flags are removed and schema is valid
                if "kpi_metadata" in processed_schema:
                    kpi_meta = processed_schema["kpi_metadata"]
                    # Remove all dummy-related flags
                    kpi_meta.pop("is_dummy", None)
                    kpi_meta.pop("requires_custom_template", None)
                    # Ensure it's marked as compatible
                    kpi_meta["vega_lite_compatible"] = True
                    # Remove any dummy kpi_data structure if present
                    if "kpi_data" in kpi_meta and isinstance(kpi_meta["kpi_data"], dict):
                        # Only keep kpi_data if it has actual useful data
                        kpi_data = kpi_meta["kpi_data"]
                        if not kpi_data.get("metrics") and not kpi_data.get("values"):
                            kpi_meta.pop("kpi_data", None)
                    processed_schema["kpi_metadata"] = kpi_meta
                
                # Final validation: ensure the schema is not a dummy
                if processed_schema.get("kpi_metadata", {}).get("is_dummy"):
                    logger.error("ERROR: Processed schema still has is_dummy=true - this should never happen!")
                    # Force remove it
                    processed_schema["kpi_metadata"].pop("is_dummy", None)
                    processed_schema["kpi_metadata"]["vega_lite_compatible"] = True
                
                result["chart_schema"] = processed_schema
                logger.info(f"KPI chart processed. Final kpi_metadata: {processed_schema.get('kpi_metadata', {})}")
            else:
                logger.info(f"Chart not detected as KPI. is_kpi_chart={is_kpi_chart}, chart_schema exists={bool(chart_schema)}")
            
            # Update chart type to reflect KPI subtype if available (for both KPI and non-KPI charts)
            if "chart_schema" in result:
                processed_schema = result.get("chart_schema", {})
                if "kpi_metadata" in processed_schema:
                    kpi_metadata = processed_schema.get("kpi_metadata", {})
                    chart_subtype = kpi_metadata.get("chart_subtype", "")
                    if chart_subtype:
                        result["chart_type"] = f"kpi_{chart_subtype}"
                    else:
                        result["chart_type"] = "kpi"
            
            # Add export functionality if requested
            if export_format and result.get("success", False):
                chart_schema = result.get("chart_schema", {})
                sample_data = data.get("data", [])
                print("export_format", export_format)
                print("chart_schema", chart_schema)
                export_format = "json"
                if export_format == "json":
                    result["exported_json"] = self.exporter.to_vega_lite_json(chart_schema)
                elif export_format == "observable":
                    result["observable_code"] = self.exporter.to_observable_notebook(chart_schema, sample_data)
                elif export_format == "altair":
                    result["altair_code"] = self.exporter.to_altair_python(chart_schema)
                elif export_format == "summary":
                    result["chart_summary"] = self.exporter.get_chart_summary(chart_schema)
                elif export_format == "all":
                    result["exported_json"] = self.exporter.to_vega_lite_json(chart_schema)
                    result["observable_code"] = self.exporter.to_observable_notebook(chart_schema, sample_data)
                    result["altair_code"] = self.exporter.to_altair_python(chart_schema)
                    result["chart_summary"] = self.exporter.get_chart_summary(chart_schema)
            print("result for vega lite chart generation pipeline", result)
            return result
            
        except Exception as e:
            logger.error(f"Error in pipeline execution: {e}")
            return {
                "chart_schema": {},
                "reasoning": f"Pipeline error: {str(e)}",
                "chart_type": "",
                "success": False,
                "error": str(e)
            }
    
    async def generate_chart_from_template(
        self,
        existing_chart: Dict[str, Any],
        new_data: Dict[str, Any],
        field_mapping: Optional[Dict[str, str]] = None,
        language: str = "English"
    ) -> Dict[str, Any]:
        """Generate a new chart using an existing chart as a template with new data
        
        This is a convenience method that creates an AdvancedVegaLiteChartGeneration
        instance and calls its generate_chart_from_template method.
        """
        advanced_pipeline = AdvancedVegaLiteChartGeneration(vega_schema=self.vega_schema)
        return await advanced_pipeline.generate_chart_from_template(
            existing_chart, new_data, field_mapping, language
        )


# Alternative pipeline class matching original structure
class ChartGeneration:
    """Chart generation pipeline compatible with original interface"""
    
    def __init__(self,  **kwargs):
        self.pipeline = VegaLiteChartGenerationPipeline(**kwargs)
    
    async def run(
        self,
        query: str,
        sql: str,
        data: dict,
        language: str,
        remove_data_from_chart_schema: Optional[bool] = True,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> dict:
        """Run chart generation with original interface"""
        result = await self.pipeline.run(
            query=query,
            sql=sql,
            data=data,
            language=language,
            remove_data_from_chart_schema=remove_data_from_chart_schema,
            existing_chart_schema=existing_chart_schema
        )
        
        # Transform result to match original output format
        return {
            "results": {
                "chart_schema": result.get("chart_schema", {}),
                "reasoning": result.get("reasoning", ""),
                "chart_type": result.get("chart_type", ""),
            }
        }


# Factory functions
def create_vega_lite_chart_generation_pipeline( **kwargs) -> VegaLiteChartGenerationPipeline:
    """Factory function to create Vega-Lite chart generation pipeline"""
    return VegaLiteChartGenerationPipeline( **kwargs)


def create_chart_generation_pipeline( **kwargs) -> ChartGeneration:
    """Factory function to create chart generation pipeline with original interface"""
    return ChartGeneration(**kwargs)


# Utility functions for integration
async def generate_vega_lite_chart(
    query: str,
    sql: str,
    data: Dict[str, Any],
    language: str = "English",
    export_format: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to generate Vega-Lite chart"""
    pipeline = create_vega_lite_chart_generation_pipeline()
    return await pipeline.run(
        query=query,
        sql=sql,
        data=data,
        language=language,
        export_format=export_format
    )


# Enhanced chart generation with additional features
class AdvancedVegaLiteChartGeneration(VegaLiteChartGenerationPipeline):
    """Advanced Vega-Lite chart generation with additional features"""
    
    def __init__(self, **kwargs):
        super().__init__( **kwargs)
        self.chart_templates = self._load_chart_templates()
    
    def _load_chart_templates(self) -> Dict[str, Any]:
        """Load predefined chart templates"""
        return {
            "sales_trend": {
                "type": "line",
                "description": "Shows sales trends over time",
                "required_fields": ["date", "sales"]
            },
            "category_comparison": {
                "type": "bar",
                "description": "Compares values across categories", 
                "required_fields": ["category", "value"]
            },
            "distribution": {
                "type": "pie",
                "description": "Shows distribution of parts within a whole",
                "required_fields": ["category", "value"]
            }
        }
    
    async def suggest_chart_type(self, data: Dict[str, Any], query: str) -> List[str]:
        """Suggest appropriate chart types based on data and query"""
        suggestions = []
        
        # Analyze data structure
        columns = data.get("columns", [])
        data_sample = data.get("data", [])[:5]  # Sample first 5 rows
        
        # Simple heuristics for chart type suggestion
        temporal_fields = []
        categorical_fields = []
        numeric_fields = []
        
        for col in columns:
            col_name = col if isinstance(col, str) else col.get("name", "")
            
            # Check sample data for type inference
            if data_sample:
                sample_values = [row[columns.index(col)] for row in data_sample if len(row) > columns.index(col)]
                
                if any(isinstance(val, (int, float)) for val in sample_values):
                    numeric_fields.append(col_name)
                elif any(str(val).lower() in ['date', 'time', 'month', 'year'] for val in sample_values):
                    temporal_fields.append(col_name)
                else:
                    categorical_fields.append(col_name)
        
        # Suggest based on field types
        if temporal_fields and numeric_fields:
            suggestions.extend(["line", "area"])
        
        if categorical_fields and numeric_fields:
            suggestions.extend(["bar", "pie"])
        
        if len(categorical_fields) >= 2 and numeric_fields:
            suggestions.extend(["grouped_bar", "stacked_bar"])
        
        # Query-based suggestions
        query_lower = query.lower()
        if "trend" in query_lower or "over time" in query_lower:
            suggestions.append("line")
        elif "compare" in query_lower or "comparison" in query_lower:
            suggestions.append("bar")
        elif "distribution" in query_lower or "share" in query_lower:
            suggestions.append("pie")
        
        return list(set(suggestions))  # Remove duplicates
    
    async def run_with_suggestions(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        **kwargs
    ) -> Dict[str, Any]:
        """Run chart generation with chart type suggestions"""
        
        # Get suggestions first
        suggestions = await self.suggest_chart_type(data, query)
        
        # Run normal pipeline
        result = await self.run(query, sql, data, language, **kwargs)
        
        # Add suggestions to result
        result["chart_suggestions"] = suggestions
        result["available_templates"] = list(self.chart_templates.keys())
        
        return result

    async def generate_chart_from_template(
        self,
        existing_chart: Dict[str, Any],
        new_data: Dict[str, Any],
        field_mapping: Optional[Dict[str, str]] = None,
        language: str = "English"
    ) -> Dict[str, Any]:
        """Generate a new chart using an existing chart as a template with new data
        
        Args:
            existing_chart: The existing chart configuration to use as template
            new_data: New data to visualize using the template
            field_mapping: Optional mapping from old field names to new field names
            language: Language for the chart titles and labels
            
        Returns:
            Dict containing the new chart configuration
        """
        try:
            logger.info("Generating chart from template...")
            
            # Extract chart schema from existing chart
            if "chart_schema" in existing_chart:
                template_schema = existing_chart["chart_schema"]
            elif "results" in existing_chart and "chart_schema" in existing_chart["results"]:
                template_schema = existing_chart["results"]["chart_schema"]
            else:
                template_schema = existing_chart
            
            if not template_schema:
                return {
                    "success": False,
                    "error": "No valid chart schema found in existing chart",
                    "chart_schema": {},
                    "reasoning": "Template chart is invalid"
                }
            
            # Preprocess new data
            preprocessed_data = self.data_preprocessor.run(new_data)
            new_columns = preprocessed_data["sample_data"].get("columns", [])
            
            # Create field mapping if not provided
            if not field_mapping:
                field_mapping = self._create_automatic_field_mapping(template_schema, new_columns)
            
            # Generate new chart schema based on template
            new_chart_schema = self._adapt_chart_schema(
                template_schema, 
                new_columns, 
                field_mapping, 
                language
            )
            
            # Validate the new chart schema
            validation_result = self._validate_chart_schema(new_chart_schema, new_columns)
            
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Chart validation failed: {validation_result['error']}",
                    "chart_schema": new_chart_schema,
                    "reasoning": f"Generated chart from template but validation failed: {validation_result['error']}"
                }
            
            # Determine chart type from schema
            chart_type = self._extract_chart_type_from_schema(new_chart_schema)
            
            return {
                "success": True,
                "chart_schema": new_chart_schema,
                "chart_type": chart_type,
                "reasoning": f"Successfully generated chart from template using field mapping: {field_mapping}",
                "field_mapping": field_mapping,
                "template_info": {
                    "original_chart_type": existing_chart.get("chart_type", "unknown"),
                    "fields_mapped": len(field_mapping),
                    "validation_passed": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating chart from template: {e}")
            return {
                "success": False,
                "error": str(e),
                "chart_schema": {},
                "reasoning": f"Error generating chart from template: {str(e)}"
            }
    
    def _create_automatic_field_mapping(
        self, 
        template_schema: Dict[str, Any], 
        new_columns: List[str]
    ) -> Dict[str, str]:
        """Create automatic field mapping based on column names and schema fields"""
        field_mapping = {}
        
        # Extract fields used in the template schema
        template_fields = self._extract_fields_from_schema(template_schema)
        
        # Create mapping based on name similarity
        for template_field in template_fields:
            best_match = self._find_best_column_match(template_field, new_columns)
            if best_match:
                field_mapping[template_field] = best_match
        
        return field_mapping
    
    def _extract_fields_from_schema(self, schema: Dict[str, Any]) -> List[str]:
        """Extract all field names used in a Vega-Lite schema"""
        fields = []
        
        def extract_from_encoding(encoding):
            if isinstance(encoding, dict):
                for key, value in encoding.items():
                    if isinstance(value, dict) and "field" in value:
                        fields.append(value["field"])
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and "field" in item:
                                fields.append(item["field"])
        
        # Extract from main encoding
        if "encoding" in schema:
            extract_from_encoding(schema["encoding"])
        
        # Extract from transform operations
        if "transform" in schema:
            for transform in schema["transform"]:
                if "fold" in transform:
                    fields.extend(transform["fold"])
                elif "as" in transform:
                    # These are new field names, not original ones
                    pass
        
        return list(set(fields))
    
    def _find_best_column_match(self, template_field: str, new_columns: List[str]) -> Optional[str]:
        """Find the best matching column name for a template field"""
        template_field_lower = template_field.lower()
        
        # Exact match
        for col in new_columns:
            if col.lower() == template_field_lower:
                return col
        
        # Partial match (contains)
        for col in new_columns:
            if template_field_lower in col.lower() or col.lower() in template_field_lower:
                return col
        
        # Fuzzy match based on common patterns
        common_patterns = {
            'date': ['date', 'time', 'timestamp', 'created', 'updated'],
            'sales': ['sales', 'revenue', 'amount', 'value'],
            'region': ['region', 'area', 'location', 'country', 'state'],
            'product': ['product', 'item', 'category', 'type'],
            'count': ['count', 'number', 'quantity', 'total'],
            'profit': ['profit', 'margin', 'income', 'earnings']
        }
        
        for pattern, keywords in common_patterns.items():
            if pattern in template_field_lower:
                for col in new_columns:
                    for keyword in keywords:
                        if keyword in col.lower():
                            return col
        
        return None
    
    def _adapt_chart_schema(
        self, 
        template_schema: Dict[str, Any], 
        new_columns: List[str], 
        field_mapping: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Adapt a template chart schema to work with new data"""
        import copy
        
        # Deep copy the template schema
        new_schema = copy.deepcopy(template_schema)
        
        # Update field references in encoding
        if "encoding" in new_schema:
            self._update_encoding_fields(new_schema["encoding"], field_mapping)
        
        # Update field references in transform operations
        if "transform" in new_schema:
            self._update_transform_fields(new_schema["transform"], field_mapping, new_columns)
        
        # Update titles to be language-appropriate
        self._update_titles_for_language(new_schema, language)
        
        return new_schema
    
    def _update_encoding_fields(self, encoding: Dict[str, Any], field_mapping: Dict[str, str]):
        """Update field references in encoding section"""
        for key, value in encoding.items():
            if isinstance(value, dict):
                if "field" in value and value["field"] in field_mapping:
                    value["field"] = field_mapping[value["field"]]
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "field" in item and item["field"] in field_mapping:
                        item["field"] = field_mapping[item["field"]]
    
    def _update_transform_fields(
        self, 
        transforms: List[Dict[str, Any]], 
        field_mapping: Dict[str, str], 
        new_columns: List[str]
    ):
        """Update field references in transform operations"""
        for transform in transforms:
            if "fold" in transform:
                # Update fold fields
                new_fold_fields = []
                for field in transform["fold"]:
                    if field in field_mapping:
                        new_fold_fields.append(field_mapping[field])
                    elif field in new_columns:
                        new_fold_fields.append(field)
                transform["fold"] = new_fold_fields
    
    def _update_titles_for_language(self, schema: Dict[str, Any], language: str):
        """Update chart titles and labels for the specified language"""
        # This is a simplified version - in practice, you might want to use
        # translation services or predefined title templates
        if "title" in schema and isinstance(schema["title"], str):
            if "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>" in schema["title"]:
                schema["title"] = f"Chart ({language})"
        
        # Update axis titles
        if "encoding" in schema:
            for key, value in schema["encoding"].items():
                if isinstance(value, dict) and "title" in value:
                    if "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>" in str(value["title"]):
                        value["title"] = f"{key.title()} ({language})"
    
    def _validate_chart_schema(self, schema: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
        """Validate that a chart schema is compatible with the provided columns"""
        try:
            # Extract all field references from the schema
            schema_fields = self._extract_fields_from_schema(schema)
            
            # Check if all referenced fields exist in the data columns
            missing_fields = []
            for field in schema_fields:
                if field not in columns:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Schema references fields not present in data: {missing_fields}"
                }
            
            # Basic schema structure validation
            if "mark" not in schema:
                return {
                    "valid": False,
                    "error": "Schema missing required 'mark' property"
                }
            
            if "encoding" not in schema:
                return {
                    "valid": False,
                    "error": "Schema missing required 'encoding' property"
                }
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Schema validation error: {str(e)}"
            }
    
    def _extract_chart_type_from_schema(self, schema: Dict[str, Any]) -> str:
        """Extract chart type from Vega-Lite schema"""
        if "mark" not in schema:
            return ""
        
        mark_type = schema["mark"].get("type", "")
        
        # Map Vega-Lite mark types to our chart types
        mark_to_chart_type = {
            "bar": "bar",
            "line": "line", 
            "area": "area",
            "arc": "pie",
            "point": "scatter",
            "circle": "scatter",
            "rect": "heatmap",
            "boxplot": "box",
            "text": "text",
            "tick": "tick",
            "rule": "rule"
        }
        
        base_type = mark_to_chart_type.get(mark_type, "")
        
        # Check for special cases
        if base_type == "bar" and "encoding" in schema:
            encoding = schema["encoding"]
            if "stack" in encoding.get("y", {}) and encoding["y"]["stack"] == "zero":
                return "stacked_bar"
            elif "xOffset" in encoding:
                return "grouped_bar"
        
        if base_type == "line" and "transform" in schema:
            # Check for multi-line chart
            for transform in schema["transform"]:
                if "fold" in transform:
                    return "multi_line"
        
        return base_type


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    import os
    from app.settings import get_settings
    
    settings = get_settings()
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    
    # Example usage
    async def test_vega_lite_chart_generation():
        # Sample data
        sample_data = {
            "columns": ["Date", "Sales", "Region"],
            "data": [
                ["2023-01-01", 100000, "North"],
                ["2023-02-01", 120000, "North"],
                ["2023-03-01", 110000, "North"],
                ["2023-01-01", 90000, "South"],
                ["2023-02-01", 95000, "South"],
                ["2023-03-01", 105000, "South"]
            ]
        }
        
        # Test chart generation (schema only)
        result = await generate_vega_lite_chart(
            query="Show me sales trends by region over time",
            sql="SELECT Date, Sales, Region FROM sales_data ORDER BY Date",
            data=sample_data,
            language="English",
            export_format="all"
        )
        
        print("Chart Generation Result (Schema Only):")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
        
        # Test with original interface
        chart_gen = create_chart_generation_pipeline()
        original_result = await chart_gen.run(
            query="Show sales by region",
            sql="SELECT Region, SUM(Sales) FROM sales GROUP BY Region",
            data=sample_data,
            language="English"
        )
        
        print("\nOriginal Interface Result:")
        print(orjson.dumps(original_result, option=orjson.OPT_INDENT_2).decode())
        
        # Test advanced features
        advanced_gen = AdvancedVegaLiteChartGeneration()
        advanced_result = await advanced_gen.run_with_suggestions(
            query="Compare sales across regions",
            sql="SELECT Region, Sales FROM sales",
            data=sample_data,
            language="English"
        )
        
        print("\nAdvanced Generation Result:")
        print(orjson.dumps(advanced_result, option=orjson.OPT_INDENT_2).decode())
        
        # Test separate chart execution (if database engine is available)
        try:
            from app.agents.nodes.sql.utils.chart import ChartExecutor, ChartExecutionConfig, execute_chart_with_sql
            
            # Mock database engine for demonstration
            class MockDBEngine:
                async def execute(self, sql):
                    # Return mock data based on SQL
                    if "sales_data" in sql.lower():
                        return [
                            {"Date": "2023-01-01", "Sales": 100000, "Region": "North"},
                            {"Date": "2023-02-01", "Sales": 120000, "Region": "North"},
                            {"Date": "2023-03-01", "Sales": 110000, "Region": "North"},
                            {"Date": "2023-04-01", "Sales": 130000, "Region": "North"},
                            {"Date": "2023-05-01", "Sales": 140000, "Region": "North"},
                            {"Date": "2023-01-01", "Sales": 90000, "Region": "South"},
                            {"Date": "2023-02-01", "Sales": 95000, "Region": "South"},
                            {"Date": "2023-03-01", "Sales": 105000, "Region": "South"},
                            {"Date": "2023-04-01", "Sales": 115000, "Region": "South"},
                            {"Date": "2023-05-01", "Sales": 125000, "Region": "South"}
                        ]
                    return []
            
            mock_engine = MockDBEngine()
            
            # Get chart schema from generation
            chart_schema = result.get("chart_schema", {})
            
            # Execute chart with SQL data
            config = ChartExecutionConfig(
                page_size=1000,
                max_rows=10000,
                enable_pagination=True,
                sort_by="Date",
                sort_order="ASC"
            )
            
            executed_result = await execute_chart_with_sql(
                chart_schema=chart_schema,
                sql_query="SELECT Date, Sales, Region FROM sales_data ORDER BY Date",
                db_engine=mock_engine,
                config=config
            )
            
            print("\nChart Execution Result (with SQL data):")
            print(f"Success: {executed_result.get('success', False)}")
            print(f"Data count: {executed_result.get('data_count', 0)}")
            print(f"Validation: {executed_result.get('validation', {})}")
            print(f"Execution config: {executed_result.get('execution_config', {})}")
            
        except ImportError:
            print("\nChart execution test skipped (database dependencies not available)")
    
    # Run the test
    asyncio.run(test_vega_lite_chart_generation())