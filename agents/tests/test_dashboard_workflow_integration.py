#!/usr/bin/env python3
"""
Test file for DashboardService Workflow Integration
Demonstrates workflow-based dashboard processing from various input sources
"""

import asyncio
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from app.services.writers.dashboard_service import create_dashboard_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock dashboard workflow data for testing
MOCK_DASHBOARD_WORKFLOW_DATA = {
    "id": "dashboard-workflow-123",
    "dashboard_id": "dashboard-456",
    "user_id": "user-789",
    "state": "active",
    "current_step": 2,
    "workflow_metadata": {
        "dashboard_title": "Q4 Sales Performance Dashboard",
        "dashboard_description": "Real-time dashboard for Q4 sales performance monitoring",
        "dashboard_template": "executive_dashboard",
        "dashboard_layout": "grid_2x2",
        "refresh_rate": 300,
        "auto_refresh": True,
        "responsive": True,
        "theme": "corporate",
        "custom_styling": {
            "primary_color": "#1f77b4",
            "secondary_color": "#ff7f0e",
            "font_family": "Arial, sans-serif"
        },
        "interactive_features": ["drill_down", "hover_tooltips", "zoom_pan"],
        "export_options": ["pdf", "png", "csv", "excel"],
        "sharing_config": {
            "allow_sharing": True,
            "permissions": ["view", "export"],
            "public_access": False
        },
        "alert_config": {
            "enable_alerts": True,
            "alert_thresholds": {
                "sales_target": 0.8,
                "performance_score": 75
            }
        },
        "performance_config": {
            "lazy_loading": True,
            "data_caching": True,
            "query_optimization": True
        }
    },
    "thread_components": [
        {
            "id": "comp-1",
            "component_type": "overview",
            "sequence_order": 1,
            "question": "Sales Overview",
            "description": "High-level sales performance summary",
            "configuration": {"style": "card", "size": "large"},
            "chart_config": None,
            "table_config": None
        },
        {
            "id": "comp-2",
            "component_type": "chart",
            "sequence_order": 2,
            "question": "Regional Sales Chart",
            "description": "Sales performance by region with interactive chart",
            "configuration": {"interactive": True, "chart_type": "bar"},
            "chart_config": {
                "type": "bar",
                "x_axis": "region",
                "y_axis": "sales_amount",
                "colors": ["#1f77b4", "#ff7f0e", "#2ca02c"],
                "animation": True
            },
            "table_config": None
        },
        {
            "id": "comp-3",
            "component_type": "metric",
            "sequence_order": 3,
            "question": "KPI Metrics",
            "description": "Key performance indicators and targets",
            "configuration": {"display_mode": "grid", "highlight_thresholds": True},
            "chart_config": None,
            "table_config": None
        },
        {
            "id": "comp-4",
            "component_type": "table",
            "sequence_order": 4,
            "question": "Detailed Sales Data",
            "description": "Detailed sales data in tabular format",
            "configuration": {"sortable": True, "filterable": True, "pagination": True},
            "chart_config": None,
            "table_config": {
                "columns": ["date", "region", "product", "sales", "profit"],
                "default_sort": "date",
                "rows_per_page": 25,
                "search_enabled": True
            }
        },
        {
            "id": "comp-5",
            "component_type": "alert",
            "sequence_order": 5,
            "question": "Performance Alerts",
            "description": "Real-time performance alerts and notifications",
            "configuration": {"alert_level": "medium", "auto_dismiss": False},
            "chart_config": None,
            "table_config": None,
            "alert_config": {
                "alert_type": "threshold",
                "severity": "medium",
                "conditions": [
                    {"metric": "sales", "operator": "<", "value": 10000},
                    {"metric": "performance_score", "operator": "<", "value": 75}
                ]
            }
        }
    ]
}

