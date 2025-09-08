#!/usr/bin/env python3
"""
Example demonstrating how chart schema is passed through the data pipelines
to make visualizations actionable.

This example shows:
1. How chart schema is passed from workflow data to dashboard/report services
2. How the data pipelines process chart schema to generate actionable visualizations
3. The complete flow from API request to chart execution
"""

import asyncio
import json
from typing import Dict, Any, List
from uuid import uuid4

# Example chart schemas for different visualization types
VEGA_LITE_BAR_CHART_SCHEMA = {
    "type": "vega_lite",
    "spec": {
        "mark": "bar",
        "encoding": {
            "x": {"field": "region", "type": "nominal", "axis": {"title": "Region"}},
            "y": {"field": "total_sales", "type": "quantitative", "axis": {"title": "Total Sales ($)"}}
        }
    },
    "title": "Q4 2024 Sales by Region",
    "width": 400,
    "height": 300,
    "config": {
        "view": {"stroke": "transparent"},
        "axis": {"domainWidth": 1}
    }
}

VEGA_LITE_LINE_CHART_SCHEMA = {
    "type": "vega_lite",
    "spec": {
        "mark": "line",
        "encoding": {
            "x": {"field": "month", "type": "temporal", "axis": {"title": "Month"}},
            "y": {"field": "monthly_sales", "type": "quantitative", "axis": {"title": "Monthly Sales ($)"}},
            "color": {"value": "#1f77b4"}
        }
    },
    "title": "Monthly Sales Trends",
    "width": 600,
    "height": 300,
    "config": {
        "view": {"stroke": "transparent"},
        "axis": {"domainWidth": 1}
    }
}

PLOTLY_PIE_CHART_SCHEMA = {
    "type": "plotly",
    "data": [{
        "type": "pie",
        "labels": ["North", "South", "East", "West"],
        "values": [25, 30, 20, 25],
        "hole": 0.3
    }],
    "layout": {
        "title": "Regional Distribution",
        "height": 400,
        "showlegend": True
    }
}

# Example workflow data with chart schemas
def create_dashboard_workflow_with_chart_schemas() -> Dict[str, Any]:
    """Create example dashboard workflow data with chart schemas"""
    return {
        "workflow_id": str(uuid4()),
        "project_id": "sales_analytics",
        "state": "completed",
        "current_step": 3,
        "workflow_metadata": {
            "dashboard_template": "executive_dashboard",
            "dashboard_layout": "grid_2x2",
            "refresh_rate": 300,
            "report_title": "Q4 2024 Sales Analytics Dashboard",
            "report_description": "Comprehensive sales analytics for Q4 2024",
            "writer_actor": "EXECUTIVE",
            "business_goal": {
                "primary_objective": "Strategic decision making",
                "target_audience": ["executives", "stakeholders"],
                "decision_context": "Q4 performance review",
                "success_metrics": ["revenue growth", "market share"],
                "timeframe": "quarterly"
            }
        },
        "thread_components": [
            {
                "id": str(uuid4()),
                "component_type": "chart",
                "sequence_order": 1,
                "question": "Show Q4 sales by region",
                "description": "Regional sales performance for Q4 2024",
                "sql_query": "SELECT region, SUM(sales_amount) as total_sales FROM sales_data WHERE sale_date >= '2024-10-01' AND sale_date < '2025-01-01' GROUP BY region ORDER BY total_sales DESC",
                "chart_schema": VEGA_LITE_BAR_CHART_SCHEMA,
                "chart_config": {
                    "chart_type": "bar",
                    "x_axis": "region",
                    "y_axis": "total_sales",
                    "title": "Q4 2024 Sales by Region"
                },
                "data_overview": {
                    "total_records": 1250,
                    "columns": [
                        {"name": "region", "type": "categorical"},
                        {"name": "total_sales", "type": "numeric"}
                    ]
                },
                "reasoning": "Bar chart best represents categorical comparison of regional sales",
                "data_count": 1250,
                "validation_results": {
                    "sql_valid": True,
                    "data_quality": "high",
                    "completeness": 0.98
                }
            },
            {
                "id": str(uuid4()),
                "component_type": "chart",
                "sequence_order": 2,
                "question": "Show monthly sales trends",
                "description": "Monthly sales trend analysis with forecasting",
                "sql_query": "SELECT DATE_TRUNC('month', sale_date) as month, SUM(sales_amount) as monthly_sales FROM sales_data WHERE sale_date >= '2024-01-01' GROUP BY month ORDER BY month",
                "chart_schema": VEGA_LITE_LINE_CHART_SCHEMA,
                "chart_config": {
                    "chart_type": "line",
                    "x_axis": "month",
                    "y_axis": "monthly_sales",
                    "title": "Monthly Sales Trends",
                    "show_trend_line": True,
                    "forecast_periods": 3
                },
                "data_overview": {
                    "total_records": 365,
                    "columns": [
                        {"name": "month", "type": "date"},
                        {"name": "monthly_sales", "type": "numeric"}
                    ]
                },
                "reasoning": "Line chart shows temporal trends and patterns over time",
                "data_count": 365,
                "validation_results": {
                    "sql_valid": True,
                    "data_quality": "high",
                    "completeness": 1.0
                }
            },
            {
                "id": str(uuid4()),
                "component_type": "table",
                "sequence_order": 3,
                "question": "Show top performing products",
                "description": "Top 10 products by sales volume",
                "sql_query": "SELECT product_name, SUM(quantity) as total_quantity, SUM(sales_amount) as total_revenue FROM sales_data WHERE sale_date >= '2024-10-01' GROUP BY product_name ORDER BY total_revenue DESC LIMIT 10",
                "chart_schema": {},  # No chart schema for table
                "table_config": {
                    "sort_by": "total_revenue",
                    "sort_order": "desc",
                    "page_size": 10,
                    "show_rankings": True
                },
                "data_overview": {
                    "total_records": 10,
                    "columns": [
                        {"name": "product_name", "type": "categorical"},
                        {"name": "total_quantity", "type": "numeric"},
                        {"name": "total_revenue", "type": "numeric"}
                    ]
                },
                "reasoning": "Table format best for detailed product performance data",
                "data_count": 10,
                "validation_results": {
                    "sql_valid": True,
                    "data_quality": "high",
                    "completeness": 1.0
                }
            }
        ],
        "natural_language_query": "Create a comprehensive dashboard showing Q4 sales performance with regional analysis, monthly trends, and top products",
        "additional_context": {
            "user_id": "executive_001",
            "dashboard_theme": "corporate",
            "color_scheme": "blue_green"
        },
        "time_filters": {
            "period": "Q4_2024",
            "start_date": "2024-10-01",
            "end_date": "2024-12-31"
        },
        "render_options": {
            "include_export": True,
            "include_drill_down": True,
            "auto_refresh": True
        }
    }

