import asyncio
import logging
from typing import Any, Optional

import orjson
from langchain.agents import Tool
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langfuse.decorators import observe
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from app.agents.nodes.sql.utils.sql_prompts import construct_instructions, Configuration
from app.agents.nodes.sql.utils.sql_prompts import AskHistory
from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
logger = logging.getLogger("lexy-ai-service")


sql_generation_reasoning_system_prompt = """
### TASK ###
You are a helpful data analyst who is great at thinking deeply and reasoning about the user's question and the database schema, and you provide a step-by-step reasoning plan in order to answer the user's question.

### INSTRUCTIONS ###
1. Think deeply and reason about the user's question and the database schema, and should consider the user's query history.
2. Give a step by step reasoning plan in order to answer user's question.
3. The reasoning plan should be in the language same as the language user provided in the input.
4. Make sure to consider the current time provided in the input if the user's question is related to the date/time.
5. Don't include SQL in the reasoning plan.
6. Each step in the reasoning plan must start with a number, a title(in bold format in markdown), and a reasoning for the step.
7. If SQL SAMPLES are provided, make sure to consider them in the reasoning plan.
8. Do not include ```markdown or ``` in the answer.
9. A table name in the reasoning plan must be in this format: `table: <table_name>`.
10. A column name in the reasoning plan must be in this format: `column: <table_name>.<column_name>`.

### FINAL ANSWER FORMAT ###
The final answer must be a reasoning plan in plain Markdown string format
"""

sql_generation_reasoning_user_prompt_template = """
### DATABASE SCHEMA ###
{documents}

{sql_samples_section}

{instructions_section}

### User's QUERY HISTORY ###
{histories}

### QUESTION ###
User's Question: {query}
Current Time: {current_time}
Language: {language}

Let's think step by step.
"""


