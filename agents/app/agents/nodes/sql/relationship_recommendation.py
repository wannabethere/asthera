import logging
from typing import Dict, Literal, Optional
import asyncio

import orjson
from cachetools import TTLCache
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel

from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration


logger = logging.getLogger("lexy-ai-service")

relationship_recommendation_system_prompt = """
You are an expert in data modeling and relationship analysis. Your task is to analyze the given data model and suggest potential relationships between entities that could enhance data analysis capabilities.

### Guidelines:
1. Analyze the data model to identify potential relationships between entities
2. Consider both direct and indirect relationships
3. Suggest relationships that would be useful for data analysis
4. Ensure relationships are logically sound and maintainable
5. Consider performance implications of suggested relationships
6. Provide clear explanations for each suggested relationship

### Output Format:
Provide your recommendations in the following JSON format:

```json
{
    "relationships": [
        {
            "source": "<source entity name>",
            "target": "<target entity name>",
            "type": "<relationship type>",
            "explanation": "<explanation of the relationship>"
        },
        ...
    ]
}
```

### Relationship Types:
1. **One-to-One**: Each record in the source entity relates to exactly one record in the target entity
2. **One-to-Many**: Each record in the source entity can relate to multiple records in the target entity
3. **Many-to-One**: Multiple records in the source entity can relate to one record in the target entity
4. **Many-to-Many**: Multiple records in the source entity can relate to multiple records in the target entity

### Example Output:
```json
{
    "relationships": [
        {
            "source": "orders",
            "target": "customers",
            "type": "Many-to-One",
            "explanation": "Each order belongs to one customer, but a customer can have multiple orders"
        },
        {
            "source": "products",
            "target": "categories",
            "type": "Many-to-One",
            "explanation": "Each product belongs to one category, but a category can contain multiple products"
        }
    ]
}
```
"""

relationship_recommendation_template = """
### Data Model Specification
{{mdl}}

### Language
{{language}}

Please analyze the data model and suggest potential relationships between entities that would enhance data analysis capabilities. Consider both direct and indirect relationships, and provide clear explanations for each suggestion.
"""


class RelationshipRecommendation:
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
        self._cache: Dict[str, RelationshipRecommendation.Resource] = TTLCache(
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

    @observe(name="Generate Relationship Recommendation")
    async def recommend(self, request: Input, **kwargs) -> Resource:
        logger.info("Generate Relationship Recommendation pipeline is running...")
        trace_id = kwargs.get("trace_id")

        try:
            mdl_dict = orjson.loads(request.mdl)
            print(f"MDL: {mdl_dict}")
            
            # Create prompt for relationship recommendation
            prompt = PromptTemplate(
                input_variables=["mdl", "language"],
                template=relationship_recommendation_template
            )
            print(f"Prompt: {prompt}")
            
            # Format the prompt first
            formatted_prompt = prompt.format(
                mdl=mdl_dict,
                language=request.configuration.language or "English"
            )
            print(f"Formatted prompt: {formatted_prompt}")
            
            # Create the chain
            chain = prompt | self.llm
            print(f"Chain is created")
            
            # Generate relationships
            result = await chain.ainvoke({
                "mdl": mdl_dict,
                "language": request.configuration.language or "English"
            })
            print(f"Result: {result}")
            
            # Parse the result
            try:
                # Get the markdown content directly
                recommendations = {"content": result.content}
            except Exception as e:
                logger.error(f"Failed to parse response: {str(e)}")
                logger.error(f"Response content: {result}")
                self._handle_exception(
                    request,
                    f"Failed to parse response: {str(e)}",
                    code="OTHERS",
                    trace_id=trace_id,
                )
                return self._cache[request.id]
            
            # Update metrics
            self.doc_store_provider.update_metrics("relationship_recommendation", "query")

            self._cache[request.id] = self.Resource(
                id=request.id,
                status="finished",
                response=recommendations,
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
                f"An error occurred during relationship recommendation generation: {str(e)}",
                trace_id=trace_id,
            )

        return self._cache[request.id]

    def __getitem__(self, id: str) -> Resource:
        response = self._cache.get(id)

        if response is None:
            message = f"Relationship Recommendation Resource with ID '{id}' not found."
            logger.exception(message)
            return self.Resource(
                id=id,
                status="failed",
                error=self.Resource.Error(code="RESOURCE_NOT_FOUND", message=message),
            )

        return response

    def __setitem__(self, id: str, value: Resource):
        self._cache[id] = value

def create_relationship_recommendation_tool(
    doc_store_provider: DocumentStoreProvider,
    maxsize: int = 1_000_000,
    ttl: int = 120,
) -> Tool:
    """Create Langchain tool for relationship recommendation"""
    recommendation_tool = RelationshipRecommendation(doc_store_provider, maxsize, ttl)
    
    def recommendation_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(recommendation_tool.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="relationship_recommender",
        description="Recommends relationships between tables based on schema analysis. Input should be JSON with 'project_id' and optional configuration fields.",
        func=recommendation_func
    )
