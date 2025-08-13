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
from app.agents.retrieval.retrieval_helper import RetrievalHelper
import orjson

logger = logging.getLogger("lexy-ai-service")


@dataclass
class DataAssistanceRequest:
    """Standard data assistance request structure"""
    query_id: str 
    query: str
    project_id: str
    language: str = "English"
    db_schemas: Optional[List[str]] = None
    histories: Optional[List[AskHistory]] = None
    configuration: Optional[Configuration | Dict[str, Any]] = None
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
Tables names are provided in schema table_name, columns are provided in table_ddl.

### INSTRUCTIONS ###

- Answer must be in the same language user specified.
- If any question cannot be answered based on the database schema, we can suggest calculated columns please assist with that as well.
- If the column is not there and cannot be calculated, please suggest that column needs to be added to the database.
- There should be proper line breaks, whitespace, and Markdown formatting(headers, lists, tables, etc.) in your response.
- If the language is Traditional/Simplified Chinese, Korean, or Japanese, the maximum response length is 150 words; otherwise, the maximum response length is 110 words.
- MUST NOT add SQL code in your response.
- MUST add tables available that are relevant to the user's question, and columns available for each table in the database in markdown format.

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


class DataAssistanceTool:
    """Langchain tool for data assistance"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider, retrieval_helper: RetrievalHelper = None,):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "data_assistance"
        self.retrieval_helper = retrieval_helper
        self.description = "Provides data assistance based on user questions"

    @observe(capture_input=False)
    def create_prompt(
        self,
        query: str,
        db_schemas: list[str],
        configuration: Optional[Configuration | Dict[str, Any]] = None
    ) -> str:
        """Create prompt for data assistance"""
        try:
            # Format database schemas as a readable string
            formatted_schemas = "\n".join(db_schemas) if db_schemas else ""
            print(f"formatted_schemas: {formatted_schemas}")
            
            # Handle configuration safely - provide default language if configuration is None
            if configuration is None:
                language = "English"
            elif isinstance(configuration, dict):
                language = configuration.get('language', 'English')
            else:
                language = getattr(configuration, 'language', 'English') or "English"
                
            user_prompt = data_assistance_user_prompt_template.format(
                db_schemas=formatted_schemas,
                query=query,
                language=language
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
            logger.info(f"data assistance full_prompt: {full_prompt}")
            result = await self.llm.ainvoke(full_prompt)
            self.doc_store_provider.update_metrics("data_assistance", "query")
            print(f"data assistance result: {result.content}")
            return {"replies": [result.content]}
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
       request: DataAssistanceRequest,
       **kwargs
    ) -> DataAssistanceResult:
        """Main execution method for data assistance"""
        try:
            logger.info(f"Data Assistance pipeline is running...{request}")
            
            db_schemas = await self.retrieval_helper.get_database_schemas(
                project_id=request.project_id,
                table_retrieval={
                    "table_retrieval_size": 10,
                    "table_column_retrieval_size": 100,
                    "allow_using_db_schemas_without_pruning": False
                },
                query=request.query
            )
            table_names = []
            schema_contexts = []
            
            if db_schemas and "schemas" in db_schemas:
                for schema in db_schemas["schemas"]:
                    if isinstance(schema, dict):
                        # Extract table name from schema
                        table_name = schema.get("table_name", "")
                        if table_name:
                            table_names.append(table_name)
                        
                        # Extract table DDL from schema
                        table_ddl = schema.get("table_ddl", "")
                        if table_ddl:
                            schema_contexts.append(table_ddl)
            
            #logger.info(f"db_schemas: {schema_contexts}")
            # Step 1: Create prompt
            prompt_input = self.create_prompt(
                query=request.query,
                db_schemas=schema_contexts,
                configuration=request.configuration
            )
            #logger.info(f"data assistance prompt_input I created the prompt: {prompt_input}")
            # Step 2: Generate assistance
            generate_result = await self.generate_assistance(prompt_input, request.query_id)
            
            # Step 3: Post-process
            assistance = self.post_process(generate_result)
            
            return DataAssistanceResult(
                success=True,
                data=assistance,
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


def create_data_assistance_tool(doc_store_provider: DocumentStoreProvider) -> Tool:
    """Create Langchain tool for data assistance"""
    assistance_tool = DataAssistanceTool(doc_store_provider)
    
    def assistance_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(assistance_tool.run(**input_data))
            # Convert DataAssistanceResult to dict for JSON serialization
            result_dict = {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "metadata": result.metadata
            }
            return orjson.dumps(result_dict).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="data_assistant",
        description="Provides data assistance based on user questions. Input should be JSON with 'query', 'db_schemas', and optional configuration fields.",
        func=assistance_func
    )


