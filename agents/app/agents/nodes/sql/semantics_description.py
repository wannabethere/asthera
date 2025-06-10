import logging
from typing import Any, Dict, List, Optional, Union, Literal
from dataclasses import dataclass
import asyncio

import orjson
from langchain_openai import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.tools import Tool

from app.agents.nodes.sql.sql_rag_agent import (
    SQLRAGAgent,
    SQLOperationType,
    create_sql_rag_agent,
    generate_sql_with_rag,
    breakdown_sql_with_rag,
    answer_with_sql_rag,
)
from app.agents.nodes.sql.utils.sql_rag_tools import (
    SQLGenerationTool,
    SQLBreakdownTool,
    SQLReasoningTool,
    SQLAnswerTool,
    SQLCorrectionTool,
    SQLExpansionTool,
    SQLQuestionTool,
    SQLSummaryTool,
)
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration
from cachetools import TTLCache
from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel

logger = logging.getLogger("lexy-ai-service")

semantics_description_system_prompt = """
You are an expert in data modeling and semantic analysis. Your task is to analyze the given data model and provide a clear, concise description of its semantic meaning and business context.

### Guidelines:
1. Analyze the data model to understand its purpose and structure
2. Identify key entities and their relationships
3. Explain the business context and domain
4. Highlight important patterns and insights
5. Provide clear, concise descriptions
6. Use domain-appropriate terminology

### Output Format:
Provide your analysis in the following JSON format:

```json
{{
    "description": "<overall description of the data model>",
    "entities": [
        {{
            "name": "<entity name>",
            "description": "<entity description>",
            "key_attributes": ["<attribute1>", "<attribute2>", ...]
        }},
        ...
    ],
    "relationships": [
        {{
            "source": "<source entity>",
            "target": "<target entity>",
            "type": "<relationship type>",
            "description": "<relationship description>"
        }},
        ...
    ],
    "business_context": "<business context and domain description>"
}}
```

### Example Output:
```json
{{
    "description": "This data model represents a customer relationship management (CRM) system that tracks customer interactions, sales opportunities, and product information.",
    "entities": [
        {{
            "name": "customers",
            "description": "Stores information about customers including their contact details and preferences",
            "key_attributes": ["customer_id", "name", "email", "created_at"]
        }},
        {{
            "name": "opportunities",
            "description": "Tracks potential sales opportunities and their stages",
            "key_attributes": ["opportunity_id", "customer_id", "amount", "stage"]
        }}
    ],
    "relationships": [
        {{
            "source": "opportunities",
            "target": "customers",
            "type": "Many-to-One",
            "description": "Each opportunity is associated with one customer, while a customer can have multiple opportunities"
        }},
        ...
    ],
    "business_context": "This model supports a B2B sales organization by tracking customer interactions and sales pipeline. It enables analysis of customer behavior, sales performance, and opportunity conversion rates."
}}
```
"""

semantics_description_template = """
### Data Model Specification
{{mdl}}

### Language
{{language}}

Please analyze the data model and provide a comprehensive semantic description that explains its purpose, structure, and business context. Focus on making the description clear and accessible while using appropriate domain terminology.
"""


class SemanticsDescription:
    class Input(BaseModel):
        id: str
        mdl: str
        project_id: Optional[str] = None  # this is for tracing purpose
        configuration: Optional[Configuration] = Configuration()

    class Resource(BaseModel):
        class Error(BaseModel):
            code: Literal["OTHERS", "MDL_PARSE_ERROR", "RESOURCE_NOT_FOUND"]
            message: str

        id: str
        status: Literal["generating", "finished", "failed"] = "generating"
        response: Optional[dict] = None
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
        self._cache: Dict[str, SemanticsDescription.Resource] = TTLCache(
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

    @observe(name="Generate Semantics Description")
    async def describe(self, request: Input, **kwargs) -> Resource:
        logger.info("Generate Semantics Description pipeline is running...")
        trace_id = kwargs.get("trace_id")

        try:
            mdl_dict = orjson.loads(request.mdl)

            # Create prompt for semantics description
            prompt = PromptTemplate(
                input_variables=["mdl", "language"],
                template=semantics_description_template
            )
            
            # Generate semantics description using operator pattern
            result = await (
                self.llm
                | {
                    "system_prompt": semantics_description_system_prompt,
                    "user_prompt": prompt.format(
                        mdl=mdl_dict,
                        language=request.configuration.language or "English"
                    )
                }
            ).invoke()

            # Parse the result
            description = orjson.loads(result)
            
            # Update metrics
            self.doc_store_provider.update_metrics("semantics_description", "query")

            self._cache[request.id] = self.Resource(
                id=request.id,
                status="finished",
                response=description,
                trace_id=trace_id,
            )
        except orjson.JSONDecodeError as e:
            self._handle_exception(
                request,
                f"Failed to parse MDL: {str(e)}",
                code="MDL_PARSE_ERROR",
                trace_id=trace_id,
            )
        except Exception as e:
            self._handle_exception(
                request,
                f"An error occurred during semantics description generation: {str(e)}",
                trace_id=trace_id,
            )

        return self._cache[request.id]

    def __getitem__(self, id: str) -> Resource:
        response = self._cache.get(id)

        if response is None:
            message = f"Semantics Description Resource with ID '{id}' not found."
            logger.exception(message)
            return self.Resource(
                id=id,
                status="failed",
                error=self.Resource.Error(code="RESOURCE_NOT_FOUND", message=message),
            )

        return response

    def __setitem__(self, id: str, value: Resource):
        self._cache[id] = value

def create_semantics_description_tool(
    doc_store_provider: DocumentStoreProvider,
    maxsize: int = 1_000_000,
    ttl: int = 120,
) -> Tool:
    """Create Langchain tool for semantics description"""
    description_tool = SemanticsDescription(doc_store_provider, maxsize, ttl)
    
    def description_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(description_tool.describe(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="semantics_descriptor",
        description="Generates semantic descriptions of data models. Input should be JSON with 'id', 'mdl', and optional 'project_id' and configuration fields.",
        func=description_func
    )

if __name__ == "__main__":
    # Test the semantics description tool
    async def test_semantics_description():
        from app.core.dependencies import get_doc_store_provider
        
        doc_store_provider = get_doc_store_provider()
        description = SemanticsDescription(doc_store_provider)
        
        result = await description.describe(
            SemanticsDescription.Input(
                id="test",
                mdl='{"tables": [{"name": "customers", "columns": [{"name": "id", "type": "INT"}]}]}'
            )
        )
        
        print("Semantics Description Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(test_semantics_description())