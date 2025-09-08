#!/usr/bin/env python3
"""
Workflow Data Integration Example

This file demonstrates how to use the dashboard and report services with complete workflow data
passed in the request instead of fetching from the database.
"""

import asyncio
import logging
from typing import Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

# Example workflow data structure based on workflow services models

def create_sample_workflow_data() -> Dict[str, Any]:
    """Create sample workflow data matching the workflow services models"""
    
    workflow_id = str(uuid4())
    
    # Sample thread components with SQL queries
    thread_components = [
        {
            "id": str(uuid4()),
            "component_type": "sql_summary",
            "sequence_order": 1,
            "question": "Show sales performance by region for Q4 2024",
            "description": "Regional sales analysis with executive summary",
            "sql_query": "SELECT region, SUM(sales_amount) as total_sales, COUNT(*) as transactions FROM sales_data WHERE quarter = 'Q4' AND year = 2024 GROUP BY region ORDER BY total_sales DESC",
            "executive_summary": "Q4 2024 shows strong sales performance across all regions with West region leading at $2.5M",
            "data_overview": {
                "total_records": 1250,
                "columns": [
                    {"name": "region", "type": "string"},
                    {"name": "total_sales", "type": "numeric"},
                    {"name": "transactions", "type": "integer"}
                ],
                "summary_stats": {
                    "total_sales": 8500000,
                    "avg_transactions": 312,
                    "top_region": "West"
                }
            },
            "visualization_data": {
                "chart_type": "bar",
                "x_axis": "region",
                "y_axis": "total_sales",
                "title": "Q4 2024 Sales by Region"
            },
            "chart_schema": {
                "type": "vega_lite",
                "spec": {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "region", "type": "nominal"},
                        "y": {"field": "total_sales", "type": "quantitative"}
                    }
                },
                "title": "Q4 2024 Sales by Region",
                "width": 400,
                "height": 300
            },
            "reasoning": "Regional analysis shows consistent growth patterns with West region outperforming due to new product launches",
            "data_count": 1250,
            "validation_results": {
                "sql_valid": True,
                "data_quality": "high",
                "completeness": 0.98
            },
            "configuration": {
                "enable_pagination": True,
                "page_size": 1000,
                "sort_by": "total_sales",
                "sort_order": "desc"
            },
            "is_configured": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": str(uuid4()),
            "component_type": "chart",
            "sequence_order": 2,
            "question": "Show monthly sales trends over the past year",
            "description": "Monthly sales trend analysis with forecasting",
            "sql_query": "SELECT DATE_TRUNC('month', sale_date) as month, SUM(sales_amount) as monthly_sales FROM sales_data WHERE sale_date >= CURRENT_DATE - INTERVAL '12 months' GROUP BY month ORDER BY month",
            "chart_config": {
                "type": "line",
                "x_axis": "month",
                "y_axis": "monthly_sales",
                "title": "Monthly Sales Trends",
                "show_trend_line": True,
                "forecast_periods": 3
            },
            "chart_schema": {
                "type": "vega_lite",
                "spec": {
                    "mark": "line",
                    "encoding": {
                        "x": {"field": "month", "type": "temporal"},
                        "y": {"field": "monthly_sales", "type": "quantitative"}
                    }
                },
                "title": "Monthly Sales Trends",
                "width": 600,
                "height": 300
            },
            "data_overview": {
                "total_records": 365,
                "columns": [
                    {"name": "month", "type": "date"},
                    {"name": "monthly_sales", "type": "numeric"}
                ]
            },
            "configuration": {
                "enable_forecasting": True,
                "forecast_method": "linear_regression",
                "confidence_interval": 0.95
            },
            "is_configured": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": str(uuid4()),
            "component_type": "table",
            "sequence_order": 3,
            "question": "Show top 10 products by revenue",
            "description": "Product performance analysis with detailed metrics",
            "sql_query": "SELECT product_name, category, SUM(sales_amount) as revenue, COUNT(*) as units_sold, AVG(unit_price) as avg_price FROM sales_data GROUP BY product_name, category ORDER BY revenue DESC LIMIT 10",
            "table_config": {
                "columns": ["product_name", "category", "revenue", "units_sold", "avg_price"],
                "sortable": True,
                "filterable": True,
                "page_size": 10,
                "show_totals": True
            },
            "data_overview": {
                "total_records": 10,
                "columns": [
                    {"name": "product_name", "type": "string"},
                    {"name": "category", "type": "string"},
                    {"name": "revenue", "type": "numeric"},
                    {"name": "units_sold", "type": "integer"},
                    {"name": "avg_price", "type": "numeric"}
                ]
            },
            "configuration": {
                "enable_export": True,
                "export_formats": ["csv", "excel"],
                "enable_search": True
            },
            "is_configured": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": str(uuid4()),
            "component_type": "metric",
            "sequence_order": 4,
            "question": "What is the current conversion rate?",
            "description": "Key performance metric for conversion tracking",
            "sql_query": "SELECT COUNT(CASE WHEN status = 'converted' THEN 1 END) * 100.0 / COUNT(*) as conversion_rate FROM leads WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'",
            "data_overview": {
                "total_records": 1,
                "columns": [
                    {"name": "conversion_rate", "type": "numeric"}
                ]
            },
            "configuration": {
                "metric_format": "percentage",
                "decimal_places": 2,
                "show_trend": True,
                "trend_period": "30_days"
            },
            "is_configured": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    ]
    
    # Sample workflow metadata
    workflow_metadata = {
        "dashboard_template": "executive_dashboard",
        "dashboard_layout": "grid_2x2",
        "refresh_rate": 300,
        "report_title": "Q4 2024 Sales Performance Dashboard",
        "report_description": "Comprehensive analysis of Q4 2024 sales performance across regions, products, and key metrics",
        "report_sections": [
            "executive_summary",
            "regional_analysis", 
            "product_performance",
            "key_metrics",
            "trends_and_forecasting",
            "recommendations"
        ],
        "writer_actor": "EXECUTIVE",
        "business_goal": {
            "primary_objective": "Strategic decision making",
            "target_audience": ["executives", "stakeholders"],
            "decision_context": "Q4 performance review and Q1 planning",
            "success_metrics": ["revenue_growth", "market_share", "customer_satisfaction"],
            "timeframe": "quarterly"
        },
        "custom_config": {
            "enable_alerts": True,
            "alert_thresholds": {
                "sales_decline": 0.1,
                "conversion_rate_min": 0.15
            },
            "export_settings": {
                "default_format": "pdf",
                "include_charts": True,
                "include_data": True
            }
        }
    }
    
    # Complete workflow data
    workflow_data = {
        "workflow_id": workflow_id,
        "state": "ACTIVE",
        "current_step": 4,
        "workflow_metadata": workflow_metadata,
        "thread_components": thread_components,
        "error_message": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "completed_at": None
    }
    
    return workflow_data


