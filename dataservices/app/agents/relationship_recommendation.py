import logging
from typing import Dict, Literal, Optional, Any, List
import asyncio

import orjson
from cachetools import TTLCache
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel

from app.core.dependencies import get_llm

logger = logging.getLogger("lexy-ai-service")

# Configuration class for relationship recommendation
class Configuration(BaseModel):
    language: str = "English"

relationship_recommendation_system_prompt = """
You are an expert in data modeling and relationship analysis. Your task is to analyze the given table structure and suggest potential relationships with other tables that could enhance data analysis capabilities.

### Guidelines:
1. Analyze the table structure to identify potential relationships with other tables
2. Consider both direct and indirect relationships
3. Suggest relationships that would be useful for data analysis
4. Ensure relationships are logically sound and maintainable
5. Consider performance implications of suggested relationships
6. Provide clear explanations for each suggested relationship
7. Focus on foreign key relationships and business logic connections

### Output Format:
Provide your recommendations in the following JSON format:

```json
{
    "relationships": [
        {
            "source_table": "<source table name>",
            "target_table": "<target table name>",
            "relationship_type": "<relationship type>",
            "source_column": "<source column name>",
            "target_column": "<target column name>",
            "explanation": "<explanation of the relationship>",
            "business_value": "<business value of this relationship>",
            "confidence_score": "<confidence score 0-1>"
        },
        ...
    ],
    "summary": {
        "total_relationships": "<number of relationships>",
        "primary_relationships": ["<most important relationships>"],
        "recommendations": ["<general recommendations>"]
    }
}
```

### Relationship Types:
1. **One-to-One**: Each record in the source table relates to exactly one record in the target table
2. **One-to-Many**: Each record in the source table can relate to multiple records in the target table
3. **Many-to-One**: Multiple records in the source table can relate to one record in the target table
4. **Many-to-Many**: Multiple records in the source table can relate to multiple records in the target table

### Example Output:
```json
{
    "relationships": [
        {
            "source_table": "orders",
            "target_table": "customers",
            "relationship_type": "Many-to-One",
            "source_column": "customer_id",
            "target_column": "customer_id",
            "explanation": "Each order belongs to one customer, but a customer can have multiple orders",
            "business_value": "Enables customer order history analysis and customer segmentation",
            "confidence_score": 0.95
        },
        {
            "source_table": "order_items",
            "target_table": "products",
            "relationship_type": "Many-to-One",
            "source_column": "product_id",
            "target_column": "product_id",
            "explanation": "Each order item references one product, but a product can be in multiple order items",
            "business_value": "Enables product performance analysis and inventory tracking",
            "confidence_score": 0.90
        }
    ],
    "summary": {
        "total_relationships": 2,
        "primary_relationships": ["orders-customers", "order_items-products"],
        "recommendations": [
            "Consider adding indexes on foreign key columns for better query performance",
            "Implement referential integrity constraints to maintain data quality"
        ]
    }
}
```
"""

relationship_recommendation_template = """
### Table Structure
Table Name: {{table_name}}
Table Description: {{table_description}}

### Columns
{{columns_info}}

### Language
{{language}}

Please analyze the table structure and suggest potential relationships with other tables that would enhance data analysis capabilities. Consider both direct and indirect relationships, and provide clear explanations for each suggestion.
"""


