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
from app.core.provider import DocumentStoreProvider
import orjson
import asyncio
import pandas as pd
from typing import Optional, Dict, Any

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()

class SQLRAGTest:
    def __init__(self):
        """Initialize the SQL RAG test with all necessary components."""
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
            
            documentProvider = DocumentStoreProvider(stores=self.document_stores)
            # Create agent
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
            engine = PandasEngine(data_sources={
                'employees': employees_df,
                'overdue_analysis': overdue_df
            })
            agent = create_sql_rag_agent(llm=llm, engine=engine,document_store_provider=documentProvider)
            
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
            print(result)
            #logger.info(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            
            # Test SQL breakdown if generation was successful
            #result {'valid_generation_results': [{'sql': 'SELECT AVG("days_overdue") FROM "overdue_analysis"', 'correlation_id': ''}], 'invalid_generation_results': []}
            sql = result["valid_generation_results"][0]["sql"]
            breakdown_result = await breakdown_sql_with_rag(
                agent,
                test_query,
                sql,
                language="English"
            )
            
            logger.info("\nSQL Breakdown Result:")
            logger.info(orjson.dumps(breakdown_result, option=orjson.OPT_INDENT_2).decode())
            print(orjson.dumps(breakdown_result, option=orjson.OPT_INDENT_2).decode())
            return result
            
        except Exception as e:
            logger.error(f"Error in test: {str(e)}")
            raise

async def main():
    """Main function to run the SQL RAG test."""
    try:
        # Initialize test
        test = SQLRAGTest()
        
        # Run test
        logger.info("Starting SQL RAG test")
        result = await test.test_sql_rag_agent_with_chroma()
        
        # Print summary
        if result:
            logger.info("\nSQL RAG Test Summary:")
            logger.info(f"Success: {result.get('success', False)}")
            if result.get('sql'):
                logger.info(f"Generated SQL: {result['sql']}")
            if result.get('error'):
                logger.info(f"Error: {result['error']}")
                
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())