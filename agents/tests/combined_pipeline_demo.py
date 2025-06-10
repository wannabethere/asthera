"""
Practical usage example of Combined SQL and Chart Pipeline
This demonstrates how to use the combined pipeline that handles SQL generation, chart generation, and reasoning
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.pipeline_container import PipelineContainer
from app.storage.documents import DocumentChromaStore
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider

settings = get_settings()

class CombinedPipelineDemo:
    """Demonstration of Combined SQL and Chart Pipeline with practical examples"""
    
    def __init__(self):
        self.schema_context = self._setup_demo_schema()
         
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.0,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize ChromaDB client
        self.persistent_client = chromadb.PersistentClient(
            path=settings.CHROMA_STORE_PATH
        )
        
        # Initialize document stores
        self.document_stores = {
            "db_schema": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="db_schema"
            ),
            "sql_pairs": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="sql_pairs"
            ),
            "instructions": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="instructions"
            ),
            "historical_question": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="historical_question"
            ),
            "table_description": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="table_description"
            )
        }
        
        # Initialize document store provider
        self.document_provider = DocumentStoreProvider(stores=self.document_stores)
        self.schema_documents = self._setup_schema_documents()
        
        # Initialize pipeline container
        self.pipeline_container = PipelineContainer.initialize()
        self.combined_pipeline = self.pipeline_container.get_pipeline("combined_sql_chart")
    
    def _setup_demo_schema(self) -> Dict[str, Any]:
        """Set up demo database schema context"""
        return {
            "schema": {
                "customers": [
                    "customer_id", "first_name", "last_name", "email",
                    "phone", "registration_date", "last_login", "is_active"
                ],
                "orders": [
                    "order_id", "customer_id", "order_date", "ship_date",
                    "total_amount", "tax_amount", "status", "payment_method"
                ],
                "products": [
                    "product_id", "product_name", "category", "price",
                    "stock_quantity", "supplier_id", "created_date"
                ],
                "order_items": [
                    "order_item_id", "order_id", "product_id", "quantity",
                    "unit_price", "discount", "line_total"
                ]
            },
            "relationships": {
                "customers_orders": "customers.customer_id = orders.customer_id",
                "orders_order_items": "orders.order_id = order_items.order_id",
                "products_order_items": "products.product_id = order_items.product_id"
            }
        }
    
    def _setup_schema_documents(self) -> List[str]:
        """Set up schema documents for RAG"""
        return [
            "CREATE TABLE customers (customer_id INT PRIMARY KEY, first_name VARCHAR(50), last_name VARCHAR(50), email VARCHAR(100), phone VARCHAR(20), registration_date DATE, last_login DATETIME, is_active BOOLEAN)",
            "CREATE TABLE orders (order_id INT PRIMARY KEY, customer_id INT, order_date DATE, ship_date DATE, total_amount DECIMAL(10,2), tax_amount DECIMAL(8,2), status VARCHAR(20), payment_method VARCHAR(30), FOREIGN KEY (customer_id) REFERENCES customers(customer_id))",
            "CREATE TABLE products (product_id INT PRIMARY KEY, product_name VARCHAR(100), category VARCHAR(50), price DECIMAL(8,2), stock_quantity INT, supplier_id INT, created_date DATE)",
            "CREATE TABLE order_items (order_item_id INT PRIMARY KEY, order_id INT, product_id INT, quantity INT, unit_price DECIMAL(8,2), discount DECIMAL(5,2), line_total DECIMAL(10,2), FOREIGN KEY (order_id) REFERENCES orders(order_id), FOREIGN KEY (product_id) REFERENCES products(product_id))"
        ]
    
    async def demo_combined_pipeline(self):
        """Demonstrate combined pipeline with different scenarios"""
        print("\n" + "=" * 80)
        print("🎯 COMBINED SQL AND CHART PIPELINE DEMO")
        print("=" * 80)
        
        # Example 1: Basic analysis with chart
        print("\n--- Example 1: Basic Analysis with Chart ---")
        request = {
            "query": "Show me the monthly sales trends for the last 6 months",
            "schema_context": self.schema_context,
            "schema_documents": self.schema_documents
        }
        
        print("Request: ", request["query"])
        result = await self.combined_pipeline.run(request)
        self._display_pipeline_result(result)
        
        # Example 2: Complex analysis with multiple metrics
        print("\n--- Example 2: Complex Analysis with Multiple Metrics ---")
        request = {
            "query": "Compare the average order value and total sales by product category",
            "schema_context": self.schema_context,
            "schema_documents": self.schema_documents
        }
        
        print("Request: ", request["query"])
        result = await self.combined_pipeline.run(request)
        self._display_pipeline_result(result)
        
        # Example 3: Time-based analysis with reasoning
        print("\n--- Example 3: Time-based Analysis with Reasoning ---")
        request = {
            "query": "Analyze customer retention rate and identify any seasonal patterns",
            "schema_context": self.schema_context,
            "schema_documents": self.schema_documents
        }
        
        print("Request: ", request["query"])
        result = await self.combined_pipeline.run(request)
        self._display_pipeline_result(result)
    
    def _display_pipeline_result(self, result: Dict[str, Any]):
        """Display pipeline results in a formatted way"""
        print("\nPipeline Results:")
        print("-" * 40)
        
        if not result.get("success", False):
            print("❌ Pipeline execution failed")
            return
        
        # Display SQL Results
        sql_result = result.get("sql_result", {})
        print("\n📊 SQL Generation:")
        print(f"Query: {sql_result.get('sql_query', 'N/A')}")
        print(f"Result: {json.dumps(sql_result.get('result', {}), indent=2)}")
        
        # Display Chart Results
        chart_result = result.get("chart_result", {})
        print("\n📈 Chart Generation:")
        print(f"Chart Type: {chart_result.get('chart_type', 'N/A')}")
        print(f"Chart Configuration: {json.dumps(chart_result.get('config', {}), indent=2)}")
        
        # Display Reasoning Results
        reasoning_result = result.get("reasoning_result", {})
        print("\n🤔 Reasoning Analysis:")
        print(f"Insights: {reasoning_result.get('insights', 'N/A')}")
        print(f"Recommendations: {reasoning_result.get('recommendations', 'N/A')}")
    
    async def run_complete_demo(self):
        """Run the complete demonstration"""
        print("🚀 Initializing Combined Pipeline Demo...")
        await self.demo_combined_pipeline()
        print("\n✅ Demo completed successfully!")

async def main():
    """Main entry point for the demo"""
    demo = CombinedPipelineDemo()
    await demo.run_complete_demo()

if __name__ == "__main__":
    asyncio.run(main()) 