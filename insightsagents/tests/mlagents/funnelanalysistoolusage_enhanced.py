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
from app.agents.nodes.mlagents.analysis_intent_classification_simplified import SimplifiedAnalysisIntentPlanner
from app.agents.nodes.mlagents.pipeline_flow_integration import PipelineFlowIntegrationAgent
from app.agents.nodes.mlagents.flow_graph_generator import FlowGraphGenerator
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper
import json

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
    "code_output_directory": "generated_code",  # Directory for generated Python code
    "create_flow_visualization": True,  # Create flow graph visualization
    "visualization_output_directory": "flow_visualizations",  # Directory for flow visualizations
    "create_mermaid_charts": True,  # Create Mermaid charts
    "mermaid_output_directory": "mermaid_charts"  # Directory for Mermaid charts
}

os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
# Use the same ChromaDB path as RetrievalHelper
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH+"/enhanced_comprehensive_registry"
# Initialize ChromaDB client and collections
client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
collection_name = "comprehensive_ml_functions_demo"
# Define collection names for different data types
# Note: These must match the collection names expected by RetrievalHelper
collection_names = {
    'unified': collection_name,
    'toolspecs': f"{collection_name}_toolspecs",  # Enhanced collection with detailed parameters
    'instructions': f"{collection_name}_instructions",  # Enhanced collection with detailed parameters
    'usage_examples': f"{collection_name}_usage_examples",  # Enhanced collection with detailed parameters
    'code_examples': f"{collection_name}_code_examples",
    'code': f"{collection_name}_code"
}

# Initialize separate document stores for each collection type (excluding unified)
document_stores = {}
for collection_type, full_collection_name in collection_names.items():
    if collection_type != 'unified':  # Skip unified collection, use parent's document_store
        print(f"Initializing document store for collection: {full_collection_name}")
        try:
            document_stores[full_collection_name] = DocumentChromaStore(
                persistent_client=client,
                collection_name=full_collection_name,
                tf_idf=False  # Disable TF-IDF to avoid UUID collection issues
            )
            print(f"Successfully initialized document store for: {full_collection_name}")
        except Exception as e:
            print(f"Failed to initialize document store for {full_collection_name}: {e}")
            raise

#examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_examples_collection")
#functions_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_spec_collection")
#insights_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_insights_collection")
#usage_examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="usage_examples_collection")

# Use the base collection name to access the document stores
# Note: These must match the collection names expected by RetrievalHelper
examples_vectorstore = document_stores[f'{collection_name}_code_examples']
functions_vectorstore = document_stores[f'{collection_name}_toolspecs']  # Enhanced collection with detailed parameters
insights_vectorstore = document_stores[f'{collection_name}_instructions']  # Enhanced collection with detailed parameters
usage_examples_vectorstore = document_stores[f'{collection_name}_usage_examples']  # Enhanced collection with detailed parameters
# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
retrieval_helper = RetrievalHelper()

# Initialize the pipeline flow integration agent
pipeline_flow_agent = PipelineFlowIntegrationAgent(
    llm=llm,
    usage_examples_store=usage_examples_vectorstore,
    code_examples_store=examples_vectorstore,
    function_definition_store=functions_vectorstore,
    retrieval_helper=retrieval_helper
)

# Initialize the simplified intent planner
planner = SimplifiedAnalysisIntentPlanner(
    llm=llm,
    retrieval_helper=retrieval_helper
)

