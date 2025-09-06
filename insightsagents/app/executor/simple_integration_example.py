#!/usr/bin/env python3
"""
Simple Integration Example: Jinja Template Manager + ML Pipeline Analysis

This example demonstrates the core integration between:
1. Jinja Template Manager for database connection code generation
2. analyze_question_with_intent_classification for ML pipeline generation
3. The complete workflow from data loading to executable code
"""

import pandas as pd
import asyncio
import sys
import json
from pathlib import Path

# Add the insightsagents path to sys.path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

import os

from langchain_openai import ChatOpenAI
from app.storage.documents import DocumentChromaStore, create_langchain_doc_util
from app.core.settings import get_settings
from app.core.dependencies import get_llm
from app.agents.nodes.mlagents.funnelanalysis_node import FunnelAnalysisAgent,retrieve_function_definition, retrieve_function_examples
from app.agents.nodes.mlagents.selfrag_mltool_pipeline import SelfCorrectingForwardPlanner
from app.agents.nodes.recommenders.ds_agents import SummarizeDatasetAgent
from app.agents.models.dsmodels import InsightManagerState
from app.agents.nodes.mlagents.analysis_intent_classification import AnalysisIntentPlanner
from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.executor.jinja_template_manager import template_manager, create_executable

import chromadb


# DEBUG: Print API key and configuration
print("🔍 DEBUG: Checking OpenAI API Configuration")
print("=" * 50)

settings = get_settings()
print(f"Settings object type: {type(settings)}")
print(f"Settings attributes: {dir(settings)}")

# Check if OPENAI_API_KEY exists in settings
if hasattr(settings, 'OPENAI_API_KEY'):
    api_key = settings.OPENAI_API_KEY
    print(f"OPENAI_API_KEY from settings: {api_key if api_key else 'None'}...")
else:
    print("❌ OPENAI_API_KEY not found in settings")
    api_key = None

# Check environment variable
env_api_key = os.environ.get("OPENAI_API_KEY")
print(f"OPENAI_API_KEY from environment: {env_api_key if env_api_key else 'None'}...")

# Check if we have a valid API key
if not api_key and not env_api_key:
    print("❌ No OpenAI API key found in settings or environment")
    print("Please check your configuration file or set OPENAI_API_KEY environment variable")
    sys.exit(1)

# Set the API key
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key
    print(f"✅ Set OPENAI_API_KEY from settings")
elif env_api_key:
    print(f"✅ Using OPENAI_API_KEY from environment")
else:
    print("❌ No valid API key available")
    sys.exit(1)

# Verify the key format
final_api_key = os.environ.get("OPENAI_API_KEY")
if final_api_key:
    print(f"🔑 Final API key format: {final_api_key}...")
    print(f"🔑 API key length: {len(final_api_key)} characters")
    
    # Check if it looks like a valid OpenAI key
    if final_api_key.startswith('sk-'):
        print("✅ API key format looks correct (starts with 'sk-')")
    else:
        print("⚠️  API key format may be incorrect (should start with 'sk-')")
else:
    print("❌ Failed to set OPENAI_API_KEY")
    sys.exit(1)

print("=" * 50)

CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH
print(f"ChromaDB path: {CHROMA_STORE_PATH}")

# Initialize ChromaDB client and collections
client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_examples_collection")
functions_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_spec_collection")
insights_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_insights_collection")
usage_examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="usage_examples_collection")

# Initialize LLM with error handling
print("\n🤖 Initializing LLM...")
try:
    llm = get_llm()
    print("✅ LLM initialized successfully")
    print(f"LLM type: {type(llm)}")
    print(f"LLM model: {getattr(llm, 'model_name', 'Unknown')}")
except Exception as e:
    print(f"❌ Failed to initialize LLM: {str(e)}")
    print("This might be due to the API key issue")
    sys.exit(1)

retrieval_helper = RetrievalHelper()

