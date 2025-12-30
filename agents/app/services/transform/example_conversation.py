"""
Example: Feature Conversation Service Usage

This demonstrates a complete conversation flow:
1. Ask for feature recommendations
2. Select features
3. Ask for more features (context maintained)
4. Select more features
5. Save all selected features to file
"""

import asyncio
import logging
from app.services.transform import (
    FeatureConversationService,
    FeatureConversationRequest
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_streaming_conversation():
    """Example: Streaming conversation with multiple turns"""
    
    service = FeatureConversationService()
    
    print("=" * 80)
    print("Feature Conversation Service - Streaming Example")
    print("=" * 80)
    
    # Turn 1: Initial feature recommendation
    print("\n📝 Turn 1: Requesting SOC2 vulnerability features")
    print("-" * 80)
    
    request1 = FeatureConversationRequest(
        user_query="""
        Create a report for Snyk that looks at the Critical and High vulnerabilities 
        for SOC2 compliance. I need to know SLAs, Repos, and Exploitability.
        Critical = 7 Days, High = 30 days since created and open.
        """,
        project_id="cve_data",
        domain="cybersecurity",
        action="recommend"
    )
    
    print("Streaming recommendations...")
    async for update in service.process_request_with_streaming(request1):
        status = update.get("status")
        if status == "recommending":
            total = update.get("total_found", 0)
            current_batch = update.get("current_batch", 0)
            total_batches = update.get("total_batches", 0)
            print(f"  📊 Found {total} features (batch {current_batch}/{total_batches})")
        elif status == "finished":
            features = update.get("recommended_features", [])
            print(f"  ✅ Generated {len(features)} feature recommendations")
            print(f"  📋 First 3 features:")
            for i, feature in enumerate(features[:3], 1):
                print(f"     {i}. {feature['feature_name']}")
            break
        elif status == "error":
            print(f"  ❌ Error: {update.get('error')}")
            return
    
    # Get the response
    response1 = await service.process_request(request1)
    if response1.status != "finished":
        print(f"Failed: {response1.error}")
        return
    
    # Turn 2: Select some features
    print("\n\n✅ Turn 2: Selecting first 3 features")
    print("-" * 80)
    
    selected_ids = [f["feature_id"] for f in response1.recommended_features[:3]]
    select_request = FeatureConversationRequest(
        query_id=response1.query_id,
        project_id="cve_data",
        domain="cybersecurity",
        action="select",
        selected_feature_ids=selected_ids
    )
    
    select_response = await service.process_request(select_request)
    if select_response.status == "finished":
        print(f"  ✅ Selected {select_response.total_selected} features")
        for feature in select_response.selected_features:
            print(f"     - {feature['feature_name']}")
    
    # Turn 3: Ask for more features (context maintained)
    print("\n\n📝 Turn 3: Requesting risk scoring features")
    print("-" * 80)
    
    request2 = FeatureConversationRequest(
        user_query="Now I need risk scoring features that calculate risk, impact and likelihood metrics",
        project_id="cve_data",  # Same project_id maintains context
        domain="cybersecurity",
        action="recommend"
    )
    
    print("Streaming recommendations...")
    async for update in service.process_request_with_streaming(request2):
        status = update.get("status")
        if status == "recommending":
            total = update.get("total_found", 0)
            print(f"  📊 Found {total} features so far...")
        elif status == "finished":
            features = update.get("recommended_features", [])
            print(f"  ✅ Generated {len(features)} additional feature recommendations")
            break
    
    response2 = await service.process_request(request2)
    if response2.status != "finished":
        print(f"Failed: {response2.error}")
        return
    
    # Turn 4: Select more features
    print("\n\n✅ Turn 4: Selecting 2 more features")
    print("-" * 80)
    
    selected_ids2 = [f["feature_id"] for f in response2.recommended_features[:2]]
    select_request2 = FeatureConversationRequest(
        query_id=response2.query_id,
        project_id="cve_data",
        domain="cybersecurity",
        action="select",
        selected_feature_ids=selected_ids2
    )
    
    select_response2 = await service.process_request(select_request2)
    if select_response2.status == "finished":
        print(f"  ✅ Selected {len(select_response2.selected_features)} more features")
        print(f"  📊 Total selected: {select_response2.total_selected}")
    
    # Turn 5: Save all selected features
    print("\n\n💾 Turn 5: Saving all selected features")
    print("-" * 80)
    
    save_request = FeatureConversationRequest(
        query_id=response2.query_id,
        project_id="cve_data",
        domain="cybersecurity",
        action="save"
        # save_path is optional - will generate default if not provided
    )
    
    save_response = await service.process_request(save_request)
    if save_response.status == "finished":
        print(f"  ✅ {save_response.message}")
    
    # Check conversation state
    print("\n\n📊 Conversation State")
    print("-" * 80)
    state = service.get_conversation_state("cve_data", "cybersecurity")
    if state:
        print(f"  Total Queries: {state['total_queries']}")
        print(f"  Total Features in Registry: {state['total_features']}")
        print(f"  Selected Features: {state['selected_features']}")
        print(f"  Compliance Framework: {state.get('compliance_framework', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("✅ Conversation completed successfully!")
    print("=" * 80)


async def example_simple_conversation():
    """Example: Simple non-streaming conversation"""
    
    service = FeatureConversationService()
    
    # Request features
    request = FeatureConversationRequest(
        user_query="I need SOC2 vulnerability features",
        project_id="cve_data",
        domain="cybersecurity",
        action="recommend"
    )
    
    response = await service.process_request(request)
    
    if response.status == "finished":
        print(f"Generated {len(response.recommended_features)} features")
        
        # Select first 2
        if response.recommended_features:
            select_request = FeatureConversationRequest(
                query_id=response.query_id,
                project_id="cve_data",
                domain="cybersecurity",
                action="select",
                selected_feature_ids=[f["feature_id"] for f in response.recommended_features[:2]]
            )
            
            select_response = await service.process_request(select_request)
            print(f"Selected {select_response.total_selected} features")
            
            # Save
            save_request = FeatureConversationRequest(
                query_id=response.query_id,
                project_id="cve_data",
                domain="cybersecurity",
                action="save"
            )
            
            save_response = await service.process_request(save_request)
            print(f"Saved: {save_response.message}")


if __name__ == "__main__":
    # Run the streaming conversation example
    asyncio.run(example_streaming_conversation())
    
    # Or run the simple example:
    # asyncio.run(example_simple_conversation())

