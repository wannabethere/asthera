#!/usr/bin/env python3
"""
Test file for ReportService
Demonstrates basic usage and functionality
"""

import asyncio
import logging
from typing import Dict, Any
from app.services.writers.report_service import ReportService,create_report_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock data for testing (in real usage, you'd get this from your database)
MOCK_REPORT_QUERIES = [
    {
        "project_id": "cornerstone",
        "sql": "SELECT region, SUM(sales_amount) as sales, COUNT(*) as transactions FROM sales_data GROUP BY region ORDER BY sales DESC;",
        "query": "Show sales and transaction count by region",
        "data_description": "Sales data aggregated by region"
    },
    {
        "project_id": "csodworkday",
        "sql": "SELECT date, AVG(performance_score) as avg_score FROM performance_data WHERE date >= '2024-01-01' GROUP BY date ORDER BY date;",
        "query": "Show average performance score over time",
        "data_description": "Performance trends over time"
    },
    {
        "project_id": "cornerstone",
        "sql": "SELECT category, SUM(profit) as total_profit, AVG(profit_margin) as avg_margin FROM sales_data GROUP BY category ORDER BY total_profit DESC;",
        "query": "Show profit and margin by category",
        "data_description": "Profit analysis by product category"
    }
]

MOCK_REPORT_CONTEXT = {
    "title": "Q4 2024 Sales Performance Report",
    "description": "Comprehensive analysis of Q4 sales performance across regions and categories with performance insights",
    "sections": [
        "executive_summary",
        "regional_analysis", 
        "performance_trends",
        "category_insights",
        "recommendations"
    ],
    "available_columns": ["date", "region", "sales", "quantity", "profit", "category", "status", "performance_score"],
    "data_types": {
        "date": "datetime",
        "region": "categorical",
        "sales": "numeric",
        "quantity": "numeric",
        "profit": "numeric",
        "category": "categorical",
        "status": "categorical",
        "performance_score": "numeric"
    }
}

MOCK_NATURAL_LANGUAGE_QUERY = """
Highlight regions with sales above $100,000 in green and below $50,000 in red.
Filter performance data to show only scores above 75.
Emphasize categories with profit margins above 20%.
Add trend indicators for improving and declining metrics.
"""


async def test_report_service_basic():
    """Test basic report service functionality"""
    try:
        
        print("🚀 Testing Report Service Basic Functionality")
        print("=" * 50)
        
        # Create report service
        report_service = create_report_service()
        
        # Check service status
        status = report_service.get_service_status()
        print(f"✅ Service Status: {status['report_orchestrator']['available']}")
        print(f"📊 Available Templates: {status['report_templates']['available_templates']}")
        
        # Validate configuration
        validation = report_service.validate_report_configuration(
            MOCK_REPORT_QUERIES, 
            MOCK_REPORT_CONTEXT, 
            MOCK_NATURAL_LANGUAGE_QUERY
        )
        
        print(f"✅ Configuration Valid: {validation['valid']}")
        if validation['warnings']:
            print(f"⚠️  Warnings: {validation['warnings']}")
        if validation['issues']:
            print(f"❌ Issues: {validation['issues']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in basic test: {e}")
        return False


async def test_report_templates():
    """Test report template functionality"""
    try:
        
        print("\n📋 Testing Report Templates")
        print("=" * 30)
        
        report_service = create_report_service()
        
        # Get available templates
        templates = report_service.get_available_templates()
        print(f"📚 Available Templates: {list(templates.keys())}")
        
        # Test adding custom template
        custom_template = {
            "name": "Custom Sales Report",
            "description": "Custom template for sales analysis",
            "components": ["overview", "sales_analysis", "insights"],
            "writer_actor": "DATA_ANALYST",
            "business_goal": "OPERATIONAL_INSIGHTS"
        }
        
        success = report_service.add_custom_template("custom_sales", custom_template)
        print(f"✅ Custom Template Added: {success}")
        
        # Verify template was added
        updated_templates = report_service.get_available_templates()
        print(f"📚 Updated Templates: {list(updated_templates.keys())}")
        
        # Test removing template
        remove_success = report_service.remove_template("custom_sales")
        print(f"✅ Custom Template Removed: {remove_success}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in template test: {e}")
        return False


async def test_simple_report_generation():
    """Test simple report generation (without comprehensive components)"""
    try:
        from report_service import create_report_service
        
        print("\n📊 Testing Simple Report Generation")
        print("=" * 40)
        
        report_service = create_report_service()
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Generate simple report
        print("🔄 Generating simple report...")
        result = await report_service.generate_simple_report(
            report_queries=MOCK_REPORT_QUERIES,
            project_id="test_simple_report",
            report_context=MOCK_REPORT_CONTEXT,
            status_callback=status_callback
        )
        
        print(f"✅ Simple Report Generated: {result.get('post_process', {}).get('success', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in simple report test: {e}")
        return False


async def test_conditional_formatting_only():
    """Test conditional formatting generation only"""
    try:
       
        
        print("\n🎨 Testing Conditional Formatting Only")
        print("=" * 40)
        
        report_service = create_report_service()
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Generate conditional formatting only
        print("🔄 Generating conditional formatting...")
        result = await report_service.generate_conditional_formatting_only(
            natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
            report_context=MOCK_REPORT_CONTEXT,
            project_id="test_conditional_formatting",
            status_callback=status_callback
        )
        
        print(f"✅ Conditional Formatting Generated: {result.get('post_process', {}).get('success', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in conditional formatting test: {e}")
        return False


async def test_comprehensive_report_generation():
    """Test comprehensive report generation with all features"""
    try:
        
        
        print("\n📈 Testing Comprehensive Report Generation")
        print("=" * 50)
        
        report_service = create_report_service()
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📡 Status: {status} - {details}")
        
        # Generate comprehensive report using executive summary template
        print("🔄 Generating comprehensive report with executive summary template...")
        result = await report_service.generate_comprehensive_report(
            report_queries=MOCK_REPORT_QUERIES,
            project_id="test_comprehensive_report",
            report_context=MOCK_REPORT_CONTEXT,
            natural_language_query=MOCK_NATURAL_LANGUAGE_QUERY,
            report_template="executive_summary",
            additional_context={"user_id": "test_user", "report_period": "Q4 2024"},
            time_filters={"period": "last_quarter"},
            status_callback=status_callback
        )
        
        print(f"✅ Comprehensive Report Generated: {result.get('post_process', {}).get('success', False)}")
        
        # Check orchestration metadata
        orchestration_metadata = result.get('post_process', {}).get('orchestration_metadata', {})
        print(f"🎨 Conditional Formatting Applied: {orchestration_metadata.get('conditional_formatting_applied', False)}")
        print(f"📝 Comprehensive Report Generated: {orchestration_metadata.get('comprehensive_report_generated', False)}")
        print(f"⏱️  Execution Time: {orchestration_metadata.get('total_execution_time_seconds', 0)} seconds")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in comprehensive report test: {e}")
        return False


async def test_execution_history():
    """Test execution history functionality"""
    try:
        
        
        print("\n📚 Testing Execution History")
        print("=" * 30)
        
        report_service = create_report_service()
        
        # Get execution history
        history = report_service.get_execution_history(limit=10)
        print(f"📊 Execution History Entries: {len(history)}")
        
        if history:
            latest_entry = history[-1]
            print(f"🕒 Latest Execution: {latest_entry.get('timestamp', 'N/A')}")
            print(f"📋 Project ID: {latest_entry.get('project_id', 'N/A')}")
            print(f"✅ Success: {latest_entry.get('success', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in execution history test: {e}")
        return False


async def main():
    """Run all tests"""
    print("🧪 Report Service Test Suite")
    print("=" * 50)
    
    tests = [
        ("Basic Functionality", test_report_service_basic),
        ("Report Templates", test_report_templates),
        ("Simple Report Generation", test_simple_report_generation),
        ("Conditional Formatting Only", test_conditional_formatting_only),
        ("Comprehensive Report Generation", test_comprehensive_report_generation),
        ("Execution History", test_execution_history)
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
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Report Service is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())