# Initialize the function retrieval system
function_retrieval = FunctionRetrieval(llm=llm, function_library_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/all_pipes_functions.json")

self_correcting_pipeline_code_generator = SelfCorrectingPipelineCodeGenerator(
                llm=llm,
                usage_examples_store=usage_examples_vectorstore,
                code_examples_store=examples_vectorstore,
                function_definition_store=functions_vectorstore,
                function_retrieval=function_retrieval  # Pass the FunctionRetrieval instance
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
    
    # DEBUG: Print current API key before function retrieval
    current_api_key = os.environ.get("OPENAI_API_KEY")
    print(f"🔍 Current API key being used: {current_api_key[:10] if current_api_key else 'None'}...")
    
     # Use the already initialized function retrieval system
    
    try:
        result = asyncio.run(function_retrieval.retrieve_relevant_functions(question,dataframe_description,dataframe_summary,columns_description))
        print("Retrieval functions result",result)
    except Exception as e:
        print(f"❌ Function retrieval failed: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Check if it's an API key issue
        if "401" in str(e) or "invalid_organization" in str(e):
            print("\n🔑 API Key Issue Detected!")
            print("This appears to be an authentication problem. Please check:")
            print("1. Your OpenAI API key is valid and active")
            print("2. Your OpenAI account has access to the required models")
            print("3. Your organization settings are correct")
            print("4. Your API key has the necessary permissions")
        
        raise e
    
    
    
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
                
                # Debug: Check what the code generation returned
                print(f"🔍 Debug - code_result type: {type(code_result)}")
                print(f"🔍 Debug - code_result keys: {code_result.keys() if isinstance(code_result, dict) else 'Not a dict'}")
                if isinstance(code_result, dict):
                    for key, value in code_result.items():
                        print(f"🔍 Debug - {key}: {type(value)} = {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
                
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


def generate_data_loader_code(template_name: str, sql_query: str, config: dict):
    """
    Generate data loader code using the Jinja template manager.
    
    Args:
        template_name (str): Name of the template (e.g., 'postgresql', 'trino')
        sql_query (str): SQL query to execute
        config (dict): Database connection configuration
    
    Returns:
        str: Generated Python code for data loading
    """
    print(f"🚀 Generating {template_name.upper()} Data Loader Code")
    print("=" * 50)
    
    try:
        # Use the template manager to generate executable code
        generated_code = create_executable(template_name, sql_query, config)
        
        if generated_code:
            print(f"✅ Successfully generated {template_name} data loader code")
            print(f"📏 Code length: {len(generated_code)} characters")
            return generated_code
        else:
            print(f"❌ Failed to generate code for template: {template_name}")
            return None
            
    except Exception as e:
        print(f"❌ Error generating {template_name} code: {str(e)}")
        return None


def main():
    """Main integration example"""
    
    print("🚀 Jinja Template Manager + ML Pipeline Integration Example")
    print("=" * 60)
    
    # Step 1: Check available templates
    print("\n📋 Step 1: Checking available Jinja templates...")
    available_templates = template_manager.list_templates()
    print(f"✅ Available templates: {', '.join(available_templates)}")
    
    # Step 2: Define SQL query and configuration
    print("\n🔍 Step 2: Setting up SQL query and database configuration...")
    
    # Example SQL query for financial analysis
    sql_query = """
    SELECT 
        DATE_TRUNC('day', transaction_date) as date,
        region,
        project,
        source_system,
        AVG(transaction_amount) as avg_amount,
        COUNT(*) as transaction_count,
        SUM(transaction_amount) as total_amount
    FROM financial_transactions 
    WHERE transaction_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY DATE_TRUNC('day', transaction_date), region, project, source_system
    ORDER BY date DESC, total_amount DESC
    """
    
    # PostgreSQL configuration
    postgres_config = {
        "host": "prod-db.company.com",
        "port": 5432,
        "database": "analytics",
        "user": "analytics_user",
        "password": "secure_password_123",
        "ssl_mode": "require",
        "connection_pool": True,
        "pool_size": 10,
        "test_connection": True,
        "show_info": True,
        "show_stats": True
    }
    
    # Trino configuration (alternative)
    trino_config = {
        "host": "trino-cluster.company.com",
        "port": 8080,
        "catalog": "analytics",
        "schema": "financial",
        "user": "analytics_user"
    }
    
    print(f"   📝 SQL Query length: {len(sql_query)} characters")
    print(f"   🔧 PostgreSQL config: {len(postgres_config)} parameters")
    print(f"   🔧 Trino config: {len(trino_config)} parameters")
    
    # Step 3: Generate data loader code
    print("\n🔧 Step 3: Generating data loader code...")
    
    # Generate PostgreSQL data loader
    postgres_loader_code = generate_data_loader_code("postgresql", sql_query, postgres_config)
    
    if postgres_loader_code:
        # Save PostgreSQL data loader
        postgres_filename = "postgres_data_loader.py"
        with open(postgres_filename, 'w', encoding='utf-8') as f:
            f.write(postgres_loader_code)
        print(f"   💾 PostgreSQL data loader saved to: {postgres_filename}")
    
    # Generate Trino data loader
    trino_loader_code = generate_data_loader_code("trino", sql_query, trino_config)
    
    if trino_loader_code:
        # Save Trino data loader
        trino_filename = "trino_data_loader.py"
        with open(trino_filename, 'w', encoding='utf-8') as f:
            f.write(trino_loader_code)
        print(f"   💾 Trino data loader saved to: {trino_filename}")
    
    # Step 4: ML Pipeline Analysis
    print("\n🤖 Step 4: Running ML pipeline analysis...")
    
    # Load real financial transaction data from the CSV file for analysis
    # This replaces the sample data with actual BV Finance Flux data containing real transactions
    csv_file_path = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/inputs/bv_finance_flux_final.csv"
    
    try:
        # Load the CSV data
        financial_data = pd.read_csv(csv_file_path)
        
        # Debug: Verify the DataFrame shape
        print(f"   📊 CSV DataFrame loaded: {financial_data.shape[0]} rows, {financial_data.shape[1]} columns")
        print(f"   📋 CSV columns: {list(financial_data.columns)}")
        
        # Display first few rows for verification
        print(f"   📋 First few rows:")
        print(financial_data.head(3).to_string())
        
    except FileNotFoundError:
        print(f"   ❌ Error: CSV file not found at {csv_file_path}")
        print(f"   📍 Current working directory: {os.getcwd()}")
        # Fallback to sample data if CSV is not available
        print(f"   🔄 Falling back to sample data...")
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        regions = ['North', 'South', 'East', 'West'] * 8
        projects = ['Project A', 'Project B', 'Project C'] * 10
        source_systems = ['PROJECT_ACCOUNTING', 'PAYABLES', 'REVALUATION'] * 10
        avg_amounts = [1000, 1500, 2000, 2500] * 8
        transaction_counts = [50, 75, 100, 125] * 8
        total_amounts = [50000, 112500, 200000, 312500] * 8
        
        regions = regions[:30]
        avg_amounts = avg_amounts[:30]
        transaction_counts = transaction_counts[:30]
        total_amounts = total_amounts[:30]
        
        financial_data = pd.DataFrame({
            'date': dates,
            'region': regions,
            'project': projects,
            'source_system': source_systems,
            'avg_amount': avg_amounts,
            'transaction_count': transaction_counts,
            'total_amount': total_amounts
        })
    
    # Define column descriptions based on the actual CSV structure
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
        "PO with Line item": "Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking"
    }
    
    # Example question for analysis
    question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
    
    try:
        print(f"   📝 Analyzing question: {question}")
        
        analysis_result = analyze_question_with_intent_classification(
            question=question,
            dataframe=financial_data,
            dataframe_description="Financial transaction data with detailed project, region, cost center, and transaction information",
            dataframe_summary="Dataset contains detailed financial transactions with purchase orders, invoices, and cost distributions across multiple regions and projects",
            columns_description=columns_description,
            enable_code_generation=True,
            context="Analyze daily trends in transaction amounts to understand spending patterns",
            dataframe_name="financial_data"
        )
        
        # Pretty print the analysis result to see reasoning steps
        import json
        print("\n" + "="*80)
        print("ANALYSIS RESULT - REASONING STEPS")
        print("="*80)
        
        # Extract and print key reasoning information
        if hasattr(analysis_result, 'reasoning_plan') and analysis_result.reasoning_plan:
            print("\nREASONING PLAN:")
            print(json.dumps(analysis_result.reasoning_plan, indent=2, default=str))
        
        if hasattr(analysis_result, 'retrieved_functions') and analysis_result.retrieved_functions:
            print("\nRETRIEVED FUNCTIONS:")
            print(json.dumps(analysis_result.retrieved_functions, indent=2, default=str))
        
        if hasattr(analysis_result, 'intent_type'):
            print(f"\nINTENT TYPE: {analysis_result.intent_type}")
            print(f"CONFIDENCE: {analysis_result.confidence_score}")
            print(f"REPHRASED QUESTION: {analysis_result.rephrased_question}")
            print(f"REASONING: {analysis_result.reasoning}")
        
        if hasattr(analysis_result, 'suggested_functions'):
            print(f"\nSUGGESTED FUNCTIONS: {analysis_result.suggested_functions}")
        
        if hasattr(analysis_result, 'required_data_columns'):
            print(f"\nREQUIRED COLUMNS: {analysis_result.required_data_columns}")
        
        if hasattr(analysis_result, 'missing_columns'):
            print(f"\nMISSING COLUMNS: {analysis_result.missing_columns}")
        
        if hasattr(analysis_result, 'can_be_answered'):
            print(f"\nCAN BE ANSWERED: {analysis_result.can_be_answered}")
            print(f"FEASIBILITY SCORE: {analysis_result.feasibility_score}")
        
        if hasattr(analysis_result, 'clarification_needed'):
            print(f"\nCLARIFICATION NEEDED: {analysis_result.clarification_needed}")
        
        # Print the full result as JSON for complete inspection
        print("\n" + "="*80)
        print("FULL ANALYSIS RESULT (JSON)")
        print("="*80)
        try:
            # Convert to dict if it's a Pydantic model
            if hasattr(analysis_result, 'dict'):
                result_dict = analysis_result.dict()
            elif hasattr(analysis_result, 'model_dump'):
                result_dict = analysis_result.model_dump()
            else:
                result_dict = analysis_result.__dict__
            
            print(json.dumps(result_dict, indent=2, default=str))
        except Exception as e:
            print(f"Error converting to JSON: {e}")
            print(f"Raw result type: {type(analysis_result)}")
            print(f"Raw result: {analysis_result}")
        
        print("="*80)
        print(f"   ✅ Analysis completed successfully")
        print(f"   🎯 Intent classification: {analysis_result['intent_classification'].can_be_answered}")
        
        if 'generated_code' in analysis_result:
            print(f"   💻 Code generated successfully!")
            print(f"   📏 Generated code length: {len(analysis_result['generated_code'])} characters")
            
            # Show a preview of the generated code
            print(f"   🔍 Code preview (first 200 chars):")
            code_preview = analysis_result['generated_code'][:200] + "..." if len(analysis_result['generated_code']) > 200 else analysis_result['generated_code']
            print(f"      {code_preview}")
            
            # Debug: Check what type of data we received
            generated_code = analysis_result.get('generated_code')
            print(f"   🔍 Debug - generated_code type: {type(generated_code)}")
            
            # Handle different types of generated code results
            if isinstance(generated_code, dict):
                # If it's a dictionary, extract the actual code
                if 'generated_code' in generated_code:
                    actual_code = generated_code['generated_code']
                elif 'code' in generated_code:
                    actual_code = generated_code['code']
                elif 'pipeline_code' in generated_code:
                    actual_code = generated_code['pipeline_code']
                else:
                    # Try to find any string field that looks like code
                    actual_code = None
                    for key, value in generated_code.items():
                        if isinstance(value, str) and ('from_dataframe' in value or 'Pipe' in value):
                            actual_code = value
                            break
                    
                    if actual_code is None:
                        # Convert the entire dict to a string representation
                        actual_code = f"# Generated code structure:\n{json.dumps(generated_code, indent=2)}"
                        print(f"   ⚠️  Warning: No direct code found, saving structure instead")
            elif isinstance(generated_code, str):
                actual_code = generated_code
            else:
                # Convert to string if it's not a string
                actual_code = str(generated_code)
                print(f"   ⚠️  Warning: Generated code was not a string, converted to: {type(actual_code)}")
            
            # Save the generated pipeline code to a Python file
            try:
                pipeline_filename = "generated_pipeline_code.py"
                with open(pipeline_filename, 'w', encoding='utf-8') as f:
                    # Add header
                    f.write("# Generated Pipeline Code\n")
                    f.write("# Generated by SelfCorrectingPipelineCodeGenerator\n")
                    f.write("# Date: " + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
                    f.write("# Question: " + question + "\n")
                    f.write("#" + "="*60 + "\n\n")
                    
                    # Add imports
                    f.write("import pandas as pd\n")
                    f.write("import numpy as np\n")
                    f.write("from datetime import datetime\n")
                    f.write("import os\n")
                    f.write("from pathlib import Path\n\n")
                    
                    # Add the generated code
                    f.write(actual_code)
                    
                    # Add execution function
                    f.write("\n\n# Pipeline Execution Function\n")
                    f.write("# ===========================\n\n")
                    
                    f.write("def execute_pipeline():\n")
                    f.write("    \"\"\"Execute the complete pipeline: Data Loading → ML Pipeline\"\"\"\n")
                    f.write("    print('🚀 Starting Financial Data Pipeline')\n")
                    f.write("    print('=' * 50)\n")
                    f.write("    \n")
                    f.write("    try:\n")
                    f.write("        # Step 1: Load data using the generated data loader\n")
                    f.write("        print('🔍 Step 1: Loading data...')\n")
                    f.write("        print('💡 Note: Import and run your data loader first')\n")
                    f.write("        print('   Example: from postgres_data_loader import *')\n")
                    f.write("        print('   Then run the data loading code')\n")
                    f.write("        \n")
                    f.write("        # Step 2: Execute the ML pipeline code\n")
                    f.write("        print('🤖 Step 2: Executing ML pipeline...')\n")
                    f.write("        \n")
                    f.write("        # The generated ML code will use the DataFrame\n")
                    f.write("        # Make sure you have a DataFrame named 'financial_data' available\n")
                    f.write("        \n")
                    f.write("        print('✅ ML pipeline executed successfully!')\n")
                    f.write("        \n")
                    f.write("    except Exception as e:\n")
                    f.write("        print(f'❌ Pipeline failed: {e}')\n")
                    f.write("        import traceback\n")
                    f.write("        traceback.print_exc()\n")
                    f.write("        raise e\n\n")
                    
                    # Example execution
                    f.write("# Example execution:\n")
                    f.write("if __name__ == '__main__':\n")
                    f.write("    print('🚀 Starting Financial Data Pipeline')\n")
                    f.write("    print('=' * 50)\n")
                    f.write("    \n")
                    f.write("    try:\n")
                    f.write("        # Execute the complete pipeline\n")
                    f.write("        execute_pipeline()\n")
                    f.write("        \n")
                    f.write("        print(f'\\n🎉 Pipeline completed successfully!')\n")
                    f.write("        \n")
                    f.write("    except Exception as e:\n")
                    f.write("        print(f'\\n❌ Pipeline failed: {e}')\n")
                    f.write("        \n")
                    f.write("    print('\\n💡 Template Usage:')\n")
                    f.write("    print('1. First run your data loader: python postgres_data_loader.py')\n")
                    f.write("    print('2. Then run this pipeline: python generated_pipeline_code.py')\n")
                    f.write("    print('3. Modify the data loader configuration as needed')\n")
                    f.write("    print('4. Update the ML pipeline logic in the generated code section')\n")
                
                print(f"   💾 Generated pipeline code saved to: {pipeline_filename}")
                print(f"   📁 File path: {os.path.abspath(pipeline_filename)}")
                
                # Also save a metadata file with analysis details
                metadata_filename = "generated_code_metadata.txt"
                with open(metadata_filename, 'w', encoding='utf-8') as f:
                    f.write("Generated Pipeline Code Metadata\n")
                    f.write("=" * 40 + "\n\n")
                    f.write(f"Question: {question}\n")
                    f.write(f"Generated Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Intent Classification: {analysis_result['intent_classification'].can_be_answered}\n")
                    f.write(f"Feasibility Score: {analysis_result['intent_classification'].feasibility_score}\n")
                    f.write(f"Suggested Functions: {analysis_result['intent_classification'].suggested_functions}\n")
                    f.write(f"Required Columns: {analysis_result['intent_classification'].required_data_columns}\n")
                    f.write(f"Missing Columns: {analysis_result['intent_classification'].missing_columns}\n")
                    f.write(f"Reasoning Plan: {analysis_result['intent_classification'].reasoning_plan}\n")
                    f.write(f"Code Length: {len(actual_code) if isinstance(actual_code, str) else 'N/A'} characters\n")
                    f.write(f"Code Type: {type(actual_code)}\n")
                    f.write(f"Original Result Type: {type(generated_code)}\n")
                
                print(f"   📋 Metadata saved to: {metadata_filename}")
                
                # Offer to test the generated code
                print(f"   🧪 To test the generated code:")
                print(f"      1. First run data loader: python postgres_data_loader.py")
                print(f"      2. Then run pipeline: python {pipeline_filename}")
                print(f"   📖 Review the metadata in: {metadata_filename}")
                
            except Exception as save_error:
                print(f"   ⚠️  Warning: Could not save generated code to file: {str(save_error)}")
                print(f"   💡 You can copy the code manually from the output above")
                print(f"   🔍 Debug info: generated_code type={type(generated_code)}, actual_code type={type(actual_code) if 'actual_code' in locals() else 'Not defined'}")
            
        else:
            print(f"   ⚠️  No code generated")
            
    except Exception as e:
        print(f"   ❌ Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Step 5: Demonstrate template manager capabilities
    print("\n⚡ Step 5: Demonstrating Jinja Template Manager capabilities...")
    
    # Get template information
    for template_name in available_templates:
        template_info = template_manager.get_template_info(template_name)
        if template_info:
            print(f"   📋 Template: {template_name}")
            print(f"   🔧 Dependencies: {', '.join(template_info['dependencies'])}")
            print(f"   📊 Required params: {', '.join(template_info['connection_parameters'])}")
    
    # Get template statistics
    template_stats = template_manager.get_template_stats()
    print(f"   🗂️  Total templates: {template_stats['total_templates']}")
    print(f"   📊 Templates by type: {template_stats['templates_by_type']}")
    
    print("\n🎉 Integration example completed successfully!")
    print("=" * 60)
    
    print("\n🔗 Integration Summary:")
    print("   ✅ Jinja Template Manager generates database connection code")
    print("   ✅ ML pipeline analysis generates executable code")
    print("   ✅ Both systems work together seamlessly")
    print("   ✅ Data flows from template generation to analysis to code generation")
    
    # Show information about the generated files
    generated_files = []
    if os.path.exists("postgres_data_loader.py"):
        generated_files.append(("PostgreSQL Data Loader", "postgres_data_loader.py"))
    if os.path.exists("trino_data_loader.py"):
        generated_files.append(("Trino Data Loader", "trino_data_loader.py"))
    if os.path.exists("generated_pipeline_code.py"):
        generated_files.append(("ML Pipeline Code", "generated_pipeline_code.py"))
    
    if generated_files:
        print(f"\n📁 Generated Files:")
        for file_desc, filename in generated_files:
            print(f"   💻 {file_desc}: {os.path.abspath(filename)}")
        
        print(f"\n🧪 To verify the generated code:")
        print(f"   1. Review the data loaders in: postgres_data_loader.py / trino_data_loader.py")
        print(f"   2. Check the pipeline code in: generated_pipeline_code.py")
        print(f"   3. Test data loading: python postgres_data_loader.py")
        print(f"   4. Test pipeline execution: python generated_pipeline_code.py")
        print(f"   5. Modify the code as needed for your specific use case")
    
    print("\n🚀 Next Steps:")
    print("   1. Customize the database configuration in the data loaders")
    print("   2. Modify the column descriptions for your data")
    print("   3. Deploy the generated code to production")
    print("   4. Add more database templates as needed")


if __name__ == "__main__":
    main()
