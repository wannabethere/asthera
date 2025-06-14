import asyncio
import logging
import sys
from typing import Any, Optional, Dict, List
from dataclasses import dataclass

from langfuse.decorators import observe
from langchain_openai import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.agents import Tool
from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration
from app.agents.nodes.sql.utils.sql_prompts import AskHistory
import orjson

logger = logging.getLogger("lexy-ai-service")


@dataclass
class DataAssistanceRequest:
    """Standard data assistance request structure"""
    query: str
    db_schemas: List[str]
    language: str = "English"
    histories: Optional[List[AskHistory]] = None
    configuration: Configuration = None
    project_id: str = None
    timeout: float = 30.0


@dataclass
class DataAssistanceResult:
    """Standard data assistance result structure"""
    success: bool
    data: Dict[str, Any] = None
    error: str = None
    metadata: Dict[str, Any] = None


data_assistance_system_prompt = """
### TASK ###
You are a data analyst great at answering user's questions about given database schema.
Please carefully read user's question and database schema to answer it in easy to understand manner
using the Markdown format. Your goal is to help guide user understand its database!

### INSTRUCTIONS ###

- Answer must be in the same language user specified.
- There should be proper line breaks, whitespace, and Markdown formatting(headers, lists, tables, etc.) in your response.
- If the language is Traditional/Simplified Chinese, Korean, or Japanese, the maximum response length is 150 words; otherwise, the maximum response length is 110 words.
- MUST NOT add SQL code in your response.

### OUTPUT FORMAT ###
Please provide your response in proper Markdown format.
"""

data_assistance_user_prompt_template = """
### DATABASE SCHEMA ###
{db_schemas}

### INPUT ###
User's question: {query}
Language: {language}

Please think step by step
"""


class DataAssistancePipeline:
    """Data assistance pipeline for answering questions about database schema"""
    
    def __init__(
        self,
        doc_store_provider: DocumentStoreProvider,
        **kwargs
    ):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self._user_queues = {}
        
        # Initialize components with LangChain PromptTemplate
        self.prompt_template = PromptTemplate(
            template=data_assistance_user_prompt_template,
            input_variables=["query", "db_schemas", "language"]
        )
        
        # Initialize generator with system prompt
        self.generator = self.llm.bind(
            system_prompt=data_assistance_system_prompt,
            streaming_callback=self._streaming_callback
        )
    
    def _streaming_callback(self, chunk, query_id):
        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()
        asyncio.create_task(self._user_queues[query_id].put(chunk.content))
        if chunk.meta.get("finish_reason"):
            asyncio.create_task(self._user_queues[query_id].put("<DONE>"))
    
    async def get_streaming_results(self, query_id):
        async def _get_streaming_results(query_id):
            return await self._user_queues[query_id].get()

        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()
            
        while True:
            try:
                self._streaming_results = await asyncio.wait_for(
                    _get_streaming_results(query_id), timeout=120
                )
                if self._streaming_results == "<DONE>":
                    del self._user_queues[query_id]
                    break
                if self._streaming_results:
                    yield self._streaming_results
                    self._streaming_results = ""
            except TimeoutError:
                break
    
    @observe(name="Data Assistance")
    async def run(
        self,
        request: DataAssistanceRequest
    ) -> DataAssistanceResult:
        """Run the data assistance pipeline"""
        logger.info("Data Assistance pipeline is running...")
        
        try:
            # Prepare query with history
            query = request.query
            if request.histories:
                previous_queries = [history.question for history in request.histories]
                query = "\n".join(previous_queries) + "\n" + query
            
            
            # Build prompt using LangChain PromptTemplate
            prompt = self.prompt_template.format(
                query=query,
                db_schemas=request.db_schemas,
                language=request.language
            )
            
            # Concatenate system and user prompts directly
            full_prompt = f"{data_assistance_system_prompt}\n\n{prompt}"
            
            result = await self.llm.ainvoke(full_prompt)
            
            # Update metrics
            self.doc_store_provider.update_metrics("sql_queries", "query")
            logger.info(f"data assistance result I am here {result}")
            return DataAssistanceResult(
                success=True,
                data=result.content,
                metadata={
                    "operation": "data_assistance",
                    "language": request.language
                }
            )
            
        except Exception as e:
            logger.error(f"Error in data assistance: {e}")
            return DataAssistanceResult(
                success=False,
                error=str(e),
                metadata={
                    "operation": "data_assistance",
                    "language": request.language
                }
            )


