#!/usr/bin/env python3
"""
Report Workflow Integration Examples

This file demonstrates how to use the report service with workflow database models.
It shows the complete flow from workflow creation to report rendering.
"""

import asyncio
import logging
from typing import Dict, Any
from uuid import UUID, uuid4

# Usage Example for Report Workflow Integration

async def example_report_workflow_integration():
    """Example usage of the Report Workflow Integration"""
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.services.writers.report_service import ReportService
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
    
    # Initialize report service
    report_service = ReportService()
    
    # Initialize workflow integration service
    workflow_integration = WorkflowIntegrationService()
    
    # Sample workflow ID (in production, this would come from the database)
    workflow_id = str(uuid4())
    project_id = "report_workflow_integration_test"
    
    print(f"🚀 Testing Report Workflow Integration")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   Project ID: {project_id}")
    
    # Status callback for workflow updates
    def workflow_status_callback(status: str, details: Dict[str, Any]):
        """Handle status updates from workflow processing"""
        print(f"🔄 Report Workflow Status: {status}")
        if details:
            print(f"   Details: {details}")
    
    try:
        # Example 1: Render report from workflow database model
        print("\n=== Example 1: Render Report from Workflow Database ===")
        
        result = await report_service.render_report_from_workflow_db(
            workflow_id=workflow_id,
            project_id=project_id,
            natural_language_query="Create an executive summary highlighting key performance indicators and trends",
            additional_context={"user_id": "user123", "session_id": "session456"},
            time_filters={"period": "last_quarter"},
            render_options={"mode": "full", "enable_caching": True},
            report_template="executive_summary",
            writer_actor="EXECUTIVE",
            business_goal="strategic",
            status_callback=workflow_status_callback
        )
        
        print(f"✅ Report rendered successfully from workflow!")
        print(f"   Success: {result.get('post_process', {}).get('success', False)}")
        print(f"   Workflow ID: {result.get('workflow_metadata', {}).get('workflow_id')}")
        print(f"   Report Template: {result.get('workflow_metadata', {}).get('report_template')}")
        print(f"   Writer Actor: {result.get('workflow_metadata', {}).get('writer_actor')}")
        
        # Example 2: Get workflow components
        print("\n=== Example 2: Get Workflow Components ===")
        
        components = await report_service.get_workflow_components(workflow_id)
        print(f"✅ Retrieved {len(components)} workflow components")
        
        for i, component in enumerate(components[:3]):  # Show first 3
            print(f"   Component {i+1}: {component.get('component_type')} - {component.get('question', 'No question')[:50]}...")
        
        # Example 3: Get workflow status
        print("\n=== Example 3: Get Workflow Status ===")
        
        status = await report_service.get_workflow_status(workflow_id)
        print(f"✅ Workflow status retrieved")
        print(f"   Status: {status.get('status')}")
        print(f"   State: {status.get('state')}")
        print(f"   Total Components: {status.get('total_components')}")
        print(f"   Dashboard Template: {status.get('dashboard_template')}")
        
        # Example 4: Preview report from workflow
        print("\n=== Example 4: Preview Report from Workflow ===")
        
        preview_result = await report_service.preview_report_from_workflow(
            workflow_id=workflow_id,
            preview_options={"max_queries": 2, "enable_caching": True}
        )
        
        print(f"✅ Report preview generated")
        print(f"   Success: {preview_result.get('post_process', {}).get('success', False)}")
        print(f"   Preview Mode: {preview_result.get('preview_metadata', {}).get('preview_mode')}")
        print(f"   Queries Previewed: {preview_result.get('preview_metadata', {}).get('total_queries_previewed')}")
        
        return {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "report_result": result,
            "components": components,
            "status": status,
            "preview_result": preview_result
        }
        
    except Exception as e:
        print(f"💥 Error in report workflow integration: {e}")
        raise
    finally:
        # Cleanup
        await workflow_integration.close()


async def example_report_templates():
    """Example showing different report templates and configurations"""
    
    print("\n=== Example: Report Templates and Configurations ===")
    
    from app.services.writers.report_service import ReportService
    
    report_service = ReportService()
    
    # Get available templates
    templates = report_service.get_available_templates()
    print(f"📋 Available Report Templates: {len(templates)}")
    
    for template_name, template_config in templates.items():
        print(f"   - {template_name}: {template_config['name']}")
        print(f"     Description: {template_config['description']}")
        print(f"     Writer Actor: {template_config['writer_actor']}")
        print(f"     Components: {len(template_config['components'])}")
    
    # Test different writer actors
    print(f"\n🎭 Testing Writer Actors:")
    writer_actors = ["EXECUTIVE", "ANALYST", "DATA_SCIENTIST"]
    
    for actor in writer_actors:
        try:
            from app.agents.nodes.writers.report_writing_agent import WriterActorType
            actor_type = WriterActorType[actor]
            print(f"   ✅ {actor}: {actor_type}")
        except KeyError:
            print(f"   ❌ {actor}: Not found")
    
    # Test business goals
    print(f"\n🎯 Testing Business Goals:")
    business_goals = ["strategic", "operational", "performance"]
    
    for goal in business_goals:
        parsed_goal = report_service._parse_business_goal(goal)
        if parsed_goal:
            print(f"   ✅ {goal}: {parsed_goal.primary_objective}")
        else:
            print(f"   ❌ {goal}: Failed to parse")
    
    return {
        "templates": templates,
        "writer_actors": writer_actors,
        "business_goals": business_goals
    }


