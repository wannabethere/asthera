import logging
from typing import Any, Dict, List, Optional, Union, Literal
from dataclasses import dataclass
import asyncio

import orjson
from langchain_openai import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.tools import Tool

from cachetools import TTLCache
from langchain.prompts import PromptTemplate,ChatPromptTemplate
from langchain_core.runnables import RunnableMap
import re

# Import langfuse compatibility layer
from app.utils.langfuse_compat import observe

from pydantic import BaseModel
from app.core.dependencies import get_llm
from dotenv import load_dotenv

load_dotenv()


logger = logging.getLogger("lexy-ai-service")

# Configuration class for semantics description
class Configuration(BaseModel):
    language: str = "English"

semantics_description_system_prompt = """
You are an expert in data modeling and semantic analysis. Your task is to analyze the given table structure and provide a clear, concise description of its semantic meaning and business context.

### Guidelines:
1. Analyze the table structure to understand its purpose and data organization
2. Identify key columns and their business significance
3. Explain the business context and domain
4. Highlight important patterns and insights
5. Provide clear, concise descriptions
6. Use domain-appropriate terminology

### Output Format:
Provide your analysis in the following JSON format:

```json
{{
    "description": "<overall description of the table and its purpose>",
    "table_purpose": "<specific business purpose of this table>",
    "key_columns": [
        {{
            "name": "<column name>",
            "description": "<column description>",
            "business_significance": "<why this column is important>",
            "data_type": "<data type>"
        }},
        ...
    ],
    "business_context": "<business context and domain description>",
    "data_patterns": ["<pattern1>", "<pattern2>", ...],
    "suggested_relationships": [
        {{
            "related_entity": "<potential related table/entity>",
            "relationship_type": "<relationship type>",
            "reasoning": "<why this relationship makes sense>"
        }},
        ...
    ]
}}
```

### Example Output:
```json
{{
    "description": "This table represents customer information in a CRM system, storing essential customer details for relationship management and sales tracking.",
    "table_purpose": "Central repository for customer master data including contact information, demographics, and account status.",
    "key_columns": [
        {{
            "name": "customer_id",
            "description": "Unique identifier for each customer",
            "business_significance": "Primary key used to link customer data across the system",
            "data_type": "UUID"
        }},
        {{
            "name": "email",
            "description": "Customer's primary email address",
            "business_significance": "Used for communication and account identification",
            "data_type": "VARCHAR"
        }},
        {{
            "name": "created_at",
            "description": "Timestamp when customer record was created",
            "business_significance": "Tracks customer acquisition date for lifecycle analysis",
            "data_type": "TIMESTAMP"
        }}
    ],
    "business_context": "This table supports customer relationship management by providing a single source of truth for customer information. It enables customer segmentation, communication tracking, and sales pipeline management.",
    "data_patterns": ["Customer identification", "Contact information management", "Account lifecycle tracking"],
    "suggested_relationships": [
        {{
            "related_entity": "orders",
            "relationship_type": "One-to-Many",
            "reasoning": "Each customer can have multiple orders, enabling order history and purchase analysis"
        }},
        {{
            "related_entity": "customer_segments",
            "relationship_type": "Many-to-Many",
            "reasoning": "Customers can belong to multiple segments for targeted marketing and analysis"
        }}
    ]
}}
```
"""

semantics_description_template = """
### Table Structure
Table Name: {table_name}
Table Description: {table_description}

### Columns
{columns_info}

### Language
{language}

Please analyze the table structure and provide a comprehensive semantic description that explains its purpose, structure, and business context. Focus on making the description clear and accessible while using appropriate domain terminology.
"""


