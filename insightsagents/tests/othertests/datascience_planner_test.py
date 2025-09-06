import asyncio
import json
import os
from pathlib import Path
from app.core.settings import get_settings
# Import the logical planner
from app.agents.nodes.logical_planners import DataScienceLogicalPlanner, OperationTerminologyConfig
settings = get_settings()
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH
os.environ["OPENAI_API_KEY"] = "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"
# Create an example configuration file
def create_example_config_file(file_path):
    """Create an example configuration file with custom operation terms"""
    
    # Define a custom configuration
    custom_config = {
        "reasoning_weight": 0.7,
        "terminology_value": 0.03,
        "length_score_thresholds": {
            "long": {"threshold": 50, "score": 0.20},
            "medium": {"threshold": 25, "score": 0.15},
            "short": {"threshold": 10, "score": 0.10},
            "very_short": {"score": 0.05}
        },
        "operations": {
            "cohort_analysis": {
                "terms": [
                    "cohort", "retention", "churn", "lifetime value", "ltv", 
                    "CohortPipe", "from_dataframe", "calculate_lifetime_value",
                    "form_behavioral_cohorts", "behavior_column", "cohort_column",
                    "date_column", "user_id_column", "value_column", "time_period",
                    "max_periods", "cumulative", "transactions_df"
                ],
                "max_score": 0.30,
                "min_match_threshold": 2
            },
            "segmentation": {
                "terms": [
                    "segmentation", "clustering", "kmeans", "dbscan", "hierarchical",
                    "SegmentationPipe", "from_dataframe", "get_features", "run_kmeans",
                    "run_dbscan", "run_hierarchical", "compare_algorithms", "n_clusters",
                    "eps", "min_samples", "linkage", "ward", "segment_name"
                ],
                "max_score": 0.30,
                "min_match_threshold": 2
            }
        },
        "pipeline_indicators": [
            r"pipe(?:line)?", r"sequential", r"\|", r"output.*feeds into",
            r"CohortPipe", r"SegmentationPipe", r"from_dataframe",
            r"calculate_lifetime_value", r"form_behavioral_cohorts",
            r"get_features", r"run_kmeans", r"run_dbscan", r"run_hierarchical",
            r"compare_algorithms"
        ],
        "pipeline_score_value": 0.06,
        "pipeline_max_score": 0.30
    }
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Write the configuration to file
    with open(file_path, 'w') as f:
        json.dump(custom_config, f, indent=2)
    
    print(f"Example configuration file created at: {file_path}")

