import logging
import asyncio
import orjson
from typing import Optional, Dict, Any
import uuid

from app.core.provider import DocumentStoreProvider
from app.agents.nodes.sql.followup_sql_generation_reasoning import FollowUpSQLGenerationReasoning
from app.agents.nodes.sql.data_assistance import DataAssistanceTool, DataAssistanceRequest
from app.agents.nodes.sql.followup_sql_generation import FollowUpSQLGeneration
from app.agents.nodes.sql.utils.sql_prompts import Configuration, sql_generation_system_prompt
from app.services.sql.models import AskHistory
from app.storage.documents import DocumentChromaStore
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from app.settings import get_settings
import os

os.environ["OPENAI_API_KEY"] = "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"
logger = logging.getLogger("wren-ai-service")
settings = get_settings()

class TestFollowupAndAssistance:
    def __init__(self):
        """Initialize the test suite with all necessary components."""
        # Initialize document store provider
        """Initialize the SQL RAG test with all necessary components."""
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
        
        # Initialize services
        self.followup_reasoning = FollowUpSQLGenerationReasoning(
            doc_store_provider=self.document_provider
        )
        
        self.data_assistance = DataAssistanceTool(
            doc_store_provider=self.document_provider
        )
        
        self.followup_generation = FollowUpSQLGeneration(
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
                        {"name": "salary", "type": "decimal", "description": "Employee annual salary"}
                    ],
                    "primary_key": ["employee_id"],
                    "description": "Employee information"
                },
                {
                    "name": "departments",
                    "columns": [
                        {"name": "department_id", "type": "integer", "description": "Unique identifier for department"},
                        {"name": "department_name", "type": "string", "description": "Department name"},
                        {"name": "budget", "type": "decimal", "description": "Department annual budget"}
                    ],
                    "primary_key": ["department_id"],
                    "description": "Department information"
                }
            ],
            "relationships": [
                {
                    "source": "employees",
                    "target": "departments",
                    "type": "Many-to-One",
                    "join_condition": "employees.department_id = departments.department_id"
                }
            ]
        }
        
        return orjson.dumps(sample_mdl).decode('utf-8')

    async def test_followup_reasoning(self):
        """Test the follow-up SQL reasoning service."""
        try:
            logger.info("Testing Follow-up SQL Reasoning Service")
            
            # Create test input
            test_id = str(uuid.uuid4())
            mdl = self.create_sample_mdl()
            
            # Create test histories
            histories = [
                AskHistory(
                    question="What is the average salary by department?",
                    sql="SELECT d.department_name, AVG(e.salary) as avg_salary FROM employees e JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name",
                    summary="Average salary by department"
                )
            ]
            
            # Test follow-up question
            followup_query = "Which department has the highest average salary?"
            
            # Run follow-up reasoning
            result = await self.followup_reasoning.run(
                query=followup_query,
                contexts=[mdl],
                histories=histories,
                configuration=Configuration()
            )
            
            # Log results
            logger.info(f"Follow-up Reasoning Result:")
            logger.info(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            print("\n=== FOLLOW-UP REASONING RESULT ===")
            print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            
            # Validate the result
            if result.get("replies") and len(result["replies"]) > 0:
                logger.info("✓ Follow-up reasoning generated successfully")
            else:
                logger.warning("✗ Follow-up reasoning failed to generate")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in follow-up reasoning test: {str(e)}")
            raise

    async def test_followup_generation(self):
        """Test the follow-up SQL generation service."""
        try:
            logger.info("Testing Follow-up SQL Generation Service")
            
            # Create test input
            test_id = str(uuid.uuid4())
            mdl = self.create_sample_mdl()
            
            # Create test histories
            histories = [
                AskHistory(
                    question="What is the average salary by department?",
                    sql="SELECT d.department_name, AVG(e.salary) as avg_salary FROM employees e JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name",
                    summary="Average salary by department"
                )
            ]
            
            # Create sample SQL examples
            sql_samples = [
                {
                    "summary": "Get average salary by department",
                    "sql": "SELECT d.department_name, AVG(e.salary) as avg_salary FROM employees e JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name"
                }
            ]
            
            # Create instructions
            instructions = [
                {
                    "type": "format",
                    "content": "Use proper SQL formatting and aliases"
                },
                {
                    "type": "constraint",
                    "content": "Only use tables and columns that exist in the schema"
                }
            ]
            
            # Test follow-up question
            followup_query = "Which department has the highest average salary?"
            
            # First get the reasoning
            reasoning_result = await self.followup_reasoning.run(
                query=followup_query,
                contexts=[mdl],
                histories=histories,
                configuration=Configuration()
            )
            
            # Extract reasoning from the result
            sql_generation_reasoning = reasoning_result.get("replies", [""])[0]
            
            # Run the follow-up SQL generation pipeline
            result = await self.followup_generation.run(
                query=followup_query,
                contexts=[mdl],
                sql_generation_reasoning=sql_generation_reasoning,
                histories=histories,
                configuration=Configuration(),
                sql_samples=sql_samples,
                instructions=instructions,
                project_id=test_id
            )
            
            # Log results
            logger.info(f"Follow-up SQL Generation Result:")
            logger.info(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            print("\n=== FOLLOW-UP SQL GENERATION RESULT ===")
            print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            
            # Validate the result
            if result.get("valid_generation_results") and len(result["valid_generation_results"]) > 0:
                logger.info("✓ Follow-up SQL generation successful")
                # Log the generated SQL
                for idx, gen_result in enumerate(result["valid_generation_results"]):
                    logger.info(f"Generated SQL {idx + 1}:")
                    logger.info(gen_result.get("sql", ""))
            else:
                logger.warning("✗ Follow-up SQL generation failed")
                if result.get("error"):
                    logger.error(f"Error: {result['error']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in follow-up SQL generation test: {str(e)}")
            raise

    async def test_data_assistance(self):
        """Test the data assistance service."""
        try:
            logger.info("Testing Data Assistance Service")
            
            # Create test input
            test_id = str(uuid.uuid4())
            mdl = self.create_sample_mdl()
            
            # Create test request
            request = DataAssistanceRequest(
                query="What tables are available and what information do they contain?",
                db_schemas=[mdl],
                language="English",
                project_id=test_id
            )
            
            # Create prompt
            prompt = self.data_assistance.create_prompt(
                query=request.query,
                db_schemas=request.db_schemas,
                configuration=Configuration()
            )
            
            # Generate response using LLM
            response = await self.llm.ainvoke(prompt)
            
            # Create result
            result = {
                "assistance": response.content,
                "success": True
            }
            
            # Log results
            logger.info(f"Data Assistance Result:")
            logger.info(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            print("\n=== DATA ASSISTANCE RESULT ===")
            print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            
            # Validate the result
            if result.get("success") and result.get("assistance"):
                logger.info("✓ Data assistance generated successfully")
            else:
                logger.warning("✗ Data assistance failed to generate")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in data assistance test: {str(e)}")
            raise

    async def run_all_tests(self):
        """Run all test cases."""
        logger.info("Starting comprehensive Follow-up and Assistance Tests")
        
        results = {}
        
        try:
            # Test 1: Follow-up SQL Reasoning
            print("\nStarting Follow-up SQL Reasoning Test")
            logger.info("\n" + "="*50)
            logger.info("TEST 1: FOLLOW-UP SQL REASONING")
            logger.info("="*50)
            followup_result = await self.test_followup_reasoning()
            results['followup_reasoning'] = followup_result
            
            # Test 2: Follow-up SQL Generation
            print("\nStarting Follow-up SQL Generation Test")
            logger.info("\n" + "="*50)
            logger.info("TEST 2: FOLLOW-UP SQL GENERATION")
            logger.info("="*50)
            generation_result = await self.test_followup_generation()
            results['followup_generation'] = generation_result
            
            # Test 3: Data Assistance
            print("\nStarting Data Assistance Test")
            logger.info("\n" + "="*50)
            logger.info("TEST 3: DATA ASSISTANCE")
            logger.info("="*50)
            assistance_result = await self.test_data_assistance()
            results['data_assistance'] = assistance_result
            
            # Print summary
            logger.info("\n" + "="*50)
            logger.info("TEST SUMMARY")
            logger.info("="*50)
            
            for test_name, result in results.items():
                if isinstance(result, dict):
                    if test_name == 'followup_generation':
                        status = "SUCCESS" if result.get("valid_generation_results") else "FAILED"
                    else:
                        status = "SUCCESS" if result.get("success", False) or result.get("replies") else "FAILED"
                    logger.info(f"{test_name}: {status}")
                else:
                    logger.info(f"{test_name}: UNKNOWN")
            
            return results
            
        except Exception as e:
            print(f"Error in comprehensive test: {str(e)}")
            logger.error(f"Error in comprehensive test: {str(e)}")
            raise

async def main():
    """Main function to run all tests."""
    try:
        # Initialize test
        test = TestFollowupAndAssistance()
        
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