# Mock dashboard queries
MOCK_DASHBOARD_QUERIES = [
    {
        "chart_id": "sales_overview",
        "project_id": "cornerstone",
        "sql": "SELECT region, SUM(sales_amount) as sales, COUNT(*) as transactions FROM sales_data WHERE date >= '2024-10-01' GROUP BY region ORDER BY sales DESC;",
        "query": "Show Q4 sales and transaction count by region",
        "data_description": "Sales data aggregated by region for Q4 2024"
    },
    {
        "chart_id": "performance_trends",
        "project_id": "csodworkday",
        "sql": "SELECT date, AVG(performance_score) as avg_score FROM performance_data WHERE date >= '2024-10-01' GROUP BY date ORDER BY date;",
        "query": "Show average performance score over Q4",
        "data_description": "Performance trends over time for Q4 2024"
    },
    {
        "chart_id": "profit_analysis",
        "project_id": "cornerstone",
        "sql": "SELECT category, SUM(profit) as total_profit, AVG(profit_margin) as avg_margin FROM sales_data WHERE date >= '2024-10-01' GROUP BY category ORDER BY total_profit DESC;",
        "query": "Show profit and margin by category for Q4",
        "data_description": "Profit analysis by product category for Q4 2024"
    }
]

# Mock natural language query
MOCK_NATURAL_LANGUAGE_QUERY = """
Highlight regions with sales above $100,000 in green and below $50,000 in red.
Filter performance data to show only scores above 75.
Emphasize categories with profit margins above 20%.
Add trend indicators for improving and declining metrics.
"""


async def test_dashboard_workflow_from_dict():
    """Test dashboard processing from workflow dictionary input"""
    try:
        
        
        print("🔧 Testing Dashboard Workflow from Dictionary Input")
        print("=" * 60)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Process dashboard from workflow dictionary
        print("🔄 Processing dashboard from workflow dictionary...")
        result = await dashboard_service.process_dashboard_from_workflow(
            workflow_data=MOCK_DASHBOARD_WORKFLOW_DATA,
            dashboard_queries=MOCK_DASHBOARD_QUERIES,
            project_id="test_dashboard_workflow_dict",
            natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
            additional_context={"test_mode": True},
            time_filters={"period": "last_quarter"},
            status_callback=status_callback
        )
        
        print(f"✅ Dashboard Processed: {result.get('success', False)}")
        
        # Check workflow metadata
        workflow_metadata = result.get("workflow_metadata", {})
        print(f"📋 Workflow ID: {workflow_metadata.get('workflow_id')}")
        print(f"🔄 Workflow State: {workflow_metadata.get('workflow_state')}")
        print(f"🔧 Components Processed: {workflow_metadata.get('components_processed')}")
        print(f"📊 Dashboard Template: {workflow_metadata.get('dashboard_template')}")
        print(f"📁 Source: {workflow_metadata.get('workflow_source')}")
        
        # Check dashboard configuration
        dashboard_config = result.get("dashboard_config", {})
        print(f"🎨 Layout: {dashboard_config.get('layout')}")
        print(f"⏱️  Refresh Rate: {dashboard_config.get('refresh_rate')} seconds")
        print(f"🔄 Auto Refresh: {dashboard_config.get('auto_refresh')}")
        print(f"📱 Responsive: {dashboard_config.get('responsive')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in dashboard workflow dict test: {e}")
        return False


async def test_dashboard_workflow_from_json_file():
    """Test dashboard processing from JSON file input"""
    try:
        
        
        print("\n📁 Testing Dashboard Workflow from JSON File Input")
        print("=" * 60)
        
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(MOCK_DASHBOARD_WORKFLOW_DATA, f, indent=2)
            temp_file_path = f.name
        
        try:
            # Create dashboard service
            dashboard_service = create_dashboard_service()
            
            # Status callback for monitoring
            def status_callback(status: str, details: Dict[str, Any] = None):
                print(f"📡 Status: {status} - {details}")
            
            # Process dashboard from JSON file
            print(f"🔄 Processing dashboard from JSON file: {temp_file_path}")
            result = await dashboard_service.process_dashboard_from_workflow(
                workflow_data=temp_file_path,
                dashboard_queries=MOCK_DASHBOARD_QUERIES,
                project_id="test_dashboard_workflow_json_file",
                natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
                status_callback=status_callback
            )
            
            print(f"✅ Dashboard Processed: {result.get('success', False)}")
            
            # Check workflow metadata
            workflow_metadata = result.get("workflow_metadata", {})
            print(f"📋 Workflow ID: {workflow_metadata.get('workflow_id')}")
            print(f"📁 Source: {workflow_metadata.get('workflow_source')}")
            
            return True
            
        finally:
            # Clean up temporary file
            Path(temp_file_path).unlink(missing_ok=True)
        
    except Exception as e:
        print(f"❌ Error in dashboard workflow JSON file test: {e}")
        return False


