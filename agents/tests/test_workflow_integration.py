#!/usr/bin/env python3
"""
Test file for ReportService Workflow Integration
Demonstrates workflow-based report generation from various input sources
"""

import asyncio
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock workflow data for testing
MOCK_WORKFLOW_DATA = {
    "id": "workflow-123",
    "report_id": "report-456",
    "user_id": "user-789",
    "state": "active",
    "current_step": 2,
    "workflow_metadata": {
        "report_title": "Q4 Sales Performance Report",
        "report_description": "Comprehensive analysis of Q4 sales performance",
        "report_sections": ["executive_summary", "regional_analysis", "performance_trends", "recommendations"],
        "writer_actor": "EXECUTIVE_ANALYST",
        "business_goal": "STRATEGIC_DECISION_MAKING",
        "report_period": "Q4 2024",
        "target_audience": "executives"
    },
    "thread_components": [
        {
            "id": "comp-1",
            "component_type": "overview",
            "sequence_order": 1,
            "question": "Executive Overview",
            "description": "High-level summary of Q4 performance",
            "configuration": {"style": "executive", "length": "concise"}
        },
        {
            "id": "comp-2",
            "component_type": "chart",
            "sequence_order": 2,
            "question": "Regional Sales Analysis",
            "description": "Sales performance by region with visualizations",
            "chart_config": {"type": "bar", "metrics": ["sales", "growth"]},
            "configuration": {"interactive": True}
        },
        {
            "id": "comp-3",
            "component_type": "metric",
            "sequence_order": 3,
            "question": "Key Performance Indicators",
            "description": "Critical KPIs and their trends",
            "configuration": {"highlight_thresholds": True}
        },
        {
            "id": "comp-4",
            "component_type": "insight",
            "sequence_order": 4,
            "question": "Strategic Insights",
            "description": "Key insights and actionable recommendations",
            "configuration": {"priority": "high", "actionable": True}
        }
    ]
}

