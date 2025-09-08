#!/usr/bin/env python3
"""
Workflow Dashboard Integration Examples

This file demonstrates how to use the dashboard service with workflow database models.
It shows the complete flow from workflow creation to dashboard rendering.
"""

import asyncio
import logging
from typing import Dict, Any
from uuid import UUID, uuid4

# Usage Example for Workflow Dashboard Integration

async def example_workflow_dashboard_integration():
    """Example usage of the Workflow Dashboard Integration"""
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.services.writers.dashboard_service import DashboardService
    from app.services.workflow_integration import WorkflowIntegrationService
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
        print(f"   Engine Type: {settings.ENGINE_TYPE}")
        print(f"   Database: {settings.POSTGRES_DB} on {settings.POSTGRES_HOST}")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Initialize dashboard service
    dashboard_service = DashboardService()
    
    # Initialize workflow integration service
    workflow_integration = WorkflowIntegrationService()
    
    # Sample workflow ID (in production, this would come from the database)
    workflow_id = str(uuid4())
    project_id = "workflow_integration_test"
    
    print(f"🚀 Testing Workflow Dashboard Integration")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   Project ID: {project_id}")
    
    # Status callback for workflow updates
    def workflow_status_callback(status: str, details: Dict[str, Any]):
        """Handle status updates from workflow processing"""
        print(f"🔄 Workflow Status: {status}")
        if details:
            print(f"   Details: {details}")
    
    try:
        # Example 1: Render dashboard from workflow database model
        print("\n=== Example 1: Render Dashboard from Workflow Database ===")
        
        result = await dashboard_service.render_dashboard_from_workflow_db(
            workflow_id=workflow_id,
            project_id=project_id,
            natural_language_query="Highlight high-performing regions in green and low-performing ones in red",
            additional_context={"user_id": "user123", "session_id": "session456"},
            time_filters={"period": "last_quarter"},
            render_options={"mode": "full", "enable_caching": True},
            status_callback=workflow_status_callback
        )
        
        print(f"✅ Dashboard rendered successfully from workflow!")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Workflow ID: {result.get('workflow_metadata', {}).get('workflow_id')}")
        print(f"   Dashboard Template: {result.get('workflow_metadata', {}).get('dashboard_template')}")
        print(f"   Total Charts: {len(result.get('dashboard_data', {}).get('results', {}))}")
        
        # Example 2: Get workflow components
        print("\n=== Example 2: Get Workflow Components ===")
        
        components = await dashboard_service.get_workflow_components(workflow_id)
        print(f"✅ Retrieved {len(components)} workflow components")
        
        for i, component in enumerate(components[:3]):  # Show first 3
            print(f"   Component {i+1}: {component.get('component_type')} - {component.get('question', 'No question')[:50]}...")
        
        # Example 3: Get workflow status
        print("\n=== Example 3: Get Workflow Status ===")
        
        status = await dashboard_service.get_workflow_status(workflow_id)
        print(f"✅ Workflow status retrieved")
        print(f"   Status: {status.get('status')}")
        print(f"   State: {status.get('state')}")
        print(f"   Total Components: {status.get('total_components')}")
        print(f"   Dashboard Template: {status.get('dashboard_template')}")
        
        # Example 4: Preview dashboard from workflow
        print("\n=== Example 4: Preview Dashboard from Workflow ===")
        
        preview_result = await dashboard_service.preview_dashboard_from_workflow(
            workflow_id=workflow_id,
            preview_options={"max_queries": 2, "enable_caching": True}
        )
        
        print(f"✅ Dashboard preview generated")
        print(f"   Success: {preview_result.get('post_process', {}).get('success', False)}")
        print(f"   Preview Mode: {preview_result.get('preview_metadata', {}).get('preview_mode')}")
        print(f"   Queries Previewed: {preview_result.get('preview_metadata', {}).get('total_queries_previewed')}")
        
        return {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "dashboard_result": result,
            "components": components,
            "status": status,
            "preview_result": preview_result
        }
        
    except Exception as e:
        print(f"💥 Error in workflow dashboard integration: {e}")
        raise
    finally:
        # Cleanup
        await workflow_integration.close()


