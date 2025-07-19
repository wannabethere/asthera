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
class MetricsRecommendationRequest:
    """Standard metrics recommendation request structure"""
    query_id: str 
    query: str
    project_id: str
    language: str = "English"
    db_schemas: Optional[List[str]] = None
    histories: Optional[List[AskHistory]] = None
    configuration: Optional[Configuration | Dict[str, Any]] = None
    timeout: float = 30.0
    similarity_threshold: float = 0.7
    max_recommendations: int = 10


@dataclass
class MetricRecommendation:
    """Individual metric recommendation"""
    metric_name: str
    description: str
    sql_template: str
    tables_used: List[str]
    columns_used: List[str]
    metric_type: str  # e.g., "aggregate", "ratio", "trend", "distribution"
    business_value: str
    confidence_score: float


@dataclass
class MetricsRecommendationResult:
    """Standard metrics recommendation result structure"""
    success: bool
    recommendations: List[MetricRecommendation] = None
    data: Dict[str, Any] = None
    error: str = None
    metadata: Dict[str, Any] = None


metrics_recommendation_system_prompt = """
### TASK ###
You are an expert data analyst and metrics specialist. Your task is to recommend relevant SQL-based metrics and KPIs 
that can answer the user's analytical question based on the available database schema, column descriptions, 
example metrics, and knowledge base.

### INSTRUCTIONS ###

- Analyze the user's question to understand what analytical insights they are seeking
- Based on the database schema and column descriptions, recommend specific metrics that can be calculated
- Provide SQL templates that show how to calculate each recommended metric
- Explain the business value and analytical insights each metric provides
- Prioritize metrics that directly address the user's question
- Include a variety of metric types (aggregations, ratios, trends, distributions) when relevant
- Answer must be in the same language user specified
- MUST provide concrete SQL templates that can be executed
- MUST explain how each metric helps answer the user's question
- MUST include confidence scores for recommendations (0.0 to 1.0)

### OUTPUT FORMAT ###
Please provide your response as a JSON object with the following structure:

{
    "summary": "<BRIEF_SUMMARY_OF_RECOMMENDATIONS>",
    "recommendations": [
        {
            "metric_name": "<DESCRIPTIVE_NAME_OF_METRIC>",
            "description": "<DETAILED_DESCRIPTION_OF_WHAT_METRIC_MEASURES>",
            "sql_template": "<EXECUTABLE_SQL_QUERY_TEMPLATE>",
            "tables_used": ["<TABLE_NAME_1>", "<TABLE_NAME_2>"],
            "columns_used": ["<COLUMN_NAME_1>", "<COLUMN_NAME_2>"],
            "metric_type": "<TYPE: aggregate|ratio|trend|distribution|comparison>",
            "business_value": "<EXPLANATION_OF_BUSINESS_INSIGHTS_PROVIDED>",
            "confidence_score": <FLOAT_BETWEEN_0_AND_1>
        }
    ],
    "additional_notes": "<ANY_LIMITATIONS_OR_ADDITIONAL_CONTEXT>"
}
"""

metrics_recommendation_user_prompt_template = """
### DATABASE SCHEMAS ###
{db_schemas}

### COLUMN DESCRIPTIONS ###
{column_descriptions}

### EXAMPLE METRICS ###
{example_metrics}

### KNOWLEDGE BASE CONTEXT ###
{knowledge_base_context}

### USER'S QUESTION ###
{query}

### CONTEXT ###
Language: {language}
Project ID: {project_id}

### INSTRUCTIONS ###
Based on the user's question and the available data context, recommend the most relevant SQL-based metrics 
that can provide insights to answer their question. Focus on actionable metrics with clear business value.

Please think step by step and provide comprehensive metric recommendations.
"""