def create_report_workflow_with_chart_schemas() -> Dict[str, Any]:
    """Create example report workflow data with chart schemas"""
    return {
        "workflow_id": str(uuid4()),
        "project_id": "sales_report",
        "state": "completed",
        "current_step": 4,
        "workflow_metadata": {
            "report_title": "Q4 2024 Sales Performance Report",
            "report_description": "Comprehensive analysis of Q4 sales performance",
            "report_sections": ["executive_summary", "regional_analysis", "trend_analysis", "recommendations"],
            "writer_actor": "ANALYST",
            "business_goal": {
                "primary_objective": "Operational insights",
                "target_audience": ["managers", "analysts"],
                "decision_context": "Performance review and planning",
                "success_metrics": ["accuracy", "actionability"],
                "timeframe": "monthly"
            }
        },
        "thread_components": [
            {
                "id": str(uuid4()),
                "component_type": "chart",
                "sequence_order": 1,
                "question": "Show regional performance distribution",
                "description": "Pie chart showing regional sales distribution",
                "sql_query": "SELECT region, SUM(sales_amount) as total_sales FROM sales_data WHERE sale_date >= '2024-10-01' GROUP BY region",
                "chart_schema": PLOTLY_PIE_CHART_SCHEMA,
                "chart_config": {
                    "chart_type": "pie",
                    "title": "Regional Distribution",
                    "show_percentages": True,
                    "show_legend": True
                },
                "data_overview": {
                    "total_records": 4,
                    "columns": [
                        {"name": "region", "type": "categorical"},
                        {"name": "total_sales", "type": "numeric"}
                    ]
                },
                "reasoning": "Pie chart best shows proportional distribution of sales across regions",
                "data_count": 4,
                "validation_results": {
                    "sql_valid": True,
                    "data_quality": "high",
                    "completeness": 1.0
                }
            }
        ],
        "natural_language_query": "Generate a comprehensive report analyzing Q4 sales performance with regional insights",
        "additional_context": {
            "user_id": "analyst_001",
            "report_format": "pdf",
            "include_charts": True
        },
        "time_filters": {
            "period": "Q4_2024",
            "start_date": "2024-10-01",
            "end_date": "2024-12-31"
        },
        "render_options": {
            "include_executive_summary": True,
            "include_recommendations": True,
            "chart_format": "high_quality"
        }
    }

