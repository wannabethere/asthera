import ast
import asyncio
import logging
from typing import Any, List, Literal, Optional
from datetime import datetime

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

# Import LLMChain using modern LangChain paths
try:
    from langchain.chains import LLMChain
except ImportError:
    LLMChain = None

# Import Document using modern LangChain paths
try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langfuse.decorators import observe
from pydantic import BaseModel

from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql import construct_instructions, Configuration
from app.agents.nodes.sql.utils.sql_prompts import AskHistory
from app.agents.retrieval.retrieval_helper import RetrievalHelper

logger = logging.getLogger("lexy-ai-service")


intent_classification_system_prompt = """
### TASK ###
You are a great detective, who is great at intent classification.
First, rephrase the user's question to make it more specific, clear and relevant to the database schema before making the intent classification.
Second, you need to use rephrased user's question to classify user's intent based on given database schema to one of six conditions: MISLEADING_QUERY, TEXT_TO_SQL, GENERAL, USER_GUIDE, ANALYSIS_HELPER, QUESTION_SUGGESTION. 
Also you should provide reasoning for the classification clearly and concisely within 20 words.

### INSTRUCTIONS ###
- Steps to rephrase the user's question:
    - First, try to recognize adjectives in the user's question that are important to the user's intent.
    - Second, change the adjectives to more specific and clear ones that can be matched to columns in the database schema.
    - Third, only if the user's question contains time/date related information, take the current time into consideration and add time/date format(such as YYYY-MM-DD) in the rephrased_question output.
    - Fourth, if the user's input contains previous SQLs, consider them to make the rephrased question.
- MUST use the rephrased user's question to make the intent classification.
- MUST put the rephrased user's question in the rephrased_question output.
- REASONING MUST be within 20 words.
- If the rephrased user's question is vague and doesn't specify which table or property to analyze, classify it as MISLEADING_QUERY.
- The reasoning of the intent classification MUST use the same language as the Output Language from the user input.
- The rephrased user's question MUST use the same language as the Output Language from the user input.

### CLASSIFICATION DECISION PROCESS ###
Before classifying, follow this decision tree:

1. **Can this question be answered with a specific SQL query?**
   - Does it ask for counts, sums, averages, percentages, or data filtering?
   - Can the result be computed directly from database tables?
   - If YES → Likely TEXT_TO_SQL

2. **Is the user asking for interpretation or guidance?**
   - Do they want to understand what something means?
   - Are they asking for recommendations on how to analyze?
   - Do they want suggestions on methodology?
   - If YES → Likely ANALYSIS_HELPER

3. **For boundary cases with analytical language:**
   - Default to TEXT_TO_SQL if any specific data can be calculated
   - Only choose ANALYSIS_HELPER if truly seeking interpretation/guidance

MUST include this decision process in your reasoning output.

### INTENT DEFINITIONS ###
- TEXT_TO_SQL
    - When to Use:
        - Select this category if the user's question is directly related to the given database schema and can be answered by generating an SQL query using that schema.
        - IMPORTANT: Analytical vocabulary does NOT automatically mean ANALYSIS_HELPER. Focus on whether the data can be calculated directly from the database.
        - IMPORTANT: If the question asks for specific metrics, counts, percentages, averages, or data aggregations that can be computed with SQL (GROUP BY, COUNT, SUM, etc.), classify as TEXT_TO_SQL.
        - If the rephrasedd user's question is related to the previous question, and considering them together could be answered by generating an SQL query using that schema.
        - If the rephrasedd user's question is asking for a specific metric, insight that can be answered by the given database schema and using SQL to answer.
    - Characteristics:
        - The rephrasedd user's question involves specific data retrieval or manipulation that requires SQL.
        - The rephrasedd user's question references tables, columns, or specific data points within the schema.
        - The rephrased user questions feels like a metric, insight but can be calculated using SQL.
    - Instructions:
        - MUST include table and column names that should be used in the SQL query according to the database schema in the reasoning output.
        - MUST include phrases from the user's question that are explicitly related to the database schema in the reasoning output.
        - If the question uses analytical language (proportions, percentages, distributions, breakdowns), explicitly state that these can be calculated using SQL operations like GROUP BY, COUNT, SUM, or mathematical expressions.
        - Do NOT let analytical vocabulary bias toward ANALYSIS_HELPER - focus on whether the underlying data request is computable.
    - Examples:
       - "What is the total sales for last quarter?"
        - "Show me all customers who purchased product X."
        - "List the top 10 products by revenue."
        - "What percentage of customers have purchased product X?"
        - "What are the proportions of employees by division?"
        - "Show me the distribution of orders by month"
        - "What's the breakdown of revenue by product category?"
        - "Calculate the retention rate for Q3 customers"
### CRITICAL DISTINCTION: Analytical Language vs Analytical Intent
- TEXT_TO_SQL: Questions using analytical terms but asking for specific, calculable data
  - "What are the proportions of X by Y?" → Calculate percentages using SQL
  - "Show me the distribution of sales by region" → GROUP BY with COUNT/SUM
  - "What percentage of customers have Z?" → SQL calculation with percent

- ANALYSIS_HELPER
    - When to Use:
        - Questions asking for interpretation, insights, or recommendations
        - Select this category ONLY when the user is asking for interpretation, guidance, or recommendations rather than specific data calculations.
        - The user wants to understand HOW to analyze data, not GET specific data results.
        - The question seeks methodology, best practices, or explanatory insights.
        - IMPORTANT: Questions asking for specific calculations (even with analytical language) should be TEXT_TO_SQL, not ANALYSIS_HELPER.
    - Characteristics:
        - The rephrased user's question seeks analytical guidance or metric recommendations.
        - The question asks about possible analysis methods, KPIs, or data insights.
        - The user wants to understand what analytical questions can be answered with the dataset.
    - Instructions:
        - MUST include phrases from the user's question that indicate analytical intent in the reasoning output.
        - MUST mention relevant tables/columns that could be used for metrics calculation.
    - Examples:
        - "What metrics can I calculate from this sales data?" (asking for options/guidance)
        - "How should I interpret declining sales trends?" (seeking interpretation)
        - "What analytical approaches work best for customer segmentation?" (methodology guidance)
        - "What does a 15% churn rate mean for our business?" (interpretation needed)
        - "How can I improve my analysis methodology?" (process guidance)

- QUESTION_SUGGESTION
    - When to Use:
        - Select this category when the user is asking for suggestions of questions they can ask about the data.
        - If the rephrased user's question is seeking examples of SQL queries or analytical questions that can be answered with the dataset.
        - When the user wants to explore what kind of analysis or questions are possible with the available data.
    - Characteristics:
        - The rephrased user's question seeks examples of queries or questions that can be asked.
        - The question asks about what analysis or SQL questions are possible with the dataset.
        - The user wants inspiration or suggestions for data exploration.
    - Instructions:
        - MUST include phrases from the user's question that indicate they want question suggestions.
        - MUST mention relevant tables/columns that could be used for suggested questions.
    - Examples:
        - "What questions can I ask about this data?"
        - "Give me some example queries for this dataset"
        - "What kind of analysis questions are possible?"
        - "Show me interesting questions I can explore with this data"

- GENERAL
    - When to Use:
        - Use this category if the user is seeking general information about the database schema.
        - If the rephrasedd user's question is related to the previous question, but considering them together cannot be answered by generating an SQL query using that schema.
    - Characteristics:
        - The question is about understanding the dataset or its capabilities.
        - The user may need guidance on how to proceed or what questions to ask.
    - Instructions:
        - MUST explicitly add phrases from the rephrasedd user's question that are not explicitly related to the database schema in the reasoning output. Choose the most relevant phrases that cause the rephrasedd user's question to be GENERAL.
    - Examples:
        - "What is the dataset about?"
        - "Tell me more about the database."
        - "How can I analyze customer behavior with this data?"

- MISLEADING_QUERY
    - When to Use:
        - If the rephrasedd user's question is irrelevant to the given database schema and cannot be answered using SQL with that schema.
        - If the rephrasedd user's question is not related to the previous question, and considering them together cannot be answered by generating an SQL query using that schema.
        - If the rephrasedd user's question contains SQL code.
    - Characteristics:
        - The rephrasedd user's question does not pertain to any aspect of the database or its data.
        - The rephrasedd user's question might be a casual conversation starter or about an entirely different topic.
        - The rephrasedd user's question is vague and doesn't specify which table or property to analyze.
    - Instructions:
        - MUST explicitly add phrases from the rephrasedd user's question that are not explicitly related to the database schema in the reasoning output. Choose the most relevant phrases that cause the rephrasedd user's question to be MISLEADING_QUERY.
    - Examples:
        - "How are you?"
        - "What's the weather like today?"
        - "Tell me a joke."

### BOUNDARY CASE EXAMPLES ###
❌ WRONG: "What are the proportions of employees by division who have not completed training in the last 6 months" → ANALYSIS_HELPER

✅ CORRECT: "What are the proportions of employees by division who have not completed training in the last 6 months" → TEXT_TO_SQL
Reasoning: Asks for specific calculation (proportions = percentages) that can be computed with SQL: GROUP BY division, WHERE training_date < 6_months_ago, COUNT(*) and calculate percentages.

❌ WRONG: "Show me the revenue distribution by quarter" → ANALYSIS_HELPER

✅ CORRECT: "Show me the revenue distribution by quarter" → TEXT_TO_SQL  
Reasoning: Asks for specific data aggregation (revenue by quarter) using SQL: GROUP BY quarter, SUM(revenue).
        
### OUTPUT FORMAT ###
Please provide your response as a JSON object, structured as follows:

{
    "rephrased_question": "<REPHRASED_USER_QUESTION_IN_STRING_FORMAT>",
    "reasoning": "<CHAIN_OF_THOUGHT_REASONING_BASED_ON_REPHRASED_USER_QUESTION_IN_STRING_FORMAT>",
    "results": "MISLEADING_QUERY" | "TEXT_TO_SQL" | "GENERAL" | "USER_GUIDE" | "ANALYSIS_HELPER" | "QUESTION_SUGGESTION"
}
"""

