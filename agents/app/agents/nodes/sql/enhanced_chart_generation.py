import asyncio
import logging
import os
import json
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

# Use centralized agent creation utility (imports AgentExecutor from there)
from app.agents.utils.agent_utils import create_agent_with_executor, AgentExecutor
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
from app.agents.nodes.sql.utils.enhanced_chart_generation import (
    EnhancedChartDataPreprocessor,
    EnhancedChartGenerationPostProcessor,
    enhanced_chart_generation_instructions,
    create_enhanced_chart_data_preprocessor_tool,
    create_enhanced_chart_postprocessor_tool
)
from app.agents.nodes.sql.chart_generation import VegaLiteChartGenerationPipeline
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider
from app.agents.nodes.sql.utils.chart_models import EnhancedChartGenerationResults

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()


class EnhancedVegaLiteChartGenerationAgent:
    """Enhanced Vega-Lite chart generation agent with support for additional chart types"""
    
    def __init__(self, vega_schema: Optional[Dict[str, Any]] = None, **kwargs):
        self.llm = get_llm()
        self.vega_schema = vega_schema or {}
        self.data_preprocessor = EnhancedChartDataPreprocessor()
        self.post_processor = EnhancedChartGenerationPostProcessor()
        
        # Create enhanced tools
        self.tools = [
            create_enhanced_chart_data_preprocessor_tool(),
            create_enhanced_chart_postprocessor_tool(),
        ]
        
        # Initialize agent
        self.agent = self._create_agent()
        
        # Enhanced system prompt for Vega-Lite chart generation
        self.system_prompt = f"""
        ### TASK ###
        
        You are an expert data analyst specializing in advanced data visualization using Vega-Lite! Given the user's question, SQL, sample data and sample column values, you need to generate vega-lite schema in JSON and provide suitable chart type.
        
        Besides, you need to give a concise and easy-to-understand reasoning to describe why you provide such vega-lite schema based on the question, SQL, sample data and sample column values.
        
        {enhanced_chart_generation_instructions}
        
        ### CRITICAL INSTRUCTION ###
        
        You MUST respond with ONLY a valid JSON object. Do NOT include:
        - Any text before the JSON
        - Any text after the JSON  
        - Markdown formatting
        - Code blocks
        - Explanations outside the JSON
        
        Your entire response should be a single JSON object starting with {{ and ending with }}.
        
        ### CHART TYPE SELECTION RULES ###
        
        IMPORTANT: Use "kpi" chart type ONLY when ALL of the following conditions are met:
        1. Data has AT MOST 5 rows
        2. Data has AT MOST 2 columns (1 column for single metric, or 2 columns where one is a key/identifier)
        
        KPI chart is appropriate for:
        - Single count values (e.g., total sales, number of users) - 1 row, 1 column
        - Single metrics (e.g., conversion rate, average score) - 1 row, 1-2 columns
        - Small sets of KPIs with metric name + value pairs - up to 5 rows, 2 columns
        - Data with zero or identical values when it's still a single metric
        
        KPI chart is NOT appropriate when:
        - Data has MORE than 2 columns - use bar, grouped_bar, line, or other appropriate chart
        - Data has more than 5 rows with multiple columns - use bar, line, scatter, or other appropriate chart
        - Data represents trends over time - use line or area chart
        - Data represents comparisons across many categories - use bar or grouped_bar chart
        
        When data has 3+ columns, choose a chart type that can display multi-dimensional data:
        - grouped_bar: For comparing values across categories and sub-categories
        - stacked_bar: For showing composition of categories
        - scatter: For showing relationships between two quantitative variables
        - heatmap: For showing patterns across two categorical dimensions
        
        Do NOT return empty chart_type for single values - use "kpi" instead.
        
        CRITICAL: Zero values and identical values are still valid data that should be visualized. Do not reject them as "not suitable for visualization".
        
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
        
        ### OUTPUT FORMAT ###
        
        {{
            "reasoning": "<REASON_TO_CHOOSE_THE_SCHEMA_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>",
            "chart_type": "line" | "multi_line" | "bar" | "pie" | "grouped_bar" | "stacked_bar" | "area" | "scatter" | "heatmap" | "boxplot" | "histogram" | "bubble" | "text" | "tick" | "rule" | "kpi" | "",
            "chart_schema": <VEGA_LITE_JSON_SCHEMA>,
            "enhanced_metadata": {{
                "data_analysis": "<BRIEF_ANALYSIS_OF_DATA_STRUCTURE>",
                "alternative_charts": ["<LIST_OF_ALTERNATIVE_CHART_TYPES>"],
                "chart_selection_reasoning": "<DETAILED_REASONING_FOR_CHART_SELECTION>"
            }}
        }}
        
        ### EXAMPLES ###
        
        For a single count value (KPI):
        {{
            "reasoning": "A KPI chart is chosen to display the single count value of late completions as a key performance indicator",
            "chart_type": "kpi",
            "chart_schema": {{
                "title": "Late Completions Count",
                "mark": {{"type": "text"}},
                "encoding": {{
                    "text": {{"field": "count", "type": "quantitative"}}
                }}
            }},
            "enhanced_metadata": {{
                "data_analysis": "Single quantitative metric representing a count",
                "alternative_charts": ["text", "tick"],
                "chart_selection_reasoning": "KPI chart best displays single count values as key performance indicators"
            }}
        }}
        
        For a scatter chart:
        {{
            "reasoning": "A scatter chart is chosen to show the relationship between sales and profit across different regions",
            "chart_type": "scatter",
            "chart_schema": {{
                "title": "Sales vs Profit by Region",
                "mark": {{"type": "circle"}},
                "encoding": {{
                    "x": {{"field": "Sales", "type": "quantitative", "title": "Sales"}},
                    "y": {{"field": "Profit", "type": "quantitative", "title": "Profit"}},
                    "color": {{"field": "Region", "type": "nominal", "title": "Region"}}
                }}
            }},
            "enhanced_metadata": {{
                "data_analysis": "Two quantitative variables (Sales, Profit) and one categorical variable (Region)",
                "alternative_charts": ["bubble", "line", "bar"],
                "chart_selection_reasoning": "Scatter chart best shows correlation between continuous variables"
            }}
        }}
        
        For a heatmap:
        {{
            "reasoning": "A heatmap is chosen to show sales intensity across months and regions",
            "chart_type": "heatmap",
            "chart_schema": {{
                "title": "Sales Heatmap by Month and Region",
                "mark": {{"type": "rect"}},
                "encoding": {{
                    "x": {{"field": "Month", "type": "nominal", "title": "Month"}},
                    "y": {{"field": "Region", "type": "nominal", "title": "Region"}},
                    "color": {{"field": "Sales", "type": "quantitative", "title": "Sales"}}
                }}
            }},
            "enhanced_metadata": {{
                "data_analysis": "Two categorical variables (Month, Region) and one quantitative variable (Sales)",
                "alternative_charts": ["bar", "line", "scatter"],
                "chart_selection_reasoning": "Heatmap best shows two-dimensional data with color intensity"
            }}
        }}
        
        For multiple KPIs:
        {{
            "reasoning": "A KPI chart is chosen to display key performance indicators and summary metrics",
            "chart_type": "kpi",
            "chart_schema": {{
                "title": "Key Performance Indicators",
                "mark": {{"type": "text"}},
                "encoding": {{
                    "text": {{"field": "Value", "type": "quantitative"}},
                    "color": {{"field": "Metric", "type": "nominal"}}
                }}
            }},
            "enhanced_metadata": {{
                "data_analysis": "Multiple quantitative metrics representing KPIs",
                "alternative_charts": ["text", "bar", "tick"],
                "chart_selection_reasoning": "KPI chart best displays key performance indicators and summary metrics"
            }}
        }}
        
        For data with all zero or identical values:
        {{
            "reasoning": "A KPI chart is chosen to display the compliance rates, even though all values are zero, as this represents important business information",
            "chart_type": "kpi",
            "chart_schema": {{
                "title": "Compliance Rates by Manager",
                "mark": {{"type": "text"}},
                "encoding": {{
                    "text": {{"field": "Compliance_Rate", "type": "quantitative"}},
                    "color": {{"field": "Division", "type": "nominal"}}
                }}
            }},
            "enhanced_metadata": {{
                "data_analysis": "All compliance rates are zero, indicating no compliance across all managers",
                "alternative_charts": ["bar", "text", "tick"],
                "chart_selection_reasoning": "KPI chart best displays compliance metrics even when all values are zero"
            }}
        }}
        
        For no suitable chart (only for truly non-visualizable data):
        {{
            "reasoning": "The data is not suitable for visualization",
            "chart_type": "",
            "chart_schema": {{}},
            "enhanced_metadata": {{
                "data_analysis": "Insufficient or inappropriate data for visualization",
                "alternative_charts": [],
                "chart_selection_reasoning": "No suitable chart type for this data structure"
            }}
        }}
        """
        
        # User prompt template
        self.user_prompt_template = PromptTemplate(
            input_variables=["query", "sql", "sample_data", "sample_column_values", "language", "data_analysis", "existing_chart_schema"],
            template="""
            ### INPUT ###
            Question: {query}
            SQL: {sql}
            Sample Data: {sample_data}
            Sample Column Values: {sample_column_values}
            Language: {language}
            Data Analysis: {data_analysis}
            Existing Chart Schema: {existing_chart_schema}
            
            ### ANALYSIS INSTRUCTIONS ###
            
            Please analyze the data structure and select the most appropriate chart type:
            
            1. **Check if this is a single value or small dataset (1-3 columns with quantitative data)**
               - If YES: Use "kpi" chart type for single metrics, counts, or small KPI sets
               - Single values like counts, totals, averages should ALWAYS use KPI charts
               - Zero values (0, 0.0) are still valid data and should be visualized
            
            2. **For larger datasets, analyze the data types and relationships**
               - Quantitative + Quantitative: Consider scatter, bubble, line
               - Categorical + Quantitative: Consider bar, pie, grouped bar
               - Temporal + Quantitative: Consider line, area, multi-line
               - Multiple categorical + Quantitative: Consider heatmap
            
            3. **Consider the user's question context**
               - What are they trying to understand?
               - What type of insight are they looking for?
            
            **CRITICAL RULES:**
            - Zero values are valid data and should be visualized
            - Data with all zero values should use KPI charts
            - Do NOT return empty chart_type for zero values
            - Do NOT say the data is "empty" if it contains zero values
            - Zero compliance rates, zero counts, etc. are important business information
            """
        )
    
    def _create_agent(self) -> Optional[AgentExecutor]:
        """Create and configure the Langchain agent using modern patterns"""
        try:
            # Create tools with proper function definitions
            tools = [
                Tool(
                    name="enhanced_preprocess_data",
                    func=lambda x: self.data_preprocessor.run(orjson.loads(x)),
                    description="Enhanced preprocessing of chart data with support for additional chart types"
                ),
                Tool(
                    name="enhanced_postprocess_chart",
                    func=lambda x: self.post_processor.run(
                        x,
                        self.vega_schema,
                        [],  # Empty sample data as it will be provided in the actual call
                        True  # Default to removing data from chart schema
                    ),
                    description="Enhanced post-processing of chart schemas with support for additional chart types"
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
            logger.error(f"Error creating enhanced agent: {e}")
            logger.debug(f"Agent creation error details: {str(e)}", exc_info=True)
            return None
    
    @observe(as_type="generation", capture_input=False)
    async def generate_chart(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_schema: bool = True,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate enhanced Vega-Lite chart schema using the agent
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_schema: Whether to remove data from config
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        try:
            # Preprocess data with enhanced analysis
            preprocessed_data = self.data_preprocessor.run(data)
            
            # Add debugging for single value detection
            logger.info(f"Data preprocessing result: {preprocessed_data}")
            logger.info(f"Sample data: {preprocessed_data['sample_data']}")
            logger.info(f"Data analysis: {preprocessed_data.get('data_analysis', {})}")
            logger.info(f"Suggested charts: {preprocessed_data.get('data_analysis', {}).get('suggested_charts', [])}")
            
            # Create the prompt with enhanced data analysis
            prompt = self.user_prompt_template.format(
                query=query,
                sql=sql,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                language=language,
                data_analysis=preprocessed_data.get("data_analysis", {}),
                existing_chart_schema=json.dumps(existing_chart_schema) if existing_chart_schema else "None"
            )
            
            # Add debugging for the prompt
            logger.info(f"Generated prompt: {prompt}")
            
            # Generate chart using LLM directly (more controlled approach)
            chart_result = await self._generate_chart_direct(prompt)
            
            # Post-process the result
            final_result = self.post_processor.run(
                chart_result,
                self.vega_schema,
                preprocessed_data["sample_data"],
                remove_data_from_chart_schema
            )
            
            # FALLBACK: If we have a single value but no chart was generated, force KPI chart
            suggested_charts = preprocessed_data.get("data_analysis", {}).get("suggested_charts", [])
            data_types = preprocessed_data.get("data_analysis", {}).get("data_types", {})
            
            # Check for single value case or all zero values case
            is_single_value = (len(preprocessed_data["sample_data"]) == 1 and 
                              len(data_types) == 1 and
                              "kpi" in suggested_charts)
            
            # Check for all zero values case
            all_zero_values = False
            if preprocessed_data["sample_data"]:
                first_row = preprocessed_data["sample_data"][0]
                numeric_values = []
                for key, value in first_row.items():
                    try:
                        if isinstance(value, str):
                            clean_value = value.replace(',', '').replace('$', '').replace('%', '')
                            numeric_values.append(float(clean_value))
                        else:
                            numeric_values.append(float(value))
                    except (ValueError, TypeError):
                        continue
                
                # Check if all numeric values are zero
                if numeric_values and all(val == 0.0 for val in numeric_values):
                    all_zero_values = True
            
            # Check if LLM returned empty chart type (which happens with zero values)
            llm_returned_empty = (not final_result.get("chart_type") or 
                                 final_result.get("chart_type") == "" or
                                 final_result.get("reasoning", "").lower().find("empty") != -1 or
                                 final_result.get("reasoning", "").lower().find("no records") != -1 or
                                 final_result.get("reasoning", "").lower().find("no data") != -1)
            
            # Also check if we have data but LLM thinks it's empty
            has_data_but_llm_empty = (len(preprocessed_data["sample_data"]) > 0 and 
                                     preprocessed_data.get("data_analysis", {}).get("row_count", 0) > 0 and
                                     llm_returned_empty)
            
            # Force fallback if we have any data but LLM says it's empty
            if has_data_but_llm_empty:
                logger.info("FALLBACK: LLM thinks data is empty but we have data - forcing KPI chart")
                all_zero_values = True  # Treat as zero values case
            
            # NOTE: We no longer create dummy KPIs here. Instead, we let the pipeline
            # detect KPIs and route them to the proper KPI processing logic.
            # If LLM returned empty but we have data, we'll let the pipeline handle it
            # as a KPI chart through the proper processing flow.
            if ((is_single_value or all_zero_values or has_data_but_llm_empty) and llm_returned_empty):
                logger.info("FALLBACK: LLM returned empty but we have data - will be handled by KPI processing in pipeline")
                # Don't create dummy KPI here - let the pipeline detect and process it properly
                # Just ensure chart_type is set to "kpi" so it gets detected
                if not final_result.get("chart_type"):
                    final_result["chart_type"] = "kpi"
                if not final_result.get("chart_schema"):
                    final_result["chart_schema"] = {
                        "title": "Key Performance Indicator",
                        "mark": {"type": "text"}
                    }
                if all_zero_values:
                    final_result["reasoning"] = "A KPI chart is generated to display the compliance rates, even though all values are zero, as this represents important business information that indicates no compliance across all managers and divisions."
                else:
                    final_result["reasoning"] = "A KPI chart is generated to display the single count value as a key performance indicator"
            
            # Add enhanced metadata if not present
            if "enhanced_metadata" not in final_result:
                final_result["enhanced_metadata"] = {
                    "data_analysis": preprocessed_data.get("data_analysis", {}),
                    "alternative_charts": preprocessed_data.get("data_analysis", {}).get("suggested_charts", []),
                    "chart_selection_reasoning": final_result.get("reasoning", "")
                }
            
            # FINAL FALLBACK: If we still don't have a valid chart, return a default empty chart
            if (not final_result.get("chart_type") or 
                final_result.get("chart_type") == "" or
                not final_result.get("chart_schema") or
                final_result.get("success") == False):
                
                logger.info("FINAL FALLBACK: Returning default empty chart for UI handling")
                
                final_result = {
                    "chart_schema": {
                        "title": "No Data Available",
                        "mark": {"type": "text"},
                        "encoding": {
                            "text": {"value": "No data available for visualization"}
                        }
                    },
                    "reasoning": "No suitable chart could be generated for the provided data",
                    "chart_type": "text",
                    "success": True,  # Return success so UI can handle gracefully
                    "error": None,
                    "enhanced_metadata": {
                        "data_analysis": preprocessed_data.get("data_analysis", {}),
                        "alternative_charts": [],
                        "chart_selection_reasoning": "Default fallback chart for empty or invalid data"
                    }
                }
            
            logger.info(f"Enhanced chart generation result: {final_result}")
            return final_result
            
        except Exception as e:
            logger.error(f"Error in enhanced chart generation: {e}")
            # Return a default chart instead of error for UI handling
            return {
                "chart_schema": {
                    "title": "Chart Generation Error",
                    "mark": {"type": "text"},
                    "encoding": {
                        "text": {"value": "Unable to generate chart due to an error"}
                    }
                },
                "reasoning": f"Chart generation failed: {str(e)}",
                "chart_type": "text",
                "enhanced_metadata": {
                    "data_analysis": {},
                    "alternative_charts": [],
                    "chart_selection_reasoning": f"Error occurred during chart generation: {str(e)}"
                },
                "success": True,  # Return success so UI can handle gracefully
                "error": str(e)
            }
    
    def _extract_kpi_data_from_single_value(self, single_row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract KPI data from a single row of data"""
        try:
            metrics = []
            values = []
            units = []
            
            for key, value in single_row.items():
                # Try to convert to numeric
                try:
                    if isinstance(value, str):
                        # Remove any non-numeric characters except decimal point and minus
                        clean_value = value.replace(',', '').replace('$', '').replace('%', '')
                        numeric_value = float(clean_value)
                    else:
                        numeric_value = float(value)
                    
                    # Include zero values - they are valid data
                    metrics.append(key)
                    values.append(numeric_value)
                    
                    # Determine unit based on key name or value
                    if isinstance(value, str):
                        if '%' in value:
                            units.append('%')
                        elif '$' in value:
                            units.append('USD')
                        else:
                            units.append('')
                    else:
                        units.append('')
                        
                except (ValueError, TypeError):
                    # Skip non-numeric values
                    continue
            
            # Ensure we have at least one metric (even if it's zero)
            if not metrics and single_row:
                # If no numeric values found, use the first key as metric with value 0
                first_key = list(single_row.keys())[0]
                metrics.append(first_key)
                values.append(0.0)
                units.append('')
            
            return {
                "metrics": metrics,
                "values": values,
                "targets": [],
                "units": units
            }
            
        except Exception as e:
            logger.error(f"Error extracting KPI data from single value: {e}")
            return {"metrics": [], "values": [], "targets": [], "units": []}
    
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
            
            # Try to extract JSON from the response
            try:
                # Look for JSON in the response
                start_idx = result_str.find('{')
                end_idx = result_str.rfind('}') + 1
                
                if start_idx != -1 and end_idx != 0:
                    json_str = result_str[start_idx:end_idx]
                    # Validate JSON
                    orjson.loads(json_str)
                    return json_str
                else:
                    raise ValueError("No valid JSON found in response")
                    
            except Exception as json_error:
                logger.error(f"Error parsing JSON from LLM response: {json_error}")
                # Return a fallback response
                return orjson.dumps({
                    "reasoning": "Error parsing chart generation response",
                    "chart_type": "",
                    "chart_schema": {},
                    "enhanced_metadata": {
                        "data_analysis": {},
                        "alternative_charts": [],
                        "chart_selection_reasoning": "Error parsing response"
                    }
                }).decode('utf-8')
                
        except Exception as e:
            logger.error(f"Error in direct chart generation: {e}")
            raise


class EnhancedVegaLiteChartGenerationPipeline:
    """Enhanced pipeline for Vega-Lite chart generation using Langchain
    
    This pipeline supports both sample data processing and full data execution.
    When execute_on_full_data=True, the chart will be generated using sample data
    for schema validation and then executed on the complete dataset.
    
    Key Features:
    - Enhanced chart types: scatter, heatmap, boxplot, histogram, bubble, text, tick, rule
    - Intelligent chart type selection based on data analysis
    - Sample data processing for efficient chart schema generation
    - Full data execution for complete dataset visualization
    - Schema validation against Vega-Lite specifications
    - Multiple export formats (JSON, Observable, Altair, Summary)
    - Comprehensive error handling and validation
    - Enhanced metadata and alternative chart suggestions
    
    Usage:
        pipeline = EnhancedVegaLiteChartGenerationPipeline()
        result = await pipeline.run(
            query="Show sales vs profit relationship",
            sql="SELECT * FROM sales",
            data={"columns": [...], "data": [...]},
            execute_on_full_data=True  # Execute on full dataset
        )
    """
    
    def __init__(self, vega_schema: Optional[Dict[str, Any]] = None, **kwargs):
        self.agent = EnhancedVegaLiteChartGenerationAgent(vega_schema, **kwargs)
        self.vega_schema = vega_schema or self._load_default_vega_schema()
        # Create a KPI processing pipeline instance for proper KPI handling
        self.kpi_processor = VegaLiteChartGenerationPipeline(vega_schema=vega_schema, **kwargs)
        self._initialized = True
    
    def _load_default_vega_schema(self) -> Dict[str, Any]:
        """Load default Vega-Lite schema"""
        try:
            with open("app/agents/nodes/sql/utils/vega-lite-schema-v5.json", "r") as f:
                return orjson.loads(f.read())
        except Exception as e:
            logger.warning(f"Could not load Vega-Lite schema: {e}")
            return {}
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    @observe(as_type="generation", capture_input=False)
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
        """Run the enhanced chart generation pipeline
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_schema: Whether to remove data from config
            export_format: Optional export format
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        
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
            
            # Check if chart type is KPI and process accordingly using the proper KPI logic
            chart_type = result.get("chart_type", "").lower()
            chart_schema = result.get("chart_schema", {})
            
            # Early detection: Check data structure for comparison KPI patterns
            columns = data.get("columns", [])
            data_rows = data.get("data", [])
            
            # Log for debugging
            logger.info(f"Enhanced pipeline: Checking for KPI chart. chart_type={chart_type}, chart_schema keys={list(chart_schema.keys()) if chart_schema else 'empty'}, data_rows={len(data_rows)}, columns={len(columns)}")
            
            # Check for comparison KPI patterns in column names
            has_comparison_patterns = False
            if columns:
                col_names_lower = [col.lower() if isinstance(col, str) else str(col).lower() for col in columns]
                has_current = any(any(kw in col for kw in ["this_year", "current", "this_month", "completed_this", "learners_this"]) for col in col_names_lower)
                has_previous = any(any(kw in col for kw in ["last_year", "previous", "last_month", "prior", "completed_last", "learners_last"]) for col in col_names_lower)
                has_percentage_change = any("percentage_change" in col or "percent_change" in col for col in col_names_lower)
                has_comparison_patterns = (has_current and has_previous) or has_percentage_change
                logger.info(f"Enhanced pipeline: Comparison pattern detection - has_current={has_current}, has_previous={has_previous}, has_percentage_change={has_percentage_change}, has_comparison_patterns={has_comparison_patterns}")
            
            # Check for KPI chart indicators
            kpi_metadata = chart_schema.get("kpi_metadata", {}) if chart_schema else {}
            has_kpi_metadata = kpi_metadata is not None and kpi_metadata != {}
            is_dummy_kpi = kpi_metadata.get("is_dummy", False) if isinstance(kpi_metadata, dict) else False
            
            # Check mark type
            mark_type = ""
            if chart_schema and isinstance(chart_schema.get("mark"), dict):
                mark_type = chart_schema.get("mark", {}).get("type", "")
            
            # Detect KPI charts - including dummy ones that need to be replaced
            # IMPORTANT: Also check if chart_type is "kpi" even if chart_schema is minimal
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
                (mark_type == "text" and is_kpi_suitable_shape) or
                (num_rows == 1 and num_columns <= 2)  # Single row with 1-2 columns likely a KPI
            )
            
            # IMPORTANT: Override KPI detection if data has more than 2 columns
            # Data with >2 columns should use a more appropriate chart type
            if num_columns > 2 and not ("kpi" in chart_type and has_kpi_metadata):
                # Only force non-KPI if the LLM didn't explicitly choose KPI with metadata
                if is_kpi_chart and not has_kpi_metadata and not has_comparison_patterns:
                    logger.info(f"Enhanced pipeline: Overriding KPI detection - data has {num_columns} columns (>2), selecting better chart type")
                    is_kpi_chart = False
            
            logger.info(f"Enhanced pipeline: KPI detection result - is_kpi_chart={is_kpi_chart}, chart_type={chart_type}, has_comparison_patterns={has_comparison_patterns}, mark_type={mark_type}, data_rows={len(data_rows)}, columns={len(columns)}")
            
            # CRITICAL: Process KPI even if chart_schema is minimal - we'll generate it properly
            if is_kpi_chart:
                # If chart_schema is empty or minimal, create a basic one
                if not chart_schema or not chart_schema.get("mark"):
                    logger.info("Enhanced pipeline: Chart schema is minimal/empty, creating basic KPI schema structure")
                    chart_schema = {
                        "title": result.get("chart_schema", {}).get("title", "") or "Key Performance Indicator",
                        "mark": {"type": "text"}
                    }
                logger.info(f"Enhanced pipeline: Detected KPI chart, processing with proper KPI logic... (chart_type={chart_type}, has_kpi_metadata={has_kpi_metadata}, is_dummy={is_dummy_kpi}, has_comparison_patterns={has_comparison_patterns})")
                
                # If this is a dummy KPI, we MUST replace it with a proper KPI schema
                if is_dummy_kpi:
                    logger.warning(f"Enhanced pipeline: Detected dummy KPI schema - replacing with proper KPI generation. Original schema had is_dummy={is_dummy_kpi}")
                    # Clear the dummy schema and let _process_kpi_chart generate a new one
                    # Keep only essential fields that might be useful
                    chart_schema = {
                        "title": chart_schema.get("title", ""),
                        "mark": {"type": "text"}  # Minimal schema to indicate KPI
                    }
                
                # Process KPI chart with specialized logic using the proper KPI processor
                # This will always generate a proper, functional KPI schema
                processed_schema = await self.kpi_processor._process_kpi_chart(
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
                    logger.error("ERROR: Enhanced pipeline - Processed schema still has is_dummy=true - this should never happen!")
                    # Force remove it
                    processed_schema["kpi_metadata"].pop("is_dummy", None)
                    processed_schema["kpi_metadata"]["vega_lite_compatible"] = True
                
                # CRITICAL: Validate and fix encoding field to match actual data fields
                processed_schema = self.kpi_processor._validate_and_fix_encoding_field(processed_schema)
                
                result["chart_schema"] = processed_schema
                
                # Update chart type to reflect KPI subtype if available
                if "kpi_metadata" in processed_schema:
                    kpi_metadata = processed_schema.get("kpi_metadata", {})
                    chart_subtype = kpi_metadata.get("chart_subtype", "")
                    if chart_subtype:
                        result["chart_type"] = f"kpi_{chart_subtype}"
                    else:
                        result["chart_type"] = "kpi"
                
                logger.info(f"Enhanced pipeline: KPI chart processed. Final kpi_metadata: {processed_schema.get('kpi_metadata', {})}")
                logger.info(f"Enhanced pipeline: Final processed schema keys: {list(processed_schema.keys())}")
                logger.info(f"Enhanced pipeline: Final processed schema has encoding: {'encoding' in processed_schema}")
                logger.info(f"Enhanced pipeline: Final processed schema has transform: {'transform' in processed_schema}")
            else:
                logger.info(f"Enhanced pipeline: Chart not detected as KPI. is_kpi_chart={is_kpi_chart}, chart_schema exists={bool(chart_schema)}")
                logger.info(f"Enhanced pipeline: Chart type: {chart_type}, Has KPI metadata: {has_kpi_metadata}, Has comparison patterns: {has_comparison_patterns}, Mark type: {mark_type}, Data rows: {len(data_rows)}, Columns: {len(columns)}")
            
            logger.info(f"Enhanced chart generation pipeline result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced chart generation pipeline: {e}")
            return {
                "chart_schema": {},
                "reasoning": f"Error in pipeline: {str(e)}",
                "chart_type": "",
                "enhanced_metadata": {
                    "data_analysis": {},
                    "alternative_charts": [],
                    "chart_selection_reasoning": f"Error: {str(e)}"
                },
                "success": False,
                "error": str(e)
            }


def create_enhanced_vega_lite_chart_generation_pipeline() -> EnhancedVegaLiteChartGenerationPipeline:
    """Factory function to create an enhanced Vega-Lite chart generation pipeline"""
    return EnhancedVegaLiteChartGenerationPipeline()


# Enhanced chart generation with reasoning
class EnhancedChartGenerationWithReasoning:
    """Enhanced chart generation with detailed reasoning and multiple options"""
    
    def __init__(self, llm=None, **kwargs):
        """Initialize the enhanced chart generation with reasoning"""
        self.llm = llm or get_llm()
        self.pipeline = EnhancedVegaLiteChartGenerationPipeline(llm=self.llm, **kwargs)
    
    async def generate_chart_with_reasoning(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        include_alternatives: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate chart with detailed reasoning and alternative options"""
        
        try:
            # Get analysis suggestions
            analysis_suggestions = await self.pipeline.suggest_analysis_type(data, query)
            
            # Generate primary chart
            primary_result = await self.pipeline.run(query, sql, data, language, **kwargs)
            
            # Generate reasoning
            reasoning = await self._generate_detailed_reasoning(
                query, sql, data, primary_result, analysis_suggestions, language
            )
            
            result = {
                "primary_chart": primary_result,
                "reasoning": reasoning,
                "analysis_suggestions": analysis_suggestions,
                "success": primary_result.get("success", False)
            }
            
            # Generate alternative charts if requested
            if include_alternatives and analysis_suggestions:
                alternatives = await self._generate_alternative_charts(
                    query, sql, data, analysis_suggestions[:3], language, **kwargs
                )
                result["alternative_charts"] = alternatives
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced chart generation with reasoning: {e}")
            return {
                "primary_chart": {},
                "reasoning": f"Error generating chart: {str(e)}",
                "analysis_suggestions": [],
                "success": False,
                "error": str(e)
            }
    
    async def _generate_detailed_reasoning(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        chart_result: Dict[str, Any],
        analysis_suggestions: List[str],
        language: str
    ) -> str:
        """Generate detailed reasoning for the chart choice"""
        
        reasoning_prompt = f"""
        You are a data visualization expert. Analyze the following and provide detailed reasoning for the chart choice:

        User Question: {query}
        SQL Query: {sql}
        Data Shape: {data.get('data', [])[:3]} (showing first 3 rows)
        Selected Chart Type: {chart_result.get('chart_type', 'unknown')}
        Analysis Suggestions: {analysis_suggestions}

        Please provide detailed reasoning in {language} covering:
        1. Why this chart type was chosen over others
        2. How it effectively answers the user's question
        3. What insights can be derived from this visualization
        4. Any limitations or considerations
        5. Alternative approaches that could be considered

        Keep the reasoning concise but comprehensive.
        """
        
        try:
            response = await self.llm.ainvoke(reasoning_prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating reasoning: {e}")
            return f"Chart type {chart_result.get('chart_type', 'unknown')} was selected based on the data structure and user question."
    
    async def _generate_alternative_charts(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        analysis_types: List[str],
        language: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Generate alternative charts using different analysis types"""
        
        alternatives = []
        
        for analysis_type in analysis_types:
            try:
                # Skip if it's the same as the primary chart type
                if analysis_type in query.lower():
                    continue
                
                # Generate alternative using template
                alt_result = await self.pipeline.run_with_template(
                    query, sql, data, analysis_type, language, **kwargs
                )
                
                if alt_result.get("success", False):
                    alternatives.append({
                        "analysis_type": analysis_type,
                        "chart_result": alt_result,
                        "description": self.pipeline.chart_templates[analysis_type]["description"]
                    })
                
            except Exception as e:
                logger.warning(f"Error generating alternative chart for {analysis_type}: {e}")
                continue
        
        return alternatives


# Convenience functions for easy usage
async def generate_enhanced_chart(
    query: str,
    sql: str,
    data: Dict[str, Any],
    language: str = "English",
    include_reasoning: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to generate enhanced charts
    
    Args:
        query: User's question
        sql: SQL query that generated the data
        data: Data dictionary with 'columns' and 'data' fields
        language: Language for titles and labels
        include_reasoning: Whether to include detailed reasoning
        **kwargs: Additional arguments
    
    Returns:
        Dict containing the chart result and metadata
    """
    
    if include_reasoning:
        generator = EnhancedChartGenerationWithReasoning(**kwargs)
        return await generator.generate_chart_with_reasoning(query, sql, data, language)
    else:
        pipeline = EnhancedVegaLiteChartGenerationPipeline(**kwargs)
        return await pipeline.run(query, sql, data, language)


async def generate_chart_with_template(
    query: str,
    sql: str,
    data: Dict[str, Any],
    template_name: str,
    language: str = "English",
    **kwargs
) -> Dict[str, Any]:
    """
    Generate chart using a specific template
    
    Args:
        query: User's question
        sql: SQL query that generated the data
        data: Data dictionary with 'columns' and 'data' fields
        template_name: Name of the template to use
        language: Language for titles and labels
        **kwargs: Additional arguments
    
    Returns:
        Dict containing the chart result
    """
    
    pipeline = EnhancedVegaLiteChartGenerationPipeline(**kwargs)
    return await pipeline.run_with_template(query, sql, data, template_name, language) 