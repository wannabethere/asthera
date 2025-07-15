import pandas as pd
import os
import numpy as np
import asyncio
from datetime import datetime, timedelta
import chromadb
from langchain_openai import ChatOpenAI
from app.storage.documents import DocumentChromaStore, create_langchain_doc_util
from app.core.settings import get_settings
from app.agents.nodes.mlagents.funnelanalysis_node import FunnelAnalysisAgent,retrieve_function_definition, retrieve_function_examples
from app.agents.nodes.mlagents.selfrag_mltool_pipeline import SelfCorrectingForwardPlanner
from app.agents.nodes.recommenders.ds_agents import SummarizeDatasetAgent
from app.agents.models.dsmodels import InsightManagerState
from app.agents.nodes.logical_planners import DataScienceLogicalPlanner
from app.agents.nodes.mlagents.generalized_pipeline_planner import GeneralizedAnalysisAgent
from tests.mlagents.sample_purchase_order_data import demonstrate_purchase_order_analysis

settings = get_settings()
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH

os.environ["OPENAI_API_KEY"] = "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"

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

def create_sample_purchase_order_data(num_orders=500):
    """Create a sample purchase order dataset for demonstration"""
    # Create order IDs
    df = demonstrate_purchase_order_analysis()
    return df
    # Lists to store order data