async def run_example():
    """Run an example using the DataScienceLogicalPlanner with custom configuration"""
    
    # Create the example configuration file
    config_path = "configs/operation_terminology.json"
    create_example_config_file(config_path)
    
    # Initialize the planner with the custom configuration
    planner = DataScienceLogicalPlanner()
    
    # Example input for cohort analysis
    cohort_question = """
    How can I analyze customer retention and lifetime value using the CohortPipe method with this syntax:
    
    CohortPipe.from_dataframe(transactions_df)
    | form_behavioral_cohorts(
        behavior_column='value_segment',
        cohort_column='value_segment_cohort'
    )
    | calculate_lifetime_value(
        cohort_column='value_segment_cohort',
        date_column='transaction_date',
        user_id_column='user_id',
        value_column='amount',
        time_period='M',
        max_periods=6,
        cumulative=True
    )
    """
    
    cohort_context = {
        "dataset_description": "E-commerce transaction dataset with customer purchase history",
        "columns": [
            "transaction_id", "user_id", "transaction_date", "amount", 
            "product_id", "category", "value_segment"
        ],
        "dataframe": {
            "name": "transactions_df",
            "rows": 50000,
            "columns": [
                "transaction_id", "user_id", "transaction_date", "amount", 
                "product_id", "category", "value_segment"
            ]
        }
    }
    
    cohort_planner_type = "cohort analysis planner"
    
    # Run the planner for cohort analysis
    print("Running planner for cohort analysis...")
    cohort_result = await planner.plan(cohort_question, cohort_context, cohort_planner_type)
    
    # Print the cohort analysis results
    print("\n" + "="*50)
    print("COHORT ANALYSIS PLANNING RESULTS")
    print("="*50)
    print(f"Question: {cohort_result['question']}")
    
    print(f"\nDetected Operation Type: {cohort_result['relevance_components']['detected_operation_type']}")
    
    print(f"\nExtracted Reasoning (excerpt):")
    reasoning = cohort_result['extracted_reasoning']
    print(reasoning[:300] + "..." if len(reasoning) > 300 else reasoning)
    
    print(f"\nPlan ({len(cohort_result['plan'])} steps):")
    for i, step in enumerate(cohort_result['plan']):
        print(f"{i+1}. {step}")
    
    print("\nRelevance Score Components:")
    for component, score in cohort_result['relevance_components'].items():
        if isinstance(score, float):
            print(f"{component}: {score:.2f}")
        else:
            print(f"{component}: {score}")
    
    print(f"\nOverall Relevance Score: {cohort_result['relevance_score']:.2f}")
    
    # Example input for segmentation
    # Identify which combination of cost centers, project codes, and countries contribute to 85% of flux variance for accrued, invoiced, and paid amounts in the last 12 months.
    #
    #Calculate daily returns for each stock using the formula: (current day's price - previous day's price) / previous day's price
    segmentation_question = """
     How do daily returns, their short-term volatility, and their cumulative distribution evolve over the last 12 months for each stock, based on historical price and volume data?   
    """
    
    segmentation_context = {
        "dataset_description": "Stock dataset with stock, price, volume, and date",
        "features": [
            "define the features"    
        ],
        "dataframe": {
            "name": "df",
            "rows": 10000,
            "columns": [
                "stock", "price", "volume","date"
            ]
        },
        
    }
    
    segmentation_planner_type = "segmentation analysis planner"
    
    # Run the planner for segmentation
    print("\nRunning planner for segmentation...")
    segmentation_result = await planner.plan(segmentation_question, segmentation_context, segmentation_planner_type)
    
    # Print the segmentation results
    print("\n" + "="*50)
    print("SEGMENTATION ANALYSIS PLANNING RESULTS")
    print("="*50)
    print(f"Question: {segmentation_result['question']}")
    
    print(f"\nDetected Operation Type: {segmentation_result['relevance_components']['detected_operation_type']}")
    
    print(f"\nExtracted Reasoning (excerpt):")
    reasoning = segmentation_result['extracted_reasoning']
    print(reasoning[:300] + "..." if len(reasoning) > 300 else reasoning)
    
    print(f"\nPlan ({len(segmentation_result['plan'])} steps):")
    for i, step in enumerate(segmentation_result['plan']):
        print(f"{i+1}. {step}")
    
    print("\nRelevance Score Components:")
    for component, score in segmentation_result['relevance_components'].items():
        if isinstance(score, float):
            print(f"{component}: {score:.2f}")
        else:
            print(f"{component}: {score}")
    
    print(f"\nOverall Relevance Score: {segmentation_result['relevance_score']:.2f}")


    print("--------------------------------")
    print("\nRunning planner for funnel analysis...")
    funnel_analysis_question = """
    How do I analyze funnel performance across different user segments with my event data based on the user actions of views, purchases, add to cart, checkout?
    """
    funnel_analysis_context = {
       "dataset_description": "Event dataset with user actions of views, purchases, add to cart, checkout",
        "columns": [
            "event_name", "user_id", "event_date", "event_value", 
            "event_segment", "event_type"
        ],
        "dataframe": {
            "name": "transactions_df",
            "rows": 50000,
            "columns": [
                "transaction_id", "user_id", "transaction_date", "amount", 
                "product_id", "category", "value_segment"
            ]
        }
    }
    segmentation_result = await planner.plan(funnel_analysis_question, funnel_analysis_context, segmentation_planner_type)
    # Print the segmentation results
    print("\n" + "="*50)
    print("FUNNEL ANALYSIS PLANNING RESULTS")
    print("="*50)
    print(f"Question: {segmentation_result['question']}")
    
    print(f"\nDetected Operation Type: {segmentation_result['relevance_components']['detected_operation_type']}")
    
    print(f"\nExtracted Reasoning (excerpt):")
    reasoning = segmentation_result['extracted_reasoning']
    print(reasoning[:300] + "..." if len(reasoning) > 300 else reasoning)
    
    print(f"\nPlan ({len(segmentation_result['plan'])} steps):")
    for i, step in enumerate(segmentation_result['plan']):
        print(f"{i+1}. {step}")
    
    print("\nRelevance Score Components:")
    for component, score in segmentation_result['relevance_components'].items():
        if isinstance(score, float):
            print(f"{component}: {score:.2f}")
        else:
            print(f"{component}: {score}")
    
    print(f"\nOverall Relevance Score: {segmentation_result['relevance_score']:.2f}")






if __name__ == "__main__":
    # Run the example
    asyncio.run(run_example())