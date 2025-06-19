import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
import os

import aiohttp
import orjson
from langchain.agents import Tool
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.core.engine import (
    Engine,
    add_quotes,
    clean_generation_result,
)
from app.core.dependencies import get_llm
from app.agents.nodes.sql.utils.sql_prompts import Configuration, TEXT_TO_SQL_RULES, sql_generation_system_prompt, calculated_field_instructions, metric_instructions, construct_instructions
from app.agents.retrieval.retrieval_helper import RetrievalHelper
logger = logging.getLogger("lexy-ai-service")


class SQLBreakdownGenPostProcessor:
    """Langchain tool for processing SQL breakdown generation results"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
        self.name = "sql_breakdown_postprocessor"
        self.description = "Post-processes SQL breakdown generation results"

    async def run(
        self,
        replies: List[str],
        project_id: str | None = None,
        timeout: Optional[float] = 30.0,
    ) -> Dict[str, Any]:
        cleaned_generation_result = orjson.loads(clean_generation_result(replies[0]))

        steps = cleaned_generation_result.get("steps", [])
        if not steps:
            return {
                "description": cleaned_generation_result["description"],
                "steps": [],
            }

        # make sure the last step has an empty cte_name
        steps[-1]["cte_name"] = ""

        for step in steps:
            step["sql"], error_message = add_quotes(step["sql"])
            if error_message:
                return {
                    "description": cleaned_generation_result["description"],
                    "steps": [],
                }

        sql = self._build_cte_query(steps)

        if not await self._check_if_sql_executable(
            sql,
            project_id=project_id,
            timeout=timeout,
        ):
            return {
                "description": cleaned_generation_result["description"],
                "steps": [],
            }

        return {
            "description": cleaned_generation_result["description"],
            "steps": steps,
        }

    def _build_cte_query(self, steps) -> str:
        ctes = ",\n".join(
            f"{step['cte_name']} AS ({step['sql']})"
            for step in steps
            if step["cte_name"]
        )

        return f"WITH {ctes}\n" + steps[-1]["sql"] if ctes else steps[-1]["sql"]

    async def _check_if_sql_executable(
        self,
        sql: str,
        project_id: str | None = None,
        timeout: Optional[float] = 30.0,
    ):
        async with aiohttp.ClientSession() as session:
            status, addition = await self._engine.execute_sql(
                sql,
                session,
                project_id=project_id,
                timeout=timeout,
            )

        if not status:
            logger.exception(
                f"SQL is not executable: {addition.get('error_message', '')}"
            )

        return status


class SQLGenPostProcessor:
    """Langchain tool for processing SQL generation results"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
        self.name = "sql_gen_postprocessor"
        self.description = "Post-processes SQL generation results and validates them"

    async def _classify_invalid_generation_results(
        self,
        generation_results: list[str],
        timeout: float,
        project_id: str | None = None,
    ) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        valid_generation_results = []
        invalid_generation_results = []

        async def _task(sql: str):
            quoted_sql, error_message = add_quotes(sql)
            if not error_message:
                status, addition = await self._engine.execute_sql(
                  quoted_sql, session, project_id=project_id,dry_run=True, timeout=timeout
                )
                #dummy_generator = DummyDataGenerator(get_llm())
                #result = await dummy_generator.generate_data(sql)
                
               

                if status:
                    valid_generation_results.append(
                        {
                            "sql": quoted_sql,
                            "correlation_id": addition.get("correlation_id", ""),
                        }
                    )
                    print("valid_generation_results in sql gen post processor", valid_generation_results)
                else:
                    error_message = addition.get("error_message", "")
                    invalid_generation_results.append(
                        {
                            "sql": quoted_sql,
                            "type": "TIME_OUT"
                            if error_message.startswith("Request timed out")
                            else "DRY_RUN",
                            "error": error_message,
                            "correlation_id": addition.get("correlation_id", ""),
                        }
                    )
            else:
                invalid_generation_results.append(
                    {
                        "sql": sql,
                        "type": "ADD_QUOTES",
                        "error": error_message,
                    }
                )

        async with aiohttp.ClientSession() as session:
            tasks = [
                _task(generation_result) for generation_result in generation_results
            ]
            await asyncio.gather(*tasks)

        return valid_generation_results, invalid_generation_results

    def _serialize_aimessage(self, message: Any) -> str:
        """Convert AIMessage to string for JSON serialization"""
        if hasattr(message, 'content'):
            return str(message.content)
        return str(message)

    async def run(
        self,
        replies: List[str] | List[List[str]] | List[Any],
        timeout: Optional[float] = 30.0,
        project_id: str | None = None,
    ) -> dict:
        try:
            # Handle AIMessage objects by extracting their content
            if hasattr(replies[0], 'content'):
                replies = [self._serialize_aimessage(reply) for reply in replies]
            
            if not replies or not replies[0]:
                logger.warning("Empty replies received in SQLGenPostProcessor")
                return {
                    "valid_generation_results": [],
                    "invalid_generation_results": [{
                        "sql": "",
                        "type": "EMPTY_REPLY",
                        "error": "Empty reply received"
                    }]
                }

            logger.debug(f"Raw reply content: {replies[0]}")
            
            if isinstance(replies[0], dict):
                cleaned_generation_result = []
                for reply in replies:
                    try:
                        if not reply.get("replies") or not reply["replies"][0]:
                            logger.warning(f"Empty reply in dictionary: {reply}")
                            continue
                            
                        cleaned_result = clean_generation_result(reply["replies"][0])
                        logger.debug(f"Cleaned result from dictionary: {cleaned_result}")
                        
                        if not cleaned_result:
                            logger.warning(f"Empty cleaned result for reply: {reply}")
                            continue
                            
                        try:
                            parsed_result = orjson.loads(cleaned_result)
                            logger.debug(f"Parsed result from dictionary: {parsed_result}")
                            
                            if "sql" not in parsed_result:
                                logger.warning(f"No SQL in parsed result: {parsed_result}")
                                continue
                                
                            cleaned_generation_result.append(parsed_result["sql"])
                        except orjson.JSONDecodeError as e:
                            logger.error(f"JSON decode error in dictionary processing: {e}")
                            logger.error(f"Failed to parse content: {cleaned_result}")
                            continue
                    except Exception as e:
                        logger.exception(f"Error processing dictionary reply: {e}")
            else:
                try:
                    cleaned_result = clean_generation_result(replies[0])
                    logger.debug(f"Cleaned result: {cleaned_result}")
                    
                    if not cleaned_result:
                        logger.warning("Empty cleaned result")
                        return {
                            "valid_generation_results": [],
                            "invalid_generation_results": [{
                                "sql": "",
                                "type": "EMPTY_CLEANED_RESULT",
                                "error": "Empty cleaned result"
                            }]
                        }
                    
                    # Try to clean the result if it's not valid JSON
                    if not cleaned_result.strip().startswith('{'):
                        logger.warning(f"Result is not JSON format, attempting to extract JSON: {cleaned_result}")
                        # Try to find JSON-like content
                        import re
                        json_match = re.search(r'\{.*\}', cleaned_result, re.DOTALL)
                        if json_match:
                            cleaned_result = json_match.group(0)
                            logger.debug(f"Extracted JSON content: {cleaned_result}")
                        else:
                            logger.error("Could not find JSON content in result")
                            return {
                                "valid_generation_results": [],
                                "invalid_generation_results": [{
                                    "sql": "",
                                    "type": "INVALID_JSON_FORMAT",
                                    "error": "Could not find valid JSON content"
                                }]
                            }
                    
                    try:
                        parsed_result = orjson.loads(cleaned_result)
                        logger.debug(f"Parsed result: {parsed_result}")
                        
                        if "sql" not in parsed_result:
                            logger.warning(f"No SQL in parsed result: {parsed_result}")
                            return {
                                "valid_generation_results": [],
                                "invalid_generation_results": [{
                                    "sql": "",
                                    "type": "NO_SQL_IN_RESULT",
                                    "error": "No SQL found in result"
                                }]
                            }
                            
                        cleaned_generation_result = parsed_result["sql"]
                    except orjson.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                        logger.error(f"Failed to parse content: {cleaned_result}")
                        return {
                            "valid_generation_results": [],
                            "invalid_generation_results": [{
                                "sql": "",
                                "type": "JSON_DECODE_ERROR",
                                "error": f"Failed to parse JSON: {str(e)}"
                            }]
                        }
                except Exception as e:
                    logger.exception(f"Error processing reply: {e}")
                    return {
                        "valid_generation_results": [],
                        "invalid_generation_results": [{
                            "sql": "",
                            "type": "PROCESSING_ERROR",
                            "error": str(e)
                        }]
                    }

            if isinstance(cleaned_generation_result, str):
                cleaned_generation_result = [cleaned_generation_result]

            if not cleaned_generation_result:
                logger.warning("No valid SQL generation results after processing")
                return {
                    "valid_generation_results": [],
                    "invalid_generation_results": [{
                        "sql": "",
                        "type": "NO_VALID_RESULTS",
                        "error": "No valid SQL generation results after processing"
                    }]
                }
            print("cleaned_generation_result in sql gen post processor", cleaned_generation_result)
            valid_results, invalid_results = await self._classify_invalid_generation_results(
                cleaned_generation_result,
                project_id=project_id,
                timeout=timeout,
            )
            print("valid_results in sql gen post processor", valid_results)
            return {
                "valid_generation_results": valid_results,
                "invalid_generation_results": invalid_results,
            }
        except Exception as e:
            logger.exception(f"Error in SQLGenPostProcessor: {e}")
            return {
                "valid_generation_results": [],
                "invalid_generation_results": [{
                    "sql": "",
                    "type": "UNEXPECTED_ERROR",
                    "error": str(e)
                }]
            }


