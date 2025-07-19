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
class SQLQuestionSuggestionRequest:
    """Standard SQL question suggestion request structure"""
    query_id: str 
    query: str
    project_id: str
    language: str = "English"
    db_schemas: Optional[List[str]] = None
    histories: Optional[List[AskHistory]] = None
    configuration: Optional[Configuration | Dict[str, Any]] = None
    timeout: float = 30.0
    similarity_threshold: float = 0.7
    max_suggestions: int = 15


@dataclass
class QuestionSuggestion:
    """Individual question suggestion"""
    question: str
    description: str
    example_sql: str
    tables_involved: List[str]
    columns_involved: List[str]
    difficulty_level: str  # e.g., "beginner", "intermediate", "advanced"
    category: str  # e.g., "revenue_analysis", "customer_behavior", "product_performance"
    business_value: str
    confidence_score: float


@dataclass
class SQLQuestionSuggestionResult:
    """Standard SQL question suggestion result structure"""
    success: bool
    suggestions: List[QuestionSuggestion] = None
    data: Dict[str, Any] = None
    error: str = None
    metadata: Dict[str, Any] = None


sql_question_suggestion_system_prompt = """
### TASK ###
You are an expert data analyst and SQL specialist. Your task is to suggest relevant and interesting SQL questions 
that can be asked about the available dataset based on the database schema, column descriptions, example SQL queries, 
and domain knowledge.

### INSTRUCTIONS ###

- Analyze the database schema to understand what data is available
- Based on the SQL examples and patterns, suggest similar but varied questions that can be answered
- Provide a diverse range of questions covering different business areas and difficulty levels
- Include executable SQL examples that demonstrate how each question can be answered
- Categorize questions by business domain (e.g., revenue, customer behavior, product performance)
- Provide beginner, intermediate, and advanced level questions
- Answer must be in the same language user specified
- MUST provide concrete SQL examples that can be executed
- MUST explain the business value and insights each question provides
- MUST include confidence scores for suggestions (0.0 to 1.0)

### OUTPUT FORMAT ###
Please provide your response as a JSON object with the following structure:

{
    "summary": "<BRIEF_SUMMARY_OF_QUESTION_SUGGESTIONS>",
    "suggestions": [
        {
            "question": "<CLEAR_BUSINESS_QUESTION>",
            "description": "<DETAILED_DESCRIPTION_OF_WHAT_QUESTION_EXPLORES>",
            "example_sql": "<EXECUTABLE_SQL_QUERY_EXAMPLE>",
            "tables_involved": ["<TABLE_NAME_1>", "<TABLE_NAME_2>"],
            "columns_involved": ["<COLUMN_NAME_1>", "<COLUMN_NAME_2>"],
            "difficulty_level": "<beginner|intermediate|advanced>",
            "category": "<BUSINESS_CATEGORY>",
            "business_value": "<EXPLANATION_OF_BUSINESS_INSIGHTS_PROVIDED>",
            "confidence_score": <FLOAT_BETWEEN_0_AND_1>
        }
    ],
    "categories_covered": ["<CATEGORY_1>", "<CATEGORY_2>"],
    "additional_notes": "<ANY_LIMITATIONS_OR_ADDITIONAL_CONTEXT>"
}
"""

sql_question_suggestion_user_prompt_template = """
### DATABASE SCHEMA ###
{db_schemas}

### COLUMN DESCRIPTIONS ###
{column_descriptions}

### EXAMPLE SQL QUERIES ###
{sql_examples}

### QUERY HISTORY ###
{query_history}

### KNOWLEDGE BASE CONTEXT ###
{knowledge_base_context}

### USER'S REQUEST ###
{query}

### CONTEXT ###
Language: {language}
Project ID: {project_id}

### INSTRUCTIONS ###
Based on the available database schema, example SQL queries, and domain knowledge, suggest interesting and valuable 
SQL questions that users can ask about this dataset. Focus on questions that:

1. Provide actionable business insights
2. Cover different aspects of the data (trends, comparisons, segmentation, etc.)
3. Range from simple to complex analysis
4. Are inspired by the example SQL patterns but offer new perspectives

Please think step by step and provide comprehensive question suggestions with executable SQL examples.
"""


