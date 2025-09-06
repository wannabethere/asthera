import pandas as pd
import asyncio
import os
import numpy as np
from datetime import datetime, timedelta
import chromadb
from langchain_openai import ChatOpenAI
from app.storage.documents import DocumentChromaStore, create_langchain_doc_util
from app.core.settings import get_settings
from app.agents.nodes.mlagents.funnelanalysis_node import FunnelAnalysisAgent,retrieve_function_definition, retrieve_function_examples
from app.agents.nodes.mlagents.selfrag_mltool_pipeline import SelfCorrectingForwardPlanner
from app.agents.nodes.recommenders.ds_agents import SummarizeDatasetAgent
from app.agents.models.dsmodels import InsightManagerState
from app.agents.nodes.mlagents.analysis_intent_classification import AnalysisIntentPlanner
from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper

settings = get_settings()
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH

# Output configuration
OUTPUT_CONFIG = {
    "save_to_json": True,           # Save results to JSON files
    "save_individual_files": True,   # Save individual analysis files
    "output_directory": "analysis_results",  # Directory to save files
    "include_timestamp": True,       # Include timestamp in filenames
    "create_summary": True,          # Create summary text file
    "console_output": True,          # Also show results in console
    "file_encoding": "utf-8",       # File encoding for output files
    "extract_generated_code": True,  # Extract generated code to Python files
    "code_output_directory": "generated_code"  # Directory for generated Python code
}

os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
 # Initialize ChromaDB client and collections
client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_examples_collection")
functions_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_spec_collection")
insights_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_insights_collection")
usage_examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="usage_examples_collection")

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
retrieval_helper = RetrievalHelper()

self_correcting_pipeline_code_generator = SelfCorrectingPipelineCodeGenerator(
                llm=llm,
                usage_examples_store=usage_examples_vectorstore,
                code_examples_store=examples_vectorstore,
                function_definition_store=functions_vectorstore
            )
# Initialize the intent planner
planner = AnalysisIntentPlanner(
    llm=llm,
    function_collection=functions_vectorstore,
    example_collection=examples_vectorstore, 
    insights_collection=insights_vectorstore
)