def analyze_question_with_pipeline_flow(
    question: str,
    dataframe: pd.DataFrame,
    dataframe_description: str = None,
    dataframe_summary: str = None,
    columns_description: dict = None,
    context: str = None,
    dataframe_name: str = "Dataset"
):
    """
    Analyze a question using pipeline flow integration with separate step codes and flow graphs.
    
    Args:
        question (str): The question to analyze
        dataframe (pd.DataFrame): The dataframe to analyze
        dataframe_description (str, optional): Description of the dataframe
        dataframe_summary (str, optional): Summary of the dataframe
        columns_description (dict, optional): Description of each column
        context (str, optional): Additional context for code generation
        dataframe_name (str): Name of the dataframe for code generation
    
    Returns:
        dict: Analysis results including pipeline flow with separate step codes and flow graphs
    """
    print(f"\n{'='*80}")
    print(f"🔍 ANALYZING QUESTION: {question}")
    print(f"{'='*80}")
    
    # Initialize function retrieval
    retrieval = FunctionRetrieval(
        llm=llm,
        function_library_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/all_pipes_functions.json"
    )
    retrieval_result = asyncio.run(retrieval.retrieve_relevant_functions(
        question, dataframe_description, dataframe_summary, columns_description
    ))
    print(f"📋 Retrieved {len(retrieval_result.top_functions)} relevant functions")
    
    # If dataframe description/summary not provided, generate them
    if dataframe_description is None or dataframe_summary is None:
        print("📊 Generating dataframe summary...")
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
    print("🎯 Classifying intent...")
    intent_result = asyncio.run(planner.classify_intent(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=dataframe.columns.tolist()
    ))
    
    # Print intent classification results
    print(f"\n📈 Intent Classification Results:")
    print(f"  ✅ Feasibility Score: {intent_result.get('feasibility_score', 0.0)}")
    print(f"  ✅ Can be answered: {intent_result.get('can_be_answered', False)}")
    print(f"  📊 Missing columns: {intent_result.get('missing_columns', [])}")
    print(f"  🔧 Suggested functions: {intent_result.get('suggested_functions', [])}")
    print(f"  📋 Reasoning plan steps: {len(intent_result.get('reasoning_plan', []))}")
    print(f"  📋 Pipeline plan steps: {len(intent_result.get('pipeline_reasoning_plan', []))}")
    
    if not intent_result.get('can_be_answered', False):
        print("❌ Question cannot be answered with available data")
        return {
            "question": question,
            "intent_classification": intent_result,
            "pipeline_flow_result": None,
            "error": "Question cannot be answered with available data"
        }
    
    # Generate pipeline with flow graph
    print("\n🚀 Generating Pipeline with Flow Graph...")
    try:
        # Extract function names from suggested functions
        function_names = []
        suggested_functions = intent_result.get('suggested_functions', [])
        if suggested_functions:
            for func in suggested_functions:
                if ': ' in func:
                    function_name = func.split(': ')[0]
                    function_names.append(function_name)
                else:
                    function_names.append(func)
        
        # Create enhanced columns description
        enhanced_columns_description = columns_description or {}
        reasoning_plan = intent_result.get('reasoning_plan', [])
        pipeline_reasoning_plan = intent_result.get('pipeline_reasoning_plan', [])
        
        if reasoning_plan and isinstance(reasoning_plan, list):
            enhanced_columns_description['_enhanced_metadata'] = {
                'reasoning_plan_steps': len(reasoning_plan),
                'pipeline_plan_steps': len(pipeline_reasoning_plan),
                'has_enhanced_metadata': any(
                    step.get('column_mapping') or step.get('input_columns') or step.get('output_columns')
                    for step in pipeline_reasoning_plan if isinstance(step, dict)
                ),
                'pipeline_types': list(set(
                    step.get('pipeline_type') for step in pipeline_reasoning_plan 
                    if isinstance(step, dict) and step.get('pipeline_type')
                )),
                'function_categories': list(set(
                    step.get('function_category') for step in pipeline_reasoning_plan 
                    if isinstance(step, dict) and step.get('function_category')
                ))
            }
        
        # Generate pipeline with flow graph
        pipeline_flow_result = asyncio.run(pipeline_flow_agent.generate_pipeline_with_flow_graph(
            context=context or question,
            function_name=function_names,
            function_inputs=intent_result.get('required_data_columns', []),
            dataframe_name=dataframe_name,
            classification=intent_result,
            dataset_description=dataframe_summary,
            columns_description=enhanced_columns_description
        ))
        
        print("✅ Pipeline flow generation completed successfully!")
        
        # Display results summary
        if pipeline_flow_result["status"] == "success":
            pipeline_result = pipeline_flow_result["pipeline_result"]
            flow_graph_result = pipeline_flow_result["flow_graph_result"]
            
            print(f"\n📊 Pipeline Flow Summary:")
            print(f"  🔧 Total Steps: {len(pipeline_result.get('step_codes', []))}")
            print(f"  🕸️  Flow Graph Nodes: {flow_graph_result['metadata']['total_nodes']}")
            print(f"  🔗 Flow Graph Edges: {flow_graph_result['metadata']['total_edges']}")
            print(f"  ⚡ Can Parallelize: {flow_graph_result['metadata']['can_parallelize']}")
            print(f"  🎯 Pipeline Types: {flow_graph_result['metadata']['pipeline_types']}")
            
            # Display step details
            step_codes = pipeline_result.get('step_codes', [])
            if step_codes:
                print(f"\n🔧 Individual Step Details:")
                for i, step in enumerate(step_codes, 1):
                    print(f"  Step {i}: {step['title']}")
                    print(f"    Function: {step['function']}")
                    print(f"    Pipeline Type: {step['pipeline_type']}")
                    print(f"    Input: {step['input_dataframe']} -> Output: {step['output_dataframe']}")
                    print(f"    Dependencies: {step['dependencies']}")
        
        return {
            "question": question,
            "intent_classification": intent_result,
            "pipeline_flow_result": pipeline_flow_result,
            "dataframe_info": {
                "shape": dataframe.shape,
                "columns": dataframe.columns.tolist(),
                "summary": dataframe_summary
            }
        }
        
    except Exception as e:
        print(f"❌ Error during pipeline flow generation: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "question": question,
            "intent_classification": intent_result,
            "pipeline_flow_result": None,
            "error": str(e)
        }