class SQLQuestionSuggestionTool:
    """Tool for suggesting SQL questions based on available data and examples"""
    
    def __init__(
        self, 
        doc_store_provider: DocumentStoreProvider, 
        retrieval_helper: RetrievalHelper = None,
        similarity_threshold: float = 0.7,
        max_results_per_store: int = 15
    ):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.retrieval_helper = retrieval_helper or RetrievalHelper()
        self.similarity_threshold = similarity_threshold
        self.max_results_per_store = max_results_per_store
        self.name = "sql_question_suggestion"
        self.description = "Suggests SQL questions based on available data and examples"
        
        # Initialize vector stores
        self.column_descriptions_store = doc_store_provider.get_store("column_descriptions")
        self.sql_examples_store = doc_store_provider.get_store("sql_examples")
        self.knowledge_base_store = doc_store_provider.get_store("knowledge_base")

    async def retrieve_column_descriptions(self, query: str, project_id: str) -> List[Dict[str, Any]]:
        """Retrieve relevant column descriptions"""
        try:
            results = await self.column_descriptions_store.semantic_search(
                query=query,
                filters={"project_id": project_id} if project_id else None,
                limit=self.max_results_per_store,
                similarity_threshold=self.similarity_threshold
            )
            return [{"content": result.get("content", ""), "metadata": result.get("metadata", {})} 
                   for result in results]
        except Exception as e:
            logger.warning(f"Error retrieving column descriptions: {e}")
            return []

    async def retrieve_sql_examples(self, query: str, project_id: str = None) -> List[Dict[str, Any]]:
        """Retrieve relevant SQL examples and patterns"""
        try:
            # Try to get SQL examples from the existing retrieval helper first
            sql_pairs_results = await self.retrieval_helper.get_sql_pairs(
                query=query,
                project_id=project_id,
                similarity_threshold=self.similarity_threshold,
                max_retrieval_size=self.max_results_per_store
            )
            
            sql_examples = []
            for pair in sql_pairs_results.get("sql_pairs", []):
                sql_examples.append({
                    "content": f"Question: {pair.get('question', '')}\nSQL: {pair.get('sql', '')}",
                    "metadata": {
                        "question": pair.get('question', ''),
                        "sql": pair.get('sql', ''),
                        "project_id": project_id
                    }
                })
            
            # Also try the SQL examples store if available
            try:
                store_results = await self.sql_examples_store.semantic_search(
                    query=query,
                    filters={"project_id": project_id} if project_id else None,
                    limit=self.max_results_per_store,
                    similarity_threshold=self.similarity_threshold
                )
                
                for result in store_results:
                    sql_examples.append({
                        "content": result.get("content", ""),
                        "metadata": result.get("metadata", {})
                    })
            except Exception as e:
                logger.warning(f"SQL examples store not available: {e}")
            
            return sql_examples
            
        except Exception as e:
            logger.warning(f"Error retrieving SQL examples: {e}")
            return []

    async def retrieve_knowledge_base(self, query: str, project_id: str = None) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge base documents"""
        try:
            filters = {"project_id": project_id} if project_id else None
            results = await self.knowledge_base_store.semantic_search(
                query=query,
                filters=filters,
                limit=self.max_results_per_store,
                similarity_threshold=self.similarity_threshold
            )
            return [{"content": result.get("content", ""), "metadata": result.get("metadata", {})} 
                   for result in results]
        except Exception as e:
            logger.warning(f"Error retrieving knowledge base: {e}")
            return []

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
                metadata_items = [f"{k}: {v}" for k, v in metadata.items() if v and k != "content"]
                if metadata_items:
                    metadata_str = f" ({', '.join(metadata_items)})"
            
            formatted_items.append(f"- {content}{metadata_str}")
        
        return f"### {title} ###\n" + "\n".join(formatted_items) + "\n"

    def format_query_history(self, histories: List[AskHistory]) -> str:
        """Format query history for prompt inclusion"""
        if not histories:
            return "### QUERY HISTORY ###\nNo previous queries available.\n"
        
        formatted_history = []
        for history in histories:
            if isinstance(history, dict):
                question = history.get('question', '')
                sql = history.get('statement', '') or history.get('sql', '')
                formatted_history.append(f"Question: {question}\nSQL: {sql}")
        
        return f"### QUERY HISTORY ###\n" + "\n\n".join(formatted_history) + "\n"

    @observe(capture_input=False)
    async def create_prompt(
        self,
        query: str,
        project_id: str,
        db_schemas: List[str],
        histories: Optional[List[AskHistory]] = None,
        configuration: Configuration | Dict[str, Any] = None
    ) -> str:
        """Create comprehensive prompt for SQL question suggestions"""
        try:
            # Retrieve relevant data from all vector stores
            column_descriptions = await self.retrieve_column_descriptions(query, project_id)
            sql_examples = await self.retrieve_sql_examples(query, project_id)
            knowledge_base_context = await self.retrieve_knowledge_base(query, project_id)
            
            # Format database schemas
            formatted_schemas = "\n".join(db_schemas) if db_schemas else "No database schema available."
            
            # Format retrieved data
            formatted_column_descriptions = self.format_retrieved_data(
                column_descriptions, "COLUMN DESCRIPTIONS"
            )
            formatted_sql_examples = self.format_retrieved_data(
                sql_examples, "EXAMPLE SQL QUERIES"
            )
            formatted_knowledge_base = self.format_retrieved_data(
                knowledge_base_context, "KNOWLEDGE BASE CONTEXT"
            )
            
            # Format query history
            formatted_query_history = self.format_query_history(histories or [])
            
            # Handle configuration
            if isinstance(configuration, dict):
                language = configuration.get('language', 'English')
            else:
                language = getattr(configuration, 'language', 'English') if configuration else 'English'
            
            # Create the prompt
            user_prompt = sql_question_suggestion_user_prompt_template.format(
                db_schemas=formatted_schemas,
                column_descriptions=formatted_column_descriptions,
                sql_examples=formatted_sql_examples,
                query_history=formatted_query_history,
                knowledge_base_context=formatted_knowledge_base,
                query=query,
                language=language,
                project_id=project_id or "N/A"
            )
            
            return user_prompt
            
        except Exception as e:
            logger.error(f"Error creating SQL question suggestion prompt: {e}")
            return ""

    @observe(as_type="generation", capture_input=False)
    async def generate_suggestions(self, prompt_input: str, query_id: str = None) -> dict:
        """Generate SQL question suggestions using LLM"""
        try:
            # Concatenate system and user prompts
            full_prompt = f"{sql_question_suggestion_system_prompt}\n\n{prompt_input}"
            logger.info(f"SQL question suggestion full_prompt: {full_prompt}")
            
            result = await self.llm.ainvoke(full_prompt)
            self.doc_store_provider.update_metrics("sql_question_suggestion", "query")
            
            logger.info(f"SQL question suggestion result: {result.content}")
            return {"replies": [result.content]}
            
        except Exception as e:
            logger.error(f"Error in SQL question suggestion generation: {e}")
            return {"replies": [""]}

    @observe()
    def post_process(self, generate_result: dict) -> Dict[str, Any]:
        """Post-process the generated suggestions"""
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
            
            # Convert to QuestionSuggestion objects
            suggestions = []
            for sug in parsed_result.get("suggestions", []):
                question_sug = QuestionSuggestion(
                    question=sug.get("question", ""),
                    description=sug.get("description", ""),
                    example_sql=sug.get("example_sql", ""),
                    tables_involved=sug.get("tables_involved", []),
                    columns_involved=sug.get("columns_involved", []),
                    difficulty_level=sug.get("difficulty_level", "intermediate"),
                    category=sug.get("category", "general"),
                    business_value=sug.get("business_value", ""),
                    confidence_score=sug.get("confidence_score", 0.5)
                )
                suggestions.append(question_sug)
            
            return {
                "summary": parsed_result.get("summary", ""),
                "suggestions": suggestions,
                "categories_covered": parsed_result.get("categories_covered", []),
                "additional_notes": parsed_result.get("additional_notes", "")
            }
            
        except Exception as e:
            logger.error(f"Error post-processing SQL question suggestions: {e}")
            return {
                "summary": "Error processing suggestions",
                "suggestions": [],
                "categories_covered": [],
                "additional_notes": f"Processing error: {str(e)}"
            }

    async def run(
        self,
        request: SQLQuestionSuggestionRequest,
        **kwargs
    ) -> SQLQuestionSuggestionResult:
        """Main execution method for SQL question suggestions"""
        try:
            logger.info(f"SQL Question Suggestion pipeline is running... {request}")
            
            # Get database schemas
            db_schemas = await self.retrieval_helper.get_database_schemas(
                project_id=request.project_id,
                table_retrieval={
                    "table_retrieval_size": 10,
                    "table_column_retrieval_size": 100,
                    "allow_using_db_schemas_without_pruning": False
                },
                query=request.query
            )
            
            schema_contexts = []
            if db_schemas and "schemas" in db_schemas:
                for schema in db_schemas["schemas"]:
                    if isinstance(schema, dict):
                        table_ddl = schema.get("table_ddl", "")
                        if table_ddl:
                            schema_contexts.append(table_ddl)
            
            # Get historical questions if available
            try:
                historical_results = await self.retrieval_helper.get_historical_questions(
                    query=request.query,
                    project_id=request.project_id,
                    similarity_threshold=self.similarity_threshold
                )
                historical_questions = historical_results.get("historical_questions", [])
            except Exception as e:
                logger.warning(f"Error retrieving historical questions: {str(e)}")
                historical_questions = []
            
            # Step 1: Create comprehensive prompt
            prompt_input = await self.create_prompt(
                query=request.query,
                project_id=request.project_id,
                db_schemas=schema_contexts,
                histories=historical_questions,
                configuration=request.configuration
            )
            
            # Step 2: Generate suggestions
            generate_result = await self.generate_suggestions(prompt_input, request.query_id)
            
            # Step 3: Post-process results
            processed_results = self.post_process(generate_result)
            
            return SQLQuestionSuggestionResult(
                success=True,
                suggestions=processed_results["suggestions"],
                data={
                    "summary": processed_results["summary"],
                    "categories_covered": processed_results["categories_covered"],
                    "additional_notes": processed_results["additional_notes"]
                },
                metadata={
                    "operation": "sql_question_suggestion",
                    "language": request.language,
                    "total_suggestions": len(processed_results["suggestions"]),
                    "categories_covered": len(processed_results["categories_covered"]),
                    "project_id": request.project_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error in SQL question suggestion: {e}")
            return SQLQuestionSuggestionResult(
                success=False,
                error=str(e),
                metadata={
                    "operation": "sql_question_suggestion",
                    "language": request.language,
                    "project_id": request.project_id
                }
            )


def create_sql_question_suggestion_tool(doc_store_provider: DocumentStoreProvider) -> Tool:
    """Create Langchain tool for SQL question suggestions"""
    suggestion_tool = SQLQuestionSuggestionTool(doc_store_provider)
    
    def suggestion_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            
            # Convert input to SQLQuestionSuggestionRequest
            request = SQLQuestionSuggestionRequest(
                query_id=input_data.get("query_id", ""),
                query=input_data.get("query", ""),
                project_id=input_data.get("project_id", ""),
                language=input_data.get("language", "English"),
                configuration=input_data.get("configuration", {})
            )
            
            result = asyncio.run(suggestion_tool.run(request))
            
            # Convert SQLQuestionSuggestionResult to dict for JSON serialization
            result_dict = {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "metadata": result.metadata,
                "suggestions": [
                    {
                        "question": sug.question,
                        "description": sug.description,
                        "example_sql": sug.example_sql,
                        "tables_involved": sug.tables_involved,
                        "columns_involved": sug.columns_involved,
                        "difficulty_level": sug.difficulty_level,
                        "category": sug.category,
                        "business_value": sug.business_value,
                        "confidence_score": sug.confidence_score
                    }
                    for sug in (result.suggestions or [])
                ]
            }
            
            return orjson.dumps(result_dict).decode()
            
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_question_suggester",
        description="Suggests SQL questions based on available data and examples. Input should be JSON with 'query', 'project_id', and optional configuration fields.",
        func=suggestion_func
    )


# Example usage and testing
if __name__ == "__main__":
    async def test_sql_question_suggestion():
        from app.core.dependencies import get_doc_store_provider
        
        doc_store_provider = get_doc_store_provider()
        
        suggestion_tool = SQLQuestionSuggestionTool(
            doc_store_provider=doc_store_provider
        )
        
        request = SQLQuestionSuggestionRequest(
            query_id="test_001",
            query="What questions can I ask about this sales and customer data?",
            project_id="test_project",
            language="English"
        )
        
        result = await suggestion_tool.run(request)
        
        print("SQL Question Suggestion Result:")
        print(f"Success: {result.success}")
        if result.success:
            print(f"Summary: {result.data.get('summary', '')}")
            print(f"Number of suggestions: {len(result.suggestions or [])}")
            print(f"Categories covered: {result.data.get('categories_covered', [])}")
            
            for i, sug in enumerate(result.suggestions or [], 1):
                print(f"\n{i}. {sug.question}")
                print(f"   Category: {sug.category} | Difficulty: {sug.difficulty_level}")
                print(f"   Description: {sug.description}")
                print(f"   SQL: {sug.example_sql}")
                print(f"   Confidence: {sug.confidence_score}")
        else:
            print(f"Error: {result.error}")

    # asyncio.run(test_sql_question_suggestion())