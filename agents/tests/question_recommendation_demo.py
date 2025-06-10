"""
Practical usage example of Question Recommendation System
This shows how to integrate and use the question recommendation system in your application
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.base import Pipeline
from app.agents.pipelines.enhanced_sql_pipeline import EnhancedPipelineFactory
from app.storage.documents import DocumentChromaStore
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider
from app.services.sql.question_recommendation import QuestionRecommendation, Configuration
from app.services.sql.models import Event
from app.agents.pipelines.pipeline_container import PipelineContainer

settings = get_settings()

class QuestionRecommendationDemo:
    """Demonstration of Question Recommendation System with practical examples"""
    
    def __init__(self):
        self.system = None
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
    
    async def initialize_system(self):
        """Initialize the question recommendation system"""
        print("🚀 Initializing Question Recommendation System...")
        
        # Get pipelines from pipeline container
        pipelines = {
            "retrieval": self.pipeline_container.get_pipeline("table_description"),
            "sql_pairs_retrieval": self.pipeline_container.get_pipeline("sql_pairs"),
            "instructions_retrieval": self.pipeline_container.get_pipeline("instructions"),
            "sql_generation_reasoning": self.pipeline_container.get_pipeline("sql_reasoning"),
            "sql_generation": self.pipeline_container.get_pipeline("sql_generation"),
            "question_recommendation": self.pipeline_container.get_pipeline("question_recommendation")
        }
        
        # Initialize question recommendation system
        self.system = QuestionRecommendation(pipelines=pipelines)
        
        print("✅ System initialized successfully!")
        print(f"📋 Schema Tables: {len(self.schema_context['schema'])}")
        print(f"📄 Schema Documents: {len(self.schema_documents)}")
    
    def _initialize_cache(self, event_id: str):
        """Initialize the cache with an Event object"""
        self.system[event_id] = Event(
            event_id=event_id,
            status="indexing",
            response={"questions": {}}
        )
    
    async def demo_question_recommendation(self):
        """Demonstrate question recommendation with different scenarios"""
        print("\n" + "=" * 80)
        print("🎯 QUESTION RECOMMENDATION DEMO")
        print("=" * 80)
        
        # Example 1: Basic recommendation
        print("\n--- Example 1: Basic Recommendation ---")
        event_id = "demo_1"
        self._initialize_cache(event_id)
        
        request = QuestionRecommendation.Request(
            event_id=event_id,
            mdl=json.dumps(self.schema_context),
            previous_questions=[],
            max_questions=5,
            max_categories=3,
            configuration=Configuration(),
            user_question="What are the top 5 customers by total spending in the last 3 months?"
        )
        
        print("Request: ", request)
        result = await self.system.recommend(request)
        self._display_recommendation_result(result)
        
        # Example 2: Recommendation with previous questions
        print("\n--- Example 2: With Previous Questions ---")
        event_id = "demo_2"
        self._initialize_cache(event_id)
        
        request = QuestionRecommendation.Request(
            event_id=event_id,
            mdl=json.dumps(self.schema_context),
            previous_questions=[
                "What are the top 5 customers by total spending?",
                "Show me monthly sales trends"
            ],
            max_questions=5,
            max_categories=3,
            configuration=Configuration(),
            user_question="What is the average order value by product category?"
        )
        
        result = await self.system.recommend(request)
        self._display_recommendation_result(result)
        
        # Example 3: Regeneration with specific categories
        print("\n--- Example 3: Regeneration with Categories ---")
        event_id = "demo_3"
        self._initialize_cache(event_id)
        
        request = QuestionRecommendation.Request(
            event_id=event_id,
            mdl=json.dumps(self.schema_context),
            previous_questions=[],
            max_questions=5,
            max_categories=3,
            regenerate=True,
            configuration=Configuration(),
            user_question="What is the customer retention rate over the last 6 months?"
        )
        
        result = await self.system.recommend(request)
        self._display_recommendation_result(result)
    
    def _display_recommendation_result(self, result):
        """Display recommendation results in a formatted way"""
        print(f"\nStatus: {result.status}")
        
        if result.error:
            print(f"Error: {result.error.code} - {result.error.message}")
            return
        
        if result.response and "questions" in result.response:
            questions = result.response["questions"]
            print("\nRecommended Questions by Category:")
            for category, category_questions in questions.items():
                print(f"\n📊 {category.upper()}")
                for i, q in enumerate(category_questions, 1):
                    print(f"{i}. Question: {q['question']}")
                    if 'sql' in q:
                        print(f"   SQL: {q['sql']}")
    
    async def run_complete_demo(self):
        """Run the complete demonstration"""
        await self.initialize_system()
        await self.demo_question_recommendation()

async def main():
    """Main entry point for the demo"""
    demo = QuestionRecommendationDemo()
    await demo.run_complete_demo()

if __name__ == "__main__":
    asyncio.run(main()) 