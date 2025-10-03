import asyncio
import logging
from typing import Any, Dict, List, Optional
from enum import Enum

import orjson
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from pydantic import BaseModel

from app.agents.nodes.sql.utils.sql_prompts import (
    TEXT_TO_SQL_RULES,
    construct_instructions,
    Configuration
)

from app.core.engine import Engine
import datetime
import pytz
import logging

logger = logging.getLogger("lexy-ai-service")


class SQLGenerationTool:
    """Individual SQL generation tool"""
    
    def __init__(self, llm, engine: Engine):
        self.llm = llm
        self.engine = engine
        self.name = "sql_generation"
        self.description = "Generates SQL queries from natural language questions"
    
    async def run(
        self,
        query: str,
        contexts: List[str],
        reasoning: str = "",
        configuration: Configuration = Configuration(),
        **kwargs
    ) -> Dict[str, Any]:
        """Generate SQL from natural language query"""
        try:
            system_prompt = f"""
You are a helpful assistant that converts natural language queries into ANSI SQL queries.
Given user's question, database schema, etc., you should think deeply and carefully and generate the SQL query based on the given reasoning plan step by step.

{TEXT_TO_SQL_RULES}

### FINAL ANSWER FORMAT ###
The final answer must be a ANSI SQL query in JSON format:
{{
    "sql": <SQL_QUERY_STRING>
}}
"""
            
            prompt_template = PromptTemplate(
                input_variables=["query", "contexts", "reasoning", "instructions", "current_time"],
                template="""
### DATABASE SCHEMA ###
{contexts}

{instructions}

### QUESTION ###
User's Question: {query}
Current Time: {current_time}

{reasoning}

Let's think step by step.
"""
            )
            
            instructions = construct_instructions(configuration)
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            user_prompt = prompt_template.format(
                query=query,
                contexts="\n".join(contexts),
                reasoning=f"### REASONING PLAN ###\n{reasoning}" if reasoning else "",
                instructions=f"### INSTRUCTIONS ###\n{instructions}" if instructions else "",
                current_time=configuration.show_current_time()
            )
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            try:
                sql_data = orjson.loads(result)
                return {
                    "sql": sql_data.get("sql", ""),
                    "success": True
                }
            except:
                return {
                    "sql": result,
                    "success": True
                }
            
        except Exception as e:
            logger.error(f"Error in SQL generation: {e}")
            return {
                "sql": "",
                "success": False,
                "error": str(e)
            }


class SQLBreakdownTool:
    """Individual SQL breakdown tool"""
    
    def __init__(self, llm, engine: Engine):
        self.llm = llm
        self.engine = engine
        self.name = "sql_breakdown"
        self.description = "Breaks down complex SQL queries into understandable steps"
    
    async def run(
        self,
        query: str,
        sql: str,
        language: str = "English",
        **kwargs
    ) -> Dict[str, Any]:
        """Break down SQL into steps"""
        try:
            system_prompt = """
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
    "steps": [
        {
            "sql": <SQL_QUERY_STRING_1>,
            "summary": <SUMMARY_STRING_1>,
            "cte_name": <CTE_NAME_STRING_1>
        },
        ...
    ]
}
"""
            
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
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            user_prompt = prompt_template.format(
                query=query,
                sql=sql,
                language=language
            )
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            try:
                breakdown_data = orjson.loads(result)
                return {
                    "description": breakdown_data.get("description", ""),
                    "steps": breakdown_data.get("steps", []),
                    "success": True
                }
            except:
                return {
                    "description": result,
                    "steps": [],
                    "success": False,
                    "error": "Failed to parse breakdown result"
                }
            
        except Exception as e:
            logger.error(f"Error in SQL breakdown: {e}")
            return {
                "description": "",
                "steps": [],
                "success": False,
                "error": str(e)
            }


