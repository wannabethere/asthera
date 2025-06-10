import asyncio
import logging
from typing import Dict, Any, Optional, List

import chromadb
from langchain_openai import OpenAIEmbeddings

from app.indexing.orchestrator import IndexingOrchestrator
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.agents.retrieval.instructions import Instructions
from app.agents.retrieval.historical_question_retrieval import HistoricalQuestionRetrieval
from app.agents.retrieval.sql_pairs_retrieval import SqlPairsRetrieval
from app.agents.retrieval.retrieval import TableRetrieval
from app.agents.retrieval.preprocess_sql_data import PreprocessSqlData
from app.agents.nodes.sql.utils.sql_prompts import AskHistory
from app.core.dependencies import get_doc_store_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()





class RetrievalHelper:
    def __init__(self):
        """Initialize the retrieval test with all necessary components."""
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
        self.document_stores = get_doc_store_provider().stores
        
        # Initialize retrievers
        self.retrievers = {
            "instructions": Instructions(
                document_store=self.document_stores["instructions"],
                embedder=self.embeddings,
                similarity_threshold=0.7,
                top_k=30
            ),
            "historical_question": HistoricalQuestionRetrieval(
                document_store=self.document_stores["historical_question"],
                embedder=self.embeddings,
                similarity_threshold=0.7  # Lowered threshold for testing
            ),
            "sql_pairs": SqlPairsRetrieval(
                document_store=self.document_stores["sql_pairs"],
                embedder=self.embeddings,
                similarity_threshold=0.1,
                max_retrieval_size=10
            ),
            "table_retrieval": TableRetrieval(
                document_store=self.document_stores["table_description"],
                embedder=self.embeddings,
                model_name="gpt-4",
                table_retrieval_size=10,
                table_column_retrieval_size=100,
                allow_using_db_schemas_without_pruning=False
            ),
            "db_schema": TableRetrieval(
                document_store=self.document_stores["db_schema"],
                embedder=self.embeddings,
                model_name="gpt-4",
                table_retrieval_size=10,
                table_column_retrieval_size=100,
            )
        }
        
        # Initialize SQL data preprocessor
        self.sql_preprocessor = PreprocessSqlData(
            model="gpt-4",
            max_tokens=100_000,
            max_iterations=1000,
            reduction_step=50
        )

    async def get_database_schemas(
        self, 
        project_id: str, 
        table_retrieval: dict, 
        query: str, 
        histories: Optional[list[AskHistory]] = None,
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fetch database schemas for a given project.
        
        Args:
            project_id: The project ID to fetch schemas for
            table_retrieval: Dictionary containing table retrieval configuration
            query: The query string to use for schema retrieval
            histories: Optional list of AskHistory objects for context
            tables: Optional list of specific tables to retrieve schemas for
            
        Returns:
            Dictionary containing database schemas and metadata
        """
        try:
            # Initialize empty history_dicts
            history_dicts = []
            
            # Only process histories if they exist and are not empty
            if histories and len(histories) > 0:
                history_dicts = [
                    {
                        "question": history.query if hasattr(history, 'query') else history.question if hasattr(history, 'question') else "",
                        "sql": history.sql if hasattr(history, 'sql') else ""
                    } for history in histories
                ]
            
            print("Input get_database_schemas tables: ", tables)
            print("Input get_database_schemas table_retrieval: ", table_retrieval)
            print("Input get_database_schemas query: ", query)
            print("Input get_database_schemas project_id: ", project_id)
            
            # Use the table retrieval to get schema information
            schema_result = await self.retrievers["table_retrieval"].run(
                query=query,
                project_id=project_id,
                tables=tables,
                histories=history_dicts
            )
            logger.info(f"schema_result: {schema_result}")
            if not schema_result or "retrieval_results" not in schema_result:
                logger.warning(f"No schema information found for project {project_id}")
                return {
                    "error": "No schema information found",
                    "schemas": []
                }
            
            # Process and format the schema information
            schemas = []
            for result in schema_result["retrieval_results"]:
                if isinstance(result, dict):
                    schema_info = {
                        "table_name": result.get("table_name", ""),
                        "table_ddl": result.get("table_ddl", ""),
                        "has_calculated_field": schema_result.get("has_calculated_field", False),
                        "has_metric": schema_result.get("has_metric", False)
                    }
                    schemas.append(schema_info)
            
            return {
                "schemas": schemas,
                "total_schemas": len(schemas),
                "project_id": project_id,
                "query": query,
                "retrieval_config": table_retrieval,
                "tables": tables,
                "has_calculated_field": schema_result.get("has_calculated_field", False),
                "has_metric": schema_result.get("has_metric", False)
            }
            
        except Exception as e:
            logger.error(f"Error fetching database schemas: {str(e)}")
            return {
                "error": str(e),
                "schemas": [],
                "project_id": project_id,
                "query": query,
                "tables": tables
            }
    
    async def get_sql_pairs(
        self,
        query: str,
        project_id: str,
        similarity_threshold: float = 0.3,
        max_retrieval_size: int = 10
    ) -> Dict[str, Any]:
        """Fetch SQL pairs for a given query.
        
        Args:
            query: The query string to search for similar SQL pairs
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            max_retrieval_size: Maximum number of documents to retrieve
            
        Returns:
            Dictionary containing SQL pairs and metadata
        """
        try:
            # Use the SQL pairs retriever to get similar queries and their SQL
            sql_pairs_result = await self.retrievers["sql_pairs"].run(
                query=query,
                project_id=project_id
            )
            
            if not sql_pairs_result or "documents" not in sql_pairs_result:
                logger.warning(f"No SQL pairs found for project {project_id}")
                return {
                    "error": "No SQL pairs found",
                    "sql_pairs": []
                }
            
            # Process and format the SQL pairs
            logger.info(f"sql_pairs_result in retrieval_helper: {sql_pairs_result}")
            sql_pairs = []
            for doc in sql_pairs_result["documents"]:
                if isinstance(doc, dict):
                    sql_pair = {
                        "question": doc.get("question", ""),
                        "sql": doc.get("sql", ""),
                        "instructions": doc.get("instructions", ""),
                        "score": doc.get("score", 0.0),
                        "raw_distance": doc.get("raw_distance", 0.0)
                    }
                    sql_pairs.append(sql_pair)
            
            return {
                "sql_pairs": sql_pairs,
                "total_pairs": len(sql_pairs),
                "project_id": project_id,
                "query": query,
                "similarity_threshold": similarity_threshold,
                "max_retrieval_size": max_retrieval_size
            }
            
        except Exception as e:
            logger.error(f"Error fetching SQL pairs: {str(e)}")
            return {
                "error": str(e),
                "sql_pairs": [],
                "project_id": project_id,
                "query": query
            }

    async def get_instructions(
        self,
        query: str,
        project_id: str,
        similarity_threshold: float = 0.7,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """Fetch instructions for a given query.
        
        Args:
            query: The query string to search for similar instructions
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            top_k: Maximum number of documents to retrieve
            
        Returns:
            Dictionary containing instructions and metadata
        """
        try:
            # Use the instructions retriever to get similar instructions
            instructions_result = await self.retrievers["instructions"].run(
                query=query,
                project_id=project_id
            )
            
            if not instructions_result or "documents" not in instructions_result:
                logger.warning(f"No instructions found for project {project_id}")
                return {
                    "error": "No instructions found",
                    "instructions": []
                }
            
            # Process and format the instructions
            instructions = []
            for doc in instructions_result["documents"]:
                if isinstance(doc, dict):
                    instruction = {
                        "instruction": doc.get("instruction", ""),
                        "question": doc.get("question", ""),
                        "instruction_id": doc.get("instruction_id", "")
                    }
                    instructions.append(instruction)
            
            return {
                "instructions": instructions,
                "total_instructions": len(instructions),
                "project_id": project_id,
                "query": query,
                "similarity_threshold": similarity_threshold,
                "top_k": top_k
            }
            
        except Exception as e:
            logger.error(f"Error fetching instructions: {str(e)}")
            return {
                "error": str(e),
                "instructions": [],
                "project_id": project_id,
                "query": query
            }

    async def get_historical_questions(
        self,
        query: str,
        project_id: str,
        similarity_threshold: float = 0.9
    ) -> Dict[str, Any]:
        """Fetch historical questions for a given query.
        
        Args:
            query: The query string to search for similar historical questions
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            
        Returns:
            Dictionary containing historical questions and metadata
        """
        try:
            # Generate embedding for the query
            embedding = await self.embeddings.aembed_query(query)
            if not embedding:
                logger.warning("Failed to generate embedding for query")
                return {
                    "error": "Failed to generate embedding",
                    "historical_questions": []
                }

            # Use the historical question retriever to get similar questions
            historical_result = await self.retrievers["historical_question"].run(
                query=query,
                project_id=project_id
            )
            
            if not historical_result or "documents" not in historical_result:
                logger.warning(f"No historical questions found for project {project_id}")
                return {
                    "error": "No historical questions found",
                    "historical_questions": []
                }
            
            # Process and format the historical questions
            historical_questions = []
            for doc in historical_result["documents"]:
                if isinstance(doc, dict):
                    question = {
                        "question": doc.get("question", ""),
                        "summary": doc.get("summary", ""),
                        "statement": doc.get("statement", ""),
                        "viewId": doc.get("viewId", "")
                    }
                    historical_questions.append(question)
            
            return {
                "historical_questions": historical_questions,
                "total_questions": len(historical_questions),
                "project_id": project_id,
                "query": query,
                "similarity_threshold": similarity_threshold
            }
            
        except Exception as e:
            logger.error(f"Error fetching historical questions: {str(e)}")
            return {
                "error": str(e),
                "historical_questions": [],
                "project_id": project_id,
                "query": query
            }

async def main():
    """Main function to test the RetrievalHelper functionality."""
    try:
        # Initialize helper
        helper = RetrievalHelper()
        
        # Test configuration
        test_project_id = "cornerstone"  # Replace with your project ID
        test_query = "Show me all tables and their columns"
        test_table_retrieval = {
            "table_retrieval_size": 10,
            "table_column_retrieval_size": 100,
            "allow_using_db_schemas_without_pruning": False
        }
        test_tables = ["users", "orders", "products"]  # Example tables to test with
        
        # Test database schema retrieval
        logger.info(f"Testing database schema retrieval with query: {test_query}")
        print("test_project_id: ", test_project_id)
        print("test_table_retrieval: ", test_table_retrieval)
        print("test_query: ", test_query)
        print("test_tables: ", test_tables)
        
        schema_results = await helper.get_database_schemas(
            project_id=test_project_id,
            table_retrieval=test_table_retrieval,
            query=test_query,
            tables=test_tables
        )
        print("schema_results: ", schema_results)
        
        # Test SQL pairs retrieval
        logger.info(f"\nTesting SQL pairs retrieval with query: {test_query}")
        sql_pairs_results = await helper.get_sql_pairs(
            query=test_query,
            project_id=test_project_id
        )
        print("sql_pairs_results: ", sql_pairs_results)
        
        # Test instructions retrieval
        logger.info(f"\nTesting instructions retrieval with query: {test_query}")
        instructions_results = await helper.get_instructions(
            query=test_query,
            project_id=test_project_id
        )
        print("instructions_results: ", instructions_results)
        
        # Test historical questions retrieval
        logger.info(f"\nTesting historical questions retrieval with query: {test_query}")
        historical_results = await helper.get_historical_questions(
            query=test_query,
            project_id=test_project_id
        )
        print("historical_results: ", historical_results)
        
        # Print results
        logger.info("\nDatabase Schema Retrieval Results:")
        if "error" in schema_results:
            logger.error(f"Error: {schema_results['error']}")
        else:
            logger.info(f"Total schemas found: {schema_results['total_schemas']}")
            for i, schema in enumerate(schema_results['schemas'], 1):
                logger.info(f"\nSchema {i}:")
                logger.info(f"Table Name: {schema['table_name']}")
                
                # Extract description from table_ddl if it exists
                table_ddl = schema.get('table_ddl', '')
                if table_ddl and table_ddl.startswith('--'):
                    description = table_ddl.split('\n')[0].replace('--', '').strip()
                    if description:
                        logger.info(f"Description: {description}")
                
                # Extract columns from table_ddl
                logger.info("Columns:")
                if table_ddl:
                    # Split the DDL into lines and extract column definitions
                    lines = table_ddl.split('\n')
                    for line in lines:
                        if line.strip() and not line.startswith('--') and not line.startswith('CREATE'):
                            # Clean up the column definition
                            col_def = line.strip().rstrip(',').strip()
                            if col_def:
                                logger.info(f"  - {col_def}")
                
                # Log additional metadata
                logger.info(f"Has Calculated Field: {schema.get('has_calculated_field', False)}")
                logger.info(f"Has Metric: {schema.get('has_metric', False)}")
                
                # Log if it's a view
                if 'CREATE VIEW' in table_ddl:
                    logger.info("Type: View")
                else:
                    logger.info("Type: Table")
        
        # Print SQL pairs results
        logger.info("\nSQL Pairs Retrieval Results:")
        if "error" in sql_pairs_results:
            logger.error(f"Error: {sql_pairs_results['error']}")
        else:
            logger.info(f"Total SQL pairs found: {sql_pairs_results['total_pairs']}")
            for i, pair in enumerate(sql_pairs_results['sql_pairs'], 1):
                logger.info(f"\nSQL Pair {i}:")
                logger.info(f"Question: {pair['question']}")
                logger.info(f"SQL: {pair['sql']}")
                if pair['instructions']:
                    logger.info(f"Instructions: {pair['instructions']}")
                logger.info(f"Similarity Score: {pair['score']}")
        
        # Print instructions results
        logger.info("\nInstructions Retrieval Results:")
        if "error" in instructions_results:
            logger.error(f"Error: {instructions_results['error']}")
        else:
            logger.info(f"Total instructions found: {instructions_results['total_instructions']}")
            for i, instruction in enumerate(instructions_results['instructions'], 1):
                logger.info(f"\nInstruction {i}:")
                logger.info(f"Question: {instruction['question']}")
                logger.info(f"Instruction: {instruction['instruction']}")
                if instruction['instruction_id']:
                    logger.info(f"Instruction ID: {instruction['instruction_id']}")
        
        # Print historical questions results
        logger.info("\nHistorical Questions Retrieval Results:")
        if "error" in historical_results:
            logger.error(f"Error: {historical_results['error']}")
        else:
            logger.info(f"Total historical questions found: {historical_results['total_questions']}")
            for i, question in enumerate(historical_results['historical_questions'], 1):
                logger.info(f"\nHistorical Question {i}:")
                logger.info(f"Question: {question['question']}")
                if question['summary']:
                    logger.info(f"Summary: {question['summary']}")
                if question['statement']:
                    logger.info(f"Statement: {question['statement']}")
                if question['viewId']:
                    logger.info(f"View ID: {question['viewId']}")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise



if __name__ == "__main__":
    asyncio.run(main())

