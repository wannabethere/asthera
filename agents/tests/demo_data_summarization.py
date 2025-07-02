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
from app.services.sql.sql_helper_services import SQLHelperService

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
            
            # Initialize SQL Helper Service
            self.sql_helper_service = SQLHelperService(
                pipeline_container=self.pipeline_container,
                allow_intent_classification=True,
                allow_sql_generation_reasoning=True,
                max_histories=10
            )
            
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

    async def test_data_assistance(self, query: str, project_id: str):
        """
        Test data assistance functionality
        
        Args:
            query: The user's query for data assistance
            project_id: The project ID
            
        Returns:
            Dict containing data assistance results
        """
        print(f"\nTesting Data Assistance for: {query}")
        print("="*60)
        
        try:
            result = await self.sql_helper_service.generate_data_assistance(
                query_id=f"data_assistance_{project_id}",
                query=query,
                project_id=project_id,
                configuration={
                    "language": "English",
                    "include_schema_info": True
                }
            )
            
            if result.get("success"):
                print("✅ Data assistance generated successfully!")
                data = result.get("data", {})
                
                if "assistance_type" in data:
                    print(f"   Assistance Type: {data['assistance_type']}")
                
                if "suggestions" in data:
                    print(f"   Suggestions: {len(data['suggestions'])} items")
                    for i, suggestion in enumerate(data['suggestions'][:3], 1):  # Show first 3
                        print(f"     {i}. {suggestion}")
                
                if "schema_info" in data:
                    print(f"   Schema Information: {len(data['schema_info'])} tables")
                
                if "metadata" in result:
                    print(f"   Processing Time: {result['metadata'].get('processing_time', 'Unknown')}")
                
                return {"status": "success", "data": data}
            else:
                print(f"❌ Data assistance failed: {result.get('error', 'Unknown error')}")
                return {"status": "failed", "error": result.get('error')}
                
        except Exception as e:
            print(f"❌ Error testing data assistance: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def test_sql_correction(self, query: str, sql: str, error_message: str, project_id: str):
        """
        Test SQL correction functionality
        
        Args:
            query: The user's original query
            sql: The SQL query that needs correction
            error_message: The error message from the failed SQL
            project_id: The project ID
            
        Returns:
            Dict containing SQL correction results
        """
        print(f"\nTesting SQL Correction for: {query}")
        print("="*60)
        print(f"Original SQL: {sql}")
        print(f"Error Message: {error_message}")
        
        try:
            result = await self.sql_helper_service.generate_sql_correction(
                query_id=f"sql_correction_{project_id}",
                query=query,
                sql=sql,
                error_message=error_message,
                project_id=project_id,
                configuration={
                    "language": "English",
                    "include_explanation": True
                }
            )
            
            if result.get("success"):
                print("✅ SQL correction generated successfully!")
                data = result.get("data", {})
                print("data in sql correction", data)
                # Display correction suggestions
                if "correction_suggestions" in data:
                    corrections = data["correction_suggestions"]
                    if "required_changes" in corrections:
                        print(f"   Required Changes: {len(corrections['required_changes'])} items")
                        for i, change in enumerate(corrections['required_changes'][:3], 1):  # Show first 3
                            print(f"     {i}. {change}")
                print("correction_suggestions in sql correction", data["correction_suggestions"])
                # Display combined analysis
                if "combined_analysis" in data:
                    analysis = data["combined_analysis"]
                    if "suggested_improvements" in analysis:
                        print(f"   Suggested Improvements: {len(analysis['suggested_improvements'])} items")
                        for i, improvement in enumerate(analysis['suggested_improvements'][:3], 1):  # Show first 3
                            print(f"     {i}. {improvement}")
                print("combined_analysis in sql correction", data["combined_analysis"])
                return {"status": "success", "data": data}
            else:
                print(f"❌ SQL correction failed: {result.get('error', 'Unknown error')}")
                return {"status": "failed", "error": result.get('error')}
                
        except Exception as e:
            print(f"❌ Error testing SQL correction: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def test_sql_expansion(self, query: str, sql: str, project_id: str, original_query: str, original_reasoning: str):
        """
        Test SQL expansion functionality
        
        Args:
            query: The user's original query
            sql: The SQL query to expand
            project_id: The project ID
            
        Returns:
            Dict containing SQL expansion results
        """
        print(f"\nTesting SQL Expansion for: {query}")
        print("="*60)
        print(f"Original SQL: {sql}")
        
        try:
            result = await self.sql_helper_service.generate_sql_expansion(
                query_id=f"sql_expansion_{project_id}",
                query=query,
                sql=sql,
                project_id=project_id,
                original_query=original_query,
                original_reasoning=original_reasoning,
                configuration={
                    "language": "English",
                    "include_explanation": True
                }
            )
            
            if result.get("success"):
                print("✅ SQL expansion generated successfully!")
                data = result.get("data", {})
                
                # Display expansion suggestions
                if "expansion_suggestions" in data:
                    expansions = data["expansion_suggestions"]
                    if "missing_elements" in expansions:
                        print(f"   Missing Elements: {len(expansions['missing_elements'])} items")
                        for i, element in enumerate(expansions['missing_elements'][:3], 1):  # Show first 3
                            print(f"     {i}. {element}")
                
                # Display combined analysis
                if "combined_analysis" in data:
                    analysis = data["combined_analysis"]
                    if "suggested_improvements" in analysis:
                        print(f"   Suggested Improvements: {len(analysis['suggested_improvements'])} items")
                        for i, improvement in enumerate(analysis['suggested_improvements'][:3], 1):  # Show first 3
                            print(f"     {i}. {improvement}")
                
                return {"status": "success", "data": data}
            else:
                print(f"❌ SQL expansion failed: {result.get('error', 'Unknown error')}")
                return {"status": "failed", "error": result.get('error')}
                
        except Exception as e:
            print(f"❌ Error testing SQL expansion: {str(e)}")
            return {"status": "error", "error": str(e)}

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
    test_cases1 = [
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
    """
    {

  "sql": "",

  "query": "How many trainings are assigned vs completed across different Divisions (Administration, Acme Products, Private Operations)?",

  "project_id": "cornerstone",

  "data_description": "sample"

}
 
    """

    test_cases   = [
        {
            "query": "How many trainings are assigned vs completed across different Divisions (Administration, Acme Products, Private Operations)?",
            "sql": """
               SELECT cr.division AS Division, COUNT(CASE WHEN lower(cr.transcript_status) = lower('Assigned') THEN 1 END) AS Assigned_Trainings, COUNT(CASE WHEN cr.completed_date IS NOT NULL THEN 1 END) AS Completed_Trainings FROM csod_training_records AS cr WHERE lower(cr.division) IN (lower('Administration'), lower('Acme Products'), lower('Private Operations')) GROUP BY cr.division
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



async def run_additional_tests():
    """Run additional tests for data assistance, SQL correction, and SQL expansion"""
    print("\n" + "="*80)
    print("ADDITIONAL TESTS: DATA ASSISTANCE, SQL CORRECTION, SQL EXPANSION")
    print("="*80)
    
    # Initialize demo
    demo = DataSummarizationDemo()
    await demo.initialize()
    
    # Test cases for data assistance
    data_assistance_tests = [
        {
            "query": "What tables are available for analyzing employee training data?",
            "project_id": "cornerstone"
        },
        {
            "query": "What are the columns available for performing analysis on learning objectives?",
            "project_id": "cornerstone"
        },
        {
            "query": "What metrics can I calculate from the training records?",
            "project_id": "cornerstone"
        }
    ]
    
    """
    # Test cases for SQL correction
    sql_correction_tests = [
        {
            "query": "Show me sales by region",
            "sql": "SELECT region, SUM(sales) FROM sales_table GROUP BY region",
            "error_message": "Column 'sales' does not exist. Did you mean 'sales_amount'?",
            "project_id": "cornerstone"
        },
        {
            "query": "Count employees by department",
            "sql": "SELECT department, COUNT(*) FROM employees GROUP BY dept",
            "error_message": "Column 'dept' does not exist. Did you mean 'department'?",
            "project_id": "cornerstone"
        },
        {
            "query": "Get training completion rates",
            "sql": "SELECT division, COUNT(*) FROM csod_training_records WHERE is_completed = true",
            "error_message": "Boolean value 'true' is not valid. Use 1 or '1' for true values.",
            "project_id": "cornerstone"
        },
        {
            "query": "Show me sales performance",
            "sql": "SELECT region, SUM(sales_amount) FROM sales GROUP BY region",
            "project_id": "cornerstone"
        },
        {
            "query": "Training effectiveness analysis",
            "sql": "SELECT division, COUNT(*) FROM csod_training_records WHERE is_completed = 1 GROUP BY division",
            "project_id": "cornerstone"
        }
    ]
    """
    # Test cases for SQL expansion
    sql_expansion_tests = [
        
        {
            "query": "Enhance the query to include the total employees  in each division by transcript status",
            "original_query": "What is the proportion of different Transcript Status (Assigned / Satisfied / Expired / Waived)?",
            "original_reasoning": "```markdown\n1. **Understand the Question**  \n   The user is asking for the proportion of different Transcript Status values (Assigned, Satisfied, Expired, Waived) from the training records. This means we need to analyze the data in the `csod_training_records` table to determine how many records fall into each of these categories and then calculate their proportions relative to the total number of records.\n\n2. **Identify Relevant Data**  \n   We need to focus on the `transcript_status` column in the `csod_training_records` table. This column contains the values we are interested in (Assigned, Satisfied, Expired, Waived). We will also need to count the total number of records to calculate proportions.\n\n3. **Count Each Status**  \n   We will write a SQL query to count the occurrences of each Transcript Status. This can be done using a `GROUP BY` clause on the `transcript_status` column, which will allow us to see how many records correspond to each status.\n\n4. **Calculate Total Records**  \n   In the same query or a separate one, we will calculate the total number of records in the `csod_training_records` table. This total will be used to compute the proportions of each status.\n\n5. **Compute Proportions**  \n   Once we have the counts for each status and the total number of records, we will calculate the proportion of each status by dividing the count of each status by the total number of records. This will give us the desired proportions in decimal form.\n\n6. **Format the Results**  \n   Finally, we will format the results in a clear and understandable way, possibly as a percentage, to present the proportions of each Transcript Status to the user.\n```",
            "sql": "SELECT tr.transcript_status AS Transcript_Status, COUNT(tr.transcript_status) * 1.0 / SUM(COUNT(tr.transcript_status)) OVER () AS Proportion FROM csod_training_records AS tr WHERE lower(tr.transcript_status) IN (lower('Assigned'), lower('Satisfied'), lower('Expired'), lower('Waived')) GROUP BY tr.transcript_status",
            "project_id": "cornerstone"
        }
        
    ]
    
    # Run data assistance tests
    print("\n" + "="*60)
    print("DATA ASSISTANCE TESTS")
    print("="*60)
    print("SKIPPING DATA ASSISTANCE TESTS FOR NOW")
    print("="*60)
    
    data_assistance_results = []
    for test in data_assistance_tests:
        result = await demo.test_data_assistance(
            query=test["query"],
            project_id=test["project_id"]
        )
        data_assistance_results.append({
            "test": test,
            "result": result
        })
    
    # Run SQL correction tests
    print("\n" + "="*60)
    print("SQL CORRECTION TESTS")
    print("="*60)
    
    """
    sql_correction_results = []
    for test in sql_correction_tests:
        result = await demo.test_sql_correction(
            query=test["query"],
            sql=test["sql"],
            error_message=test["error_message"],
            project_id=test["project_id"]
        )
        sql_correction_results.append({
            "test": test,
            "result": result
        })
    """
    # Run SQL expansion tests
    print("\n" + "="*60)
    print("SQL EXPANSION TESTS")
    print("="*60)
    
    sql_expansion_results = []
    for test in sql_expansion_tests:
        result = await demo.test_sql_expansion(
            query=test["query"],
            sql=test["sql"],
            project_id=test["project_id"],
            original_query=test["original_query"],
            original_reasoning=test["original_reasoning"]
        )
        sql_expansion_results.append({
            "test": test,
            "result": result
        })
    
    # Print summary
    print("\n" + "="*80)
    print("ADDITIONAL TESTS SUMMARY")
    print("="*80)
    
    # Data assistance summary
    print("\nData Assistance Tests:")
    print("SKIPPING DATA ASSISTANCE TESTS FOR NOW")
    print("="*60)
    success_count = sum(1 for r in data_assistance_results if r["result"]["status"] == "success")
    print(f"  ✅ Success: {success_count}/{len(data_assistance_results)}")
    for i, result in enumerate(data_assistance_results, 1):
        status = "✅" if result["result"]["status"] == "success" else "❌"
        print(f"    {status} Test {i}: {result['test']['query'][:50]}...")
    
    """
    # SQL correction summary
    print("\nSQL Correction Tests:")
    success_count = sum(1 for r in sql_correction_results if r["result"]["status"] == "success")
    print(f"  ✅ Success: {success_count}/{len(sql_correction_results)}")
    for i, result in enumerate(sql_correction_results, 1):
        status = "✅" if result["result"]["status"] == "success" else "❌"
        print(f"    {status} Test {i}: {result['test']['query'][:50]}...")
    """
    # SQL expansion summary
    print("\nSQL Expansion Tests:")
    success_count = sum(1 for r in sql_expansion_results if r["result"]["status"] == "success")
    print(f"  ✅ Success: {success_count}/{len(sql_expansion_results)}")
    for i, result in enumerate(sql_expansion_results, 1):
        status = "✅" if result["result"]["status"] == "success" else "❌"
        print(f"    {status} Test {i}: {result['test']['query'][:50]}...")
    
    return {
        "data_assistance": data_assistance_results,
        #"sql_correction": sql_correction_results,
        "sql_expansion": sql_expansion_results
    }

# Example usage of the enhanced DataSummarizationPipeline with chart generation
async def example_data_summarization_with_charts():
    """
    Example demonstrating how to use the DataSummarizationPipeline with multi-format chart generation
    """
    import os
    from app.core.engine import Engine
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    # Setup (you would normally get these from your application context)
    llm = get_llm()
    engine = Engine()  # Your database engine
    retrieval_helper = RetrievalHelper()  # Your retrieval helper
    
    # Create chart generation pipelines (to avoid circular dependency)
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Create the pipeline with chart generation pipelines passed as parameters
    pipeline = DataSummarizationPipeline(
        name="Enhanced Data Summarization",
        version="1.0",
        description="Data summarization with multi-format chart generation",
        llm=llm,
        engine=engine,
        retrieval_helper=retrieval_helper,
        chart_generation_pipeline=chart_generation_pipeline,
        plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
        powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
    )
    
    # Configure chart generation
    pipeline.enable_chart_generation(True)
    pipeline.set_chart_generation_batch(0)  # Use first batch for chart generation
    pipeline.set_chart_format("vega_lite")  # Set chart format
    pipeline.set_include_other_formats(True)  # Include other format conversions
    pipeline.set_use_multi_format(True)  # Use multi-format chart generation
    
    # Example configuration
    configuration = {
        "batch_size": 500,  # Smaller batches for better chart generation
        "chunk_size": 100,
        "language": "English",
        "chart_language": "English",
        "chart_format": "vega_lite",
        "include_other_formats": True,
        "use_multi_format": True
    }
    
    # Example usage
    try:
        result = await pipeline.run(
            query="Analyze sales performance trends",
            sql="SELECT date, region, sales_amount, product_category FROM sales_data ORDER BY date",
            data_description="Sales performance data across regions and product categories",
            project_id="example_project_123",
            configuration=configuration
        )
        
        print("=== Data Summarization with Multi-Format Charts Result ===")
        print(f"Executive Summary: {result['post_process']['executive_summary'][:200]}...")
        print(f"Data Overview: {result['post_process']['data_overview']}")
        
        # Check if visualization was generated
        if 'visualization' in result['post_process']:
            viz = result['post_process']['visualization']
            if 'chart_schema' in viz:
                print(f"Chart Type: {viz.get('chart_type', 'Unknown')}")
                print(f"Chart Format: {viz.get('format', 'Unknown')}")
                print(f"Chart Schema: {viz.get('chart_schema', {})}")
                print(f"Chart Reasoning: {viz.get('reasoning', '')[:100]}...")
                print(f"Batch Used: {viz.get('batch_used', 'Unknown')}")
                
                # Check for other format schemas
                if 'plotly_schema' in viz:
                    print(f"Plotly Schema Available: {list(viz['plotly_schema'].keys())}")
                if 'powerbi_schema' in viz:
                    print(f"PowerBI Schema Available: {list(viz['powerbi_schema'].keys())}")
            else:
                print(f"Chart Generation Error: {viz.get('error', 'Unknown error')}")
        else:
            print("No visualization generated")
        
        # Print metrics
        metrics = pipeline.get_metrics()
        print(f"Processing Metrics: {metrics}")
        
    except Exception as e:
        print(f"Error in example: {str(e)}")


async def example_data_summarization_with_status_callback():
    """
    Example demonstrating how to use the DataSummarizationPipeline with status callback
    """
    import os
    from app.core.engine import Engine
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    # Setup
    llm = get_llm()
    engine = Engine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Define status callback function
    def status_callback(status: str, details: Dict[str, Any]):
        """Example status callback function"""
        print(f"🔄 STATUS UPDATE: {status}")
        print(f"   Details: {details}")
        
        # You can implement different logic based on status
        if status == "fetch_data_complete":
            print(f"   ✅ Data fetch completed - {details.get('total_count', 0)} records, {details.get('total_batches', 0)} batches")
        elif status == "summarization_begin":
            print(f"   📊 Starting summarization for batch {details.get('batch_number', 0)}/{details.get('total_batches', 0)}")
        elif status == "summarization_complete":
            print(f"   ✅ Summarization completed for batch {details.get('batch_number', 0)}")
            if details.get('is_last_batch', False):
                print(f"   🎉 All batches processed!")
        elif status == "chart_generation_begin":
            print(f"   📈 Starting chart generation with format: {details.get('chart_format', 'unknown')}")
        elif status == "chart_generation_complete":
            if details.get('success', False):
                print(f"   ✅ Chart generation completed successfully")
            else:
                print(f"   ❌ Chart generation failed: {details.get('error', 'Unknown error')}")
        elif status == "chart_generation_error":
            print(f"   ❌ Chart generation error: {details.get('error', 'Unknown error')}")
    
    # Create the pipeline (without status callback in constructor)
    pipeline = DataSummarizationPipeline(
        name="Data Summarization with Status Callback",
        version="1.0",
        description="Data summarization with status updates",
        llm=llm,
        engine=engine,
        retrieval_helper=retrieval_helper,
        chart_generation_pipeline=chart_generation_pipeline,
        plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
        powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
    )
    
    # Configure pipeline
    pipeline.enable_chart_generation(True)
    pipeline.set_chart_format("vega_lite")
    
    # Example configuration
    configuration = {
        "batch_size": 100,  # Small batches to see more status updates
        "chunk_size": 50,
        "language": "English",
        "chart_language": "English"
    }
    
    print("🚀 Starting Data Summarization with Status Callback Example")
    print("=" * 60)
    
    try:
        result = await pipeline.run(
            query="Analyze customer purchase patterns",
            sql="SELECT customer_id, purchase_date, amount, product_category FROM customer_purchases ORDER BY purchase_date",
            data_description="Customer purchase data with product categories",
            project_id="status_callback_example",
            configuration=configuration,
            status_callback=status_callback  # Pass callback to run method
        )
        
        print("\n" + "=" * 60)
        print("🎯 FINAL RESULT")
        print("=" * 60)
        print(f"Executive Summary: {result['post_process']['executive_summary'][:200]}...")
        print(f"Data Overview: {result['post_process']['data_overview']}")
        
        if 'visualization' in result['post_process']:
            viz = result['post_process']['visualization']
            if 'chart_schema' in viz:
                print(f"Chart Generated: {viz.get('chart_type', 'Unknown')} ({viz.get('format', 'Unknown')})")
            else:
                print(f"Chart Generation Error: {viz.get('error', 'Unknown error')}")
        
        # Print final metrics
        metrics = pipeline.get_metrics()
        print(f"Final Metrics: {metrics}")
        
    except Exception as e:
        print(f"❌ Error in example: {str(e)}")


async def example_different_chart_formats():
    """
    Example demonstrating different chart formats
    """
    import os
    from app.core.engine import Engine
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    # Setup
    llm = get_llm()
    engine = Engine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Test different formats
    formats = ["vega_lite", "plotly", "powerbi"]
    
    for chart_format in formats:
        print(f"\n=== Testing {chart_format.upper()} Format ===")
        
        # Create pipeline with chart generation pipelines
        pipeline = DataSummarizationPipeline(
            name=f"Data Summarization - {chart_format}",
            version="1.0",
            description=f"Data summarization with {chart_format} chart generation",
            llm=llm,
            engine=engine,
            retrieval_helper=retrieval_helper,
            chart_generation_pipeline=chart_generation_pipeline,
            plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
            powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
        )
        
        # Configure for specific format
        pipeline.enable_chart_generation(True)
        pipeline.set_chart_format(chart_format)
        pipeline.set_include_other_formats(False)  # Don't include other formats for this test
        pipeline.set_use_multi_format(True)
        
        try:
            result = await pipeline.run(
                query="Show sales trends by region",
                sql="SELECT date, region, sales_amount FROM sales_data ORDER BY date",
                data_description="Sales data with regional breakdown",
                project_id=f"test_project_{chart_format}",
                configuration={
                    "batch_size": 100,
                    "chunk_size": 50,
                    "language": "English",
                    "chart_format": chart_format
                }
            )
            
            if 'visualization' in result['post_process']:
                viz = result['post_process']['visualization']
                if 'chart_schema' in viz:
                    print(f"✅ {chart_format.upper()} chart generated successfully")
                    print(f"   Chart Type: {viz.get('chart_type', 'Unknown')}")
                    print(f"   Format: {viz.get('format', 'Unknown')}")
                else:
                    print(f"❌ {chart_format.upper()} chart generation failed: {viz.get('error', 'Unknown error')}")
            else:
                print(f"❌ No {chart_format.upper()} visualization generated")
                
        except Exception as e:
            print(f"❌ Error testing {chart_format}: {str(e)}")

if __name__ == "__main__":
    # Run the main demo
    asyncio.run(run_demo())
    
    # Run the additional tests
    asyncio.run(run_additional_tests())
    
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