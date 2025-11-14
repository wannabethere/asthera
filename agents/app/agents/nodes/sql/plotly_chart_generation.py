import logging
from typing import Any, Dict, Optional, List
import asyncio
import json

import orjson
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent import AgentExecutor
from langchain.schema import AgentAction, AgentFinish
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema import LLMResult

from app.agents.nodes.sql.utils.plotly_chart import (
    PlotlyChartDataPreprocessor,
    PlotlyChartGenerationPostProcessor,
    PlotlyChartGenerationResults,
    plotly_chart_generation_instructions,
    create_plotly_data_preprocessor_tool,
    create_plotly_chart_postprocessor_tool,
    PlotlyChartExporter,
)

logger = logging.getLogger("lexy-ai-service")


class PlotlyChartGenerationAgent:
    """Langchain agent for Plotly chart generation"""
    
    def __init__(self, llm, **kwargs):
        self.llm = llm
        self.data_preprocessor = PlotlyChartDataPreprocessor()
        self.post_processor = PlotlyChartGenerationPostProcessor()
        self.exporter = PlotlyChartExporter()
        
        # Create tools
        self.tools = [
            create_plotly_data_preprocessor_tool(),
            create_plotly_chart_postprocessor_tool(),
        ]
        
        # Initialize agent
        self.agent = self._create_agent()
        
        # System prompt for Plotly chart generation
        self.system_prompt = f"""
        ### TASK ###
        
        You are a data analyst expert at creating Plotly visualizations! Given the user's question, SQL query, sample data, sample column values, and column metadata, you need to generate a Plotly chart configuration in JSON format and provide the most suitable chart type.
        
        You need to analyze the data structure, understand the user's intent, and create an appropriate Plotly chart configuration that effectively visualizes the data to answer the user's question.
        
        Additionally, provide a concise and easy-to-understand reasoning to describe why you chose this particular chart type and configuration based on the question, SQL query, sample data, and column metadata.
        
        {plotly_chart_generation_instructions}
        
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
        
        Please provide your chain of thought reasoning, chart type, and the Plotly chart configuration in JSON format.
        
        {{
            "reasoning": "<REASON_TO_CHOOSE_THE_CHART_TYPE_AND_CONFIGURATION_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>",
            "chart_type": "scatter" | "line" | "bar" | "horizontal_bar" | "pie" | "histogram" | "box" | "heatmap" | "area" | "violin" | "bubble" | "sunburst" | "treemap" | "waterfall" | "funnel" | "",
            "chart_config": <PLOTLY_CHART_JSON_CONFIGURATION>
        }}
        
        ### DATA SIZE CONSIDERATIONS ###
        
        IMPORTANT: Before selecting a chart type, check the data size (number of rows in the sample data):
        - If the data has MORE than 5 rows, you MUST NOT recommend KPI charts (also known as metric cards, gauge charts, indicator charts, or single-value visualizations)
        - KPI charts are only suitable for datasets with 5 or fewer rows, as they display individual metrics that cannot effectively render when there are many data points
        - For datasets with more than 5 rows, choose from other appropriate chart types such as:
          * Line charts for trends over time
          * Bar charts for categorical comparisons
          * Pie charts for part-to-whole relationships
          * Area charts for cumulative trends
          * Scatter plots for correlations
          * Histograms for distributions
          * Heatmaps for multi-dimensional data
          * And other suitable visualization types based on the data structure
        
        Always count the rows in the sample data before making your chart type recommendation.
        
        ### IMPORTANT NOTES ###
        
        - Ensure all field names in traces exist in the actual data columns
        - Choose appropriate trace types based on chart type (scatter for line/scatter, bar for bar charts, pie for pie charts)
        - Use proper data types and scales for axes
        - Consider the user's question intent when selecting chart type
        - For multiple metrics, consider using multiple traces or secondary y-axis
        - For categorical data, use appropriate color schemes and legends
        - For time series data, ensure proper date formatting and time-based x-axis
        - For statistical data, consider box plots, histograms, or violin plots
        - Configure layout properties (title, axis labels, legends) appropriately
        """
        
        # User prompt template
        self.user_prompt_template = PromptTemplate(
            input_variables=["query", "sql", "sample_data", "sample_column_values", "column_metadata", "language", "existing_chart_schema"],
            template="""
            ### INPUT ###
            Question: {query}
            SQL: {sql}
            Sample Data: {sample_data}
            Sample Column Values: {sample_column_values}
            Column Metadata: {column_metadata}
            Language: {language}
            Existing Chart Schema: {existing_chart_schema}
            
            Please analyze the data and user question step by step to create the most appropriate Plotly visualization.
            """
        )
    
    def _create_agent(self) -> AgentExecutor:
        """Create and configure the Langchain agent"""
        try:
            agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=3,
                early_stopping_method="generate"
            )
            return agent
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise
    
    async def generate_chart(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_config: bool = True,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate Plotly chart configuration using the agent
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_config: Whether to remove data from config
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        try:
            # Preprocess data
            preprocessed_data = self.data_preprocessor.run(data)
            
            # Create the prompt
            prompt = self.user_prompt_template.format(
                query=query,
                sql=sql,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                column_metadata=preprocessed_data["column_metadata"],
                language=language,
                existing_chart_schema=json.dumps(existing_chart_schema) if existing_chart_schema else "None"
            )
            
            # Generate chart using LLM directly (more controlled approach)
            chart_result = await self._generate_chart_direct(prompt)
            
            # Post-process the result
            final_result = self.post_processor.run(
                chart_result, 
                preprocessed_data["sample_data"], 
                remove_data_from_chart_config
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in chart generation: {e}")
            return {
                "chart_config": {},
                "reasoning": f"Error generating chart: {str(e)}",
                "chart_type": "",
                "success": False,
                "error": str(e)
            }
    
    async def _generate_chart_direct(self, prompt: str) -> str:
        """Generate chart using LLM directly with structured output"""
        try:
            # Create a chain for structured output
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=generation_prompt)
            
            # Generate response
            result = await chain.arun(
                system_prompt=self.system_prompt,
                user_prompt=prompt
            )
            
            # Ensure the result is a properly formatted JSON string
            try:
                # First try to parse the raw result
                parsed_result = orjson.loads(result)
                return orjson.dumps(parsed_result).decode('utf-8')
            except orjson.JSONDecodeError:
                # If parsing fails, try to extract JSON from the text
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        # Validate the extracted JSON
                        parsed_result = orjson.loads(json_str)
                        return orjson.dumps(parsed_result).decode('utf-8')
                    except orjson.JSONDecodeError:
                        pass
                
                # If all parsing attempts fail, return a default structure
                default_result = {
                    "reasoning": "Failed to parse LLM response into valid JSON format.",
                    "chart_type": "",
                    "chart_config": {}
                }
                return orjson.dumps(default_result).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error in direct chart generation: {e}")
            default_result = {
                "reasoning": f"Error: {str(e)}",
                "chart_type": "",
                "chart_config": {}
            }
            return orjson.dumps(default_result).decode('utf-8')


class PlotlyChartGenerationPipeline:
    """Main pipeline for Plotly chart generation using Langchain"""
    
    def __init__(self, llm, **kwargs):
        self.agent = PlotlyChartGenerationAgent(llm, **kwargs)
        self.exporter = PlotlyChartExporter()
    
    async def _process_kpi_chart(
        self,
        data: Dict[str, Any],
        chart_config: Dict[str, Any],
        query: str,
        language: str = "English"
    ) -> Dict[str, Any]:
        """Process KPI chart generation using LLM
        
        Args:
            data: Data dictionary with columns and data
            chart_config: Initial chart config from LLM
            query: Natural language query
            language: Language for the chart
            
        Returns:
            Updated chart config with KPI-specific configuration
        """
        try:
            columns = data.get("columns", [])
            data_rows = data.get("data", [])
            
            if not data_rows or len(data_rows) == 0:
                logger.warning("No data available for KPI chart")
                return chart_config
            
            # Preprocess data for KPI generation
            preprocessed_data = self.agent.data_preprocessor.run(data)
            
            # Generate KPI chart using LLM
            kpi_config = await self._generate_kpi_chart_with_llm(
                query=query,
                columns=columns,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                column_metadata=preprocessed_data.get("column_metadata", {}),
                language=language,
                existing_config=chart_config
            )
            
            # Merge with existing config, preserving any customizations
            if kpi_config:
                # Preserve title from original config if it exists
                if "layout" in chart_config and "title" in chart_config.get("layout", {}):
                    if "layout" not in kpi_config:
                        kpi_config["layout"] = {}
                    kpi_config["layout"]["title"] = chart_config["layout"]["title"]
                
                # Update the chart config
                chart_config.update(kpi_config)
                logger.info("Generated KPI chart config using LLM")
            
            return chart_config
            
        except Exception as e:
            logger.error(f"Error processing KPI chart: {e}")
            return chart_config
    
    async def _generate_kpi_chart_with_llm(
        self,
        query: str,
        columns: List[str],
        sample_data: Dict[str, Any],
        sample_column_values: Dict[str, Any],
        column_metadata: Dict[str, Any],
        language: str,
        existing_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate KPI chart config using LLM with specialized KPI prompt for Plotly"""
        try:
            kpi_system_prompt = f"""
            ### TASK ###
            
            You are an expert at creating KPI (Key Performance Indicator) charts using Plotly! Given the user's question, data columns, sample data, and sample column values, you need to generate a specialized KPI chart configuration.
            
            KPI charts are single-value visualizations that display important metrics. There are four main types of KPI charts:
            
            ### 1. COUNTER KPI ###
            Purpose: Displays a single numeric count or total value.
            
            Plotly Config Structure:
            {{
                "data": [{{
                    "type": "indicator",
                    "mode": "number",
                    "value": <NUMERIC_VALUE>,
                    "number": {{
                        "font": {{ "size": 48, "color": "#2563eb" }},
                        "valueformat": ","
                    }},
                    "title": {{ "text": "<TITLE>", "font": {{ "size": 20 }} }}
                }}],
                "layout": {{
                    "title": {{ "text": "<TITLE>" }},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white"
                }},
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
            
            Plotly Config Structure:
            {{
                "data": [{{
                    "type": "indicator",
                    "mode": "number",
                    "value": <0_TO_1_VALUE>,
                    "number": {{
                        "font": {{ "size": 48, "color": "#10b981" }},
                        "valueformat": ".0%"
                    }},
                    "title": {{ "text": "<TITLE>", "font": {{ "size": 20 }} }}
                }}],
                "layout": {{
                    "title": {{ "text": "<TITLE>" }},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white"
                }},
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
            
            Plotly Config Structure:
            {{
                "data": [{{
                    "type": "indicator",
                    "mode": "number+delta",
                    "value": <0_TO_100_VALUE>,
                    "number": {{
                        "font": {{ 
                            "size": 48,
                            "color": "<COLOR_BASED_ON_VALUE>"
                        }},
                        "valueformat": ".0f"
                    }},
                    "title": {{ "text": "<TITLE>", "font": {{ "size": 20 }} }},
                    "delta": {{
                        "reference": 50,
                        "position": "top"
                    }}
                }}],
                "layout": {{
                    "title": {{ "text": "<TITLE>" }},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white"
                }},
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
            
            Plotly Config Structure:
            {{
                "data": [{{
                    "type": "indicator",
                    "mode": "number+delta",
                    "value": <CURRENT_VALUE>,
                    "delta": {{
                        "reference": <PREVIOUS_VALUE>,
                        "position": "top",
                        "valueformat": ".1%",
                        "increasing": {{ "color": "#16a34a" }},
                        "decreasing": {{ "color": "#ef4444" }}
                    }},
                    "number": {{
                        "font": {{ 
                            "size": 48,
                            "color": "#2563eb"
                        }},
                        "valueformat": ","
                    }},
                    "title": {{ "text": "<TITLE>", "font": {{ "size": 20 }} }}
                }}],
                "layout": {{
                    "title": {{ "text": "<TITLE> vs Previous" }},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white"
                }},
                "kpi_metadata": {{
                    "chart_type": "comparison_kpi",
                    "chart_subtype": "current_vs_percentage",
                    "columns": ["current", "previous", "percentage_change"],
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
               - Column names contain "current", "previous", "prior", "last"
               - The query mentions comparison, change, increase, decrease, growth, vs, versus
               - You want to show both the current value and the percentage change
            
            ### OUTPUT FORMAT ###
            
            You MUST respond with ONLY a valid JSON object containing the complete Plotly KPI chart configuration. Do NOT include:
            - Any text before the JSON
            - Any text after the JSON
            - Markdown formatting
            - Code blocks
            - Explanations outside the JSON
            
            Your response should be a single JSON object starting with {{ and ending with }}.
            
            ### IMPORTANT NOTES ###
            
            - Extract the actual values from the sample data
            - Use appropriate field names from the columns
            - Ensure all numeric values are properly formatted
            - For percentage KPI, normalize values > 1 by dividing by 100
            - For comparison KPI, identify current and previous columns intelligently
            - Use Plotly's indicator chart type for KPI visualizations
            - Use the query to determine an appropriate title
            - Preserve any existing title from the existing_config if provided
            """
            
            kpi_user_prompt = f"""
            ### INPUT ###
            Question: {query}
            Columns: {json.dumps(columns)}
            Sample Data: {json.dumps(sample_data)}
            Sample Column Values: {json.dumps(sample_column_values)}
            Column Metadata: {json.dumps(column_metadata)}
            Language: {language}
            Existing Config: {json.dumps(existing_config) if existing_config else "None"}
            
            Please analyze the data and generate the most appropriate Plotly KPI chart configuration based on the question and data structure.
            """
            
            # Generate KPI config using LLM
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{{system_prompt}}\n\n{{user_prompt}}"
            )
            
            chain = LLMChain(llm=self.agent.llm, prompt=generation_prompt)
            
            result = await chain.arun(
                system_prompt=kpi_system_prompt,
                user_prompt=kpi_user_prompt
            )
            
            # Extract content from the response
            if hasattr(result, 'content'):
                result_str = result.content
            else:
                result_str = str(result)
            
            logger.info(f"Raw LLM KPI response (Plotly): {result_str}")
            
            # Parse JSON response
            try:
                parsed = orjson.loads(result_str)
                logger.info(f"Successfully parsed KPI JSON directly: {parsed}")
                return parsed
            except orjson.JSONDecodeError:
                import re
                json_patterns = [
                    r'```json\s*(\{{.*?\}})\s*```',
                    r'```\s*(\{{.*?\}})\s*```',
                    r'(\{{.*?\}})',
                ]
                
                for pattern in json_patterns:
                    json_matches = re.findall(pattern, result_str, re.DOTALL)
                    for match in json_matches:
                        try:
                            parsed = orjson.loads(match)
                            logger.info(f"Successfully parsed KPI JSON from pattern: {parsed}")
                            return parsed
                        except orjson.JSONDecodeError:
                            continue
                
                logger.warning("Failed to parse JSON from LLM KPI response")
                return {}
            
        except Exception as e:
            logger.error(f"Error generating KPI chart with LLM: {e}")
            return {}
    
    async def run(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_config: bool = True,
        export_format: Optional[str] = None,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the complete Plotly chart generation pipeline
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_config: Whether to remove data from config
            export_format: Optional export format
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        logger.info("Plotly Chart Generation pipeline is running...")
        
        try:
            # Generate chart
            result = await self.agent.generate_chart(
                query=query,
                sql=sql,
                data=data,
                language=language,
                remove_data_from_chart_config=remove_data_from_chart_config,
                existing_chart_schema=existing_chart_schema
            )
            
            # Check if chart type is KPI and process accordingly
            chart_type = result.get("chart_type", "").lower()
            chart_config = result.get("chart_config", {})
            
            # Check for KPI chart indicators
            is_kpi_chart = (
                "kpi" in chart_type or
                "metric" in chart_type or
                "counter" in chart_type or
                "gauge" in chart_type or
                "indicator" in chart_type or
                chart_config.get("kpi_metadata") is not None or
                (isinstance(chart_config.get("data"), list) and
                 len(chart_config.get("data", [])) > 0 and
                 chart_config.get("data", [{}])[0].get("type") == "indicator" and
                 len(data.get("data", [])) <= 5)
            )
            
            if is_kpi_chart and chart_config:
                logger.info("Detected KPI chart, processing with KPI-specific logic...")
                # Process KPI chart with specialized logic using LLM
                processed_config = await self._process_kpi_chart(
                    data=data,
                    chart_config=chart_config,
                    query=query,
                    language=language
                )
                result["chart_config"] = processed_config
                # Update chart type to reflect KPI subtype if available
                if "kpi_metadata" in processed_config:
                    kpi_metadata = processed_config.get("kpi_metadata", {})
                    chart_subtype = kpi_metadata.get("chart_subtype", "")
                    if chart_subtype:
                        result["chart_type"] = f"kpi_{chart_subtype}"
                    else:
                        result["chart_type"] = "kpi"
            
            # Add export functionality if requested
            if export_format and result.get("success", False):
                chart_config = result.get("chart_config", {})
                
                if export_format == "json":
                    result["exported_json"] = self.exporter.to_plotly_json(chart_config)
                elif export_format == "python":
                    result["python_code"] = self.exporter.to_plotly_python(chart_config)
                elif export_format == "express":
                    result["express_code"] = self.exporter.to_plotly_express(chart_config)
                elif export_format == "javascript":
                    result["javascript_code"] = self.exporter.to_javascript(chart_config)
                elif export_format == "summary":
                    result["chart_summary"] = self.exporter.get_chart_summary(chart_config)
                elif export_format == "all":
                    result["exported_json"] = self.exporter.to_plotly_json(chart_config)
                    result["python_code"] = self.exporter.to_plotly_python(chart_config)
                    result["express_code"] = self.exporter.to_plotly_express(chart_config)
                    result["javascript_code"] = self.exporter.to_javascript(chart_config)
                    result["chart_summary"] = self.exporter.get_chart_summary(chart_config)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in pipeline execution: {e}")
            return {
                "chart_config": {},
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
        
        This is a convenience method that creates an AdvancedPlotlyChartGeneration
        instance and calls its generate_chart_from_template method.
        """
        advanced_pipeline = AdvancedPlotlyChartGeneration(self.agent.llm)
        return await advanced_pipeline.generate_chart_from_template(
            existing_chart, new_data, field_mapping, language
        )


# Alternative pipeline class matching original structure
class PlotlyChartGeneration:
    """Plotly chart generation pipeline compatible with original interface"""
    
    def __init__(self, llm, **kwargs):
        self.pipeline = PlotlyChartGenerationPipeline(llm, **kwargs)
    
    async def run(
        self,
        query: str,
        sql: str,
        data: dict,
        language: str,
        remove_data_from_chart_config: Optional[bool] = True,
    ) -> dict:
        """Run chart generation with original interface"""
        result = await self.pipeline.run(
            query=query,
            sql=sql,
            data=data,
            language=language,
            remove_data_from_chart_config=remove_data_from_chart_config
        )
        
        # Transform result to match original output format
        return {
            "results": {
                "chart_config": result.get("chart_config", {}),
                "reasoning": result.get("reasoning", ""),
                "chart_type": result.get("chart_type", ""),
            }
        }


# Factory function to create the pipeline
def create_plotly_chart_generation_pipeline(llm, **kwargs) -> PlotlyChartGenerationPipeline:
    """Factory function to create Plotly chart generation pipeline"""
    return PlotlyChartGenerationPipeline(llm, **kwargs)


def create_plotly_chart_generation_pipeline_original(llm, **kwargs) -> PlotlyChartGeneration:
    """Factory function to create chart generation pipeline with original interface"""
    return PlotlyChartGeneration(llm, **kwargs)


# Utility functions for integration
async def generate_plotly_chart(
    llm,
    query: str,
    sql: str,
    data: Dict[str, Any],
    language: str = "English",
    export_format: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to generate Plotly chart"""
    pipeline = create_plotly_chart_generation_pipeline(llm)
    return await pipeline.run(
        query=query,
        sql=sql,
        data=data,
        language=language,
        export_format=export_format
    )


# Enhanced chart generation with additional features
class AdvancedPlotlyChartGeneration(PlotlyChartGenerationPipeline):
    """Advanced Plotly chart generation with additional features"""
    
    def __init__(self, llm, **kwargs):
        super().__init__(llm, **kwargs)
        self.chart_templates = self._load_chart_templates()
    
    def _load_chart_templates(self) -> Dict[str, Any]:
        """Load predefined chart templates"""
        return {
            "sales_trend": {
                "type": "line",
                "description": "Shows sales trends over time",
                "required_fields": ["date", "sales"],
                "template": {
                    "chart_type": "line",
                    "data": [{
                        "type": "scatter",
                        "mode": "lines+markers",
                        "line": {"width": 2},
                        "marker": {"size": 6}
                    }],
                    "layout": {
                        "xaxis": {"title": "Date"},
                        "yaxis": {"title": "Sales"},
                        "showlegend": True
                    }
                }
            },
            "category_comparison": {
                "type": "bar",
                "description": "Compares values across categories",
                "required_fields": ["category", "value"],
                "template": {
                    "chart_type": "bar",
                    "data": [{
                        "type": "bar",
                        "marker": {
                            "color": "lightblue",
                            "line": {"color": "darkblue", "width": 1}
                        }
                    }],
                    "layout": {
                        "xaxis": {"title": "Category"},
                        "yaxis": {"title": "Value"},
                        "showlegend": False
                    }
                }
            },
            "distribution": {
                "type": "pie",
                "description": "Shows distribution of parts within a whole",
                "required_fields": ["category", "value"],
                "template": {
                    "chart_type": "pie",
                    "data": [{
                        "type": "pie",
                        "textinfo": "label+percent",
                        "textposition": "auto"
                    }],
                    "layout": {
                        "showlegend": True
                    }
                }
            },
            "correlation": {
                "type": "scatter",
                "description": "Shows correlation between two variables",
                "required_fields": ["x_variable", "y_variable"],
                "template": {
                    "chart_type": "scatter",
                    "data": [{
                        "type": "scatter",
                        "mode": "markers",
                        "marker": {"size": 8}
                    }],
                    "layout": {
                        "xaxis": {"title": "X Variable"},
                        "yaxis": {"title": "Y Variable"},
                        "showlegend": True
                    }
                }
            },
            "statistical_distribution": {
                "type": "histogram",
                "description": "Shows statistical distribution of a variable",
                "required_fields": ["variable"],
                "template": {
                    "chart_type": "histogram",
                    "data": [{
                        "type": "histogram",
                        "nbinsx": 20,
                        "marker": {"color": "skyblue", "line": {"color": "black", "width": 1}}
                    }],
                    "layout": {
                        "xaxis": {"title": "Variable"},
                        "yaxis": {"title": "Frequency"},
                        "showlegend": False
                    }
                }
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
                col_index = columns.index(col) if col in columns else -1
                if col_index >= 0:
                    sample_values = [row[col_index] for row in data_sample if len(row) > col_index]
                    
                    if any(isinstance(val, (int, float)) for val in sample_values):
                        numeric_fields.append(col_name)
                    elif any(str(val).lower() in ['date', 'time', 'month', 'year'] for val in sample_values):
                        temporal_fields.append(col_name)
                    else:
                        categorical_fields.append(col_name)
        
        # Suggest based on field types and combinations
        if temporal_fields and numeric_fields:
            suggestions.extend(["line", "area"])
        
        if categorical_fields and numeric_fields:
            suggestions.extend(["bar", "pie"])
            
            # Multiple categories suggest grouped/stacked charts
            if len(categorical_fields) >= 2:
                suggestions.append("heatmap")
        
        if len(numeric_fields) >= 2:
            suggestions.extend(["scatter", "bubble"])
        
        if len(numeric_fields) >= 1 and not categorical_fields:
            suggestions.extend(["histogram", "box"])
        
        # Query-based suggestions
        query_lower = query.lower()
        if any(word in query_lower for word in ["trend", "over time", "time series"]):
            suggestions.append("line")
        elif any(word in query_lower for word in ["compare", "comparison", "vs"]):
            suggestions.extend(["bar", "scatter"])
        elif any(word in query_lower for word in ["distribution", "share", "percentage"]):
            suggestions.extend(["pie", "histogram"])
        elif any(word in query_lower for word in ["correlation", "relationship"]):
            suggestions.append("scatter")
        elif any(word in query_lower for word in ["outlier", "statistical"]):
            suggestions.extend(["box", "violin"])
        
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
    
    async def apply_template(
        self,
        template_name: str,
        data: Dict[str, Any],
        field_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Apply a predefined template with field mapping"""
        if template_name not in self.chart_templates:
            return {"error": f"Template '{template_name}' not found"}
        
        template = self.chart_templates[template_name]["template"].copy()
        
        # Apply field mapping to template
        for trace in template.get("data", []):
            for field in ["x", "y", "labels", "values"]:
                if field in trace and trace[field] in field_mapping:
                    trace[field] = field_mapping[trace[field]]
        
        return {
            "chart_config": template,
            "chart_type": template["chart_type"],
            "reasoning": f"Applied template '{template_name}' with field mapping",
            "success": True
        }
    
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
            logger.info("Generating Plotly chart from template...")
            
            # Extract chart config from existing chart
            if "chart_config" in existing_chart:
                template_config = existing_chart["chart_config"]
            elif "results" in existing_chart and "chart_config" in existing_chart["results"]:
                template_config = existing_chart["results"]["chart_config"]
            else:
                template_config = existing_chart
            
            if not template_config:
                return {
                    "success": False,
                    "error": "No valid chart config found in existing chart",
                    "chart_config": {},
                    "reasoning": "Template chart is invalid"
                }
            
            # Preprocess new data
            preprocessed_data = self.data_preprocessor.run(new_data)
            new_columns = preprocessed_data["sample_data"].get("columns", [])
            
            # Create field mapping if not provided
            if not field_mapping:
                field_mapping = self._create_automatic_field_mapping(template_config, new_columns)
            
            # Generate new chart config based on template
            new_chart_config = self._adapt_chart_config(
                template_config, 
                new_columns, 
                field_mapping, 
                language
            )
            
            # Validate the new chart config
            validation_result = self._validate_chart_config(new_chart_config, new_columns)
            
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Chart validation failed: {validation_result['error']}",
                    "chart_config": new_chart_config,
                    "reasoning": f"Generated chart from template but validation failed: {validation_result['error']}"
                }
            
            # Determine chart type from config
            chart_type = self._extract_chart_type_from_config(new_chart_config)
            
            return {
                "success": True,
                "chart_config": new_chart_config,
                "chart_type": chart_type,
                "reasoning": f"Successfully generated Plotly chart from template using field mapping: {field_mapping}",
                "field_mapping": field_mapping,
                "template_info": {
                    "original_chart_type": existing_chart.get("chart_type", "unknown"),
                    "fields_mapped": len(field_mapping),
                    "validation_passed": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating Plotly chart from template: {e}")
            return {
                "success": False,
                "error": str(e),
                "chart_config": {},
                "reasoning": f"Error generating chart from template: {str(e)}"
            }
    
    def _create_automatic_field_mapping(
        self, 
        template_config: Dict[str, Any], 
        new_columns: List[str]
    ) -> Dict[str, str]:
        """Create automatic field mapping based on column names and config fields"""
        field_mapping = {}
        
        # Extract fields used in the template config
        template_fields = self._extract_fields_from_config(template_config)
        
        # Create mapping based on name similarity
        for template_field in template_fields:
            best_match = self._find_best_column_match(template_field, new_columns)
            if best_match:
                field_mapping[template_field] = best_match
        
        return field_mapping
    
    def _extract_fields_from_config(self, config: Dict[str, Any]) -> List[str]:
        """Extract all field names used in a Plotly chart config"""
        fields = []
        
        # Extract from data traces
        if "data" in config and isinstance(config["data"], list):
            for trace in config["data"]:
                if isinstance(trace, dict):
                    # Common field names in Plotly traces
                    field_keys = ["x", "y", "z", "labels", "values", "text", "color", "size"]
                    for key in field_keys:
                        if key in trace and isinstance(trace[key], str):
                            fields.append(trace[key])
        
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
    
    def _adapt_chart_config(
        self, 
        template_config: Dict[str, Any], 
        new_columns: List[str], 
        field_mapping: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Adapt a template chart config to work with new data"""
        import copy
        
        # Deep copy the template config
        new_config = copy.deepcopy(template_config)
        
        # Update field references in data traces
        if "data" in new_config and isinstance(new_config["data"], list):
            for trace in new_config["data"]:
                if isinstance(trace, dict):
                    self._update_trace_fields(trace, field_mapping)
        
        # Update titles to be language-appropriate
        self._update_titles_for_language(new_config, language)
        
        return new_config
    
    def _update_trace_fields(self, trace: Dict[str, Any], field_mapping: Dict[str, str]):
        """Update field references in a Plotly trace"""
        field_keys = ["x", "y", "z", "labels", "values", "text", "color", "size"]
        
        for key in field_keys:
            if key in trace and isinstance(trace[key], str) and trace[key] in field_mapping:
                trace[key] = field_mapping[trace[key]]
    
    def _update_titles_for_language(self, config: Dict[str, Any], language: str):
        """Update chart titles and labels for the specified language"""
        # Update main title
        if "layout" in config and "title" in config["layout"]:
            title = config["layout"]["title"]
            if isinstance(title, str) and "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>" in title:
                config["layout"]["title"] = f"Chart ({language})"
        
        # Update axis titles
        if "layout" in config:
            for axis_key in ["xaxis", "yaxis", "zaxis"]:
                if axis_key in config["layout"] and "title" in config[axis_key]:
                    title = config[axis_key]["title"]
                    if isinstance(title, str) and "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>" in title:
                        config[axis_key]["title"] = f"{axis_key.replace('axis', '').title()} ({language})"
    
    def _validate_chart_config(self, config: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
        """Validate that a chart config is compatible with the provided columns"""
        try:
            # Extract all field references from the config
            config_fields = self._extract_fields_from_config(config)
            
            # Check if all referenced fields exist in the data columns
            missing_fields = []
            for field in config_fields:
                if field not in columns:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Config references fields not present in data: {missing_fields}"
                }
            
            # Basic config structure validation
            if "data" not in config:
                return {
                    "valid": False,
                    "error": "Config missing required 'data' property"
                }
            
            if not isinstance(config["data"], list) or len(config["data"]) == 0:
                return {
                    "valid": False,
                    "error": "Config 'data' must be a non-empty list"
                }
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Config validation error: {str(e)}"
            }
    
    def _extract_chart_type_from_config(self, config: Dict[str, Any]) -> str:
        """Extract chart type from Plotly config"""
        if "data" not in config or not isinstance(config["data"], list) or len(config["data"]) == 0:
            return ""
        
        # Get the first trace to determine chart type
        first_trace = config["data"][0]
        if not isinstance(first_trace, dict) or "type" not in first_trace:
            return ""
        
        trace_type = first_trace["type"]
        
        # Map Plotly trace types to our chart types
        trace_to_chart_type = {
            "scatter": "scatter",
            "bar": "bar",
            "pie": "pie",
            "histogram": "histogram",
            "box": "box",
            "heatmap": "heatmap",
            "area": "area",
            "violin": "violin",
            "sunburst": "sunburst",
            "treemap": "treemap",
            "waterfall": "waterfall",
            "funnel": "funnel"
        }
        
        base_type = trace_to_chart_type.get(trace_type, "")
        
        # Check for special cases
        if trace_type == "scatter":
            mode = first_trace.get("mode", "")
            if "lines" in mode:
                return "line"
            elif "markers" in mode:
                return "scatter"
        
        if trace_type == "bar":
            orientation = first_trace.get("orientation", "v")
            if orientation == "h":
                return "horizontal_bar"
        
        return base_type


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    from langchain.llms import OpenAI
    
    # Example usage
    async def test_plotly_chart_generation():
        # Initialize LLM (replace with your preferred LLM)
        from app.core.dependencies import get_llm
        llm = get_llm()
        
        # Sample data
        sample_data = {
            "columns": ["Date", "Sales", "Region", "Profit"],
            "data": [
                ["2023-01-01", 100000, "North", 25000],
                ["2023-02-01", 120000, "North", 30000],
                ["2023-03-01", 110000, "North", 22000],
                ["2023-01-01", 90000, "South", 20000],
                ["2023-02-01", 95000, "South", 21000],
                ["2023-03-01", 105000, "South", 24000]
            ]
        }
        
        # Test chart generation
        result = await generate_plotly_chart(
            llm=llm,
            query="Show me sales trends by region over time",
            sql="SELECT Date, Sales, Region FROM sales_data ORDER BY Date",
            data=sample_data,
            language="English",
            export_format="all"
        )
        
        print("Chart Generation Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
        
        # Test with original interface
        chart_gen = create_plotly_chart_generation_pipeline_original(llm)
        original_result = await chart_gen.run(
            query="Show sales by region",
            sql="SELECT Region, SUM(Sales) FROM sales GROUP BY Region",
            data=sample_data,
            language="English"
        )
        
        print("\nOriginal Interface Result:")
        print(orjson.dumps(original_result, option=orjson.OPT_INDENT_2).decode())
        
        # Test advanced features
        advanced_gen = AdvancedPlotlyChartGeneration(llm)
        advanced_result = await advanced_gen.run_with_suggestions(
            query="Compare sales and profit across regions",
            sql="SELECT Region, Sales, Profit FROM sales",
            data=sample_data,
            language="English"
        )
        
        print("\nAdvanced Generation Result:")
        print(orjson.dumps(advanced_result, option=orjson.OPT_INDENT_2).decode())
        
        # Test template application
        template_result = await advanced_gen.apply_template(
            template_name="correlation",
            data=sample_data,
            field_mapping={"x_variable": "Sales", "y_variable": "Profit"}
        )
        
        print("\nTemplate Application Result:")
        print(orjson.dumps(template_result, option=orjson.OPT_INDENT_2).decode())
    
    # Run the test
    asyncio.run(test_plotly_chart_generation())