async def example_dashboard_workflow_integration():
    """Example of dashboard workflow integration with complete data"""
    
    print("🚀 Dashboard Workflow Integration Example")
    print("=" * 50)
    
    # Create sample workflow data
    workflow_data = create_sample_workflow_data()
    
    print(f"📊 Workflow ID: {workflow_data['workflow_id']}")
    print(f"📊 State: {workflow_data['state']}")
    print(f"📊 Components: {len(workflow_data['thread_components'])}")
    print(f"📊 Template: {workflow_data['workflow_metadata']['dashboard_template']}")
    
    # Example API request structure
    print("\n📡 Example API Request:")
    print("POST /dashboard/render-from-workflow")
    print("Content-Type: application/json")
    print()
    
    # Show the request structure
    request_example = {
        "workflow_id": workflow_data["workflow_id"],
        "project_id": "q4_sales_analysis",
        "state": workflow_data["state"],
        "current_step": workflow_data["current_step"],
        "workflow_metadata": workflow_data["workflow_metadata"],
        "thread_components": workflow_data["thread_components"],
        "natural_language_query": "Highlight regions with sales above $2M in green and show trends for underperforming products",
        "additional_context": {
            "user_id": "exec_123",
            "session_id": "session_456",
            "department": "sales"
        },
        "time_filters": {
            "period": "Q4_2024",
            "timezone": "UTC"
        },
        "render_options": {
            "mode": "full",
            "enable_caching": True,
            "include_forecasting": True
        },
        "error_message": workflow_data["error_message"],
        "created_at": workflow_data["created_at"],
        "updated_at": workflow_data["updated_at"],
        "completed_at": workflow_data["completed_at"]
    }
    
    print("Request Body:")
    print(f"  workflow_id: {request_example['workflow_id']}")
    print(f"  project_id: {request_example['project_id']}")
    print(f"  state: {request_example['state']}")
    print(f"  current_step: {request_example['current_step']}")
    print(f"  natural_language_query: {request_example['natural_language_query']}")
    print(f"  thread_components: {len(request_example['thread_components'])} components")
    print(f"  workflow_metadata: {len(request_example['workflow_metadata'])} fields")
    
    # Show component details
    print(f"\n📋 Thread Components:")
    for i, component in enumerate(workflow_data["thread_components"], 1):
        print(f"  {i}. {component['component_type'].upper()}: {component['question'][:50]}...")
        print(f"     SQL: {component['sql_query'][:60]}...")
        print(f"     Configured: {component['is_configured']}")
    
    # Show workflow metadata
    print(f"\n⚙️  Workflow Metadata:")
    metadata = workflow_data["workflow_metadata"]
    print(f"  Dashboard Template: {metadata['dashboard_template']}")
    print(f"  Layout: {metadata['dashboard_layout']}")
    print(f"  Refresh Rate: {metadata['refresh_rate']}s")
    print(f"  Writer Actor: {metadata['writer_actor']}")
    print(f"  Report Sections: {len(metadata['report_sections'])}")
    
    return workflow_data