class SqlGenerationResult(BaseModel):
    sql: str


SQL_GENERATION_MODEL_KWARGS = {
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "sql_generation_result",
            "schema": SqlGenerationResult.model_json_schema(),
        },
    }
}


# Langchain Tools for SQL operations
def create_sql_breakdown_postprocessor_tool(engine: Engine) -> Tool:
    """Create Langchain tool for SQL breakdown post-processing"""
    processor = SQLBreakdownGenPostProcessor(engine)
    
    def breakdown_postprocess_func(input_json: str) -> str:
        """Post-process SQL breakdown results"""
        try:
            input_data = orjson.loads(input_json)
            replies = input_data.get("replies", [])
            project_id = input_data.get("project_id")
            timeout = input_data.get("timeout", 30.0)
            
            result = asyncio.run(processor.run(replies, project_id, timeout))
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in SQL breakdown post-processing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="sql_breakdown_postprocessor",
        description="Post-processes SQL breakdown generation results. Input should be JSON with 'replies', 'project_id', and 'timeout' fields.",
        func=breakdown_postprocess_func
    )


def create_sql_gen_postprocessor_tool(engine: Engine) -> Tool:
    """Create Langchain tool for SQL generation post-processing"""
    processor = SQLGenPostProcessor(engine)
    
    def gen_postprocess_func(input_json: str) -> str:
        """Post-process SQL generation results"""
        try:
            input_data = orjson.loads(input_json)
            replies = input_data.get("replies", [])
            project_id = input_data.get("project_id")
            timeout = input_data.get("timeout", 30.0)
            
            result = asyncio.run(processor.run(replies, timeout, project_id))
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in SQL generation post-processing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="sql_gen_postprocessor",
        description="Post-processes SQL generation results and validates them. Input should be JSON with 'replies', 'project_id', and 'timeout' fields.",
        func=gen_postprocess_func
    )


