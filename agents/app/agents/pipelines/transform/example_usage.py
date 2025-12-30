"""
Example Usage of Transformation Pipeline

This module demonstrates how to use the TransformationPipeline for:
1. Feature recommendation based on user queries
2. Feature selection and registry management
3. Pipeline generation for selected features

This matches the chat-based UX flow shown in CompletePipelineWithExport.jsx
"""

import asyncio
import logging
from app.agents.pipelines.transform import (
    TransformationPipeline,
    FeatureRecommendationRequest,
    PipelineGenerationRequest
)
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_feature_recommendation():
    """Example: Generate feature recommendations from a user query"""
    
    # Initialize pipeline
    retrieval_helper = RetrievalHelper()
    pipeline = TransformationPipeline(
        llm=get_llm(temperature=0, model="gpt-4o-mini"),
        retrieval_helper=retrieval_helper
    )
    
    await pipeline.initialize()
    
    # Create recommendation request (matches UX chat input)
    request = FeatureRecommendationRequest(
        user_query="""
        Create a report for Snyk that looks at the Critical and High vulnerabilities 
        for SOC2 compliance and provides risk, impact and likelihood metrics. I need to know SLAs, Repos, and Exploitability of the 
        vulnerabilities. Critical = 7 Days, High = 30 days since created and open and their risks.
        """,
        project_id="cve_data",
        domain="cybersecurity",
        include_risk_features=True,
        include_impact_features=True,
        include_likelihood_features=True
    )
    
    # Get recommendations
    response = await pipeline.recommend_features(request)
    
    if response.success:
        print(f"✅ Generated {len(response.recommended_features)} feature recommendations")
        print(f"📋 Clarifying questions: {len(response.clarifying_questions)}")
        print(f"📊 Relevant schemas: {response.relevant_schemas}")
        
        # Display first few recommendations
        for i, feature in enumerate(response.recommended_features[:3], 1):
            print(f"\n{i}. {feature.feature_name}")
            print(f"   Question: {feature.natural_language_question}")
            print(f"   Layer: {feature.transformation_layer}")
            print(f"   Score: {feature.recommendation_score}")
        
        # Return context for next steps
        return response.conversation_context
    else:
        print(f"❌ Error: {response.error}")
        return None


async def example_feature_selection(conversation_context, feature_ids):
    """Example: Select features from recommendations"""
    
    # Initialize pipeline (same instance or new)
    pipeline = TransformationPipeline()
    await pipeline.initialize()
    
    # Select features (matches UX checkbox selection)
    result = await pipeline.select_features(
        feature_ids=feature_ids,
        conversation_context=conversation_context
    )
    
    if result["success"]:
        print(f"✅ Selected {len(result['selected_features'])} features")
        for feature in result["selected_features"]:
            print(f"   - {feature['feature_name']} ({feature['status']})")
        
        return result["conversation_context"]
    else:
        print("❌ Failed to select features")
        return None


async def example_pipeline_generation(conversation_context, selected_feature_ids):
    """Example: Generate transformation pipelines for selected features"""
    
    # Initialize pipeline
    pipeline = TransformationPipeline()
    await pipeline.initialize()
    
    # Create pipeline generation request
    request = PipelineGenerationRequest(
        feature_ids=selected_feature_ids,
        conversation_context=conversation_context,
        export_format="dbt",  # or "airflow", "databricks", "sql"
        include_dependencies=True
    )
    
    # Generate pipelines
    response = await pipeline.generate_pipelines(request)
    
    if response.success:
        print(f"✅ Generated pipelines for {len(response.pipelines)} features")
        print(f"📦 Execution order: {response.execution_order}")
        
        # Display pipeline structure for first feature
        if response.pipelines:
            first_feature_id = list(response.pipelines.keys())[0]
            pipeline_data = response.pipelines[first_feature_id]
            
            print(f"\n📊 Pipeline for: {pipeline_data['feature_name']}")
            print(f"   Transformation Layer: {pipeline_data['transformation_layer']}")
            
            if pipeline_data.get("silver_pipeline"):
                silver = pipeline_data["silver_pipeline"]
                print(f"   Silver Pipeline:")
                print(f"     Source: {[t['name'] for t in silver['source_tables']]}")
                print(f"     Destination: {silver['destination_table']['name']}")
            
            if pipeline_data.get("gold_pipeline"):
                gold = pipeline_data["gold_pipeline"]
                print(f"   Gold Pipeline:")
                print(f"     Source: {[t['name'] for t in gold['source_tables']]}")
                print(f"     Destination: {gold['destination_table']['name']}")
        
        return response
    else:
        print(f"❌ Error: {response.error}")
        return None


