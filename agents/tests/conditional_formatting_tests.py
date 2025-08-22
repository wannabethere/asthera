import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta

from dashboard_conditional_formatting import (
    DashboardConditionalFormattingService,
    ConditionalFormattingPipeline,
    DashboardConfiguration,
    ControlFilter,
    ConditionalFormat,
    FilterOperator,
    FilterType,
    ActionType,
    create_conditional_formatting_service
)

from dashboard_integration import (
    EnhancedDashboardService,
    ConditionalFormattingUtils,
    add_conditional_formatting_to_pipeline_container
)

class ConditionalFormattingExamples:
    """Collection of example configurations and test cases"""
    
    @staticmethod
    def get_sales_dashboard_context() -> Dict[str, Any]:
        """Sales dashboard context with multiple chart types"""
        return {
            "charts": [
                {
                    "chart_id": "sales_by_region",
                    "type": "bar",
                    "columns": ["region", "sales_amount", "order_count", "date"],
                    "query": "Show sales performance by region",
                    "sql": "SELECT region, SUM(sales_amount) as sales_amount, COUNT(*) as order_count FROM sales GROUP BY region"
                },
                {
                    "chart_id": "monthly_trends",
                    "type": "line", 
                    "columns": ["month", "revenue", "profit_margin", "customer_count"],
                    "query": "Show monthly revenue trends",
                    "sql": "SELECT DATE_TRUNC('month', date) as month, SUM(revenue) as revenue, AVG(profit_margin) as profit_margin, COUNT(DISTINCT customer_id) as customer_count FROM sales GROUP BY month ORDER BY month"
                },
                {
                    "chart_id": "product_performance",
                    "type": "pie",
                    "columns": ["product_category", "total_sales", "units_sold"],
                    "query": "Show product category breakdown",
                    "sql": "SELECT product_category, SUM(sales_amount) as total_sales, SUM(quantity) as units_sold FROM sales GROUP BY product_category"
                },
                {
                    "chart_id": "sales_rep_performance",
                    "type": "table",
                    "columns": ["sales_rep", "quota", "actual_sales", "achievement_rate", "status"],
                    "query": "Show sales representative performance",
                    "sql": "SELECT sales_rep, quota, actual_sales, (actual_sales / quota * 100) as achievement_rate, status FROM sales_performance"
                }
            ],
            "available_columns": [
                "region", "sales_amount", "order_count", "date", "month", "revenue", 
                "profit_margin", "customer_count", "product_category", "total_sales", 
                "units_sold", "sales_rep", "quota", "actual_sales", "achievement_rate", 
                "status", "customer_type", "discount_rate", "shipping_cost"
            ],
            "data_types": {
                "sales_amount": "numeric",
                "revenue": "numeric",
                "profit_margin": "numeric",
                "customer_count": "numeric",
                "total_sales": "numeric",
                "units_sold": "numeric",
                "quota": "numeric",
                "actual_sales": "numeric",
                "achievement_rate": "numeric",
                "discount_rate": "numeric",
                "shipping_cost": "numeric",
                "date": "datetime",
                "month": "datetime",
                "region": "categorical",
                "product_category": "categorical",
                "sales_rep": "categorical",
                "status": "categorical",
                "customer_type": "categorical"
            }
        }
    
    @staticmethod
    def get_financial_dashboard_context() -> Dict[str, Any]:
        """Financial dashboard context"""
        return {
            "charts": [
                {
                    "chart_id": "kpi_metrics",
                    "type": "metric",
                    "columns": ["metric_name", "current_value", "target_value", "variance"],
                    "query": "Show key financial KPIs",
                    "sql": "SELECT metric_name, current_value, target_value, (current_value - target_value) as variance FROM financial_kpis"
                },
                {
                    "chart_id": "budget_vs_actual",
                    "type": "bar",
                    "columns": ["department", "budget", "actual_spend", "variance_pct"],
                    "query": "Show budget vs actual spending",
                    "sql": "SELECT department, budget, actual_spend, ((actual_spend - budget) / budget * 100) as variance_pct FROM budget_analysis"
                },
                {
                    "chart_id": "cash_flow",
                    "type": "line",
                    "columns": ["date", "cash_inflow", "cash_outflow", "net_cash_flow"],
                    "query": "Show cash flow trends",
                    "sql": "SELECT date, cash_inflow, cash_outflow, (cash_inflow - cash_outflow) as net_cash_flow FROM cash_flow ORDER BY date"
                }
            ],
            "available_columns": [
                "metric_name", "current_value", "target_value", "variance", "department",
                "budget", "actual_spend", "variance_pct", "date", "cash_inflow", 
                "cash_outflow", "net_cash_flow", "account_type", "cost_center"
            ],
            "data_types": {
                "current_value": "numeric",
                "target_value": "numeric", 
                "variance": "numeric",
                "budget": "numeric",
                "actual_spend": "numeric",
                "variance_pct": "numeric",
                "cash_inflow": "numeric",
                "cash_outflow": "numeric",
                "net_cash_flow": "numeric",
                "date": "datetime",
                "metric_name": "categorical",
                "department": "categorical",
                "account_type": "categorical",
                "cost_center": "categorical"
            }
        }