def main():
    print("🚀 Enhanced Funnel Analysis Tool with Pipeline Flow Integration")
    print("=" * 80)
    
    # Load data
    po_df = pd.read_csv("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/ai-report/app/bv_finance_flux_final.csv")
    print(f"📊 Loaded dataset with shape: {po_df.shape}")
    
    # Initialize summarization agent
    summarize_agent = SummarizeDatasetAgent()
    
    # Define analysis questions
    analysis_questions = [
         
        {
            "name": "rolling_variance_analysis_2",
            "question": "What are the daily total transactional values for purchase orders by projects, region and departments",
            "context": "Analyze the flux values over time for each group of projects, cost centers, and departments for making better decisions of investment"
        },{
            "name": "daily_trends_forecast",
            "question": "What are the daily trends of transactional values, forecasted values, and forecasted PO with line item for purchase orders by region and project",
            "context": "Calculate mean daily transactional values"
        }
         
    ]
    """
        {
            "name": "anomaly_detection",
            "question": "Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns week by week by region and project",
            "context": "Find anomalies in daily spending patterns"
        }
       {
            "name": "rolling_variance_analysis",
            "question": "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            "context": "Analyze the flux values over time for each group of projects, cost centers, and departments for making better decisions of investment"
        },

        {
            "name": "anomaly_detection",
            "question": "Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns week by week by region and project",
            "context": "Find anomalies in daily spending patterns"
        },
        {
            "name": "mean_transactional_values",
            "question": "What are the mean, average daily transactional values for purchase orders by region and project",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "daily_trends_forecast",
            "question": "What are the daily trends of transactional values, forecasted values, and forecasted PO with line item for purchase orders by region and project",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "distribution_analysis",
            "question": "What is the distribution of the mean daily transactional values for each type of source by region and project daily?",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "flux_analysis",
            "question": "Perform rolling 5 day mean transactiona values, forecasted values. Using those perform flux analysis by calculating the variance for the mean transactional values, forecasted values by region,cost center, and project",
            "context": "Calculate mean daily transactional values"
        }
    """
    
    # Column descriptions
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
        "Forecasted PO with Line item": "Forecasted Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking"
    }
    
    # Run analyses
    results = {}
    for analysis in analysis_questions:
        print(f"\n{'='*80}")
        print(f"🔍 Running Analysis: {analysis['name'].replace('_', ' ').title()}")
        print(f"{'='*80}")
        
        # Generate dataframe summary
        state = InsightManagerState(
            question=analysis["question"],
            context=analysis["context"],
            goal="Generate insights from the dataset",
            dataset_path=""
        )
        dataframe_summary = summarize_agent.summarize_dataframe(
            dataframe=po_df, 
            question=analysis["question"], 
            state=state
        )
        
        # Run analysis
        result = analyze_question_with_pipeline_flow(
            question=analysis["question"],
            dataframe=po_df,
            dataframe_description="Financial flux data with project, cost center, and department information",
            dataframe_summary=dataframe_summary,
            columns_description=columns_description,
            context=analysis["context"],
            dataframe_name="Purchase Orders Data"
        )
        
        results[analysis["name"]] = result
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') if OUTPUT_CONFIG["include_timestamp"] else ""
    
    # Create output directory
    output_dir = OUTPUT_CONFIG["output_directory"]
    os.makedirs(output_dir, exist_ok=True)
    
    # Create visualizations and comprehensive files
    print(f"\n🎨 Creating Visualizations and Comprehensive Files...")
    for analysis_name, result in results.items():
        if result.get("pipeline_flow_result"):
            # Create flow graph generator instance
            flow_graph_generator = FlowGraphGenerator()
            
            # Create Mermaid flow visualization
            if OUTPUT_CONFIG["create_flow_visualization"]:
                flow_graph_generator.create_mermaid_visualization(
                    result["pipeline_flow_result"], 
                    output_dir, 
                    analysis_name, 
                    timestamp
                )
            
            # Create comprehensive flow file
            flow_graph_generator.create_comprehensive_flow_file(
                result["pipeline_flow_result"], 
                output_dir, 
                analysis_name, 
                timestamp
            )
    
    # Save results to JSON
    if OUTPUT_CONFIG["save_to_json"]:
        print(f"\n💾 Saving Results to JSON...")
        
        # Convert results to JSON-serializable format
        def convert_to_json_serializable(obj):
            if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
                return obj.dict()
            elif isinstance(obj, dict):
                return {key: convert_to_json_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_json_serializable(item) for item in obj]
            else:
                return obj
        
        json_results = {
            "analysis_results": {
                name: convert_to_json_serializable(result) 
                for name, result in results.items()
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_analyses": len(results),
                "analysis_type": "enhanced_funnel_analysis_with_pipeline_flow"
            }
        }
        
        # Save main results file
        main_filename = f"enhanced_funnel_analysis_results{'_' + timestamp if timestamp else ''}.json"
        output_filename = os.path.join(output_dir, main_filename)
        
        try:
            with open(output_filename, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as json_file:
                json.dump(json_results, json_file, indent=4, ensure_ascii=False, default=str)
            print(f"✅ Results saved to: {output_filename}")
        except Exception as e:
            print(f"❌ Error saving results: {e}")
    
    # Display summary
    print(f"\n📊 ANALYSIS SUMMARY")
    print(f"{'='*80}")
    print(f"Total analyses: {len(results)}")
    print(f"Successful analyses: {sum(1 for r in results.values() if r.get('pipeline_flow_result'))}")
    print(f"Failed analyses: {sum(1 for r in results.values() if not r.get('pipeline_flow_result'))}")
    
    # Display file summary
    print(f"\n📁 OUTPUT FILES CREATED:")
    print(f"   📄 Main results: {output_filename if OUTPUT_CONFIG['save_to_json'] else 'Not saved'}")
    
    if OUTPUT_CONFIG["create_flow_visualization"]:
        vis_dir = os.path.join(output_dir, OUTPUT_CONFIG["visualization_output_directory"])
        if os.path.exists(vis_dir):
            png_files = [f for f in os.listdir(vis_dir) if f.endswith('.png')]
            print(f"   🎨 Flow visualizations: {len(png_files)} PNG files")
            print(f"   📁 Visualization directory: {os.path.abspath(vis_dir)}")
    
    if OUTPUT_CONFIG["create_mermaid_charts"]:
        mermaid_dir = os.path.join(output_dir, OUTPUT_CONFIG["mermaid_output_directory"])
        if os.path.exists(mermaid_dir):
            mmd_files = [f for f in os.listdir(mermaid_dir) if f.endswith('.mmd')]
            html_files = [f for f in os.listdir(mermaid_dir) if f.endswith('.html')]
            print(f"   📊 Mermaid charts: {len(mmd_files)} MMD files, {len(html_files)} HTML files")
            print(f"   📁 Mermaid directory: {os.path.abspath(mermaid_dir)}")
    
    # Count comprehensive flow files
    py_files = [f for f in os.listdir(output_dir) if f.endswith('_comprehensive_flow.py')]
    print(f"   📄 Comprehensive flow files: {len(py_files)} Python files")
    print(f"   📁 Output directory: {os.path.abspath(output_dir)}")
    
    print(f"\n🎉 Enhanced Funnel Analysis Complete!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
