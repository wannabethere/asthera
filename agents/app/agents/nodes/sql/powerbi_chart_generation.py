import logging
from typing import Any, Dict, Optional, List
import asyncio

import orjson
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent import AgentExecutor
from langchain.schema import AgentAction, AgentFinish
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema import LLMResult

from app.agents.nodes.sql.utils.power_bi_chart import (
    PowerBIChartDataPreprocessor,
    PowerBIChartGenerationPostProcessor,
    PowerBIChartGenerationResults,
    powerbi_chart_generation_instructions,
    create_powerbi_data_preprocessor_tool,
    create_powerbi_chart_postprocessor_tool,
    PowerBIChartExporter,
)

logger = logging.getLogger("lexy-ai-service")


class PowerBIChartGenerationAgent:
    """Langchain agent for PowerBI chart generation"""
    
    def __init__(self, llm, **kwargs):
        self.llm = llm
        self.data_preprocessor = PowerBIChartDataPreprocessor()
        self.post_processor = PowerBIChartGenerationPostProcessor()
        self.exporter = PowerBIChartExporter()
        
        # Create tools
        self.tools = [
            create_powerbi_data_preprocessor_tool(),
            create_powerbi_chart_postprocessor_tool(),
        ]
        
        # Initialize agent
        self.agent = self._create_agent()
        
        # System prompt for PowerBI chart generation
        self.system_prompt = f"""
        ### TASK ###
        
        You are a data analyst expert at creating PowerBI visualizations! Given the user's question, SQL query, sample data, sample column values, and column metadata, you need to generate a PowerBI chart configuration in JSON format and provide the most suitable chart type.
        
        You need to analyze the data structure, understand the user's intent, and create an appropriate PowerBI chart configuration that effectively visualizes the data to answer the user's question.
        
        Additionally, provide a concise and easy-to-understand reasoning to describe why you chose this particular chart type and configuration based on the question, SQL query, sample data, and column metadata.
        
        {powerbi_chart_generation_instructions}
        
        ### OUTPUT FORMAT ###
        
        Please provide your chain of thought reasoning, chart type, and the PowerBI chart configuration in JSON format.
        
        {{
            "reasoning": "<REASON_TO_CHOOSE_THE_CHART_TYPE_AND_CONFIGURATION_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>",
            "chart_type": "columnChart" | "clusteredColumnChart" | "stackedColumnChart" | "lineChart" | "areaChart" | "pieChart" | "donutChart" | "scatterChart" | "barChart" | "clusteredBarChart" | "stackedBarChart" | "comboChart" | "",
            "chart_config": <POWERBI_CHART_JSON_CONFIGURATION>
        }}
        
        ### IMPORTANT NOTES ###
        
        - Ensure all field names in dataRoles exist in the actual data columns
        - Choose appropriate aggregation methods based on data types (Sum for sales/revenue, Count for items, Average for rates)
        - Use proper date hierarchies for time-based data (Year, Quarter, Month, Day)
        - Consider the user's question intent when selecting chart type
        - For multiple metrics, consider using clustered charts or combo charts
        - For part-to-whole relationships, use pie or donut charts
        - For trends over time, use line or area charts
        - For comparisons across categories, use column or bar charts
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
            
            Please analyze the data and user question step by step to create the most appropriate PowerBI visualization.
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
        """Generate PowerBI chart configuration using the agent"""
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
            # Create a chain for structured output using pipe operator
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Create the chain using pipe operator
            chain = (
                {"system_prompt": lambda x: self.system_prompt, "user_prompt": lambda x: x}
                | generation_prompt
                | self.llm
            )
            
            # Generate response
            result = await chain.ainvoke(prompt)
            
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


class PowerBIChartGenerationPipeline:
    """Main pipeline for PowerBI chart generation using Langchain"""
    
    def __init__(self, llm, **kwargs):
        self.agent = PowerBIChartGenerationAgent(llm, **kwargs)
        self.exporter = PowerBIChartExporter()
    
    async def run(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_config: bool = True,
        export_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the complete PowerBI chart generation pipeline"""
        logger.info("PowerBI Chart Generation pipeline is running...")
        
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
                    result["exported_json"] = self.exporter.to_powerbi_json(chart_config)
                elif export_format == "dax":
                    result["dax_measures"] = self.exporter.to_powerbi_dax_measures(chart_config)
                elif export_format == "settings":
                    result["visual_settings"] = self.exporter.to_powerbi_visual_settings(chart_config)
                elif export_format == "all":
                    result["exported_json"] = self.exporter.to_powerbi_json(chart_config)
                    result["dax_measures"] = self.exporter.to_powerbi_dax_measures(chart_config)
                    result["visual_settings"] = self.exporter.to_powerbi_visual_settings(chart_config)
            
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


# Factory function to create the pipeline
def create_powerbi_chart_generation_pipeline(llm, **kwargs) -> PowerBIChartGenerationPipeline:
    """Factory function to create PowerBI chart generation pipeline"""
    return PowerBIChartGenerationPipeline(llm, **kwargs)


# Utility functions for integration
async def generate_powerbi_chart(
    llm,
    query: str,
    sql: str,
    data: Dict[str, Any],
    language: str = "English",
    export_format: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to generate PowerBI chart"""
    pipeline = create_powerbi_chart_generation_pipeline(llm)
    return await pipeline.run(
        query=query,
        sql=sql,
        data=data,
        language=language,
        export_format=export_format
    )


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    from langchain.llms import OpenAI
    
    # Example usage
    async def test_powerbi_chart_generation():
        # Initialize LLM (replace with your preferred LLM)
        from app.core.dependencies import get_llm
        llm = get_llm()
        
        # Sample data
        sample_data = {
            "columns": ["Region", "Sales", "Date"],
            "data": [
                ["North", 100000, "2023-01-01"],
                ["South", 150000, "2023-01-01"],
                ["East", 120000, "2023-01-01"],
                ["West", 180000, "2023-01-01"]
            ]
        }
        
        # Test chart generation
        result = await generate_powerbi_chart(
            llm=llm,
            query="Show me sales by region",
            sql="SELECT Region, SUM(Sales) as Sales FROM sales_data GROUP BY Region",
            data=sample_data,
            language="English",
            export_format="all"
        )
        
        print("Chart Generation Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
        
        # Test individual components
        pipeline = create_powerbi_chart_generation_pipeline(llm)
        
        # Test data preprocessing
        preprocessor = PowerBIChartDataPreprocessor()
        preprocessed = preprocessor.run(sample_data)
        print("\nPreprocessed Data:")
        print(orjson.dumps(preprocessed, option=orjson.OPT_INDENT_2).decode())
        
        # Test export functionality
        exporter = PowerBIChartExporter()
        if result.get("success", False):
            chart_config = result.get("chart_config", {})
            
            print("\nExported JSON:")
            print(exporter.to_powerbi_json(chart_config))
            
            print("\nDAX Measures:")
            print(exporter.to_powerbi_dax_measures(chart_config))
            
            print("\nVisual Settings:")
            print(orjson.dumps(exporter.to_powerbi_visual_settings(chart_config), option=orjson.OPT_INDENT_2).decode())
    
    # Run the test
    asyncio.run(test_powerbi_chart_generation())