async def test_dashboard_workflow_from_json_string():
    """Test dashboard processing from JSON string input"""
    try:
        
        
        print("\n📝 Testing Dashboard Workflow from JSON String Input")
        print("=" * 60)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Convert workflow data to JSON string
        workflow_json_string = json.dumps(MOCK_DASHBOARD_WORKFLOW_DATA)
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Process dashboard from JSON string
        print("🔄 Processing dashboard from JSON string...")
        result = await dashboard_service.process_dashboard_from_workflow(
            workflow_data=workflow_json_string,
            dashboard_queries=MOCK_DASHBOARD_QUERIES,
            project_id="test_dashboard_workflow_json_string",
            natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
            status_callback=status_callback
        )
        
        print(f"✅ Dashboard Processed: {result.get('success', False)}")
        
        # Check workflow metadata
        workflow_metadata = result.get("workflow_metadata", {})
        print(f"📋 Workflow ID: {workflow_metadata.get('workflow_id')}")
        print(f"📁 Source: {workflow_metadata.get('workflow_source')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in dashboard workflow JSON string test: {e}")
        return False


async def test_dashboard_config_extraction():
    """Test extraction of dashboard configuration from workflow data"""
    try:
        
        
        print("\n⚙️  Testing Dashboard Configuration Extraction")
        print("=" * 60)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Test configuration extraction
        workflow_info = dashboard_service._parse_dashboard_workflow_data(MOCK_DASHBOARD_WORKFLOW_DATA)
        dashboard_config = dashboard_service._extract_dashboard_config_from_workflow(workflow_info)
        
        print("📊 Extracted Dashboard Configuration:")
        print(f"   Template: {dashboard_config.get('template')}")
        print(f"   Layout: {dashboard_config.get('layout')}")
        print(f"   Refresh Rate: {dashboard_config.get('refresh_rate')} seconds")
        print(f"   Auto Refresh: {dashboard_config.get('auto_refresh')}")
        print(f"   Responsive: {dashboard_config.get('responsive')}")
        print(f"   Theme: {dashboard_config.get('theme')}")
        print(f"   Interactive Features: {dashboard_config.get('interactive_features')}")
        print(f"   Export Options: {dashboard_config.get('export_options')}")
        
        # Check custom styling
        custom_styling = dashboard_config.get("custom_styling", {})
        if custom_styling:
            print(f"   Custom Styling:")
            print(f"     Primary Color: {custom_styling.get('primary_color')}")
            print(f"     Secondary Color: {custom_styling.get('secondary_color')}")
            print(f"     Font Family: {custom_styling.get('font_family')}")
        
        # Check alert configuration
        alert_config = dashboard_config.get("alert_config", {})
        if alert_config:
            print(f"   Alert Configuration:")
            print(f"     Enable Alerts: {alert_config.get('enable_alerts')}")
            print(f"     Sales Target Threshold: {alert_config.get('alert_thresholds', {}).get('sales_target')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in dashboard config extraction test: {e}")
        return False


async def test_thread_component_extraction():
    """Test extraction of thread components from workflow data"""
    try:
        
        
        print("\n🧩 Testing Thread Component Extraction")
        print("=" * 60)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Test component extraction
        workflow_info = dashboard_service._parse_dashboard_workflow_data(MOCK_DASHBOARD_WORKFLOW_DATA)
        thread_components = dashboard_service._extract_thread_components_from_workflow(workflow_info)
        
        print(f"📊 Total Components Extracted: {len(thread_components)}")
        
        for i, component in enumerate(thread_components):
            print(f"\n🔧 Component {i+1}:")
            print(f"   ID: {component.get('id')}")
            print(f"   Type: {component.get('component_type')}")
            print(f"   Title: {component.get('question')}")
            print(f"   Description: {component.get('description')}")
            print(f"   Sequence Order: {component.get('sequence_order')}")
            print(f"   Configuration: {component.get('configuration')}")
            
            # Check chart configuration
            chart_config = component.get("chart_config")
            if chart_config:
                print(f"   Chart Config:")
                print(f"     Type: {chart_config.get('type')}")
                print(f"     X-Axis: {chart_config.get('x_axis')}")
                print(f"     Y-Axis: {chart_config.get('y_axis')}")
                print(f"     Colors: {chart_config.get('colors')}")
                print(f"     Animation: {chart_config.get('animation')}")
            
            # Check table configuration
            table_config = component.get("table_config")
            if table_config:
                print(f"   Table Config:")
                print(f"     Columns: {table_config.get('columns')}")
                print(f"     Default Sort: {table_config.get('default_sort')}")
                print(f"     Rows Per Page: {table_config.get('rows_per_page')}")
                print(f"     Search Enabled: {table_config.get('search_enabled')}")
            
            # Check alert configuration
            alert_config = component.get("alert_config")
            if alert_config:
                print(f"   Alert Config:")
                print(f"     Alert Type: {alert_config.get('alert_type')}")
                print(f"     Severity: {alert_config.get('severity')}")
                print(f"     Conditions: {alert_config.get('conditions')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in thread component extraction test: {e}")
        return False