async def run_advanced_logical_plan_example():
    """
    Advanced example with more complex multi-step analysis using the actual DataScienceLogicalPlanner
    """
    
    print("\n🔬 ADVANCED LOGICAL PLAN EXAMPLE")
    print("=" * 60)
    
    # Initialize the actual DataScienceLogicalPlanner
    print("Initializing DataScienceLogicalPlanner...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
    examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_examples_collection")
    functions_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_spec_collection")
    insights_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_insights_collection")
    
    planner = DataScienceLogicalPlanner(
        llm=llm,
        examples_vectorstore=examples_vectorstore,
        functions_vectorstore=functions_vectorstore,
        insights_vectorstore=insights_vectorstore
    )
    
    # Test different types of analysis questions
    test_cases = [
        {
            "name": "Funnel Analysis",
            "question": "How do I analyze funnel performance across different user segments with my event data based on the user actions of views, purchases, add to cart, checkout?",
            "context": {
                "dataset_description": "Event dataset with user actions of views, purchases, add to cart, checkout",
                "columns": ["event_name", "user_id", "event_date", "event_value", "event_segment", "event_type"],
                "dataframe": {
                    "name": "events_df",
                    "rows": 50000,
                    "columns": ["event_name", "user_id", "event_date", "event_value", "event_segment", "event_type"]
                }
            },
            "planner_type": "funnel analysis"
        },
        {
            "name": "Cohort Analysis",
            "question": "How do I perform cohort analysis to understand user retention patterns over time based on the user activity type and date?",
            "context": {
                "dataset_description": "User activity dataset with signup dates and activity tracking",
                "columns": ["user_id", "signup_date", "activity_date", "user_segment", "activity_type"],
                "dataframe": {
                    "name": "user_activity_df",
                    "rows": 10000,
                    "columns": ["user_id", "signup_date", "activity_date", "user_segment", "activity_type"]
                }
            },
            "planner_type": "cohort analysis"
        },
        {
            "name": "Segmentation Analysis",
            "question": "How do I segment users based on their behavior patterns using page views and session duration and demographics?",
            "context": {
                "dataset_description": "User behavior dataset with demographics and activity metrics",
                "columns": ["user_id", "age", "gender", "location", "page_views", "session_duration", "purchase_amount"],
                "dataframe": {
                    "name": "user_behavior_df",
                    "rows": 15000,
                    "columns": ["user_id", "age", "gender", "location", "page_views", "session_duration", "purchase_amount"]
                }
            },
            "planner_type": "segmentation"
        },
        {
            "name": "Risk Analysis",
            "question": "How do I perform risk analysis on financial data to calculate Value at Risk (VaR) and portfolio risk metrics for price with 95% confidence?",
            "context": {
                "dataset_description": "Financial dataset with asset returns and portfolio weights",
                "columns": ["date", "asset_id", "returns", "price", "volume", "portfolio_weight"],
                "dataframe": {
                    "name": "financial_df",
                    "rows": 20000,
                    "columns": ["date", "asset_id", "returns", "price", "volume", "portfolio_weight"]
                }
            },
            "planner_type": "risk analysis"
        }
    ]
    
    results = {}
    
    for test_case in test_cases:
        print(f"\n📊 Testing {test_case['name']}...")
        print(f"Question: {test_case['question']}")
        print(f"Planner Type: {test_case['planner_type']}")
        
        try:
            # Run the actual planner
            result = await planner.plan(
                question=test_case['question'],
                context=test_case['context'],
                planner_type=test_case['planner_type']
            )
            
            # Store results
            results[test_case['name']] = result
            
            # Print results
            print(f"\n✅ {test_case['name']} Planning Results:")
            print(f"   Relevance Score: {result['relevance_score']:.3f}")
            print(f"   Plan Steps: {len(result['plan'])}")
            print(f"   Detected Operation Type: {result['relevance_components'].get('detected_operation_type', 'Unknown')}")
            
            print(f"\n📋 Plan Steps:")
            for i, step in enumerate(result['plan'], 1):
                print(f"   {i}. {step}")
            
            print(f"\n🔍 Relevance Components:")
            for component, score in result['relevance_components'].items():
                if isinstance(score, (int, float)):
                    print(f"   {component}: {score:.3f}")
                else:
                    print(f"   {component}: {score}")
            
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(result['recommendations'], 1):
                print(f"   {i}. {rec}")
            
        except Exception as e:
            print(f"❌ Error in {test_case['name']}: {str(e)}")
            results[test_case['name']] = {"error": str(e)}
    
    return results

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
    client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
    print("client",CHROMA_STORE_PATH)
    examples_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_examples_collection")
    functions_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_spec_collection")
    insights_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_insights_collection")

    print("--------------------------------")
    print("Creating sample purchase order data...")
    po_df = create_sample_purchase_order_data()
    print(f"Created dataset with {len(po_df)} purchase orders")
    print(po_df.head())
    
    print("--------------------------------")
    print("Creating sample event data...")
    events_df = create_sample_event_data()
    print(f"Created dataset with {len(events_df)} events from {events_df['user_id'].nunique()} users")

async def run_logical_planner_tests():
    """Run the logical planner tests"""
    print("🚀 LOGICAL PLANNER TESTS")
    print("=" * 60)
    
    # Run the advanced logical plan example
    results = await run_advanced_logical_plan_example()
    
    print(f"\n🎉 All tests completed!")
    print(f"   ✓ Tested {len(results)} different analysis types")
    print(f"   ✓ Used actual DataScienceLogicalPlanner")
    print(f"   ✓ Generated plans with relevance scoring")
    
    return results



async def run_with_logical_plan_example(llm,function_collection, example_collection, insights_collection):
    """
    Example function demonstrating how to use the GeneralizedAnalysisAgent
    with a sample logical plan output
    """
    
    print("🚀 LOGICAL PLAN PROCESSING EXAMPLE")
    print("=" * 60)
    
   
    # Create mock agent
   
    
    agent = GeneralizedAnalysisAgent(
        llm=llm,
        function_collection=function_collection,
        example_collection=example_collection,
        insights_collection=insights_collection
    )
    
    planner = DataScienceLogicalPlanner(
        llm=llm,
        examples_vectorstore=examples_vectorstore,
        functions_vectorstore=functions_vectorstore,
        insights_vectorstore=insights_vectorstore
    )
    
    # Test different types of analysis questions
    test_cases = [
        {
            "name": "Funnel Analysis",
            "question": "How do I analyze funnel performance across different user segments with my event data based on the user actions of views, purchases, add to cart, checkout?",
            "context": {
                "dataset_description": "Event dataset with user actions of views, purchases, add to cart, checkout",
                "columns": ["event_name", "user_id", "event_date", "event_value", "event_segment", "event_type"],
                "dataframe": {
                    "name": "events_df",
                    "rows": 50000,
                    "columns": ["event_name", "user_id", "event_date", "event_value", "event_segment", "event_type"]
                }
            },
            "planner_type": "funnel analysis"
        },
        {
            "name": "Cohort Analysis",
            "question": "How do I perform cohort analysis to understand user retention patterns over time based on the user activity type and date?",
            "context": {
                "dataset_description": "User activity dataset with signup dates and activity tracking",
                "columns": ["user_id", "signup_date", "activity_date", "user_segment", "activity_type"],
                "dataframe": {
                    "name": "user_activity_df",
                    "rows": 10000,
                    "columns": ["user_id", "signup_date", "activity_date", "user_segment", "activity_type"]
                }
            },
            "planner_type": "cohort analysis"
        },
        {
            "name": "Segmentation Analysis",
            "question": "How do I segment users based on their behavior patterns using page views and session duration and demographics?",
            "context": {
                "dataset_description": "User behavior dataset with demographics and activity metrics",
                "columns": ["user_id", "age", "gender", "location", "page_views", "session_duration", "purchase_amount"],
                "dataframe": {
                    "name": "user_behavior_df",
                    "rows": 15000,
                    "columns": ["user_id", "age", "gender", "location", "page_views", "session_duration", "purchase_amount"]
                }
            },
            "planner_type": "segmentation"
        },
        {
            "name": "Risk Analysis",
            "question": "How do I perform risk analysis on financial data to calculate Value at Risk (VaR) and portfolio risk metrics for price with 95% confidence?",
            "context": {
                "dataset_description": "Financial dataset with asset returns and portfolio weights",
                "columns": ["date", "asset_id", "returns", "price", "volume", "portfolio_weight"],
                "dataframe": {
                    "name": "financial_df",
                    "rows": 20000,
                    "columns": ["date", "asset_id", "returns", "price", "volume", "portfolio_weight"]
                }
            },
            "planner_type": "risk analysis"
        }
    ]
    
    results = {}
    
    for test_case in test_cases:
        print(f"\n📊 Testing {test_case['name']}...")
        print(f"Question: {test_case['question']}")
        print(f"Planner Type: {test_case['planner_type']}")
        
        try:
            # Run the actual planner
            result = await planner.plan(
                question=test_case['question'],
                context=test_case['context'],
                planner_type=test_case['planner_type']
            )
            
            # Store results
            results[test_case['name']] = result
            
            # Print results
            print(f"\n✅ {test_case['name']} Planning Results:")
            print(f"   Relevance Score: {result['relevance_score']:.3f}")
            print(f"   Plan Steps: {len(result['plan'])}")
            print(f"   Detected Operation Type: {result['relevance_components'].get('detected_operation_type', 'Unknown')}")
            print(f"\n📋 Plan Steps:")
            for i, step in enumerate(result['plan'], 1):
                print(f"   {i}. {step}")
            
            print(f"\n🔍 Relevance Components:")
            for component, score in result['relevance_components'].items():
                if isinstance(score, (int, float)):
                    print(f"   {component}: {score:.3f}")
                else:
                    print(f"   {component}: {score}")
            
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(result['recommendations'], 1):
                print(f"   {i}. {rec}")
            # Run the agent
            try:
                # Convert plan list to pipe-separated string format expected by agent.run()
                logical_plan_string = ' | '.join(result['plan'])
                
                # Create proper dataframe description with schema information
                dataframe_description = {
                    'schema': {col: 'object' for col in test_case['context']['dataframe']['columns']},
                    'summary': test_case['context']['dataset_description'],
                    'columns': test_case['context']['dataframe']['columns']
                }
                
                print(f"\n🔄 Processing with GeneralizedAnalysisAgent...")
                print(f"   Logical Plan: {logical_plan_string[:200]}...")
                print(f"   Columns: {test_case['context']['dataframe']['columns']}")
                
                job_result = agent.run(
                    logical_plan_output=logical_plan_string,
                    dataframe_columns=test_case['context']['dataframe']['columns'],
                    dataframe_description=dataframe_description
                )
                
                print("\n✅ Processing completed successfully!")
                
                for key, value in job_result.items():
                    print(f"--------------{key}------------------")
                    print(f"{value}")
                    print("--------------------------------")
                
            except Exception as e:
                print(f"\n❌ Error during processing: {str(e)}")
                return {
                    "error": str(e),
                    "original_plan": result['plan'],
                    "status": "failed"
                }
            
            
        except Exception as e:
            print(f"❌ Error in {test_case['name']}: {str(e)}")
            results[test_case['name']] = {"error": str(e)}
    
    

if __name__ == "__main__":
    # Run the logical planner tests
    print("\nInitializing Funnel Analysis Agent...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
    print("client",CHROMA_STORE_PATH)
    examples_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_examples_collection")
    functions_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_spec_collection")
    insights_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_insights_collection")
    asyncio.run(run_logical_planner_tests())
    asyncio.run(run_with_logical_plan_example(llm,functions_vectorstore, examples_vectorstore, insights_vectorstore))