async def example_report_workflow_integration():
    """Example of report workflow integration with complete data"""
    
    print("\n🚀 Report Workflow Integration Example")
    print("=" * 50)
    
    # Create sample workflow data
    workflow_data = create_sample_workflow_data()
    
    print(f"📊 Workflow ID: {workflow_data['workflow_id']}")
    print(f"📊 State: {workflow_data['state']}")
    print(f"📊 Components: {len(workflow_data['thread_components'])}")
    print(f"📊 Template: {workflow_data['workflow_metadata']['dashboard_template']}")
    
    # Example API request structure
    print("\n📡 Example API Request:")
    print("POST /report/render-from-workflow")
    print("Content-Type: application/json")
    print()
    
    # Show the request structure
    request_example = {
        "workflow_id": workflow_data["workflow_id"],
        "project_id": "q4_sales_report",
        "state": workflow_data["state"],
        "current_step": workflow_data["current_step"],
        "workflow_metadata": workflow_data["workflow_metadata"],
        "thread_components": workflow_data["thread_components"],
        "natural_language_query": "Create an executive summary highlighting key performance indicators and provide strategic recommendations for Q1 2025",
        "additional_context": {
            "user_id": "exec_123",
            "session_id": "session_456",
            "department": "sales",
            "report_audience": "executives"
        },
        "time_filters": {
            "period": "Q4_2024",
            "timezone": "UTC"
        },
        "render_options": {
            "mode": "full",
            "enable_caching": True,
            "include_executive_summary": True
        },
        "report_template": "executive_summary",
        "writer_actor": "EXECUTIVE",
        "business_goal": "strategic",
        "error_message": workflow_data["error_message"],
        "created_at": workflow_data["created_at"],
        "updated_at": workflow_data["updated_at"],
        "completed_at": workflow_data["completed_at"]
    }
    
    print("Request Body:")
    print(f"  workflow_id: {request_example['workflow_id']}")
    print(f"  project_id: {request_example['project_id']}")
    print(f"  state: {request_example['state']}")
    print(f"  current_step: {request_example['current_step']}")
    print(f"  natural_language_query: {request_example['natural_language_query']}")
    print(f"  report_template: {request_example['report_template']}")
    print(f"  writer_actor: {request_example['writer_actor']}")
    print(f"  business_goal: {request_example['business_goal']}")
    print(f"  thread_components: {len(request_example['thread_components'])} components")
    
    # Show component details
    print(f"\n📋 Thread Components:")
    for i, component in enumerate(workflow_data["thread_components"], 1):
        print(f"  {i}. {component['component_type'].upper()}: {component['question'][:50]}...")
        print(f"     SQL: {component['sql_query'][:60]}...")
        print(f"     Executive Summary: {component.get('executive_summary', 'N/A')[:50]}...")
        print(f"     Configured: {component['is_configured']}")
    
    # Show workflow metadata
    print(f"\n⚙️  Workflow Metadata:")
    metadata = workflow_data["workflow_metadata"]
    print(f"  Report Title: {metadata['report_title']}")
    print(f"  Report Description: {metadata['report_description']}")
    print(f"  Writer Actor: {metadata['writer_actor']}")
    print(f"  Business Goal: {metadata['business_goal']['primary_objective']}")
    print(f"  Target Audience: {metadata['business_goal']['target_audience']}")
    print(f"  Report Sections: {len(metadata['report_sections'])}")
    
    return workflow_data