class SQLReasoningTool:
    """Individual SQL reasoning tool"""
    
    def __init__(self, llm):
        self.llm = llm
        self.name = "sql_reasoning"
        self.description = "Generates reasoning plans for SQL query creation"
    
    async def run(
        self,
        query: str,
        contexts: List[str],
        language: str = "English",
        sql_samples: List[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate reasoning plan for SQL"""
        try:
            system_prompt = """
### TASK ###
You are a helpful data analyst who is great at thinking deeply and reasoning about the user's question and the database schema, and you provide a step-by-step reasoning plan in order to answer the user's question.

### INSTRUCTIONS ###
1. Think deeply and reason about the user's question and the database schema.
2. Give a step by step reasoning plan in order to answer user's question.
3. The reasoning plan should be in the language same as the language user provided in the input.
4. Make sure to consider the current time provided in the input if the user's question is related to the date/time.
5. Each step in the reasoning plan must start with a number, a title(in bold format in markdown), and a reasoning for the step.
6. If SQL SAMPLES are provided, make sure to consider them in the reasoning plan.

### SCHEMA ANALYSIS REQUIREMENTS ###
Before generating your reasoning plan, you MUST:
- **SCHEMA VALIDATION**: Carefully examine the database schema and identify all available tables and their exact column names (case-sensitive)
- **COLUMN EXISTENCE VERIFICATION**: For any column you plan to use, verify it exists in the schema exactly as written and use the exact case-sensitive name
- **CALCULATED FIELDS IDENTIFICATION**: Look for pre-calculated fields that can be used directly instead of recreating calculations
- **METRICS IDENTIFICATION**: Look for tables marked as "metric" with base objects, dimensions, and measures
- **REFERENCE FORMAT**: Table names must be in format: `table: <table_name>`, Column names must be in format: `column: <table_name>.<column_name>`
- **NO SQL CODE**: Do not include SQL code in the reasoning plan
- **NO MARKDOWN BLOCKS**: Do not include ```markdown or ``` in the answer

### CALCULATION REASONING WHEN NO PRE-CALCULATED FIELDS ###
When no calculated fields or metrics are available, you MUST:
- **ANALYZE THE USER'S INTENT**: Understand what calculation or aggregation the user is asking for
- **IDENTIFY BASE COLUMNS**: Determine which raw columns from the schema can be used to perform the calculation
- **REASON THROUGH THE CALCULATION**: Think step-by-step about how to derive the desired result from available columns
- **CONSIDER AGGREGATION FUNCTIONS**: Determine if you need SUM, COUNT, AVG, MIN, MAX, or other SQL functions
- **PLAN GROUPING**: Identify which columns should be used for GROUP BY clauses
- **CONSIDER FILTERING**: Determine if WHERE clauses are needed to filter the data
- **THINK ABOUT RELATIONSHIPS**: If multiple tables are involved, reason through how to join them properly
- **VALIDATE CALCULATION LOGIC**: Ensure the calculation approach makes logical sense for the user's question

### CRITICAL SCHEMA RULES ###
- **ONLY use columns that exist in the provided schema**
- **Use exact column names as they appear in the schema (case-sensitive)**
- **Verify table names exist before referencing them**
- **For calculated fields, use the pre-calculated values when available**
- **For metrics, understand the base object and use appropriate dimensions/measures**
- **NEVER invent or assume column names that don't exist in the schema**

### FINAL ANSWER FORMAT ###
The final answer must be a reasoning plan in plain Markdown string format
"""
            
            samples_text = ""
            if sql_samples:
                samples_text = "\n### SQL SAMPLES ###\n"
                for sample in sql_samples:
                    samples_text += f"Question: {sample.get('question', '')}\n"
                    samples_text += f"SQL: {sample.get('sql', '')}\n\n"
            
            prompt_template = PromptTemplate(
                input_variables=["query", "contexts", "language", "samples"],
                template="""
### DATABASE SCHEMA ###
{contexts}

{samples}

### QUESTION ###
User's Question: {query}
Language: {language}

Let's think step by step.
"""
            )
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            user_prompt = prompt_template.format(
                query=query,
                contexts="\n".join(contexts),
                language=language,
                samples=samples_text
            )
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            return {
                "reasoning": result,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in SQL reasoning: {e}")
            return {
                "reasoning": "",
                "success": False,
                "error": str(e)
            }


class SQLAnswerTool:
    """Individual SQL answer tool"""
    
    def __init__(self, llm):
        self.llm = llm
        self.name = "sql_answer"
        self.description = "Converts SQL query results to natural language answers"
    
    async def run(
        self,
        query: str,
        sql: str,
        sql_data: Dict,
        language: str = "English",
        **kwargs
    ) -> Dict[str, Any]:
        """Generate natural language answer from SQL results"""
        try:
            system_prompt = """
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
"""
            
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
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            user_prompt = prompt_template.format(
                query=query,
                sql=sql,
                sql_data=orjson.dumps(sql_data).decode(),
                language=language
            )
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            return {
                "answer": result,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in SQL answer: {e}")
            return {
                "answer": "",
                "success": False,
                "error": str(e)
            }


class SQLCorrectionTool:
    """Individual SQL correction tool"""
    
    def __init__(self, llm, engine: Engine):
        self.llm = llm
        self.engine = engine
        self.name = "sql_correction"
        self.description = "Corrects invalid SQL queries based on error messages"
    
    async def run(
        self,
        sql: str,
        error_message: str,
        contexts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Correct invalid SQL"""
        try:
            system_prompt = f"""
### TASK ###
You are an ANSI SQL expert with exceptional logical thinking skills and debugging skills.
Now you are given syntactically incorrect ANSI SQL query and related error message, please generate the syntactically correct ANSI SQL query without changing original semantics.

{TEXT_TO_SQL_RULES}

### FINAL ANSWER FORMAT ###
The final answer must be a corrected SQL query in JSON format:
{{
    "sql": <CORRECTED_SQL_QUERY_STRING>
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
            
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            user_prompt = prompt_template.format(
                contexts="\n".join(contexts),
                sql=sql,
                error_message=error_message
            )
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            try:
                corrected_data = orjson.loads(result)
                return {
                    "sql": corrected_data.get("sql", ""),
                    "success": True
                }
            except:
                return {
                    "sql": result,
                    "success": True
                }
            
        except Exception as e:
            logger.error(f"Error in SQL correction: {e}")
            return {
                "sql": "",
                "success": False,
                "error": str(e)
            }


class SQLExpansionTool:
    """Individual SQL expansion tool"""
    
    def __init__(self, llm, engine: Engine):
        self.llm = llm
        self.engine = engine
        self.name = "sql_expansion"
        self.description = "Expands SQL queries based on user adjustment requests"
    
    async def run(
        self,
        adjustment_request: str,
        original_sql: str,
        contexts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Expand SQL based on user request"""
        try:
            system_prompt = """
### TASK ###
You are a great data analyst. You are now given a task to expand original SQL from user input.

### INSTRUCTIONS ###
- Columns are given from the user's adjustment request
- Columns to be adjusted must belong to the given database schema; if no such column exists, keep sql empty string
- You can add/delete/modify columns, add/delete/modify keywords such as DISTINCT or apply aggregate functions on columns
- Consider current time from user input if user's adjustment request is related to date and time

### FINAL ANSWER FORMAT ###
The final answer must be a SQL query in JSON format:
{
    "sql": <SQL_QUERY_STRING>
}
"""
            
            prompt_template = PromptTemplate(
                input_variables=["adjustment_request", "original_sql", "contexts"],
                template="""
### DATABASE SCHEMA ###
{contexts}

### QUESTION ###
User's adjustment request: {adjustment_request}
Original SQL: {original_sql}
"""
            )
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            user_prompt = prompt_template.format(
                adjustment_request=adjustment_request,
                original_sql=original_sql,
                contexts="\n".join(contexts)
            )
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            try:
                expanded_data = orjson.loads(result)
                return {
                    "sql": expanded_data.get("sql", ""),
                    "success": True
                }
            except:
                return {
                    "sql": result,
                    "success": True
                }
            
        except Exception as e:
            logger.error(f"Error in SQL expansion: {e}")
            return {
                "sql": "",
                "success": False,
                "error": str(e)
            }


class SQLQuestionTool:
    """Individual SQL to question tool"""
    
    def __init__(self, llm):
        self.llm = llm
        self.name = "sql_question"
        self.description = "Converts SQL queries to natural language questions"
    
    async def run(
        self,
        sqls: List[str],
        language: str = "English",
        **kwargs
    ) -> Dict[str, Any]:
        """Convert SQL to questions"""
        try:
            questions = []
            
            for sql in sqls:
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
                
                prompt_template = PromptTemplate(
                    input_variables=["sql", "language"],
                    template="""
SQL: {sql}
Language: {language}

Let's think step by step.
"""
                )
                
                full_prompt = PromptTemplate(
                    input_variables=["system_prompt", "user_prompt"],
                    template="{system_prompt}\n\n{user_prompt}"
                )
                
                chain = LLMChain(llm=self.llm, prompt=full_prompt)
                
                user_prompt = prompt_template.format(sql=sql, language=language)
                
                result = await chain.arun(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )
                
                try:
                    question_data = orjson.loads(result)
                    questions.append(question_data.get("question", ""))
                except:
                    questions.append(result)
            
            return {
                "questions": questions,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in SQL question generation: {e}")
            return {
                "questions": [],
                "success": False,
                "error": str(e)
            }


class SQLSummaryTool:
    """Individual SQL summary tool"""
    
    def __init__(self, llm):
        self.llm = llm
        self.name = "sql_summary"
        self.description = "Summarizes SQL queries in human-readable format"
    
    async def run(
        self,
        query: str,
        sqls: List[str],
        language: str = "English",
        **kwargs
    ) -> Dict[str, Any]:
        """Summarize SQL queries"""
        try:
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
            
            prompt_template = PromptTemplate(
                input_variables=["query", "sqls", "language"],
                template="""
User's Question: {query}
SQLs: {sqls}
Language: {language}

Please think step by step.
"""
            )
            
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            chain = LLMChain(llm=self.llm, prompt=full_prompt)
            
            user_prompt = prompt_template.format(
                query=query,
                sqls=orjson.dumps(sqls).decode(),
                language=language
            )
            
            result = await chain.arun(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            try:
                summary_data = orjson.loads(result)
                summaries = summary_data.get("sql_summary_results", [])
                return {
                    "summaries": [s.get("summary", "") for s in summaries],
                    "success": True
                }
            except:
                return {
                    "summaries": [result],
                    "success": False,
                    "error": "Failed to parse summary result"
                }
            
        except Exception as e:
            logger.error(f"Error in SQL summary: {e}")
            return {
                "summaries": [],
                "success": False,
                "error": str(e)
            }


# Tool factory functions
def create_sql_generation_tool(llm, engine: Engine) -> Tool:
    """Create Langchain tool for SQL generation"""
    sql_gen = SQLGenerationTool(llm, engine)
    
    def generate_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_gen.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_generator",
        description="Generates SQL queries from natural language. Input should be JSON with 'query', 'contexts', 'reasoning', and 'configuration' fields.",
        func=generate_func
    )


def create_sql_breakdown_tool(llm, engine: Engine) -> Tool:
    """Create Langchain tool for SQL breakdown"""
    sql_breakdown = SQLBreakdownTool(llm, engine)
    
    def breakdown_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_breakdown.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_breakdown",
        description="Breaks down complex SQL into steps. Input should be JSON with 'query', 'sql', and 'language' fields.",
        func=breakdown_func
    )


def create_sql_reasoning_tool(llm) -> Tool:
    """Create Langchain tool for SQL reasoning"""
    sql_reasoning = SQLReasoningTool(llm)
    
    def reasoning_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_reasoning.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_reasoner",
        description="Generates reasoning plans for SQL. Input should be JSON with 'query', 'contexts', 'language', and optional 'sql_samples' fields.",
        func=reasoning_func
    )


def create_sql_answer_tool(llm) -> Tool:
    """Create Langchain tool for SQL answer generation"""
    sql_answer = SQLAnswerTool(llm)
    
    def answer_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_answer.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_answerer",
        description="Converts SQL results to natural language. Input should be JSON with 'query', 'sql', 'sql_data', and 'language' fields.",
        func=answer_func
    )