async def example_workflow_integration_service():
    """Example using the WorkflowIntegrationService directly"""
    
    print("\n=== Example: WorkflowIntegrationService Direct Usage ===")
    
    # Initialize workflow integration service
    workflow_integration = WorkflowIntegrationService()
    
    # Sample workflow ID
    workflow_id = str(uuid4())
    project_id = "integration_service_test"
    
    try:
        # Test workflow data fetching
        print(f"🔍 Testing workflow data fetching for {workflow_id}")
        
        workflow_data = await workflow_integration.fetch_workflow_from_db(workflow_id)
        
        if workflow_data:
            print(f"✅ Workflow data fetched successfully")
            print(f"   Workflow ID: {workflow_data.get('id')}")
            print(f"   State: {workflow_data.get('state')}")
            print(f"   Components: {len(workflow_data.get('thread_components', []))}")
        else:
            print(f"⚠️  Workflow not found (this is expected for test workflow ID)")
        
        # Test component fetching
        print(f"\n🔍 Testing component fetching for {workflow_id}")
        
        components = await workflow_integration.fetch_workflow_components(workflow_id)
        print(f"✅ Retrieved {len(components)} components")
        
        # Test status fetching
        print(f"\n🔍 Testing status fetching for {workflow_id}")
        
        status = await workflow_integration.get_workflow_status(workflow_id)
        print(f"✅ Status retrieved: {status.get('status')}")
        
        # Test dashboard rendering
        print(f"\n🔍 Testing dashboard rendering for {workflow_id}")
        
        render_result = await workflow_integration.render_dashboard_from_workflow(
            workflow_id=workflow_id,
            project_id=project_id,
            natural_language_query="Apply conditional formatting to highlight trends",
            additional_context={"test_mode": True},
            time_filters={"period": "last_month"},
            render_options={"mode": "preview"}
        )
        
        print(f"✅ Dashboard rendering result: {render_result.get('success')}")
        if render_result.get('success'):
            print(f"   Dashboard Queries: {len(render_result.get('dashboard_queries', []))}")
            print(f"   Dashboard Context: {bool(render_result.get('dashboard_context'))}")
        
        return {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "workflow_data": workflow_data,
            "components": components,
            "status": status,
            "render_result": render_result
        }
        
    except Exception as e:
        print(f"💥 Error in workflow integration service: {e}")
        raise
    finally:
        # Cleanup
        await workflow_integration.close()


async def example_api_endpoints():
    """Example showing how to use the API endpoints"""
    
    print("\n=== Example: API Endpoints Usage ===")
    
    # This would typically be done via HTTP requests to the API
    # For this example, we'll show the expected request/response format
    
    # Example 1: Render dashboard from workflow
    print("📡 POST /dashboard/render-from-workflow")
    print("   Request Body:")
    print("   {")
    print(f'     "workflow_id": "123e4567-e89b-12d3-a456-426614174000",')
    print(f'     "project_id": "api_test_project",')
    print(f'     "natural_language_query": "Highlight sales above $50,000 in green",')
    print(f'     "additional_context": {{"user_id": "user123"}},')
    print(f'     "time_filters": {{"period": "last_quarter"}},')
    print(f'     "render_options": {{"mode": "full", "enable_caching": true}}')
    print("   }")
    
    # Example 2: Get workflow components
    print("\n📡 GET /dashboard/workflow/{workflow_id}/components")
    print("   Response:")
    print("   {")
    print(f'     "workflow_id": "123e4567-e89b-12d3-a456-426614174000",')
    print(f'     "components": [')
    print(f'       {{')
    print(f'         "id": "component_1",')
    print(f'         "component_type": "chart",')
    print(f'         "question": "Show sales by region",')
    print(f'         "description": "Sales analysis by geographic region",')
    print(f'         "sequence_order": 1,')
    print(f'         "sql": "SELECT region, SUM(sales) FROM sales_data GROUP BY region",')
    print(f'         "chart_config": {{"type": "bar", "x_axis": "region", "y_axis": "sales"}}')
    print(f'       }}')
    print(f'     ],')
    print(f'     "total_components": 1')
    print("   }")
    
    # Example 3: Get workflow status
    print("\n📡 GET /dashboard/workflow/{workflow_id}/status")
    print("   Response:")
    print("   {")
    print(f'     "workflow_id": "123e4567-e89b-12d3-a456-426614174000",')
    print(f'     "status": "found",')
    print(f'     "state": "ACTIVE",')
    print(f'     "total_components": 3,')
    print(f'     "dashboard_template": "operational_dashboard",')
    print(f'     "last_updated": "2024-01-15T10:30:00Z",')
    print(f'     "created_at": "2024-01-15T09:00:00Z"')
    print("   }")
    
    # Example 4: Preview dashboard
    print("\n📡 POST /dashboard/workflow/{workflow_id}/preview")
    print("   Request Body:")
    print("   {")
    print(f'     "preview_options": {{"max_queries": 2, "enable_caching": true}}')
    print("   }")
    
    return {
        "message": "API endpoint examples shown",
        "endpoints": [
            "POST /dashboard/render-from-workflow",
            "GET /dashboard/workflow/{workflow_id}/components",
            "GET /dashboard/workflow/{workflow_id}/status",
            "POST /dashboard/workflow/{workflow_id}/preview"
        ]
    }


