import asyncio
import logging
import os
from typing import Any, Dict, Literal, Optional, List

import orjson
from langchain.agents import AgentExecutor, initialize_agent, AgentType, Tool
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
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
        
        For a KPI chart:
        {{
            "reasoning": "A KPI chart is chosen to display key performance indicators and summary metrics",
            "chart_type": "kpi",
            "chart_schema": {{
                "title": "Key Performance Indicators",
                "mark": {{"type": "text"}},
                "encoding": {{
                    "text": {{"field": "Value", "type": "quantitative"}},
                    "color": {{"field": "Metric", "type": "nominal"}}
                }},
                "kpi_metadata": {{
                    "chart_type": "kpi",
                    "is_dummy": true,
                    "description": "KPI chart - templates will be created elsewhere",
                    "kpi_data": {{
                        "metrics": ["Total Sales", "Conversion Rate"],
                        "values": [1500000, 0.15],
                        "targets": [2000000, 0.20],
                        "units": ["USD", "%"]
                    }}
                }}
            }},
            "enhanced_metadata": {{
                "data_analysis": "Single or few quantitative metrics representing KPIs",
                "alternative_charts": ["text", "bar", "tick"],
                "chart_selection_reasoning": "KPI chart best displays key performance indicators and summary metrics"
            }}
        }}
        
        For no suitable chart:
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
            input_variables=["query", "sql", "sample_data", "sample_column_values", "language", "data_analysis"],
            template="""
            ### INPUT ###
            Question: {query}
            SQL: {sql}
            Sample Data: {sample_data}
            Sample Column Values: {sample_column_values}
            Language: {language}
            Data Analysis: {data_analysis}
            
            Please think step by step and select the most appropriate chart type based on the data structure and the user's question.
            """
        )
    
    def _create_agent(self) -> AgentExecutor:
        """Create and configure the Langchain agent"""
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
            
            agent = initialize_agent(
                tools=tools,
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=3,
                early_stopping_method="generate"
            )
            return agent
        except Exception as e:
            logger.error(f"Error creating enhanced agent: {e}")
            raise
    
    @observe(as_type="generation", capture_input=False)
    async def generate_chart(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_schema: bool = True
    ) -> Dict[str, Any]:
        """Generate enhanced Vega-Lite chart schema using the agent"""
        try:
            # Preprocess data with enhanced analysis
            preprocessed_data = self.data_preprocessor.run(data)
            
            # Create the prompt with enhanced data analysis
            prompt = self.user_prompt_template.format(
                query=query,
                sql=sql,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                language=language,
                data_analysis=preprocessed_data.get("data_analysis", {})
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
            
            # Add enhanced metadata if not present
            if "enhanced_metadata" not in final_result:
                final_result["enhanced_metadata"] = {
                    "data_analysis": preprocessed_data.get("data_analysis", {}),
                    "alternative_charts": preprocessed_data.get("data_analysis", {}).get("suggested_charts", []),
                    "chart_selection_reasoning": final_result.get("reasoning", "")
                }
            
            logger.info(f"Enhanced chart generation result: {final_result}")
            return final_result
            
        except Exception as e:
            logger.error(f"Error in enhanced chart generation: {e}")
            return {
                "chart_schema": {},
                "reasoning": f"Error generating chart: {str(e)}",
                "chart_type": "",
                "enhanced_metadata": {
                    "data_analysis": {},
                    "alternative_charts": [],
                    "chart_selection_reasoning": f"Error: {str(e)}"
                },
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
        export_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the enhanced chart generation pipeline"""
        
        try:
            # Update agent's vega schema
            self.agent.vega_schema = self.vega_schema
            
            # Generate chart
            result = await self.agent.generate_chart(
                query=query,
                sql=sql,
                data=data,
                language=language,
                remove_data_from_chart_schema=remove_data_from_chart_schema
            )
            
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