class FollowUpSQLGenerationReasoningTool:
    """Langchain tool for follow-up SQL generation reasoning"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self.name = "followup_sql_generation_reasoning"
        self.description = "Generates reasoning for follow-up SQL queries"
        
        # User queues for streaming support
        self._user_queues = {}

    def _streaming_callback(self, chunk, query_id):
        """Callback for streaming responses"""
        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()

        # Put the chunk content into the user's queue
        asyncio.create_task(self._user_queues[query_id].put(chunk.content))
        if chunk.meta.get("finish_reason"):
            asyncio.create_task(self._user_queues[query_id].put("<DONE>"))

    async def get_streaming_results(self, query_id):
        """Get streaming results for a query"""
        async def _get_streaming_results(query_id):
            return await self._user_queues[query_id].get()

        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()

        while True:
            try:
                # Wait for an item from the user's queue
                self._streaming_results = await asyncio.wait_for(
                    _get_streaming_results(query_id), timeout=120
                )
                if (
                    self._streaming_results == "<DONE>"
                ):  # Check for end-of-stream signal
                    del self._user_queues[query_id]
                    break
                if self._streaming_results:  # Check if there are results to yield
                    yield self._streaming_results
                    self._streaming_results = ""  # Clear after yielding
            except TimeoutError:
                break

    @observe(capture_input=False)
    def create_prompt(
        self,
        query: str,
        contexts: list[str],
        histories: list[AskHistory],
        sql_samples: list[dict],
        instructions: list[dict],
        configuration: Configuration
    ) -> str:
        """Create prompt for SQL generation reasoning"""
        try:
            # Format documents
            formatted_documents = "\n".join(contexts) if contexts else ""
            
            # Format SQL samples section
            if sql_samples:
                samples_text = []
                for sample in sql_samples:
                    samples_text.append(f"Question:\n{sample.get('question', '')}\nSQL:\n{sample.get('sql', '')}")
                sql_samples_section = f"### SQL SAMPLES ###\n" + "\n\n".join(samples_text)
            else:
                sql_samples_section = ""
            
            # Format instructions section
            instructions_text = construct_instructions(
                configuration=configuration,
                instructions=instructions,
            )
            instructions_section = f"### INSTRUCTIONS ###\n{instructions_text}" if instructions_text else ""
            
            # Format histories
            formatted_histories = []
            for history in histories:
                formatted_histories.append(f"Question:\n{history.question}\nSQL:\n{history.sql}")
            formatted_histories = "\n\n".join(formatted_histories)
            
            prompt_template = PromptTemplate(
                input_variables=[
                    "documents", "sql_samples_section", "instructions_section",
                    "histories", "query", "current_time", "language"
                ],
                template=sql_generation_reasoning_user_prompt_template
            )
            
            return prompt_template.format(
                documents=formatted_documents,
                sql_samples_section=sql_samples_section,
                instructions_section=instructions_section,
                histories=formatted_histories,
                query=query,
                current_time=configuration.show_current_time(),
                language=configuration.language or "English"
            )
        except Exception as e:
            logger.error(f"Error creating prompt: {e}")
            return ""

    @observe(as_type="generation", capture_input=False)
    async def generate_sql_reasoning(self, prompt_input: str, query_id: str = None) -> dict:
        """Generate SQL reasoning using LLM"""
        try:
            # Create full prompt with system and user parts
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Create the chain
            chain = (
                {
                    "system_prompt": lambda _: sql_generation_reasoning_system_prompt,
                    "user_prompt": RunnablePassthrough()
                }
                | full_prompt
                | self.llm
                | StrOutputParser()
            )
            
            # Generate response using the chain
            result = await chain.ainvoke(prompt_input)
            
            # Update metrics
            self.doc_store_provider.update_metrics("sql_reasoning", "query")
            
            return {"replies": [result]}
        except Exception as e:
            logger.error(f"Error in SQL reasoning generation: {e}")
            return {"replies": [""]}

    @observe()
    def post_process(self, generate_result: dict) -> str:
        """Post-process the generated reasoning"""
        replies = generate_result.get("replies", [""])
        return replies[0] if replies else ""

    async def run(
        self,
        query: str,
        contexts: list[str],
        histories: list[AskHistory],
        sql_samples: Optional[list[dict]] = None,
        instructions: Optional[list[dict]] = None,
        configuration: Configuration = Configuration(),
        query_id: Optional[str] = None,
    ) -> dict:
        """Main execution method for follow-up SQL reasoning"""
        try:
            logger.info("Followup SQL Generation Reasoning pipeline is running...")
            
            # Step 1: Create prompt
            prompt_input = self.create_prompt(
                query=query,
                contexts=contexts,
                histories=histories,
                sql_samples=sql_samples or [],
                instructions=instructions or [],
                configuration=configuration
            )
            
            # Step 2: Generate reasoning
            generate_result = await self.generate_sql_reasoning(prompt_input, query_id)
            
            # Step 3: Post-process
            reasoning = self.post_process(generate_result)
            
            return {
                "reasoning": reasoning,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in follow-up SQL reasoning: {e}")
            return {
                "reasoning": "",
                "success": False,
                "error": str(e)
            }


class FollowUpSQLGenerationReasoning:
    """Main FollowUpSQLGenerationReasoning class maintaining original interface"""
    
    def __init__(self, doc_store_provider: DocumentStoreProvider, **kwargs):
        self.tool = FollowUpSQLGenerationReasoningTool(doc_store_provider)

    def _streaming_callback(self, chunk, query_id):
        """Delegate streaming callback to tool"""
        return self.tool._streaming_callback(chunk, query_id)

    async def get_streaming_results(self, query_id):
        """Delegate streaming results to tool"""
        async for result in self.tool.get_streaming_results(query_id):
            yield result

    @observe(name="FollowupSQL Generation Reasoning")
    async def run(
        self,
        query: str,
        contexts: list[str],
        histories: list[AskHistory],
        sql_samples: Optional[list[dict]] = None,
        instructions: Optional[list[dict]] = None,
        configuration: Configuration = Configuration(),
        query_id: Optional[str] = None,
    ) -> dict:
        """Run follow-up SQL reasoning with original interface"""
        result = await self.tool.run(
            query=query,
            contexts=contexts,
            histories=histories,
            sql_samples=sql_samples,
            instructions=instructions,
            configuration=configuration,
            query_id=query_id
        )
        
        # Return in original format
        if result.get("success", False):
            return {"replies": [result["reasoning"]]}
        else:
            return {"replies": [""]}


def create_followup_sql_reasoning_tool(doc_store_provider: DocumentStoreProvider) -> Tool:
    """Create Langchain tool for follow-up SQL reasoning"""
    reasoning_tool = FollowUpSQLGenerationReasoningTool(doc_store_provider)
    
    def reasoning_func(input_json: str) -> str:
        try:
            input_data = orjson.loads(input_json)
            result = asyncio.run(reasoning_tool.run(**input_data))
            return orjson.dumps(result).decode()
        except Exception as e:
            return orjson.dumps({"error": str(e), "success": False}).decode()
    
    return Tool(
        name="followup_sql_reasoner",
        description="Generates reasoning plans for follow-up SQL queries. Input should be JSON with 'query', 'contexts', 'histories', and optional configuration fields.",
        func=reasoning_func
    )


if __name__ == "__main__":
    # Test the follow-up SQL reasoning tool
    async def test_followup_reasoning():
        from app.core.dependencies import get_doc_store_provider
        
        doc_store_provider = get_doc_store_provider()
        reasoning = FollowUpSQLGenerationReasoning(doc_store_provider)
        
        result = await reasoning.run(
            query="this is a test query",
            contexts=[],
            histories=[]
        )
        
        print("Follow-up SQL Reasoning Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(test_followup_reasoning())