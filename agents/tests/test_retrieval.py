import asyncio
import logging
from typing import Dict, Any, Optional

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()

class RetrievalTest:
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
        self.document_stores = {
            "instructions": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="instructions"
            ),
            "historical_question": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="historical_question"
            ),
            "sql_pairs": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="sql_pairs"
            ),
            "table_description": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="table_description"
            )
        }
        
        # Initialize retrievers
        self.retrievers = {
            "instructions": Instructions(
                document_store=self.document_stores["instructions"],
                embedder=self.embeddings,
                similarity_threshold=0.7,
                top_k=10
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
            )
        }
        
        # Initialize SQL data preprocessor
        self.sql_preprocessor = PreprocessSqlData(
            model="gpt-4",
            max_tokens=100_000,
            max_iterations=1000,
            reduction_step=50
        )

    async def check_collection_status(self, collection_name: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Check the status of a collection.
        
        Args:
            collection_name: Name of the collection to check
            project_id: Optional project ID to filter by
            
        Returns:
            Dictionary containing collection status information
        """
        try:
            collection = self.document_stores[collection_name].collection
            
            # Get total count
            total_count = collection.count()
            
            # Get sample documents
            where = {"project_id": project_id} if project_id else None
            sample_docs = collection.get(
                where=where,
                limit=5
            )
            
            return {
                "total_count": total_count,
                "has_documents": total_count > 0,
                "sample_documents": sample_docs.get("documents", []),
                "sample_metadatas": sample_docs.get("metadatas", [])
            }
        except Exception as e:
            logger.error(f"Error checking collection {collection_name}: {str(e)}")
            return {
                "error": str(e),
                "total_count": 0,
                "has_documents": False
            }

    async def test_historical_question_retrieval(
        self,
        query: str,
        project_id: str,
        debug: bool = True
    ) -> Dict[str, Any]:
        """Test historical question retrieval with debugging information.
        
        Args:
            query: The query string to test with
            project_id: The project ID to filter results
            debug: Whether to include debugging information
            
        Returns:
            Dictionary containing retrieval results and debug info
        """
        results = {}
        
        try:
            if debug:
                # Check collection status
                collection_status = await self.check_collection_status(
                    "historical_question",
                    project_id
                )
                results["collection_status"] = collection_status
                logger.info(f"Collection status: {collection_status}")
                
                if not collection_status["has_documents"]:
                    logger.warning("No documents found in historical_question collection")
                    return results
            
            # Generate query embedding
            embedding_result = await self.embeddings.aembed_query(query)
            results["query_embedding"] = {
                "length": len(embedding_result),
                "sample": embedding_result[:5] if embedding_result else None
            }
            
            # Run retrieval
            logger.info("Testing Historical Question retriever...")
            historical_result = await self.retrievers["historical_question"].run(
                query=query,
                project_id=project_id
            )
            results["retrieval_result"] = historical_result
            
            if debug:
                # Get raw results from collection
                collection = self.document_stores["historical_question"].collection
                where = {"project_id": project_id} if project_id else None
                raw_results = collection.query(
                    query_embeddings=[embedding_result],
                    where=where,
                    n_results=10
                )
                results["raw_results"] = {
                    "documents": raw_results.get("documents", []),
                    "metadatas": raw_results.get("metadatas", []),
                    "distances": raw_results.get("distances", [])
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Error in historical question retrieval test: {str(e)}")
            results["error"] = str(e)
            return results

    async def test_all_retrievers(self, query: str, project_id: str) -> Dict[str, Any]:
        """Test all retrievers with the given query.
        
        Args:
            query: The query string to test with
            project_id: The project ID to filter results
            
        Returns:
            Dictionary containing results from all retrievers
        """
        results = {}
        
        try:
            
            # Test Instructions retriever
            logger.info("Testing Instructions retriever...")
            instructions_result = await self.retrievers["instructions"].run(
                query=query,
                project_id=project_id
            )
            results["instructions"] = instructions_result
            logger.info(f"Instructions results: {instructions_result}")
            
            
            # Test Historical Question retriever with debugging
            logger.info("Testing Historical Question retriever...")
            historical_result = await self.test_historical_question_retrieval(
                query=query,
                project_id=project_id,
                debug=True
            )
            results["historical_questions"] = historical_result
            logger.info(f"Historical questions results: {historical_result}")
            
            # Test SQL Pairs retriever
            
            
            # Test Table retriever
            logger.info("Testing Table retriever...")
            table_result = await self.retrievers["table_retrieval"].run(
                query=query,
                project_id=project_id
            )
            results["tables"] = table_result
            logger.info(f"Table results: {table_result}")
            
            logger.info("Testing SQL Pairs retriever...")
            sql_pairs_result = await self.retrievers["sql_pairs"].run(
                query=query,
                project_id=project_id
            )
            results["sql_pairs"] = sql_pairs_result
            logger.info(f"SQL pairs results: {sql_pairs_result}")
            # Test SQL data preprocessing if we have SQL results
            if sql_pairs_result.get("documents"):
                logger.info("Testing SQL data preprocessing...")
                sql_data = {
                    "data": [{"row": i} for i in range(1000)],
                    "metadata": {"table": "example"}
                }
                preprocessed_result = self.sql_preprocessor.run(sql_data)
                results["preprocessed_sql"] = preprocessed_result
                logger.info(f"Preprocessed SQL results: {preprocessed_result}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in retrieval test: {str(e)}")
            raise

async def main():
    """Main function to run the retrieval tests."""
    try:
        # Initialize test
        test = RetrievalTest()
        
        # Test query
        test_query = "What is the average days over due for training of employees?"
        project_id = "cornerstone"  # Replace with your project ID
        
        # Run tests
        logger.info(f"Starting retrieval tests with query: {test_query}")
        results = await test.test_all_retrievers(
            query=test_query,
            project_id=project_id
        )
        
        # Print summary
        logger.info("\nRetrieval Test Summary:")
        for retriever_name, result in results.items():
            logger.info(f"\n{retriever_name.upper()} Results:")
            if isinstance(result, dict):
                if "documents" in result:
                    logger.info(f"Number of documents found: {len(result['documents'])}")
                    for i, doc in enumerate(result["documents"], 1):
                        logger.info(f"\nDocument {i}:")
                        for key, value in doc.items():
                            logger.info(f"  {key}: {value}")
                elif "collection_status" in result:
                    logger.info("Collection Status:")
                    logger.info(f"  Total documents: {result['collection_status']['total_count']}")
                    logger.info(f"  Has documents: {result['collection_status']['has_documents']}")
                    if result['collection_status'].get('sample_documents'):
                        logger.info("  Sample documents:")
                        for i, doc in enumerate(result['collection_status']['sample_documents'], 1):
                            logger.info(f"    Document {i}: {doc}")
                else:
                    logger.info(f"Result: {result}")
            else:
                logger.info(f"Result: {result}")
                
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 