class ConditionalFormattingTestCases:
    """Test cases for different conditional formatting scenarios"""
    
    def __init__(self):
        self.service = create_conditional_formatting_service()
    
    async def test_basic_highlighting(self) -> Dict[str, Any]:
        """Test basic conditional highlighting"""
        query = "Highlight sales amounts greater than $100,000 in green and less than $50,000 in red"
        
        dashboard_context = ConditionalFormattingExamples.get_sales_dashboard_context()
        
        result = await self.service.process_conditional_formatting_request(
            query=query,
            dashboard_context=dashboard_context,
            project_id="test_basic_highlighting"
        )
        
        return result
    
    async def test_time_based_filtering(self) -> Dict[str, Any]:
        """Test time-based filtering"""
        query = "Show only data from the last 30 days and highlight current month in blue"
        
        dashboard_context = ConditionalFormattingExamples.get_sales_dashboard_context()
        
        time_filters = {
            "period": "last_30_days",
            "highlight_current_month": True
        }
        
        result = await self.service.process_conditional_formatting_request(
            query=query,
            dashboard_context=dashboard_context,
            project_id="test_time_filtering",
            time_filters=time_filters
        )
        
        return result
    
    async def test_performance_thresholds(self) -> Dict[str, Any]:
        """Test performance-based thresholds"""
        query = """
        For the sales rep performance chart:
        - Highlight achievement rates above 120% in dark green
        - Highlight achievement rates between 100-120% in light green  
        - Highlight achievement rates between 80-100% in yellow
        - Highlight achievement rates below 80% in red
        Also filter to show only active sales reps.
        """
        
        dashboard_context = ConditionalFormattingExamples.get_sales_dashboard_context()
        
        additional_context = {
            "performance_thresholds": {
                "excellent": 120,
                "good": 100,
                "acceptable": 80,
                "needs_improvement": 0
            }
        }
        
        result = await self.service.process_conditional_formatting_request(
            query=query,
            dashboard_context=dashboard_context,
            project_id="test_performance_thresholds",
            additional_context=additional_context
        )
        
        return result
    
    async def test_financial_variance_analysis(self) -> Dict[str, Any]:
        """Test financial variance analysis formatting"""
        query = """
        For the budget analysis:
        - Highlight departments over budget (positive variance) in red
        - Highlight departments under budget (negative variance) in green
        - Filter to show only departments with variance greater than 5%
        
        For the KPI metrics:
        - Highlight metrics that missed target by more than 10% in red
        - Highlight metrics that exceeded target by more than 5% in green
        """
        
        dashboard_context = ConditionalFormattingExamples.get_financial_dashboard_context()
        
        additional_context = {
            "variance_thresholds": {
                "significant_over": 5,
                "significant_under": -5,
                "target_miss_threshold": 10,
                "target_exceed_threshold": 5
            }
        }
        
        result = await self.service.process_conditional_formatting_request(
            query=query,
            dashboard_context=dashboard_context,
            project_id="test_financial_variance",
            additional_context=additional_context
        )
        
        return result
    
    async def test_categorical_filtering(self) -> Dict[str, Any]:
        """Test categorical filtering and formatting"""
        query = """
        Filter the dashboard to show only 'North America' and 'Europe' regions.
        Highlight 'Premium' customer types in gold color.
        Show only 'Electronics' and 'Software' product categories.
        """
        
        dashboard_context = ConditionalFormattingExamples.get_sales_dashboard_context()
        
        additional_context = {
            "region_filter": ["North America", "Europe"],
            "product_categories": ["Electronics", "Software"],
            "highlight_customer_types": ["Premium"]
        }
        
        result = await self.service.process_conditional_formatting_request(
            query=query,
            dashboard_context=dashboard_context,
            project_id="test_categorical_filtering",
            additional_context=additional_context
        )
        
        return result
    
    async def test_complex_multi_condition(self) -> Dict[str, Any]:
        """Test complex multi-condition formatting"""
        query = """
        Create a comprehensive dashboard view with these conditions:
        
        1. Time Filter: Show data from Q4 2024 only
        
        2. Sales Performance:
           - Highlight sales > $200K in dark green with bold font
           - Highlight sales between $100K-200K in light green
           - Highlight sales < $50K in red with italic font
        
        3. Regional Analysis:
           - Filter to show top 5 performing regions only
           - Highlight regions with growth > 25% in blue
        
        4. Product Categories:
           - Show only categories with > 1000 units sold
           - Highlight top 3 categories by revenue in gold
        
        5. Sales Rep Performance:
           - Filter to show only reps with achievement rate > 70%
           - Highlight top 10% performers in green
           - Highlight bottom 20% performers in orange
        """
        
        dashboard_context = ConditionalFormattingExamples.get_sales_dashboard_context()
        
        additional_context = {
            "analysis_period": "Q4_2024",
            "performance_criteria": {
                "top_regions_count": 5,
                "min_units_threshold": 1000,
                "top_categories_count": 3,
                "min_achievement_rate": 70,
                "top_performers_percentile": 10,
                "bottom_performers_percentile": 20
            },
            "formatting_preferences": {
                "high_performance_color": "dark_green",
                "medium_performance_color": "light_green", 
                "low_performance_color": "red",
                "special_highlight_color": "gold",
                "warning_color": "orange"
            }
        }
        
        time_filters = {
            "start_date": "2024-10-01",
            "end_date": "2024-12-31",
            "period": "Q4_2024"
        }
        
        result = await self.service.process_conditional_formatting_request(
            query=query,
            dashboard_context=dashboard_context,
            project_id="test_complex_conditions",
            additional_context=additional_context,
            time_filters=time_filters
        )
        
        return result

