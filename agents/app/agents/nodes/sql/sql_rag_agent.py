import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import datetime
import orjson
import json
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent import AgentExecutor
from langchain.schema import AgentAction, AgentFinish
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.schema import LLMResult
from langchain.agents import Tool
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.docstore.document import Document
import chromadb
from langchain_openai import OpenAIEmbeddings
from app.storage.documents import DocumentChromaStore
from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration, SQL_GENERATION_MODEL_KWARGS
from app.agents.retrieval.retrieval_helper import RetrievalHelper


from app.agents.nodes.sql.utils.sql import (
    SQLBreakdownGenPostProcessor,
    SQLGenPostProcessor,
    create_sql_breakdown_postprocessor_tool,
    create_sql_gen_postprocessor_tool,
)
from app.core.engine import Engine
from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
from app.settings import get_settings
from app.agents.nodes.sql.utils.sql_prompts import TEXT_TO_SQL_RULES, sql_generation_system_prompt, calculated_field_instructions, metric_instructions, construct_instructions

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()


class SQLOperationType(Enum):
    GENERATION = "generation"
    BREAKDOWN = "breakdown"
    EXPANSION = "expansion"
    CORRECTION = "correction"
    REGENERATION = "regeneration"
    REASONING = "reasoning"
    ANSWER = "answer"
    QUESTION = "question"
    SUMMARY = "summary"


class SQLRAGAgent:
    """Self-correcting RAG agent for comprehensive SQL operations"""
    
    def __init__(
        self, 
        llm, 
        engine: Engine,
        embeddings=None,
        max_iterations: int = 5,
        document_store_provider: DocumentStoreProvider = None,
        retrieval_helper: RetrievalHelper = None,
        **kwargs
    ):
        self.llm = llm
        self.engine = engine
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.max_iterations = max_iterations
        self.document_store_provider = document_store_provider
        self.retrieval_helper = retrieval_helper or RetrievalHelper()
        
        # Initialize processors
        self.breakdown_processor = SQLBreakdownGenPostProcessor(engine)
        self.gen_processor = SQLGenPostProcessor(engine)
        
        # Create tools
        self.tools = self._create_tools()
        
        # Initialize agent
        self.agent = self._create_agent()
        
        # System prompts for different operations
        self.system_prompts = self._initialize_system_prompts()
        
        # User queues for streaming
        self._user_queues = {}
    
   
    
    def _create_tools(self) -> List[Tool]:
        """Create all SQL-related tools"""
        tools = [
            create_sql_breakdown_postprocessor_tool(self.engine),
            create_sql_gen_postprocessor_tool(self.engine),
            self._create_sql_generation_tool(),
            self._create_sql_breakdown_tool(),
            self._create_sql_expansion_tool(),
            self._create_sql_correction_tool(),
            self._create_sql_reasoning_tool(),
            self._create_sql_answer_tool(),
            self._create_sql_question_tool(),
            self._create_sql_summary_tool(),
            self._create_schema_retrieval_tool(),
            self._create_sample_retrieval_tool(),
        ]
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create and configure the main RAG agent"""
        try:
            agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=self.max_iterations,
                early_stopping_method="generate"
            )
            return agent
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise
    
    def _initialize_system_prompts(self) -> Dict[str, str]:
        """Initialize system prompts for different SQL operations"""
        return {
            SQLOperationType.GENERATION.value: f"""
You are a helpful assistant that converts natural language queries into ANSI SQL queries.
Given user's question, database schema, etc., you should think deeply and carefully and generate the SQL query based on the given reasoning plan step by step.
**In addition, you should also provide a column filters chosen,time filters chosen, aggregations applied on columns and group by columns chosen in the SQL query as a JSON object**

{TEXT_TO_SQL_RULES}

### FINAL ANSWER FORMAT ###
The final answer must be a ANSI SQL query in JSON format:
{{
    "sql": <SQL_QUERY_STRING>
}}
""",
            
            SQLOperationType.BREAKDOWN.value: """
### TASK ###
You are an ANSI SQL expert with exceptional logical thinking skills.
You are going to break a complex SQL query into 1 to 3 steps to make it easier to understand for end users.
Each step should have a SQL query part, a summary explaining the purpose of that query, and a CTE name to link the queries.
Also, you need to give a short description describing the purpose of the original SQL query.
Description and summary in each step MUST BE in the same language as user specified.

### SQL QUERY BREAKDOWN INSTRUCTIONS ###
- SQL BREAKDOWN MUST BE 1 to 3 steps only.
- YOU MUST BREAK DOWN any SQL query into small steps if there is JOIN operations or sub-queries.
- ONLY USE the tables and columns mentioned in the original sql query.
- ONLY CHOOSE columns belong to the tables mentioned in the database schema.
- ALWAYS USE alias for tables and referenced CTEs.
- ALWAYS SHOW alias for columns and tables such as SELECT [column_name] AS [alias_column_name].
- MUST USE alias from the original SQL query.

### FINAL ANSWER FORMAT ###
The final answer must be a valid JSON format as following:
{
    "description": <SHORT_SQL_QUERY_DESCRIPTION_STRING>,
    "steps: [
        {
            "sql": <SQL_QUERY_STRING_1>,
            "summary": <SUMMARY_STRING_1>,
            "cte_name": <CTE_NAME_STRING_1>
        },
        ...
    ]
}
""",
            
            SQLOperationType.REASONING.value: """
### TASK ###
You are a helpful data analyst who is great at thinking deeply and reasoning about the user's question and the database schema, and you provide a step-by-step reasoning plan in order to answer the user's question.

### INSTRUCTIONS ###
1. Think deeply and reason about the user's question and the database schema.
2. Give a step by step reasoning plan in order to answer user's question.
3. The reasoning plan should be in the language same as the language user provided in the input.
4. Make sure to consider the current time provided in the input if the user's question is related to the date/time.
5. Each step in the reasoning plan must start with a number, a title(in bold format in markdown), and a reasoning for the step.

### FINAL ANSWER FORMAT ###
The final answer must be a reasoning plan in plain Markdown string format
""",
            
            SQLOperationType.ANSWER.value: """
### TASK ###
You are a data analyst that is great at answering non-technical user's questions based on the data, sql so that even non technical users can easily understand.
Please answer the user's question in concise and clear manner in Markdown format.

### INSTRUCTIONS ###
1. Read the user's question and understand the user's intention.
2. Read the sql and understand the data.
3. Make sure the answer is aimed for non-technical users, so don't mention any technical terms such as SQL syntax.
4. Generate a concise and clear answer in string format to answer the user's question based on the data and sql.
5. If answer is in list format, only list top few examples, and tell users there are more results omitted.
6. Answer must be in the same language user specified.
7. Do not include ```markdown or ``` in the answer.