class DataAssistanceFactory:
    """Factory class for creating data assistance pipelines"""
    
    @staticmethod
    def create_pipeline(
        doc_store_provider: DocumentStoreProvider,
        **kwargs
    ) -> DataAssistancePipeline:
        """Create data assistance pipeline with specified configuration"""
        return DataAssistancePipeline(
            doc_store_provider=doc_store_provider,
            **kwargs
        )
    
    @staticmethod
    def create_simple_pipeline(doc_store_provider: DocumentStoreProvider) -> DataAssistancePipeline:
        """Create simple pipeline with default settings"""
        return DataAssistanceFactory.create_pipeline(
            doc_store_provider=doc_store_provider
        )


# Convenience functions for common operations
async def quick_data_assistance(
    query: str,
    db_schemas: List[str],
    doc_store_provider: DocumentStoreProvider,
    language: str = "English"
) -> Dict[str, Any]:
    """Quick data assistance with minimal setup"""
    pipeline = DataAssistanceFactory.create_pipeline(
        doc_store_provider=doc_store_provider
    )
    
    request = DataAssistanceRequest(
        query=query,
        db_schemas=db_schemas,
        language=language
    )
    
    result = await pipeline.run(request)
    return result.data if result.success else {"error": result.error}


# Example usage and testing
async def example_usage():
    """Example of how to use the data assistance pipeline"""
    from app.core.dependencies import get_doc_store_provider
    
    # Get document store provider
    doc_store_provider = get_doc_store_provider()
    
    # Schema documents
    schema_docs = [
        "CREATE TABLE customers (id INT, name VARCHAR, email VARCHAR, created_at TIMESTAMP)",
        "CREATE TABLE orders (id INT, customer_id INT, total DECIMAL, order_date TIMESTAMP)",
        "CREATE TABLE order_items (order_id INT, product_id INT, quantity INT, price DECIMAL)"
    ]
    
    # Example: Quick data assistance
    print("=== Quick Data Assistance ===")
    result = await quick_data_assistance(
        query="What tables are available in the database?",
        db_schemas=schema_docs,
        doc_store_provider=doc_store_provider,
        language="English"
    )
    print(result)


class DataAssistanceTool:
    """Langchain tool for data assistance"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "data_assistance"
        self.description = "Provides data assistance based on user questions"

    @observe(capture_input=False)
    def create_prompt(
        self,
        query: str,
        db_schemas: list[str],
        configuration: Configuration
    ) -> str:
        """Create prompt for data assistance"""
        try:
            # Format database schemas as a readable string
            formatted_schemas = "\n".join(db_schemas) if db_schemas else ""
            user_prompt = data_assistance_user_prompt_template.format(
                db_schemas=formatted_schemas,
                query=query,
                language=configuration.language or "English"
            )
            return user_prompt
        except Exception as e:
            logger.error(f"Error creating prompt: {e}")
            return ""

    @observe(as_type="generation", capture_input=False)
    async def generate_assistance(self, prompt_input: str, query_id: str = None) -> dict:
        """Generate data assistance using LLM"""
        try:
            # Concatenate system and user prompts directly
            full_prompt = f"{data_assistance_system_prompt}\n\n{prompt_input}"
            logger.info("data assistance full_prompt", full_prompt)
            result = await self.llm.ainvoke(full_prompt)
            self.doc_store_provider.update_metrics("data_assistance", "query")
            return {"replies": [result]}
        except Exception as e:
            logger.error(f"Error in data assistance generation: {e}")
            return {"replies": [""]}

    @observe()
    def post_process(self, generate_result: dict) -> str:
        """Post-process the generated assistance"""
        replies = generate_result.get("replies", [""])
        return replies[0] if replies else ""

    async def run(
        self,
        query: str,
        db_schemas: list[str],
        configuration: Configuration = Configuration(),
        query_id: Optional[str] = None,
    ) -> dict:
        """Main execution method for data assistance"""
        try:
            logger.info("Data Assistance pipeline is running...")
            
            # Step 1: Create prompt
            prompt_input = self.create_prompt(
                query=query,
                db_schemas=db_schemas,
                configuration=configuration
            )
            logger.info("data assistance prompt_input I created the prompt", prompt_input)
            # Step 2: Generate assistance
            generate_result = await self.generate_assistance(prompt_input, query_id)
            
            # Step 3: Post-process
            assistance = self.post_process(generate_result)
            
            return {
                "assistance": assistance,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in data assistance: {e}")
            return {
                "assistance": "",
                "success": False,
                "error": str(e)
            }


def create_data_assistance_tool(doc_store_provider: DocumentStoreProvider) -> Tool:
    """Create Langchain tool for data assistance"""
    assistance_tool = DataAssistanceTool(doc_store_provider)
    
    def assistance_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(assistance_tool.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="data_assistant",
        description="Provides data assistance based on user questions. Input should be JSON with 'query', 'db_schemas', and optional configuration fields.",
        func=assistance_func
    )


if __name__ == "__main__":
    asyncio.run(example_usage())