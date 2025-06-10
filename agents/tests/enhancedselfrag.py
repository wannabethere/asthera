"""
Complete usage example of the EnhancedSQLRAGAgent
This shows how to integrate the advanced relevance scoring system with your existing SQL RAG agent
"""

import asyncio
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example of how to use the EnhancedSQLRAGAgent
async def complete_enhanced_agent_example():
    """
    Complete example showing how to use EnhancedSQLRAGAgent with your existing SQL RAG system
    """
    
    print("=" * 80)
    print("ENHANCED SQL RAG AGENT - COMPLETE USAGE EXAMPLE")
    print("=" * 80)
    
    # Step 1: Import the required classes
    # In your actual implementation, you would import from your modules:
    # from sql_rag_agent import SQLRAGAgent
    # from sql_relevance_scorer import SQLAdvancedRelevanceScorer, EnhancedSQLRAGAgent
    
    # For this example, we'll create mock versions
    class MockSQLRAGAgent:
        """Mock version of your existing SQL RAG Agent"""
        
        class SQLOperationType:
            GENERATION = "generation"
            CORRECTION = "correction"
            BREAKDOWN = "breakdown"
            ANSWER = "answer"
        
        def __init__(self, llm, engine, **kwargs):
            self.llm = llm
            self.engine = engine
        
        async def process_sql_request(self, operation_type, query, **kwargs):
            """Mock SQL processing - replace with your actual implementation"""
            
            if operation_type == self.SQLOperationType.GENERATION:
                return await self._mock_generate_sql(query, **kwargs)
            elif operation_type == self.SQLOperationType.CORRECTION:
                return await self._mock_correct_sql(kwargs.get('sql', ''), kwargs.get('error_message', ''))
            elif operation_type == self.SQLOperationType.BREAKDOWN:
                return await self._mock_breakdown_sql(query, kwargs.get('sql', ''))
            elif operation_type == self.SQLOperationType.ANSWER:
                return await self._mock_answer_sql(query, kwargs.get('sql', ''), kwargs.get('sql_data', {}))
            
            return {"success": False, "error": "Unknown operation type"}
        
        async def _mock_generate_sql(self, query: str, **kwargs) -> Dict[str, Any]:
            """Mock SQL generation - replace with your actual generation logic"""
            
            # Simple pattern matching for demo
            if "customers" in query.lower() and "orders" in query.lower():
                return {
                    "success": True,
                    "sql": """SELECT c.customer_id, c.first_name, c.last_name, c.email,
                           SUM(o.total_amount) as total_purchase_amount,
                           COUNT(o.order_id) as total_orders
                    FROM customers c
                    INNER JOIN orders o ON c.customer_id = o.customer_id  
                    WHERE o.order_date >= CURRENT_DATE - INTERVAL '6 months'
                        AND o.status != 'CANCELLED'
                    GROUP BY c.customer_id, c.first_name, c.last_name, c.email
                    ORDER BY total_purchase_amount DESC
                    LIMIT 10;""",
                    "reasoning": """To find the top customers by purchase amount, I need to:
                    
1. **Identify relevant tables**: customers table for customer info, orders table for purchase data
2. **Join tables**: Use INNER JOIN on customer_id to connect customer and order information  
3. **Apply filters**: Filter out cancelled orders and limit to last 6 months
4. **Aggregate data**: Group by customer and sum total_amount to get total purchases
5. **Sort and limit**: Order by total purchase amount descending, limit to top 10
6. **Include additional metrics**: Also count number of orders per customer for context
                    
The query uses proper table aliases and includes necessary filters for data quality.""",
                    "correlation_id": "demo_001"
                }
            
            elif "revenue" in query.lower() and "month" in query.lower():
                return {
                    "success": True,
                    "sql": """SELECT 
                        EXTRACT(YEAR FROM order_date) as year,
                        EXTRACT(MONTH FROM order_date) as month,
                        SUM(total_amount) as monthly_revenue,
                        COUNT(order_id) as total_orders,
                        AVG(total_amount) as avg_order_value
                    FROM orders
                    WHERE order_date >= CURRENT_DATE - INTERVAL '1 year'
                        AND status = 'COMPLETED'
                    GROUP BY EXTRACT(YEAR FROM order_date), EXTRACT(MONTH FROM order_date)
                    ORDER BY year DESC, month DESC;""",
                    "reasoning": """For monthly revenue analysis, I need to:
                    
1. **Extract time components**: Use EXTRACT functions to get year and month from order_date
2. **Filter recent data**: Only include orders from the last year  
3. **Filter valid orders**: Only include completed orders for accurate revenue calculation
4. **Group by time period**: Group by year and month to get monthly aggregates
5. **Calculate metrics**: Sum revenue, count orders, calculate average order value
6. **Order results**: Sort by year and month in descending order for most recent first""",
                    "correlation_id": "demo_002"
                }
            
            else:
                return {
                    "success": True,  
                    "sql": f"SELECT * FROM table WHERE condition;",
                    "reasoning": f"Basic query analysis for: {query}. This is a simple SELECT statement.",
                    "correlation_id": "demo_basic"
                }
        
        async def _mock_correct_sql(self, sql: str, error_message: str) -> Dict[str, Any]:
            """Mock SQL correction"""
            return {
                "success": True,
                "sql": sql.replace("customer", "customers"),  # Simple correction
                "reasoning": "Corrected table name from 'customer' to 'customers' based on schema."
            }
        
        async def _mock_breakdown_sql(self, query: str, sql: str) -> Dict[str, Any]:
            """Mock SQL breakdown"""
            return {
                "success": True,
                "breakdown": "Step-by-step breakdown of the SQL query...",
                "reasoning": "Breaking down the complex query into understandable steps."
            }
        
        async def _mock_answer_sql(self, query: str, sql: str, sql_data: Dict) -> Dict[str, Any]:
            """Mock SQL answer generation"""
            return {
                "success": True,
                "answer": "Based on the query results, here's what the data shows...",
                "reasoning": "Interpreting the SQL results to answer the user's question."
            }
    
    # Import the actual enhanced components (for demo, we'll define simplified versions)
    from sql_relevance_scorer import SQLAdvancedRelevanceScorer, EnhancedSQLRAGAgent
    
    # Step 2: Set up your existing components
    print("Step 1: Setting up base components...")
    
    # Your existing LLM and engine (mock for demo)
    class MockLLM:
        def __init__(self, model_name="gpt-4"):
            self.model_name = model_name
    
    class MockEngine:
        def __init__(self, database_url="your_db_url"):
            self.database_url = database_url
    
    llm = MockLLM()
    engine = MockEngine()
    
    # Step 3: Create your base SQL RAG agent
    print("Step 2: Creating base SQL RAG agent...")
    base_sql_agent = MockSQLRAGAgent(llm=llm, engine=engine)
    
    # Step 4: Set up schema context for scoring
    print("Step 3: Setting up database schema context...")
    schema_context = {
        "schema": {
            "customers": [
                "customer_id", "first_name", "last_name", "email", "phone",
                "address", "city", "state", "zip_code", "registration_date", 
                "last_login", "is_active"
            ],
            "orders": [
                "order_id", "customer_id", "order_date", "ship_date", 
                "total_amount", "tax_amount", "shipping_cost", "status",
                "payment_method", "shipping_address"
            ],
            "order_items": [
                "order_item_id", "order_id", "product_id", "quantity",
                "unit_price", "discount", "line_total"
            ],
            "products": [
                "product_id", "product_name", "category", "subcategory",
                "brand", "price", "cost", "stock_quantity", "supplier_id",
                "is_active", "created_date"
            ]
        },
        "relationships": {
            "customers_orders": "customers.customer_id = orders.customer_id",
            "orders_order_items": "orders.order_id = order_items.order_id",
            "products_order_items": "products.product_id = order_items.product_id"
        }
    }
    
    # Step 5: Create the relevance scorer with custom configuration
    print("Step 4: Creating advanced relevance scorer...")
    relevance_scorer = SQLAdvancedRelevanceScorer(
        config_file_path=None,  # Use default config
        schema_context=schema_context
    )
    
    # Step 6: Create the enhanced SQL RAG agent
    print("Step 5: Creating EnhancedSQLRAGAgent...")
    enhanced_agent = EnhancedSQLRAGAgent(
        base_agent=base_sql_agent,
        relevance_scorer=relevance_scorer
    )
    
    print("✅ EnhancedSQLRAGAgent created successfully!")
    print()
    
    # Step 7: Test SQL generation with scoring
    print("=" * 60)
    print("TESTING SQL GENERATION WITH SCORING")
    print("=" * 60)
    
    test_queries = [
        "Find the top 10 customers by total purchase amount in the last 6 months",
        "Show monthly revenue trends for the current year",
        "List all customers"  # Simple query for comparison
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Test Query {i} ---")
        print(f"Query: {query}")
        
        # Generate SQL with scoring
        result = await enhanced_agent.generate_sql_with_scoring(
            query,
            schema_context=schema_context,
            max_improvement_attempts=2
        )
        
        print(f"\n✅ Success: {result['success']}")
        print(f"🎯 Quality Score: {result['final_score']:.3f}")
        print(f"📊 Quality Level: {result['quality_level'].upper()}")
        print(f"🔄 Attempts: {result.get('attempt_number', 1)}")
        
        # Show generated SQL (truncated for display)
        sql_preview = result['sql'].strip()[:200] + "..." if len(result['sql']) > 200 else result['sql'].strip()
        print(f"\n💻 Generated SQL:\n{sql_preview}")
        
        # Show improvement recommendations if available
        recommendations = result.get('improvement_recommendations', [])
        if recommendations:
            print(f"\n💡 Improvement Recommendations:")
            for j, rec in enumerate(recommendations[:3], 1):
                print(f"   {j}. {rec}")
        
        print("-" * 40)
    
    # Step 8: Test SQL correction with scoring
    print("\n" + "=" * 60)
    print("TESTING SQL CORRECTION WITH SCORING")
    print("=" * 60)
    
    # Test correction scenario
    faulty_sql = "SELECT * FROM customer WHERE id = 1"
    error_message = "Table 'customer' doesn't exist"
    
    print(f"Original SQL: {faulty_sql}")
    print(f"Error: {error_message}")
    
    correction_result = await enhanced_agent.correct_sql_with_scoring(
        sql=faulty_sql,
        error_message=error_message,
        schema_context=schema_context
    )
    
    print(f"\n✅ Correction Success: {correction_result['success']}")
    print(f"📈 Correction Quality: {correction_result['correction_quality']:.3f}")
    print(f"🔧 Corrected SQL: {correction_result['sql']}")
    
    # Step 9: Test other enhanced methods
    print("\n" + "=" * 60)
    print("TESTING OTHER ENHANCED METHODS")
    print("=" * 60)
    
    # Test breakdown with scoring
    complex_sql = """SELECT c.customer_id, c.first_name, c.last_name,
                     SUM(o.total_amount) as total_spent
                     FROM customers c JOIN orders o ON c.customer_id = o.customer_id
                     GROUP BY c.customer_id, c.first_name, c.last_name
                     ORDER BY total_spent DESC LIMIT 5"""
    
    breakdown_result = await enhanced_agent.breakdown_sql_with_scoring(
        query="Explain this complex query",
        sql=complex_sql,
        schema_context=schema_context
    )
    
    print(f"Breakdown Quality: {breakdown_result.get('explanation_quality', 'N/A')}")
    
    # Step 10: Get performance analytics
    print("\n" + "=" * 60)
    print("PERFORMANCE ANALYTICS")
    print("=" * 60)
    
    analytics = enhanced_agent.get_performance_analytics()
    
    print(f"📊 Total Queries Processed: {analytics['total_queries']}")
    print(f"📈 Average Quality Score: {analytics['average_score']:.3f}")
    print(f"🎯 High Quality Rate: {analytics['success_rates']['overall_success_rate']:.1%}")
    
    print(f"\n📋 Quality Distribution:")
    for quality, count in analytics['quality_distribution'].items():
        print(f"   {quality.upper()}: {count}")
    
    # Step 11: Get quality insights and recommendations
    print("\n" + "=" * 60)
    print("QUALITY INSIGHTS & RECOMMENDATIONS")
    print("=" * 60)
    
    insights = enhanced_agent.get_quality_insights()
    
    if insights.get('insights'):
        print("🔍 System Insights:")
        for insight in insights['insights']:
            print(f"   • {insight}")
    
    if insights.get('recommendations'):
        print("\n💡 System Recommendations:")
        for rec in insights['recommendations']:
            print(f"   • {rec}")
    
    # Step 12: Export scoring data (optional)
    print("\n" + "=" * 60)
    print("DATA EXPORT")
    print("=" * 60)
    
    export_file = enhanced_agent.export_scoring_data("enhanced_sql_agent_results.json")
    print(f"📁 Scoring data exported to: {export_file}")
    
    print("\n" + "=" * 80)
    print("✅ ENHANCED SQL RAG AGENT DEMONSTRATION COMPLETED!")
    print("=" * 80)
    
    return enhanced_agent


# Example of integrating with your existing codebase
def integrate_with_existing_system():
    """
    Example of how to integrate EnhancedSQLRAGAgent with your existing system
    """
    
    print("\n" + "=" * 80)
    print("INTEGRATION WITH EXISTING SYSTEM")
    print("=" * 80)
    
    # Your existing code structure might look like this:
    class YourExistingSQLSystem:
        """Your existing SQL system"""
        
        def __init__(self):
            # Your existing initialization
            self.llm = None  # Your LLM
            self.engine = None  # Your database engine
            self.sql_agent = None  # Your SQL RAG agent
            self.enhanced_agent = None  # New enhanced agent
        
        def setup_enhanced_scoring(self, schema_context: Dict[str, Any]):
            """Add enhanced scoring to your existing system"""
            
            # Import the enhanced components
            from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
            from genieml.agents.app.agents.nodes.sql.scoring_sql_rag_agent import EnhancedSQLRAGAgent
            
            # Create enhanced agent using your existing components
            self.enhanced_agent = EnhancedSQLRAGAgent(
                base_agent=self.sql_agent,  # Your existing SQL RAG agent
                relevance_scorer=SQLAdvancedRelevanceScorer(schema_context=schema_context)
            )
        
        async def generate_sql_enhanced(self, query: str, **kwargs):
            """Enhanced SQL generation method"""
            if self.enhanced_agent:
                return await self.enhanced_agent.generate_sql_with_scoring(query, **kwargs)
            else:
                # Fallback to regular agent
                return await self.sql_agent.process_sql_request("generation", query, **kwargs)
        
        def get_system_analytics(self):
            """Get system performance analytics"""
            if self.enhanced_agent:
                return self.enhanced_agent.get_performance_analytics()
            return {"message": "Enhanced scoring not enabled"}
    
    print("Integration example structure created!")
    print("To integrate:")
    print("1. Import EnhancedSQLRAGAgent and SQLAdvancedRelevanceScorer")
    print("2. Wrap your existing SQL RAG agent")
    print("3. Provide schema context for better scoring")
    print("4. Use enhanced methods for better quality assessment")
    
    return YourExistingSQLSystem()


# Main execution
async def main():
    """Main execution function"""
    try:
        # Run complete example
        enhanced_agent = await complete_enhanced_agent_example()
        
        # Show integration pattern
        system_example = integrate_with_existing_system()
        
        print(f"\n🎉 Demo completed successfully!")
        print(f"The EnhancedSQLRAGAgent is now ready for use in your system.")
        
        return enhanced_agent, system_example
        
    except Exception as e:
        logger.error(f"Error in demonstration: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())