def analyze_question_with_intent_classification(
    question: str,
    dataframe: pd.DataFrame,
    dataframe_description: str = None,
    dataframe_summary: str = None,
    columns_description: dict = None,
    enable_code_generation: bool = False,
    context: str = None,
    dataframe_name: str = "Dataset"
):
    """
    Analyze a question using intent classification with optional code generation.
    
    Args:
        question (str): The question to analyze
        dataframe (pd.DataFrame): The dataframe to analyze
        dataframe_description (str, optional): Description of the dataframe
        dataframe_summary (str, optional): Summary of the dataframe
        columns_description (dict, optional): Description of each column
        enable_code_generation (bool): Whether to generate code for the analysis
        context (str, optional): Additional context for code generation
        dataframe_name (str): Name of the dataframe for code generation
    
    Returns:
        dict: Analysis results including intent classification and optionally generated code
    """
    print(f"\n{'='*60}")
    print(f"Analyzing Question: {question}")
    print(f"{'='*60}")
    
     # Initialize function retrieval
    retrieval = FunctionRetrieval(llm=llm,function_library_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/all_pipes_functions.json")
    result = asyncio.run(retrieval.retrieve_relevant_functions(question,dataframe_description,dataframe_summary,columns_description))
    print("Retrieval functions result",result)
    
    
    
    # If dataframe description/summary not provided, generate them
    if dataframe_description is None or dataframe_summary is None:
        summarize_agent = SummarizeDatasetAgent()
        state = InsightManagerState(
            question=question,
            context="Data analysis request",
            goal="Generate insights from the dataset",
            dataset_path=""
        )
        dataframe_summary = summarize_agent.summarize_dataframe(
            dataframe=dataframe, 
            question=question, 
            state=state
        )
        dataframe_description = dataframe_description or "Dataset for analysis"
    
    # Classify intent
    print("Classifying intent...")
    result = asyncio.run(planner.classify_intent(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=dataframe.columns.tolist()
    ))
    
    # Print intent classification results
    print(f"\nIntent Classification Results:")
    print(f"  Feasibility Score: {result.feasibility_score}")
    print(f"  Can be answered: {result.can_be_answered}")
    print(f"  Missing columns: {result.missing_columns}")
    print(f"  Available alternatives: {result.available_alternatives}")
    print(f"  Data suggestions: {result.data_suggestions}")
    print(f"  Suggested functions: {result.suggested_functions}")
    print(f"  Required data columns: {result.required_data_columns}")
    print(f"  Reasoning plan: {result.reasoning_plan}")
    
    # Print enhanced metadata if available
    if result.reasoning_plan and isinstance(result.reasoning_plan, list):
        print(f"\nEnhanced Metadata Analysis:")
        for i, step in enumerate(result.reasoning_plan):
            if isinstance(step, dict):
                print(f"  Step {i+1}: {step.get('step_title', 'Unknown')}")
                
                # Column mapping
                if step.get('column_mapping'):
                    print(f"    Column Mapping: {step.get('column_mapping')}")
                
                # Input/Output columns
                if step.get('input_columns'):
                    print(f"    Input Columns: {step.get('input_columns')}")
                if step.get('output_columns'):
                    print(f"    Output Columns: {step.get('output_columns')}")
                
                # Pipeline info
                if step.get('pipeline_type'):
                    print(f"    Pipeline Type: {step.get('pipeline_type')}")
                if step.get('function_category'):
                    print(f"    Function Category: {step.get('function_category')}")
                
                # Dependencies and data flow
                if step.get('step_dependencies'):
                    print(f"    Dependencies: Step {step.get('step_dependencies')}")
                if step.get('data_flow'):
                    print(f"    Data Flow: {step.get('data_flow')}")
                
                # Constraints and error handling
                if step.get('parameter_constraints'):
                    print(f"    Parameter Constraints: {step.get('parameter_constraints')}")
                if step.get('error_handling'):
                    print(f"    Error Handling: {step.get('error_handling')}")
                
                # Embedded function details
                if step.get('embedded_function_parameter') and step.get('embedded_function_details'):
                    embedded_details = step.get('embedded_function_details', {})
                    print(f"    Embedded Function: {embedded_details.get('embedded_function', '')} in {embedded_details.get('embedded_pipe', '')}")
                    if step.get('embedded_function_columns'):
                        print(f"    Embedded Function Columns: {step.get('embedded_function_columns')}")

    
    analysis_results = {
        "question": question,
        "intent_classification": result,
        "dataframe_info": {
            "shape": dataframe.shape,
            "columns": dataframe.columns.tolist(),
            "summary": dataframe_summary
        }
    }
    
    # Generate code if requested
    if enable_code_generation and result.can_be_answered:
        print("\nGenerating code...")
        try:
            code_context = context or question
            
            # Debug: Print the types and values of parameters
            print(f"Debug - suggested_functions type: {type(result.suggested_functions)}")
            print(f"Debug - suggested_functions value: {result.suggested_functions}")
            print(f"Debug - required_data_columns type: {type(result.required_data_columns)}")
            print(f"Debug - required_data_columns value: {result.required_data_columns}")
            
            # Ensure suggested_functions is a list and extract function names from formatted strings
            raw_functions = result.suggested_functions if isinstance(result.suggested_functions, list) else [result.suggested_functions]
            
            # Extract function names from formatted strings (remove category and pipeline info)
            function_names = []
            for func in raw_functions:
                if ': ' in func:
                    # Extract function name from 'function_name: category (pipeline)' format
                    function_name = func.split(': ')[0]
                    function_names.append(function_name)
                else:
                    # Keep original if not formatted
                    function_names.append(func)
            
            # Additional debugging for the classification object
            print(f"Debug - classification type: {type(result)}")
            print(f"Debug - classification attributes: {dir(result)}")
            
            try:
                # Create enhanced columns description with metadata from reasoning plan
                enhanced_columns_description = columns_description or {}
                if result.reasoning_plan and isinstance(result.reasoning_plan, list):
                    # Add enhanced metadata to columns description
                    enhanced_columns_description['_enhanced_metadata'] = {
                        'reasoning_plan_steps': len(result.reasoning_plan),
                        'has_enhanced_metadata': any(
                            step.get('column_mapping') or step.get('input_columns') or step.get('output_columns')
                            for step in result.reasoning_plan if isinstance(step, dict)
                        ),
                        'pipeline_types': list(set(
                            step.get('pipeline_type') for step in result.reasoning_plan 
                            if isinstance(step, dict) and step.get('pipeline_type')
                        )),
                        'function_categories': list(set(
                            step.get('function_category') for step in result.reasoning_plan 
                            if isinstance(step, dict) and step.get('function_category')
                        ))
                    }
                
                code_result = asyncio.run(self_correcting_pipeline_code_generator.generate_pipeline_code(
                    context=code_context,
                    function_name=function_names,
                    function_inputs=result.required_data_columns,
                    dataframe_name=dataframe_name,
                    classification=result,
                    dataset_description=dataframe_summary,
                    columns_description=enhanced_columns_description
                ))
            except Exception as code_gen_error:
                print(f"Detailed error in code generation: {str(code_gen_error)}")
                print(f"Error type: {type(code_gen_error)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                raise code_gen_error
            
            analysis_results["generated_code"] = code_result
            print("code_result",analysis_results["generated_code"])
            print(f"Code generation completed successfully!")
            
        except Exception as e:
            print(f"Error during code generation: {str(e)}")
            analysis_results["code_generation_error"] = str(e)
    
    elif enable_code_generation and not result.can_be_answered:
        print("\nSkipping code generation - question cannot be answered with available data")
        analysis_results["code_generation_skipped"] = "Question cannot be answered with available data"
    
    print(f"\n{'='*60}")
    return analysis_results

# Example usage of the FunnelAnalysisAgent
def main():
    print("Funnel Analysis Agent Example Usage")
    print("===================================")
    
    """
    # Step 1: Create sample data
    print("\nCreating sample event data...")
    events_df = create_sample_event_data()
    print(f"Created dataset with {len(events_df)} events from {events_df['user_id'].nunique()} users")
    print(events_df.head())
    
    # Print distribution of events
    event_counts = events_df['event_name'].value_counts()
    print("\nEvent distribution:")
    for event, count in event_counts.items():
        print(f"  {event}: {count} events")
    
    # Print distribution of segments
    segment_counts = events_df['user_segment'].value_counts()
    print("\nSegment distribution:")
    for segment, count in segment_counts.items():
        print(f"  {segment}: {count} events from {events_df[events_df['user_segment'] == segment]['user_id'].nunique()} users")
    """
    po_df = pd.read_csv("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/ai-report/app/bv_finance_flux_final.csv")
    # Step 2: Initialize the agent
    print("\nInitializing Funnel Analysis Agent...")
   
   
    summarize_agent = SummarizeDatasetAgent()
    state = InsightManagerState(
            question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            context="Objective - to capture segments of user behavior based on the user actions of views, purchases, add to cart, start checkout",
            goal="I want to generate a dashboard to analyze funnel performance across different user segments with my event data",
            dataset_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/ai-report/app/bv_finance_flux_final.csv",
        )
    agent = FunnelAnalysisAgent(llm,functions_vectorstore,examples_vectorstore,insights_vectorstore)
    dataframe_description = {}
    dataframe_summary = summarize_agent.summarize_dataframe(dataframe=po_df, question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?", state=state)    
    dataframe_description['summary'] = dataframe_summary
    #dataframe_description['stats'] = events_df.describe().to_dict()
    print("dataframe_description",dataframe_description)
    
    # Step 3: Define a query
    query = "How do I analyze funnel performance across different user segments with my event data based on the user actions of views, purchases, add to cart, checkout?"
    print(f"\nUser Query: '{query}'")
    
    # Step 4: Run the agent to generate code
    print("\nGenerating code with the agent...")
    #response = agent.run(query,dataframe_description=dataframe_description,dataframe_columns=events_df.columns.tolist())
    #for key, value in response.items():
    #    print(f"{key}: {value} \n  \n")
    
    # query 2
    query = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
    print(f"\nUser Query: '{query}'")
    
    print(po_df.head())
    state = InsightManagerState(
            question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            context="Objective - to capture Variance of flux over time for each group of projects, cost centers, and departments",
            goal="I want to generate a dashboard to analyze flux analysis performance across different segments with my po data when it drops more than 10%",
            dataset_path="/Users/sameerm/self-learn-agents/data/inputs/bv_finance_flux_final.csv",
    )
    dataframe_summary = summarize_agent.summarize_dataframe(dataframe=po_df, question=query, state=state)    
    dataframe_description['summary'] = dataframe_summary
    print(dataframe_description)
    columns_description = {
        "Date": "Transaction date in YYYY-MM-DD format, indicating when the financial transaction occurred",
        "Region": "Geographic region or country where the transaction took place (e.g., France, Germany, United Kingdom, United Arab Emirates)",
        "Cost center": "Organizational cost center identifier, typically 'Center A' in this dataset, representing the department or unit responsible for the cost",
        "Project": "Project identifier or project number, can be numeric (e.g., 10.0, 20.0) or empty, indicating which project the transaction is associated with",
        "Account": "Account number or identifier, appears to be consistently '2' in this dataset, representing the general ledger account",
        "Source": "Source system or module that generated the transaction (e.g., PROJECT ACCOUNTING, PAYABLES, REVALUATION, SPREADSHEET)",
        "Category": "Transaction category or type (e.g., MISCELLANEOUS_COST, PURCHASE INVOICES, ACCRUAL - AUTOREVERSE, REVALUE PROFIT/LOSS)",
        "Event Type": "Specific event or action type (e.g., MISC_COST_DIST, INVOICE VALIDATED, INVOICE CANCELLED, CREDIT MEMO VALIDATED, MISC_COST_DIST_ADJ)",
        "PO No": "Purchase Order number identifier, format like 'NEW_PO_XXXX' where XXXX is a numeric identifier",
        "Transactional value": "Original transaction amount in the transaction currency, can be positive or negative values representing debits and credits",
        "Functional value": "Transaction amount converted to the functional currency (typically the reporting currency), accounting for exchange rate differences",
        "PO with Line item": "Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking",
        "Forecasted value": "Forecasted transaction amount in the transaction currency, can be positive or negative values representing debits and credits",
        "Forecasted functional value": "Forecasted transaction amount converted to the functional currency (typically the reporting currency), accounting for exchange rate differences",
        "Forecasted PO with Line item": "Forecasted Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking",
        "Forecasted PO with Line item": "Forecasted Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking"
    } 
    
    # Example usage of the new function
    print("\n" + "="*80)
    print("EXAMPLE USAGE OF NEW FUNCTION")
    print("="*80)
    
    # Example 1: Intent classification only
    print("\n1. Intent classification only:")
    
    result1 = analyze_question_with_intent_classification(
        question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
        dataframe=po_df,
        dataframe_description="Financial flux data with project, cost center, and department information",
        dataframe_summary="Dataset contains flux values over time with grouping dimensions",
        enable_code_generation=True,
        context="Analyze the flux values over time for each group of projects, cost centers, and departments for making better decisions of investment",
        dataframe_name="Purchase Orders Data"
    )
    
    
    
    # Example 2: Intent classification with code generation
    print("\n2. Intent classification with code generation:")
    result2 = analyze_question_with_intent_classification(
        question="Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns week by week by region and project",
        dataframe=po_df,
        dataframe_description="Financial flux data with project, cost center, and department information",
        dataframe_summary="Dataset contains flux values over time with grouping dimensions",
        columns_description=columns_description,
        enable_code_generation=True,
        context="Find anomalies in daily spending patterns",
        dataframe_name="Purchase Orders Data"
    )
    
    # Example 3: Another question with code generation
    print("\n3. Another question with code generation:")
    result3 = analyze_question_with_intent_classification(
        question="What are the mean, average daily transactional values for purchase orders by region and project",
        dataframe=po_df,
        dataframe_description="Financial flux data with project, cost center, and department information",
        dataframe_summary="Dataset contains flux values over time with grouping dimensions",
        columns_description=columns_description,
        enable_code_generation=True,
        context="Calculate mean daily transactional values",
        dataframe_name="Purchase Orders Data"
    )

    # Example 3: Another question with code generation
    print("\n4. Another question with code generation:")
    result4= analyze_question_with_intent_classification(
        question="What are the daily trends of transactional values, forecasted values, and forecasted PO with line item for purchase orders by region and project",
        dataframe=po_df,
        dataframe_description="Financial flux data with project, cost center, and department information",
        dataframe_summary="Dataset contains flux values over time with grouping dimensions",
        columns_description=columns_description,
        enable_code_generation=True,
        context="Calculate mean daily transactional values",
        dataframe_name="Purchase Orders Data"
    )

    # Example 5: Another question with code generation
    print("\n5. Another question with code generation:")
    result5= analyze_question_with_intent_classification(
        question="What is the distribution of the mean daily transactional values for each type of source by region and project daily?",
        dataframe=po_df,
        dataframe_description="Financial flux data with project, cost center, and department information",
        dataframe_summary="Dataset contains flux values over time with grouping dimensions",
        columns_description=columns_description,
        enable_code_generation=True,
        context="Calculate mean daily transactional values",
        dataframe_name="Purchase Orders Data"
    )

     # Example 6: Another question with code generation
    print("\n6. Another question with code generation:")
    result6= analyze_question_with_intent_classification(
        question="Perform rolling 5 day mean transactiona values, forecasted values. Using those perform flux analysis by calculating the variance for the mean transactional values, forecasted values by region,cost center, and project ",
        dataframe=po_df,
        dataframe_description="Financial flux data with project, cost center, and department information",
        dataframe_summary="Dataset contains flux values over time with grouping dimensions",
        columns_description=columns_description,
        enable_code_generation=True,
        context="Calculate mean daily transactional values",
        dataframe_name="Purchase Orders Data"
    )
   
   
    import json
    
    def convert_analysis_intent_result(obj):
        """Recursively convert AnalysisIntentResult objects to dictionaries"""
        if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
            # This is an AnalysisIntentResult or similar Pydantic model
            return obj.dict()
        elif isinstance(obj, dict):
            # Recursively process dictionary values
            return {key: convert_analysis_intent_result(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            # Recursively process list items
            return [convert_analysis_intent_result(item) for item in obj]
        else:
            # Return as is for other types
            return obj
    
    print("="*80)
    
    # Prepare results for JSON file output
    results_data = {
        "analysis_results": {
            "rolling_variance_analysis": {
                "question": "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
                "result": convert_analysis_intent_result(result1)
            },
            "anomaly_detection": {
                "question": "Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns by region and project",
                "result": convert_analysis_intent_result(result2)
            },
            "mean_transactional_values": {
                "question": "What are the mean, average daily transactional values for purchase orders by region and project",
                "result": convert_analysis_intent_result(result3)
            },
            "daily_trends_forecast": {
                "question": "What are the daily trends of transactional values, forecasted values, and forecasted PO with line item for purchase orders by region and project",
                "result": convert_analysis_intent_result(result4)
            },
            "distribution_analysis": {
                "question": "What is the distribution of the transactional values for each type of source by region and project daily?",
                "result": convert_analysis_intent_result(result5)
            },
            "flux_analysis": {
                "question": "Perform 5 day rolling flux analysis for the data, with mean daily transactional values, forecasted values with line item by region and project",
                "result": convert_analysis_intent_result(result6)
            }
        },
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_analyses": 6,
            "analysis_type": "funnel_analysis_tool_usage"
        }
    }
    
    # Initialize output variables
    output_dir = OUTPUT_CONFIG["output_directory"]
    output_filename = ""
    summary_filename = ""
    
    # Handle output based on configuration
    if OUTPUT_CONFIG["save_to_json"]:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate timestamp if needed
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') if OUTPUT_CONFIG["include_timestamp"] else ""
        
        # Save main results file
        main_filename = f"funnel_analysis_results{'_' + timestamp if timestamp else ''}.json"
        output_filename = os.path.join(output_dir, main_filename)
        
        try:
            with open(output_filename, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as json_file:
                json.dump(results_data, json_file, indent=4, ensure_ascii=False, default=str)
            print(f"✅ Results successfully saved to: {output_filename}")
            print(f"📊 File size: {os.path.getsize(output_filename)} bytes")
            
            # Save summary file if configured
            if OUTPUT_CONFIG["create_summary"]:
                summary_filename = os.path.join(output_dir, f"analysis_summary{'_' + timestamp if timestamp else ''}.txt")
                with open(summary_filename, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as summary_file:
                    summary_file.write("FUNNEL ANALYSIS TOOL USAGE - ANALYSIS SUMMARY\n")
                    summary_file.write("=" * 60 + "\n\n")
                    summary_file.write(f"Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    summary_file.write(f"Total analyses performed: {results_data['metadata']['total_analyses']}\n\n")
                    
                    for analysis_name, analysis_data in results_data['analysis_results'].items():
                        summary_file.write(f"Analysis: {analysis_name.replace('_', ' ').title()}\n")
                        summary_file.write(f"Question: {analysis_data['question']}\n")
                        summary_file.write("-" * 40 + "\n")
                
                print(f"📝 Summary saved to: {summary_filename}")
            
            # Save individual result files if configured
            if OUTPUT_CONFIG["save_individual_files"]:
                for analysis_name, analysis_data in results_data['analysis_results'].items():
                    individual_filename = os.path.join(output_dir, f"{analysis_name}{'_' + timestamp if timestamp else ''}.json")
                    try:
                        with open(individual_filename, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as individual_file:
                            json.dump(analysis_data, individual_file, indent=4, ensure_ascii=False, default=str)
                        print(f"📄 Individual result saved: {individual_filename}")
                    except Exception as e:
                        print(f"⚠️  Warning: Could not save individual file for {analysis_name}: {e}")
            
            # Extract and save generated code as Python files if configured
            if OUTPUT_CONFIG.get("extract_generated_code", True):
                _extract_and_save_generated_code(results_data, output_dir, timestamp)
            
        except Exception as e:
            print(f"Error saving results to JSON file: {e}")
            # Fallback: print results to console if file saving fails
            print("Falling back to console output...")
            print(f"RESULT for How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?")
            print("="*80)
            print("result1", json.dumps(results_data["analysis_results"]["rolling_variance_analysis"]["result"], indent=4))
            print("="*80)
            
            print(f"RESULT for Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns by region and project")
            print("="*80)
            print("result2", json.dumps(results_data["analysis_results"]["anomaly_detection"]["result"], indent=4))
            print("="*80)
            
            print(f"RESULT for What are the mean, average daily transactional values for purchase orders by region and project")
            print("="*80)
            print("result3", json.dumps(results_data["analysis_results"]["mean_transactional_values"]["result"], indent=4))
            print("\n" + "="*80)
            
            print(f"RESULT for What are the daily trends of transactional values, forecasted values, and forecasted PO with line item for purchase orders by region and project")
            print("="*80)
            print("result4", json.dumps(results_data["analysis_results"]["daily_trends_forecast"]["result"], indent=4))
            print("\n" + "="*80)
            
            print(f"RESULT for What is the distribution of the transactional values for each type of source by region and project daily?")
            print("="*80)
            print("result5", json.dumps(results_data["analysis_results"]["distribution_analysis"]["result"], indent=4))
            print("\n" + "="*80)

    # Console output if configured
    if OUTPUT_CONFIG["console_output"]:
        print("\n" + "="*80)
        print("CONSOLE OUTPUT OF RESULTS:")
        print("="*80)
        
        for analysis_name, analysis_data in results_data['analysis_results'].items():
            print(f"\n📊 {analysis_name.replace('_', ' ').title()}:")
            print(f"Question: {analysis_data['question']}")
            print("-" * 60)
            print(json.dumps(analysis_data['result'], indent=2))
            print("-" * 60)
    
    print("\nANALYSIS COMPLETE")
    print("="*80)
    
    # Display summary of saved files
    print(f"\n📁 OUTPUT FILES CREATED:")
    if OUTPUT_CONFIG["save_to_json"]:
        print(f"   📄 Main results: {output_filename}")
        if OUTPUT_CONFIG["create_summary"]:
            print(f"   📄 Summary: {summary_filename}")
        if OUTPUT_CONFIG["save_individual_files"]:
            print(f"   📄 Individual results: {len(results_data['analysis_results'])} files")
        if OUTPUT_CONFIG.get("extract_generated_code", True):
            code_dir = os.path.join(output_dir, OUTPUT_CONFIG["code_output_directory"])
            if os.path.exists(code_dir):
                python_files = [f for f in os.listdir(code_dir) if f.endswith('.py')]
                print(f"   🐍 Generated Python code: {len(python_files)} files")
                print(f"   📁 Code directory: {os.path.abspath(code_dir)}")
        print(f"   📁 Output directory: {os.path.abspath(output_dir)}")
    else:
        print("   📄 No files saved (JSON output disabled)")
    
    print(f"\n📊 ANALYSIS SUMMARY:")
    print(f"   • Total analyses: {results_data['metadata']['total_analyses']}")
    print(f"   • Analysis type: {results_data['metadata']['analysis_type']}")
    print(f"   • Timestamp: {results_data['metadata']['timestamp']}")
    
    print("="*80)
    
    # Add instructions for using generated Python files
    if OUTPUT_CONFIG.get("extract_generated_code", True):
        code_dir = os.path.join(output_dir, OUTPUT_CONFIG["code_output_directory"])
        if os.path.exists(code_dir):
            python_files = [f for f in os.listdir(code_dir) if f.endswith('.py')]
            if python_files:
                print(f"\n🐍 GENERATED PYTHON CODE INSTRUCTIONS:")
                print(f"   📁 Code location: {os.path.abspath(code_dir)}")
                print(f"   📝 Files created: {len(python_files)} Python files")
                print(f"\n💡 HOW TO USE:")
                print(f"   1. Navigate to the code directory:")
                print(f"      cd {os.path.abspath(code_dir)}")
                print(f"   2. Run any pipeline file directly:")
                print(f"      python {python_files[0]}")
                print(f"   3. The files include sample data and are ready to run!")
                print(f"   4. Modify the sample data function to match your actual data")
                print(f"   5. Each file contains your generated pipeline code with error handling")


def _extract_and_save_generated_code(results_data, output_dir, timestamp):
        """Extract generated code from results and save as Python files"""
        try:
            # Create code output directory
            code_dir = os.path.join(output_dir, OUTPUT_CONFIG["code_output_directory"])
            os.makedirs(code_dir, exist_ok=True)
            
            extracted_files = []
            
            for analysis_name, analysis_data in results_data['analysis_results'].items():
                # Check if this analysis has generated code
                if "result" in analysis_data and "generated_code" in analysis_data["result"]:
                    code_data = analysis_data["result"]["generated_code"]
                    
                    if isinstance(code_data, dict) and "generated_code" in code_data:
                        # Extract the actual code
                        generated_code = code_data["generated_code"]
                        pipeline_type = code_data.get("pipeline_type", "unknown")
                        function_name = code_data.get("function_name", "unknown")
                        status = code_data.get("status", "unknown")
                        
                        if generated_code and status == "success":
                            # Create Python file
                            python_filename = f"{analysis_name}{'_' + timestamp if timestamp else ''}.py"
                            python_filepath = os.path.join(code_dir, python_filename)
                            
                            try:
                                with open(python_filepath, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as py_file:
                                    # Write header
                                    py_file.write(f'"""\n')
                                    py_file.write(f'Generated Pipeline Code\n')
                                    py_file.write(f'Analysis: {analysis_name}\n')
                                    py_file.write(f'Question: {analysis_data.get("question", "Unknown")}\n')
                                    py_file.write(f'Pipeline Type: {pipeline_type}\n')
                                    py_file.write(f'Function: {function_name}\n')
                                    py_file.write(f'Status: {status}\n')
                                    py_file.write(f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
                                    py_file.write(f'"""\n\n')
                                    
                                    # Write imports
                                    py_file.write('# Required imports\n')
                                    py_file.write('import pandas as pd\n')
                                    py_file.write('import numpy as np\n')
                                    py_file.write('from datetime import datetime, timedelta\n\n')
                                    
                                    # Pipeline imports
                                    py_file.write('# Pipeline imports\n')
                                    py_file.write('from app.tools.mltools import (\n')
                                    py_file.write('    # Cohort Analysis\n')
                                    py_file.write('    CohortPipe, form_time_cohorts, form_behavioral_cohorts, form_acquisition_cohorts,\n')
                                    py_file.write('    calculate_retention, calculate_conversion, calculate_lifetime_value,\n\n')
                                    py_file.write('    # Segmentation\n')
                                    py_file.write('    SegmentationPipe, get_features, run_kmeans, run_dbscan, run_hierarchical,\n')
                                    py_file.write('    run_rule_based, generate_summary, get_segment_data, compare_algorithms, custom_calculation,\n\n')
                                    py_file.write('    # Trend Analysis\n')
                                    py_file.write('    TrendPipe, aggregate_by_time, calculate_growth_rates, calculate_moving_average,\n')
                                    py_file.write('    calculate_statistical_trend, decompose_trend, forecast_metric, compare_periods, get_top_metrics,\n\n')
                                    py_file.write('    # Funnel Analysis\n')
                                    py_file.write('    analyze_funnel, analyze_funnel_by_time, analyze_user_paths, analyze_funnel_by_segment,\n')
                                    py_file.write('    get_funnel_summary, compare_segments,\n\n')
                                    py_file.write('    # Time Series Analysis\n')
                                    py_file.write('    TimeSeriesPipe, lead, lag, distribution_analysis, cumulative_distribution,\n')
                                    py_file.write('    variance_analysis, get_distribution_summary,\n\n')
                                    py_file.write('    # Metrics Analysis\n')
                                    py_file.write('    MetricsPipe, Mean, Sum, Count, Max, Min, Ratio, Dot, Nth, Variance,\n')
                                    py_file.write('    StandardDeviation, CV, Correlation, Cov, Median, Percentile, PivotTable,\n')
                                    py_file.write('    GroupBy, Filter, CumulativeSum, RollingMetric, Execute,\n\n')
                                    py_file.write('    # Operations Analysis\n')
                                    py_file.write('    OperationsPipe, PercentChange, AbsoluteChange, MH, CUPED, PrePostChange,\n')
                                    py_file.write('    FilterConditions, PowerAnalysis, StratifiedSummary, BootstrapCI,\n')
                                    py_file.write('    MultiComparisonAdjustment, ExecuteOperations,\n\n')
                                    py_file.write('    # Moving Averages\n')
                                    py_file.write('    MovingAggrPipe, moving_average, moving_sum, moving_std, moving_variance, moving_apply_by_group,\n\n')
                                    py_file.write('    # Risk Analysis\n')
                                    py_file.write('    RiskPipe, calculate_var, calculate_cvar,\n\n')
                                    py_file.write('    # Anomaly Detection\n')
                                    py_file.write('    AnomalyPipe, detect_statistical_outliers, detect_contextual_anomalies, get_anomaly_summary\n')
                                    py_file.write(')\n\n')
                                    
                                    
                                    
                                    # Write the actual generated code
                                    py_file.write('# Generated Pipeline Code\n')
                                    py_file.write('# =======================\n\n')
                                    py_file.write('def run_generated_pipeline(df):\n')
                                    py_file.write('    """Execute the generated pipeline"""\n')
                                    py_file.write('    try:\n')
                                    
                                    # Indent the generated code
                                    for line in generated_code.split('\n'):
                                        if line.strip():
                                            py_file.write(f'        {line}\n')
                                        else:
                                            py_file.write('\n')
                                    
                                    py_file.write('        \n')
                                    py_file.write('        return result\n')
                                    py_file.write('    except Exception as e:\n')
                                    py_file.write('        print(f"Error running pipeline: {e}")\n')
                                    py_file.write('        return None\n\n')
                                    
                                    # Write main execution block
                                    py_file.write('if __name__ == "__main__":\n')
                                    py_file.write('    result = run_generated_pipeline(df)\n')
                                    py_file.write('    \n')
                                    py_file.write('    if result is not None:\n')
                                    py_file.write('        print("✅ Pipeline executed successfully!")\n')
                                    py_file.write('        print(f"Result type: {type(result)}")\n')
                                    py_file.write('        if hasattr(result, "shape"):\n')
                                    py_file.write('            print(f"Result shape: {result.shape}")\n')
                                    py_file.write('        print("\\nResult preview:")\n')
                                    py_file.write('        print(result)\n')
                                    py_file.write('    else:\n')
                                    py_file.write('        print("❌ Pipeline execution failed!")\n')
                                
                                extracted_files.append(python_filepath)
                                print(f"🐍 Generated Python file: {python_filename}")
                                
                            except Exception as e:
                                print(f"⚠️  Warning: Could not create Python file for {analysis_name}: {e}")
                        else:
                            print(f"⚠️  No valid generated code found for {analysis_name} (status: {status})")
                    else:
                        print(f"⚠️  No generated code data found for {analysis_name}")
            
            if extracted_files:
                print(f"\n🎉 Successfully created {len(extracted_files)} Python files in: {code_dir}")
                print(f"💡 You can now run these files directly to test your pipelines!")
            else:
                print(f"\n⚠️  No Python files were created - check if analyses have generated code")
                
        except Exception as e:
            print(f"❌ Error extracting generated code: {e}")
            import traceback
            traceback.print_exc()


def create_sample_event_data(num_users=500):
    """Create a sample event dataset for demonstration"""
    # Create user IDs
    user_ids = np.arange(1, num_users + 1)
    
    # Lists to store event data
    all_user_ids = []
    all_events = []
    all_segments = []
    all_timestamps = []
    
    # Define conversion rates for different steps and segments
    segment_types = ['mobile', 'desktop', 'tablet']
    segment_conversion_rates = {
        'mobile': [0.78, 0.57, 0.39],  # [view->cart, cart->checkout, checkout->purchase]
        'desktop': [0.82, 0.65, 0.48],
        'tablet': [0.72, 0.48, 0.31]
    }
    
    # Create events for each user
    for user_id in user_ids:
        # Assign a segment
        segment = segment_types[user_id % len(segment_types)]
        
        # Start timestamp
       # Start timestamp - Convert NumPy int64 to Python int
        base_time = datetime.now() - timedelta(days=30)
        current_time = base_time + timedelta(minutes=int(user_id))
        
        # Everyone views a product
        all_user_ids.append(user_id)
        all_events.append('view_product')
        all_segments.append(segment)
        all_timestamps.append(current_time)
        
        # Some add to cart based on segment
        if np.random.random() < segment_conversion_rates[segment][0]:
            current_time += timedelta(minutes=np.random.randint(1, 10))
            all_user_ids.append(user_id)
            all_events.append('add_to_cart')
            all_segments.append(segment)
            all_timestamps.append(current_time)
            
            # Some start checkout based on segment
            if np.random.random() < segment_conversion_rates[segment][1]:
                current_time += timedelta(minutes=np.random.randint(1, 15))
                all_user_ids.append(user_id)
                all_events.append('start_checkout')
                all_segments.append(segment)
                all_timestamps.append(current_time)
                
                # Some purchase based on segment
                if np.random.random() < segment_conversion_rates[segment][2]:
                    current_time += timedelta(minutes=np.random.randint(1, 20))
                    all_user_ids.append(user_id)
                    all_events.append('purchase')
                    all_segments.append(segment)
                    all_timestamps.append(current_time)
    
    # Create the DataFrame
    df = pd.DataFrame({
        'user_id': all_user_ids,
        'event_name': all_events,
        'user_segment': all_segments,
        'event_timestamp': all_timestamps
    })
    
    return df

if __name__ == "__main__":
    main()
    """
    from app.tools.mltools.metrics_tools import MetricsPipe, GroupBy, Mean
    
    
    result = (
    MetricsPipe.from_dataframe("Purchase Orders Data")
    | GroupBy(
        by=["Date", "Region", "Project"],
        agg_dict={"Total Transactional value": "sum"},
    )
    | Mean(variable="Total Transactional value",
           output_name="average_daily_transactional_value")
    ).to_df()
    """