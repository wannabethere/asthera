#!/usr/bin/env python3
"""
Example script demonstrating the n8n workflow creator functionality

This script shows how to:
1. Create a dashboard workflow
2. Add components to it
3. Configure sharing and scheduling
4. Publish the dashboard (which automatically creates the n8n workflow)
5. Manage the generated n8n workflow files
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import the app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.services.dashboard_workflow import DashboardWorkflowService
from app.services.n8n_workflow_creator import N8nWorkflowCreator
from app.models.workflowmodels import (
    ThreadComponentCreate, ShareConfigCreate, ScheduleConfigCreate,
    IntegrationConfigCreate, ComponentType, ShareType, ScheduleType, IntegrationType
)
from app.models.schema import DashboardCreate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def create_example_dashboard_workflow():
    """Create a complete example dashboard workflow with n8n integration"""
    
    # Initialize database connection (you'll need to adjust this for your setup)
    # engine = create_engine("postgresql://user:password@localhost/dbname")
    # SessionLocal = sessionmaker(autocreate=False, autocommit=False, autoflush=False, bind=engine)
    # db = SessionLocal()
    
    print("🚀 Creating example dashboard workflow with n8n integration...")
    
    # For demonstration purposes, we'll show the workflow creation steps
    # In a real scenario, you would use the actual database session
    
    print("\n1️⃣ Creating dashboard workflow...")
    print("   - Dashboard name: Sales Performance Dashboard")
    print("   - Description: Q4 2024 sales analytics and insights")
    
    print("\n2️⃣ Adding workflow components...")
    components = [
        {
            "type": ComponentType.QUESTION,
            "question": "What were our Q4 sales performance metrics?",
            "description": "Analyze sales data for Q4 2024"
        },
        {
            "type": ComponentType.CHART,
            "question": "Sales Trend Analysis",
            "chart_config": {
                "type": "line",
                "data_source": "sales_database",
                "x_axis": "month",
                "y_axis": "revenue",
                "filters": {"quarter": "Q4", "year": "2024"}
            }
        },
        {
            "type": ComponentType.TABLE,
            "question": "Top Performing Products",
            "table_config": {
                "columns": ["Product", "Units Sold", "Revenue", "Growth %"],
                "data_source": "product_performance",
                "sort_by": "revenue",
                "limit": 10
            }
        },
        {
            "type": ComponentType.METRIC,
            "question": "Total Q4 Revenue",
            "description": "Overall revenue achievement for Q4"
        }
    ]
    
    for i, comp in enumerate(components, 1):
        print(f"   {i}. {comp['type'].value.title()}: {comp['question']}")
    
    print("\n3️⃣ Configuring sharing...")
    share_configs = [
        {
            "type": ShareType.TEAM,
            "target_id": "sales-team",
            "permissions": {"view": True, "edit": False, "share": True}
        },
        {
            "type": ShareType.EMAIL,
            "target_id": "sales-manager@company.com",
            "permissions": {"view": True, "edit": False}
        }
    ]
    
    for config in share_configs:
        print(f"   - {config['type'].value.title()}: {config['target_id']}")
    
    print("\n4️⃣ Setting up scheduling...")
    schedule_config = {
        "type": ScheduleType.WEEKLY,
        "timezone": "UTC",
        "start_date": "2024-10-01T00:00:00Z",
        "configuration": {"day_of_week": "monday", "time": "09:00"}
    }
    print(f"   - Schedule: {schedule_config['type'].value.title()} on Monday at 9 AM UTC")
    
    print("\n5️⃣ Configuring integrations...")
    integrations = [
        {
            "type": IntegrationType.SLACK,
            "connection_config": {
                "webhook_url": "https://hooks.slack.com/services/...",
                "channel": "#sales-updates"
            },
            "mapping_config": {
                "message_template": "Sales Dashboard Update: Revenue is {{revenue}} for {{period}}"
            }
        },
        {
            "type": IntegrationType.POWERBI,
            "connection_config": {
                "workspace_id": "sales-workspace",
                "api_key": "***"
            },
            "mapping_config": {
                "dataset_name": "Q4_Sales_Data",
                "refresh_schedule": "daily"
            }
        }
    ]
    
    for integration in integrations:
        print(f"   - {integration['type'].value.title()}: {integration['mapping_config']}")
    
    print("\n6️⃣ Publishing dashboard...")
    print("   - Dashboard becomes active")
    print("   - n8n workflow is automatically generated")
    
    print("\n7️⃣ Generated n8n workflow structure:")
    print("   - Trigger: Weekly cron (Monday 9 AM UTC)")
    print("   - Data Processing: 4 component nodes")
    print("   - Sharing: 2 sharing nodes (Team + Email)")
    print("   - Integrations: 2 integration nodes (Slack + Power BI)")
    
    return {
        "dashboard_name": "Sales Performance Dashboard",
        "components_count": len(components),
        "share_configs_count": len(share_configs),
        "integrations_count": len(integrations),
        "schedule_type": schedule_config["type"].value
    }

def demonstrate_n8n_workflow_creator():
    """Demonstrate the n8n workflow creator functionality"""
    
    print("\n🔧 Demonstrating n8n workflow creator functionality...")
    
    # Initialize the n8n workflow creator
    creator = N8nWorkflowCreator(output_dir="example_n8n_workflows")
    
    print(f"   - Output directory: {creator.output_dir}")
    
    # Show example workflow file management
    print("\n   📁 Workflow file management:")
    print("   - List all workflows: creator.list_workflow_files()")
    print("   - Get specific workflow: creator.get_workflow_file_path(dashboard_id, workflow_id)")
    print("   - Delete workflow: creator.delete_workflow_file(dashboard_id, workflow_id)")
    
    # Show example generated workflow structure
    print("\n   📋 Example generated n8n workflow structure:")
    example_workflow = {
        "name": "Dashboard Workflow - Sales Performance Dashboard",
        "nodes": [
            {
                "id": "trigger_weekly",
                "name": "Weekly Trigger",
                "type": "n8n-nodes-base.cron",
                "position": [240, 300]
            },
            {
                "id": "chart_sales_trend",
                "name": "Chart: Sales Trend Analysis",
                "type": "n8n-nodes-base.code",
                "position": [480, 300]
            },
            {
                "id": "table_top_products",
                "name": "Table: Top Performing Products",
                "type": "n8n-nodes-base.code",
                "position": [680, 300]
            },
            {
                "id": "slack_share",
                "name": "Slack Share: #sales-updates",
                "type": "n8n-nodes-base.slack",
                "position": [1200, 200]
            },
            {
                "id": "powerbi_integration",
                "name": "Power BI Integration",
                "type": "n8n-nodes-base.httpRequest",
                "position": [1400, 400]
            }
        ],
        "connections": {
            "trigger_weekly": {
                "main": [[{"node": "chart_sales_trend", "type": "main", "index": 0}]]
            },
            "chart_sales_trend": {
                "main": [[{"node": "table_top_products", "type": "main", "index": 0}]]
            },
            "table_top_products": {
                "main": [[{"node": "slack_share", "type": "main", "index": 0}]]
            },
            "slack_share": {
                "main": [[{"node": "powerbi_integration", "type": "main", "index": 0}]]
            }
        }
    }
    
    print(f"   - Workflow name: {example_workflow['name']}")
    print(f"   - Total nodes: {len(example_workflow['nodes'])}")
    print(f"   - Node types: {[node['type'] for node in example_workflow['nodes']]}")
    
    return example_workflow

def show_api_endpoints():
    """Show the available API endpoints for n8n workflow management"""
    
    print("\n🌐 Available API endpoints for n8n workflow management:")
    
    endpoints = [
        {
            "method": "POST",
            "path": "/api/v1/workflows/{workflow_id}/n8n/create",
            "description": "Manually create n8n workflow for an existing active dashboard"
        },
        {
            "method": "GET",
            "path": "/api/v1/workflows/{workflow_id}/n8n/status",
            "description": "Get the status of n8n workflow for a dashboard"
        },
        {
            "method": "GET",
            "path": "/api/v1/workflows/n8n/workflows",
            "description": "List all generated n8n workflow files"
        },
        {
            "method": "DELETE",
            "path": "/api/v1/workflows/{workflow_id}/n8n/delete",
            "description": "Delete n8n workflow file for a dashboard"
        }
    ]
    
    for endpoint in endpoints:
        print(f"   {endpoint['method']} {endpoint['path']}")
        print(f"      {endpoint['description']}")
        print()

def main():
    """Main function to run the example"""
    
    print("🎯 N8N Workflow Creator Example")
    print("=" * 50)
    
    try:
        # Create example dashboard workflow
        workflow_info = create_example_dashboard_workflow()
        
        # Demonstrate n8n workflow creator
        example_workflow = demonstrate_n8n_workflow_creator()
        
        # Show API endpoints
        show_api_endpoints()
        
        print("\n✅ Example completed successfully!")
        print(f"\n📊 Created workflow: {workflow_info['dashboard_name']}")
        print(f"   - Components: {workflow_info['components_count']}")
        print(f"   - Sharing configs: {workflow_info['share_configs_count']}")
        print(f"   - Integrations: {workflow_info['integrations_count']}")
        print(f"   - Schedule: {workflow_info['schedule_type']}")
        
        print("\n🚀 The n8n workflow will be automatically generated when the dashboard is published!")
        print("   - Workflow files are saved to the 'n8n_workflows' directory")
        print("   - Each workflow is a complete JSON file ready for n8n import")
        print("   - Workflows include all components, sharing, and integrations")
        
    except Exception as e:
        print(f"\n❌ Error running example: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
