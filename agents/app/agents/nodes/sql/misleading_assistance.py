import asyncio
import logging
from typing import Any, Optional

import orjson
# Import Tool using modern LangChain paths
try:
    from langchain_core.tools import Tool
except ImportError:
    try:
        from langchain.tools import Tool
    except ImportError:
        from langchain.agents import Tool
# Import PromptTemplate using modern LangChain paths
try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
import json

from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import AskHistory

logger = logging.getLogger("lexy-ai-service")


misleading_assistance_system_prompt = """
### TASK ###
You are a helpful assistant that can help users understand their data better. Currently, you are given a user's question that is potentially misleading.
Your goal is to help guide user understand its data better and suggest few better questions to ask.

### INSTRUCTIONS ###

- Answer must be in the same language user specified.
- There should be proper line breaks, whitespace, and Markdown formatting(headers, lists, tables, etc.) in your response.
- If the language is Traditional/Simplified Chinese, Korean, or Japanese, the maximum response length is 150 words; otherwise, the maximum response length is 110 words.
- MUST NOT add SQL code in your response.
- MUST consider database schema when suggesting better questions.

### OUTPUT FORMAT ###
Please provide your response in proper Markdown format.
"""

misleading_assistance_user_prompt_template = """
### DATABASE SCHEMA ###
{db_schemas}

### INPUT ###
User's question: {query}
Language: {language}

Please think step by step
"""


class MisleadingAssistanceTool:
    """Langchain tool for misleading assistance"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "misleading_assistance"
        self.description = "Provides assistance for misleading or unclear queries"
        
        # User queues for streaming support
        self._user_queues = {}

    def _streaming_callback(self, chunk, query_id):
        """Callback for streaming responses"""
        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()

        # Put the chunk content into the user's queue
        asyncio.create_task(self._user_queues[query_id].put(chunk.content))
        if chunk.meta.get("finish_reason"):
            asyncio.create_task(self._user_queues[query_id].put("<DONE>"))

    async def get_streaming_results(self, query_id):
        """Get streaming results for a query"""
        async def _get_streaming_results(query_id):
            return await self._user_queues[query_id].get()

        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()

        while True:
            try:
                # Wait for an item from the user's queue
                self._streaming_results = await asyncio.wait_for(
                    _get_streaming_results(query_id), timeout=120
                )
                if (
                    self._streaming_results == "<DONE>"
                ):  # Check for end-of-stream signal
                    del self._user_queues[query_id]
                    break
                if self._streaming_results:  # Check if there are results to yield
                    yield self._streaming_results
                    self._streaming_results = ""  # Clear after yielding
            except TimeoutError:
                break

    @observe(capture_input=False)
    def create_prompt(
        self,
        query: str,
        db_schemas: list[str],
        language: str,
        histories: Optional[list[AskHistory]] = None,
    ) -> str:
        """Create prompt for misleading assistance"""
        try:
            # Combine query with previous query summaries if available
            previous_query_summaries = (
                [history.question for history in histories] if histories else []
            )
            full_query = "\n".join(previous_query_summaries) + "\n" + query
            
            prompt_template = PromptTemplate(
                input_variables=["query", "db_schemas", "language"],
                template=misleading_assistance_user_prompt_template
            )
            
            return prompt_template.format(
                query=full_query,
                db_schemas=json.dumps(db_schemas),
                language=language,
            )
        except Exception as e:
            logger.error(f"Error creating prompt: {e}")
            return ""

    @observe(as_type="generation", capture_input=False)
    async def generate_misleading_assistance(self, prompt_input: str, query_id: str = None) -> dict:
        """Generate misleading assistance using LLM"""
        try:
            # Create full prompt with system and user parts
            full_prompt = f"{misleading_assistance_system_prompt}\n\n{prompt_input}"
            
            # Generate response using LLM
            result = await self.llm.ainvoke(full_prompt)
            
            # Update metrics
            self.doc_store_provider.update_metrics("misleading_assistance", "query")
            
            return {"replies": [result]}
        except Exception as e:
            logger.error(f"Error in misleading assistance generation: {e}")
            return {"replies": [""]}

    async def run(
        self,
        query: str,
        db_schemas: list[str],
        language: str,
        query_id: Optional[str] = None,
        histories: Optional[list[AskHistory]] = None,
    ) -> dict:
        """Main execution method for misleading assistance"""
        try:
            logger.info("Misleading Assistance pipeline is running...")
            
            # Step 1: Create prompt
            prompt_input = self.create_prompt(
                query=query,
                db_schemas=db_schemas,
                language=language,
                histories=histories,
            )
            
            # Step 2: Generate assistance
            generate_result = await self.generate_misleading_assistance(prompt_input, query_id)
            print("misleading assistance result generate_result", generate_result)
            # Step 3: Return result
            assistance_text = generate_result.get("replies", [""])[0]
            print("misleading assistance result assistance_text", assistance_text.content)
            return {
                "assistance": assistance_text.content,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in misleading assistance: {e}")
            return {
                "assistance": "",
                "success": False,
                "error": str(e)
            }


class MisleadingAssistance:
    """Main MisleadingAssistance class maintaining original interface"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider, **kwargs):
        self.tool = MisleadingAssistanceTool(doc_store_provider)

   

    @observe(name="Misleading Assistance")
    async def run(
        self,
        query: str,
        db_schemas: list[str],
        language: str,
        query_id: Optional[str] = None,
        histories: Optional[list[AskHistory]] = None,
    ) -> dict:
        """Run misleading assistance with original interface"""
        result = await self.tool.run(
            query=query,
            db_schemas=db_schemas,
            language=language,
            query_id=query_id,
            histories=histories,
        )
       
        # Return in original format
        if result.get("success", False):
            return {"replies": [result["assistance"]]}
        else:
            return {"replies": [""]}


def create_misleading_assistance_tool(doc_store_provider: DocumentStoreProvider) -> Tool:
    """Create Langchain tool for misleading assistance"""
    assistance_tool = MisleadingAssistanceTool(doc_store_provider)
    
    def assistance_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(assistance_tool.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="misleading_assistant",
        description="Provides assistance for misleading or unclear queries. Input should be JSON with 'query', 'db_schemas', 'language', and optional 'query_id' and 'histories' fields.",
        func=assistance_func
    )


if __name__ == "__main__":
    # Test the misleading assistance tool
    async def test_misleading_assistance():
        from app.core.dependencies import get_doc_store_provider
        
        doc_store_provider = get_doc_store_provider()
        assistance = MisleadingAssistance(doc_store_provider)
        
        result = await assistance.run(
            query="hi",
            db_schemas=[],
            language="English",
        )
        
        print("Misleading Assistance Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(test_misleading_assistance())