async def test_enhanced_context_creation():
    """Test creation of enhanced dashboard context from workflow data"""
    try:
        
        
        print("\n📋 Testing Enhanced Dashboard Context Creation")
        print("=" * 60)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Parse workflow data
        workflow_info = dashboard_service._parse_dashboard_workflow_data(MOCK_DASHBOARD_WORKFLOW_DATA)
        dashboard_config = dashboard_service._extract_dashboard_config_from_workflow(workflow_info)
        thread_components = dashboard_service._extract_thread_components_from_workflow(workflow_info)
        
        # Create enhanced context
        enhanced_context = dashboard_service._create_enhanced_dashboard_context(
            workflow_info, dashboard_config, thread_components
        )
        
        print("📋 Generated Enhanced Dashboard Context:")
        print(f"   Title: {enhanced_context.get('title')}")
        print(f"   Description: {enhanced_context.get('description')}")
        print(f"   Template: {enhanced_context.get('template')}")
        print(f"   Layout: {enhanced_context.get('layout')}")
        print(f"   Refresh Rate: {enhanced_context.get('refresh_rate')} seconds")
        print(f"   Auto Refresh: {enhanced_context.get('auto_refresh')}")
        print(f"   Responsive: {enhanced_context.get('responsive')}")
        print(f"   Theme: {enhanced_context.get('theme')}")
        print(f"   Interactive Features: {enhanced_context.get('interactive_features')}")
        print(f"   Export Options: {enhanced_context.get('export_options')}")
        print(f"   Workflow ID: {enhanced_context.get('workflow_id')}")
        print(f"   Workflow State: {enhanced_context.get('workflow_state')}")
        
        # Check components
        components = enhanced_context.get("components", [])
        print(f"\n🔧 Components ({len(components)}):")
        for comp in components:
            print(f"   - {comp.get('title')} ({comp.get('type')}) - Order: {comp.get('sequence_order')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in enhanced context creation test: {e}")
        return False


async def test_dashboard_workflow_validation():
    """Test dashboard workflow data validation"""
    try:
       
        
        print("\n✅ Testing Dashboard Workflow Data Validation")
        print("=" * 60)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Test valid workflow data
        print("🔍 Testing valid workflow data...")
        workflow_info = dashboard_service._parse_dashboard_workflow_data(MOCK_DASHBOARD_WORKFLOW_DATA)
        is_valid = workflow_info is not None
        print(f"   Valid Workflow Data: {is_valid}")
        
        # Test invalid workflow data
        print("\n🔍 Testing invalid workflow data...")
        invalid_workflow = {"invalid": "data"}
        invalid_info = dashboard_service._parse_dashboard_workflow_data(invalid_workflow)
        is_invalid = invalid_info is None
        print(f"   Invalid Workflow Data Handled: {is_invalid}")
        
        # Test validation of dashboard configuration
        print("\n🔍 Testing dashboard configuration validation...")
        if workflow_info:
            dashboard_config = dashboard_service._extract_dashboard_config_from_workflow(workflow_info)
            config_valid = all(key in dashboard_config for key in ["template", "layout", "refresh_rate"])
            print(f"   Dashboard Configuration Valid: {config_valid}")
            print(f"   Template: {dashboard_config.get('template')}")
            print(f"   Layout: {dashboard_config.get('layout')}")
            print(f"   Refresh Rate: {dashboard_config.get('refresh_rate')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in validation test: {e}")
        return False


