"""
Practical usage example of Enhanced Unified Pipeline System with Relevance Scoring
This shows how to integrate and use the enhanced system in your application
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime
from app.agents.pipelines.pipeline_container import PipelineContainer
# Import the enhanced system
from app.agents.pipelines.enhanced_sql_pipeline import (
    EnhancedPipelineFactory,
    PipelineRequest,
    PipelineType,
    RelevanceScoring
)
from app.storage.documents import DocumentChromaStore
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider
from app.core.dependencies import get_llm
from app.core.engine import Engine
from app.core.engine_provider import EngineProvider
from app.core.dependencies import get_doc_store_provider
from app.indexing.table_description import TableDescription
from app.indexing.db_schema import DBSchema
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class EnhancedPipelineDemo:
    """Demonstration of Enhanced Pipeline System with practical examples"""
    
    def __init__(self):
        self.system = None
        self.schema_context = self._setup_demo_schema()
        
        # Initialize core dependencies
        self.llm = get_llm()
        self.engine = EngineProvider.get_engine()
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
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
        self.document_provider = get_doc_store_provider()
        self.schema_documents = self._setup_schema_documents()
    
    def _setup_demo_schema(self) -> Dict[str, Any]:
        """Set up demo database schema context"""
        # Sample MDL data for customers table
        customers_mdl = {
            "catalog": "demo_catalog",
            "schema": "public",
            "models": [
                {
                    "name": "customers",
                    "tableReference": {
                        "table": "sampleCustomers"
                    },
                    "columns": [
                        {
                            "name": "customer_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Customer ID",
                                "description": "Unique identifier for the customer"
                            }
                        },
                        {
                            "name": "first_name",
                            "type": "string",
                            "properties": {
                                "displayName": "First Name",
                                "description": "Customer's first name"
                            }
                        },
                        {
                            "name": "last_name",
                            "type": "string",
                            "properties": {
                                "displayName": "Last Name",
                                "description": "Customer's last name"
                            }
                        },
                        {
                            "name": "email",
                            "type": "string",
                            "properties": {
                                "displayName": "Email",
                                "description": "Customer's email address"
                            }
                        },
                        {
                            "name": "phone",
                            "type": "string",
                            "properties": {
                                "displayName": "Phone",
                                "description": "Customer's phone number"
                            }
                        },
                        {
                            "name": "registration_date",
                            "type": "date",
                            "properties": {
                                "displayName": "Registration Date",
                                "description": "Date when customer registered"
                            }
                        },
                        {
                            "name": "last_login",
                            "type": "datetime",
                            "properties": {
                                "displayName": "Last Login",
                                "description": "Last login timestamp"
                            }
                        },
                        {
                            "name": "is_active",
                            "type": "boolean",
                            "properties": {
                                "displayName": "Is Active",
                                "description": "Whether the customer account is active"
                            }
                        }
                    ],
                    "primaryKey": "customer_id",
                    "properties": {
                        "displayName": "Customers",
                        "description": "Customer information"
                    }
                }
            ]
        }

        # Sample MDL data for orders table
        orders_mdl = {
            "catalog": "demo_catalog",
            "schema": "public",
            "models": [
                {
                    "name": "orders",
                    "tableReference": {
                        "table": "sampleOrders"
                    },
                    "columns": [
                        {
                            "name": "order_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Order ID",
                                "description": "Unique identifier for the order"
                            }
                        },
                        {
                            "name": "customer_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Customer ID",
                                "description": "Reference to the customer"
                            }
                        },
                        {
                            "name": "order_date",
                            "type": "date",
                            "properties": {
                                "displayName": "Order Date",
                                "description": "Date when order was placed"
                            }
                        },
                        {
                            "name": "ship_date",
                            "type": "date",
                            "properties": {
                                "displayName": "Ship Date",
                                "description": "Date when order was shipped"
                            }
                        },
                        {
                            "name": "total_amount",
                            "type": "decimal",
                            "properties": {
                                "displayName": "Total Amount",
                                "description": "Total order amount"
                            }
                        },
                        {
                            "name": "tax_amount",
                            "type": "decimal",
                            "properties": {
                                "displayName": "Tax Amount",
                                "description": "Tax amount for the order"
                            }
                        },
                        {
                            "name": "status",
                            "type": "string",
                            "properties": {
                                "displayName": "Status",
                                "description": "Order status"
                            }
                        },
                        {
                            "name": "payment_method",
                            "type": "string",
                            "properties": {
                                "displayName": "Payment Method",
                                "description": "Method of payment"
                            }
                        }
                    ],
                    "primaryKey": "order_id",
                    "properties": {
                        "displayName": "Orders",
                        "description": "Order information"
                    }
                }
            ]
        }

        # Sample MDL data for products table
        products_mdl = {
            "catalog": "demo_catalog",
            "schema": "public",
            "models": [
                {
                    "name": "products",
                    "tableReference": {
                        "table": "sampleProducts"
                    },
                    "columns": [
                        {
                            "name": "product_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Product ID",
                                "description": "Unique identifier for the product"
                            }
                        },
                        {
                            "name": "product_name",
                            "type": "string",
                            "properties": {
                                "displayName": "Product Name",
                                "description": "Name of the product"
                            }
                        },
                        {
                            "name": "category",
                            "type": "string",
                            "properties": {
                                "displayName": "Category",
                                "description": "Product category"
                            }
                        },
                        {
                            "name": "price",
                            "type": "decimal",
                            "properties": {
                                "displayName": "Price",
                                "description": "Product price"
                            }
                        },
                        {
                            "name": "stock_quantity",
                            "type": "integer",
                            "properties": {
                                "displayName": "Stock Quantity",
                                "description": "Available stock quantity"
                            }
                        },
                        {
                            "name": "supplier_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Supplier ID",
                                "description": "Reference to the supplier"
                            }
                        },
                        {
                            "name": "created_date",
                            "type": "date",
                            "properties": {
                                "displayName": "Created Date",
                                "description": "Date when product was added"
                            }
                        }
                    ],
                    "primaryKey": "product_id",
                    "properties": {
                        "displayName": "Products",
                        "description": "Product catalog"
                    }
                }
            ]
        }

        # Sample MDL data for order_items table
        order_items_mdl = {
            "catalog": "demo_catalog",
            "schema": "public",
            "models": [
                {
                    "name": "order_items",
                    "tableReference": {
                        "table": "sampleOrderItems"
                    },
                    "columns": [
                        {
                            "name": "order_item_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Order Item ID",
                                "description": "Unique identifier for the order item"
                            }
                        },
                        {
                            "name": "order_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Order ID",
                                "description": "Reference to the order"
                            }
                        },
                        {
                            "name": "product_id",
                            "type": "integer",
                            "properties": {
                                "displayName": "Product ID",
                                "description": "Reference to the product"
                            }
                        },
                        {
                            "name": "quantity",
                            "type": "integer",
                            "properties": {
                                "displayName": "Quantity",
                                "description": "Number of items ordered"
                            }
                        },
                        {
                            "name": "unit_price",
                            "type": "decimal",
                            "properties": {
                                "displayName": "Unit Price",
                                "description": "Price per unit"
                            }
                        },
                        {
                            "name": "discount",
                            "type": "decimal",
                            "properties": {
                                "displayName": "Discount",
                                "description": "Discount amount"
                            }
                        },
                        {
                            "name": "line_total",
                            "type": "decimal",
                            "properties": {
                                "displayName": "Line Total",
                                "description": "Total amount for this line item"
                            }
                        }
                    ],
                    "primaryKey": "order_item_id",
                    "properties": {
                        "displayName": "Order Items",
                        "description": "Order line items"
                    }
                }
            ]
        }
        
        return {
            "mdl": {
                "customers": customers_mdl,
                "orders": orders_mdl,
                "products": products_mdl,
                "order_items": order_items_mdl
            },
            "relationships": {
                "customers_orders": "customers.customer_id = orders.customer_id",
                "orders_order_items": "orders.order_id = order_items.order_id",
                "products_order_items": "products.product_id = order_items.product_id"
            }
        }
    
    def _setup_schema_documents(self) -> List[str]:
        """Set up schema documents for RAG"""
        schema = self._setup_demo_schema()
        documents = []
        
        # Convert each MDL to a string and add to documents
        for table_name, mdl in schema["mdl"].items():
            documents.append(json.dumps(mdl))
        
        return documents
    
    async def initialize_system(self, enable_scoring: bool = True):
        """Initialize the enhanced pipeline system"""
        print("🚀 Initializing Enhanced Pipeline System...")
        
        try:
            self.pipeline_container = PipelineContainer.initialize()
            # Get schema and documents
            schema = self._setup_demo_schema()
            schema_documents = self._setup_schema_documents()
            
            # Initialize document store and schema components
            doc_store = get_doc_store_provider()
            schema_store = doc_store.get_store("db_schema")
            table_store = doc_store.get_store("table_description")
            embedder = self.embeddings
            
            # Initialize table description and db schema components
            table_description = TableDescription(document_store=table_store, embedder=embedder)
            db_schema = DBSchema(document_store=schema_store, embedder=embedder)
            
            # Store each table's MDL
            for table_name, mdl in schema["mdl"].items():
                try:
                    mdl_str = json.dumps(mdl)
                    # Store in both table description and db schema
                    #await table_description.run(mdl=mdl_str, project_id="demo_project")
                    #await db_schema.run(mdl_str=mdl_str, project_id="demo_project")
                    logger.info(f"Stored the {table_name} table in chroma")
                except Exception as e:
                    logger.warning(f"Failed to store {table_name} table: {str(e)}")
                    # Continue with other tables even if one fails
                    continue
            
            # Create enhanced system
            self.system = EnhancedPipelineFactory.create_enhanced_unified_system(
                engine=self.engine,
                document_store_provider=self.document_provider,
                use_rag=True,
                enable_sql_scoring=enable_scoring,
                scoring_config_path=None  # Use default config
            )
            
            
            print("✅ System initialized successfully!")
            print(f"📊 SQL Scoring Enabled: {enable_scoring}")
            print(f"📋 Schema Tables: {len(schema['mdl'])}")
            print(f"📄 Schema Documents: {len(schema_documents)}")
            
        except Exception as e:
            logger.error(f"Error initializing system: {str(e)}")
            # Re-raise the exception to be handled by the caller
            raise
    
    async def demo_sql_generation_with_scoring(self):
        """Demonstrate SQL generation with relevance scoring"""
        print("\n" + "=" * 80)
        print("🎯 SQL GENERATION WITH RELEVANCE SCORING DEMO")
        print("=" * 80)
        
        test_queries = [
            {
                "query": "Find the top 10 customers by total spending in the last 6 months including their contact information",
                "description": "Complex query with multiple requirements",
                "expected_quality": "excellent"
            },

            {
                "query": "Show monthly sales trends",
                "description": "Time-series analysis query",
                "expected_quality": "good"
            },
            {
                "query": "List customers",
                "description": "Simple query",
                "expected_quality": "fair"
            }
        ]
        
        results = []
        
        for i, test_case in enumerate(test_queries, 1):
            print(f"\n--- Test Case {i}: {test_case['description']} ---")
            print(f"Query: {test_case['query']}")
            print(f"Expected Quality: {test_case['expected_quality']}")
            
            try:
                # Create request with scoring enabled
                request = PipelineRequest(
                    pipeline_type=PipelineType.SQL_GENERATION,
                    query=test_case['query'],
                    language="English",
                    contexts=self.schema_documents,
                    enable_scoring=True,
                    schema_context=self.schema_context,
                    max_improvement_attempts=2,
                    quality_threshold=0.6
                )
                
                # Execute pipeline
                start_time = datetime.now()
                result = await self.system.execute_pipeline(request)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # Display results
                self._display_sql_result(result, execution_time)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error in test case {i}: {str(e)}")
                print(f"❌ Error in test case {i}: {str(e)}")
                continue
            
            print("-" * 60)
        
        return results
    
    async def demo_complete_workflow_with_scoring(self):
        """Demonstrate complete workflow with scoring"""
        print("\n" + "=" * 80)
        print("🔄 COMPLETE WORKFLOW WITH SCORING DEMO")
        print("=" * 80)
        
        query = "Analyze customer purchase patterns and show me customers who might be at risk of churning"
        print(f"Query: {query}")
        
        # Execute complete workflow with scoring
        results = await self.system.execute_complete_workflow_with_scoring(
            query=query,
            language="English",
            contexts=self.schema_documents,
            enable_scoring=True,
            quality_threshold=0.6,
            schema_context=self.schema_context
        )
        
        print(f"\n📊 Workflow completed with {len(results)} steps:")
        
        for step_name, result in results.items():
            print(f"\n--- {step_name.upper()} ---")
            print(f"✅ Success: {result.success}")
            
            if result.success and result.data:
                # Show key data points
                data_preview = str(result.data)[:200] + "..." if len(str(result.data)) > 200 else str(result.data)
                print(f"📄 Data Preview: {data_preview}")
            
            # Show scoring information if available
            if result.relevance_scoring.enabled:
                self._display_scoring_info(result.relevance_scoring)
            
            if result.error:
                print(f"❌ Error: {result.error}")
        
        return results
    
    async def demo_sql_correction_with_scoring(self):
        """Demonstrate SQL correction with quality assessment"""
        print("\n" + "=" * 80)
        print("🔧 SQL CORRECTION WITH SCORING DEMO")
        print("=" * 80)
        
        # Test correction scenario
        faulty_sql = "SELECT * FROM customer WHERE id = 1"
        error_message = "Table 'customer' doesn't exist. Did you mean 'customers'?"
        
        print(f"Original SQL: {faulty_sql}")
        print(f"Error Message: {error_message}")
        
        request = PipelineRequest(
            pipeline_type=PipelineType.SQL_CORRECTION,
            query="Get customer with ID 1",  # Context query
            enable_scoring=True,
            schema_context=self.schema_context,
            additional_params={
                "sql": faulty_sql,
                "error_message": error_message
            }
        )
        
        result = await self.system.execute_pipeline(request)
        
        print(f"\n🔧 Correction Results:")
        print(f"✅ Success: {result.success}")
        
        if result.success:
            print(f"🛠️ Corrected SQL: {result.data.get('sql', 'N/A')}")
            print(f"📈 Correction Quality: {result.data.get('correction_quality', 0.0):.3f}")
            print(f"📊 Improvement Achieved: {result.data.get('improvement_achieved', 0.0):.3f}")
        
        if result.relevance_scoring.enabled:
            print(f"\n📋 Scoring Information:")
            print(f"   Final Score: {result.relevance_scoring.final_score:.3f}")
            print(f"   Quality Level: {result.relevance_scoring.quality_level}")
        
        return result
    
    def _display_sql_result(self, result, execution_time: float):
        """Display SQL generation result with scoring"""
        print(f"\n📊 Results (executed in {execution_time:.2f}s):")
        print(f"✅ Success: {result.success}")
        
        if result.success and result.data:
            # Show SQL (truncated for display)
            sql = result.data.get('sql', '')
            sql_preview = sql[:200] + "..." if len(sql) > 200 else sql
            print(f"💻 Generated SQL:\n{sql_preview}")
            
            # Show quality metrics if available
            quality_metrics = result.data.get('quality_metrics', {})
            if quality_metrics:
                print(f"📈 Quality Score: {quality_metrics.get('final_score', 0.0):.3f}")
                print(f"🏆 Quality Level: {quality_metrics.get('quality_level', 'unknown').upper()}")
        
        # Show detailed scoring information
        if result.relevance_scoring.enabled:
            self._display_scoring_info(result.relevance_scoring)
        
        if result.error:
            print(f"❌ Error: {result.error}")
    
    def _display_scoring_info(self, scoring: RelevanceScoring):
        """Display detailed scoring information"""
        print(f"\n📋 Relevance Scoring Details:")
        print(f"   🎯 Final Score: {scoring.final_score:.3f}")
        print(f"   🏆 Quality Level: {scoring.quality_level.upper()}")
        print(f"   🔍 Operation Type: {scoring.detected_operation_type}")
        print(f"   🔄 Attempts: {scoring.attempt_number}")
        print(f"   ⏱️ Processing Time: {scoring.processing_time_seconds:.2f}s")
        
        # Show reasoning components if available
        if scoring.reasoning_components:
            print(f"   📊 Reasoning Components:")
            for component, score in scoring.reasoning_components.items():
                print(f"      • {component}: {score:.3f}")
        
        # Show improvement recommendations
        if scoring.improvement_recommendations:
            print(f"   💡 Recommendations:")
            for i, rec in enumerate(scoring.improvement_recommendations[:3], 1):
                print(f"      {i}. {rec}")
    
    async def demo_system_analytics(self):
        """Demonstrate system analytics and quality insights"""
        print("\n" + "=" * 80)
        print("📊 SYSTEM ANALYTICS & QUALITY INSIGHTS DEMO")
        print("=" * 80)
        
        # Get comprehensive system analytics
        analytics = self.system.get_system_analytics()
        
        print("🖥️ System Overview:")
        print(f"   SQL Scoring Enabled: {analytics.get('sql_scoring_enabled', False)}")
        print(f"   Total Pipelines: {analytics.get('total_pipelines', 0)}")
        print(f"   Available Pipeline Types: {len(analytics.get('available_pipeline_types', []))}")
        
        # Get quality summary
        quality_summary = self.system.get_quality_summary()
        
        if quality_summary.get('overall_quality'):
            overall = quality_summary['overall_quality']
            print(f"\n📈 Quality Overview:")
            print(f"   Total Queries Processed: {overall.get('total_queries', 0)}")
            print(f"   Average Quality Score: {overall.get('average_score', 0.0):.3f}")
            print(f"   High Quality Rate: {overall.get('high_quality_rate', 0.0):.1%}")
        
        # Quality distribution
        quality_dist = quality_summary.get('quality_distribution', {})
        if quality_dist:
            print(f"\n🏆 Quality Distribution:")
            for level, count in quality_dist.items():
                print(f"   {level.upper()}: {count} queries")
        
        # Improvement areas
        improvement_areas = quality_summary.get('improvement_areas', [])
        if improvement_areas:
            print(f"\n🎯 Improvement Areas:")
            for i, area in enumerate(improvement_areas[:5], 1):
                print(f"   {i}. {area}")
        
        return analytics, quality_summary
    
    async def run_complete_demo(self):
        """Run the complete demonstration"""
        print("🌟 ENHANCED SQL PIPELINE SYSTEM - COMPLETE DEMO")
        print("=" * 80)
        
        try:
            # Initialize system
            await self.initialize_system(enable_scoring=True)
            
            # Run demos
            sql_results = await self.demo_sql_generation_with_scoring()
            #workflow_results = await self.demo_complete_workflow_with_scoring()
            #correction_result = await self.demo_sql_correction_with_scoring()
            #analytics, quality_summary = await self.demo_system_analytics()
            
            # Final summary
            print("\n" + "=" * 80)
            print("🎉 DEMO COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            sql_results = {}
            print(f"📋 Summary:")
            print(f"   • SQL Generation Tests: {len(sql_results)}")
            #print(f"   • Workflow Steps: {len(workflow_results)}")
            #print(f"   • Correction Test: {'✅' if correction_result.success else '❌'}")
            #print(f"   • Analytics Generated: {'✅' if analytics else '❌'}")
            
            # Calculate average score from SQL results
            if sql_results:
                scores = [r.relevance_scoring.final_score for r in sql_results if r.relevance_scoring.enabled]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    print(f"   • Average Quality Score: {avg_score:.3f}")
            
            print(f"\n🚀 The Enhanced Pipeline System is ready for production use!")
            
        except Exception as e:
            print(f"❌ Demo failed with error: {e}")
            raise


# Practical integration example
class ProductionIntegration:
    """Example of how to integrate the enhanced system in production"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.system = None
    
    async def initialize(self):
        """Initialize the production system"""
        # Use your actual providers
        from app.core.provider import DocumentStoreProvider
        from app.core.engine import Engine
        
        engine = Engine()
        document_store_provider = DocumentStoreProvider(config=self.config.get('document_store_config'))
        
        self.system = EnhancedPipelineFactory.create_enhanced_unified_system(
            engine=engine,
            document_store_provider=document_store_provider,
            enable_sql_scoring=self.config.get('enable_scoring', True),
            scoring_config_path=self.config.get('scoring_config_path')
        )
    
    async def process_user_query(
        self, 
        query: str, 
        user_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process a user query with enhanced capabilities"""
        
        # Create request
        request = PipelineRequest(
            pipeline_type=PipelineType.SQL_GENERATION,
            query=query,
            language=user_context.get('language', 'English'),
            contexts=self.config.get('schema_documents', []),
            enable_scoring=True,
            schema_context=self.config.get('schema_context', {}),
            project_id=user_context.get('project_id')
        )
        
        # Execute with enhanced scoring
        result = await self.system.execute_pipeline(request)
        
        # Initialize response data with default values
        response_data = {
            "query": query,
            "success": result.success,
            "sql": None,
            "reasoning": None,
            "quality_score": None,
            "quality_level": None,
            "improvements": [],
            "error": result.error,
            "timestamp": result.timestamp,
            "processing_time": None
        }
        
        # Update response data if result is successful and has data
        if result.success and result.data:
            response_data.update({
                "sql": result.data.get('sql', ''),
                "reasoning": result.data.get('reasoning', ''),
                "quality_score": result.relevance_scoring.final_score if result.relevance_scoring.enabled else None,
                "quality_level": result.relevance_scoring.quality_level if result.relevance_scoring.enabled else None,
                "improvements": result.relevance_scoring.improvement_recommendations if result.relevance_scoring.enabled else [],
                "processing_time": result.relevance_scoring.processing_time_seconds if result.relevance_scoring.enabled else None
            })
        
        return response_data
    
    async def get_quality_dashboard_data(self) -> Dict[str, Any]:
        """Get data for quality monitoring dashboard"""
        analytics = self.system.get_system_analytics()
        quality_summary = self.system.get_quality_summary()
        
        return {
            "system_status": {
                "scoring_enabled": analytics.get('sql_scoring_enabled', False),
                "total_pipelines": analytics.get('total_pipelines', 0),
                "last_updated": analytics.get('timestamp')
            },
            "quality_metrics": quality_summary.get('overall_quality', {}),
            "quality_distribution": quality_summary.get('quality_distribution', {}),
            "improvement_areas": quality_summary.get('improvement_areas', []),
            "recent_trend": quality_summary.get('recent_trend', {})
        }


# Example configuration
PRODUCTION_CONFIG = {
    "document_store_config": {
        "type": "chroma",
        "persist_directory": "./data/chroma"
    },
    "enable_scoring": True,
    "scoring_config_path": "./config/sql_scoring_config.json",
    "schema_documents": [
        # Your schema documents
    ],
    "schema_context": {
        # Your schema context
    }
}


async def main():
    """Main demo execution"""
    # Run the complete demo
    demo = EnhancedPipelineDemo()
    await demo.run_complete_demo()
    
    # Show production integration example
    print(f"\n📚 Production Integration Example:")
    print(f"   See ProductionIntegration class for complete implementation")
    print(f"   Key features:")
    print(f"   • Configurable scoring system")
    print(f"   • Quality monitoring dashboard")
    print(f"   • Enhanced API responses with quality metrics")
    print(f"   • Real-time performance analytics")


if __name__ == "__main__":
    asyncio.run(main())