async def demonstrate_dashboard_chart_schema_flow():
    """Demonstrate how chart schema flows through dashboard pipeline"""
    print("=== Dashboard Chart Schema Flow Demo ===")
    
    # Create workflow data with chart schemas
    workflow_data = create_dashboard_workflow_with_chart_schemas()
    
    print(f"Workflow ID: {workflow_data['workflow_id']}")
    print(f"Project ID: {workflow_data['project_id']}")
    print(f"Total Components: {len(workflow_data['thread_components'])}")
    
    # Show how chart schemas are extracted
    print("\n--- Chart Schema Extraction ---")
    for i, component in enumerate(workflow_data['thread_components']):
        if component.get('chart_schema'):
            chart_schema = component['chart_schema']
            print(f"Component {i+1}: {component['component_type']}")
            print(f"  Chart Type: {chart_schema.get('type', 'unknown')}")
            print(f"  Title: {chart_schema.get('title', 'No title')}")
            print(f"  Dimensions: {chart_schema.get('width', 'N/A')}x{chart_schema.get('height', 'N/A')}")
            
            if chart_schema.get('type') == 'vega_lite':
                spec = chart_schema.get('spec', {})
                mark = spec.get('mark', 'unknown')
                encoding = spec.get('encoding', {})
                print(f"  Mark Type: {mark}")
                print(f"  X-Axis: {encoding.get('x', {}).get('field', 'N/A')}")
                print(f"  Y-Axis: {encoding.get('y', {}).get('field', 'N/A')}")
            elif chart_schema.get('type') == 'plotly':
                data = chart_schema.get('data', [{}])[0]
                print(f"  Plot Type: {data.get('type', 'unknown')}")
                print(f"  Labels: {data.get('labels', [])}")
    
    # Show how this would be processed by the dashboard service
    print("\n--- Dashboard Service Processing ---")
    print("1. Dashboard service receives workflow data with chart schemas")
    print("2. Service extracts chart schemas from thread components")
    print("3. Service creates dashboard queries with chart_schema field")
    print("4. Service calls dashboard orchestrator pipeline")
    print("5. Pipeline passes chart schemas to data execution pipelines")
    print("6. Data pipelines use chart schemas to generate actionable visualizations")
    
    return workflow_data

async def demonstrate_report_chart_schema_flow():
    """Demonstrate how chart schema flows through report pipeline"""
    print("\n=== Report Chart Schema Flow Demo ===")
    
    # Create workflow data with chart schemas
    workflow_data = create_report_workflow_with_chart_schemas()
    
    print(f"Workflow ID: {workflow_data['workflow_id']}")
    print(f"Project ID: {workflow_data['project_id']}")
    print(f"Total Components: {len(workflow_data['thread_components'])}")
    
    # Show how chart schemas are extracted
    print("\n--- Chart Schema Extraction ---")
    for i, component in enumerate(workflow_data['thread_components']):
        if component.get('chart_schema'):
            chart_schema = component['chart_schema']
            print(f"Component {i+1}: {component['component_type']}")
            print(f"  Chart Type: {chart_schema.get('type', 'unknown')}")
            print(f"  Title: {chart_schema.get('title', 'No title')}")
            
            if chart_schema.get('type') == 'plotly':
                data = chart_schema.get('data', [{}])[0]
                layout = chart_schema.get('layout', {})
                print(f"  Plot Type: {data.get('type', 'unknown')}")
                print(f"  Height: {layout.get('height', 'N/A')}")
                print(f"  Show Legend: {layout.get('showlegend', 'N/A')}")
    
    # Show how this would be processed by the report service
    print("\n--- Report Service Processing ---")
    print("1. Report service receives workflow data with chart schemas")
    print("2. Service extracts chart schemas from thread components")
    print("3. Service creates report queries with chart_schema field")
    print("4. Service calls report orchestrator pipeline")
    print("5. Pipeline passes chart schemas to simple report generation pipeline")
    print("6. Simple report pipeline uses data summarization pipeline for chart execution")
    print("7. Data summarization pipeline executes charts using provided schemas")
    print("8. Generated charts are included in the final report")
    
    return workflow_data