class MetricsRecommendationTool:
    """Tool for recommending SQL-based metrics"""
    
    def __init__(
        self, 
        doc_store_provider: DocumentStoreProvider, 
        retrieval_helper: RetrievalHelper = None,
        similarity_threshold: float = 0.7,
        max_results_per_store: int = 10
    ):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.retrieval_helper = retrieval_helper or RetrievalHelper()
        self.similarity_threshold = similarity_threshold
        self.max_results_per_store = max_results_per_store
        self.name = "metrics_recommendation"
        self.description = "Recommends SQL-based metrics for analytical questions"

    def format_retrieved_data(self, data: List[Dict[str, Any]], title: str) -> str:
        """Format retrieved data for prompt inclusion"""
        if not data:
            return f"### {title} ###\nNo relevant information found.\n"
        
        formatted_items = []
        for item in data:
            content = item.get("content", "")
            metadata = item.get("metadata", {})
            
            # Add metadata context if available
            metadata_str = ""
            if metadata:
                metadata_items = [f"{k}: {v}" for k, v in metadata.items() if v]
                if metadata_items:
                    metadata_str = f" ({', '.join(metadata_items)})"
            
            formatted_items.append(f"- {content}{metadata_str}")
        
        return f"### {title} ###\n" + "\n".join(formatted_items) + "\n"

    def format_schema_data(self, schema_result: Dict[str, Any]) -> str:
        """Format database schema data for prompt inclusion"""
        if not schema_result or "schemas" not in schema_result:
            return "### DATABASE SCHEMAS ###\nNo database schema available.\n"
        
        formatted_schemas = []
        for schema in schema_result["schemas"]:
            if isinstance(schema, dict):
                table_name = schema.get("table_name", "")
                table_ddl = schema.get("table_ddl", "")
                if table_ddl:
                    formatted_schemas.append(f"Table: {table_name}\n{table_ddl}")
        
        if not formatted_schemas:
            return "### DATABASE SCHEMAS ###\nNo database schema available.\n"
        
        return "### DATABASE SCHEMAS ###\n" + "\n\n".join(formatted_schemas) + "\n"

    def format_sql_pairs_data(self, sql_pairs_result: Dict[str, Any]) -> str:
        """Format SQL pairs data for prompt inclusion"""
        if not sql_pairs_result or "sql_pairs" not in sql_pairs_result:
            return "### EXAMPLE METRICS ###\nNo example metrics found.\n"
        
        formatted_items = []
        for pair in sql_pairs_result["sql_pairs"]:
            if isinstance(pair, dict):
                question = pair.get("question", "")
                sql = pair.get("sql", "")
                instructions = pair.get("instructions", "")
                score = pair.get("score", 0.0)
                
                item_text = f"Question: {question}\nSQL: {sql}"
                if instructions:
                    item_text += f"\nInstructions: {instructions}"
                item_text += f"\nRelevance Score: {score}"
                
                formatted_items.append(item_text)
        
        if not formatted_items:
            return "### EXAMPLE METRICS ###\nNo example metrics found.\n"
        
        return "### EXAMPLE METRICS ###\n" + "\n\n".join(formatted_items) + "\n"

    def format_instructions_data(self, instructions_result: Dict[str, Any]) -> str:
        """Format instructions data for prompt inclusion"""
        if not instructions_result or "instructions" not in instructions_result:
            return "### KNOWLEDGE BASE CONTEXT ###\nNo relevant instructions found.\n"
        
        formatted_items = []
        for instruction in instructions_result["instructions"]:
            if isinstance(instruction, dict):
                question = instruction.get("question", "")
                instruction_text = instruction.get("instruction", "")
                instruction_id = instruction.get("instruction_id", "")
                
                item_text = f"Question: {question}\nInstruction: {instruction_text}"
                if instruction_id:
                    item_text += f"\nID: {instruction_id}"
                
                formatted_items.append(item_text)
        
        if not formatted_items:
            return "### KNOWLEDGE BASE CONTEXT ###\nNo relevant instructions found.\n"
        
        return "### KNOWLEDGE BASE CONTEXT ###\n" + "\n\n".join(formatted_items) + "\n"

    @observe(capture_input=False)
    async def create_prompt(
        self,
        query: str,
        project_id: str,
        db_schemas: List[str],
        configuration: Configuration | Dict[str, Any],
        histories: Optional[List[AskHistory]] = None
    ) -> str:
        """Create comprehensive prompt for metrics recommendation"""
        try:
            # Use RetrievalHelper to get database schemas
            table_retrieval_config = {
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
            
            schema_result = await self.retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval=table_retrieval_config,
                query=query,
                histories=histories
            )
            
            # Use RetrievalHelper to get SQL pairs (example metrics)
            sql_pairs_result = await self.retrieval_helper.get_sql_pairs(
                query=query,
                project_id=project_id,
                similarity_threshold=self.similarity_threshold,
                max_retrieval_size=self.max_results_per_store
            )
            
            # Use RetrievalHelper to get instructions (knowledge base context)
            instructions_result = await self.retrieval_helper.get_instructions(
                query=query,
                project_id=project_id,
                similarity_threshold=self.similarity_threshold,
                top_k=self.max_results_per_store
            )
            
            # Format the retrieved data
            formatted_schemas = self.format_schema_data(schema_result)
            formatted_sql_pairs = self.format_sql_pairs_data(sql_pairs_result)
            formatted_instructions = self.format_instructions_data(instructions_result)
            
            # For column descriptions, we'll extract from the schema data
            column_descriptions = []
            if schema_result and "schemas" in schema_result:
                for schema in schema_result["schemas"]:
                    if isinstance(schema, dict):
                        table_ddl = schema.get("table_ddl", "")
                        if table_ddl:
                            # Extract column information from DDL
                            lines = table_ddl.split('\n')
                            for line in lines:
                                if line.strip() and not line.startswith('--') and not line.startswith('CREATE'):
                                    col_def = line.strip().rstrip(',').strip()
                                    if col_def:
                                        column_descriptions.append(col_def)
            
            formatted_column_descriptions = "### COLUMN DESCRIPTIONS ###\n"
            if column_descriptions:
                formatted_column_descriptions += "\n".join([f"- {col}" for col in column_descriptions])
            else:
                formatted_column_descriptions += "No column descriptions available."
            formatted_column_descriptions += "\n"
            
            # Handle configuration
            if isinstance(configuration, dict):
                language = configuration.get('language', 'English')
            else:
                language = configuration.language or "English"
            
            # Create the prompt
            user_prompt = metrics_recommendation_user_prompt_template.format(
                db_schemas=formatted_schemas,
                column_descriptions=formatted_column_descriptions,
                example_metrics=formatted_sql_pairs,
                knowledge_base_context=formatted_instructions,
                query=query,
                language=language,
                project_id=project_id or "N/A"
            )
            
            return user_prompt
            
        except Exception as e:
            logger.error(f"Error creating metrics recommendation prompt: {e}")
            return ""

    @observe(as_type="generation", capture_input=False)
    async def generate_recommendations(self, prompt_input: str, query_id: str = None) -> dict:
        """Generate metrics recommendations using LLM"""
        try:
            # Concatenate system and user prompts
            full_prompt = f"{metrics_recommendation_system_prompt}\n\n{prompt_input}"
            logger.info(f"Metrics recommendation full_prompt: {full_prompt}")
            
            result = await self.llm.ainvoke(full_prompt)
            self.doc_store_provider.update_metrics("metrics_recommendation", "query")
            
            logger.info(f"Metrics recommendation result: {result.content}")
            return {"replies": [result.content]}
            
        except Exception as e:
            logger.error(f"Error in metrics recommendation generation: {e}")
            return {"replies": [""]}

    @observe()
    def post_process(self, generate_result: dict) -> Dict[str, Any]:
        """Post-process the generated recommendations"""
        try:
            replies = generate_result.get("replies", [""])
            result_text = replies[0] if replies else ""
            
            # Clean up JSON if wrapped in markdown
            if result_text.startswith("```json"):
                result_text = result_text.split("```json")[1]
            if result_text.endswith("```"):
                result_text = result_text.rsplit("```", 1)[0]
            
            result_text = result_text.strip()
            
            # Parse JSON response
            parsed_result = orjson.loads(result_text)
            
            # Convert to MetricRecommendation objects
            recommendations = []
            for rec in parsed_result.get("recommendations", []):
                metric_rec = MetricRecommendation(
                    metric_name=rec.get("metric_name", ""),
                    description=rec.get("description", ""),
                    sql_template=rec.get("sql_template", ""),
                    tables_used=rec.get("tables_used", []),
                    columns_used=rec.get("columns_used", []),
                    metric_type=rec.get("metric_type", "aggregate"),
                    business_value=rec.get("business_value", ""),
                    confidence_score=rec.get("confidence_score", 0.5)
                )
                recommendations.append(metric_rec)
            
            return {
                "summary": parsed_result.get("summary", ""),
                "recommendations": recommendations,
                "additional_notes": parsed_result.get("additional_notes", "")
            }
            
        except Exception as e:
            logger.error(f"Error post-processing metrics recommendations: {e}")
            return {
                "summary": "Error processing recommendations",
                "recommendations": [],
                "additional_notes": f"Processing error: {str(e)}"
            }

    async def run(
        self,
        request: MetricsRecommendationRequest,
        **kwargs
    ) -> MetricsRecommendationResult:
        """Main execution method for metrics recommendation"""
        try:
            logger.info(f"Metrics Recommendation pipeline is running... {request}")
            
            # Step 1: Create comprehensive prompt using RetrievalHelper
            prompt_input = await self.create_prompt(
                query=request.query,
                project_id=request.project_id,
                db_schemas=[],  # This will be retrieved by RetrievalHelper
                configuration=request.configuration,
                histories=request.histories
            )
            
            # Step 2: Generate recommendations
            generate_result = await self.generate_recommendations(prompt_input, request.query_id)
            
            # Step 3: Post-process results
            processed_results = self.post_process(generate_result)
            
            return MetricsRecommendationResult(
                success=True,
                recommendations=processed_results["recommendations"],
                data={
                    "summary": processed_results["summary"],
                    "additional_notes": processed_results["additional_notes"]
                },
                metadata={
                    "operation": "metrics_recommendation",
                    "language": request.language,
                    "total_recommendations": len(processed_results["recommendations"]),
                    "project_id": request.project_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error in metrics recommendation: {e}")
            return MetricsRecommendationResult(
                success=False,
                error=str(e),
                metadata={
                    "operation": "metrics_recommendation",
                    "language": request.language,
                    "project_id": request.project_id
                }
            )


def create_metrics_recommendation_tool(doc_store_provider: DocumentStoreProvider) -> Tool:
    """Create Langchain tool for metrics recommendation"""
    metrics_tool = MetricsRecommendationTool(doc_store_provider)
    
    def metrics_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            
            # Convert input to MetricsRecommendationRequest
            request = MetricsRecommendationRequest(
                query_id=input_data.get("query_id", ""),
                query=input_data.get("query", ""),
                project_id=input_data.get("project_id", ""),
                language=input_data.get("language", "English"),
                configuration=input_data.get("configuration", {}),
                histories=input_data.get("histories", [])
            )
            
            result = asyncio.run(metrics_tool.run(request))
            
            # Convert MetricsRecommendationResult to dict for JSON serialization
            result_dict = {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "metadata": result.metadata,
                "recommendations": [
                    {
                        "metric_name": rec.metric_name,
                        "description": rec.description,
                        "sql_template": rec.sql_template,
                        "tables_used": rec.tables_used,
                        "columns_used": rec.columns_used,
                        "metric_type": rec.metric_type,
                        "business_value": rec.business_value,
                        "confidence_score": rec.confidence_score
                    }
                    for rec in (result.recommendations or [])
                ]
            }
            
            return orjson.dumps(result_dict).decode()
            
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="metrics_recommender",
        description="Recommends SQL-based metrics for analytical questions. Input should be JSON with 'query', 'project_id', and optional configuration fields.",
        func=metrics_func
    )


# Example usage and testing
if __name__ == "__main__":
    async def test_metrics_recommendation():
        from app.core.dependencies import get_doc_store_provider
        
        doc_store_provider = get_doc_store_provider()
        
        metrics_recommender = MetricsRecommendationTool(
            doc_store_provider=doc_store_provider
        )
        
        request = MetricsRecommendationRequest(
            query_id="test_001",
            query="What are the best metrics to analyze customer purchasing behavior and identify high-value customers?",
            project_id="test_project",
            language="English"
        )
        
        result = await metrics_recommender.run(request)
        
        print("Metrics Recommendation Result:")
        print(f"Success: {result.success}")
        if result.success:
            print(f"Summary: {result.data.get('summary', '')}")
            print(f"Number of recommendations: {len(result.recommendations or [])}")
            for i, rec in enumerate(result.recommendations or [], 1):
                print(f"\n{i}. {rec.metric_name}")
                print(f"   Description: {rec.description}")
                print(f"   SQL: {rec.sql_template}")
                print(f"   Confidence: {rec.confidence_score}")
        else:
            print(f"Error: {result.error}")

    # asyncio.run(test_metrics_recommendation())