"""
Practical example of using the Advanced SQL Relevance Scoring System
This example demonstrates real-world usage patterns and configurations
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Sample configuration for SQL relevance scoring
SAMPLE_SCORING_CONFIG = {
    "reasoning_weight": 0.65,
    "sql_quality_weight": 0.35,
    "terminology_value": 0.025,
    "schema_relevance_weight": 0.3,
    "query_correctness_weight": 0.4,
    "reasoning_depth_weight": 0.3,
    
    "length_score_thresholds": {
        "comprehensive": {"threshold": 120, "score": 0.30},
        "detailed": {"threshold": 80, "score": 0.25},
        "adequate": {"threshold": 40, "score": 0.20},
        "minimal": {"threshold": 15, "score": 0.15},
        "insufficient": {"score": 0.08}
    },
    
    "sql_operations": {
        "basic_sql": {
            "terms": ["select", "from", "where", "group by", "order by", "having",
                     "insert", "update", "delete", "create", "alter", "drop", "distinct"],
            "max_score": 0.18,
            "min_match_threshold": 2
        },
        "advanced_sql": {
            "terms": ["join", "inner join", "left join", "right join", "full join",
                     "union", "union all", "intersect", "except", "cte", "with",
                     "window function", "partition by", "row_number", "rank", "dense_rank",
                     "lead", "lag", "first_value", "last_value", "over"],
            "max_score": 0.28,
            "min_match_threshold": 1
        },
        "sql_functions": {
            "terms": ["count", "sum", "avg", "min", "max", "concat", "substring", "length",
                     "upper", "lower", "trim", "coalesce", "case when", "cast", "convert",
                     "date", "datetime", "timestamp", "extract", "datepart", "datediff"],
            "max_score": 0.22,
            "min_match_threshold": 2
        }
    }
}


class SQLScoringSystemDemo:
    """
    Comprehensive demonstration of the SQL relevance scoring system
    """
    
    def __init__(self):
        self.config_path = self._setup_config()
        self.test_scenarios = self._load_test_scenarios()
        self.schema_context = self._setup_schema_context()
    
    def _setup_config(self) -> str:
        """Set up configuration file"""
        config_path = "sql_scoring_config.json"
        
        with open(config_path, 'w') as f:
            json.dump(SAMPLE_SCORING_CONFIG, f, indent=2)
        
        logger.info(f"Configuration saved to {config_path}")
        return config_path
    
    def _setup_schema_context(self) -> Dict[str, Any]:
        """Set up realistic database schema context"""
        return {
            "schema": {
                "customers": [
                    "customer_id", "first_name", "last_name", "email", 
                    "phone", "address", "city", "state", "zip_code",
                    "registration_date", "last_login", "is_active"
                ],
                "orders": [
                    "order_id", "customer_id", "order_date", "ship_date",
                    "total_amount", "tax_amount", "shipping_cost", "status",
                    "payment_method", "shipping_address", "notes"
                ],
                "order_items": [
                    "order_item_id", "order_id", "product_id", "quantity",
                    "unit_price", "discount", "line_total"
                ],
                "products": [
                    "product_id", "product_name", "category", "subcategory",
                    "brand", "price", "cost", "stock_quantity", "reorder_level",
                    "supplier_id", "is_active", "created_date", "updated_date"
                ],
                "suppliers": [
                    "supplier_id", "company_name", "contact_name", "email",
                    "phone", "address", "city", "state", "zip_code", "country"
                ],
                "categories": [
                    "category_id", "category_name", "parent_category_id", "description"
                ]
            },
            "relationships": {
                "customers_orders": "customers.customer_id = orders.customer_id",
                "orders_order_items": "orders.order_id = order_items.order_id",
                "products_order_items": "products.product_id = order_items.product_id",
                "suppliers_products": "suppliers.supplier_id = products.supplier_id",
                "categories_products": "categories.category_id = products.category"
            }
        }
    
    def _load_test_scenarios(self) -> List[Dict[str, Any]]:
        """Load comprehensive test scenarios"""
        return [
            {
                "name": "Excellent Quality Example",
                "query": "Find the top 10 customers by total purchase amount in the last 6 months, including their contact information",
                "model_output": """
                ### REASONING ###
                To find the top 10 customers by total purchase amount in the last 6 months with their contact information, I need to:
                
                1. **Identify relevant tables**: I need customers table for contact information and orders table for purchase amounts
                2. **Establish table relationships**: Join customers and orders tables using customer_id as the foreign key
                3. **Apply time filter**: Filter orders to only include those from the last 6 months using order_date >= CURRENT_DATE - INTERVAL '6 months'
                4. **Calculate total purchases**: Use SUM(total_amount) to calculate total purchase amount per customer
                5. **Group and aggregate**: Group by customer to get total per customer
                6. **Sort and limit**: Order by total purchase amount in descending order and limit to top 10
                7. **Include contact information**: Select customer details like name, email, phone for the result
                
                The query will use INNER JOIN to ensure we only get customers who have made orders, GROUP BY to aggregate by customer, and proper date filtering for the 6-month window.
                
                ### SQL ###
                SELECT 
                    c.customer_id,
                    c.first_name,
                    c.last_name,
                    c.email,
                    c.phone,
                    SUM(o.total_amount) as total_purchase_amount,
                    COUNT(o.order_id) as total_orders
                FROM customers c
                INNER JOIN orders o ON c.customer_id = o.customer_id
                WHERE o.order_date >= CURRENT_DATE - INTERVAL '6 months'
                    AND o.status != 'CANCELLED'
                GROUP BY c.customer_id, c.first_name, c.last_name, c.email, c.phone
                ORDER BY total_purchase_amount DESC
                LIMIT 10;
                """,
                "expected_score_range": (0.80, 1.0),
                "expected_quality": "excellent"
            },
            
            {
                "name": "Good Quality Example",
                "query": "Show monthly sales trends for the current year",
                "model_output": """
                ### REASONING ###
                To show monthly sales trends for the current year, I need to:
                1. Use the orders table to get sales data
                2. Filter for current year orders
                3. Group by month to get monthly aggregates
                4. Calculate total sales per month
                
                ### SQL ###
                SELECT 
                    EXTRACT(MONTH FROM order_date) as month,
                    SUM(total_amount) as monthly_sales
                FROM orders
                WHERE EXTRACT(YEAR FROM order_date) = EXTRACT(YEAR FROM CURRENT_DATE)
                GROUP BY EXTRACT(MONTH FROM order_date)
                ORDER BY month;
                """,
                "expected_score_range": (0.60, 0.79),
                "expected_quality": "good"
            },
            
            {
                "name": "Fair Quality Example", 
                "query": "List all products with low stock",
                "model_output": """
                Need to find products with low stock.
                
                SELECT product_name, stock_quantity
                FROM products
                WHERE stock_quantity < reorder_level;
                """,
                "expected_score_range": (0.40, 0.59),
                "expected_quality": "fair"
            },
            
            {
                "name": "Poor Quality Example",
                "query": "Get customer order information",
                "model_output": """
                SELECT * FROM customers, orders;
                """,
                "expected_score_range": (0.0, 0.39),
                "expected_quality": "poor"
            },
            
            {
                "name": "Complex Query Example",
                "query": "Create a comprehensive sales report with customer segments, product performance, and trend analysis",
                "model_output": """
                ### REASONING ###
                This is a complex analytical query that requires multiple components:
                
                1. **Customer Segmentation**: Classify customers based on purchase behavior (frequency and monetary value)
                2. **Product Performance Analysis**: Analyze product sales, margins, and trends
                3. **Time-based Trend Analysis**: Show sales trends over time periods
                4. **Cross-dimensional Analysis**: Combine customer segments with product categories
                
                I'll use Common Table Expressions (CTEs) to break this into logical steps:
                - First CTE: Calculate customer metrics (RFM analysis)
                - Second CTE: Calculate product performance metrics
                - Third CTE: Calculate time-based trends
                - Final query: Combine all dimensions for comprehensive reporting
                
                This approach ensures data accuracy and query maintainability while providing comprehensive insights.
                
                ### SQL ###
                WITH customer_segments AS (
                    SELECT 
                        c.customer_id,
                        c.first_name || ' ' || c.last_name as customer_name,
                        COUNT(o.order_id) as order_frequency,
                        SUM(o.total_amount) as total_spent,
                        MAX(o.order_date) as last_order_date,
                        CASE 
                            WHEN SUM(o.total_amount) > 5000 AND COUNT(o.order_id) > 10 THEN 'VIP'
                            WHEN SUM(o.total_amount) > 2000 AND COUNT(o.order_id) > 5 THEN 'Regular'
                            WHEN SUM(o.total_amount) > 500 THEN 'Occasional'
                            ELSE 'New'
                        END as customer_segment
                    FROM customers c
                    LEFT JOIN orders o ON c.customer_id = o.customer_id
                    WHERE o.order_date >= CURRENT_DATE - INTERVAL '1 year'
                    GROUP BY c.customer_id, c.first_name, c.last_name
                ),
                product_performance AS (
                    SELECT 
                        p.product_id,
                        p.product_name,
                        p.category,
                        SUM(oi.quantity) as total_sold,
                        SUM(oi.line_total) as total_revenue,
                        AVG(oi.unit_price) as avg_selling_price,
                        SUM(oi.line_total - (oi.quantity * p.cost)) as total_profit
                    FROM products p
                    INNER JOIN order_items oi ON p.product_id = oi.product_id
                    INNER JOIN orders o ON oi.order_id = o.order_id
                    WHERE o.order_date >= CURRENT_DATE - INTERVAL '1 year'
                    GROUP BY p.product_id, p.product_name, p.category
                )
                SELECT 
                    cs.customer_segment,
                    pp.category,
                    COUNT(DISTINCT cs.customer_id) as customer_count,
                    SUM(pp.total_revenue) as segment_category_revenue,
                    AVG(pp.total_profit) as avg_profit_per_product,
                    SUM(pp.total_sold) as total_units_sold
                FROM customer_segments cs
                INNER JOIN orders o ON cs.customer_id = o.customer_id
                INNER JOIN order_items oi ON o.order_id = oi.order_id
                INNER JOIN product_performance pp ON oi.product_id = pp.product_id
                GROUP BY cs.customer_segment, pp.category
                ORDER BY segment_category_revenue DESC;
                """,
                "expected_score_range": (0.85, 1.0),
                "expected_quality": "excellent"
            }
        ]
    
    async def run_comprehensive_evaluation(self):
        """Run comprehensive evaluation of all test scenarios"""
        # Import the scoring system (in real implementation)
        from sql_relevance_scorer import SQLAdvancedRelevanceScorer
        
        # Initialize scorer with configuration
        scorer = SQLAdvancedRelevanceScorer(
            config_file_path=self.config_path,
            schema_context=self.schema_context
        )
        
        print("=" * 80)
        print("SQL RELEVANCE SCORING SYSTEM - COMPREHENSIVE EVALUATION")
        print("=" * 80)
        
        results = []
        
        for i, scenario in enumerate(self.test_scenarios, 1):
            print(f"\n--- Test Scenario {i}: {scenario['name']} ---")
            print(f"Query: {scenario['query']}")
            print()
            
            # Score the scenario
            scoring_result = scorer.score_sql_reasoning(
                scenario['model_output'],
                scenario['query'],
                self.schema_context
            )
            
            # Extract key metrics
            final_score = scoring_result['final_relevance_score']
            quality_level = scoring_result['quality_level']
            
            # Display results
            print(f"Final Relevance Score: {final_score:.3f}")
            print(f"Quality Level: {quality_level.upper()}")
            
            # Check if score is within expected range
            expected_min, expected_max = scenario['expected_score_range']
            score_in_range = expected_min <= final_score <= expected_max
            quality_matches = quality_level == scenario['expected_quality']
            
            print(f"Expected Score Range: {expected_min:.2f} - {expected_max:.2f}")
            print(f"Score in Expected Range: {'✓' if score_in_range else '✗'}")
            print(f"Quality Level Match: {'✓' if quality_matches else '✗'}")
            
            # Show component breakdown
            print("\nScore Breakdown:")
            for component, score in scoring_result['reasoning_components'].items():
                print(f"  {component}: {score:.3f}")
            
            # Show improvement recommendations if score is low
            if final_score < 0.7:
                recommendations = scorer.get_improvement_recommendations(scoring_result)
                print(f"\nImprovement Recommendations:")
                for j, rec in enumerate(recommendations, 1):
                    print(f"  {j}. {rec}")
            
            # Store results for summary
            results.append({
                'scenario_name': scenario['name'],
                'final_score': final_score,
                'quality_level': quality_level,
                'expected_quality': scenario['expected_quality'],
                'score_in_range': score_in_range,
                'quality_matches': quality_matches
            })
            
            print("-" * 60)
        
        # Summary
        self._print_evaluation_summary(results)
        return results
    
    def _print_evaluation_summary(self, results: List[Dict]):
        """Print evaluation summary statistics"""
        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)
        
        total_scenarios = len(results)
        scores_in_range = sum(1 for r in results if r['score_in_range'])
        qualities_match = sum(1 for r in results if r['quality_matches'])
        
        avg_score = sum(r['final_score'] for r in results) / total_scenarios
        
        print(f"Total Scenarios Evaluated: {total_scenarios}")
        print(f"Average Score: {avg_score:.3f}")
        print(f"Scores in Expected Range: {scores_in_range}/{total_scenarios} ({scores_in_range/total_scenarios*100:.1f}%)")
        print(f"Quality Levels Match: {qualities_match}/{total_scenarios} ({qualities_match/total_scenarios*100:.1f}%)")
        
        # Quality distribution
        quality_dist = {}
        for result in results:
            quality = result['quality_level']
            quality_dist[quality] = quality_dist.get(quality, 0) + 1
        
        print(f"\nQuality Distribution:")
        for quality, count in sorted(quality_dist.items()):
            print(f"  {quality.upper()}: {count} scenarios")
        
        print("\nDetailed Results:")
        for result in results:
            status = "✓" if result['score_in_range'] and result['quality_matches'] else "✗"
            print(f"  {status} {result['scenario_name']}: {result['final_score']:.3f} ({result['quality_level']})")
    
    async def demonstrate_correction_scoring(self):
        """Demonstrate SQL correction quality scoring"""
        from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
        
        scorer = SQLAdvancedRelevanceScorer(
            config_file_path=self.config_path,
            schema_context=self.schema_context
        )
        
        print("\n" + "=" * 80)
        print("SQL CORRECTION QUALITY SCORING DEMONSTRATION")
        print("=" * 80)
        
        correction_scenarios = [
            {
                "name": "Table Name Correction",
                "original_sql": "SELECT * FROM customer WHERE customer_id = 1",
                "corrected_sql": "SELECT * FROM customers WHERE customer_id = 1",
                "error_message": "Table 'customer' doesn't exist",
                "reasoning": "The error indicates that table 'customer' doesn't exist. Checking the database schema, I can see the correct table name is 'customers' (plural). The table name should be corrected while maintaining the same query structure and logic."
            },
            {
                "name": "Column Reference Correction",
                "original_sql": "SELECT name, total FROM orders JOIN customers ON orders.cust_id = customers.id",
                "corrected_sql": "SELECT CONCAT(c.first_name, ' ', c.last_name) as name, o.total_amount FROM orders o JOIN customers c ON o.customer_id = c.customer_id",
                "error_message": "Column 'name' not found, column 'total' not found, column 'cust_id' not found",
                "reasoning": "Multiple column reference errors need to be fixed: 1) 'name' column doesn't exist - need to concatenate first_name and last_name, 2) 'total' should be 'total_amount', 3) 'cust_id' should be 'customer_id', and 4) 'id' should be 'customer_id'. Added table aliases for clarity."
            }
        ]
        
        for i, scenario in enumerate(correction_scenarios, 1):
            print(f"\n--- Correction Scenario {i}: {scenario['name']} ---")
            
            correction_score = scorer.score_sql_correction_quality(
                scenario['original_sql'],
                scenario['corrected_sql'],
                scenario['error_message'],
                scenario['reasoning']
            )
            
            print(f"Original SQL: {scenario['original_sql']}")
            print(f"Error: {scenario['error_message']}")
            print(f"Corrected SQL: {scenario['corrected_sql']}")
            print(f"\nCorrection Quality Score: {correction_score['total_correction_score']:.3f}")
            print(f"Improvement Score: {correction_score['improvement_score']:.3f}")
            print(f"Error Addressed Score: {correction_score['error_addressed_score']:.3f}")
            
            print("\nScore Breakdown:")
            for component, score in correction_score.items():
                if component.endswith('_score'):
                    print(f"  {component}: {score:.3f}")
    
async def demonstrate_enhanced_agent_integration():
    """Demonstrate the EnhancedSQLRAGAgent integration"""
    
    print("\n" + "=" * 80)
    print("ENHANCED SQL RAG AGENT INTEGRATION DEMONSTRATION")
    print("=" * 80)
    
    # Import the enhanced agent
    from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
    from genieml.agents.app.agents.nodes.sql.scoring_sql_rag_agent import EnhancedSQLRAGAgent
    
    # Mock base agent for demonstration
    class MockSQLRAGAgent:
        class SQLOperationType:
            GENERATION = "generation"
            CORRECTION = "correction"
            BREAKDOWN = "breakdown"
            ANSWER = "answer"
        
        async def process_sql_request(self, operation_type, query, **kwargs):
            # Mock SQL generation based on query
            if "customers" in query.lower() and "orders" in query.lower():
                return {
                    "success": True,
                    "sql": """
                    SELECT c.customer_id, c.first_name, c.last_name, c.email,
                           SUM(o.total_amount) as total_spent
                    FROM customers c
                    INNER JOIN orders o ON c.customer_id = o.customer_id
                    WHERE o.order_date >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY c.customer_id, c.first_name, c.last_name, c.email
                    ORDER BY total_spent DESC
                    LIMIT 10;
                    """,
                    "reasoning": """
                    To find customers who made orders in the last 30 days with their spending:
                    1. Join customers and orders tables on customer_id
                    2. Filter orders for last 30 days using date comparison
                    3. Group by customer information to aggregate spending
                    4. Sum total_amount to get total spending per customer
                    5. Order by spending amount in descending order
                    6. Limit to top 10 customers
                    """
                }
            else:
                return {
                    "success": True,
                    "sql": f"SELECT * FROM table WHERE condition;",
                    "reasoning": f"Simple query for: {query}"
                }
    
    # Create enhanced agent
    base_agent = MockSQLRAGAgent()
    enhanced_agent = EnhancedSQLRAGAgent(
        base_agent=base_agent,
        relevance_scorer=SQLAdvancedRelevanceScorer()
    )
    
    # Set up schema context
    schema_context = {
        "schema": {
            "customers": ["customer_id", "first_name", "last_name", "email", "signup_date"],
            "orders": ["order_id", "customer_id", "order_date", "total_amount", "status"]
        }
    }
    
    enhanced_agent.update_schema_context(schema_context)
    
    # Test SQL generation with scoring
    test_query = "Find the top 10 customers by spending in the last 30 days"
    
    print(f"Test Query: {test_query}")
    print("-" * 60)
    
    result = await enhanced_agent.generate_sql_with_scoring(
        test_query,
        schema_context=schema_context,
        max_improvement_attempts=2
    )
    
    print(f"Generated SQL:")
    print(result['sql'])
    print(f"\nQuality Score: {result['final_score']:.3f}")
    print(f"Quality Level: {result['quality_level'].upper()}")
    print(f"Attempts Made: {result.get('attempt_number', 1)}")
    
    # Show improvement recommendations
    if result.get('improvement_recommendations'):
        print(f"\nImprovement Recommendations:")
        for i, rec in enumerate(result['improvement_recommendations'], 1):
            print(f"  {i}. {rec}")
    
    # Test another query with scoring
    simple_query = "Get all customers"
    print(f"\n" + "=" * 60)
    print(f"Simple Query Test: {simple_query}")
    print("-" * 60)
    
    simple_result = await enhanced_agent.generate_sql_with_scoring(
        simple_query,
        schema_context=schema_context
    )
    
    print(f"Generated SQL: {simple_result['sql']}")
    print(f"Quality Score: {simple_result['final_score']:.3f}")
    print(f"Quality Level: {simple_result['quality_level'].upper()}")
    
    # Show performance analytics
    print(f"\n" + "=" * 60)
    print("PERFORMANCE ANALYTICS")
    print("=" * 60)
    
    analytics = enhanced_agent.get_performance_analytics()
    print(f"Total Queries Processed: {analytics['total_queries']}")
    print(f"Average Score: {analytics['average_score']:.3f}")
    
    if analytics['total_queries'] > 0:
        print(f"Quality Distribution:")
        for quality, count in analytics['quality_distribution'].items():
            print(f"  {quality.upper()}: {count}")
        
        print(f"Success Rate: {analytics['success_rates']['overall_success_rate']:.1%}")
    
    # Show quality insights
    insights = enhanced_agent.get_quality_insights()
    if insights.get('insights'):
        print(f"\nQuality Insights:")
        for insight in insights['insights']:
            print(f"  • {insight}")
    
    if insights.get('recommendations'):
        print(f"\nSystem Recommendations:")
        for rec in insights['recommendations']:
            print(f"  • {rec}")
    
    return enhanced_agent
    
    def cleanup(self):
        """Clean up configuration files"""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
            logger.info(f"Cleaned up configuration file: {self.config_path}")


async def run_performance_benchmark():
    """Run performance benchmark to test scoring system efficiency"""
    print("\n" + "=" * 80)
    print("PERFORMANCE BENCHMARK")
    print("=" * 80)
    
    from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
    import time
    
    # Create test cases of varying complexity
    test_cases = []
    
    # Simple queries
    for i in range(50):
        test_cases.append({
            "query": f"SELECT * FROM customers WHERE customer_id = {i}",
            "model_output": f"Simple query to get customer {i}.\n\nSELECT * FROM customers WHERE customer_id = {i};"
        })
    
    # Complex queries
    for i in range(20):
        test_cases.append({
            "query": f"Complex analysis query {i}",
            "model_output": f"""
            ### REASONING ###
            This is a complex analytical query requiring multiple steps:
            1. Join multiple tables for comprehensive data
            2. Apply appropriate filters and conditions
            3. Use window functions for advanced analytics
            4. Group and aggregate data properly
            5. Order results for meaningful presentation
            
            ### SQL ###
            WITH sales_data AS (
                SELECT c.customer_id, c.first_name, c.last_name,
                       o.order_date, o.total_amount,
                       ROW_NUMBER() OVER (PARTITION BY c.customer_id ORDER BY o.order_date DESC) as rn
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                WHERE o.order_date >= CURRENT_DATE - INTERVAL '1 year'
            )
            SELECT customer_id, first_name, last_name, total_amount
            FROM sales_data
            WHERE rn = 1
            ORDER BY total_amount DESC;
            """
        })
    
    # Initialize scorer
    scorer = SQLAdvancedRelevanceScorer()
    
    print(f"Testing {len(test_cases)} queries...")
    
    start_time = time.time()
    scores = []
    
    for i, test_case in enumerate(test_cases):
        if i % 20 == 0:
            print(f"Processed {i}/{len(test_cases)} queries...")
        
        result = scorer.score_sql_reasoning(
            test_case['model_output'],
            test_case['query']
        )
        scores.append(result['final_relevance_score'])
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\nPerformance Results:")
    print(f"Total Time: {total_time:.2f} seconds")
    print(f"Average Time per Query: {total_time/len(test_cases)*1000:.1f} ms")
    print(f"Queries per Second: {len(test_cases)/total_time:.1f}")
    print(f"Average Score: {sum(scores)/len(scores):.3f}")
    print(f"Score Range: {min(scores):.3f} - {max(scores):.3f}")


async def main():
    """Main demonstration function"""
    print("Advanced SQL Relevance Scoring System")
    print("Based on GRPO methodology for SQL reasoning evaluation")
    print("=" * 80)
    
    # Initialize demo
    demo = SQLScoringSystemDemo()
    
    try:
        # Run comprehensive evaluation
        await demo.run_comprehensive_evaluation()
        
        # Demonstrate correction scoring
        await demo.demonstrate_correction_scoring()
        
        # Demonstrate enhanced agent integration
        await demonstrate_enhanced_agent_integration()
        
        # Run performance benchmark
        await run_performance_benchmark()
        
        print("\n" + "=" * 80)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"Error during demonstration: {e}")
        raise
    finally:
        # Cleanup
        demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())