import asyncio
import logging
from typing import Dict, List, Optional, Union
import json

from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.sql.ask import AskService
from app.services.sql.question_recommendation import QuestionRecommendation
from app.services.sql.models import (
    AskRequest,
    AskResultResponse,
    Configuration,
    Event,
)
from app.agents.nodes.sql.utils.sql_prompts import Configuration as SQLConfiguration
from app.storage.documents import DocumentChromaStore, create_langchain_doc_util
from app.core.dependencies import get_doc_store_provider
from app.indexing.table_description import TableDescription
from app.indexing.db_schema import DBSchema
from app.core.provider import get_embedder

# Configure logging to reduce verbosity
logging.getLogger("app.storage.documents").setLevel(logging.WARNING)
logging.getLogger("agents.app.storage.documents").setLevel(logging.WARNING)

logger = logging.getLogger("lexy-ai-service")

class QuestionRecommendationDemo:
    _instance = None
    _initialized = False
    _schema_cache = {}  # Initialize schema cache as empty dict

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QuestionRecommendationDemo, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Initialize pipeline container
            self.pipeline_container = PipelineContainer.initialize()
            
            # Initialize services
            self.ask_service = AskService(
                pipeline_container=self.pipeline_container,
                allow_intent_classification=True,
                allow_sql_generation_reasoning=True,
                enable_enhanced_sql=True,
                sql_scoring_config_path="app/agents/nodes/sql/utils/scoring_config.json"
            )
            
            self.question_recommendation = QuestionRecommendation(
                pipelines=self.pipeline_container.get_all_pipelines()
            )
            
            self._initialized = True

    def _get_cached_schema(self, mdl: str) -> Optional[Dict]:
        """Get cached schema if available"""
        return self._schema_cache.get(mdl)

    def _cache_schema(self, mdl: str, schema: Dict):
        """Cache schema for future use"""
        self._schema_cache[mdl] = schema

    async def initialize(self):
        """Initialize the document store with sample data"""
        if not hasattr(self, '_doc_store_initialized'):
            await self._initialize_document_store()
            self._doc_store_initialized = True

    async def _initialize_document_store(self):
        """Initialize the document store with sample MDL data"""
        doc_store = get_doc_store_provider()
        
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
                            "name": "id",
                            "type": "integer",
                            "properties": {
                                "displayName": "ID",
                                "description": "Unique identifier for the product"
                            }
                        },
                        {
                            "name": "name",
                            "type": "string",
                            "properties": {
                                "displayName": "Name",
                                "description": "Product name"
                            }
                        },
                        {
                            "name": "price",
                            "type": "decimal",
                            "properties": {
                                "displayName": "Price",
                                "description": "Product price"
                            }
                        }
                    ],
                    "primaryKey": "id",
                    "properties": {
                        "displayName": "Products",
                        "description": "Product catalog"
                    }
                }
            ]
        }

        # Sample MDL data for sales table
        sales_mdl = {
            "catalog": "demo_catalog",
            "schema": "public",
            "models": [
                {
                    "name": "sales",
                    "tableReference": {
                        "table": "sampleSales"
                    },
                    "columns": [
                        {
                            "name": "id",
                            "type": "integer",
                            "properties": {
                                "displayName": "ID",
                                "description": "Unique identifier for the sale"
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
                                "description": "Number of units sold"
                            }
                        },
                        {
                            "name": "sale_date",
                            "type": "date",
                            "properties": {
                                "displayName": "Sale Date",
                                "description": "Date of the sale"
                            }
                        }
                    ],
                    "primaryKey": "id",
                    "properties": {
                        "displayName": "Sales",
                        "description": "Sales transaction records"
                    }
                }
            ]
        }
        
        schema_store = doc_store.get_store("db_schema")
        table_store = doc_store.get_store("table_description")
        embedder = get_embedder()
        
        # Use TableDescription to create standardized documents
        table_description = TableDescription(document_store=table_store, embedder=embedder)
        db_schema = DBSchema(document_store=schema_store, embedder=embedder)
        
        # Convert dicts to strings for run method
        products_mdl_str = json.dumps(products_mdl)
        sales_mdl_str = json.dumps(sales_mdl)

        # Store both tables
        #products_result = await table_description.run(mdl=products_mdl_str, project_id="demo_project")
        #sales_result = await table_description.run(mdl=sales_mdl_str, project_id="demo_project")
        #products_result = await db_schema.run(mdl_str=products_mdl_str, project_id="demo_project")
        #sales_result = await db_schema.run(mdl_str=sales_mdl_str, project_id="demo_project")
        #logger.info("Stored the products table in chroma", products_result)
        #logger.info("Stored the sales table in chroma", sales_result)

    async def process_user_question(
        self,
        user_question: str,
        mdl: str,
        project_id: str,
        event_id: str,
        configuration: Optional[SQLConfiguration] = None,
        use_schema_cache: bool = True  # Default to True
    ) -> Dict:
        """
        Process a user question and return both the answer and recommended follow-up questions.
        
        Args:
            user_question: The user's question
            mdl: The MDL string containing database schema
            project_id: The project ID
            event_id: Unique identifier for this interaction
            configuration: Optional configuration for SQL generation
            use_schema_cache: Whether to use schema caching (default: True)
            
        Returns:
            Dict containing the answer and recommended questions
        """
        try:
            # Create and convert configuration to dict
            config = configuration or SQLConfiguration(
                enable_scoring=True,
                quality_threshold=0.6,
                max_improvement_attempts=3
            )
            config_dict = config.dict()
            
            # Get cached schema if available and caching is enabled
            schema_context = {"mdl": mdl}
            if use_schema_cache:
                cached_schema = self._get_cached_schema(mdl)
                if cached_schema:
                    schema_context["cached_schema"] = cached_schema
            
            # Step 1: Process the user's question through Ask service
            ask_request = AskRequest(
                query_id=event_id,
                query=user_question,
                project_id=project_id,
                configurations=config_dict,
                histories=[],  # No history for this demo
                enable_scoring=True,  # Enable scoring for enhanced SQL
                schema_context=schema_context  # Add schema context for better scoring
            )
            
            # Get the answer
            ask_result = await self.ask_service.process_request(ask_request)
            
            # Cache the schema if caching is enabled and we have a new schema
            if use_schema_cache and "schema" in ask_result:
                self._cache_schema(mdl, ask_result["schema"])
            
            # Step 2: Generate question recommendations
            recommendation_request = QuestionRecommendation.Request(
                event_id=f"{event_id}_recommendations",
                mdl=mdl,
                user_question=user_question,
                project_id=project_id,
                configuration=config,
                max_questions=5,  # Get 5 questions per category
                max_categories=3,  # Get questions from 3 different categories
                regenerate=True  # Ensure we get enough questions
            )
            
            # Get recommendations
            recommendations = await self.question_recommendation.recommend(recommendation_request)
            
            # Combine results
            return {
                "answer": ask_result,
                "recommendations": recommendations,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error in demo: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

async def run_demo():
    """Run a demo of the question recommendation system with multiple test cases"""
    # Sample MDL (you would replace this with your actual MDL)
    sample_mdl = """
    {
        "models": [
            {
                "name": "sales",
                "columns": [
                    {"name": "id", "type": "integer"},
                    {"name": "product_id", "type": "integer"},
                    {"name": "quantity", "type": "integer"},
                    {"name": "sale_date", "type": "date"}
                ]
            },
            {
                "name": "products",
                "columns": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "price", "type": "decimal"}
                ]
            }
        ]
    }
    """
    
    # Initialize demo
    demo = QuestionRecommendationDemo()
    await demo.initialize()
    """
       ,
         {
            "question": "What are the top 5 products by sales volume?",
            "event_id": "demo_event_1"
        },
        {
            "question": "What is the average price of products sold in the last month?",
            "event_id": "demo_event_2"
        },
        {
            "question": "Which products have the highest profit margin?",
            "event_id": "demo_event_3"
        },
        {
            "question": "What is the total revenue by product category?",
            "event_id": "demo_event_4"
        },
        {
            "question": "What is the average completion time for different types of training over the last 6 months, and how many were completed late?",
            "event_id": "cornerstone_event_2"
        },
        # Employee Training Records test cases
        {
            "question": "What is the compliance rate across different organizations?",
            "event_id": "employee_event_1"
        },
        {
            "question": "how many training assignments are currently overdue",
            "event_id": "employee_event_2"
        },
        {
            "question": "How many training assignments are completed on time?",
            "event_id": "employee_event_3"
        },
        {
            "question": "Show me the certification completion rates by activity type, including how long it takes employees to complete their certifications on average",
            "event_id": "employee_event_4"
        }
        """
    # Test cases
    test_cases = [
        # Cornerstone Training Records test cases
        {
            #"question": "Show me the training completion rates by division, including how many assignments were completed on time versus late",
            #"question": "How many trainings are assigned vs completed across different Divisions (Administration, Acme Products, Private Operations)?",
            #"question": "What is the proportion of different Transcript Status (Assigned / Satisfied / Expired / Waived)?",
            #"question": "What are the proportions of different Transcript Status(Assigned / Satisfied / Expired / Waived) when compared to the total number of transcripts ?",
            #"question": "How many employees have completed the training on time or Late per Division?",
            #"question": "How has the number of completed trainings changed month by month? (using CompletionDate)",
            #"question": "How many training activities for each employee and give me their Training Statuses by Assigned, Completed, Expired",
            "question": "On average, how many days does it take from AssignmentDate to CompletionDate for each employee?",
            "event_id": "cornerstone_event_1"
        }
    ]
    
    # Process each test case
    for test_case in test_cases:
        print("\n" + "="*50)
        print(f"\nTest Case: {test_case['event_id']}")
        print(f"User Question: {test_case['question']}")
        
        # Process the question
        result = await demo.process_user_question(
            user_question=test_case['question'],
            mdl=sample_mdl,
            project_id="cornerstone",  # Here
            event_id=test_case['event_id'],
            configuration=SQLConfiguration(
                enable_scoring=True,
                quality_threshold=0.6,
                max_improvement_attempts=3
            )
        )
        
        # Print results
        if result["status"] == "success":
            print("\nAnswer:")
            if isinstance(result["answer"], dict):
                if "metadata" in result["answer"]:
                    if "error_type" in result["answer"]["metadata"]:
                        print(f"Error: {result['answer']['metadata'].get('error_message', 'Unknown error')}")
                    else:
                        print(result["answer"])
                        # Add scoring output
                        if "relevance_scoring" in result["answer"]:
                            scoring = result["answer"]["relevance_scoring"]
                            print("\nScoring Information:")
                            print(f"Final Score: {scoring.get('final_score', 'N/A')}")
                            print(f"Quality Level: {scoring.get('quality_level', 'N/A')}")
                            if scoring.get('improvement_recommendations'):
                                print("\nImprovement Recommendations:")
                                for rec in scoring['improvement_recommendations']:
                                    print(f"- {rec}")
                else:
                    print(result["answer"])
            else:
                print(result["answer"])
            
            print("\nRecommended Questions:")
            if isinstance(result["recommendations"], dict):
                recommendations = result["recommendations"]
                if "response" in recommendations:
                    response = recommendations["response"]
                    if isinstance(response, dict):
                        questions = response.get("questions", {})
                        categories = list(questions.keys())
                        reasoning = response.get("reasoning", "")

                        for category in categories:
                            print(f"\n{category}:")
                            if category in questions:
                                for q in questions[category]:
                                    print(f"- {q}")
                        
                        if reasoning:
                            print(f"\nReasoning: {reasoning}")
                    else:
                        print(response)
                else:
                    print(result["recommendations"])
            else:
                print(result["recommendations"])
        else:
            print(f"\nError: {result['error']}")
        
        print("\n" + "="*50)

if __name__ == "__main__":
    # Run the demo
    asyncio.run(run_demo()) 