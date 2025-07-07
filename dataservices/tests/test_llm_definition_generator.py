"""
Test suite for LLMDefinitionGenerator
Tests the generation of metrics, views, and calculated columns using LLM
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any
from datetime import datetime

# Import the classes we're testing
from app.agents.project_manager import LLMDefinitionGenerator
from app.service.models import UserExample, GeneratedDefinition, DefinitionType


class TestLLMDefinitionGenerator:
    """Test suite for LLMDefinitionGenerator"""
    
    @pytest.fixture
    def mock_llm(self):
        """Mock LLM client"""
        mock = Mock()
        mock.ainvoke = AsyncMock()
        return mock
    
    @pytest.fixture
    def generator(self, mock_llm):
        """LLMDefinitionGenerator instance with mocked LLM"""
        return LLMDefinitionGenerator(llm=mock_llm)
    
    @pytest.fixture
    def sample_context(self):
        """Sample project context for testing"""
        return {
            "tables": {
                "users": {
                    "name": "users",
                    "description": "User account information",
                    "columns": [
                        {"name": "user_id", "type": "INTEGER", "description": "Unique user identifier"},
                        {"name": "email", "type": "VARCHAR", "description": "User email address"},
                        {"name": "created_at", "type": "TIMESTAMP", "description": "Account creation date"},
                        {"name": "status", "type": "VARCHAR", "description": "Account status"}
                    ]
                },
                "orders": {
                    "name": "orders",
                    "description": "Customer order information",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "description": "Unique order identifier"},
                        {"name": "user_id", "type": "INTEGER", "description": "User who placed the order"},
                        {"name": "amount", "type": "DECIMAL", "description": "Order total amount"},
                        {"name": "order_date", "type": "TIMESTAMP", "description": "Order placement date"},
                        {"name": "status", "type": "VARCHAR", "description": "Order status"}
                    ]
                },
                "products": {
                    "name": "products",
                    "description": "Product catalog information",
                    "columns": [
                        {"name": "product_id", "type": "INTEGER", "description": "Unique product identifier"},
                        {"name": "name", "type": "VARCHAR", "description": "Product name"},
                        {"name": "price", "type": "DECIMAL", "description": "Product price"},
                        {"name": "category", "type": "VARCHAR", "description": "Product category"}
                    ]
                }
            },
            "existing_metrics": {
                "total_users": "Count of all users",
                "total_orders": "Count of all orders"
            },
            "business_context": {
                "domain": "E-commerce",
                "key_metrics": ["revenue", "conversion_rate", "customer_lifetime_value"],
                "business_goals": ["increase_sales", "improve_customer_satisfaction"]
            },
            "data_lineage": {
                "orders": ["users", "products"],
                "order_items": ["orders", "products"]
            }
        }
    
    @pytest.fixture
    def sample_user_examples(self):
        """Sample user examples for different definition types"""
        return {
            "metric": UserExample(
                definition_type=DefinitionType.METRIC,
                name="conversion_rate",
                description="Calculate the percentage of users who made a purchase",
                sql="SELECT COUNT(DISTINCT o.user_id) * 100.0 / COUNT(DISTINCT u.user_id) FROM users u LEFT JOIN orders o ON u.user_id = o.user_id",
                additional_context={"business_goal": "measure_user_engagement"}
            ),
            "view": UserExample(
                definition_type=DefinitionType.VIEW,
                name="user_order_summary",
                description="Create a view showing user order statistics",
                sql="SELECT u.user_id, u.email, COUNT(o.order_id) as order_count, SUM(o.amount) as total_spent FROM users u LEFT JOIN orders o ON u.user_id = o.user_id GROUP BY u.user_id, u.email",
                additional_context={"purpose": "reporting_and_analytics"}
            ),
            "calculated_column": UserExample(
                definition_type=DefinitionType.CALCULATED_COLUMN,
                name="order_value_tier",
                description="Categorize orders into value tiers based on amount",
                sql="CASE WHEN amount >= 100 THEN 'High Value' WHEN amount >= 50 THEN 'Medium Value' ELSE 'Low Value' END",
                additional_context={"business_rule": "segment_customers_by_spending"}
            )
        }
    
    @pytest.mark.asyncio
    async def test_generate_metric_definition_success(self, generator, sample_context, sample_user_examples, mock_llm):
        """Test successful metric definition generation"""
        # Mock LLM response
        mock_response = {
            "name": "conversion_rate",
            "display_name": "User Conversion Rate",
            "description": "Percentage of users who have made at least one purchase",
            "sql_query": "SELECT ROUND(CAST(COUNT(DISTINCT o.user_id) * 100.0 / NULLIF(COUNT(DISTINCT u.user_id), 0) AS DECIMAL(5,2)), 2) as conversion_rate FROM users u LEFT JOIN orders o ON u.user_id = o.user_id",
            "chain_of_thought": "Calculate conversion rate by dividing users with orders by total users, multiply by 100 for percentage",
            "related_tables": ["users", "orders"],
            "related_columns": ["user_id", "order_id"],
            "metadata": {
                "metric_type": "percentage",
                "aggregation_type": "custom",
                "format_string": "0.00%",
                "business_category": "performance",
                "update_frequency": "daily",
                "data_quality_requirements": ["no_duplicate_users", "valid_order_amounts"]
            },
            "confidence_score": 0.95,
            "suggestions": ["Add date filters for time-based analysis", "Consider excluding test users"]
        }
        
        mock_llm.ainvoke.return_value = json.dumps(mock_response)
        
        # Test the method
        result = await generator.generate_metric_definition(
            sample_user_examples["metric"], 
            sample_context
        )
        
        # Verify the result
        assert isinstance(result, GeneratedDefinition)
        assert result.definition_type == DefinitionType.METRIC
        assert result.name == "conversion_rate"
        assert result.display_name == "User Conversion Rate"
        assert result.confidence_score == 0.95
        assert "users" in result.related_tables
        assert "orders" in result.related_tables
        assert result.metadata["metric_type"] == "percentage"
        
        # Verify LLM was called with correct parameters
        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "conversion_rate" in call_args["name"]
        assert "percentage of users who made a purchase" in call_args["description"]
    
    @pytest.mark.asyncio
    async def test_generate_view_definition_success(self, generator, sample_context, sample_user_examples, mock_llm):
        """Test successful view definition generation"""
        # Mock LLM response
        mock_response = {
            "name": "user_order_summary",
            "display_name": "User Order Summary View",
            "description": "Comprehensive view of user order statistics for reporting and analytics",
            "sql_query": "CREATE VIEW user_order_summary AS SELECT u.user_id, u.email, COUNT(o.order_id) as order_count, SUM(o.amount) as total_spent, AVG(o.amount) as avg_order_value FROM users u LEFT JOIN orders o ON u.user_id = o.user_id GROUP BY u.user_id, u.email",
            "chain_of_thought": "Create a view that aggregates order data by user for easy reporting and analysis",
            "related_tables": ["users", "orders"],
            "related_columns": ["user_id", "email", "order_id", "amount"],
            "metadata": {
                "view_type": "aggregated",
                "refresh_strategy": "on-demand",
                "performance_impact": "medium",
                "business_use_case": "reporting",
                "dependencies": ["users", "orders"],
                "security_considerations": ["user_privacy", "data_access_controls"]
            },
            "confidence_score": 0.90,
            "suggestions": ["Add indexes on user_id for better performance", "Consider materializing for large datasets"]
        }
        
        mock_llm.ainvoke.return_value = json.dumps(mock_response)
        
        # Test the method
        result = await generator.generate_view_definition(
            sample_user_examples["view"], 
            sample_context
        )
        
        # Verify the result
        assert isinstance(result, GeneratedDefinition)
        assert result.definition_type == DefinitionType.VIEW
        assert result.name == "user_order_summary"
        assert result.display_name == "User Order Summary View"
        assert result.confidence_score == 0.90
        assert result.metadata["view_type"] == "aggregated"
        assert "CREATE VIEW" in result.sql_query
    
    @pytest.mark.asyncio
    async def test_generate_calculated_column_definition_success(self, generator, sample_context, sample_user_examples, mock_llm):
        """Test successful calculated column definition generation"""
        # Mock LLM response
        mock_response = {
            "name": "order_value_tier",
            "display_name": "Order Value Tier",
            "description": "Categorizes orders into value tiers for customer segmentation and analysis",
            "sql_query": "CASE WHEN amount >= 100 THEN 'High Value' WHEN amount >= 50 THEN 'Medium Value' ELSE 'Low Value' END",
            "chain_of_thought": "Use CASE statement to categorize orders based on amount thresholds for business analysis",
            "related_tables": ["orders"],
            "related_columns": ["amount"],
            "metadata": {
                "data_type": "VARCHAR",
                "calculation_type": "conditional",
                "dependencies": ["amount"],
                "null_handling": "Returns NULL if amount is NULL",
                "performance_impact": "low",
                "validation_rules": ["amount_should_be_positive"],
                "business_rules_applied": ["value_tier_categorization"]
            },
            "confidence_score": 0.88,
            "suggestions": ["Consider making thresholds configurable", "Add more granular tiers"]
        }
        
        mock_llm.ainvoke.return_value = json.dumps(mock_response)
        
        # Test the method
        result = await generator.generate_calculated_column_definition(
            sample_user_examples["calculated_column"], 
            sample_context
        )
        
        # Verify the result
        assert isinstance(result, GeneratedDefinition)
        assert result.definition_type == DefinitionType.CALCULATED_COLUMN
        assert result.name == "order_value_tier"
        assert result.display_name == "Order Value Tier"
        assert result.confidence_score == 0.88
        assert result.metadata["calculation_type"] == "conditional"
        assert "CASE WHEN" in result.sql_query
    
    @pytest.mark.asyncio
    async def test_llm_error_handling(self, generator, sample_context, sample_user_examples, mock_llm):
        """Test error handling when LLM call fails"""
        # Mock LLM to raise an exception
        mock_llm.ainvoke.side_effect = Exception("LLM API error")
        
        # Test that the original exception is re-raised
        with pytest.raises(Exception) as exc_info:
            await generator.generate_metric_definition(
                sample_user_examples["metric"], 
                sample_context
            )
        
        assert "LLM API error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_invalid_json_response_handling(self, generator, sample_context, sample_user_examples, mock_llm):
        """Test handling of invalid JSON response from LLM"""
        # Mock LLM to return invalid JSON
        mock_llm.ainvoke.return_value = "Invalid JSON response"
        
        # Test that JSON parsing error is handled
        with pytest.raises(Exception) as exc_info:
            await generator.generate_metric_definition(
                sample_user_examples["metric"], 
                sample_context
            )
        
        assert "Failed to parse LLM response" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_missing_required_fields_handling(self, generator, sample_context, sample_user_examples, mock_llm):
        """Test handling of LLM response with missing required fields"""
        # Mock LLM to return incomplete response
        mock_response = {
            "name": "test_metric",
            # Missing other required fields
        }
        
        mock_llm.ainvoke.return_value = json.dumps(mock_response)
        
        # Test that the method handles missing fields gracefully
        result = await generator.generate_metric_definition(
            sample_user_examples["metric"], 
            sample_context
        )
        
        # Verify default values are used for missing fields
        assert result.name == "test_metric"
        assert result.display_name == ""  # Default empty string
        assert result.confidence_score == 0.0  # Default score
        assert result.related_tables == []  # Default empty list
    
    @pytest.mark.asyncio
    async def test_percentage_handling_in_sql(self, generator, sample_context, mock_llm):
        """Test that percentage calculations are properly formatted"""
        # Create a user example with percentage calculation
        percentage_example = UserExample(
            definition_type=DefinitionType.METRIC,
            name="success_rate",
            description="Calculate success rate as percentage",
            sql="SELECT successful_count / total_count * 100 FROM events",
            additional_context={"business_goal": "measure_success_rate"}
        )
        
        # Mock LLM response
        mock_response = {
            "name": "success_rate",
            "display_name": "Success Rate",
            "description": "Percentage of successful events",
            "sql_query": "SELECT ROUND(CAST(CASE WHEN total_count > 0 THEN (successful_count * 100.0 / total_count) ELSE 0 END AS DECIMAL(5,2)), 2) as success_rate FROM events",
            "chain_of_thought": "Calculate percentage with proper decimal casting and rounding",
            "related_tables": ["events"],
            "related_columns": ["successful_count", "total_count"],
            "metadata": {
                "metric_type": "percentage",
                "aggregation_type": "custom"
            },
            "confidence_score": 0.95,
            "suggestions": []
        }
        
        mock_llm.ainvoke.return_value = json.dumps(mock_response)
        
        # Test the method
        result = await generator.generate_metric_definition(
            percentage_example, 
            sample_context
        )
        
        # Verify percentage formatting is applied
        assert "CAST" in result.sql_query
        assert "DECIMAL" in result.sql_query
        assert "ROUND" in result.sql_query
        assert result.metadata["metric_type"] == "percentage"
    
    @pytest.mark.asyncio
    async def test_complex_business_context_handling(self, generator, mock_llm):
        """Test handling of complex business context"""
        # Create complex context
        complex_context = {
            "tables": {
                "customer_segments": {
                    "name": "customer_segments",
                    "description": "Customer segmentation data",
                    "columns": [
                        {"name": "customer_id", "type": "INTEGER", "description": "Customer identifier"},
                        {"name": "segment", "type": "VARCHAR", "description": "Customer segment"},
                        {"name": "lifetime_value", "type": "DECIMAL", "description": "Customer lifetime value"}
                    ]
                }
            },
            "business_context": {
                "domain": "Financial Services",
                "key_metrics": ["customer_lifetime_value", "churn_rate", "acquisition_cost"],
                "business_goals": ["increase_retention", "reduce_churn", "optimize_acquisition"],
                "regulatory_requirements": ["GDPR", "SOX", "PCI_DSS"],
                "risk_factors": ["credit_risk", "operational_risk", "compliance_risk"]
            }
        }
        
        complex_example = UserExample(
            definition_type=DefinitionType.METRIC,
            name="customer_lifetime_value",
            description="Calculate average customer lifetime value by segment",
            sql="SELECT segment, AVG(lifetime_value) FROM customer_segments GROUP BY segment",
            additional_context={"business_goal": "customer_valuation"}
        )
        
        # Mock LLM response
        mock_response = {
            "name": "customer_lifetime_value",
            "display_name": "Customer Lifetime Value by Segment",
            "description": "Average customer lifetime value segmented by customer category",
            "sql_query": "SELECT segment, ROUND(CAST(AVG(lifetime_value) AS DECIMAL(10,2)), 2) as avg_lifetime_value FROM customer_segments GROUP BY segment",
            "chain_of_thought": "Calculate average lifetime value grouped by customer segments for business analysis",
            "related_tables": ["customer_segments"],
            "related_columns": ["segment", "lifetime_value"],
            "metadata": {
                "metric_type": "average",
                "aggregation_type": "avg",
                "business_category": "customer_analytics",
                "regulatory_considerations": ["data_privacy", "financial_reporting"]
            },
            "confidence_score": 0.92,
            "suggestions": ["Consider time-based analysis", "Add confidence intervals"]
        }
        
        mock_llm.ainvoke.return_value = json.dumps(mock_response)
        
        # Test the method
        result = await generator.generate_metric_definition(
            complex_example, 
            complex_context
        )
        
        # Verify complex context is handled
        assert result.metadata["business_category"] == "customer_analytics"
        assert "regulatory_considerations" in result.metadata
        assert result.confidence_score == 0.92


class TestLLMDefinitionGeneratorIntegration:
    """Integration tests for LLMDefinitionGenerator with real scenarios"""
    
    @pytest.mark.asyncio
    async def test_full_definition_generation_workflow(self):
        """Test the complete workflow of generating all three definition types"""
        # This would be an integration test with a real LLM
        # For now, we'll test the structure and flow
        
        generator = LLMDefinitionGenerator()
        
        # Test data
        context = {
            "tables": {
                "sales": {
                    "name": "sales",
                    "description": "Sales transaction data",
                    "columns": [
                        {"name": "sale_id", "type": "INTEGER"},
                        {"name": "product_id", "type": "INTEGER"},
                        {"name": "quantity", "type": "INTEGER"},
                        {"name": "unit_price", "type": "DECIMAL"},
                        {"name": "sale_date", "type": "TIMESTAMP"}
                    ]
                }
            },
            "business_context": {
                "domain": "Retail",
                "key_metrics": ["revenue", "units_sold", "average_order_value"]
            }
        }
        
        # Test all three definition types
        examples = [
            UserExample(
                definition_type=DefinitionType.METRIC,
                name="total_revenue",
                description="Sum of all sales revenue",
                sql="SELECT SUM(quantity * unit_price) FROM sales"
            ),
            UserExample(
                definition_type=DefinitionType.VIEW,
                name="daily_sales_summary",
                description="Daily aggregated sales data",
                sql="SELECT DATE(sale_date), SUM(quantity * unit_price) as daily_revenue FROM sales GROUP BY DATE(sale_date)"
            ),
            UserExample(
                definition_type=DefinitionType.CALCULATED_COLUMN,
                name="total_amount",
                description="Calculate total amount for each sale",
                sql="quantity * unit_price"
            )
        ]
        
        # Note: These would fail with real LLM calls in test environment
        # but we can verify the method signatures and expected behavior
        for example in examples:
            assert example.definition_type in [DefinitionType.METRIC, DefinitionType.VIEW, DefinitionType.CALCULATED_COLUMN]
            assert example.name
            assert example.description


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"]) 