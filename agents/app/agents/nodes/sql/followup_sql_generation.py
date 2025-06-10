import asyncio
import logging
from typing import Any, Optional

import orjson
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langfuse.decorators import observe

from app.core.engine_provider import EngineProvider
from app.core.engine import Engine
from app.core.provider import get_embedder
from app.agents.nodes.sql.utils.sql_prompts import (
    Configuration,
    construct_instructions,
    sql_generation_system_prompt,
    AskHistory
)
from app.agents.nodes.sql.utils.sql import SQLGenPostProcessor
from app.agents.retrieval.sql_functions import SqlFunction


from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

logger = logging.getLogger("lexy-ai-service")


text_to_sql_with_followup_user_prompt_template = """
### TASK ###
Given the following user's follow-up question and previous SQL query and summary,
generate one SQL query to best answer user's question.

### DATABASE SCHEMA ###
{documents}

{instructions_section}

{sql_functions_section}

{sql_samples_section}

### CONTEXT ###
User's query history:
{histories}

### QUESTION ###
User's Follow-up Question: {query}
Current Time: {current_time}

### REASONING PLAN ###
{sql_generation_reasoning}

Let's think step by step.
"""


class FollowUpSQLGenerationTool:
    """Langchain tool for follow-up SQL generation"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "followup_sql_generation"
        self.description = "Generates SQL queries for follow-up questions"
        
        # Initialize engine and post processor using EngineProvider
        self.engine = EngineProvider.get_engine()
        self.post_processor = SQLGenPostProcessor(engine=self.engine)
        self.engine_timeout = 30  # Default timeout in seconds
        
        # User queues for streaming support
        self._user_queues = {}

    @observe(capture_input=False)
    def create_prompt(
        self,
        query: str,
        contexts: list[str],
        histories: list[AskHistory],
        sql_samples: list[dict],
        instructions: list[dict],
        configuration: Configuration,
        sql_functions: list[SqlFunction] = None,
        sql_generation_reasoning: str = "",
    ) -> str:
        """Create prompt for SQL generation"""
        try:
            # Format documents
            formatted_documents = "\n".join(contexts) if contexts else ""
            
            # Format instructions section
            instructions_text = construct_instructions(
                configuration=configuration,
                instructions=instructions,
            )
            instructions_section = f"### INSTRUCTIONS ###\n{instructions_text}" if instructions_text else ""
            
            # Format SQL functions section
            if sql_functions:
                functions_text = "\n".join(str(func) for func in sql_functions)
                sql_functions_section = f"### SQL FUNCTIONS ###\n{functions_text}"
            else:
                sql_functions_section = ""
            
            # Format SQL samples section
            if sql_samples:
                samples_text = []
                for sample in sql_samples:
                    samples_text.append(f"Summary:\n{sample.get('summary', '')}\nSQL:\n{sample.get('sql', '')}")
                sql_samples_section = f"### SQL SAMPLES ###\n" + "\n\n".join(samples_text)
            else:
                sql_samples_section = ""
            
            # Format histories
            formatted_histories = []
            for history in histories:
                formatted_histories.append(f"{history.question}\n{history.sql}")
            formatted_histories = "\n\n".join(formatted_histories)
            
            prompt_template = PromptTemplate(
                input_variables=[
                    "documents", "instructions_section", "sql_functions_section",
                    "sql_samples_section", "histories", "query", "current_time",
                    "sql_generation_reasoning"
                ],
                template=text_to_sql_with_followup_user_prompt_template
            )
            
            return prompt_template.format(
                documents=formatted_documents,
                instructions_section=instructions_section,
                sql_functions_section=sql_functions_section,
                sql_samples_section=sql_samples_section,
                histories=formatted_histories,
                query=query,
                current_time=configuration.show_current_time(),
                sql_generation_reasoning=sql_generation_reasoning
            )
        except Exception as e:
            logger.error(f"Error creating prompt: {e}")
            return ""

    @observe(as_type="generation", capture_input=False)
    async def generate_sql(self, prompt_input: str, query_id: str = None) -> dict:
        """Generate SQL using LLM"""
        try:
            # Create full prompt with system and user parts
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Create the chain
            chain = (
                {
                    "system_prompt": lambda _: sql_generation_system_prompt,
                    "user_prompt": RunnablePassthrough()
                }
                | full_prompt
                | self.llm
                | StrOutputParser()
            )
            
            # Generate response using the chain
            result = await chain.ainvoke(prompt_input)
            
            # Update metrics
            self.doc_store_provider.update_metrics("sql_generation", "query")
            
            return {"replies": [result]}
        except Exception as e:
            logger.error(f"Error in SQL generation: {e}")
            return {"replies": [""]}

    @observe(capture_input=False)
    async def post_process(
        self,
        generate_result: dict,
        project_id: str = None,
    ) -> dict:
        """Post-process generated SQL"""
        return await self.post_processor.run(
            generate_result.get("replies"),
            timeout=self.engine_timeout,
            project_id=project_id,
        )

    async def run(
        self,
        query: str,
        contexts: list[str],
        sql_generation_reasoning: str,
        histories: list[AskHistory],
        configuration: Configuration = Configuration(),
        sql_samples: list[dict] = None,
        instructions: list[dict] = None,
        project_id: str = None,
        has_calculated_field: bool = False,
        has_metric: bool = False,
        sql_functions: list[SqlFunction] = None,
    ) -> dict:
        """Main execution method for follow-up SQL generation"""
        try:
            logger.info("Follow-Up SQL Generation pipeline is running...")
            
            # Step 1: Create prompt
            prompt_input = self.create_prompt(
                query=query,
                contexts=contexts,
                histories=histories,
                sql_samples=sql_samples,
                instructions=instructions,
                configuration=configuration,
                sql_functions=sql_functions,
                sql_generation_reasoning=sql_generation_reasoning,
            )
            
            # Step 2: Generate SQL
            generate_result = await self.generate_sql(prompt_input)
            
            # Step 3: Post-process
            final_result = await self.post_process(generate_result, project_id)
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in follow-up SQL generation: {e}")
            return {
                "valid_generation_results": [],
                "invalid_generation_results": [],
                "error": str(e)
            }


class FollowUpSQLGeneration:
    """Main FollowUpSQLGeneration class maintaining original interface"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider, **kwargs):
        self.tool = FollowUpSQLGenerationTool(doc_store_provider)

    @observe(name="Follow-Up SQL Generation")
    async def run(
        self,
        query: str,
        contexts: list[str],
        sql_generation_reasoning: str,
        histories: list[AskHistory],
        configuration: Configuration = Configuration(),
        sql_samples: list[dict] = None,
        instructions: list[dict] = None,
        project_id: str = None,
        has_calculated_field: bool = False,
        has_metric: bool = False,
        sql_functions: list[SqlFunction] = None,
    ) -> dict:
        """Run follow-up SQL generation with original interface"""
        return await self.tool.run(
            query=query,
            contexts=contexts,
            sql_generation_reasoning=sql_generation_reasoning,
            histories=histories,
            configuration=configuration,
            sql_samples=sql_samples,
            instructions=instructions,
            project_id=project_id,
            has_calculated_field=has_calculated_field,
            has_metric=has_metric,
            sql_functions=sql_functions,
        )


def create_followup_sql_generation_tool(doc_store_provider: DocumentStoreProvider) -> Tool:
    """Create Langchain tool for follow-up SQL generation"""
    generation_tool = FollowUpSQLGenerationTool(doc_store_provider)
    
    def generation_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(generation_tool.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="followup_sql_generator",
        description="Generates SQL queries for follow-up questions. Input should be JSON with 'query', 'contexts', 'histories', and optional configuration fields.",
        func=generation_func
    )


if __name__ == "__main__":
    # Test the follow-up SQL generation tool
    async def test_followup_generation():
        from app.core.dependencies import get_doc_store_provider
        
        doc_store_provider = get_doc_store_provider()
        generation = FollowUpSQLGeneration(doc_store_provider)
        
        result = await generation.run(
            query="this is a test query",
            contexts=[],
            histories=[]
        )
        
        print("Follow-up SQL Generation Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(test_followup_generation())