class SemanticsDescription:
    class Input(BaseModel):
        id: str
        table_data: Dict[str, Any]  # Changed from mdl to table_data
        domain_id: Optional[str] = None  # this is for tracing purpose
        configuration: Optional[Configuration] = Configuration()

    class Resource(BaseModel):
        class Error(BaseModel):
            code: Literal["OTHERS", "TABLE_PARSE_ERROR", "RESOURCE_NOT_FOUND"]
            message: str

        id: str
        status: Literal["generating", "finished", "failed"] = "generating"
        response: Optional[dict] = None
        error: Optional[Error] = None
        trace_id: Optional[str] = None

    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
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

    def _format_columns_info(self, columns: List[Dict[str, Any]]) -> str:
        """Format columns information for the prompt"""
        if not columns:
            return "No columns defined"
        
        formatted_columns = []
        for col in columns:
            col_info = f"- {col.get('name', 'Unknown')}"
            if col.get('display_name') and col.get('display_name') != col.get('name'):
                col_info += f" (Display: {col.get('display_name')})"
            if col.get('description'):
                col_info += f": {col.get('description')}"
            if col.get('data_type'):
                col_info += f" [Type: {col.get('data_type')}]"
            if col.get('is_primary_key'):
                col_info += " [Primary Key]"
            if col.get('is_nullable') is False:
                col_info += " [Not Null]"
            formatted_columns.append(col_info)
        
        return "\n".join(formatted_columns)

    async def describe(self, request: Input, **kwargs) -> Resource:
        logger.info("Generate Semantics Description pipeline is running...")
        trace_id = kwargs.get("trace_id")

        try:
            table_data = request.table_data
            
            # Extract table information
            table_name = table_data.get('name', 'Unknown Table')
            table_description = table_data.get('description', 'No description available')
            columns = table_data.get('columns', [])
            
            # Format columns information
            columns_info = self._format_columns_info(columns)
            print(f"tablename,tabledescription,columnsinfo",table_name,table_description,columns_info)

            # Create prompt for semantics description
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", semantics_description_system_prompt),
                ("human", semantics_description_template)
            ])

            # Runnable chain
            chain = (
                RunnableMap({
                    "table_name": lambda x: table_name,
                    "table_description": lambda x: table_description,
                    "columns_info": lambda x: columns_info,
                    "language": lambda x: request.configuration.language or "English"
                })
                | chat_prompt  # Converts into BaseMessages
                | self.llm      
            )

            result = await chain.ainvoke({})
            

            content = result.content.strip()

            # Remove ```json ... ```
            if content.startswith("```json"):
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)

            try:
                print("Got content from llm",content)
                description = orjson.loads(content)
                print("description from llm",description)

            except orjson.JSONDecodeError as e:
                logger.error(f"Failed to parse cleaned LLM response: {str(e)}")
                raise

            
            self._cache[request.id] = self.Resource(
                id=request.id,
                status="finished",
                response=description,
                trace_id=trace_id,
            )
        except orjson.JSONDecodeError as e:
            self._handle_exception(
                request,
                f"Failed to parse table data: {str(e)}",
                code="TABLE_PARSE_ERROR",
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
    maxsize: int = 1_000_000,
    ttl: int = 120,
) -> Tool:
    """Create Langchain tool for semantics description"""
    description_tool = SemanticsDescription(maxsize, ttl)
    
    def description_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(description_tool.describe(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="semantics_descriptor",
        description="Generates semantic descriptions of table structures. Input should be JSON with 'id', 'table_data' (containing table name, description, and columns), and optional 'project_id' and configuration fields.",
        func=description_func
    )

if __name__ == "__main__":
    # Test the semantics description tool
    async def test_semantics_description():
        description = SemanticsDescription()
        
        # Sample table data
        table_data = {
            "name": "customers",
            "display_name": "Customer Information",
            "description": "Stores customer master data including contact information and account details",
            "columns": [
                {
                    "name": "customer_id",
                    "display_name": "Customer ID",
                    "description": "Unique identifier for each customer",
                    "data_type": "UUID",
                    "is_primary_key": True,
                    "is_nullable": False
                },
                {
                    "name": "email",
                    "display_name": "Email Address",
                    "description": "Customer's primary email address",
                    "data_type": "VARCHAR(255)",
                    "is_nullable": False
                },
                {
                    "name": "created_at",
                    "display_name": "Created Date",
                    "description": "Timestamp when customer record was created",
                    "data_type": "TIMESTAMP",
                    "is_nullable": False
                }
            ]
        }
        
        result = await description.describe(
            SemanticsDescription.Input(
                id="test",
                table_data=table_data
            )
        )
        
        print("Semantics Description Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(test_semantics_description())