def create_sql_correction_tool(llm, engine: Engine) -> Tool:
    """Create Langchain tool for SQL correction"""
    sql_correction = SQLCorrectionTool(llm, engine)
    
    def correction_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_correction.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_corrector",
        description="Corrects invalid SQL queries. Input should be JSON with 'sql', 'error_message', and 'contexts' fields.",
        func=correction_func
    )


def create_sql_expansion_tool(llm, engine: Engine) -> Tool:
    """Create Langchain tool for SQL expansion"""
    sql_expansion = SQLExpansionTool(llm, engine)
    
    def expansion_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_expansion.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_expander",
        description="Expands SQL based on user requests. Input should be JSON with 'adjustment_request', 'original_sql', and 'contexts' fields.",
        func=expansion_func
    )


def create_sql_question_tool(llm) -> Tool:
    """Create Langchain tool for SQL to question conversion"""
    sql_question = SQLQuestionTool(llm)
    
    def question_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_question.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_questioner",
        description="Converts SQL to questions. Input should be JSON with 'sqls' and 'language' fields.",
        func=question_func
    )


def create_sql_summary_tool(llm) -> Tool:
    """Create Langchain tool for SQL summary"""
    sql_summary = SQLSummaryTool(llm)
    
    def summary_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(sql_summary.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="sql_summarizer",
        description="Summarizes SQL queries. Input should be JSON with 'query', 'sqls', and 'language' fields.",
        func=summary_func
    )


# Pydantic models for structured outputs
class SQLGenerationResult(BaseModel):
    sql: str
    success: bool
    error: Optional[str] = None


class SQLBreakdownResult(BaseModel):
    description: str
    steps: List[Dict[str, str]]
    success: bool
    error: Optional[str] = None


class SQLReasoningResult(BaseModel):
    reasoning: str
    success: bool
    error: Optional[str] = None


class SQLAnswerResult(BaseModel):
    answer: str
    success: bool
    error: Optional[str] = None