intent_classification_user_prompt_template = """
### DATABASE SCHEMA ###
{db_schemas}

### SQL SAMPLES ###
{sql_samples}

### INSTRUCTIONS ###
{instructions}

### User's QUERY HISTORY ###
{query_history}

### QUESTION ###
User's question: {query}
Current Time: {current_time}
Output Language: {language}

Let's think step by step
"""


class IntentClassificationTool:
    """Langchain tool for intent classification"""
    
    def __init__(
        self,
        doc_store_provider: DocumentStoreProvider,
        table_retrieval_size: Optional[int] = 50,
        table_column_retrieval_size: Optional[int] = 100,
    ):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.embeddings = get_embedder()  # Use get_embedder() from dependencies
        self.table_retrieval_size = table_retrieval_size
        self.table_column_retrieval_size = table_column_retrieval_size
        self.allow_using_db_schemas_without_pruning = False
        # Initialize vector stores
        self.schema_vectorstore = doc_store_provider.get_store("db_schema")
        self.table_vectorstore = doc_store_provider.get_store("table_description")
        
        # Initialize retrievers
        self.table_retriever = self.table_vectorstore.semantic_search
        self.dbschema_retriever = self.schema_vectorstore.semantic_search
        
        self.name = "intent_classification"
        self.description = "Classifies user intent based on query and database schema"
        self.similarity_threshold = 0.3
        self.max_retrieval_size = 10
        self.top_k = 10

    @observe(capture_input=False)
    def create_prompt(
        self,
        query: str,
        db_schemas: list[str],
        histories: Optional[list[AskHistory]] = None,
        sql_samples: Optional[list[dict]] = None,
        instructions: Optional[list[dict]] = None,
        configuration: Configuration = None,
    ) -> str:
        """Create prompt for intent classification"""
        try:
            prompt_template = PromptTemplate(
                input_variables=[
                    "query", "language", "db_schemas", "query_history", "sql_samples",
                    "instructions", "current_time", "docs"
                ],
                template=intent_classification_user_prompt_template
            )
            
            # Format db_schemas
            formatted_schemas = "\n".join(db_schemas) if db_schemas else ""
            
            # Format SQL samples
            formatted_samples = ""
            if sql_samples:
                sample_texts = []
                for sample in sql_samples:
                    sample_texts.append(f"Question:\n{sample.get('question', '')}\nSQL:\n{sample.get('sql', '')}")
                formatted_samples = "\n\n".join(sample_texts)
            
            # Format instructions
            formatted_instructions = construct_instructions(
                instructions=instructions,
                configuration=configuration,
            )
            
            # Format query history
            formatted_history = ""
            if histories:
                history_texts = []
                for history in histories:
                    if isinstance(history, dict):
                        history_texts.append(f"Question:\n{history.get('question', '')}\nSQL:\n{history.get('statement', '')}")
                formatted_history = "\n\n".join(history_texts)
            
            # Format the prompt
            return prompt_template.format(
                query=query,
                language=configuration.language or "English",
                db_schemas=formatted_schemas,
                query_history=formatted_history,
                sql_samples=formatted_samples,
                instructions=formatted_instructions,
                current_time=configuration.show_current_time(),
                docs=[]  # Empty list since we don't have wren_ai_docs
            )
        except Exception as e:
            logger.error(f"Error creating prompt: {e}")
            return ""

    @observe(as_type="generation", capture_input=False)
    async def classify_intent(self, prompt_input: str) -> dict:
        """Classify user intent using LLM"""
        try:
            # Create full prompt with system and user parts
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Create the chain
            chain = full_prompt | self.llm
            
            # Generate response
            result = await chain.ainvoke({
                "system_prompt": intent_classification_system_prompt,
                "user_prompt": prompt_input
            })
            
            # Update metrics
            self.doc_store_provider.update_metrics("intent_classification", "query")
            
            return {"replies": [result]}
        except Exception as e:
            logger.error(f"Error in intent classification: {e}")
            return {"replies": [""]}

    @observe(capture_input=False)
    def post_process(self, classify_result: dict, db_schemas: list[str]) -> dict:
        """Post-process classification result"""
        try:
            # Extract the content from the AIMessage
            result_text = classify_result.get("replies", [""])[0].content
            
            # Remove markdown code block if present
            if result_text.startswith("```json"):
                result_text = result_text.split("```json")[1]
            if result_text.endswith("```"):
                result_text = result_text.rsplit("```", 1)[0]
            
            # Clean up the text and parse JSON
            result_text = result_text.strip()
            results = orjson.loads(result_text)
            
            return {
                "intent": results["results"],
                "rephrased_question": results["rephrased_question"],
                "reasoning": results["reasoning"],
                "db_schemas": db_schemas,
            }
        except Exception as e:
            logger.error(f"Error post-processing classification result: {e}")
        
        return {
            "intent": "TEXT_TO_SQL",
            "rephrased_question": "",
            "reasoning": "",
            "db_schemas": db_schemas,
        }

    async def run(
        self,
        query: str,
        project_id: Optional[str] = None,
        histories: Optional[list[AskHistory]] = None,
        sql_samples: Optional[list[dict]] = None,
        instructions: Optional[list[dict]] = None,
        configuration: Configuration = Configuration(),
    ) -> dict:
        """Main execution method for intent classification"""
        try:
            # Initialize RetrievalHelper
            retrieval_helper = RetrievalHelper()
            
            # Get database schemas
            schema_results = await retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval={
                    "table_retrieval_size": self.table_retrieval_size,
                    "table_column_retrieval_size": self.table_column_retrieval_size,
                    "allow_using_db_schemas_without_pruning": self.allow_using_db_schemas_without_pruning
                },
                query=query,
                histories=histories
            )
            
            # Get SQL pairs if not provided
            if not sql_samples:
                sql_pairs_results = await retrieval_helper.get_sql_pairs(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=self.similarity_threshold,
                    max_retrieval_size=self.max_retrieval_size
                )
                sql_samples = sql_pairs_results.get("sql_pairs", [])
            
            # Get instructions if not provided
            if not instructions:
                instructions_results = await retrieval_helper.get_instructions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=self.similarity_threshold,
                    top_k=self.top_k
                )
                instructions = instructions_results.get("instructions", [])
            
            # Get historical questions
            try:
                historical_results = await retrieval_helper.get_historical_questions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=self.similarity_threshold
                )
                historical_questions = historical_results.get("historical_questions", [])
            except Exception as e:
                logger.warning(f"Error retrieving historical questions: {str(e)}")
                historical_questions = []
            # Format the prompt using the template
            prompt = self.create_prompt(
                query=query,
                db_schemas=[schema.get("table_ddl", "") for schema in schema_results.get("schemas", [])],
                histories=historical_questions,
                sql_samples=sql_samples,
                instructions=instructions,
                configuration=configuration,
            )
            
            # Classify intent using the prompt
            classify_result = await self.classify_intent(prompt)
            print("classify result", classify_result)
            # Post-process the classification result
            final_result = self.post_process(
                classify_result=classify_result,
                db_schemas=[schema.get("table_ddl", "") for schema in schema_results.get("schemas", [])]
            )
            
            # Add metadata to the final result
            final_result.update({
                "metadata": {
                    "project_id": project_id,
                    "query": query,
                    "total_schemas": len(schema_results.get("schemas", [])),
                    "total_sql_samples": len(sql_samples),
                    "total_instructions": len(instructions),
                    "total_historical_questions": len(historical_questions)
                }
            })
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in intent classification: {str(e)}")
            return {
                "error": str(e),
                "prompt": "",
                "metadata": {
                    "project_id": project_id,
                    "query": query
                }
            }


