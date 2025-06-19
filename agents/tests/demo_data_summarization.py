import asyncio
import logging
from typing import Dict, Optional
import json

from app.agents.pipelines.pipeline_container import PipelineContainer
from app.agents.pipelines.sql_execution import DataSummarizationPipeline
from app.core.dependencies import get_llm
from app.core.engine import Engine
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine_provider import EngineProvider
from app.agents.nodes.sql.chart_generation import create_chart_generation_pipeline
from app.agents.nodes.sql.plotly_chart_generation import create_plotly_chart_generation_pipeline
from app.agents.nodes.sql.powerbi_chart_generation import create_powerbi_chart_generation_pipeline

# Configure logging
logging.getLogger("app.storage.documents").setLevel(logging.WARNING)
logging.getLogger("agents.app.storage.documents").setLevel(logging.WARNING)

logger = logging.getLogger("lexy-ai-service")

class DataSummarizationDemo:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataSummarizationDemo, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Initialize pipeline container
            self.pipeline_container = PipelineContainer.initialize()
            
            # Create chart generation pipelines (to avoid circular dependency)
            self.chart_generation_pipeline = create_chart_generation_pipeline()
            self.plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline(llm=get_llm())
            self.powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline(llm=get_llm())
            
            # Initialize the data summarization pipeline with chart generation pipelines
            self.data_summarization_pipeline = DataSummarizationPipeline(
                name="data_summarization",
                version="1.0",
                description="Pipeline for generating data summaries using recursive summarization",
                llm=get_llm(),
                engine=EngineProvider.get_engine(),
                retrieval_helper=RetrievalHelper(),
                chart_generation_pipeline=self.chart_generation_pipeline,
                plotly_chart_generation_pipeline=self.plotly_chart_generation_pipeline,
                powerbi_chart_generation_pipeline=self.powerbi_chart_generation_pipeline
            )
            
            # Configure chart generation
            self.data_summarization_pipeline.enable_chart_generation(True)
            self.data_summarization_pipeline.set_chart_generation_batch(0)  # Use first batch
            self.data_summarization_pipeline.set_chart_format("vega_lite")  # Set primary format
            self.data_summarization_pipeline.set_include_other_formats(True)  # Include other formats
            self.data_summarization_pipeline.set_use_multi_format(True)  # Use multi-format generation
            
            self._initialized = True

    async def initialize(self):
        """Async initialization if needed"""
        if not hasattr(self, '_async_initialized'):
            # Initialize the pipeline asynchronously
            await self.data_summarization_pipeline.initialize()
            self._async_initialized = True

    async def process_data_summarization(
        self,
        query: str,
        sql: str,
        data_description: str,
        project_id: str,
        configuration: Optional[Dict] = None
    ) -> Dict:
        """
        Process data summarization request and return the summary.
        
        Args:
            query: The user's query about the data
            sql: The SQL query to execute
            data_description: Description of the data being summarized
            project_id: The project ID
            configuration: Optional configuration for summarization
            
        Returns:
            Dict containing the summary and metadata
        """
        try:
            # Merge default configuration with provided configuration
            default_config = {
                "chunk_size": 150,
                "language": "English",
                "batch_size": 1000,
                "enable_chart_generation": True,
                "chart_batch_index": 0,
                "chart_language": "English",
                "chart_format": "vega_lite",
                "include_other_formats": True,
                "use_multi_format": True
            }
            
            if configuration:
                default_config.update(configuration)
            
            # Run the data summarization pipeline
            result = await self.data_summarization_pipeline.run(
                query=query,
                sql=sql,
                data_description=data_description,
                project_id=project_id,
                configuration=default_config
            )
            
            return {
                "summary": result,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error in data summarization demo: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def test_chart_formats(self, query: str, sql: str, data_description: str, project_id: str):
        """
        Test different chart formats with the same data
        
        Args:
            query: The user's query about the data
            sql: The SQL query to execute
            data_description: Description of the data being summarized
            project_id: The project ID
            
        Returns:
            Dict containing results for each format
        """
        formats = ["vega_lite", "plotly", "powerbi"]
        results = {}
        
        print(f"\nTesting Chart Formats for: {query}")
        print("="*60)
        
        for chart_format in formats:
            print(f"\n--- Testing {chart_format.upper()} Format ---")
            
            # Set chart format
            self.data_summarization_pipeline.set_chart_format(chart_format)
            self.data_summarization_pipeline.set_include_other_formats(False)  # Don't include other formats for this test
            
            try:
                result = await self.process_data_summarization(
                    query=query,
                    sql=sql,
                    data_description=data_description,
                    project_id=f"{project_id}_{chart_format}",
                    configuration={
                        "chunk_size": 150,
                        "language": "English",
                        "batch_size": 1000,
                        "chart_format": chart_format,
                        "include_other_formats": False
                    }
                )
                
                if result["status"] == "success":
                    viz = result["summary"].get("post_process", {}).get("visualization", {})
                    if 'chart_schema' in viz:
                        print(f"✅ {chart_format.upper()} chart generated successfully!")
                        print(f"   Chart Type: {viz.get('chart_type', 'Unknown')}")
                        print(f"   Format: {viz.get('format', 'Unknown')}")
                        results[chart_format] = "success"
                    else:
                        print(f"❌ {chart_format.upper()} chart generation failed: {viz.get('error', 'Unknown error')}")
                        results[chart_format] = "failed"
                else:
                    print(f"❌ {chart_format.upper()} processing failed: {result.get('error', 'Unknown error')}")
                    results[chart_format] = "failed"
                    
            except Exception as e:
                print(f"❌ Error testing {chart_format}: {str(e)}")
                results[chart_format] = "error"
        
        return results

"""
,
        {
            "query": "Analyze the monthly sales trends",
            "sql":
                SELECT 
                    DATE_TRUNC('month', sale_date) as month,
                    COUNT(s.id) as total_sales,
                    SUM(s.quantity) as total_quantity,
                    AVG(s.quantity) as avg_quantity
                FROM sales s
                GROUP BY DATE_TRUNC('month', sale_date)
                ORDER BY month
         
            "data_description": "Monthly sales trends showing total sales count, total quantity sold, and average quantity per sale",
            "event_id": "demo_event_2"
        }
"""

async def run_demo():
    """Run a demo of the data summarization system with multiple test cases"""
    # Sample SQL queries for testing
    test_cases = [
        {
            "query": "Show me the training completion rates by division, including how many assignments were completed on time versus late",
            "sql": """
               SELECT cr.division AS Division, COUNT(*) AS Total_Assignments, COUNT(CASE WHEN cr.is_completed THEN 1 END) AS Completed_Assignments, 
               COUNT(CASE WHEN cr.is_completed AND cr.completed_date <= cr.assigned_date THEN 1 END) AS On_Time_Completions, 
               COUNT(CASE WHEN cr.is_completed AND cr.completed_date > cr.assigned_date THEN 1 END) AS Late_Completions 
               FROM csod_training_records AS cr GROUP BY cr.division
            """,
            "data_description": "Corner stone data learning management data for coaching and training",
            "event_id": "demo_event_1",
            "chart_format": "vega_lite"
        }
    ]
    
    # Initialize demo
    demo = DataSummarizationDemo()
    await demo.initialize()
    
    # Process each test case
    for test_case in test_cases:
        print("\n" + "="*50)
        print(f"\nTest Case: {test_case['event_id']}")
        print(f"Query: {test_case['query']}")
        print(f"SQL: {test_case['sql']}")
        print(f"Chart Format: {test_case.get('chart_format', 'vega_lite')}")
        
        # Set chart format for this test case
        demo.data_summarization_pipeline.set_chart_format(test_case.get('chart_format', 'vega_lite'))
        
        # Process the summarization request
        result = await demo.process_data_summarization(
            query=test_case['query'],
            sql=test_case['sql'],
            data_description=test_case['data_description'],
            project_id="demo_project",
            configuration={
                "chunk_size": 150,
                "language": "English",
                "batch_size": 1000,
                "chart_format": test_case.get('chart_format', 'vega_lite'),
                "include_other_formats": True
            }
        )
        
        # Print results
        if result["status"] == "success":
            print("\nSummary Results:")
            if isinstance(result["summary"], dict):
                if "post_process" in result["summary"]:
                    post_process = result["summary"]["post_process"]
                    
                    if "executive_summary" in post_process:
                        print("\nExecutive Summary:")
                        print(post_process["executive_summary"])
                    
                    if "data_overview" in post_process:
                        print("\nData Overview:")
                        print(json.dumps(post_process["data_overview"], indent=2))
                    
                    # Display chart generation results
                    if "visualization" in post_process:
                        viz = post_process["visualization"]
                        print(f"\nChart Generation Results: {viz}")
                        print(f"Chart Type: {viz.get('chart_type', 'Unknown')}")
                        print(f"Chart Format: {viz.get('format', 'Unknown')}")
                        print(f"Batch Used: {viz.get('batch_used', 'Unknown')}")
                        
                        if 'chart_schema' in viz:
                            print("✅ Chart generated successfully!")
                            print(f"Chart Schema Keys: {list(viz.get('chart_schema', {}).keys())}")
                            
                            # Show reasoning if available
                            if 'reasoning' in viz:
                                print(f"Chart Reasoning: {viz.get('reasoning', '')[:200]}...")
                            
                            # Show other format schemas if available
                            if 'plotly_schema' in viz:
                                print("✅ Plotly schema available")
                                print(f"   Plotly Schema Keys: {list(viz['plotly_schema'].keys())}")
                            
                            if 'powerbi_schema' in viz:
                                print("✅ PowerBI schema available")
                                print(f"   PowerBI Schema Keys: {list(viz['powerbi_schema'].keys())}")
                            
                            if 'vega_lite_schema' in viz:
                                print("✅ Vega-Lite schema available")
                                print(f"   Vega-Lite Schema Keys: {list(viz['vega_lite_schema'].keys())}")
                        else:
                            print(f"❌ Chart generation failed: {viz.get('error', 'Unknown error')}")
                    else:
                        print("❌ No visualization generated")
                    
                    if "metadata" in result["summary"]:
                        print("\nProcessing Stats:")
                        print(json.dumps(result["summary"]["metadata"], indent=2))
                else:
                    print(result["summary"])
            else:
                print(result["summary"])
        else:
            print(f"\nError: {result['error']}")
        
        print("\n" + "="*50)

if __name__ == "__main__":
    # Run the demo
    asyncio.run(run_demo())
    
    # Additional chart format testing
    async def run_chart_format_testing():
        """Run additional chart format testing"""
        print("\n" + "="*80)
        print("ADDITIONAL CHART FORMAT TESTING")
        print("="*80)
        
        demo = DataSummarizationDemo()
        await demo.initialize()
        
        # Test chart formats with a simple query
        test_query = "Show sales performance by region"
        test_sql = """
            SELECT 
                region,
                SUM(sales_amount) as total_sales,
                COUNT(*) as number_of_transactions
            FROM sales_data
            GROUP BY region
            ORDER BY total_sales DESC
        """
        test_description = "Regional sales performance data"
        
        results = await demo.test_chart_formats(
            query=test_query,
            sql=test_sql,
            data_description=test_description,
            project_id="chart_format_test"
        )
        
        # Print summary
        print("\n" + "="*60)
        print("CHART FORMAT TESTING SUMMARY")
        print("="*60)
        for format_name, result in results.items():
            status_icon = "✅" if result == "success" else "❌"
            print(f"{status_icon} {format_name.upper()}: {result}")
        
        # Test with all formats included
        print("\n" + "="*60)
        print("TESTING WITH ALL FORMATS INCLUDED")
        print("="*60)
        
        demo.data_summarization_pipeline.set_chart_format("vega_lite")
        demo.data_summarization_pipeline.set_include_other_formats(True)
        
        all_formats_result = await demo.process_data_summarization(
            query=test_query,
            sql=test_sql,
            data_description=test_description,
            project_id="all_formats_test",
            configuration={
                "chunk_size": 150,
                "language": "English",
                "batch_size": 1000,
                "chart_format": "vega_lite",
                "include_other_formats": True
            }
        )
        
        if all_formats_result["status"] == "success":
            viz = all_formats_result["summary"].get("post_process", {}).get("visualization", {})
            print(f"Primary Format: {viz.get('format', 'Unknown')}")
            print(f"Chart Type: {viz.get('chart_type', 'Unknown')}")
            
            format_count = 0
            if 'chart_schema' in viz:
                format_count += 1
            if 'plotly_schema' in viz:
                format_count += 1
                print("✅ Plotly schema included")
            if 'powerbi_schema' in viz:
                format_count += 1
                print("✅ PowerBI schema included")
            if 'vega_lite_schema' in viz:
                format_count += 1
                print("✅ Vega-Lite schema included")
            
            print(f"Total formats available: {format_count}")
        else:
            print(f"❌ All formats test failed: {all_formats_result.get('error', 'Unknown error')}")
    
    # Run the additional testing
    #asyncio.run(run_chart_format_testing()) 