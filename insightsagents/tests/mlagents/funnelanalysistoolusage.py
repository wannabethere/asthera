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

settings = get_settings()
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH

os.environ["OPENAI_API_KEY"] = "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"
 # Initialize ChromaDB client and collections
client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_examples_collection")
functions_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_spec_collection")
insights_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_insights_collection")
usage_examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="usage_examples_collection")

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)



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
    
    # Initialize the intent planner
    planner = AnalysisIntentPlanner(
        llm=llm,
        function_collection=functions_vectorstore,
        example_collection=examples_vectorstore, 
        insights_collection=insights_vectorstore
    )
    
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
            self_correcting_pipeline_code_generator = SelfCorrectingPipelineCodeGenerator(
                llm=llm,
                usage_examples_store=usage_examples_vectorstore,
                code_examples_store=examples_vectorstore,
                function_definition_store=functions_vectorstore
            )
            
            code_context = context or question
            
            code_result = asyncio.run(self_correcting_pipeline_code_generator.generate_pipeline_code(
                context=code_context,
                function_name=result.suggested_functions,
                function_inputs=result.required_data_columns,
                dataframe_name=dataframe_name,
                classification=result,
                dataset_description=dataframe_summary,
                columns_description=columns_description or {}
            ))
            
            analysis_results["generated_code"] = code_result
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
    
    # Step 2: Initialize the agent
    print("\nInitializing Funnel Analysis Agent...")
   
   
    summarize_agent = SummarizeDatasetAgent()
    state = InsightManagerState(
            question="How do I analyze funnel performance across different user segments with my event data?",
            context="Objective - to capture segments of user behavior based on the user actions of views, purchases, add to cart, start checkout",
            goal="I want to generate a dashboard to analyze funnel performance across different user segments with my event data",
            dataset_path="/Users/sameerm/self-learn-agents/data/inputs/bv_finance_flux_final.csv",
        )
    agent = FunnelAnalysisAgent(llm,functions_vectorstore,examples_vectorstore,insights_vectorstore)
    dataframe_description = {}
    dataframe_summary = summarize_agent.summarize_dataframe(dataframe=events_df, question="How do I analyze funnel performance across different user segments with my event data based on the user actions of views, purchases, add to cart, checkout?", state=state)    
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
    po_df = pd.read_csv("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/ai-report/app/bv_finance_flux_final.csv")
    print(po_df.head())
    state = InsightManagerState(
            question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            context="Objective - to capture Variance of flux over time for each group of projects, cost centers, and departments",
            goal="I want to generate a dashboard to analyze flux analysis performance across different segments with my po data when it drops more than 10%",
            dataset_path="/Users/sameerm/self-learn-agents/data/inputs/bv_finance_flux_final.csv",
    )
    dataframe_summary = summarize_agent.summarize_dataframe(dataframe=events_df, question=query, state=state)    
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
        enable_code_generation=False
    )
    
    # Example 2: Intent classification with code generation
    print("\n2. Intent classification with code generation:")
    result2 = analyze_question_with_intent_classification(
        question="Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns by region and project",
        dataframe=po_df,
        dataframe_description="Financial flux data with project, cost center, and department information",
        dataframe_summary="Dataset contains flux values over time with grouping dimensions",
        columns_description=columns_description,
        enable_code_generation=False,
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
        enable_code_generation=False,
        context="Calculate mean daily transactional values",
        dataframe_name="Purchase Orders Data"
    )
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


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