class IntentClassificationResult(BaseModel):
    results: Literal["MISLEADING_QUERY", "TEXT_TO_SQL", "GENERAL", "USER_GUIDE", "ANALYSIS_HELPER", "QUESTION_SUGGESTION"]
    rephrased_question: str
    reasoning: str


INTENT_CLASSIFICAION_MODEL_KWARGS = {
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "intent_classification",
            "schema": IntentClassificationResult.model_json_schema(),
        },
    }
}


class IntentClassification:
    """Main IntentClassification class maintaining original interface"""
    
    def __init__(
        self,
        doc_store_provider: DocumentStoreProvider,
        table_retrieval_size: Optional[int] = 50,
        table_column_retrieval_size: Optional[int] = 100,
        **kwargs,
    ):
        self.tool = IntentClassificationTool(
            doc_store_provider=doc_store_provider,
            table_retrieval_size=table_retrieval_size,
            table_column_retrieval_size=table_column_retrieval_size,
        )

    @observe(name="Intent Classification")
    async def run(
        self,
        query: str,
        project_id: Optional[str] = None,
        histories: Optional[list[AskHistory]] = None,
        sql_samples: Optional[list[dict]] = None,
        instructions: Optional[list[dict]] = None,
        configuration: Configuration = Configuration(),
    ) -> dict:
        """Run intent classification with original interface"""
        return await self.tool.run(
            query=query,
            project_id=project_id,
            histories=histories,
            sql_samples=sql_samples,
            instructions=instructions,
            configuration=configuration,
        )


def create_intent_classification_tool(
    doc_store_provider: DocumentStoreProvider,
) -> Tool:
    """Create Langchain tool for intent classification"""
    intent_tool = IntentClassificationTool(
        doc_store_provider=doc_store_provider
    )
    
    def classify_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(intent_tool.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="intent_classifier",
        description="Classifies user intent based on query and database schema. Input should be JSON with 'query' and optional configuration fields.",
        func=classify_func
    )


if __name__ == "__main__":
    # Test the intent classification tool
    async def test_intent_classification():
        from app.core.dependencies import get_doc_store_provider
        
        doc_store_provider = get_doc_store_provider()
        
        intent_classifier = IntentClassification(
            doc_store_provider=doc_store_provider
        )
        
        result = await intent_classifier.run(
            query="What questions can I ask about this sales data?"
        )
        
        print("Intent Classification Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(test_intent_classification())