async def example_error_handling():
    """Example showing error handling scenarios"""
    
    print("\n=== Example: Error Handling ===")
    
    from app.services.writers.dashboard_service import DashboardService
    
    dashboard_service = DashboardService()
    
    # Test with invalid workflow ID
    invalid_workflow_id = "invalid-workflow-id"
    
    try:
        print(f"🔍 Testing with invalid workflow ID: {invalid_workflow_id}")
        
        result = await dashboard_service.render_dashboard_from_workflow_db(
            workflow_id=invalid_workflow_id,
            project_id="error_test"
        )
        
        print(f"❌ Unexpected success with invalid workflow ID")
        
    except Exception as e:
        print(f"✅ Expected error caught: {type(e).__name__}: {e}")
    
    # Test with empty workflow ID
    try:
        print(f"\n🔍 Testing with empty workflow ID")
        
        result = await dashboard_service.render_dashboard_from_workflow_db(
            workflow_id="",
            project_id="error_test"
        )
        
        print(f"❌ Unexpected success with empty workflow ID")
        
    except Exception as e:
        print(f"✅ Expected error caught: {type(e).__name__}: {e}")
    
    # Test workflow components with invalid ID
    try:
        print(f"\n🔍 Testing workflow components with invalid ID")
        
        components = await dashboard_service.get_workflow_components(invalid_workflow_id)
        print(f"✅ Components retrieved (empty for invalid ID): {len(components)}")
        
    except Exception as e:
        print(f"✅ Expected error caught: {type(e).__name__}: {e}")
    
    return {
        "message": "Error handling examples completed",
        "scenarios_tested": [
            "Invalid workflow ID",
            "Empty workflow ID",
            "Invalid workflow components"
        ]
    }


async def run_all_workflow_examples():
    """Run all workflow dashboard integration examples"""
    print("🚀 Starting Workflow Dashboard Integration Examples")
    print("=" * 60)
    
    results = {}
    
    try:
        # Run all examples
        results["workflow_integration"] = await example_workflow_dashboard_integration()
        results["integration_service"] = await example_workflow_integration_service()
        results["api_endpoints"] = await example_api_endpoints()
        results["error_handling"] = await example_error_handling()
        
        print("\n" + "=" * 60)
        print("🎉 All workflow examples completed!")
        
        # Summary
        successful_examples = sum(1 for result in results.values() if result is not None)
        total_examples = len(results)
        
        print(f"\nSummary: {successful_examples}/{total_examples} examples successful")
        
        return results
        
    except Exception as e:
        print(f"❌ Error running workflow examples: {e}")
        return results


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_workflow_examples())