async def example_api_endpoints():
    """Example showing how to use the API endpoints"""
    
    print("\n=== Example: API Endpoints Usage ===")
    
    # This would typically be done via HTTP requests to the API
    # For this example, we'll show the expected request/response format
    
    # Example 1: Render report from workflow
    print("📡 POST /report/render-from-workflow")
    print("   Request Body:")
    print("   {")
    print(f'     "workflow_id": "123e4567-e89b-12d3-a456-426614174000",')
    print(f'     "project_id": "api_test_project",')
    print(f'     "natural_language_query": "Create executive summary with key insights",')
    print(f'     "additional_context": {{"user_id": "user123"}},')
    print(f'     "time_filters": {{"period": "last_quarter"}},')
    print(f'     "render_options": {{"mode": "full", "enable_caching": true}},')
    print(f'     "report_template": "executive_summary",')
    print(f'     "writer_actor": "EXECUTIVE",')
    print(f'     "business_goal": "strategic"')
    print("   }")
    
    # Example 2: Get workflow components
    print("\n📡 GET /report/workflow/{workflow_id}/components")
    print("   Response:")
    print("   {")
    print(f'     "workflow_id": "123e4567-e89b-12d3-a456-426614174000",')
    print(f'     "components": [')
    print(f'       {{')
    print(f'         "component_id": "component_1",')
    print(f'         "component_type": "chart",')
    print(f'         "question": "Show sales performance by region",')
    print(f'         "description": "Regional sales analysis",')
    print(f'         "sequence_order": 1,')
    print(f'         "sql": "SELECT region, SUM(sales) FROM sales_data GROUP BY region",')
    print(f'         "chart_config": {{"type": "bar", "x_axis": "region", "y_axis": "sales"}}')
    print(f'       }}')
    print(f'     ],')
    print(f'     "total_components": 1')
    print("   }")
    
    # Example 3: Get workflow status
    print("\n📡 GET /report/workflow/{workflow_id}/status")
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
    
    # Example 4: Preview report
    print("\n📡 POST /report/workflow/{workflow_id}/preview")
    print("   Request Body:")
    print("   {")
    print(f'     "preview_options": {{"max_queries": 2, "enable_caching": true}}')
    print("   }")
    
    return {
        "message": "API endpoint examples shown",
        "endpoints": [
            "POST /report/render-from-workflow",
            "GET /report/workflow/{workflow_id}/components",
            "GET /report/workflow/{workflow_id}/status",
            "POST /report/workflow/{workflow_id}/preview"
        ]
    }


async def example_error_handling():
    """Example showing error handling scenarios"""
    
    print("\n=== Example: Error Handling ===")
    
    from app.services.writers.report_service import ReportService
    
    report_service = ReportService()
    
    # Test with invalid workflow ID
    invalid_workflow_id = "invalid-workflow-id"
    
    try:
        print(f"🔍 Testing with invalid workflow ID: {invalid_workflow_id}")
        
        result = await report_service.render_report_from_workflow_db(
            workflow_id=invalid_workflow_id,
            project_id="error_test"
        )
        
        print(f"❌ Unexpected success with invalid workflow ID")
        
    except Exception as e:
        print(f"✅ Expected error caught: {type(e).__name__}: {e}")
    
    # Test with empty workflow ID
    try:
        print(f"\n🔍 Testing with empty workflow ID")
        
        result = await report_service.render_report_from_workflow_db(
            workflow_id="",
            project_id="error_test"
        )
        
        print(f"❌ Unexpected success with empty workflow ID")
        
    except Exception as e:
        print(f"✅ Expected error caught: {type(e).__name__}: {e}")
    
    # Test workflow components with invalid ID
    try:
        print(f"\n🔍 Testing workflow components with invalid ID")
        
        components = await report_service.get_workflow_components(invalid_workflow_id)
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


async def run_all_report_examples():
    """Run all report workflow integration examples"""
    print("🚀 Starting Report Workflow Integration Examples")
    print("=" * 60)
    
    results = {}
    
    try:
        # Run all examples
        results["report_integration"] = await example_report_workflow_integration()
        results["report_templates"] = await example_report_templates()
        results["api_endpoints"] = await example_api_endpoints()
        results["error_handling"] = await example_error_handling()
        
        print("\n" + "=" * 60)
        print("🎉 All report examples completed!")
        
        # Summary
        successful_examples = sum(1 for result in results.values() if result is not None)
        total_examples = len(results)
        
        print(f"\nSummary: {successful_examples}/{total_examples} examples successful")
        
        return results
        
    except Exception as e:
        print(f"❌ Error running report examples: {e}")
        return results


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_report_examples())