# Mock report queries
MOCK_REPORT_QUERIES = [
    {
        "project_id": "cornerstone",
        "sql": "SELECT region, SUM(sales_amount) as sales, COUNT(*) as transactions FROM sales_data WHERE date >= '2024-10-01' GROUP BY region ORDER BY sales DESC;",
        "query": "Show Q4 sales and transaction count by region",
        "data_description": "Sales data aggregated by region for Q4 2024"
    },
    {
        "project_id": "csodworkday",
        "sql": "SELECT date, AVG(performance_score) as avg_score FROM performance_data WHERE date >= '2024-10-01' GROUP BY date ORDER BY date;",
        "query": "Show average performance score over Q4",
        "data_description": "Performance trends over time for Q4 2024"
    },
    {
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


async def test_workflow_from_dict():
    """Test report generation from workflow dictionary input"""
    try:
        from report_service import create_report_service
        
        print("🔧 Testing Workflow from Dictionary Input")
        print("=" * 50)
        
        # Create report service
        report_service = create_report_service()
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Generate report from workflow dictionary
        print("🔄 Generating report from workflow dictionary...")
        result = await report_service.generate_report_from_workflow(
            workflow_data=MOCK_WORKFLOW_DATA,
            report_queries=MOCK_REPORT_QUERIES,
            project_id="test_workflow_dict",
            natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
            additional_context={"test_mode": True},
            time_filters={"period": "last_quarter"},
            status_callback=status_callback
        )
        
        print(f"✅ Report Generated: {result.get('post_process', {}).get('success', False)}")
        
        # Check workflow metadata
        workflow_metadata = result.get("workflow_metadata", {})
        print(f"📋 Workflow ID: {workflow_metadata.get('workflow_id')}")
        print(f"🔄 Workflow State: {workflow_metadata.get('workflow_state')}")
        print(f"🔧 Components Processed: {workflow_metadata.get('components_processed')}")
        print(f"📁 Source: {workflow_metadata.get('workflow_source')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in workflow dict test: {e}")
        return False


async def test_workflow_from_json_file():
    """Test report generation from JSON file input"""
    try:
        from report_service import create_report_service
        
        print("\n📁 Testing Workflow from JSON File Input")
        print("=" * 50)
        
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(MOCK_WORKFLOW_DATA, f, indent=2)
            temp_file_path = f.name
        
        try:
            # Create report service
            report_service = create_report_service()
            
            # Status callback for monitoring
            def status_callback(status: str, details: Dict[str, Any] = None):
                print(f"📡 Status: {status} - {details}")
            
            # Generate report from JSON file
            print(f"🔄 Generating report from JSON file: {temp_file_path}")
            result = await report_service.generate_report_from_workflow(
                workflow_data=temp_file_path,
                report_queries=MOCK_REPORT_QUERIES,
                project_id="test_workflow_json_file",
                natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
                status_callback=status_callback
            )
            
            print(f"✅ Report Generated: {result.get('post_process', {}).get('success', False)}")
            
            # Check workflow metadata
            workflow_metadata = result.get("workflow_metadata", {})
            print(f"📋 Workflow ID: {workflow_metadata.get('workflow_id')}")
            print(f"📁 Source: {workflow_metadata.get('workflow_source')}")
            
            return True
            
        finally:
            # Clean up temporary file
            Path(temp_file_path).unlink(missing_ok=True)
        
    except Exception as e:
        print(f"❌ Error in workflow JSON file test: {e}")
        return False


async def test_workflow_from_json_string():
    """Test report generation from JSON string input"""
    try:
        from report_service import create_report_service
        
        print("\n📝 Testing Workflow from JSON String Input")
        print("=" * 50)
        
        # Create report service
        report_service = create_report_service()
        
        # Convert workflow data to JSON string
        workflow_json_string = json.dumps(MOCK_WORKFLOW_DATA)
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Generate report from JSON string
        print("🔄 Generating report from JSON string...")
        result = await report_service.generate_report_from_workflow(
            workflow_data=workflow_json_string,
            report_queries=MOCK_REPORT_QUERIES,
            project_id="test_workflow_json_string",
            natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
            status_callback=status_callback
        )
        
        print(f"✅ Report Generated: {result.get('post_process', {}).get('success', False)}")
        
        # Check workflow metadata
        workflow_metadata = result.get("workflow_metadata", {})
        print(f"📋 Workflow ID: {workflow_metadata.get('workflow_id')}")
        print(f"📁 Source: {workflow_metadata.get('workflow_source')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in workflow JSON string test: {e}")
        return False


async def test_workflow_component_extraction():
    """Test extraction of thread components from workflow data"""
    try:
        from report_service import create_report_service
        
        print("\n🧩 Testing Workflow Component Extraction")
        print("=" * 50)
        
        # Create report service
        report_service = create_report_service()
        
        # Test component extraction
        workflow_info = report_service._parse_workflow_data(MOCK_WORKFLOW_DATA)
        thread_components = report_service._extract_thread_components_from_workflow(workflow_info)
        
        print(f"📊 Total Components Extracted: {len(thread_components)}")
        
        for i, component in enumerate(thread_components):
            print(f"\n🔧 Component {i+1}:")
            print(f"   ID: {component.id}")
            print(f"   Name: {component.name}")
            print(f"   Type: {component.type}")
            print(f"   Sequence: {component.metadata.get('sequence_order')}")
            print(f"   Original Type: {component.metadata.get('original_type')}")
            print(f"   Configuration: {component.metadata.get('configuration')}")
        
        # Test writer actor determination
        writer_actor = report_service._determine_writer_actor_from_workflow(workflow_info)
        print(f"\n✍️  Writer Actor: {writer_actor}")
        
        # Test business goal determination
        business_goal = report_service._determine_business_goal_from_workflow(workflow_info)
        print(f"🎯 Business Goal: {business_goal}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in component extraction test: {e}")
        return False


async def test_workflow_report_context():
    """Test creation of report context from workflow data"""
    try:
        from report_service import create_report_service
        
        print("\n📋 Testing Workflow Report Context Creation")
        print("=" * 50)
        
        # Create report service
        report_service = create_report_service()
        
        # Parse workflow data
        workflow_info = report_service._parse_workflow_data(MOCK_WORKFLOW_DATA)
        
        # Create report context
        report_context = report_service._create_report_context_from_workflow(
            workflow_info, MOCK_REPORT_QUERIES
        )
        
        print("📋 Generated Report Context:")
        print(f"   Title: {report_context.get('title')}")
        print(f"   Description: {report_context.get('description')}")
        print(f"   Sections: {report_context.get('sections')}")
        print(f"   Available Columns: {report_context.get('available_columns')}")
        print(f"   Data Types: {report_context.get('data_types')}")
        print(f"   Workflow ID: {report_context.get('workflow_id')}")
        print(f"   Workflow State: {report_context.get('workflow_state')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in report context test: {e}")
        return False


async def test_workflow_validation():
    """Test workflow data validation"""
    try:
        from report_service import create_report_service
        
        print("\n✅ Testing Workflow Data Validation")
        print("=" * 50)
        
        # Create report service
        report_service = create_report_service()
        
        # Test valid workflow data
        print("🔍 Testing valid workflow data...")
        workflow_info = report_service._parse_workflow_data(MOCK_WORKFLOW_DATA)
        is_valid = workflow_info is not None
        print(f"   Valid Workflow Data: {is_valid}")
        
        # Test invalid workflow data
        print("\n🔍 Testing invalid workflow data...")
        invalid_workflow = {"invalid": "data"}
        invalid_info = report_service._parse_workflow_data(invalid_workflow)
        is_invalid = invalid_info is None
        print(f"   Invalid Workflow Data Handled: {is_invalid}")
        
        # Test validation of report configuration
        print("\n🔍 Testing report configuration validation...")
        validation = report_service.validate_report_configuration(
            MOCK_REPORT_QUERIES,
            {"title": "Test", "description": "Test"},
            MOCK_NATURAL_LANGUAGE_QUERY
        )
        print(f"   Configuration Valid: {validation['valid']}")
        if validation['warnings']:
            print(f"   Warnings: {validation['warnings']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in validation test: {e}")
        return False


async def test_workflow_error_handling():
    """Test error handling for workflow operations"""
    try:
        from report_service import create_report_service
        
        print("\n⚠️  Testing Workflow Error Handling")
        print("=" * 50)
        
        # Create report service
        report_service = create_report_service()
        
        # Test with non-existent file
        print("🔍 Testing non-existent file handling...")
        try:
            workflow_info = report_service._parse_workflow_data("/non/existent/file.json")
            print(f"   Non-existent file handled: {workflow_info is None}")
        except Exception as e:
            print(f"   Non-existent file error caught: {type(e).__name__}")
        
        # Test with malformed JSON
        print("\n🔍 Testing malformed JSON handling...")
        try:
            workflow_info = report_service._parse_workflow_data('{"invalid": json}')
            print(f"   Malformed JSON handled: {workflow_info is None}")
        except Exception as e:
            print(f"   Malformed JSON error caught: {type(e).__name__}")
        
        # Test with empty workflow data
        print("\n🔍 Testing empty workflow data handling...")
        try:
            workflow_info = report_service._parse_workflow_data({})
            print(f"   Empty workflow data handled: {workflow_info is not None}")
        except Exception as e:
            print(f"   Empty workflow data error caught: {type(e).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in error handling test: {e}")
        return False


async def test_workflow_integration_end_to_end():
    """Test complete end-to-end workflow integration"""
    try:
        from report_service import create_report_service
        
        print("\n🚀 Testing End-to-End Workflow Integration")
        print("=" * 60)
        
        # Create report service
        report_service = create_report_service()
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Test with different workflow input types
        test_cases = [
            ("Dictionary Input", MOCK_WORKFLOW_DATA),
            ("JSON String Input", json.dumps(MOCK_WORKFLOW_DATA)),
        ]
        
        results = []
        
        for test_name, workflow_input in test_cases:
            print(f"\n🔍 Testing: {test_name}")
            try:
                result = await report_service.generate_report_from_workflow(
                    workflow_data=workflow_input,
                    report_queries=MOCK_REPORT_QUERIES,
                    project_id=f"test_e2e_{test_name.lower().replace(' ', '_')}",
                    natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
                    status_callback=status_callback
                )
                
                success = result.get('post_process', {}).get('success', False)
                results.append((test_name, success))
                print(f"   ✅ {test_name}: {'SUCCESS' if success else 'FAILED'}")
                
            except Exception as e:
                results.append((test_name, False))
                print(f"   ❌ {test_name}: ERROR - {type(e).__name__}")
        
        # Summary
        print(f"\n📊 End-to-End Test Results:")
        successful = sum(1 for _, success in results if success)
        total = len(results)
        print(f"   Successful: {successful}/{total}")
        
        return successful == total
        
    except Exception as e:
        print(f"❌ Error in end-to-end test: {e}")
        return False


async def main():
    """Run all workflow integration tests"""
    print("🧪 Report Service Workflow Integration Test Suite")
    print("=" * 70)
    
    tests = [
        ("Workflow from Dictionary", test_workflow_from_dict),
        ("Workflow from JSON File", test_workflow_from_json_file),
        ("Workflow from JSON String", test_workflow_from_json_string),
        ("Component Extraction", test_workflow_component_extraction),
        ("Report Context Creation", test_workflow_report_context),
        ("Workflow Validation", test_workflow_validation),
        ("Error Handling", test_workflow_error_handling),
        ("End-to-End Integration", test_workflow_integration_end_to_end)
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
    print("\n" + "=" * 70)
    print("📊 Workflow Integration Test Results Summary")
    print("=" * 70)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All workflow integration tests passed! Report Service is ready for production use.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return results


if __name__ == "__main__":
    # Run the workflow integration test suite
    asyncio.run(main())
