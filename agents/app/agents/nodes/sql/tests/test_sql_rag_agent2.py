import logging
import chromadb
from langchain_openai import OpenAIEmbeddings
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from langchain_openai import ChatOpenAI
from app.core.pandas_engine import PandasEngine
from app.agents.nodes.sql.sql_rag_agent import create_sql_rag_agent
from app.agents.nodes.sql.sql_rag_agent import generate_sql_with_rag
from app.agents.nodes.sql.sql_rag_agent import breakdown_sql_with_rag
from app.agents.nodes.sql.utils.sql_prompts import Configuration
from app.core.provider import DocumentStoreProvider
from app.agents.nodes.sql.relationship_recommendation import RelationshipRecommendation
from app.agents.nodes.sql.question_recommendation import QuestionRecommendation
from app.agents.nodes.sql.intent_classification import IntentClassification
import orjson
import asyncio
import pandas as pd
from typing import Optional, Dict, Any
import uuid

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()


class SQLRAGTest:
    def __init__(self):
        """Initialize the SQL RAG test with all necessary components."""
        print("settings: ", settings.OPENAI_API_KEY)
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
        self.document_provider = DocumentStoreProvider(stores=self.document_stores)
        
        # Initialize recommendation services
        self.relationship_service = RelationshipRecommendation(
            doc_store_provider=self.document_provider,
            maxsize=1000,
            ttl=300
        )
        
        self.question_service = QuestionRecommendation(
            doc_store_provider=self.document_provider,
        
        )
        
        # Initialize intent classification service
        self.intent_service = IntentClassification(
            doc_store_provider=self.document_provider
        )

    def create_sample_mdl(self) -> str:
        """Create a sample MDL (Model Definition Language) for testing."""
        sample_mdl = {
            "models": [
                {
                    "name": "employees",
                    "columns": [
                        {"name": "employee_id", "type": "integer", "description": "Unique identifier for employee"},
                        {"name": "name", "type": "string", "description": "Employee full name"},
                        {"name": "department_id", "type": "integer", "description": "Foreign key to departments table"},
                        {"name": "department", "type": "string", "description": "Department name"},
                        {"name": "hire_date", "type": "date", "description": "Date when employee was hired"},
                        {"name": "salary", "type": "decimal", "description": "Employee annual salary"},
                        {"name": "manager_id", "type": "integer", "description": "Employee ID of the manager"},
                        {"name": "last_training_date", "type": "date", "description": "Date of last training completion"},
                        {"name": "required_training_date", "type": "date", "description": "Required training completion date"},
                        {"name": "is_active", "type": "boolean", "description": "Whether employee is currently active"}
                    ],
                    "primary_key": ["employee_id"],
                    "description": "Employee information and training status"
                },
                {
                    "name": "departments",
                    "columns": [
                        {"name": "department_id", "type": "integer", "description": "Unique identifier for department"},
                        {"name": "department_name", "type": "string", "description": "Department name"},
                        {"name": "manager_id", "type": "integer", "description": "Employee ID of department manager"},
                        {"name": "budget", "type": "decimal", "description": "Department annual budget"},
                        {"name": "location", "type": "string", "description": "Department office location"}
                    ],
                    "primary_key": ["department_id"],
                    "description": "Department information and budget details"
                },
                {
                    "name": "training_records",
                    "columns": [
                        {"name": "training_id", "type": "integer", "description": "Unique identifier for training record"},
                        {"name": "employee_id", "type": "integer", "description": "Foreign key to employees table"},
                        {"name": "training_type", "type": "string", "description": "Type of training completed"},
                        {"name": "completion_date", "type": "date", "description": "Date training was completed"},
                        {"name": "score", "type": "integer", "description": "Training completion score (0-100)"},
                        {"name": "is_mandatory", "type": "boolean", "description": "Whether training is mandatory"},
                        {"name": "instructor", "type": "string", "description": "Training instructor name"}
                    ],
                    "primary_key": ["training_id"],
                    "description": "Individual training completion records"
                },
                {
                    "name": "overdue_analysis",
                    "columns": [
                        {"name": "employee_id", "type": "integer", "description": "Foreign key to employees table"},
                        {"name": "days_overdue", "type": "integer", "description": "Number of days overdue for training"},
                        {"name": "is_overdue", "type": "boolean", "description": "Whether employee is overdue for training"},
                        {"name": "risk_level", "type": "string", "description": "Risk level: Low, Medium, High"}
                    ],
                    "description": "Analysis of training compliance and overdue status"
                }
            ],
            "relationships": [
                {
                    "source": "employees",
                    "target": "departments",
                    "type": "Many-to-One",
                    "join_condition": "employees.department_id = departments.department_id"
                }
            ],
            "metadata": {
                "version": "1.0",
                "description": "Employee training management system data model",
                "last_updated": "2024-01-15"
            }
        }
        
        # Convert to JSON string and ensure it's properly formatted
        return orjson.dumps(sample_mdl).decode('utf-8')

    async def test_relationship_recommendation(self):
        """Test the relationship recommendation service."""
        try:
            logger.info("Testing Relationship Recommendation Service")
            
            # Create test input
            test_id = str(uuid.uuid4())
            mdl = self.create_sample_mdl()
            
            # Create recommendation request
            request = RelationshipRecommendation.Input(
                id=test_id,
                mdl=mdl,
                project_id="test_project"
            )
            
            # Generate relationship recommendations
            logger.info("Generating relationship recommendations...")
            result = await self.relationship_service.recommend(
                request, 
                trace_id=f"relationship_test_{test_id}"
            )
            
            # Wait for completion if still generating
            max_retries = 10
            retry_count = 0
            while result.status == "generating" and retry_count < max_retries:
                await asyncio.sleep(1)
                result = self.relationship_service[test_id]
                retry_count += 1
            
            # Log results
            logger.info(f"Relationship Recommendation Status: {result.status}")
            if result.status == "finished":
                logger.info("Relationship Recommendations:")
                logger.info(orjson.dumps(result.response, option=orjson.OPT_INDENT_2).decode())
                print("\n=== RELATIONSHIP RECOMMENDATIONS ===")
                print(orjson.dumps(result.response, option=orjson.OPT_INDENT_2).decode())
                
                # Validate the response structure
                if result.response and "relationships" in result.response:
                    relationships = result.response["relationships"]
                    logger.info(f"Generated {len(relationships)} relationship recommendations")
                    for i, rel in enumerate(relationships):
                        logger.info(f"Relationship {i+1}: {rel.get('source')} -> {rel.get('target')} ({rel.get('type')})")
                else:
                    logger.warning("No relationships found in response")
                    
            elif result.status == "failed":
                logger.error(f"Relationship recommendation failed: {result.error}")
                
            return result
            
        except Exception as e:
            logger.error(f"Error in relationship recommendation test: {str(e)}")
            raise

    async def test_question_recommendation(self):
        """Test the question recommendation service."""
        try:
            logger.info("Testing Question Recommendation Service")
            
            # Create test input
            mdl = self.create_sample_mdl()
            
            # Define test categories
            categories = [
                "Training Compliance",
                "Department Analysis", 
                "Employee Performance",
                "Data Quality"
            ]
            
            # Previous questions to simulate context
            previous_questions = [
                "How many employees are overdue for training?",
                "Which department has the highest training completion rate?"
            ]
            
            # Generate question recommendations
            logger.info("Generating question recommendations...")
            result = await self.question_service.run(
                user_question="What are some interesting questions I can ask about this data?",
                mdl=mdl,
                previous_questions=previous_questions,
                categories=categories,
                language="English",
                max_questions=4,
                max_categories=3
            )
            
            # Log results
            logger.info(f"Question Recommendation Status: {result.get('status')}")
            if result.get('status') == "success":
                logger.info("Question Recommendations:")
                logger.info(result.get('response', {}).get('content', ''))
                print("\n=== QUESTION RECOMMENDATIONS ===")
                print(result.get('response', {}).get('content', ''))
                
                # Validate the response structure
                if result.get('response') and 'content' in result['response']:
                    content = result['response']['content']
                    logger.info(f"Generated recommendations in markdown format")
                    
                    # Count questions by category
                    categories = {}
                    current_category = None
                    
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.startswith('###'):
                            current_category = line.replace('###', '').strip()
                            if current_category not in categories:
                                categories[current_category] = 0
                        elif line and line[0].isdigit() and '. ' in line:
                            if current_category:
                                categories[current_category] += 1
                    
                    # Log category statistics
                    for category, count in categories.items():
                        logger.info(f"\n{category}: {count} questions")
                else:
                    logger.warning("No content found in response")
                    
            elif result.get('status') == "failed":
                logger.error(f"Question recommendation failed: {result.get('error')}")
            print("Question recommendation result: ", result)
            return result
            
        except Exception as e:
            logger.error(f"Error in question recommendation test: {str(e)}")
            raise

    async def test_sql_rag_agent_with_chroma(self):
        """Test SQL RAG agent with ChromaDB vectors"""
        try:
            # Create sample data for testing
            employees_df = pd.DataFrame({
                'employee_id': [1, 2, 3, 4, 5],
                'name': ['John', 'Jane', 'Bob', 'Alice', 'Charlie'],
                'department': ['IT', 'HR', 'Finance', 'IT', 'HR'],
                'last_training_date': pd.to_datetime(['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01']),
                'required_training_date': pd.to_datetime(['2023-01-15', '2023-02-15', '2023-03-15', '2023-04-15', '2023-05-15']),
                'days_overdue': [15, 14, 16, 14, 15],
                'is_overdue': [True, True, True, True, True]
            })
            
            # Create overdue analysis view
            overdue_df = employees_df[['employee_id', 'days_overdue', 'is_overdue']].copy()
            
            # Create agent
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
            engine = PandasEngine(data_sources={
                'employees': employees_df,
                'overdue_analysis': overdue_df
            })
            agent = create_sql_rag_agent(llm=llm, engine=engine, document_store_provider=self.document_provider)
            
            # Initialize vectorstores with existing Chroma data
            logger.info("Initializing vectorstores with existing Chroma data")
            
            # Test query for semantic search
            test_query = "What is the average days over due for training of employees in the last 3 months by department? "
            
            # Get schema documents using semantic search
            schema_results = self.document_stores["db_schema"].semantic_search(
                query=test_query,
                k=5  # Get top 5 most relevant schema documents
            )
           
            # Get SQL pairs using semantic search
            sql_pair_results = self.document_stores["sql_pairs"].semantic_search(
                query=test_query,
                k=5  # Get top 5 most relevant SQL pairs
            )
            sample_data = []
            for result in sql_pair_results:
                try:
                    sample_data.append(orjson.loads(result["content"]))
                except:
                    sample_data.append({"question": result["content"], "sql": ""})
           
            # Test SQL generation with the query
            logger.info(f"Testing SQL generation with query: {test_query}")
            
            result = await generate_sql_with_rag(
                agent,
                test_query,
                language="English"
            )
            
            logger.info("SQL Generation Result:")
            logger.info(result)
            print("\n=== SQL GENERATION RESULT ===")
            print(result)
            
            # Test SQL breakdown if generation was successful
            if result.get("valid_generation_results") and len(result["valid_generation_results"]) > 0:
                sql = result["valid_generation_results"][0]["sql"]
                breakdown_result = await breakdown_sql_with_rag(
                    agent,
                    test_query,
                    sql,
                    language="English"
                )
                
                logger.info("\nSQL Breakdown Result:")
                logger.info(orjson.dumps(breakdown_result, option=orjson.OPT_INDENT_2).decode())
                print("\n=== SQL BREAKDOWN RESULT ===")
                print(orjson.dumps(breakdown_result, option=orjson.OPT_INDENT_2).decode())
            
            return result
            
        except Exception as e:
            logger.error(f"Error in test: {str(e)}")
            raise

    async def test_intent_classification(self):
        """Test the intent classification service."""
        try:
            logger.info("Testing Intent Classification Service")
            
            # Test cases with different types of queries
            test_queries = [
                {
                    "query": "What is the average salary by department?",
                    "expected_intent": "TEXT_TO_SQL"
                },
                {
                    "query": "How can I use this dataset?",
                    "expected_intent": "GENERAL"
                },
                {
                    "query": "What can Wren AI do?",
                    "expected_intent": "USER_GUIDE"
                },
                {
                    "query": "Tell me a joke",
                    "expected_intent": "MISLEADING_QUERY"
                }
            ]
            
            results = []
            for test_case in test_queries:
                print("test_case: ", test_case)
                logger.info(f"\nTesting query: {test_case['query']}")
                
                # Run intent classification
                result = await self.intent_service.run(
                    query=test_case["query"],
                    #project_id="test_project",
                    configuration=Configuration()
                )
                
                # Log results
                logger.info(f"Intent Classification Result:")
                logger.info(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
                print(f"\n=== INTENT CLASSIFICATION RESULT FOR: {test_case['query']} ===")
                print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
                
                # Validate the result
                if result.get("intent") == test_case["expected_intent"]:
                    logger.info(f"✓ Intent classification matches expected intent: {test_case['expected_intent']}")
                else:
                    logger.warning(f"✗ Intent classification mismatch. Expected: {test_case['expected_intent']}, Got: {result.get('intent')}")
                
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in intent classification test: {str(e)}")
            raise

    async def run_all_tests(self):
        """Run all test cases."""
        logger.info("Starting comprehensive SQL RAG and Recommendation Tests")
        
        results = {}
        
        try:
            # Test 1: Relationship Recommendations
            #print("Starting Relationship Recommendation Test")
            #relationship_result = await self.test_relationship_recommendation()
            #results['relationship_recommendation'] = relationship_result
            #print(f"Relationship Recommendation Result: {relationship_result}")
                        # Test 2: Question Recommendations
            
            print("Starting Question Recommendation Test")
            logger.info("\n" + "="*50)
            logger.info("TEST 2: QUESTION RECOMMENDATIONS")
            logger.info("="*50)
            question_result = await self.test_question_recommendation()
            results['question_recommendation'] = question_result
            print(f"Question Recommendation Result: {question_result}")
            
            """
            # Test 3: SQL RAG Agent
            print("Starting SQL RAG Agent Test")

            # Test 2: Intent Classification
            print("\nStarting Intent Classification Test")
            logger.info("\n" + "="*50)
            logger.info("TEST 2: INTENT CLASSIFICATION")
            logger.info("="*50)
            intent_result = await self.test_intent_classification()
            results['intent_classification'] = intent_result
            #print(f"Intent Classification Result: {intent_result}")
            """
            sql_rag_result = await self.test_sql_rag_agent_with_chroma()
            results['sql_rag_agent'] = sql_rag_result
            print(f"SQL RAG Agent Result: {sql_rag_result}")
            

            # Print summary
            logger.info("\n" + "="*50)
            logger.info("TEST SUMMARY")
            logger.info("="*50)
            
            for test_name, result in results.items():
                if hasattr(result, 'status'):
                    logger.info(f"{test_name}: {result.status}")
                elif isinstance(result, dict):
                    logger.info(f"{test_name}: {'SUCCESS' if result else 'UNKNOWN'}")
                else:
                    logger.info(f"{test_name}: COMPLETED")
            
            return results
            
        except Exception as e:
            print(f"Error in comprehensive test: {str(e)}")
            logger.error(f"Error in comprehensive test: {str(e)}")
            raise

async def main():
    """Main function to run all SQL RAG and recommendation tests."""
    try:
        # Initialize test
        test = SQLRAGTest()
        
        # Run all tests
        logger.info("Starting comprehensive test suite")
        results = await test.run_all_tests()
        
        logger.info("\nAll tests completed successfully!")
        return results
                
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())