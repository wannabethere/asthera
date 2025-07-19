import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from app.core.provider import DocumentStoreProvider
from app.core.dependencies import get_embedder

logger = logging.getLogger("lexy-ai-service")


@dataclass
class VectorStoreDocument:
    """Document structure for vector store ingestion"""
    content: str
    metadata: Dict[str, Any]
    doc_id: Optional[str] = None


class MetricsVectorStoreSetup:
    """Setup and manage vector stores for metrics recommendation system"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.doc_store_provider = doc_store_provider
        self.embeddings = get_embedder()
        
        # Initialize required vector stores
        self.store_configs = {
            "dataset_definitions": {
                "description": "Dataset definitions and data dictionary information",
                "collection_name": "dataset_definitions"
            },
            "column_descriptions": {
                "description": "Detailed column descriptions and data types",
                "collection_name": "column_descriptions"
            },
            "example_metrics": {
                "description": "Example metrics and SQL query templates",
                "collection_name": "example_metrics"
            },
            "sql_examples": {
                "description": "Example SQL queries and their corresponding business questions",
                "collection_name": "sql_examples"
            },
            "knowledge_base": {
                "description": "Domain knowledge and analytical best practices",
                "collection_name": "knowledge_base"
            }
        }

    async def setup_all_stores(self) -> Dict[str, bool]:
        """Setup all required vector stores"""
        results = {}
        
        for store_name, config in self.store_configs.items():
            try:
                store = self.doc_store_provider.get_store(store_name)
                await self._initialize_store_if_empty(store, store_name)
                results[store_name] = True
                logger.info(f"Successfully setup vector store: {store_name}")
            except Exception as e:
                logger.error(f"Failed to setup vector store {store_name}: {e}")
                results[store_name] = False
        
        return results

    async def _initialize_store_if_empty(self, store, store_name: str):
        """Initialize store with sample data if empty"""
        try:
            # Check if store has documents
            # This is a placeholder - actual implementation depends on your vector store interface
            existing_docs = await self._check_store_contents(store)
            
            if not existing_docs:
                logger.info(f"Initializing empty store: {store_name}")
                await self._populate_store_with_samples(store, store_name)
            else:
                logger.info(f"Store {store_name} already contains {len(existing_docs)} documents")
                
        except Exception as e:
            logger.warning(f"Could not check/initialize store {store_name}: {e}")

    async def _check_store_contents(self, store) -> List[Dict]:
        """Check if store contains documents - implement based on your vector store interface"""
        try:
            # This is a placeholder - implement based on your actual vector store interface
            # For example, if using ChromaDB:
            # results = store.get(limit=1)
            # return results.get('documents', [])
            return []
        except:
            return []

    async def _populate_store_with_samples(self, store, store_name: str):
        """Populate store with sample data"""
        sample_data = self._get_sample_data(store_name)
        
        for doc in sample_data:
            try:
                await store.add_document(
                    content=doc.content,
                    metadata=doc.metadata,
                    doc_id=doc.doc_id
                )
            except Exception as e:
                logger.warning(f"Failed to add sample document to {store_name}: {e}")

    def _get_sample_data(self, store_name: str) -> List[VectorStoreDocument]:
        """Get sample data for each store type"""
        
        if store_name == "dataset_definitions":
            return self._get_dataset_definition_samples()
        elif store_name == "column_descriptions":
            return self._get_column_description_samples()
        elif store_name == "example_metrics":
            return self._get_example_metrics_samples()
        elif store_name == "sql_examples":
            return self._get_sql_examples_samples()
        elif store_name == "knowledge_base":
            return self._get_knowledge_base_samples()
        else:
            return []

    def _get_dataset_definition_samples(self) -> List[VectorStoreDocument]:
        """Sample dataset definitions"""
        return [
            VectorStoreDocument(
                content="Sales Dataset: Contains transaction-level sales data with customer information, product details, timestamps, quantities, and revenue amounts. Includes data from multiple channels including online, retail, and wholesale.",
                metadata={
                    "dataset_name": "sales_data",
                    "domain": "e-commerce",
                    "data_type": "transactional",
                    "time_range": "2020-2024",
                    "update_frequency": "daily"
                },
                doc_id="dataset_sales_001"
            ),
            VectorStoreDocument(
                content="Customer Dataset: Comprehensive customer profiles including demographics, registration dates, loyalty status, communication preferences, and geographical information. Used for customer segmentation and behavior analysis.",
                metadata={
                    "dataset_name": "customer_data",
                    "domain": "customer_management",
                    "data_type": "master_data",
                    "time_range": "2018-2024",
                    "update_frequency": "real-time"
                },
                doc_id="dataset_customer_001"
            ),
            VectorStoreDocument(
                content="Product Catalog: Master product information including SKUs, categories, brands, pricing, inventory levels, and product attributes. Essential for inventory management and product performance analysis.",
                metadata={
                    "dataset_name": "product_catalog",
                    "domain": "inventory",
                    "data_type": "master_data",
                    "time_range": "2019-2024",
                    "update_frequency": "hourly"
                },
                doc_id="dataset_product_001"
            )
        ]

    def _get_column_description_samples(self) -> List[VectorStoreDocument]:
        """Sample column descriptions"""
        return [
            VectorStoreDocument(
                content="customer_id: Unique identifier for each customer. Primary key for customer table. Format: CUS followed by 8-digit number (e.g., CUS12345678). Never null.",
                metadata={
                    "table_name": "customers",
                    "column_name": "customer_id",
                    "data_type": "varchar(12)",
                    "is_primary_key": True,
                    "is_nullable": False
                },
                doc_id="col_customer_id_001"
            ),
            VectorStoreDocument(
                content="order_total: Total amount of the order including tax and shipping. Calculated field based on line items. Currency in USD. Range typically $5-$5000.",
                metadata={
                    "table_name": "orders",
                    "column_name": "order_total",
                    "data_type": "decimal(10,2)",
                    "is_primary_key": False,
                    "is_nullable": False,
                    "business_rules": "includes_tax_and_shipping"
                },
                doc_id="col_order_total_001"
            ),
            VectorStoreDocument(
                content="product_category: Main category classification for products. Values include Electronics, Clothing, Home_Garden, Books, Sports, Beauty. Used for reporting and inventory management.",
                metadata={
                    "table_name": "products",
                    "column_name": "product_category",
                    "data_type": "varchar(50)",
                    "is_primary_key": False,
                    "is_nullable": False,
                    "valid_values": ["Electronics", "Clothing", "Home_Garden", "Books", "Sports", "Beauty"]
                },
                doc_id="col_product_category_001"
            )
        ]

    def _get_example_metrics_samples(self) -> List[VectorStoreDocument]:
        """Sample metrics and SQL templates"""
        return [
            VectorStoreDocument(
                content="""
                Metric: Customer Lifetime Value (CLV)
                Description: Total revenue generated by a customer over their entire relationship with the company
                SQL Template:
                SELECT 
                    customer_id,
                    SUM(order_total) as lifetime_value,
                    COUNT(DISTINCT order_id) as total_orders,
                    AVG(order_total) as avg_order_value
                FROM orders 
                WHERE customer_id = '{customer_id}'
                GROUP BY customer_id
                
                Business Value: Identifies high-value customers for retention strategies and personalized marketing
                """,
                metadata={
                    "metric_name": "customer_lifetime_value",
                    "metric_type": "aggregate",
                    "domain": "customer_analytics",
                    "tables_used": ["orders"],
                    "complexity": "medium",
                    "confidence_score": 0.9
                },
                doc_id="metric_clv_001"
            ),
            VectorStoreDocument(
                content="""
                Metric: Monthly Recurring Revenue (MRR)
                Description: Predictable revenue generated each month from recurring subscriptions
                SQL Template:
                SELECT 
                    DATE_TRUNC('month', order_date) as month,
                    SUM(CASE WHEN subscription_type = 'monthly' THEN order_total ELSE 0 END) as monthly_revenue
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE subscription_type IN ('monthly', 'annual')
                GROUP BY DATE_TRUNC('month', order_date)
                ORDER BY month
                
                Business Value: Essential for SaaS businesses to track growth and predict future revenue
                """,
                metadata={
                    "metric_name": "monthly_recurring_revenue",
                    "metric_type": "trend",
                    "domain": "subscription_analytics",
                    "tables_used": ["orders", "customers"],
                    "complexity": "medium",
                    "confidence_score": 0.85
                },
                doc_id="metric_mrr_001"
            ),
            VectorStoreDocument(
                content="""
                Metric: Customer Acquisition Cost (CAC)
                Description: Average cost to acquire a new customer through marketing and sales efforts
                SQL Template:
                SELECT 
                    DATE_TRUNC('month', c.registration_date) as month,
                    COUNT(DISTINCT c.customer_id) as new_customers,
                    SUM(m.marketing_spend) / COUNT(DISTINCT c.customer_id) as cac
                FROM customers c
                JOIN marketing_campaigns m ON DATE_TRUNC('month', c.registration_date) = DATE_TRUNC('month', m.campaign_date)
                GROUP BY DATE_TRUNC('month', c.registration_date)
                ORDER BY month
                
                Business Value: Helps optimize marketing spend and understand customer acquisition efficiency
                """,
                metadata={
                    "metric_name": "customer_acquisition_cost",
                    "metric_type": "ratio",
                    "domain": "marketing_analytics",
                    "tables_used": ["customers", "marketing_campaigns"],
                    "complexity": "high",
                    "confidence_score": 0.8
                },
                doc_id="metric_cac_001"
            )
        ]

    def _get_sql_examples_samples(self) -> List[VectorStoreDocument]:
        """Sample SQL examples and their corresponding questions"""
        return [
            VectorStoreDocument(
                content="""
                Question: What are the top 10 customers by total revenue?
                SQL Query:
                SELECT 
                    c.customer_id,
                    c.customer_name,
                    SUM(o.order_total) as total_revenue,
                    COUNT(o.order_id) as total_orders
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                GROUP BY c.customer_id, c.customer_name
                ORDER BY total_revenue DESC
                LIMIT 10;
                
                Business Context: Identifies high-value customers for VIP programs and personalized attention
                Category: Customer Analysis
                Difficulty: Beginner
                """,
                metadata={
                    "question": "What are the top 10 customers by total revenue?",
                    "sql_type": "aggregation_with_join",
                    "category": "customer_analysis",
                    "difficulty": "beginner",
                    "tables_used": ["customers", "orders"],
                    "business_domain": "revenue_analysis"
                },
                doc_id="sql_example_top_customers_001"
            ),
            VectorStoreDocument(
                content="""
                Question: How has monthly revenue trended over the past year?
                SQL Query:
                SELECT 
                    DATE_TRUNC('month', order_date) as month,
                    SUM(order_total) as monthly_revenue,
                    COUNT(DISTINCT order_id) as total_orders,
                    COUNT(DISTINCT customer_id) as unique_customers
                FROM orders
                WHERE order_date >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY DATE_TRUNC('month', order_date)
                ORDER BY month;
                
                Business Context: Track business growth and identify seasonal patterns
                Category: Revenue Analysis
                Difficulty: Intermediate
                """,
                metadata={
                    "question": "How has monthly revenue trended over the past year?",
                    "sql_type": "time_series_analysis",
                    "category": "revenue_analysis",
                    "difficulty": "intermediate",
                    "tables_used": ["orders"],
                    "business_domain": "trend_analysis"
                },
                doc_id="sql_example_revenue_trend_001"
            ),
            VectorStoreDocument(
                content="""
                Question: Which products have the highest profit margins?
                SQL Query:
                SELECT 
                    p.product_name,
                    p.product_category,
                    AVG(oi.unit_price - p.cost_price) as avg_profit_per_unit,
                    AVG((oi.unit_price - p.cost_price) / oi.unit_price * 100) as profit_margin_percent,
                    SUM(oi.quantity) as total_units_sold
                FROM products p
                JOIN order_items oi ON p.product_id = oi.product_id
                GROUP BY p.product_id, p.product_name, p.product_category
                HAVING SUM(oi.quantity) > 50
                ORDER BY profit_margin_percent DESC;
                
                Business Context: Optimize product mix and pricing strategies
                Category: Product Analysis
                Difficulty: Intermediate
                """,
                metadata={
                    "question": "Which products have the highest profit margins?",
                    "sql_type": "profit_analysis",
                    "category": "product_analysis",
                    "difficulty": "intermediate",
                    "tables_used": ["products", "order_items"],
                    "business_domain": "profitability_analysis"
                },
                doc_id="sql_example_profit_margins_001"
            ),
            VectorStoreDocument(
                content="""
                Question: What is the customer retention rate by month?
                SQL Query:
                WITH customer_months AS (
                    SELECT 
                        customer_id,
                        DATE_TRUNC('month', order_date) as order_month,
                        LAG(DATE_TRUNC('month', order_date)) OVER (PARTITION BY customer_id ORDER BY DATE_TRUNC('month', order_date)) as prev_month
                    FROM orders
                    GROUP BY customer_id, DATE_TRUNC('month', order_date)
                ),
                retention_data AS (
                    SELECT 
                        order_month,
                        COUNT(DISTINCT customer_id) as total_customers,
                        COUNT(DISTINCT CASE WHEN prev_month = order_month - INTERVAL '1 month' THEN customer_id END) as retained_customers
                    FROM customer_months
                    GROUP BY order_month
                )
                SELECT 
                    order_month,
                    total_customers,
                    retained_customers,
                    ROUND(retained_customers * 100.0 / total_customers, 2) as retention_rate_percent
                FROM retention_data
                ORDER BY order_month;
                
                Business Context: Monitor customer loyalty and identify retention issues
                Category: Customer Retention
                Difficulty: Advanced
                """,
                metadata={
                    "question": "What is the customer retention rate by month?",
                    "sql_type": "cohort_analysis",
                    "category": "customer_retention",
                    "difficulty": "advanced",
                    "tables_used": ["orders"],
                    "business_domain": "customer_lifecycle"
                },
                doc_id="sql_example_retention_001"
            ),
            VectorStoreDocument(
                content="""
                Question: Which marketing channels drive the highest value customers?
                SQL Query:
                SELECT 
                    c.acquisition_channel,
                    COUNT(DISTINCT c.customer_id) as total_customers,
                    AVG(customer_stats.total_revenue) as avg_customer_value,
                    AVG(customer_stats.total_orders) as avg_orders_per_customer,
                    SUM(customer_stats.total_revenue) as channel_total_revenue
                FROM customers c
                JOIN (
                    SELECT 
                        customer_id,
                        SUM(order_total) as total_revenue,
                        COUNT(order_id) as total_orders
                    FROM orders
                    GROUP BY customer_id
                ) customer_stats ON c.customer_id = customer_stats.customer_id
                GROUP BY c.acquisition_channel
                ORDER BY avg_customer_value DESC;
                
                Business Context: Optimize marketing spend allocation across channels
                Category: Marketing Analysis
                Difficulty: Intermediate
                """,
                metadata={
                    "question": "Which marketing channels drive the highest value customers?",
                    "sql_type": "channel_analysis",
                    "category": "marketing_analysis",
                    "difficulty": "intermediate",
                    "tables_used": ["customers", "orders"],
                    "business_domain": "marketing_optimization"
                },
                doc_id="sql_example_marketing_channels_001"
            ),
            VectorStoreDocument(
                content="""
                Question: What are the best selling product combinations?
                SQL Query:
                WITH order_products AS (
                    SELECT 
                        o.order_id,
                        ARRAY_AGG(p.product_name ORDER BY p.product_name) as products_in_order
                    FROM orders o
                    JOIN order_items oi ON o.order_id = oi.order_id
                    JOIN products p ON oi.product_id = p.product_id
                    GROUP BY o.order_id
                    HAVING COUNT(DISTINCT oi.product_id) >= 2
                ),
                product_pairs AS (
                    SELECT 
                        products_in_order[i] as product_a,
                        products_in_order[j] as product_b,
                        COUNT(*) as combination_count
                    FROM order_products
                    CROSS JOIN generate_series(1, array_length(products_in_order, 1)) as i
                    CROSS JOIN generate_series(i+1, array_length(products_in_order, 1)) as j
                    GROUP BY products_in_order[i], products_in_order[j]
                )
                SELECT 
                    product_a,
                    product_b,
                    combination_count,
                    RANK() OVER (ORDER BY combination_count DESC) as popularity_rank
                FROM product_pairs
                ORDER BY combination_count DESC
                LIMIT 20;
                
                Business Context: Design product bundles and cross-selling strategies
                Category: Product Analysis
                Difficulty: Advanced
                """,
                metadata={
                    "question": "What are the best selling product combinations?",
                    "sql_type": "market_basket_analysis",
                    "category": "product_analysis",
                    "difficulty": "advanced",
                    "tables_used": ["orders", "order_items", "products"],
                    "business_domain": "cross_selling"
                },
                doc_id="sql_example_product_combinations_001"
            )
        ]

    def _get_knowledge_base_samples(self) -> List[VectorStoreDocument]:
        """Sample knowledge base documents"""
        return [
            VectorStoreDocument(
                content="""
                Customer Segmentation Best Practices:
                
                1. RFM Analysis: Segment customers based on Recency, Frequency, and Monetary value
                2. Behavioral Segmentation: Group customers by purchase patterns, product preferences, and engagement levels
                3. Demographic Segmentation: Use age, location, gender, and other demographic factors
                4. Value-Based Segmentation: Classify customers by lifetime value and profitability
                
                Key Metrics for Customer Analysis:
                - Customer Lifetime Value (CLV)
                - Customer Acquisition Cost (CAC)
                - Churn Rate
                - Net Promoter Score (NPS)
                - Average Order Value (AOV)
                """,
                metadata={
                    "topic": "customer_segmentation",
                    "domain": "customer_analytics",
                    "content_type": "best_practices",
                    "relevance_score": 0.9
                },
                doc_id="kb_customer_seg_001"
            ),
            VectorStoreDocument(
                content="""
                E-commerce Analytics Framework:
                
                Revenue Metrics:
                - Total Revenue: Sum of all completed transactions
                - Revenue per Visitor: Total revenue divided by unique visitors
                - Conversion Rate: Percentage of visitors who make a purchase
                - Average Order Value: Mean transaction amount
                
                Product Performance:
                - Product Revenue: Revenue contribution by product
                - Product Conversion Rate: Purchase rate for each product
                - Inventory Turnover: How quickly products sell
                - Cross-sell/Up-sell Rate: Additional product purchase rate
                
                Customer Metrics:
                - Customer Acquisition Cost
                - Customer Lifetime Value
                - Repeat Purchase Rate
                - Customer Retention Rate
                """,
                metadata={
                    "topic": "ecommerce_analytics",
                    "domain": "retail_analytics",
                    "content_type": "framework",
                    "relevance_score": 0.85
                },
                doc_id="kb_ecommerce_001"
            ),
            VectorStoreDocument(
                content="""
                SQL Optimization for Analytics:
                
                1. Use appropriate indexes on columns used in WHERE, JOIN, and GROUP BY clauses
                2. Leverage date partitioning for time-series analysis
                3. Use window functions for running totals and moving averages
                4. Implement proper data types to optimize storage and performance
                5. Use EXPLAIN plans to identify performance bottlenecks
                
                Common Analytics SQL Patterns:
                - Cohort Analysis: GROUP BY registration month, purchase month
                - Moving Averages: AVG(metric) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
                - Year-over-Year Growth: LAG(metric, 12) OVER (ORDER BY month)
                - Percentile Calculations: PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value)
                """,
                metadata={
                    "topic": "sql_optimization",
                    "domain": "data_engineering",
                    "content_type": "technical_guide",
                    "relevance_score": 0.75
                },
                doc_id="kb_sql_opt_001"
            )
        ]

    async def add_custom_document(
        self, 
        store_name: str, 
        content: str, 
        metadata: Dict[str, Any], 
        doc_id: Optional[str] = None
    ) -> bool:
        """Add a custom document to a specific store"""
        try:
            if store_name not in self.store_configs:
                raise ValueError(f"Unknown store: {store_name}")
            
            store = self.doc_store_provider.get_store(store_name)
            
            await store.add_document(
                content=content,
                metadata=metadata,
                doc_id=doc_id
            )
            
            logger.info(f"Successfully added document to {store_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document to {store_name}: {e}")
            return False

    async def bulk_import_documents(
        self, 
        store_name: str, 
        documents: List[VectorStoreDocument]
    ) -> Dict[str, Any]:
        """Bulk import documents to a specific store"""
        results = {
            "total": len(documents),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            if store_name not in self.store_configs:
                raise ValueError(f"Unknown store: {store_name}")
            
            store = self.doc_store_provider.get_store(store_name)
            
            for i, doc in enumerate(documents):
                try:
                    await store.add_document(
                        content=doc.content,
                        metadata=doc.metadata,
                        doc_id=doc.doc_id or f"bulk_import_{store_name}_{i}"
                    )
                    results["successful"] += 1
                    
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Document {i}: {str(e)}")
                    logger.warning(f"Failed to import document {i} to {store_name}: {e}")
            
            logger.info(f"Bulk import to {store_name}: {results['successful']}/{results['total']} successful")
            
        except Exception as e:
            logger.error(f"Failed bulk import to {store_name}: {e}")
            results["errors"].append(f"Bulk import error: {str(e)}")
        
        return results


# Example usage and setup script
async def setup_metrics_vector_stores():
    """Setup script for metrics recommendation vector stores"""
    from app.core.dependencies import get_doc_store_provider
    
    doc_store_provider = get_doc_store_provider()
    setup_manager = MetricsVectorStoreSetup(doc_store_provider)
    
    print("Setting up vector stores for metrics recommendation...")
    
    # Setup all stores
    results = await setup_manager.setup_all_stores()
    
    print("\nSetup Results:")
    for store_name, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"  {store_name}: {status}")
    
    # Example of adding custom documents
    custom_metric = VectorStoreDocument(
        content="""
        Metric: Customer Churn Rate
        Description: Percentage of customers who stop purchasing within a specific time period
        SQL Template:
        WITH customer_activity AS (
            SELECT 
                customer_id,
                MAX(order_date) as last_order_date,
                COUNT(*) as total_orders
            FROM orders
            GROUP BY customer_id
        )
        SELECT 
            COUNT(CASE WHEN last_order_date < CURRENT_DATE - INTERVAL '90 days' THEN 1 END) * 100.0 / COUNT(*) as churn_rate
        FROM customer_activity
        WHERE total_orders > 1
        
        Business Value: Critical for retention strategies and customer lifecycle management
        """,
        metadata={
            "metric_name": "customer_churn_rate",
            "metric_type": "ratio",
            "domain": "customer_analytics",
            "tables_used": ["orders"],
            "complexity": "medium",
            "confidence_score": 0.9
        },
        doc_id="metric_churn_001"
    )
    
    # Add the custom metric
    success = await setup_manager.add_custom_document(
        store_name="example_metrics",
        content=custom_metric.content,
        metadata=custom_metric.metadata,
        doc_id=custom_metric.doc_id
    )
    
    if success:
        print("\n✓ Successfully added custom churn rate metric")
    else:
        print("\n✗ Failed to add custom metric")
    
    # Example of adding custom SQL example
    custom_sql_example = VectorStoreDocument(
        content="""
        Question: How many new customers were acquired each quarter?
        SQL Query:
        SELECT 
            EXTRACT(YEAR FROM registration_date) as year,
            EXTRACT(QUARTER FROM registration_date) as quarter,
            COUNT(*) as new_customers,
            COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY EXTRACT(YEAR FROM registration_date), EXTRACT(QUARTER FROM registration_date)) as growth_from_prev_quarter
        FROM customers
        GROUP BY EXTRACT(YEAR FROM registration_date), EXTRACT(QUARTER FROM registration_date)
        ORDER BY year, quarter;
        
        Business Context: Track customer acquisition trends and growth rates
        Category: Customer Acquisition
        Difficulty: Intermediate
        """,
        metadata={
            "question": "How many new customers were acquired each quarter?",
            "sql_type": "time_series_growth",
            "category": "customer_acquisition",
            "difficulty": "intermediate",
            "tables_used": ["customers"],
            "business_domain": "growth_analysis"
        },
        doc_id="sql_example_quarterly_acquisition_001"
    )
    
    # Add the custom SQL example
    success = await setup_manager.add_custom_document(
        store_name="sql_examples",
        content=custom_sql_example.content,
        metadata=custom_sql_example.metadata,
        doc_id=custom_sql_example.doc_id
    )
    
    if success:
        print("✓ Successfully added custom SQL example")
    else:
        print("✗ Failed to add custom SQL example")


if __name__ == "__main__":
    # Run the setup
    asyncio.run(setup_metrics_vector_stores())