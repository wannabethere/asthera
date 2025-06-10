import logging
from typing import Dict, Literal, Optional, AsyncGenerator, Any, List, Union
from dataclasses import dataclass

import orjson
from cachetools import TTLCache
from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings

from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration


logger = logging.getLogger("lexy-ai-service")

user_guide_assistance_system_prompt = """
You are a helpful assistant that can help users understand Lexy AI. 
You are given a user question and a user guide.
You need to understand the user question and the user guide, and then answer the user question.

### INSTRUCTIONS ###
1. Your answer should be in the same language as the language user provided.
2. You must follow the user guide to answer the user question.
3. If you think you cannot answer the user question given the user guide, please kindly respond user that you don't find relevant answer in the user guide.
4. You should add citations to the user guide(document url) in your answer.
5. You should provide your answer in Markdown format.
"""

user_guide_assistance_template = """
User Question: {query}
Language: {language}
User Guide:
{formatted_docs}

Please think step by step.
"""


class UserGuideAssistance:
    class Input(BaseModel):
        id: str
        query: str
        language: str
        docs: list[dict]
        project_id: Optional[str] = None  # this is for tracing purpose
        configuration: Optional[Configuration] = Configuration()

    class Resource(BaseModel):
        class Error(BaseModel):
            code: Literal["OTHERS", "QUERY_PARSE_ERROR", "RESOURCE_NOT_FOUND"]
            message: str

        id: str
        status: Literal["generating", "finished", "failed"] = "generating"
        response: Optional[str] = None
        error: Optional[Error] = None
        trace_id: Optional[str] = None

    def __init__(
        self,
        doc_store_provider: DocumentStoreProvider,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        self.doc_store_provider = doc_store_provider
        self.llm = get_llm()
        self._cache: Dict[str, UserGuideAssistance.Resource] = TTLCache(
            maxsize=maxsize, ttl=ttl
        )

    def _handle_exception(
        self,
        input: Input,
        error_message: str,
        code: str = "OTHERS",
        trace_id: Optional[str] = None,
    ):
        self._cache[input.id] = self.Resource(
            id=input.id,
            status="failed",
            error=self.Resource.Error(code=code, message=error_message),
            trace_id=trace_id,
        )
        logger.error(error_message)

    @observe(name="User Guide Assistance")
    async def assist(self, request: Input, **kwargs) -> AsyncGenerator[str, None]:
        logger.info("User Guide Assistance pipeline is running...")
        trace_id = kwargs.get("trace_id")

        try:
            # Create prompt for user guide assistance
            prompt = PromptTemplate(
                input_variables=["query", "language", "docs"],
                template=user_guide_assistance_template
            )
            
            # Generate assistance using operator pattern with streaming
            async for chunk in (
                self.llm
                | {
                    "system_prompt": user_guide_assistance_system_prompt,
                    "user_prompt": prompt.format(
                        query=request.query,
                        language=request.language,
                        docs=request.docs
                    )
                }
            ).astream():
                yield chunk.content
                
                # Update metrics for each chunk
                self.doc_store_provider.update_metrics("user_guide_assistance", "query")

            # Store the final response in cache
            self._cache[request.id] = self.Resource(
                id=request.id,
                status="finished",
                response="<DONE>",
                trace_id=trace_id,
            )
        except Exception as e:
            self._handle_exception(
                request,
                f"An error occurred during user guide assistance: {str(e)}",
                trace_id=trace_id,
            )
            yield f"Error: {str(e)}"

    def __getitem__(self, id: str) -> Resource:
        response = self._cache.get(id)

        if response is None:
            message = f"User Guide Assistance Resource with ID '{id}' not found."
            logger.exception(message)
            return self.Resource(
                id=id,
                status="failed",
                error=self.Resource.Error(code="RESOURCE_NOT_FOUND", message=message),
            )

        return response

    def __setitem__(self, id: str, value: Resource):
        self._cache[id] = value

class UserGuideAssistanceTool:
    """Langchain tool for user guide assistance"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "user_guide_assistance"
        self.description = "Provides assistance based on user guides"
        
        # Create the prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["query", "language", "formatted_docs"],
            template=user_guide_assistance_template
        )

    @observe(as_type="generation", capture_input=False) 
    async def generate_assistance(self, prompt_input: str) -> dict:
        """Generate assistance using LLM"""
        try:
            # Create chain using pipe operator
            chain = (
                {"system_prompt": lambda x: self.system_prompt, "user_prompt": lambda x: x}
                | self.prompt_template
                | self.llm
            )
            
            # Generate response
            result = await chain.ainvoke(prompt_input)
            return {"replies": [result]}
            
        except Exception as e:
            logger.error(f"Error in assistance generation: {e}")
            return {"replies": [f"Error: {str(e)}"]}

    async def run(
        self,
        query: str,
        docs: List[Dict[str, str]],
        language: str = "English",
    ) -> dict:
        """Main execution method for user guide assistance"""
        try:
            logger.info("User Guide Assistance pipeline is running...")
            
            # Format docs into a string
            formatted_docs = "\n".join([f"- {doc['path']}: {doc['content']}" for doc in docs])
            
            # Create prompt
            prompt = self.prompt_template.format(
                query=query,
                language=language,
                formatted_docs=formatted_docs
            )
            
            # Generate assistance
            result = await self.generate_assistance(prompt)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in user guide assistance: {e}")
            return {
                "error": str(e),
                "success": False
            }