async def example_data_transformation():
    """Example showing how workflow data is transformed for processing"""
    
    print("\n🔄 Data Transformation Example")
    print("=" * 50)
    
    workflow_data = create_sample_workflow_data()
    
    # Show how thread components are transformed to dashboard queries
    print("📊 Dashboard Query Transformation:")
    print("  Thread Components → Dashboard Queries")
    print()
    
    for i, component in enumerate(workflow_data["thread_components"], 1):
        if component.get("sql_query"):
            print(f"  {i}. Component: {component['component_type']}")
            print(f"     Question: {component['question']}")
            print(f"     SQL: {component['sql_query'][:60]}...")
            print(f"     → Chart ID: chart_{component['id']}")
            print(f"     → Component Type: {component['component_type']}")
            print(f"     → Sequence Order: {component['sequence_order']}")
            print()
    
    # Show how workflow metadata is transformed to dashboard context
    print("📊 Dashboard Context Transformation:")
    print("  Workflow Metadata → Dashboard Context")
    print()
    
    metadata = workflow_data["workflow_metadata"]
    print(f"  Title: {metadata['report_title']}")
    print(f"  Description: {metadata['report_description']}")
    print(f"  Template: {metadata['dashboard_template']}")
    print(f"  Layout: {metadata['dashboard_layout']}")
    print(f"  Refresh Rate: {metadata['refresh_rate']}s")
    print(f"  Available Columns: [extracted from data_overview]")
    print(f"  Data Types: [extracted from data_overview]")
    print()
    
    # Show how workflow metadata is transformed to report context
    print("📊 Report Context Transformation:")
    print("  Workflow Metadata → Report Context")
    print()
    
    print(f"  Title: {metadata['report_title']}")
    print(f"  Description: {metadata['report_description']}")
    print(f"  Sections: {metadata['report_sections']}")
    print(f"  Writer Actor: {metadata['writer_actor']}")
    print(f"  Business Goal: {metadata['business_goal']['primary_objective']}")
    print(f"  Available Columns: [extracted from data_overview]")
    print(f"  Data Types: [extracted from data_overview]")
    print()


async def example_error_handling():
    """Example showing error handling scenarios"""
    
    print("\n⚠️  Error Handling Examples")
    print("=" * 50)
    
    # Example 1: Missing SQL queries
    print("1. Missing SQL Queries:")
    print("   - Components without sql_query are filtered out")
    print("   - Only chart, table, metric, sql_summary components are processed")
    print("   - Empty query list results in basic dashboard/report")
    print()
    
    # Example 2: Invalid component types
    print("2. Invalid Component Types:")
    print("   - Unknown component types are handled gracefully")
    print("   - Only supported types are processed for queries")
    print("   - Other components are included in context but not queried")
    print()
    
    # Example 3: Missing workflow metadata
    print("3. Missing Workflow Metadata:")
    print("   - Default values are used for missing fields")
    print("   - Basic context is created with available data")
    print("   - Workflow ID and state are preserved")
    print()
    
    # Example 4: Data transformation errors
    print("4. Data Transformation Errors:")
    print("   - Errors are logged and basic context is returned")
    print("   - Processing continues with available data")
    print("   - Error details are included in response metadata")
    print()


async def run_all_examples():
    """Run all workflow data integration examples"""
    
    print("🚀 Workflow Data Integration Examples")
    print("=" * 60)
    print("This demonstrates the new approach where complete workflow data")
    print("is passed in the request instead of fetching from database.")
    print()
    
    try:
        # Run all examples
        await example_dashboard_workflow_integration()
        await example_report_workflow_integration()
        await example_data_transformation()
        await example_error_handling()
        
        print("\n" + "=" * 60)
        print("🎉 All examples completed!")
        print()
        print("Key Benefits of New Approach:")
        print("✅ No database lookups required")
        print("✅ Complete workflow data in request")
        print("✅ Better performance and reliability")
        print("✅ Easier testing and debugging")
        print("✅ Reduced external dependencies")
        print("✅ More flexible data handling")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())