class ConditionalFormattingBenchmarks:
    """Benchmarking and performance testing for conditional formatting"""
    
    def __init__(self):
        self.service = create_conditional_formatting_service()
        self.test_cases = ConditionalFormattingTestCases()
    
    async def run_all_test_cases(self) -> Dict[str, Any]:
        """Run all test cases and collect results"""
        test_methods = [
            ("basic_highlighting", self.test_cases.test_basic_highlighting),
            ("time_based_filtering", self.test_cases.test_time_based_filtering),
            ("performance_thresholds", self.test_cases.test_performance_thresholds),
            ("financial_variance", self.test_cases.test_financial_variance_analysis),
            ("categorical_filtering", self.test_cases.test_categorical_filtering),
            ("complex_multi_condition", self.test_cases.test_complex_multi_condition)
        ]
        
        results = {}
        overall_start_time = datetime.now()
        
        for test_name, test_method in test_methods:
            print(f"Running test: {test_name}")
            start_time = datetime.now()
            
            try:
                result = await test_method()
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                results[test_name] = {
                    "success": result.get("success", False),
                    "execution_time": execution_time,
                    "configuration": result.get("configuration"),
                    "chart_configurations": result.get("chart_configurations"),
                    "metadata": result.get("metadata"),
                    "error": result.get("error")
                }
                
                print(f"✓ {test_name} completed in {execution_time:.2f}s")
                
            except Exception as e:
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                results[test_name] = {
                    "success": False,
                    "execution_time": execution_time,
                    "error": str(e)
                }
                
                print(f"✗ {test_name} failed in {execution_time:.2f}s: {e}")
        
        overall_end_time = datetime.now()
        total_execution_time = (overall_end_time - overall_start_time).total_seconds()
        
        # Calculate summary statistics
        successful_tests = sum(1 for r in results.values() if r["success"])
        total_tests = len(results)
        avg_execution_time = sum(r["execution_time"] for r in results.values()) / total_tests
        
        summary = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": total_tests - successful_tests,
            "success_rate": successful_tests / total_tests * 100,
            "total_execution_time": total_execution_time,
            "average_execution_time": avg_execution_time,
            "timestamp": overall_end_time.isoformat()
        }
        
        return {
            "summary": summary,
            "test_results": results
        }
    
    def generate_performance_report(self, benchmark_results: Dict[str, Any]) -> str:
        """Generate a performance report from benchmark results"""
        summary = benchmark_results["summary"]
        test_results = benchmark_results["test_results"]
        
        report = f"""
# Conditional Formatting Performance Report

## Summary
- **Total Tests**: {summary['total_tests']}
- **Successful Tests**: {summary['successful_tests']}
- **Failed Tests**: {summary['failed_tests']}
- **Success Rate**: {summary['success_rate']:.1f}%
- **Total Execution Time**: {summary['total_execution_time']:.2f} seconds
- **Average Execution Time**: {summary['average_execution_time']:.2f} seconds
- **Generated**: {summary['timestamp']}

## Test Results

"""
        
        for test_name, result in test_results.items():
            status = "✓ PASS" if result["success"] else "✗ FAIL"
            report += f"### {test_name.replace('_', ' ').title()}\n"
            report += f"- **Status**: {status}\n"
            report += f"- **Execution Time**: {result['execution_time']:.2f} seconds\n"
            
            if result["success"]:
                config = result.get("configuration", {})
                chart_configs = result.get("chart_configurations", {})
                report += f"- **Filters Generated**: {len(config.get('filters', []))}\n"
                report += f"- **Conditional Formats**: {len(config.get('conditional_formats', []))}\n"
                report += f"- **Charts Configured**: {len(chart_configs)}\n"
            else:
                report += f"- **Error**: {result.get('error', 'Unknown error')}\n"
            
            report += "\n"
        
        return report

# Example usage and testing
async def main():
    """Main function to run examples and tests"""
    print("Starting Conditional Formatting Examples and Tests")
    print("=" * 60)
    
    # Initialize benchmarks
    benchmarks = ConditionalFormattingBenchmarks()
    
    # Run all test cases
    print("Running benchmark tests...")
    benchmark_results = await benchmarks.run_all_test_cases()
    
    # Generate performance report
    report = benchmarks.generate_performance_report(benchmark_results)
    print(report)
    
    # Save detailed results
    with open("conditional_formatting_test_results.json", "w") as f:
        json.dump(benchmark_results, f, indent=2, default=str)
    
    print("Detailed results saved to conditional_formatting_test_results.json")
    
    # Example of individual test case
    print("\n" + "=" * 60)
    print("Running Individual Test Case Example")
    
    test_cases = ConditionalFormattingTestCases()
    
    # Run basic highlighting test
    result = await test_cases.test_basic_highlighting()
    
    print("\nBasic Highlighting Test Result:")
    print(json.dumps(result, indent=2, default=str))
    
    return benchmark_results

if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())