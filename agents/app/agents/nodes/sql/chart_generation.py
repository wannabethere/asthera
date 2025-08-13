import logging
from typing import Any, Dict, Optional, List
import asyncio
import os

import orjson
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent import AgentExecutor
from langchain.tools import Tool

from langchain.prompts import PromptTemplate


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
            input_variables=["query", "sql", "sample_data", "sample_column_values", "language"],
            template="""
            ### INPUT ###
            Question: {query}
            SQL: {sql}
            Sample Data: {sample_data}
            Sample Column Values: {sample_column_values}
            Language: {language}
            
            Please think step by step
            """
        )
    
    def _create_agent(self) -> AgentExecutor:
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
            logger.error(f"Error creating agent: {e}")
            raise
    
    async def generate_chart(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_schema: bool = True
    ) -> Dict[str, Any]:
        """Generate Vega-Lite chart schema using the agent"""
        try:
            # Preprocess data
            preprocessed_data = self.data_preprocessor.run(data)
            
            # Create the prompt
            prompt = self.user_prompt_template.format(
                query=query,
                sql=sql,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                language=language
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
    
    async def run(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_schema: bool = True,
        export_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the complete Vega-Lite chart generation pipeline"""
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
                remove_data_from_chart_schema=remove_data_from_chart_schema
            )
            print("result for vega lite chart generation pipeline", result)
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
    ) -> dict:
        """Run chart generation with original interface"""
        result = await self.pipeline.run(
            query=query,
            sql=sql,
            data=data,
            language=language,
            remove_data_from_chart_schema=remove_data_from_chart_schema
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