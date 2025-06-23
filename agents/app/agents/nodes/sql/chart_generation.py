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
)

from app.core.dependencies import get_llm


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
        
        ### OUTPUT FORMAT ###
        ***Important***
        ** Please donot put ```json at the beginning and end of your VEGA-LITE JSON SCHEMA. It will break the JSON parsing.**
        Please provide your chain of thought reasoning, chart type and the vega-lite schema in JSON format.
        
        {{
            "reasoning": "<REASON_TO_CHOOSE_THE_SCHEMA_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>",
            "chart_type": "line" | "multi_line" | "bar" | "pie" | "grouped_bar" | "stacked_bar" | "area" | "",
            "chart_schema": <VEGA_LITE_JSON_SCHEMA>
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
            
            # Try to parse as JSON to validate
            try:
                # First try to parse the raw result
                parsed = orjson.loads(result_str)
                return orjson.dumps(parsed).decode('utf-8')
            except orjson.JSONDecodeError:
                # If parsing fails, try to extract JSON from the text
                import re
                json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
                if json_match:
                    try:
                        parsed = orjson.loads(json_match.group())
                        return orjson.dumps(parsed).decode('utf-8')
                    except orjson.JSONDecodeError:
                        pass
                
                # If all parsing attempts fail, return a default structure
                default_result = {
                    "reasoning": result_str,
                    "chart_type": "",
                    "chart_schema": {}
                }
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
    """Main pipeline for Vega-Lite chart generation using Langchain"""
    
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
    os.environ["OPENAI_API_KEY"] = "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"
    
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
        
        # Test chart generation
        result = await generate_vega_lite_chart(
            query="Show me sales trends by region over time",
            sql="SELECT Date, Sales, Region FROM sales_data ORDER BY Date",
            data=sample_data,
            language="English",
            export_format="all"
        )
        
        print("Chart Generation Result:")
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
    
    # Run the test
    asyncio.run(test_vega_lite_chart_generation())