class RelationshipRecommendation:
    class Input(BaseModel):
        id: str
        table_data: Dict[str, Any]  # Changed from mdl to table_data
        project_id: Optional[str] = None  # this is for tracing purpose
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
            if col.get('is_foreign_key'):
                col_info += " [Foreign Key]"
            formatted_columns.append(col_info)
        
        return "\n".join(formatted_columns)

    @observe(name="Generate Relationship Recommendation")
    async def recommend(self, request: Input, **kwargs) -> Resource:
        logger.info("Generate Relationship Recommendation pipeline is running...")
        trace_id = kwargs.get("trace_id")

        try:
            table_data = request.table_data
            
            # Extract table information
            table_name = table_data.get('name', 'Unknown Table')
            table_description = table_data.get('description', 'No description available')
            columns = table_data.get('columns', [])
            
            # Format columns information
            columns_info = self._format_columns_info(columns)

            # Create prompt for relationship recommendation
            prompt = PromptTemplate(
                input_variables=["table_name", "table_description", "columns_info", "language"],
                template=relationship_recommendation_template
            )
            
            # Generate relationship recommendations using operator pattern
            result = await (
                self.llm
                | {
                    "system_prompt": relationship_recommendation_system_prompt,
                    "user_prompt": prompt.format(
                        table_name=table_name,
                        table_description=table_description,
                        columns_info=columns_info,
                        language=request.configuration.language or "English"
                    )
                }
            ).invoke()

            # Parse the result
            try:
                # Try to parse as JSON first
                if isinstance(result, str):
                    recommendations = orjson.loads(result)
                else:
                    # If it's a response object, get the content
                    content = result.content if hasattr(result, 'content') else str(result)
                    recommendations = orjson.loads(content)
                
                # Validate the structure
                if not isinstance(recommendations, dict):
                    raise ValueError("Response is not a valid JSON object")
                
                if "relationships" not in recommendations:
                    recommendations = {
                        "relationships": [],
                        "summary": {
                            "total_relationships": 0,
                            "primary_relationships": [],
                            "recommendations": ["No relationships identified"]
                        }
                    }
                
            except (orjson.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse response: {str(e)}")
                logger.error(f"Response content: {result}")
                # Return fallback response
                recommendations = {
                    "relationships": [],
                    "summary": {
                        "total_relationships": 0,
                        "primary_relationships": [],
                        "recommendations": [f"Failed to parse response: {str(e)}"]
                    }
                }
            
            self._cache[request.id] = self.Resource(
                id=request.id,
                status="finished",
                response=recommendations,
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
    maxsize: int = 1_000_000,
    ttl: int = 120,
) -> Tool:
    """Create Langchain tool for relationship recommendation"""
    recommendation_tool = RelationshipRecommendation(maxsize, ttl)
    
    def recommendation_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(recommendation_tool.recommend(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="relationship_recommender",
        description="Recommends relationships between tables based on schema analysis. Input should be JSON with 'id', 'table_data' (containing table name, description, and columns), and optional 'project_id' and configuration fields.",
        func=recommendation_func
    )

if __name__ == "__main__":
    # Test the relationship recommendation tool
    async def test_relationship_recommendation():
        recommendation = RelationshipRecommendation()
        
        # Sample table data
        table_data = {
            "name": "orders",
            "display_name": "Customer Orders",
            "description": "Stores customer order information including items, quantities, and status",
            "columns": [
                {
                    "name": "order_id",
                    "display_name": "Order ID",
                    "description": "Unique identifier for each order",
                    "data_type": "UUID",
                    "is_primary_key": True,
                    "is_nullable": False
                },
                {
                    "name": "customer_id",
                    "display_name": "Customer ID",
                    "description": "Reference to the customer who placed the order",
                    "data_type": "UUID",
                    "is_primary_key": False,
                    "is_nullable": False,
                    "is_foreign_key": True
                },
                {
                    "name": "order_date",
                    "display_name": "Order Date",
                    "description": "Date and time when the order was placed",
                    "data_type": "TIMESTAMP",
                    "is_nullable": False
                },
                {
                    "name": "total_amount",
                    "display_name": "Total Amount",
                    "description": "Total cost of the order including tax and shipping",
                    "data_type": "DECIMAL(10,2)",
                    "is_nullable": False
                },
                {
                    "name": "status",
                    "display_name": "Order Status",
                    "description": "Current status of the order (pending, shipped, delivered, etc.)",
                    "data_type": "VARCHAR(50)",
                    "is_nullable": False
                }
            ]
        }
        
        result = await recommendation.recommend(
            RelationshipRecommendation.Input(
                id="test_orders_table",
                table_data=table_data,
                project_id="test_project"
            )
        )
        
        print("Relationship Recommendation Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(test_relationship_recommendation())