### OUTPUT FORMAT ###
Please provide your response in proper Markdown string format.
""",
        }
    
    def _create_sql_generation_tool(self) -> Tool:
        """Create SQL generation tool"""
        def generate_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                query = input_data.get("query", "")
                contexts = input_data.get("contexts", [])
                reasoning = input_data.get("reasoning", "")
                configuration = input_data.get("configuration", {})
                
                result = asyncio.run(self._generate_sql_internal(
                    query, contexts, reasoning, configuration
                ))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL generation tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_generator",
            description="Generates SQL queries from natural language. Input should be JSON with 'query', 'contexts', 'reasoning', and 'configuration' fields.",
            func=generate_sql_func
        )
    
    def _create_sql_breakdown_tool(self) -> Tool:
        """Create SQL breakdown tool"""
        def breakdown_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                query = input_data.get("query", "")
                sql = input_data.get("sql", "")
                language = input_data.get("language", "English")
                
                result = asyncio.run(self._breakdown_sql_internal(query, sql, language))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL breakdown tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_breakdown",
            description="Breaks down complex SQL into understandable steps. Input should be JSON with 'query', 'sql', and 'language' fields.",
            func=breakdown_sql_func
        )
    
    def _create_sql_expansion_tool(self) -> Tool:
        """Create SQL expansion tool"""
        def expand_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                query = input_data.get("query", "")
                original_sql = input_data.get("original_sql", "")
                contexts = input_data.get("contexts", [])
                
                result = asyncio.run(self._expand_sql_internal(query, original_sql, contexts))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL expansion tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_expander",
            description="Expands SQL based on user adjustment requests. Input should be JSON with 'query', 'original_sql', and 'contexts' fields.",
            func=expand_sql_func
        )
    
    def _create_sql_correction_tool(self) -> Tool:
        """Create SQL correction tool"""
        def correct_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                sql = input_data.get("sql", "")
                error_message = input_data.get("error_message", "")
                contexts = input_data.get("contexts", [])
                
                result = asyncio.run(self._correct_sql_internal(sql, error_message, contexts))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL correction tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_corrector",
            description="Corrects invalid SQL queries. Input should be JSON with 'sql', 'error_message', and 'contexts' fields.",
            func=correct_sql_func
        )
    
    def _create_sql_reasoning_tool(self) -> Tool:
        """Create SQL reasoning tool"""
        def reason_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                query = input_data.get("query", "")
                contexts = input_data.get("contexts", [])
                language = input_data.get("language", "English")
                
                result = asyncio.run(self._reason_sql_internal(query, contexts, language))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL reasoning tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_reasoner",
            description="Generates reasoning plans for SQL queries. Input should be JSON with 'query', 'contexts', and 'language' fields.",
            func=reason_sql_func
        )
    
    def _create_sql_answer_tool(self) -> Tool:
        """Create SQL answer tool"""
        def answer_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                query = input_data.get("query", "")
                sql = input_data.get("sql", "")
                sql_data = input_data.get("sql_data", {})
                language = input_data.get("language", "English")
                
                result = asyncio.run(self._answer_sql_internal(query, sql, sql_data, language))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL answer tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_answerer",
            description="Converts SQL results to natural language answers. Input should be JSON with 'query', 'sql', 'sql_data', and 'language' fields.",
            func=answer_sql_func
        )
    
    def _create_sql_question_tool(self) -> Tool:
        """Create SQL question tool"""
        def question_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                sqls = input_data.get("sqls", [])
                language = input_data.get("language", "English")
                
                result = asyncio.run(self._question_sql_internal(sqls, language))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL question tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_questioner",
            description="Converts SQL queries to natural language questions. Input should be JSON with 'sqls' and 'language' fields.",
            func=question_sql_func
        )
    
    def _create_sql_summary_tool(self) -> Tool:
        """Create SQL summary tool"""
        def summarize_sql_func(input_json: str) -> str:
            try:
                input_data = orjson.loads(input_json)
                query = input_data.get("query", "")
                sqls = input_data.get("sqls", [])
                language = input_data.get("language", "English")
                
                result = asyncio.run(self._summarize_sql_internal(query, sqls, language))
                return orjson.dumps(result).decode()
            except Exception as e:
                logger.error(f"Error in SQL summary tool: {e}")
                return orjson.dumps({"error": str(e)}).decode()
        
        return Tool(
            name="sql_summarizer",
            description="Summarizes SQL queries in human-readable format. Input should be JSON with 'query', 'sqls', and 'language' fields.",
            func=summarize_sql_func
        )
    
    def _create_schema_retrieval_tool(self) -> Tool:
        """Create schema retrieval tool"""
        def retrieve_schema_func(query: str) -> str:
            try:
                schema_result = asyncio.run(self.retrieval_helper.get_database_schemas(
                    project_id="default",
                    table_retrieval={
                        "table_retrieval_size": 10,
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": False
                    },
                    query=query
                ))
                
                if not schema_result or "schemas" not in schema_result:
                    return orjson.dumps({"contexts": [], "message": "No schema information found"}).decode()
                
                contexts = []
                for schema in schema_result["schemas"]:
                    if isinstance(schema, dict):
                        table_ddl = schema.get("table_ddl", "")
                        if table_ddl:
                            contexts.append(table_ddl)
                
                return orjson.dumps({"contexts": contexts}).decode()
            except Exception as e:
                logger.error(f"Error in schema retrieval tool: {e}")
                return orjson.dumps({"contexts": [], "error": str(e)}).decode()
        
        return Tool(
            name="schema_retriever",
            description="Retrieves relevant database schema information based on the query.",
            func=retrieve_schema_func
        )
    
    def _create_sample_retrieval_tool(self) -> Tool:
        """Create sample retrieval tool"""
        def retrieve_samples_func(query: str) -> str:
            try:
                sql_pairs_result = asyncio.run(self.retrieval_helper.get_sql_pairs(
                    query=query,
                    project_id="default",
                    similarity_threshold=0.3,
                    max_retrieval_size=3
                ))
                
                if not sql_pairs_result or "sql_pairs" not in sql_pairs_result:
                    return orjson.dumps({"samples": [], "message": "No SQL pairs found"}).decode()
                
                samples = []
                for pair in sql_pairs_result["sql_pairs"]:
                    if isinstance(pair, dict):
                        samples.append({
                            "question": pair.get("question", ""),
                            "sql": pair.get("sql", "")
                        })
                
                return orjson.dumps({"samples": samples}).decode()
            except Exception as e:
                logger.error(f"Error in sample retrieval tool: {e}")
                return orjson.dumps({"samples": [], "error": str(e)}).decode()
        
        return Tool(
            name="sample_retriever",
            description="Retrieves relevant SQL samples based on the query.",
            func=retrieve_samples_func
        )
    
    def _extract_sql_from_content(self, content: str) -> Dict[str, Any]:
        """Extract SQL query and parsed entities from content that may contain explanations"""
        try:
            # First try to parse the entire content as JSON
            try:
                json_data = json.loads(content)
                if isinstance(json_data, dict):
                    
                    return {
                        "sql": json_data.get("sql", "").strip(),
                        "parsed_entities": json_data.get("parsed_entities", {})
                    }
            except json.JSONDecodeError:
                pass

            # If that fails, try to find JSON object in the content
            import re
            json_match = re.search(r'\{[\s\S]*?\}', content)
            if json_match:
                try:
                    json_str = json_match.group(0)
                    json_data = json.loads(json_str)
                    if isinstance(json_data, dict):
                        return {
                            "sql": json_data.get("sql", "").strip(),
                            "parsed_entities": json_data.get("parsed_entities", {})
                        }
                except json.JSONDecodeError:
                    pass
            
            # If no valid JSON found, look for SQL code block
            sql_match = re.search(r'```sql\n(.*?)\n```', content, re.DOTALL)
            if sql_match:
                return {
                    "sql": sql_match.group(1).strip(),
                    "parsed_entities": {}
                }
            
            # If no code block, look for SQL statement
            sql_match = re.search(r'SELECT.*?;', content, re.DOTALL | re.IGNORECASE)
            if sql_match:
                return {
                    "sql": sql_match.group(0).strip(),
                    "parsed_entities": {}
                }
            
            # If still no match, try to find any SQL-like content
            sql_match = re.search(r'(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP).*?;', content, re.DOTALL | re.IGNORECASE)
            if sql_match:
                return {
                    "sql": sql_match.group(0).strip(),
                    "parsed_entities": {}
                }
            
            # If no SQL found, return empty dict
            logger.warning(f"No SQL found in content: {content}")
            return {
                "sql": "",
                "parsed_entities": {}
            }
            
        except Exception as e:
            logger.error(f"Error extracting SQL from content: {e}")
            return {
                "sql": "",
                "parsed_entities": {}
            }

    async def _retrieve_schema_context(self, query: str, project_id: str = "default") -> Dict[str, Any]:
        """Helper method to retrieve schema context and table names"""
        schema_data = await self.retrieval_helper.get_table_names_and_schema_contexts(
            query=query,
            project_id=project_id,
            table_retrieval={
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
        )
        
        return {
            "table_names": schema_data.get("table_names", []),
            "schema_contexts": schema_data.get("schema_contexts", []),
            "has_calculated_field": schema_data.get("has_calculated_field", False),
            "has_metric": schema_data.get("has_metric", False)
        }

    async def _get_schema_and_samples(self, query: str, **kwargs):
        """Get schema and sample documents using RetrievalHelper"""
        # Get schema context using helper method
        schema_data = await self._retrieve_schema_context(
            query=query,
            project_id=kwargs.get("project_id", "default")
        )
        
        # Get SQL pairs
        sql_pairs_result = await self.retrieval_helper.get_sql_pairs(
            query=query,
            project_id=kwargs.get("project_id", "default"),
            similarity_threshold=0.3,
            max_retrieval_size=3
        )
        
        return {
            "table_names": schema_data["table_names"],
            "schema_contexts": schema_data["schema_contexts"],
            "sql_pairs": sql_pairs_result
        }

    async def _get_schema_context(self, query: str, **kwargs):
        """Get schema context for SQL generation"""
        # Get schema context using helper method
        schema_data = await self._retrieve_schema_context(
            query=query,
            project_id=kwargs.get("project_id", "default")
        )
        
        return schema_data["schema_contexts"]

    async def _generate_sql_internal(
        self,
        query: str,
        contexts: List[str],
        reasoning: str = "",
        configuration: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Internal method for SQL generation"""
        try:
            # Get schema and sample documents using helper method
            schema_data = await self._retrieve_schema_context(
                query=query,
                project_id=kwargs.get("project_id", "default")
            )
            
            sql_pairs_result, instructions_result = await asyncio.gather(
                self.retrieval_helper.get_sql_pairs(
                    query=query,
                    project_id=kwargs.get("project_id", "default"),
                    similarity_threshold=0.3,
                    max_retrieval_size=3
                ),
                self.retrieval_helper.get_instructions(
                    query=query,
                    project_id=kwargs.get("project_id", "default"),
                    similarity_threshold=0.3,
                    top_k=3
                )
            )
            
            instructions = instructions_result.get("documents", []) if instructions_result else []
            
            # Combine all contexts
            all_contexts = json.dumps(contexts) + json.dumps(schema_data["schema_contexts"]) + json.dumps(instructions)

            if sql_pairs_result and "sql_pairs" in sql_pairs_result:
                for pair in sql_pairs_result["sql_pairs"]:
                    if isinstance(pair, dict):
                        all_contexts.append(f"Question: {pair.get('question', '')}\nSQL: {pair.get('sql', '')}")

            # Generate SQL using LLM
            logger.info(f"Generating SQL for query: {query}")
            
            
            # Create configuration object
            config = Configuration(**(configuration or {}))
            
            # Construct instructions
            instructions = construct_instructions(
                configuration=config,
                has_calculated_field=any("Calculated Field" in ctx for ctx in all_contexts),
                has_metric=any("metric" in ctx.lower() for ctx in all_contexts)
            )
            logger.debug(f"reasoning in generate sql internal in sql_rag_agent: {reasoning}")
            # Add reasoning if provided
            if reasoning:
                instructions += f"\n### REASONING PLAN ###\n{reasoning}\n ###IMPORTANT **Please ensure to use all the reasoning steps to answer the question and dont skip any steps if not results will be broken**"
            
            # Add table names if available
            if schema_data["table_names"]:
                instructions += f"\n### AVAILABLE TABLES ###\n{chr(10).join(schema_data['table_names'])}\n"
            
            # Add query and contexts
            instructions += f"\n### DATABASE SCHEMA ###\n{chr(10).join(all_contexts)}\n\n### QUESTION ###\nUser's Question: {query}\nCurrent Time: {config.show_current_time()}\n\nLet's think step by step."
            
            
            
            # Create messages
            messages = [
                SystemMessage(content=sql_generation_system_prompt),
                HumanMessage(content=instructions)
            ]
            
            # Create chat prompt template and chain
            prompt = ChatPromptTemplate.from_messages(messages)
            chain = prompt | self.llm
            
            # Invoke the chain with inputs
            result = await chain.ainvoke(
                {
                    "system_prompt": sql_generation_system_prompt,
                    "user_prompt": instructions
                },
                **SQL_GENERATION_MODEL_KWARGS
            )
            logger.info(f"result in generate sql internal for token input size: {result}")
            # Extract SQL from the result
            parsed_entities = {}
            if hasattr(result, 'content'):
                extracted_data = self._extract_sql_from_content(result.content)
                
                sql_content = extracted_data["sql"]
                parsed_entities = extracted_data["parsed_entities"]
                
                if not sql_content:
                    return {
                        "valid_generation_results": [],
                        "invalid_generation_results": [{
                            "sql": "",
                            "type": "GENERATION_ERROR",
                            "error": "No valid SQL found in LLM response"
                        }]
                    }
                
                # Format as JSON for post-processor
                sql_json = {
                    "sql": sql_content,
                    "parsed_entities": parsed_entities
                }
                result = json.dumps(sql_json)
            
            
            # Post-process the result
            try:
                
                post_processed_result = await self.gen_processor.run(
                    [result],
                    timeout=kwargs.get("timeout", 30.0),
                    project_id=kwargs.get("project_id")
                )
                
                print("post_processed_result in generate sql internal", parsed_entities)
               
                
                
                return {
                    "valid_generation_results": [{
                        "sql": sql_content,
                        "parsed_entities": parsed_entities,
                        "reasoning": reasoning,
                        "type": "GENERATION_SUCCESS"
                    }],
                    "invalid_generation_results": []
                }
            except Exception as e:
                logger.error(f"Error in post-processing: {e}")
                # Attempt SQL correction when post-processing fails
                correction_result = await self._handle_post_processing_error_with_correction(
                    query=query,
                    sql_content=sql_content,
                    reasoning=reasoning,
                    schema_contexts=schema_data["schema_contexts"],
                    error_message=str(e),
                    **kwargs
                )
                return correction_result

        except Exception as e:
            logger.exception(f"Error in SQL generation: {e}")
            return {
                "valid_generation_results": [],
                "invalid_generation_results": [{
                    "sql": "",
                    "type": "GENERATION_ERROR",
                    "error": str(e)
                }]
            }
    
    async def _breakdown_sql_internal(self, query: str, sql: str, language: str) -> Dict[str, Any]:
        """Internal SQL breakdown logic"""
        try:
            prompt_template = PromptTemplate(
                input_variables=["query", "sql", "language"],
                template="""
                ### INPUT ###
                User's Question: {query}
                SQL query: {sql}
                Language: {language}
                
                Let's think step by step.
                """
            )
            
            system_prompt = self.system_prompts[SQLOperationType.BREAKDOWN.value]
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            user_prompt = prompt_template.format(query=query, sql=sql, language=language)
            prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
            
            logger.info("Breaking down SQL with prompt:")
            logger.info(f"Query: {query}")
            logger.info(f"SQL: {sql}")
            logger.info(f"Language: {language}")
            
            result = await self.llm.ainvoke(prompt)
            logger.info(f"LLM SQL breakdown result: {result}")
            
            return {"breakdown": result, "success": True}
        except Exception as e:
            logger.error(f"Error in internal SQL breakdown: {e}")
            return {"breakdown": "", "success": False, "error": str(e)}
    
    async def _expand_sql_internal(self, query: str, original_sql: str, contexts: Any, original_reasoning: str, original_query: str) -> Dict[str, Any]:
        """Internal SQL expansion logic"""
        try:
            prompt_template = PromptTemplate(
                input_variables=["query", "original_sql", "contexts", "original_reasoning", "original_query"],
                template="""
                ### DATABASE SCHEMA ###
                {contexts}
                
                ### QUESTION ###
                User's adjustment request: {query}
                Original SQL: {original_sql}
                reasoning: {original_reasoning}
                original_query: {original_query}
                """
            )
            
            system_prompt = """
            ### TASK ###
            You are a great data analyst. You are now given a task to expand original SQL from user input.
            
            ### INSTRUCTIONS ###
            - Columns are mentioned from the user's adjustment request
            - Please donot create a new table only use the schemas provided to you in the request.
            - Columns to be adjusted must belong to the given database schema; if no such column exists, keep sql empty string
            - You can add/delete/modify columns, add/delete/modify keywords such as DISTINCT or apply aggregate functions on columns
            
            ### FINAL ANSWER FORMAT ###
            The final answer must be a SQL query in JSON format:
            {
                "sql": <SQL_QUERY_STRING>
            }
            """
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            user_prompt = prompt_template.format(
                query=query, 
                original_sql=original_sql, 
                contexts="\n".join(contexts),
                original_reasoning=original_reasoning,
                original_query=original_query
            )
            prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
            result = await self.llm.ainvoke(prompt)
            
            return {"sql": result, "success": True}
        except Exception as e:
            logger.error(f"Error in internal SQL expansion: {e}")
            return {"sql": "", "success": False, "error": str(e)}
    
    async def _correct_sql_internal(self, sql: str, error_message: str, contexts: List[str]) -> Dict[str, Any]:
        """Internal SQL correction logic"""
        try:
            system_prompt = f"""
            ### TASK ###
            You are an ANSI SQL expert with exceptional logical thinking skills and debugging skills.
            Now you are given syntactically incorrect ANSI SQL query and related error message, please generate the syntactically correct ANSI SQL query without changing original semantics.
            You are also given the database schema, please use it to generate the correct SQL query.
            You are also given the reasoning used to construct the sql query.                
            {TEXT_TO_SQL_RULES}
            
            ### FINAL ANSWER FORMAT ###
            The final answer must be a corrected SQL query in JSON format:
            {{
                "sql": <CORRECTED_SQL_QUERY_STRING>
                "sql_correction_reasoning": <SQL_CORRECTION_REASONING_STRING>
            }}
            """
            
            prompt_template = PromptTemplate(
                input_variables=["contexts", "sql", "error_message"],
                template="""
                ### DATABASE SCHEMA ###
                {contexts}
                
                ### QUESTION ###
                SQL: {sql}
                Error Message: {error_message}
                
                Let's think step by step.
                """
            )
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            user_prompt = prompt_template.format(
                contexts="\n".join(contexts),
                sql=sql,
                error_message=error_message
            )
            prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
            result = await self.llm.ainvoke(prompt)
            
            # Extract content from the result
            if hasattr(result, 'content'):
                result_content = result.content
            else:
                result_content = str(result)
            
            # Try to parse the JSON response
            try:
                print("result_content in sql correction", result_content)# First try to extract JSON from the content
                extracted_data = self._extract_sql_from_content(result_content)
                
                # If we have a JSON response with sql_correction_reasoning, parse it
                if isinstance(result_content, str) and result_content.strip().startswith('{'):
                    try:
                        json_data = json.loads(result_content)
                        if isinstance(json_data, dict):
                            corrected_sql = json_data.get("sql", "")
                            correction_reasoning = json_data.get("sql_correction_reasoning", "")
                            
                            return {
                                "sql": corrected_sql,
                                "sql_correction_reasoning": correction_reasoning,
                                "success": True
                            }
                    except json.JSONDecodeError:
                        pass
                print("extracted_data in sql correction", extracted_data)
                # Fallback to extracted SQL if JSON parsing fails
                corrected_sql = extracted_data.get("sql", result_content)
                return {
                    "sql": corrected_sql,
                    "sql_correction_reasoning": f"Corrected SQL based on error: {error_message}",
                    "success": True
                }
                
            except Exception as parse_error:
                logger.warning(f"Error parsing correction result: {parse_error}")
                return {
                    "sql": result_content,
                    "sql_correction_reasoning": f"Raw correction result: {result_content}",
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"Error in internal SQL correction: {e}")
            return {"sql": "", "sql_correction_reasoning": "", "success": False, "error": str(e)}
    
    async def _handle_post_processing_error_with_correction(
        self,
        query: str,
        sql_content: str,
        reasoning: str,
        schema_contexts: List[str],
        error_message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle post-processing errors by attempting SQL correction
        
        This method is automatically called when post-processing fails in SQL generation.
        It can also be called manually using the convenience function `correct_sql_with_rag()`.
        
        The method combines all available context (schema, reasoning, original query) to
        provide the correction system with comprehensive information for better results.
        
        Args:
            query: Original user query
            sql_content: Generated SQL that failed post-processing
            reasoning: Reasoning used to generate the SQL
            schema_contexts: Database schema contexts
            error_message: Post-processing error message
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with correction attempt results containing:
            - valid_generation_results: List of successful corrections
            - invalid_generation_results: List of failed corrections with error details and recommendations
            
            Each invalid result may include:
            - sql: The corrected SQL (if available)
            - sql_correction_reasoning: Reasoning behind the correction attempt
            - type: Error type (CORRECTION_SUCCESS, CORRECTION_VALIDATION_ERROR, etc.)
            - error: Error message
            - original_error: Original post-processing error
            - recommendations: List of suggestions for fixing the issue
            - correction_attempted: Boolean indicating if correction was attempted
        """
        try:
            logger.info(f"Attempting SQL correction for post-processing error: {error_message}")
            
            # Combine all contexts for correction
            all_contexts = schema_contexts.copy()
            
            # Add reasoning as context if available
            if reasoning:
                all_contexts.append(f"### REASONING CONTEXT ###\n{reasoning}")
            
            # Add original query as context
            all_contexts.append(f"### ORIGINAL QUERY ###\n{query}")
            
            # Attempt SQL correction
            correction_result = await self._correct_sql_internal(
                sql=sql_content,
                error_message=error_message,
                contexts=all_contexts
            )
            
            if correction_result.get("success", False):
                corrected_sql = correction_result.get("sql", "")
                sql_correction_reasoning = correction_result.get("sql_correction_reasoning", "")
                
                if hasattr(corrected_sql, 'content'):
                    corrected_sql = corrected_sql.content
                
                # Try to extract SQL from correction result
                extracted_data = self._extract_sql_from_content(corrected_sql)
                corrected_sql_content = extracted_data.get("sql", corrected_sql)
                
                # Validate the corrected SQL with post-processor
                try:
                    corrected_json = json.dumps({
                        "sql": corrected_sql_content,
                        "parsed_entities": extracted_data.get("parsed_entities", {})
                    })
                    
                    post_processed_correction = await self.gen_processor.run(
                        [corrected_json],
                        timeout=kwargs.get("timeout", 30.0),
                        project_id=kwargs.get("project_id")
                    )
                    
                    logger.info("SQL correction successful and validated")
                    return {
                        "valid_generation_results": [{
                            "sql": corrected_sql_content,
                            "parsed_entities": extracted_data.get("parsed_entities", {}),
                            "reasoning": reasoning,
                            "sql_correction_reasoning": sql_correction_reasoning,
                            "type": "CORRECTION_SUCCESS",
                            "original_error": error_message
                        }],
                        "invalid_generation_results": []
                    }
                    
                except Exception as validation_error:
                    logger.warning(f"Corrected SQL failed validation: {validation_error}")
                    
                    # Create recommendations based on correction reasoning
                    recommendations = []
                    if sql_correction_reasoning:
                        recommendations.append(f"Correction attempt reasoning: {sql_correction_reasoning}")
                    
                    # Add specific recommendations based on error type
                    validation_error_str = str(validation_error).lower()
                    if "column" in validation_error_str and "not found" in validation_error_str:
                        recommendations.append("Check column names against the database schema")
                        recommendations.append("Verify table aliases and column references")
                    elif "syntax" in validation_error_str:
                        recommendations.append("Review SQL syntax and ensure proper formatting")
                        recommendations.append("Check for missing or extra parentheses, quotes, or semicolons")
                    elif "table" in validation_error_str and "not found" in validation_error_str:
                        recommendations.append("Verify table names exist in the database")
                        recommendations.append("Check table aliases and schema references")
                    elif "type" in validation_error_str and "mismatch" in validation_error_str:
                        recommendations.append("Ensure data types match between columns and values")
                        recommendations.append("Check for proper type casting where needed")
                    else:
                        recommendations.append("Review the SQL query for logical or structural issues")
                        recommendations.append("Consider simplifying the query or breaking it into smaller parts")
                    
                    return {
                        "valid_generation_results": [],
                        "invalid_generation_results": [{
                            "sql": corrected_sql_content,
                            "sql_correction_reasoning": sql_correction_reasoning,
                            "type": "CORRECTION_VALIDATION_ERROR",
                            "error": str(validation_error),
                            "original_error": error_message,
                            "recommendations": recommendations,
                            "correction_attempted": True
                        }]
                    }
            else:
                logger.warning(f"SQL correction failed: {correction_result.get('error', 'Unknown error')}")
                
                # Create recommendations for correction failure
                recommendations = []
                if correction_result.get("sql_correction_reasoning"):
                    recommendations.append(f"Correction attempt reasoning: {correction_result.get('sql_correction_reasoning')}")
                
                recommendations.extend([
                    "The SQL correction system was unable to fix the query automatically",
                    "Consider reviewing the original query and database schema",
                    "Check if the query logic matches the intended business requirement"
                ])
                
                return {
                    "valid_generation_results": [],
                    "invalid_generation_results": [{
                        "sql": sql_content,
                        "type": "CORRECTION_FAILED",
                        "error": correction_result.get("error", "Correction attempt failed"),
                        "original_error": error_message,
                        "recommendations": recommendations,
                        "correction_attempted": True
                    }]
                }
                
        except Exception as e:
            logger.error(f"Error in post-processing error correction handler: {e}")
            
            # Create recommendations for handler error
            recommendations = [
                "An error occurred during the SQL correction process",
                "The correction system encountered an unexpected issue",
                "Consider manually reviewing and fixing the SQL query",
                "Check the database schema and query requirements"
            ]
            
            return {
                "valid_generation_results": [],
                "invalid_generation_results": [{
                    "sql": sql_content,
                    "type": "CORRECTION_HANDLER_ERROR",
                    "error": str(e),
                    "original_error": error_message,
                    "recommendations": recommendations,
                    "correction_attempted": False
                }]
            }
    
    async def _reason_sql_internal(self, query: str, contexts: List[str], language: str) -> Dict[str, Any]:
        """Internal SQL reasoning logic"""
        try:
            prompt_template = PromptTemplate(
                input_variables=["query", "contexts", "language"],
                template="""
                ### DATABASE SCHEMA ###
                {contexts}
                
                ### QUESTION ###
                User's Question: {query}
                Language: {language}
                
                Let's think step by step.
                """
            )
            
            system_prompt = self.system_prompts[SQLOperationType.REASONING.value]
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            user_prompt = prompt_template.format(
                query=query,
                contexts="\n".join(contexts),
                language=language
            )
            prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
            
            logger.info("Generating SQL reasoning with prompt:")
            #logger.info(f"Query: {query}")
            #logger.info(f"Contexts: {contexts}")
            #logger.info(f"Language: {language}")
            
            result = await self.llm.ainvoke(prompt)
            #logger.info(f"LLM SQL reasoning result: {result}")
            
            return {"reasoning": result, "success": True}
        except Exception as e:
            logger.error(f"Error in internal SQL reasoning: {e}")
            return {"reasoning": "", "success": False, "error": str(e)}
    
    async def _answer_sql_internal(self, query: str, sql: str, sql_data: Dict, language: str) -> Dict[str, Any]:
        """Internal SQL answer logic"""
        try:
            prompt_template = PromptTemplate(
                input_variables=["query", "sql", "sql_data", "language"],
                template="""
                ### Input
                User's question: {query}
                SQL: {sql}
                Data: {sql_data}
                Language: {language}
                
                Please think step by step and answer the user's question.
                """
            )
            
            system_prompt = self.system_prompts[SQLOperationType.ANSWER.value]
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            user_prompt = prompt_template.format(
                query=query,
                sql=sql,
                sql_data=orjson.dumps(sql_data).decode(),
                language=language
            )
            prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
            
            logger.info("Generating SQL answer with prompt:")
            logger.info(f"Query: {query}")
            logger.info(f"SQL: {sql}")
            logger.info(f"SQL Data: {sql_data}")
            logger.info(f"Language: {language}")
            
            result = await self.llm.ainvoke(prompt)
            logger.info(f"LLM SQL answer result: {result}")
            
            return {"answer": result, "success": True}
        except Exception as e:
            logger.error(f"Error in internal SQL answer: {e}")
            return {"answer": "", "success": False, "error": str(e)}
    
    async def _question_sql_internal(self, sqls: List[str], language: str) -> Dict[str, Any]:
        """Internal SQL to question logic"""
        try:
            questions = []
            for sql in sqls:
                prompt_template = PromptTemplate(
                    input_variables=["sql", "language"],
                    template="""
                    SQL: {sql}
                    Language: {language}
                    
                    Let's think step by step.
                    """
                )
                
                system_prompt = """
                ### TASK ###
                You are a data analyst great at translating any SQL query into a question that can be answered by the given SQL query.
                
                ### INSTRUCTIONS ###
                - The question should be in the language of the user provided
                - The question should be a single sentence, concise, and easy to understand
                
                ### OUTPUT FORMAT ###
                Please return the result in the following JSON format:
                {
                    "question": <QUESTION_STRING_IN_USER_LANGUAGE>
                }
                """
                
                full_prompt = PromptTemplate(
                    input_variables=["system_prompt", "user_prompt"],
                    template="{system_prompt}\n\n{user_prompt}"
                )
                
                user_prompt = prompt_template.format(sql=sql, language=language)
                prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
                
                logger.info("Converting SQL to question with prompt:")
                logger.info(f"SQL: {sql}")
                logger.info(f"Language: {language}")
                
                result = await self.llm.ainvoke(prompt)
                logger.info(f"LLM SQL to question result: {result}")
                
                try:
                    question_data = orjson.loads(result)
                    questions.append(question_data.get("question", ""))
                except:
                    questions.append(result)
            
            return {"questions": questions, "success": True}
        except Exception as e:
            logger.error(f"Error in internal SQL question: {e}")
            return {"questions": [], "success": False, "error": str(e)}
    
    async def _summarize_sql_internal(self, query: str, sqls: List[str], language: str) -> Dict[str, Any]:
        """Internal SQL summary logic"""
        try:
            prompt_template = PromptTemplate(
                input_variables=["query", "sqls", "language"],
                template="""
                User's Question: {query}
                SQLs: {sqls}
                Language: {language}
                
                Please think step by step.
                """
            )
            
            system_prompt = """
            ### TASK ###
            You are a great data analyst. You are now given a task to summarize a list SQL queries in a human-readable format where each summary should be within 10-20 words.
            You will be given a list of SQL queries and a user's question.
            
            ### INSTRUCTIONS ###
            - SQL query summary must be within 10-20 words.
            - SQL query summary must be human-readable and easy to understand.
            - SQL query summary must be concise and to the point.
            - SQL query summary must be in the same language user specified.
            
            ### OUTPUT FORMAT ###
            Please return the result in the following JSON format:
            {
                "sql_summary_results": [
                    {
                        "summary": <SQL_QUERY_SUMMARY_STRING>
                    }
                ]
            }
            """
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            user_prompt = prompt_template.format(
                query=query,
                sqls=orjson.dumps(sqls).decode(),
                language=language
            )
            prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
            
            logger.info("Generating SQL summary with prompt:")
            logger.info(f"Query: {query}")
            logger.info(f"SQLs: {sqls}")
            logger.info(f"Language: {language}")
            
            result = await self.llm.ainvoke(prompt)
            logger.info(f"LLM SQL summary result: {result}")
            
            return {"summaries": result, "success": True}
        except Exception as e:
            logger.error(f"Error in internal SQL summary: {e}")
            return {"summaries": "", "success": False, "error": str(e)}
    
    async def process_sql_request(
        self,
        operation: SQLOperationType,
        query: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Main entry point for processing SQL requests with self-correction"""
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            try:
                attempt += 1
                logger.info(f"Processing {operation.value} request, attempt {attempt} {kwargs}")
                print(f"trying post process result {operation.value}")
                if operation == SQLOperationType.GENERATION:
                    return await self._handle_sql_generation(query, **kwargs)
                elif operation == SQLOperationType.BREAKDOWN:
                    return await self._handle_sql_breakdown(query, **kwargs)
                elif operation == SQLOperationType.EXPANSION:
                    return await self._handle_sql_expansion(query, **kwargs)
                elif operation == SQLOperationType.CORRECTION:
                    return await self._handle_sql_correction(query, **kwargs)
                elif operation == SQLOperationType.REASONING:
                    return await self._handle_sql_reasoning(query, **kwargs)
                elif operation == SQLOperationType.ANSWER:
                    return await self._handle_sql_answer(query, **kwargs)
                elif operation == SQLOperationType.QUESTION:
                    return await self._handle_sql_question(query, **kwargs)
                elif operation == SQLOperationType.SUMMARY:
                    return await self._handle_sql_summary(query, **kwargs)
                else:
                    return {"error": f"Unknown operation: {operation.value}", "success": False}
                    
            except Exception as e:
                logger.error(f"Error in attempt {attempt}: {e}")
                if attempt == max_attempts:
                    return {"error": str(e), "success": False}
                continue
        
        return {"error": "Max attempts reached", "success": False}
    
    async def _handle_sql_generation(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL generation with RAG and self-correction"""
        # Retrieve relevant schema
        schema_data = await self.retrieval_helper.get_table_names_and_schema_contexts(
            query=query,
            project_id=kwargs.get("project_id", "default"),
            table_retrieval={
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
        )
        
        schema_contexts = schema_data.get("schema_contexts", [])
        
        # Generate reasoning first
        reasoning_result = await self._reason_sql_internal(
            query, schema_contexts, kwargs.get("language", "English")
        )
        
        reasoning = reasoning_result.get("reasoning", "")
        if hasattr(reasoning, 'content'):
            # Extract content and remove markdown formatting
            content = reasoning.content
            reasoning = content
        
        # Generate SQL with the reasoning
        sql_result = await self._generate_sql_internal(
            query, schema_contexts, reasoning, kwargs.get("configuration", {})
        )
        
        # Standardize the result format
        standardized_result = {
            "success": bool(sql_result.get("valid_generation_results")),
            "data": {
                "sql": "",
                "type": "GENERATION_SUCCESS",
                "processing_time_seconds": sql_result.get("processing_time_seconds", 0),
                "data": {},
                "timestamp": sql_result.get("timestamp", ""),
                "operation_type": sql_result.get("operation_type", "generation"),
                "reasoning": reasoning,
                "parsed_entities": sql_result.get("parsed_entities", {})
            },
            "error": None
        }
        
        # Add valid generation results if available
        if sql_result.get("valid_generation_results"):
            valid_result = sql_result["valid_generation_results"][0]
            standardized_result["data"]["sql"] = valid_result.get("sql", "")
            standardized_result["data"]["type"] = valid_result.get("type", "GENERATION_SUCCESS")
            standardized_result["data"]["parsed_entities"] = valid_result.get("parsed_entities", {})
        
        # Add reasoning
        standardized_result["data"]["reasoning"] = reasoning
        
        # Add error if no valid results
        if not standardized_result["success"]:
            standardized_result["error"] = "Failed to generate valid SQL"
            logger.warning(f"Failed to generate SQL for query: {query} with reasoning: {reasoning} and schema_contexts: {schema_contexts}")
        
        print("standardized_result2 in sql generation", standardized_result)
        return standardized_result
    
    async def _handle_sql_breakdown(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL breakdown"""
        sql = kwargs.get("sql", "")
        language = kwargs.get("language", "English")
        
        breakdown_result = await self._breakdown_sql_internal(query, sql, language)
        print(f"breakdown_result: {breakdown_result}")
        if breakdown_result.get("success", False):
            # Extract content from AIMessage if needed
            breakdown_json = breakdown_result.get("breakdown", "")
            if hasattr(breakdown_json, 'content'):
                breakdown_json = breakdown_json.content
            
            # Post-process breakdown
            postprocess_result = await self.breakdown_processor.run(
                [breakdown_json],
                project_id=kwargs.get("project_id"),
                timeout=kwargs.get("timeout", 30.0)
            )
            
            return {
                "breakdown": postprocess_result,
                "success": True
            }
        
        return breakdown_result
    
    async def _handle_sql_expansion(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL expansion"""
        original_sql = kwargs.get("original_sql", "")
        contexts = kwargs.get("contexts", [])
         #contexts = kwargs.get("contexts", [])
        original_query = kwargs.pop('original_query', "")
        project_id = kwargs.pop('project_id', "")
        reasoning = kwargs.pop('reasoning', "")
        
       
        schema_data = await self.retrieval_helper.get_table_names_and_schema_contexts(
            query=original_query,
            project_id=project_id,
            table_retrieval={
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
        )
        
        schema_contexts = schema_data.get("schema_contexts", [])        
        
        
        expansion_result = await self._expand_sql_internal(query,  original_sql, schema_contexts, reasoning, original_query)
        
        if expansion_result.get("success", False):
            expanded_sql = expansion_result.get("sql", "")
            if hasattr(expanded_sql, 'content'):
                expanded_sql = expanded_sql.content
            
            # Validate expanded SQL
            validation_result = await self.gen_processor.run(
                [expanded_sql],
                timeout=kwargs.get("timeout", 30.0),
                project_id=kwargs.get("project_id")
            )
            
            valid_results = validation_result.get("valid_generation_results", [])
            if valid_results:
                return {
                    "sql": valid_results[0]["sql"],
                    "success": True,
                    "correlation_id": valid_results[0].get("correlation_id", "")
                }
        
        return expansion_result
    
    async def _handle_sql_correction(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL correction"""
        sql = kwargs.get("sql", "")
        error_message = kwargs.get("error_message", "")
        #contexts = kwargs.get("contexts", [])
        original_query = kwargs.pop('original_query', "")
        project_id = kwargs.pop('project_id', "")
        
        schema_data = await self.retrieval_helper.get_table_names_and_schema_contexts(
            query=original_query,
            project_id=project_id,
            table_retrieval={
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
        )
        
        schema_contexts = schema_data.get("schema_contexts", [])
        correction_result = await self._correct_sql_internal(sql, error_message, schema_contexts)
        
        if correction_result.get("success", False):
            corrected_sql = correction_result.get("sql", "")
            sql_correction_reasoning = correction_result.get("sql_correction_reasoning", "")
            
            if hasattr(corrected_sql, 'content'):
                corrected_sql = corrected_sql.content
            correction_result["sql"] = corrected_sql
            
        return correction_result
    
    async def _handle_sql_reasoning(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL reasoning"""
        contexts = kwargs.get("contexts", [])
        language = kwargs.get("language", "English")
        
        reasoning_result = await self._reason_sql_internal(query, contexts, language)
        
        if reasoning_result.get("success", False):
            reasoning = reasoning_result.get("reasoning", "")
            if hasattr(reasoning, 'content'):
                reasoning = reasoning.content
            reasoning_result["reasoning"] = reasoning
        
        return reasoning_result
    
    async def _handle_sql_answer(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL answer generation"""
        sql = kwargs.get("sql", "")
        sql_data = kwargs.get("sql_data", {})
        language = kwargs.get("language", "English")
        
        answer_result = await self._answer_sql_internal(query, sql, sql_data, language)
        
        if answer_result.get("success", False):
            answer = answer_result.get("answer", "")
            if hasattr(answer, 'content'):
                answer = answer.content
            answer_result["answer"] = answer
            
        return answer_result
    
    async def _handle_sql_question(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL to question conversion"""
        sqls = kwargs.get("sqls", [])
        language = kwargs.get("language", "English")
        
        question_result = await self._question_sql_internal(sqls, language)
        
        if question_result.get("success", False):
            questions = question_result.get("questions", [])
            # Handle AIMessage in questions list
            processed_questions = []
            for q in questions:
                if hasattr(q, 'content'):
                    processed_questions.append(q.content)
                else:
                    processed_questions.append(q)
            question_result["questions"] = processed_questions
            
        return question_result
    
    async def _handle_sql_summary(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle SQL summary generation"""
        sqls = kwargs.get("sqls", [])
        language = kwargs.get("language", "English")
        
        summary_result = await self._summarize_sql_internal(query, sqls, language)
        
        if summary_result.get("success", False):
            summaries = summary_result.get("summaries", "")
            if hasattr(summaries, 'content'):
                summaries = summaries.content
            summary_result["summaries"] = summaries
            
        return summary_result


# Factory function and convenience wrappers
def create_sql_rag_agent(llm, engine: Engine,document_store_provider: DocumentStoreProvider, **kwargs) -> SQLRAGAgent:
    """Factory function to create SQL RAG agent"""
    return SQLRAGAgent(llm=llm, engine=engine,document_store_provider=document_store_provider, **kwargs)


# Convenience functions for different operations
async def generate_sql_with_rag(
    agent: SQLRAGAgent,
    query: str,
    language: str = "English",
    configuration: Dict = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate SQL using RAG agent"""
    return await agent.process_sql_request(
        SQLOperationType.GENERATION,
        query,
        language=language,
        configuration=configuration,
        **kwargs
    )


async def breakdown_sql_with_rag(
    agent: SQLRAGAgent,
    query: str,
    sql: str,
    language: str = "English",
    **kwargs
) -> Dict[str, Any]:
    """Breakdown SQL using RAG agent"""
    return await agent.process_sql_request(
        SQLOperationType.BREAKDOWN,
        query,
        sql=sql,
        language=language,
        **kwargs
    )


async def answer_with_sql_rag(
    agent: SQLRAGAgent,
    query: str,
    sql: str,
    sql_data: Dict,
    language: str = "English",
    **kwargs
) -> Dict[str, Any]:
    """Generate answer from SQL results using RAG agent"""
    return await agent.process_sql_request(
        SQLOperationType.ANSWER,
        query,
        sql=sql,
        sql_data=sql_data,
        language=language,
        **kwargs
    )


async def correct_sql_with_rag(
    agent: SQLRAGAgent,
    query: str,
    sql: str,
    reasoning: str,
    schema_contexts: List[str],
    error_message: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Correct SQL using RAG agent with comprehensive context
    
    Args:
        agent: SQLRAGAgent instance
        query: Original user query
        sql: SQL that needs correction
        reasoning: Reasoning used to generate the SQL
        schema_contexts: Database schema contexts
        error_message: Error message from post-processing or execution
        **kwargs: Additional arguments
        
    Returns:
        Dictionary with correction results
    """
    return await agent._handle_post_processing_error_with_correction(
        query=query,
        sql_content=sql,
        reasoning=reasoning,
        schema_contexts=schema_contexts,
        error_message=error_message,
        **kwargs
    )


# Integration with SQL RAG Agent
class EnhancedSQLRAGAgent:
    """
    Enhanced SQL RAG Agent with integrated relevance scoring
    This is a wrapper class that enhances any SQL RAG agent with scoring capabilities
    """
    
    def __init__(self, base_agent, relevance_scorer: SQLAdvancedRelevanceScorer = None):
        """
        Initialize enhanced agent with relevance scoring
        
        Args:
            base_agent: Original SQLRAGAgent instance
            relevance_scorer: Advanced relevance scorer instance
        """
        self.base_agent = base_agent
        self.relevance_scorer = relevance_scorer or SQLAdvancedRelevanceScorer()
        self.scoring_history = []
        self.performance_metrics = {
            "total_queries": 0,
            "high_quality_queries": 0,
            "correction_attempts": 0,
            "successful_corrections": 0
        }
        
        # Quality thresholds
        self.quality_thresholds = {
            "excellent": 0.8,
            "good": 0.6,
            "fair": 0.4,
            "poor": 0.0
        }
    
    def update_schema_context(self, schema_context: Dict[str, Any]):
        """Update schema context for scoring"""
        if self.relevance_scorer:
            self.relevance_scorer.schema_context.update(schema_context)
            self.relevance_scorer._extract_schema_elements()
    
    async def generate_sql_with_scoring(self, query: str, **kwargs) -> dict:
        """
        Generate SQL with integrated relevance scoring and iterative improvement
        
        Args:
            query: Natural language query
            **kwargs: Additional arguments for SQL generation
            
        Returns:
            Dictionary with SQL result and relevance scores
        """
        max_attempts = kwargs.get("max_improvement_attempts", 3)
        current_attempt = 0
        best_result = None
        best_score = 0.0
        
        schema_context = kwargs.get('schema_context', {})
        if schema_context:
            self.update_schema_context(schema_context)
        
        while current_attempt < max_attempts:
            current_attempt += 1
            
            # Generate SQL using base agent
            sql_result = await self.base_agent.process_sql_request(
                self.base_agent.SQLOperationType.GENERATION,
                query,
                **kwargs
            )
            
            if not sql_result.get("success", False):
                continue
            
            # Score the reasoning and SQL quality
            model_output = f"""
            ### REASONING ###
            {sql_result.get('reasoning', '')}
            
            ### SQL ###
            {sql_result.get('sql', '')}
            """
            
            scoring_result = self.relevance_scorer.score_sql_reasoning(
                model_output, query, schema_context
            )
            
            # Add scoring to result
            sql_result.update({
                "relevance_scoring": scoring_result,
                "quality_level": scoring_result["quality_level"],
                "final_score": scoring_result["final_relevance_score"],
                "improvement_recommendations": self.relevance_scorer.get_improvement_recommendations(scoring_result),
                "attempt_number": current_attempt
            })
            
            current_score = scoring_result["final_relevance_score"]
            
            # Keep track of best result
            if current_score > best_score:
                best_result = sql_result
                best_score = current_score
            
            # If we have excellent quality, we can stop early
            if current_score >= self.quality_thresholds["excellent"]:
                break
            
            # If quality is poor and we have attempts left, try to improve
            if current_score < self.quality_thresholds["fair"] and current_attempt < max_attempts:
                improvement_feedback = self._generate_improvement_feedback(scoring_result)
                kwargs["additional_context"] = improvement_feedback
                continue
            
            break
        
        # Update performance metrics
        self.performance_metrics["total_queries"] += 1
        if best_score >= self.quality_thresholds["good"]:
            self.performance_metrics["high_quality_queries"] += 1
        
        # Store in history for analysis
        self.scoring_history.append({
            "query": query,
            "timestamp": datetime.datetime.now().isoformat(),
            "score": best_score,
            "quality_level": best_result["quality_level"],
            "attempts_made": current_attempt,
            "operation_type": scoring_result["detected_operation_type"]
        })
        
        return best_result
    
    def _generate_improvement_feedback(self, scoring_result: Dict) -> str:
        """Generate improvement feedback based on scoring results"""
        recommendations = self.relevance_scorer.get_improvement_recommendations(scoring_result)
        
        feedback_parts = [
            "Based on quality analysis, please improve the following aspects:",
        ]
        
        for i, rec in enumerate(recommendations[:3], 1):  # Top 3 recommendations
            feedback_parts.append(f"{i}. {rec}")
        
        return "\n".join(feedback_parts)
    
    async def correct_sql_with_scoring(self, sql: str, error_message: str, **kwargs) -> dict:
        """
        Correct SQL with quality assessment of the correction
        
        Args:
            sql: Original SQL query
            error_message: Error message from execution
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with corrected SQL and correction quality scores
        """
        self.performance_metrics["correction_attempts"] += 1
        
        # Get correction from base agent
        correction_result = await self.base_agent.process_sql_request(
            self.base_agent.SQLOperationType.CORRECTION,
            "",  # Query not needed for correction
            sql=sql,
            error_message=error_message,
            **kwargs
        )
        
        if not correction_result.get("success", False):
            return correction_result
        
        # Score correction quality
        corrected_sql = correction_result.get("sql", "")
        reasoning = correction_result.get("reasoning", "")
        
        correction_score = self.relevance_scorer.score_sql_correction_quality(
            sql, corrected_sql, error_message, reasoning
        )
        
        correction_result.update({
            "correction_scoring": correction_score,
            "correction_quality": correction_score["total_correction_score"],
            "improvement_achieved": correction_score["improvement_score"]
        })
        
        # Update metrics
        if correction_score["total_correction_score"] >= 0.6:
            self.performance_metrics["successful_corrections"] += 1
        
        return correction_result
    
    async def breakdown_sql_with_scoring(self, query: str, sql: str, **kwargs) -> dict:
        """Breakdown SQL with scoring of explanation quality"""
        breakdown_result = await self.base_agent.process_sql_request(
            self.base_agent.SQLOperationType.BREAKDOWN,
            query,
            sql=sql,
            **kwargs
        )
        
        if breakdown_result.get("success", False):
            # Score the breakdown explanation quality
            explanation_output = f"""
            ### REASONING ###
            {breakdown_result.get('reasoning', '')}
            
            ### BREAKDOWN ###
            {breakdown_result.get('breakdown', '')}
            """
            
            schema_context = kwargs.get('schema_context', {})
            scoring_result = self.relevance_scorer.score_sql_reasoning(
                explanation_output, query, schema_context
            )
            
            breakdown_result.update({
                "explanation_scoring": scoring_result,
                "explanation_quality": scoring_result["quality_level"],
                "explanation_score": scoring_result["final_relevance_score"]
            })
        
        return breakdown_result
    
    async def answer_with_scoring(self, query: str, sql: str, sql_data: Dict, **kwargs) -> dict:
        """Generate natural language answer with quality scoring"""
        answer_result = await self.base_agent.process_sql_request(
            self.base_agent.SQLOperationType.ANSWER,
            query,
            sql=sql,
            sql_data=sql_data,
            **kwargs
        )
        
        if answer_result.get("success", False):
            # Score the answer quality based on how well it explains the SQL results
            answer_output = f"""
            ### REASONING ###
            Based on the SQL query results, I need to provide a clear explanation.
            
            ### ANSWER ###
            {answer_result.get('answer', '')}
            """
            
            schema_context = kwargs.get('schema_context', {})
            scoring_result = self.relevance_scorer.score_sql_reasoning(
                answer_output, query, schema_context
            )
            
            answer_result.update({
                "answer_scoring": scoring_result,
                "answer_quality": scoring_result["quality_level"],
                "answer_score": scoring_result["final_relevance_score"]
            })
        
        return answer_result
    
    def get_performance_analytics(self) -> dict:
        """Get comprehensive performance analytics from scoring history"""
        if not self.scoring_history:
            return {
                "message": "No scoring history available",
                "performance_metrics": self.performance_metrics
            }
        
        scores = [entry["score"] for entry in self.scoring_history]
        quality_levels = [entry["quality_level"] for entry in self.scoring_history]
        
        # Quality distribution
        quality_distribution = {
            "excellent": quality_levels.count("excellent"),
            "good": quality_levels.count("good"), 
            "fair": quality_levels.count("fair"),
            "poor": quality_levels.count("poor")
        }
        
        # Recent trend analysis
        recent_scores = scores[-10:] if len(scores) > 10 else scores
        trend_direction = "improving" if len(recent_scores) > 1 and recent_scores[-1] > recent_scores[0] else "stable"
        
        # Calculate success rates
        success_rates = {
            "overall_success_rate": self.performance_metrics["high_quality_queries"] / max(1, self.performance_metrics["total_queries"]),
            "correction_success_rate": self.performance_metrics["successful_corrections"] / max(1, self.performance_metrics["correction_attempts"])
        }
        
        return {
            "total_queries": len(self.scoring_history),
            "average_score": sum(scores) / len(scores),
            "median_score": sorted(scores)[len(scores)//2] if scores else 0,
            "score_range": {
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0
            },
            "quality_distribution": quality_distribution,
            "recent_trend": {
                "direction": trend_direction,
                "recent_scores": recent_scores
            },
            "performance_metrics": self.performance_metrics,
            "success_rates": success_rates,
            "improvement_areas": self._identify_improvement_areas()
        }
    
    def get_quality_insights(self) -> Dict[str, Any]:
        """Get detailed quality insights and recommendations"""
        analytics = self.get_performance_analytics()
        
        insights = []
        recommendations = []
        
        # Analyze quality distribution
        quality_dist = analytics.get("quality_distribution", {})
        total_queries = sum(quality_dist.values())
        
        if total_queries == 0:
            return {"message": "No data available for quality insights"}
        
        excellent_rate = quality_dist.get("excellent", 0) / total_queries
        poor_rate = quality_dist.get("poor", 0) / total_queries
        
        if excellent_rate > 0.7:
            insights.append("System is performing excellently with high-quality SQL generation")
        elif excellent_rate < 0.3:
            insights.append("System needs improvement in SQL generation quality")
            recommendations.extend([
                "Review and enhance reasoning prompts",
                "Provide more comprehensive schema context",
                "Implement additional training on complex queries"
            ])
        
        if poor_rate > 0.3:
            insights.append("High rate of poor-quality outputs detected")
            recommendations.extend([
                "Implement additional validation steps",
                "Enhance error handling mechanisms",
                "Review base model capabilities"
            ])
        
        return {
            "insights": insights,
            "recommendations": recommendations,
            "quality_metrics": {
                "excellent_rate": excellent_rate,
                "poor_rate": poor_rate,
                "average_score": analytics.get("average_score", 0)
            }
        }
    
    def _identify_improvement_areas(self) -> List[str]:
        """Identify common improvement areas from scoring history"""
        if not self.scoring_history:
            return []
        
        improvement_areas = []
        
        # Analyze recent low scores
        recent_entries = self.scoring_history[-20:] if len(self.scoring_history) > 20 else self.scoring_history
        low_score_entries = [entry for entry in recent_entries if entry["score"] < 0.6]
        
        if len(low_score_entries) > len(recent_entries) * 0.3:  # More than 30% low scores
            improvement_areas.extend([
                "Focus on multi-step reasoning for complex queries",
                "Improve schema awareness in reasoning",
                "Consider edge cases and error handling",
                "Enhance SQL syntax and structure quality"
            ])
        
        # Analyze operation types with consistent low scores
        operation_scores = {}
        for entry in recent_entries:
            op_type = entry.get("operation_type", "unknown")
            if op_type not in operation_scores:
                operation_scores[op_type] = []
            operation_scores[op_type].append(entry["score"])
        
        for op_type, scores in operation_scores.items():
            if len(scores) > 2 and sum(scores) / len(scores) < 0.5:
                improvement_areas.append(f"Improve {op_type} query handling and reasoning")
        
        return improvement_areas[:5]  # Return top 5 areas
    
    def export_scoring_data(self, filepath: str = None) -> str:
        """Export all scoring data for analysis"""
        if not filepath:
            filepath = f"enhanced_sql_scoring_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            "metadata": {
                "export_timestamp": datetime.datetime.now().isoformat(),
                "total_entries": len(self.scoring_history)
            },
            "scoring_history": self.scoring_history,
            "performance_metrics": self.performance_metrics,
            "analytics": self.get_performance_analytics(),
            "quality_insights": self.get_quality_insights()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return filepath