class DummyDataRow(BaseModel):
    """Model for a single row of dummy data"""
    values: Dict[str, Any] = Field(description="Column values for this row")

class DummyDataResponse(BaseModel):
    """Model for the dummy data response"""
    rows: List[DummyDataRow] = Field(description="List of data rows")
    total_rows: int = Field(description="Total number of rows generated")

class DummyDataGenerator:
    """Generates dummy data for SQL queries using LLM"""
    
    def __init__(self, llm):
        self.llm = llm
        self.parser = PydanticOutputParser(pydantic_object=DummyDataResponse)
        self.retrieval_helper = RetrievalHelper()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data generation expert. Generate realistic dummy data for SQL queries.
            Follow these rules:
            1. Generate exactly 30 rows of data
            2. Make the data realistic and consistent
            3. Ensure data types match the SQL query
            4. Include appropriate relationships between tables
            5. Use realistic values for each column type
            
            {format_instructions}
            """),
            ("human", """Generate dummy data for this SQL query:
            {sql}
            
            The query involves these tables and their schemas:
            {schemas}
            """)
        ])
    
    async def generate_data(self, sql: str,project_id: Optional[str] = None, schemas: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate dummy data for the given SQL query"""
        try:
            # Format schemas for the prompt
            retrieval_helper = RetrievalHelper()
            test_table_retrieval = {
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
            schemas = await retrieval_helper.get_database_schemas(query=sql, table_retrieval=test_table_retrieval, project_id="demo_project")
            """
            schema_text = "\n".join([
                f"Table: {schema.get('table_name')}\n"
                f"DDL: {schema.get('table_ddl')}"
                for schema in schemas
            ])
            """
            import json
            schema_text = json.dumps(schemas)
            
            # Create the chain
            chain = self.prompt | self.llm | self.parser
            
            # Generate the data
            result = await chain.ainvoke({
                "sql": sql,
                "schemas": schema_text,
                "format_instructions": self.parser.get_format_instructions()
            })
            
            # Convert to the expected format
            rows = []
            for row in result.rows:
                rows.append(row.values)
            print("rows in dummy data generator", rows)
            return {
                "status": "success",
                "data": rows,
                "total": result.total_rows
            }
            
        except Exception as e:
            logger.error(f"Error generating dummy data: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "data": []
            }

# Add to the existing code where SQL is executed
async def execute_sql(self, sql: str, session: Any, project_id: str = None, timeout: float = 30.0) -> Tuple[str, Dict[str, Any]]:
    try:
        # If in development/test mode, use dummy data generator
        if os.getenv("USE_DUMMY_DATA", "false").lower() == "true":
            logger.info("Using dummy data generator for SQL execution")
            dummy_generator = DummyDataGenerator(self.llm)
            result = await dummy_generator.generate_data(sql, project_id, self.schemas)
            
            if result["status"] == "success":
                return "success", {
                    "rows": result["data"],
                    "total": result["total"],
                    "is_dummy_data": True
                }
            else:
                return "error", {"error": result["error"]}
        
        # Otherwise, execute the real SQL
        status, addition = await self._engine.execute_sql(
            quoted_sql, session, project_id=project_id, timeout=timeout
        )
        return status, addition
        
    except Exception as e:
        logger.error(f"Error executing SQL: {str(e)}")
        return "error", {"error": str(e)}