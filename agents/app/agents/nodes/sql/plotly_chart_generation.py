import logging
from typing import Any, Dict, Optional, List
import asyncio

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
        
        ### OUTPUT FORMAT ###
        
        Please provide your chain of thought reasoning, chart type, and the Plotly chart configuration in JSON format.
        
        {{
            "reasoning": "<REASON_TO_CHOOSE_THE_CHART_TYPE_AND_CONFIGURATION_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>",
            "chart_type": "scatter" | "line" | "bar" | "horizontal_bar" | "pie" | "histogram" | "box" | "heatmap" | "area" | "violin" | "bubble" | "sunburst" | "treemap" | "waterfall" | "funnel" | "",
            "chart_config": <PLOTLY_CHART_JSON_CONFIGURATION>
        }}
        
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
            input_variables=["query", "sql", "sample_data", "sample_column_values", "column_metadata", "language"],
            template="""
            ### INPUT ###
            Question: {query}
            SQL: {sql}
            Sample Data: {sample_data}
            Sample Column Values: {sample_column_values}
            Column Metadata: {column_metadata}
            Language: {language}
            
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
        remove_data_from_chart_config: bool = True
    ) -> Dict[str, Any]:
        """Generate Plotly chart configuration using the agent"""
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
                language=language
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
    
    async def run(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_config: bool = True,
        export_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the complete Plotly chart generation pipeline"""
        logger.info("Plotly Chart Generation pipeline is running...")
        
        try:
            # Generate chart
            result = await self.agent.generate_chart(
                query=query,
                sql=sql,
                data=data,
                language=language,
                remove_data_from_chart_config=remove_data_from_chart_config
            )
            
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