def demonstrate_api_request_structure():
    """Show the structure of API requests with chart schemas"""
    print("\n=== API Request Structure ===")
    
    # Dashboard API request
    dashboard_request = {
        "workflow_id": str(uuid4()),
        "project_id": "sales_analytics",
        "state": "completed",
        "current_step": 3,
        "workflow_metadata": {
            "dashboard_template": "executive_dashboard",
            "dashboard_layout": "grid_2x2",
            "refresh_rate": 300
        },
        "thread_components": [
            {
                "id": str(uuid4()),
                "component_type": "chart",
                "sequence_order": 1,
                "question": "Show Q4 sales by region",
                "sql_query": "SELECT region, SUM(sales_amount) as total_sales FROM sales_data WHERE sale_date >= '2024-10-01' GROUP BY region",
                "chart_schema": VEGA_LITE_BAR_CHART_SCHEMA,
                "chart_config": {
                    "chart_type": "bar",
                    "x_axis": "region",
                    "y_axis": "total_sales"
                }
            }
        ],
        "natural_language_query": "Create a comprehensive dashboard showing Q4 sales performance",
        "additional_context": {},
        "time_filters": {},
        "render_options": {}
    }
    
    print("Dashboard API Request Structure:")
    print(json.dumps(dashboard_request, indent=2))
    
    # Report API request
    report_request = {
        "workflow_id": str(uuid4()),
        "project_id": "sales_report",
        "state": "completed",
        "current_step": 4,
        "workflow_metadata": {
            "report_title": "Q4 2024 Sales Performance Report",
            "writer_actor": "ANALYST"
        },
        "thread_components": [
            {
                "id": str(uuid4()),
                "component_type": "chart",
                "sequence_order": 1,
                "question": "Show regional performance distribution",
                "sql_query": "SELECT region, SUM(sales_amount) as total_sales FROM sales_data WHERE sale_date >= '2024-10-01' GROUP BY region",
                "chart_schema": PLOTLY_PIE_CHART_SCHEMA,
                "chart_config": {
                    "chart_type": "pie",
                    "title": "Regional Distribution"
                }
            }
        ],
        "natural_language_query": "Generate a comprehensive report analyzing Q4 sales performance",
        "additional_context": {},
        "time_filters": {},
        "render_options": {}
    }
    
    print("\nReport API Request Structure:")
    print(json.dumps(report_request, indent=2))

def demonstrate_pipeline_flow():
    """Show how chart schemas flow through the pipeline"""
    print("\n=== Pipeline Flow with Chart Schemas ===")
    
    print("1. API Request")
    print("   ├── DashboardWorkflowRequest/ReportWorkflowRequest")
    print("   ├── Contains thread_components with chart_schema")
    print("   └── chart_schema: Dict[str, Any] (Vega-Lite, Plotly, etc.)")
    
    print("\n2. Service Layer")
    print("   ├── DashboardService/ReportService")
    print("   ├── Extracts chart_schema from components")
    print("   ├── Creates dashboard_queries/report_queries")
    print("   └── Passes chart_schema to pipeline")
    
    print("\n3. Orchestrator Pipeline")
    print("   ├── DashboardOrchestratorPipeline/ReportOrchestratorPipeline")
    print("   ├── Receives queries with chart_schema")
    print("   └── Delegates to streaming/generation pipelines")
    
    print("\n4. Data Execution Pipeline")
    print("   ├── DashboardStreamingPipeline/SimpleReportGenerationPipeline")
    print("   ├── Extracts chart_schema from query data")
    print("   ├── Passes chart_schema to SQL execution pipeline")
    print("   └── chart_schema passed via **kwargs")
    
    print("\n5. SQL Execution Pipeline")
    print("   ├── DataSummarizationPipeline")
    print("   ├── Receives chart_schema in kwargs")
    print("   ├── Uses chart_schema directly for chart execution")
    print("   ├── Creates ChartExecutor with provided schema")
    print("   └── Executes chart with actual SQL data")
    
    print("\n6. Chart Execution")
    print("   ├── ChartExecutor.execute_chart()")
    print("   ├── Uses provided chart_schema instead of generating")
    print("   ├── Executes SQL query with chart configuration")
    print("   ├── Returns executed chart with data")
    print("   └── Chart is now actionable with real data")

async def main():
    """Main demonstration function"""
    print("Chart Schema Pipeline Integration Demo")
    print("=" * 50)
    
    # Demonstrate dashboard flow
    await demonstrate_dashboard_chart_schema_flow()
    
    # Demonstrate report flow
    await demonstrate_report_chart_schema_flow()
    
    # Show API request structure
    demonstrate_api_request_structure()
    
    # Show pipeline flow
    demonstrate_pipeline_flow()
    
    print("\n=== Key Benefits ===")
    print("✅ Chart schemas are passed directly from workflow data")
    print("✅ No need to generate charts - use pre-defined schemas")
    print("✅ Charts are immediately actionable with real data")
    print("✅ Support for multiple chart types (Vega-Lite, Plotly, etc.)")
    print("✅ Consistent chart configuration across workflows")
    print("✅ Better performance - no chart generation overhead")
    print("✅ More predictable results - exact chart specifications")

if __name__ == "__main__":
    asyncio.run(main())