async def test_dashboard_workflow_error_handling():
    """Test error handling for dashboard workflow operations"""
    try:
        
        
        print("\n⚠️  Testing Dashboard Workflow Error Handling")
        print("=" * 60)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Test with non-existent file
        print("🔍 Testing non-existent file handling...")
        try:
            workflow_info = dashboard_service._parse_dashboard_workflow_data("/non/existent/file.json")
            print(f"   Non-existent file handled: {workflow_info is None}")
        except Exception as e:
            print(f"   Non-existent file error caught: {type(e).__name__}")
        
        # Test with malformed JSON
        print("\n🔍 Testing malformed JSON handling...")
        try:
            workflow_info = dashboard_service._parse_dashboard_workflow_data('{"invalid": json}')
            print(f"   Malformed JSON handled: {workflow_info is None}")
        except Exception as e:
            print(f"   Malformed JSON error caught: {type(e).__name__}")
        
        # Test with empty workflow data
        print("\n🔍 Testing empty workflow data handling...")
        try:
            workflow_info = dashboard_service._parse_dashboard_workflow_data({})
            print(f"   Empty workflow data handled: {workflow_info is not None}")
        except Exception as e:
            print(f"   Empty workflow data error caught: {type(e).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in error handling test: {e}")
        return False


async def test_dashboard_workflow_integration_end_to_end():
    """Test complete end-to-end dashboard workflow integration"""
    try:
        
        
        print("\n🚀 Testing End-to-End Dashboard Workflow Integration")
        print("=" * 70)
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Test with different workflow input types
        test_cases = [
            ("Dictionary Input", MOCK_DASHBOARD_WORKFLOW_DATA),
            ("JSON String Input", json.dumps(MOCK_DASHBOARD_WORKFLOW_DATA)),
        ]
        
        results = []
        
        for test_name, workflow_input in test_cases:
            print(f"\n🔍 Testing: {test_name}")
            try:
                result = await dashboard_service.process_dashboard_from_workflow(
                    workflow_data=workflow_input,
                    dashboard_queries=MOCK_DASHBOARD_QUERIES,
                    project_id=f"test_e2e_dashboard_{test_name.lower().replace(' ', '_')}",
                    natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
                    status_callback=status_callback
                )
                
                success = result.get('success', False)
                results.append((test_name, success))
                print(f"   ✅ {test_name}: {'SUCCESS' if success else 'FAILED'}")
                
                # Check workflow metadata
                workflow_metadata = result.get("workflow_metadata", {})
                print(f"   📋 Workflow ID: {workflow_metadata.get('workflow_id')}")
                print(f"   📊 Template: {workflow_metadata.get('dashboard_template')}")
                print(f"   🔧 Components: {workflow_metadata.get('components_processed')}")
                
            except Exception as e:
                results.append((test_name, False))
                print(f"   ❌ {test_name}: ERROR - {type(e).__name__}")
        
        # Summary
        print(f"\n📊 End-to-End Dashboard Test Results:")
        successful = sum(1 for _, success in results if success)
        total = len(results)
        print(f"   Successful: {successful}/{total}")
        
        return successful == total
        
    except Exception as e:
        print(f"❌ Error in end-to-end dashboard test: {e}")
        return False


async def main():
    """Run all dashboard workflow integration tests"""
    print("🧪 Dashboard Service Workflow Integration Test Suite")
    print("=" * 80)
    
    tests = [
        ("Dashboard Workflow from Dictionary", test_dashboard_workflow_from_dict),
        ("Dashboard Workflow from JSON File", test_dashboard_workflow_from_json_file),
        ("Dashboard Workflow from JSON String", test_dashboard_workflow_from_json_string),
        ("Dashboard Configuration Extraction", test_dashboard_config_extraction),
        ("Thread Component Extraction", test_thread_component_extraction),
        ("Enhanced Context Creation", test_enhanced_context_creation),
        ("Dashboard Workflow Validation", test_dashboard_workflow_validation),
        ("Error Handling", test_dashboard_workflow_error_handling),
        ("End-to-End Dashboard Integration", test_dashboard_workflow_integration_end_to_end)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔍 Running: {test_name}")
            result = await test_func()
            results[test_name] = result
            print(f"✅ {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Dashboard Workflow Integration Test Results Summary")
    print("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All dashboard workflow integration tests passed! Dashboard Service is ready for production use.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return results


if __name__ == "__main__":
    # Run the dashboard workflow integration test suite
    asyncio.run(main())