async def example_complete_workflow():
    """Example: Complete workflow from query to pipeline generation"""
    
    # Initialize pipeline once for the entire workflow
    retrieval_helper = RetrievalHelper()
    pipeline = TransformationPipeline(
        llm=get_llm(temperature=0, model="gpt-4o-mini"),
        retrieval_helper=retrieval_helper
    )
    await pipeline.initialize()
    
    print("=" * 80)
    print("Transformation Pipeline - Complete Workflow Example")
    print("=" * 80)
    
    # Step 1: Get recommendations
    print("\n📝 Step 1: Feature Recommendation")
    print("-" * 80)
    request = FeatureRecommendationRequest(
        user_query="""
        Create a report for Snyk that looks at the Critical and High vulnerabilities 
        for SOC2 compliance and provides risk, impact and likelihood metrics.
        """,
        project_id="cve_data",
        domain="cybersecurity"
    )
    response = await pipeline.recommend_features(request)
    
    if not response.success or not response.conversation_context:
        print(f"❌ Failed to get recommendations: {response.error}")
        return
    
    context = response.conversation_context
    
    # Step 2: Select features (simulate user selecting first 3 features)
    print("\n\n✅ Step 2: Feature Selection")
    print("-" * 80)
    feature_ids = list(context.feature_registry.keys())[:3]  # Select first 3
    select_result = await pipeline.select_features(feature_ids, context)
    
    if not select_result["success"]:
        print("❌ Failed to select features")
        return
    
    updated_context = select_result["conversation_context"]
    
    # Step 3: Generate pipelines
    print("\n\n🔧 Step 3: Pipeline Generation")
    print("-" * 80)
    pipeline_request = PipelineGenerationRequest(
        feature_ids=feature_ids,
        conversation_context=updated_context,
        export_format="dbt",
        include_dependencies=True
    )
    pipeline_response = await pipeline.generate_pipelines(pipeline_request)
    
    if pipeline_response.success:
        print("\n\n✅ Complete workflow finished successfully!")
        print("=" * 80)
        
        # Display metrics
        metrics = pipeline.get_metrics()
        print(f"\n📊 Pipeline Metrics:")
        print(f"   Total Recommendations: {metrics['total_recommendations']}")
        print(f"   Total Selections: {metrics['total_selections']}")
        print(f"   Total Pipelines Generated: {metrics['total_pipelines_generated']}")
        print(f"   Average Recommendation Score: {metrics['average_recommendation_score']:.2f}")


async def example_using_run_method():
    """Example: Using the pipeline.run() method directly"""
    
    pipeline = TransformationPipeline()
    await pipeline.initialize()
    
    # Recommend features using run method
    result = await pipeline.run(
        operation="recommend",
        user_query="I need SOC2 vulnerability features",
        project_id="cve_data",
        domain="cybersecurity"
    )
    
    print(f"Success: {result['success']}")
    print(f"Recommended Features: {len(result['recommended_features'])}")
    
    # Select features using run method
    if result['success'] and result['recommended_features']:
        feature_ids = [f['feature_id'] for f in result['recommended_features'][:2]]
        context = pipeline.get_conversation_context("cve_data", "cybersecurity")
        
        if context:
            select_result = await pipeline.run(
                operation="select",
                feature_ids=feature_ids,
                conversation_context=context
            )
            print(f"Selection Success: {select_result['success']}")


if __name__ == "__main__":
    # Run the complete workflow example
    asyncio.run(example_complete_workflow())
    
    # Or run individual examples:
    # asyncio.run(example_feature_recommendation())
    # asyncio.run(example_using_run_method())

