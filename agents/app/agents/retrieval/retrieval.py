import ast
import logging
import json
from typing import Any, Dict, List, Optional

import orjson
import tiktoken
from langchain_core.documents import Document as LangchainDocument
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langchain.agents import AgentExecutor, create_react_agent
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.tools import Tool
from langchain.prompts import MessagesPlaceholder
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_llm, get_doc_store_provider

logger = logging.getLogger("genieml-agents")


table_columns_selection_system_prompt = """
### TASK ###
You are a highly skilled data analyst. Your goal is to examine the provided database schema, interpret the posed question, and identify the specific columns from the relevant tables required to construct an accurate SQL query.
The database schema includes tables, columns, primary keys, foreign keys, relationships, and any relevant constraints.

### INSTRUCTIONS ###
1. Carefully analyze the schema and identify the essential tables and columns needed to answer the question.
1.1 ***Please select as many columns as possible even if they might not be fully relevant to the question. There are other downstream agents that will filter out the irrelevant columns.***
1.2 ***Please select columns that are relevant to the question from the same schema as much as possible. Then if not possible select from the next best schema. This will avoid unnecessary joins.***
1.3 ***IMPORTANT: Consider relationships between tables when selecting columns. If a table has relationships with other tables, consider including relevant columns from related tables that might be needed for joins or to provide complete context for the query.***
2. For each table, provide a clear and concise reasoning for why specific columns are selected.
3. List each reason as part of a step-by-step chain of thought, justifying the inclusion of each column.
4. If a "." is included in columns, put the name before the first dot into chosen columns.
5. The number of columns chosen must match the number of reasoning.
6. Final chosen columns must be only column names, don't prefix it with table names.
7. If the chosen column is a child column of a STRUCT type column, choose the parent column instead of the child column.
8. When analyzing relationships, consider the join type (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE) and the join condition to understand which columns are likely to be used in joins.

### FINAL ANSWER FORMAT ###

Please provide your response as a JSON object, structured as follows:
    "results": [
        {{  
            "table_selection_reason": "Reason for selecting tablename1",
            "table_contents": {{
              "chain_of_thought_reasoning": [
                  "Reason 1 for selecting column1",
                  "Reason 2 for selecting column2",
                  ...
              ],
              "columns": ["column1", "column2", ...]
            }},
            "table_name":"tablename1",
        }},
        {{
            "table_selection_reason": "Reason for selecting tablename2",
            "table_contents":
              {{
              "chain_of_thought_reasoning": [
                  "Reason 1 for selecting column1",
                  "Reason 2 for selecting column2",
                  ...
              ],
              "columns": ["column1", "column2", ...]
            }},
            "table_name":"tablename2"
        }},
        ...
    ]


### ADDITIONAL NOTES ###
- Each table key must list only the columns relevant to answering the question.
- Provide a reasoning list (`chain_of_thought_reasoning`) for each table, explaining why each column is necessary.
- Provide the reason of selecting the table in (`table_selection_reason`) for each table.
- Be logical, concise, and ensure the output strictly follows the required JSON format.
- Use table name used in the "Create Table" statement, don't use "alias".
- Match Column names with the definition in the "Create Table" statement.
- Match Table names with the definition in the "Create Table" statement.
** Please always response with JSON Format thinking like JSON Expert otherwise all my downstream application will fail.
** dont add any json tag or additional ``` to the response. This is very important.

Good luck!
"""

table_columns_selection_user_prompt_template = """
### Database Schema (Markdown Format) ###

{db_schemas}

### RELATIONSHIP INFORMATION ###
Each table may include relationship information showing how it relates to other tables. 
The relationships include:
- name: The name of the relationship
- models: The tables involved in the relationship
- joinType: The type of relationship (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE)
- condition: The join condition showing which columns are used to connect the tables
- properties: Additional metadata about the relationship

When selecting columns, consider these relationships to ensure you include columns that might be needed for joins or to provide complete context.

### INPUT ###
{question}
"""


class MatchingTableContents(BaseModel):
    """Contents of a matching table including reasoning and columns."""
    chain_of_thought_reasoning: List[str]
    columns: List[str]


class MatchingTable(BaseModel):
    """A matching table with its contents and selection reason."""
    table_name: str
    table_contents: MatchingTableContents
    table_selection_reason: str


class RetrievalResults(BaseModel):
    """Results of the retrieval process."""
    results: List[MatchingTable]


class TableRetrieval:
    """Retrieves and processes table information based on queries."""

    def __init__(
        self,
        document_store: Any,
        embedder: Any,
        model_name: str = "gpt-4o-mini",
        table_retrieval_size: int = 10,
        table_column_retrieval_size: int = 100,
        allow_using_db_schemas_without_pruning: bool = False,
        table_store: Optional[Any] = None,
        schema_store: Optional[Any] = None,
    ) -> None:
        """Initialize the table retrieval processor.

        Args:
            document_store: Document store (DocumentChromaStore or DocumentQdrantStore)
            embedder: The text embedder instance
            model_name: Name of the LLM model to use
            table_retrieval_size: Maximum number of tables to retrieve
            table_column_retrieval_size: Maximum number of columns to retrieve
            allow_using_db_schemas_without_pruning: Whether to allow using full schemas
            table_store: Optional table_description store (when using vector_store_client)
            schema_store: Optional db_schema store (when using vector_store_client)
        """
        self._embedder = embedder
        self._table_retrieval_size = table_retrieval_size
        self._table_column_retrieval_size = table_column_retrieval_size
        self._allow_using_db_schemas_without_pruning = allow_using_db_schemas_without_pruning
        provider = get_doc_store_provider()
        self.table_store = table_store if table_store is not None else provider.get_store("table_description")
        self.schema_store = schema_store if schema_store is not None else provider.get_store("db_schema")
        # Initialize LLM
        settings = get_settings()
        self._llm = get_llm()
        # Set encoding based on model
        if "gpt-4o" in model_name or "gpt-4o-mini" in model_name:
            self._encoding = tiktoken.get_encoding("o200k_base")
        else:
            self._encoding = tiktoken.get_encoding("cl100k_base")
            
        # Initialize ReAct agent
        self._initialize_agent()
        
        # Initialize prompt template
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", table_columns_selection_system_prompt),
            ("user", table_columns_selection_user_prompt_template)
        ])
        
        # Initialize output parser
        self._output_parser = JsonOutputParser(pydantic_object=RetrievalResults)

    def _initialize_agent(self):
        """Initialize the ReAct agent with tools and prompt."""
        # Define tools
        tools = [
            Tool(
                name="analyze_schema",
                func=self._analyze_schema,
                description="Analyze the database schema to understand table structures and relationships"
            ),
            Tool(
                name="select_columns",
                func=self._select_columns,
                description="Select relevant columns from tables based on the question"
            )
        ]

        # Create the agent prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a database expert that helps analyze questions and select relevant columns from database schemas.
            You have access to the following tools:
            {tools}
            
            Follow these steps:
            1. Analyze the question to understand what information is needed
            2. Review the database schema to identify relevant tables
            3. Select specific columns that can answer the question
            4. Provide reasoning for your column selections
            
            Question: {question}
            Database Schema:
            {schemas}
            
            Think through this step by step.
            
            Use the following format:
            Question: the input question you must answer
            Thought: you should always think about what to do
            Action: the action to take, should be one of [{tool_names}]
            Action Input: the input to the action
            Observation: the result of the action
            ... (this Thought/Action/Action Input/Observation can repeat N times)
            Thought: I now know the final answer
            Final Answer: the final answer to the original input question"""),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Create the ReAct agent
        self._agent = create_react_agent(
            llm=self._llm,
            tools=tools,
            prompt=prompt
        )

        # Create the agent executor
        self._agent_executor = AgentExecutor(
            agent=self._agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True
        )

    def _analyze_schema(self, schemas: str) -> str:
        """Analyze the database schema to understand its structure."""
        try:
            # Parse the schema string into a structured format
            schema_lines = schemas.split("\n")
            tables = []
            current_table = None
            
            for line in schema_lines:
                if line.startswith("CREATE TABLE"):
                    if current_table:
                        tables.append(current_table)
                    current_table = {
                        "name": line.split("CREATE TABLE")[1].split("(")[0].strip(),
                        "columns": []
                    }
                elif current_table and ";" not in line and line.strip():
                    # Parse column definition
                    col_def = line.strip().rstrip(",")
                    if col_def:
                        current_table["columns"].append(col_def)
            
            if current_table:
                tables.append(current_table)
            
            # Return analysis
            return f"Found {len(tables)} tables with their columns. Ready for column selection."
            
        except Exception as e:
            logger.error(f"Error analyzing schema: {str(e)}")
            return "Error analyzing schema"

    def _select_columns(self, question: str, schemas: str) -> Dict:
        """Select relevant columns based on the question and schema."""
        try:
            # Use the LLM to select columns
            response = self._llm.invoke(
                f"""Based on this question: {question}
                And these schemas: {schemas}
                Select the relevant columns and provide reasoning.
                Return the result as a JSON object with this structure:
                {{
                    "results": [
                        {{
                            "table_name": "table_name",
                            "table_selection_reason": "reason for selecting this table",
                            "table_contents": {{
                                "chain_of_thought_reasoning": ["reason1", "reason2"],
                                "columns": ["column1", "column2"]
                            }}
                        }}
                    ]
                }}"""
            )
            
            # Parse the response
            try:
                return orjson.loads(response.content)
            except:
                # Try to extract JSON from the response
                content = response.content.strip()
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    return orjson.loads(content[start_idx:end_idx])
                else:
                    return {"results": []}
                    
        except Exception as e:
            logger.error(f"Error selecting columns: {str(e)}")
            return {"results": []}

    async def _get_column_selection(self, prompt: str) -> Dict:
        """Get column selection from LLM."""
        try:
            # Create messages from the formatted prompt
            messages = [
                ("system", table_columns_selection_system_prompt),
                ("user", prompt)
            ]
            
            response = await self._llm.ainvoke(messages)
            
            
            # Get the content and clean it
            content = response.content.strip()
            
            if not content:
                logger.error("Empty response content received from LLM")
                return {"results": []}
            
            # Handle markdown code blocks
            if content.startswith('```json'):
                # Find the first and last ```
                first_block = content.find('```')
                last_block = content.rfind('```')
                
                if first_block >= 0 and last_block > first_block:
                    # Extract content between code blocks
                    content = content[first_block:last_block]
                    # Remove the ```json and ``` markers
                    content = content.replace('```json', '').replace('```', '').strip()
               
            # Try to parse the cleaned content as JSON
            try:
                return orjson.loads(content)
            except Exception as e:
                logger.warning(f"Failed to parse cleaned content as JSON: {str(e)}")
                # Try to extract JSON object if it's embedded in other text
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    try:
                        json_str = content[start_idx:end_idx]
                        return orjson.loads(json_str)
                    except Exception as json_error:
                        logger.error(f"Failed to parse extracted JSON: {str(json_error)}")
                        return {"results": []}
                else:
                    logger.error("No valid JSON object found in response")
                    return {"results": []}
                    
        except Exception as e:
            logger.error(f"Error in LLM invocation: {str(e)}")
            return {"results": []}

    async def run(
        self,
        query: str = "",
        tables: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        histories: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Retrieve and process table information.
        
        Args:
            query: The query string to search for similar tables
            tables: Optional list of specific tables to retrieve
            project_id: Optional project ID to filter results
            histories: Optional list of previous queries
            
        Returns:
            Dictionary containing retrieval results and metadata
        """
        # Project ID mapping for backward compatibility - DISABLED
        # project_id_mapping = {
        #     "sumtotal_learn": "sumtotal_learn_demo",
        #     "csodworkday": "csodworkday_demo",
        #     "cornerstone_learning": "cornerstone_learning_demo",
        #     "cornerstone_talent": "cornerstone_talent_demo",
        #     "cornerstone": "cornerstone_demo"
        # }
        
        # Map project_id if needed - DISABLED
        # original_project_id = project_id
        # if project_id in project_id_mapping:
        #     project_id = project_id_mapping[project_id]
        #     logger.info(f"Mapped project_id from '{original_project_id}' to '{project_id}'")
        
        logger.info(f"Table retrieval is running... for {project_id}")
        logger.info(f"DEBUG: TableRetrieval.run() called with project_id: {project_id}")
        logger.info(f"DEBUG: project_id type: {type(project_id)}")
        logger.info(f"DEBUG: project_id value: {repr(project_id)}")
        
        try:
            # Add debug logging
            logger.info(f"DEBUG: TableRetrieval.run() - about to call _retrieve_table_descriptions with project_id: {project_id}")
            
            # Get table descriptions
            try:
                table_docs = await self._retrieve_table_descriptions(
                    query, tables, project_id
                )
                logger.info(f"DEBUG: _retrieve_table_descriptions completed successfully, got {len(table_docs)} table docs")
            except Exception as e:
                logger.error(f"DEBUG: Error in _retrieve_table_descriptions: {str(e)}")
                raise
            #print("table_docs in run table retrieval", table_docs)
            if not table_docs:
                return {
                    "retrieval_results": [],
                    "has_calculated_field": False,
                    "has_metric": False
                }
           
            # Get schema information
            try:
                schema_docs = await self._retrieve_schemas(
                    table_docs, project_id
                )
                logger.info(f"DEBUG: _retrieve_schemas completed successfully, got {len(schema_docs)} schema docs")
            except Exception as e:
                logger.error(f"DEBUG: Error in _retrieve_schemas: {str(e)}")
                raise
            
            try:
                metrics = await self._retrieve_metrics(query, tables, project_id)
                logger.info(f"DEBUG: _retrieve_metrics completed successfully, got {len(metrics)} metrics")
            except Exception as e:
                logger.error(f"DEBUG: Error in _retrieve_metrics: {str(e)}")
                raise
                
            try:
                views = await self._retrieve_views(query, tables, project_id)
                logger.info(f"DEBUG: _retrieve_views completed successfully, got {len(views)} views")
            except Exception as e:
                logger.error(f"DEBUG: Error in _retrieve_views: {str(e)}")
                raise

            # Combine all
            schema_docs = schema_docs + metrics + views
            logger.info(f"DEBUG: Combined schema_docs count: {len(schema_docs)}")
            
            # Skip column metadata retrieval - only use table_columns from table schema
            column_docs = []
            
            # Construct database schemas
            try:
                logger.info(f"DEBUG: About to call _construct_db_schemas with {len(schema_docs)} schema_docs and {len(table_docs)} table_docs and {len(column_docs)} column_docs")
                logger.info(f"DEBUG: schema_docs sample: {schema_docs[:1] if schema_docs else 'None'}")
                logger.info(f"DEBUG: table_docs sample: {table_docs[:1] if table_docs else 'None'}")
                logger.info(f"DEBUG: column_docs sample: {column_docs[:1] if column_docs else 'None'}")
                db_schemas = self._construct_db_schemas(schema_docs, table_docs, column_docs)
                logger.info(f"DEBUG: _construct_db_schemas completed successfully, got {len(db_schemas)} schemas")
            except Exception as e:
                logger.error(f"DEBUG: Error in _construct_db_schemas: {str(e)}")
                raise
            
            
            # Check if we can use schemas without pruning
            try:
                logger.info(f"DEBUG: About to call _check_schemas_without_pruning with {len(db_schemas)} db_schemas and {len(schema_docs)} schema_docs")
                schema_check = self._check_schemas_without_pruning(
                    db_schemas, schema_docs
                )
                logger.info(f"DEBUG: _check_schemas_without_pruning completed successfully")
            except Exception as e:
                logger.error(f"DEBUG: Error in _check_schemas_without_pruning: {str(e)}")
                raise
            
            # Use query-based semantic search to find relevant schemas
            if query and schema_docs:
                logger.info(f"=== USING QUERY-BASED SCHEMA RETRIEVAL ===")
                logger.info(f"Query: {query}")
                logger.info(f"Available schema docs: {len(schema_docs)}")
                
                # Find most relevant schemas using ChromaDB semantic search
                relevant_schemas = await self._find_relevant_schemas_by_query(
                    query, schema_docs, project_id
                )
                logger.info(f"Found {len(relevant_schemas)} relevant schemas")
                
                if relevant_schemas:
                    # Build focused DDL with only relevant information
                    focused_ddl_results = await self._build_focused_ddl(
                        relevant_schemas, query, project_id
                    )
                    logger.info(f"Built focused DDL for {len(focused_ddl_results)} schemas")
                    
                    if focused_ddl_results:
                        return {
                            "retrieval_results": focused_ddl_results,
                            "has_calculated_field": schema_check["has_calculated_field"],
                            "has_metric": schema_check["has_metric"]
                        }
            
            # Fallback to original logic if query-based approach fails
            token_count = schema_check.get('tokens', 0)
            max_tokens = 128000  # Reasonable token limit for context
            
            if schema_check["db_schemas"] and token_count <= max_tokens:
                logger.info(f"=== FALLBACK: USING SCHEMAS WITHOUT PRUNING ===")
                logger.info(f"Schema check returned {len(schema_check['db_schemas'])} schemas")
                logger.info(f"Token count: {token_count} (within limit of {max_tokens})")
                return {
                    "retrieval_results": schema_check["db_schemas"],
                    "has_calculated_field": schema_check["has_calculated_field"],
                    "has_metric": schema_check["has_metric"]
                }
            
            # If we can't use schemas without pruning, do column selection
            logger.info(f"=== DOING COLUMN SELECTION (SCHEMAS TOO LARGE OR PRUNING REQUIRED) ===")
            logger.info(f"Query: {query}")
            logger.info(f"Schema docs count: {len(schema_docs)}")
            logger.info(f"Allow using db schemas without pruning: {self._allow_using_db_schemas_without_pruning}")
            logger.info(f"Schema check tokens: {schema_check.get('tokens', 0)}")
            
            if query:
                # Build prompt with processed db_schemas (which have columns) instead of raw schema_docs
                prompt = self._build_prompt(query, db_schemas, histories)
                print(f"=== BUILT PROMPT FOR COLUMN SELECTION ===")
                print(f"Prompt length: {len(prompt)}")
                print(f"Prompt preview: {prompt[:500]}...")
                
                # Get column selection from LLM
                column_selection = await self._get_column_selection(prompt)
                print(f"=== COLUMN SELECTION RESULT ===")
                print(f"Column selection: {column_selection}")
                
                # Retrieve TABLE_COLUMNS data for better column information
                table_columns_map = await self._retrieve_table_columns(schema_docs, project_id)
                print(f"=== TABLE COLUMNS RETRIEVED ===")
                print(f"Table columns map: {list(table_columns_map.keys())}")
                
                # Construct final results with selected columns
                result = self._construct_retrieval_results(
                    column_selection, db_schemas, schema_docs, table_columns_map
                )
                print(f"=== FINAL RETRIEVAL RESULTS ===")
                print(f"Retrieval results count: {len(result.get('retrieval_results', []))}")
                return result
            
            return {
                "retrieval_results": [],
                "has_calculated_field": False,
                "has_metric": False
            }
            
        except Exception as e:
            logger.error(f"Error in table retrieval: {str(e)}")
            return {
                "retrieval_results": [],
                "has_calculated_field": False,
                "has_metric": False
            }

    def _extract_table_names(self, results: List[Dict]) -> List[str]:
        """Extract unique table names from the results.
        
        Args:
            results: List of document results from semantic search
            
        Returns:
            List of unique table names
        """
        table_names = set()
        for doc in results:
            try:
                # Get content from document
                content = doc.get('content', '')
                if not content:
                    continue
                
                # Try to parse content as dict
                try:
                    # Clean up the content string by removing any extra quotes
                    content = content.strip("'").strip('"')
                    content_dict = ast.literal_eval(content)
                except:
                    continue
                
                if not isinstance(content_dict, dict):
                    continue
                
                # Check document type
                doc_type = content_dict.get('type')
                mdl_type = content_dict.get('mdl_type')
                if doc_type != 'TABLE_DESCRIPTION' or mdl_type not in ['TABLE_SCHEMA', 'METRIC', 'VIEW']:
                    continue
                
                # Get table name from content
                table_name = content_dict.get('name')
                if table_name:
                    table_names.add(table_name)
                    continue
                
                # If no name in content, try metadata
                table_name = doc.get('metadata', {}).get('name')
                if table_name:
                    table_names.add(table_name)
                
            except Exception as e:
                logger.warning(f"Error extracting table name from document: {str(e)}")
                continue
        
        # Log found table names
        logger.info(f"Extracted {len(table_names)} unique table names: {table_names}")
        return list(table_names)

    async def _retrieve_metrics(
        self,
        query: str,
        tables: Optional[List[str]],
        project_id: Optional[str]
    ) -> List[Any]:
        """Retrieve table descriptions from the document store."""
        try:
            where = {"type": {"$eq": 'METRIC'}}
            # Only add project_id filter if it's not "default"
            if project_id and project_id != "default":
                where = {"$and": [{"project_id": {"$eq": project_id}},{"type": {"$eq": "METRIC"}}]}
            #where = None
            if query:
                # Get query embedding
                #embedding_result = await self._embedder.aembed_query(query)
                # Get results from document store
                if where:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=10,
                        where=where,
                        #query_embedding=embedding_result
                    )
                else:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=100
                    )
        
            if not results:
                return []
            
            filtered_results = [
                item for item in results
                if (
                    (
                        isinstance(item.get('content'), str) and
                        ast.literal_eval(item['content']).get('type') == 'METRIC' 
                    )
                    or (
                        isinstance(item.get('metadata'), dict) and
                        item['metadata'].get('type') == 'METRIC'
                    )
                )
            ]
            
            # Extract table names
            #table_names = self._extract_table_names(results)
            #print("table_names in retrieve_table_descriptions", table_names)
           
            # Results are already a list of documents
            return filtered_results
        except Exception as e:
            logger.error(f"Error in table retrieval: {str(e)}")
            return []

    async def _retrieve_views(
        self,
        query: str,
        tables: Optional[List[str]],
        project_id: Optional[str]
    ) -> List[Any]:
        """Retrieve table descriptions from the document store."""
        try:
            where = {"type": {"$eq": 'VIEW'}}
            # Only add project_id filter if it's not "default"
            if project_id and project_id != "default":
                where = {"$and": [{"project_id": {"$eq": project_id}},{"type": {"$eq": "VIEW"}}]}
            #where = None
            if query:
                # Get query embedding
                #embedding_result = await self._embedder.aembed_query(query)
                # Get results from document store
                if where:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=10,
                        where=where,
                        #query_embedding=embedding_result
                    )
                else:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=100
                    )
        
            if not results:
                return []
            
            filtered_results = [
                item for item in results
                if (
                    (
                        isinstance(item.get('content'), str) and
                        ast.literal_eval(item['content']).get('type') == 'VIEW' 
                    )
                    or (
                        isinstance(item.get('metadata'), dict) and
                        item['metadata'].get('type') == 'VIEW'
                    )
                )
            ]
           
            # Extract table names
            #table_names = self._extract_table_names(results)
            #print("table_names in retrieve_table_descriptions", table_names)
           
            # Results are already a list of documents
            return filtered_results
        except Exception as e:
            logger.error(f"Error in table retrieval: {str(e)}")
            return []
        
    async def _retrieve_table_descriptions(
        self,
        query: str,
        tables: Optional[List[str]],
        project_id: Optional[str]
    ) -> List[Any]:
        """Retrieve table descriptions from the document store."""
        try:
            # Project ID mapping for backward compatibility - DISABLED
            # project_id_mapping = {
            #     "sumtotal_learn": "sumtotal_learn_demo",
            #     "csodworkday": "csodworkday_demo",
            #     "cornerstone_learning": "cornerstone_learning_demo",
            #     "cornerstone_talent": "cornerstone_talent_demo",
            #     "cornerstone": "cornerstone_demo"
            # }
            
            # Map project_id if needed - DISABLED
            # if project_id in project_id_mapping:
            #     project_id = project_id_mapping[project_id]
            #     logger.info(f"Mapped project_id in _retrieve_table_descriptions to: {project_id}")
            
            logger.info(f"DEBUG: _retrieve_table_descriptions called with project_id: {project_id}")
            
            # Search for both TABLE_DESCRIPTION and TABLE_SCHEMA documents
            # TABLE_SCHEMA documents have full column information with MDL properties
            # TABLE_DESCRIPTION documents have basic table information
            where = {"type": {"$in": ['TABLE_DESCRIPTION', 'TABLE_SCHEMA']}}
            if project_id and project_id != "default":
                where = {"$and": [{"project_id": {"$eq": project_id}},{"type": {"$in": ["TABLE_DESCRIPTION", "TABLE_SCHEMA"]}}]}
            
            logger.info(f"DEBUG: _retrieve_table_descriptions - where clause: {where}")
            
            # Query both table_description and db_schema stores
            all_results = []
            
            # Query table_description store
            if query:
                table_results = self.table_store.semantic_search(
                    query=query,
                    k=10,
                    where=where,
                )
            else:
                table_results = self.table_store.semantic_search(
                    query="",
                    k=100,
                    where=where
                )
            
            if table_results:
                all_results.extend(table_results)
                logger.info(f"DEBUG: Found {len(table_results)} results from table_description store")
            
            # Query db_schema store for TABLE_SCHEMA documents with full column information
            schema_where = {"type": {"$eq": 'TABLE_SCHEMA'}}
            if project_id and project_id != "default":
                schema_where = {"$and": [{"project_id": {"$eq": project_id}},{"type": {"$eq": "TABLE_SCHEMA"}}]}
            
            if query:
                schema_results = self.schema_store.semantic_search(
                    query=query,
                    k=10,
                    where=schema_where,
                )
            else:
                schema_results = self.schema_store.semantic_search(
                    query="",
                    k=100,
                    where=schema_where
                )
            
            if schema_results:
                all_results.extend(schema_results)
                logger.info(f"DEBUG: Found {len(schema_results)} results from db_schema store")
            
            # Skip column_metadata store queries - only use table_columns from table schema
            
            results = all_results
        
            if not results:
                return []
            
            # Filter to only include documents with correct mdl_type
            filtered_results = [
                item for item in results
                if (
                    isinstance(item.get('content'), str) and
                    self._is_table_doc_from_content(item['content'])
                ) or (
                    isinstance(item.get('metadata'), dict) and
                    self._is_table_doc_from_metadata(item['metadata'])
                )
            ]
            
            logger.info(f"DEBUG: _retrieve_table_descriptions - filtered {len(results)} results down to {len(filtered_results)} results")
            return filtered_results
        except Exception as e:
            logger.error(f"Error in table retrieval: {str(e)}")
            return []

    async def _retrieve_schemas(
        self,
        table_docs: List[Any],
        project_id: Optional[str]
    ) -> List[Any]:
        """Retrieve schema information for the given tables."""
        table_names = self._extract_table_names(table_docs)
        results = []
        
        if not table_names:
            # Search both table_description and db_schema collections
            where_table_desc = {"type": {"$eq": 'TABLE_DESCRIPTION'}}
            where_db_schema = {"type": {"$eq": 'TABLE_SCHEMA'}}
            if project_id and project_id != "default":
                where_table_desc = {"$and": [{"project_id": {"$eq": project_id}}, {"type": {"$eq": 'TABLE_DESCRIPTION'}}]}
                where_db_schema = {"$and": [{"project_id": {"$eq": project_id}}, {"type": {"$eq": 'TABLE_SCHEMA'}}]}
            
            logger.info(f"DEBUG: _retrieve_schemas - searching table_description with where: {where_table_desc}")
            table_desc_results = self.table_store.semantic_search(
                query="",
                k=10,
                where=where_table_desc
            )
            
            logger.info(f"DEBUG: _retrieve_schemas - searching db_schema with where: {where_db_schema}")
            db_schema_results = self.schema_store.semantic_search(
                query="",
                k=10,
                where=where_db_schema
            )
            
            results = table_desc_results + db_schema_results
        else:
            for table_name in table_names:
                # Search table_description collection
                where_table_desc = {"$and": [{"name": {"$eq": table_name}}, {"type": {"$eq": 'TABLE_DESCRIPTION'}}]}
                where_db_schema = {"$and": [{"name": {"$eq": table_name}}, {"type": {"$eq": 'TABLE_SCHEMA'}}]}
                if project_id and project_id != "default":
                    where_table_desc = {
                        "$and": [
                            {"project_id": {"$eq": project_id}},
                            {"name": {"$eq": table_name}},
                            {"type": {"$eq": 'TABLE_DESCRIPTION'}}
                        ]
                    }
                    where_db_schema = {
                        "$and": [
                            {"project_id": {"$eq": project_id}},
                            {"name": {"$eq": table_name}},
                            {"type": {"$eq": 'TABLE_SCHEMA'}}
                        ]
                    }    
                
                logger.info(f"DEBUG: _retrieve_schemas - searching table_description for table {table_name} with where: {where_table_desc}")
                table_desc_results = self.table_store.semantic_search(
                    query="",
                    k=10,
                    where=where_table_desc
                )
                
                logger.info(f"DEBUG: _retrieve_schemas - searching db_schema for table {table_name} with where: {where_db_schema}")
                db_schema_results = self.schema_store.semantic_search(
                    query="",
                    k=10,
                    where=where_db_schema
                )
                
                results.extend(table_desc_results + db_schema_results)
        
        logger.info(f"DEBUG: _retrieve_schemas - total results: {len(results)}")
        if not results:
            return []
        
        return results

    async def _retrieve_table_columns(
        self,
        table_docs: List[Any],
        project_id: Optional[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve TABLE_COLUMNS data from TABLE_SCHEMA documents for the given tables."""
        table_names = self._extract_table_names(table_docs)
        table_columns_map = {}
        
        if not table_names:
            logger.warning("No table names found for table columns retrieval")
            return table_columns_map
        
        logger.info(f"DEBUG: Retrieving TABLE_COLUMNS for tables: {table_names}")
        
        try:
            # Query db_schema store for TABLE_SCHEMA documents that contain TABLE_COLUMNS data
            where = {
                "name": {"$in": table_names},
                "type": {"$eq": "TABLE_SCHEMA"}
            }
            if project_id and project_id != "default":
                where = {
                    "$and": [
                        {"project_id": {"$eq": project_id}},
                        {"name": {"$in": table_names}},
                        {"type": {"$eq": "TABLE_SCHEMA"}}
                    ]
                }
            
            logger.info(f"DEBUG: _retrieve_table_columns - where clause: {where}")
            
            # Search for TABLE_COLUMNS documents
            schema_results = self.schema_store.semantic_search(
                query="",
                k=100,  # Get all schema documents for the tables
                where=where,
            )
            
            logger.info(f"DEBUG: _retrieve_table_columns - search returned {len(schema_results) if schema_results else 0} results")
            if schema_results:
                logger.info(f"DEBUG: _retrieve_table_columns - first result metadata: {schema_results[0].get('metadata', {})}")
                logger.info(f"DEBUG: _retrieve_table_columns - first result content preview: {str(schema_results[0].get('content', ''))[:200]}...")
            
            if schema_results:
                logger.info(f"DEBUG: Found {len(schema_results)} TABLE_SCHEMA documents")
                
                # Process each TABLE_SCHEMA document to extract TABLE_COLUMNS data
                for result in schema_results:
                    try:
                        # Parse the content to extract TABLE_COLUMNS data
                        import json
                        content_str = result.get('content', '')
                        if not content_str:
                            logger.warning("No content found in TABLE_SCHEMA document")
                            continue
                        
                        # Log the raw content for debugging
                        logger.info(f"Raw content type: {type(content_str)}")
                        logger.info(f"Raw content preview: {str(content_str)[:500]}...")
                        
                        # Check if content is already a dict (not a string)
                        if isinstance(content_str, dict):
                            logger.info("Content is already a dict, using directly")
                            content = content_str
                        else:
                            # Try to parse as Python dict string (using ast.literal_eval) first
                            try:
                                import ast
                                content = ast.literal_eval(content_str)
                                logger.info("Successfully parsed content using ast.literal_eval")
                            except (ValueError, SyntaxError) as ast_error:
                                # Fallback to JSON parsing
                                try:
                                    content = json.loads(content_str)
                                    logger.info("Successfully parsed content using json.loads")
                                except json.JSONDecodeError as json_error:
                                    logger.warning(f"Both ast.literal_eval and json.loads failed for table {result.get('metadata', {}).get('name', 'unknown')}")
                                    logger.warning(f"ast.literal_eval error: {str(ast_error)}")
                                    logger.warning(f"json.loads error: {str(json_error)}")
                                    logger.warning(f"Content that failed to parse: {content_str[:500]}...")
                                    continue
                        
                        table_name = result.get('metadata', {}).get("name", "")
                        if not table_name:
                            logger.warning("No table name found in metadata")
                            continue
                            
                        # Check if this TABLE_SCHEMA document contains TABLE_COLUMNS data
                        if content.get("type") == "TABLE_COLUMNS":
                            # Extract columns from the content
                            columns = content.get("columns", [])
                            logger.info(f"DEBUG: Found TABLE_COLUMNS data in TABLE_SCHEMA for {table_name} with {len(columns)} columns")
                            if columns:
                                logger.info(f"DEBUG: Sample TABLE_COLUMNS column: {columns[0]}")
                                # Add columns to the map (merge if multiple batches exist)
                                if table_name in table_columns_map:
                                    table_columns_map[table_name].extend(columns)
                                else:
                                    table_columns_map[table_name] = columns
                                logger.info(f"DEBUG: Extracted {len(columns)} columns for table {table_name}")
                            else:
                                logger.info(f"DEBUG: No columns found in TABLE_COLUMNS for table {table_name}")
                        else:
                            logger.info(f"DEBUG: TABLE_SCHEMA document for {table_name} is not TABLE_COLUMNS type: {content.get('type')}")
                            
                    except Exception as e:
                        logger.warning(f"Error processing TABLE_SCHEMA document: {str(e)}")
                        logger.warning(f"Document metadata: {result.get('metadata', {})}")
                        continue
            else:
                logger.warning("No TABLE_COLUMNS documents found")
                # Try a broader search to see what's available
                logger.info("DEBUG: Trying broader search to see what documents are available...")
                broad_where = {"type": {"$eq": "TABLE_SCHEMA"}}
                if project_id and project_id != "default":
                    broad_where = {
                        "$and": [
                            {"project_id": {"$eq": project_id}},
                            {"type": {"$eq": "TABLE_SCHEMA"}}
                        ]
                    }
                broad_results = self.schema_store.semantic_search(
                    query="",
                    k=10,
                    where=broad_where,
                )
                logger.info(f"DEBUG: Broad search returned {len(broad_results) if broad_results else 0} results")
                if broad_results:
                    for i, result in enumerate(broad_results[:3]):  # Show first 3 results
                        logger.info(f"DEBUG: Result {i} metadata: {result.get('metadata', {})}")
                        logger.info(f"DEBUG: Result {i} content type: {type(result.get('content', ''))}")
                        if hasattr(result, 'page_content'):
                            logger.info(f"DEBUG: Result {i} page_content preview: {str(result.page_content)[:200]}...")
                        else:
                            logger.info(f"DEBUG: Result {i} content preview: {str(result.get('content', ''))[:200]}...")
                
        except Exception as e:
            logger.error(f"Error retrieving table columns: {str(e)}")
            raise
        
        return table_columns_map



    def _merge_columns(self, existing_columns: list, new_columns: list, table_name: str):
        """Merge new columns with existing columns, combining information from both sources."""
        for new_col in new_columns:
            col_name = new_col.get('name', '')
            if not col_name:
                continue
                
            # Check if column already exists
            existing_col = None
            for col in existing_columns:
                if col.get('name') == col_name:
                    existing_col = col
                    break
            
            if existing_col:
                # Merge information, prioritizing new column for basic info and existing for MDL properties
                merged_col = {
                    "name": col_name,
                    "type": new_col.get('type', existing_col.get('type', 'VARCHAR')),
                    "comment": new_col.get('comment', existing_col.get('comment', '')),
                    "description": new_col.get('description', existing_col.get('description', '')),
                    "is_primary_key": new_col.get('is_primary_key', existing_col.get('is_primary_key', False)),
                    "is_foreign_key": new_col.get('is_foreign_key', existing_col.get('is_foreign_key', False)),
                    "notNull": new_col.get('notNull', existing_col.get('notNull', False)),
                    # Preserve MDL properties from existing column
                    "properties": existing_col.get('properties', new_col.get('properties', {})),
                    "isCalculated": existing_col.get('isCalculated', new_col.get('isCalculated', False)),
                    "expression": existing_col.get('expression', new_col.get('expression', '')),
                    "relationship": existing_col.get('relationship', new_col.get('relationship', {}))
                }
                
                # Update the existing column
                existing_col.update(merged_col)
                logger.debug(f"Merged column {table_name}.{col_name}")
            else:
                # Add new column
                existing_columns.append(new_col)
                logger.debug(f"Added new column {table_name}.{col_name}")

    def _parse_doc_content(self, doc) -> dict:
        """Safely parse the 'content' field from a document and return a dict."""
        content = doc.get('content', '')
        logger.info(f"DEBUG: _parse_doc_content - raw content: {content[:200]}...")
        
        if not content:
            logger.info("DEBUG: _parse_doc_content - no content found")
            return {}
        
        # Try JSON parsing first (for JSON documents)
        try:
            import json
            content = content.strip("'").strip('"')
            logger.info(f"DEBUG: _parse_doc_content - cleaned content: {content[:200]}...")
            
            parsed = json.loads(content)
            logger.info(f"DEBUG: _parse_doc_content - JSON parsed result: {parsed}")
            return parsed
        except json.JSONDecodeError:
            # Fall back to ast.literal_eval for Python literals
            try:
                parsed = ast.literal_eval(content)
                logger.info(f"DEBUG: _parse_doc_content - ast parsed result: {parsed}")
                return parsed
            except Exception as e:
                logger.warning(f"Failed to parse content with both JSON and ast: {content[:200]}... | Error: {str(e)}")
                return {}
        except Exception as e:
            logger.warning(f"Failed to parse content: {content[:200]}... | Error: {str(e)}")
            return {}

    def _is_table_doc(self, content_dict) -> bool:
        return content_dict.get('type') == 'TABLE_DESCRIPTION' and content_dict.get('mdl_type') in ['TABLE_SCHEMA', 'METRIC', 'VIEW']

    def _is_table_doc_from_content(self, content: str) -> bool:
        """Check if content string represents a valid table document."""
        try:
            content_dict = ast.literal_eval(content)
            return self._is_table_doc(content_dict)
        except:
            return False

    def _is_table_doc_from_metadata(self, metadata: dict) -> bool:
        """Check if metadata represents a valid table document."""
        return (metadata.get('type') == 'TABLE_DESCRIPTION' and 
                metadata.get('mdl_type') in ['TABLE_SCHEMA', 'METRIC', 'VIEW'])

    def _is_column_doc(self, content_dict) -> bool:
        return content_dict.get('type') in ['TABLE_COLUMNS', 'COLUMNS']

    def _extract_table_name(self, doc, content_dict) -> str:
        return content_dict.get('name') or doc.get('metadata', {}).get('name', '')

    def _extract_columns(self, content_dict) -> list:
        columns = content_dict.get('columns', '')
        if isinstance(columns, str):
            return [col.strip() for col in columns.split(',') if col.strip()]
        elif isinstance(columns, list):
            return [col.strip() if isinstance(col, str) else str(col) for col in columns]
        return []

    def _build_column_defs(self, columns, default_type="VARCHAR"):
        col_defs = []
        if not columns:
            return []
        
        logger.info(f"DEBUG: _build_column_defs called with {len(columns)} columns")
        logger.info(f"DEBUG: Sample column: {columns[0] if columns else 'None'}")
        
        # Debug: Log all column data types before processing
        for i, col in enumerate(columns[:3]):  # Log first 3 columns for debugging
            if isinstance(col, dict):
                logger.info(f"DEBUG: Column {i} ({col.get('name', 'unknown')}): data_type={col.get('data_type')}, type={col.get('type')}, keys={list(col.keys())}")
            
        for i, col in enumerate(columns):
            try:
                logger.debug(f"Processing column {i}: {col}")
                
                # Process column from table schema
                if isinstance(col, dict):
                    name = col.get('name', '')
                    # Try both 'data_type' and 'type' for compatibility - prioritize data_type
                    dtype = col.get('data_type', col.get('type', default_type))
                    
                    # Enhanced logging to debug data type extraction
                    logger.info(f"Column {name}: raw data_type={col.get('data_type')}, raw type={col.get('type')}, final dtype={dtype}")
                    logger.info(f"Column {name}: isCalculated={col.get('isCalculated', False)}, properties={col.get('properties', {})}")
                    logger.info(f"Column {name}: Full column object in _build_column_defs: {col}")
                    
                    # If we still have default type, try to extract from properties
                    if dtype == default_type and 'properties' in col and isinstance(col['properties'], dict):
                        # Check if data type is stored in properties
                        props_dtype = col['properties'].get('data_type') or col['properties'].get('type')
                        if props_dtype:
                            dtype = props_dtype
                            logger.debug(f"Column {name}: Found data type in properties: {dtype}")
                    
                    logger.debug(f"Column {name}: Final data type after processing: {dtype}")
                    
                    # Get comment and description from properties or direct fields
                    comment = col.get('comment', '')
                    description = col.get('description', '')
                    
                    if 'properties' in col and isinstance(col['properties'], dict):
                        # Get display name as comment if available
                        if not comment:
                            comment = col['properties'].get('displayName', '')
                        # Get description if not already set
                        if not description:
                            description = col['properties'].get('description', '')
                        
                        # Enhanced logging for debugging
                        logger.info(f"DEBUG: Column {col.get('name', '')} properties in _build_column_defs: {col['properties']}")
                        logger.info(f"DEBUG: Column {col.get('name', '')}: comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                    
                    # If no comment is available, generate one from the column name
                    if not comment:
                        # Convert column name to a more readable format
                        comment = name.replace('_', ' ').title()
                        logger.info(f"DEBUG: Generated comment for column {name}: '{comment}'")
                    
                    # If no description is available, generate one from the column name
                    if not description:
                        # Generate a more descriptive description based on column name patterns
                        description = self._generate_column_description(name)
                        if description:
                            logger.info(f"DEBUG: Generated description for column {name}: '{description}'")
                    
                    # Handle notNull constraint
                    not_null = col.get('notNull', False)
                    if not_null and dtype.upper() != 'PRIMARY KEY':
                        dtype += ' NOT NULL'
                    
                    # Log final comment and description
                    logger.info(f"DEBUG: Final column {name}: comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                    logger.debug(f"Column {i}: name='{name}', type='{dtype}', comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                else:
                    name = str(col) if col is not None else ''
                    dtype = default_type
                    comment = ''
                
                # Skip empty column names
                if not name or not name.strip():
                    logger.warning("Skipping column with empty name")
                    continue
                
                # Validate column name doesn't contain problematic characters
                if any(char in name for char in ['(', ')', ';', '\n', '\r']):
                    logger.warning(f"Column name contains problematic characters, skipping: {name}")
                    continue
                    
                col_def = f"{name} {dtype}"
                
                # Add comment and description in the format: -- comment -- description
                comment_parts = []
                if comment:
                    clean_comment = comment.strip().replace('\n', ' ').replace('\r', ' ')
                    if clean_comment and not clean_comment.startswith("--"):
                        comment_parts.append(clean_comment)
                
                if description:
                    clean_description = description.strip().replace('\n', ' ').replace('\r', ' ')
                    if clean_description and not clean_description.startswith("--"):
                        comment_parts.append(clean_description)
                
                if comment_parts:
                    col_def += f" -- {' -- '.join(comment_parts)}"
                    logger.debug(f"Added comment for {name}: {' -- '.join(comment_parts)[:100]}...")
                
                logger.info(f"DEBUG: Generated column definition: {col_def}")
                col_defs.append(col_def)
            except Exception as e:
                logger.warning(f"Error processing column {i} ({col}): {str(e)}")
                continue
                
        return col_defs

    def _generate_column_description(self, column_name: str) -> str:
        """Generate a meaningful description for a column based on its name patterns."""
        name_lower = column_name.lower()
        
        # Common patterns and their descriptions
        patterns = {
            'id': 'Unique identifier',
            'name': 'Name or title',
            'description': 'Detailed description or explanation',
            'type': 'Type or category classification',
            'status': 'Current status or state',
            'date': 'Date value',
            'time': 'Time value',
            'timestamp': 'Timestamp value',
            'created': 'Creation timestamp',
            'updated': 'Last update timestamp',
            'modified': 'Last modification timestamp',
            'email': 'Email address',
            'phone': 'Phone number',
            'address': 'Physical or logical address',
            'url': 'Uniform Resource Locator',
            'ip': 'IP address',
            'mac': 'MAC address',
            'host': 'Hostname or host identifier',
            'port': 'Port number',
            'version': 'Version number or identifier',
            'count': 'Count or quantity',
            'total': 'Total amount or sum',
            'amount': 'Monetary amount or value',
            'price': 'Price or cost',
            'cost': 'Cost or expense',
            'rate': 'Rate or percentage',
            'percent': 'Percentage value',
            'score': 'Score or rating',
            'level': 'Level or tier',
            'category': 'Category classification',
            'class': 'Class or type classification',
            'group': 'Group identifier',
            'team': 'Team identifier',
            'user': 'User identifier or information',
            'customer': 'Customer identifier or information',
            'order': 'Order identifier or information',
            'product': 'Product identifier or information',
            'item': 'Item identifier or information',
            'code': 'Code or identifier',
            'key': 'Key or identifier',
            'value': 'Value or data',
            'data': 'Data or information',
            'info': 'Information or details',
            'note': 'Note or comment',
            'comment': 'Comment or note',
            'flag': 'Boolean flag or indicator',
            'active': 'Active status indicator',
            'enabled': 'Enabled status indicator',
            'visible': 'Visibility indicator',
            'public': 'Public visibility indicator',
            'private': 'Private visibility indicator',
            'secret': 'Secret or sensitive data',
            'password': 'Password or authentication data',
            'token': 'Authentication token',
            'session': 'Session identifier',
            'uuid': 'Universally unique identifier',
            'guid': 'Globally unique identifier',
            'hash': 'Hash value',
            'checksum': 'Checksum or hash value',
            'size': 'Size or dimension',
            'length': 'Length or size',
            'width': 'Width dimension',
            'height': 'Height dimension',
            'weight': 'Weight value',
            'age': 'Age or duration',
            'duration': 'Duration or time period',
            'interval': 'Time interval',
            'frequency': 'Frequency or rate',
            'priority': 'Priority level',
            'rank': 'Rank or position',
            'order': 'Order or sequence',
            'index': 'Index or position',
            'position': 'Position or location',
            'location': 'Location or position',
            'address': 'Address or location',
            'country': 'Country identifier',
            'state': 'State or province',
            'city': 'City identifier',
            'zip': 'ZIP or postal code',
            'region': 'Region identifier',
            'zone': 'Zone identifier',
            'area': 'Area identifier',
            'site': 'Site identifier',
            'building': 'Building identifier',
            'floor': 'Floor number',
            'room': 'Room identifier',
            'department': 'Department identifier',
            'division': 'Division identifier',
            'company': 'Company identifier',
            'organization': 'Organization identifier',
            'project': 'Project identifier',
            'task': 'Task identifier',
            'job': 'Job identifier',
            'work': 'Work identifier',
            'process': 'Process identifier',
            'workflow': 'Workflow identifier',
            'step': 'Step identifier',
            'stage': 'Stage identifier',
            'phase': 'Phase identifier',
            'status': 'Status or state',
            'state': 'State or condition',
            'condition': 'Condition or state',
            'result': 'Result or outcome',
            'outcome': 'Outcome or result',
            'response': 'Response or answer',
            'answer': 'Answer or response',
            'solution': 'Solution or resolution',
            'resolution': 'Resolution or solution',
            'error': 'Error information',
            'exception': 'Exception information',
            'warning': 'Warning information',
            'message': 'Message or communication',
            'notification': 'Notification or alert',
            'alert': 'Alert or notification',
            'event': 'Event or occurrence',
            'action': 'Action or operation',
            'operation': 'Operation or action',
            'function': 'Function or method',
            'method': 'Method or function',
            'procedure': 'Procedure or process',
            'algorithm': 'Algorithm or method',
            'formula': 'Formula or calculation',
            'calculation': 'Calculation or computation',
            'computation': 'Computation or calculation',
            'metric': 'Metric or measurement',
            'measurement': 'Measurement or metric',
            'statistic': 'Statistic or metric',
            'kpi': 'Key Performance Indicator',
            'indicator': 'Indicator or metric',
            'threshold': 'Threshold or limit',
            'limit': 'Limit or threshold',
            'maximum': 'Maximum value',
            'minimum': 'Minimum value',
            'average': 'Average value',
            'mean': 'Mean value',
            'median': 'Median value',
            'mode': 'Mode value',
            'sum': 'Sum or total',
            'total': 'Total or sum',
            'count': 'Count or quantity',
            'quantity': 'Quantity or count',
            'number': 'Number or numeric value',
            'numeric': 'Numeric value',
            'integer': 'Integer value',
            'decimal': 'Decimal value',
            'float': 'Floating point value',
            'double': 'Double precision value',
            'boolean': 'Boolean value',
            'text': 'Text value',
            'string': 'String value',
            'char': 'Character value',
            'varchar': 'Variable character value',
            'json': 'JSON data',
            'xml': 'XML data',
            'html': 'HTML data',
            'url': 'URL or link',
            'link': 'Link or URL',
            'reference': 'Reference or pointer',
            'pointer': 'Pointer or reference',
            'foreign': 'Foreign key reference',
            'primary': 'Primary key identifier',
            'unique': 'Unique identifier',
            'index': 'Index or key',
            'key': 'Key or identifier',
            'identifier': 'Identifier or key',
            'reference': 'Reference or foreign key',
            'parent': 'Parent identifier',
            'child': 'Child identifier',
            'root': 'Root identifier',
            'leaf': 'Leaf identifier',
            'node': 'Node identifier',
            'edge': 'Edge identifier',
            'vertex': 'Vertex identifier',
            'graph': 'Graph identifier',
            'tree': 'Tree identifier',
            'list': 'List identifier',
            'array': 'Array identifier',
            'vector': 'Vector identifier',
            'matrix': 'Matrix identifier',
            'table': 'Table identifier',
            'view': 'View identifier',
            'query': 'Query identifier',
            'filter': 'Filter criteria',
            'sort': 'Sort criteria',
            'order': 'Order criteria',
            'group': 'Group criteria',
            'aggregate': 'Aggregate value',
            'summary': 'Summary information',
            'detail': 'Detail information',
            'overview': 'Overview information',
            'preview': 'Preview information',
            'thumbnail': 'Thumbnail image',
            'image': 'Image data',
            'photo': 'Photo or image',
            'picture': 'Picture or image',
            'file': 'File data',
            'document': 'Document data',
            'attachment': 'Attachment data',
            'blob': 'Binary large object',
            'clob': 'Character large object',
            'text': 'Text data',
            'content': 'Content data',
            'body': 'Body content',
            'header': 'Header information',
            'footer': 'Footer information',
            'title': 'Title or heading',
            'subject': 'Subject or topic',
            'topic': 'Topic or subject',
            'theme': 'Theme or style',
            'style': 'Style or theme',
            'format': 'Format specification',
            'template': 'Template specification',
            'pattern': 'Pattern specification',
            'rule': 'Rule or constraint',
            'constraint': 'Constraint or rule',
            'validation': 'Validation rule',
            'check': 'Check constraint',
            'trigger': 'Trigger specification',
            'event': 'Event specification',
            'handler': 'Event handler',
            'callback': 'Callback function',
            'listener': 'Event listener',
            'observer': 'Observer pattern',
            'subscriber': 'Event subscriber',
            'publisher': 'Event publisher',
            'producer': 'Data producer',
            'consumer': 'Data consumer',
            'sender': 'Message sender',
            'receiver': 'Message receiver',
            'source': 'Data source',
            'target': 'Data target',
            'destination': 'Data destination',
            'origin': 'Data origin',
            'endpoint': 'Service endpoint',
            'service': 'Service identifier',
            'api': 'API identifier',
            'interface': 'Interface specification',
            'contract': 'Service contract',
            'schema': 'Data schema',
            'model': 'Data model',
            'entity': 'Data entity',
            'object': 'Data object',
            'class': 'Class definition',
            'type': 'Type definition',
            'enum': 'Enumeration value',
            'constant': 'Constant value',
            'variable': 'Variable value',
            'parameter': 'Parameter value',
            'argument': 'Function argument',
            'option': 'Configuration option',
            'setting': 'Configuration setting',
            'config': 'Configuration data',
            'preference': 'User preference',
            'choice': 'User choice',
            'selection': 'User selection',
            'input': 'Input data',
            'output': 'Output data',
            'request': 'Request data',
            'response': 'Response data',
            'payload': 'Data payload',
            'body': 'Message body',
            'header': 'Message header',
            'metadata': 'Metadata information',
            'info': 'Information data',
            'details': 'Detail information',
            'summary': 'Summary information',
            'overview': 'Overview information',
            'preview': 'Preview information',
            'thumbnail': 'Thumbnail image',
            'icon': 'Icon image',
            'logo': 'Logo image',
            'banner': 'Banner image',
            'background': 'Background image',
            'foreground': 'Foreground image',
            'layer': 'Layer information',
            'level': 'Level information',
            'tier': 'Tier information',
            'grade': 'Grade information',
            'rating': 'Rating information',
            'score': 'Score information',
            'points': 'Points information',
            'credits': 'Credits information',
            'balance': 'Balance information',
            'amount': 'Amount information',
            'value': 'Value information',
            'price': 'Price information',
            'cost': 'Cost information',
            'fee': 'Fee information',
            'charge': 'Charge information',
            'payment': 'Payment information',
            'transaction': 'Transaction information',
            'order': 'Order information',
            'purchase': 'Purchase information',
            'sale': 'Sale information',
            'revenue': 'Revenue information',
            'profit': 'Profit information',
            'loss': 'Loss information',
            'expense': 'Expense information',
            'income': 'Income information',
            'budget': 'Budget information',
            'allocation': 'Allocation information',
            'quota': 'Quota information',
            'limit': 'Limit information',
            'threshold': 'Threshold information',
            'maximum': 'Maximum value',
            'minimum': 'Minimum value',
            'average': 'Average value',
            'mean': 'Mean value',
            'median': 'Median value',
            'mode': 'Mode value',
            'range': 'Range information',
            'variance': 'Variance information',
            'deviation': 'Deviation information',
            'standard': 'Standard information',
            'normal': 'Normal information',
            'abnormal': 'Abnormal information',
            'anomaly': 'Anomaly information',
            'outlier': 'Outlier information',
            'exception': 'Exception information',
            'error': 'Error information',
            'warning': 'Warning information',
            'alert': 'Alert information',
            'notification': 'Notification information',
            'message': 'Message information',
            'communication': 'Communication information',
            'contact': 'Contact information',
            'address': 'Address information',
            'location': 'Location information',
            'position': 'Position information',
            'coordinate': 'Coordinate information',
            'latitude': 'Latitude coordinate',
            'longitude': 'Longitude coordinate',
            'altitude': 'Altitude coordinate',
            'elevation': 'Elevation coordinate',
            'depth': 'Depth coordinate',
            'distance': 'Distance information',
            'length': 'Length information',
            'width': 'Width information',
            'height': 'Height information',
            'size': 'Size information',
            'dimension': 'Dimension information',
            'area': 'Area information',
            'volume': 'Volume information',
            'capacity': 'Capacity information',
            'weight': 'Weight information',
            'mass': 'Mass information',
            'density': 'Density information',
            'temperature': 'Temperature information',
            'pressure': 'Pressure information',
            'humidity': 'Humidity information',
            'speed': 'Speed information',
            'velocity': 'Velocity information',
            'acceleration': 'Acceleration information',
            'force': 'Force information',
            'energy': 'Energy information',
            'power': 'Power information',
            'current': 'Current information',
            'voltage': 'Voltage information',
            'resistance': 'Resistance information',
            'frequency': 'Frequency information',
            'wavelength': 'Wavelength information',
            'amplitude': 'Amplitude information',
            'phase': 'Phase information',
            'signal': 'Signal information',
            'noise': 'Noise information',
            'quality': 'Quality information',
            'performance': 'Performance information',
            'efficiency': 'Efficiency information',
            'effectiveness': 'Effectiveness information',
            'productivity': 'Productivity information',
            'throughput': 'Throughput information',
            'latency': 'Latency information',
            'bandwidth': 'Bandwidth information',
            'capacity': 'Capacity information',
            'utilization': 'Utilization information',
            'availability': 'Availability information',
            'reliability': 'Reliability information',
            'durability': 'Durability information',
            'stability': 'Stability information',
            'consistency': 'Consistency information',
            'accuracy': 'Accuracy information',
            'precision': 'Precision information',
            'recall': 'Recall information',
            'f1': 'F1 score information',
            'auc': 'AUC score information',
            'roc': 'ROC curve information',
            'confusion': 'Confusion matrix information',
            'classification': 'Classification information',
            'regression': 'Regression information',
            'clustering': 'Clustering information',
            'association': 'Association information',
            'correlation': 'Correlation information',
            'causation': 'Causation information',
            'dependency': 'Dependency information',
            'relationship': 'Relationship information',
            'connection': 'Connection information',
            'link': 'Link information',
            'edge': 'Edge information',
            'node': 'Node information',
            'vertex': 'Vertex information',
            'graph': 'Graph information',
            'tree': 'Tree information',
            'forest': 'Forest information',
            'network': 'Network information',
            'topology': 'Topology information',
            'structure': 'Structure information',
            'hierarchy': 'Hierarchy information',
            'taxonomy': 'Taxonomy information',
            'ontology': 'Ontology information',
            'schema': 'Schema information',
            'model': 'Model information',
            'pattern': 'Pattern information',
            'template': 'Template information',
            'format': 'Format information',
            'standard': 'Standard information',
            'specification': 'Specification information',
            'protocol': 'Protocol information',
            'interface': 'Interface information',
            'api': 'API information',
            'service': 'Service information',
            'endpoint': 'Endpoint information',
            'resource': 'Resource information',
            'asset': 'Asset information',
            'entity': 'Entity information',
            'object': 'Object information',
            'instance': 'Instance information',
            'record': 'Record information',
            'row': 'Row information',
            'column': 'Column information',
            'field': 'Field information',
            'attribute': 'Attribute information',
            'property': 'Property information',
            'feature': 'Feature information',
            'characteristic': 'Characteristic information',
            'trait': 'Trait information',
            'aspect': 'Aspect information',
            'dimension': 'Dimension information',
            'factor': 'Factor information',
            'element': 'Element information',
            'component': 'Component information',
            'part': 'Part information',
            'piece': 'Piece information',
            'fragment': 'Fragment information',
            'segment': 'Segment information',
            'section': 'Section information',
            'chapter': 'Chapter information',
            'page': 'Page information',
            'line': 'Line information',
            'word': 'Word information',
            'character': 'Character information',
            'byte': 'Byte information',
            'bit': 'Bit information',
            'nibble': 'Nibble information',
            'octet': 'Octet information',
            'word': 'Word information',
            'dword': 'Double word information',
            'qword': 'Quad word information',
            'float': 'Float information',
            'double': 'Double information',
            'decimal': 'Decimal information',
            'integer': 'Integer information',
            'long': 'Long information',
            'short': 'Short information',
            'byte': 'Byte information',
            'char': 'Char information',
            'boolean': 'Boolean information',
            'string': 'String information',
            'text': 'Text information',
            'varchar': 'Varchar information',
            'char': 'Char information',
            'nchar': 'NChar information',
            'nvarchar': 'NVarchar information',
            'text': 'Text information',
            'ntext': 'NText information',
            'image': 'Image information',
            'binary': 'Binary information',
            'varbinary': 'VarBinary information',
            'blob': 'Blob information',
            'clob': 'Clob information',
            'nclob': 'NClob information',
            'xml': 'XML information',
            'json': 'JSON information',
            'yaml': 'YAML information',
            'csv': 'CSV information',
            'tsv': 'TSV information',
            'xlsx': 'XLSX information',
            'pdf': 'PDF information',
            'doc': 'DOC information',
            'docx': 'DOCX information',
            'ppt': 'PPT information',
            'pptx': 'PPTX information',
            'xls': 'XLS information',
            'zip': 'ZIP information',
            'rar': 'RAR information',
            'tar': 'TAR information',
            'gz': 'GZ information',
            'bz2': 'BZ2 information',
            '7z': '7Z information',
            'iso': 'ISO information',
            'img': 'IMG information',
            'bin': 'BIN information',
            'exe': 'EXE information',
            'dll': 'DLL information',
            'so': 'SO information',
            'dylib': 'DYLIB information',
            'a': 'A information',
            'lib': 'LIB information',
            'obj': 'OBJ information',
            'o': 'O information',
            'class': 'CLASS information',
            'jar': 'JAR information',
            'war': 'WAR information',
            'ear': 'EAR information',
            'sar': 'SAR information',
            'rar': 'RAR information',
            'zip': 'ZIP information',
            'tar': 'TAR information',
            'gz': 'GZ information',
            'bz2': 'BZ2 information',
            '7z': '7Z information',
            'iso': 'ISO information',
            'img': 'IMG information',
            'bin': 'BIN information',
            'exe': 'EXE information',
            'dll': 'DLL information',
            'so': 'SO information',
            'dylib': 'DYLIB information',
            'a': 'A information',
            'lib': 'LIB information',
            'obj': 'OBJ information',
            'o': 'O information',
            'class': 'CLASS information',
            'jar': 'JAR information',
            'war': 'WAR information',
            'ear': 'EAR information',
            'sar': 'SAR information'
        }
        
        # Look for patterns in the column name
        for pattern, description in patterns.items():
            if pattern in name_lower:
                return f"{description} for {column_name.replace('_', ' ').lower()}"
        
        # If no pattern matches, generate a generic description
        return f"Data field for {column_name.replace('_', ' ').lower()}"

    def _validate_ddl_syntax(self, ddl: str) -> bool:
        """Basic validation of DDL syntax to catch obvious issues."""
        try:
            logger.debug(f"Validating DDL: {repr(ddl[:100])}...")
            
            # Check for unmatched parentheses (excluding those in comments)
            lines = ddl.split('\n')
            sql_content = []
            for line in lines:
                # Remove comment portions from each line
                if '--' in line:
                    comment_start = line.find('--')
                    sql_content.append(line[:comment_start])
                else:
                    sql_content.append(line)
            
            # Join the SQL content and count parentheses
            sql_text = '\n'.join(sql_content)
            open_parens = sql_text.count('(')
            close_parens = sql_text.count(')')
            if open_parens != close_parens:
                logger.error(f"Unmatched parentheses in DDL: {open_parens} open, {close_parens} close")
                logger.error(f"DDL content: {repr(ddl)}")
                logger.error(f"SQL content (without comments): {repr(sql_text)}")
                return False
            
            # Check for basic SQL structure - allow comments before CREATE
            ddl_content = ddl.strip()
            # Skip comment lines to find the actual CREATE statement
            lines = ddl_content.split('\n')
            create_line = None
            for line in lines:
                line = line.strip()
                if line and not line.startswith('--'):
                    create_line = line
                    break
            
            if not create_line or not create_line.upper().startswith('CREATE'):
                logger.error(f"DDL doesn't contain CREATE statement: {repr(ddl[:50])}...")
                return False
            
            # Check for empty table definition
            if 'CREATE TABLE' in ddl.upper() and '()' in ddl:
                logger.error(f"Empty table definition in DDL: {repr(ddl)}")
                return False
                
            # Check for problematic characters in table/column names
            if any(char in ddl for char in ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', '\x08', '\x0b', '\x0c', '\x0e', '\x0f']):
                logger.error(f"DDL contains control characters")
                return False
            
            # Check for common SQL syntax issues
            if 'CREATE TABLE' in ddl.upper() and not ddl.strip().endswith(';'):
                logger.error(f"DDL doesn't end with semicolon: {repr(ddl[-20:])}")
                return False
                
            logger.debug(f"DDL validation passed for: {ddl[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error validating DDL syntax: {str(e)}")
            logger.error(f"DDL that caused error: {repr(ddl)}")
            return False

    def _build_table_ddl(self, table_name, description, columns):
        try:
            logger.debug(f"Building DDL for table {table_name}")
            logger.debug(f"Description: {description[:100] if description else 'None'}...")
            logger.debug(f"Columns type: {type(columns)}, length: {len(columns) if columns else 0}")
            logger.debug(f"Columns sample: {columns[:2] if columns else 'None'}")
            
            col_defs = self._build_column_defs(columns)
            logger.debug(f"Generated column definitions: {col_defs}")
            
            # Clean description for SQL comment
            if description:
                # Remove problematic characters and limit length
                clean_description = description.replace('\n', ' ').replace('\r', ' ').strip()
                # Remove or replace problematic characters that could cause SQL issues
                clean_description = clean_description.replace('(', '[').replace(')', ']')
                # Limit comment length to avoid issues
                if len(clean_description) > 200:
                    clean_description = clean_description[:200] + "..."
                table_comment = f"-- {clean_description}\n"
            else:
                table_comment = ""
            
            # Ensure we have valid table name and column definitions
            if not table_name:
                logger.warning("No table name provided, skipping DDL generation")
                return ""
            
            if not col_defs:
                logger.warning(f"No column definitions for table {table_name}, skipping DDL generation")
                return ""
            logger.info(f"col_defs in build_table_ddl for {table_name}: {col_defs}")
            ddl = f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + "\n);"
            logger.info(f"Generated DDL for {table_name}:")
            logger.info(f"{ddl}")
            
            # Validate the generated DDL
            if not self._validate_ddl_syntax(ddl):
                logger.error(f"Generated DDL failed syntax validation for table {table_name}")
                logger.error(f"Problematic DDL: {ddl}")
                return ""
            
            return ddl
        except Exception as e:
            logger.error(f"Error building table DDL for {table_name}: {str(e)}")
            logger.error(f"Columns that caused error: {columns}")
            return ""

    def _build_metric_ddl(self, content_dict):
        try:
            table_name = content_dict.get("name", "")
            description = content_dict.get("description", "")
            columns = content_dict.get("columns", [])
            
            # Ensure we have valid table name
            if not table_name:
                logger.warning("No table name provided for metric, skipping DDL generation")
                return ""
            
            if not columns:
                logger.warning(f"No column definitions for metric {table_name}, skipping DDL generation")
                return ""
            
            col_defs = self._build_column_defs(columns, default_type="FLOAT")
            
            # Clean description for SQL comment
            if description:
                clean_description = description.replace('\n', ' ').replace('\r', ' ').strip()
                clean_description = clean_description.replace('(', '[').replace(')', ']')
                if len(clean_description) > 200:
                    clean_description = clean_description[:200] + "..."
                table_comment = f"-- {clean_description}\n"
            else:
                table_comment = ""
            
            if not col_defs:
                logger.warning(f"No valid column definitions for metric {table_name}, skipping DDL generation")
                return ""
            
            ddl = f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + "\n);"
            
            # Validate the generated DDL
            if not self._validate_ddl_syntax(ddl):
                logger.error(f"Generated metric DDL failed syntax validation for {table_name}")
                return ""
            
            return ddl
        except Exception as e:
            logger.error(f"Error building metric DDL: {str(e)}")
            return ""

    def _build_view_ddl(self, content_dict):
        try:
            view_name = content_dict.get("name", "")
            description = content_dict.get("description", "")
            statement = content_dict.get("statement", "")
            
            # Ensure we have valid view name and statement
            if not view_name:
                logger.warning("No view name provided, skipping DDL generation")
                return ""
            
            if not statement:
                logger.warning(f"No statement provided for view {view_name}, skipping DDL generation")
                return ""
            
            # Clean description for SQL comment
            if description:
                clean_description = description.replace('\n', ' ').replace('\r', ' ').strip()
                clean_description = clean_description.replace('(', '[').replace(')', ']')
                if len(clean_description) > 200:
                    clean_description = clean_description[:200] + "..."
                view_comment = f"-- {clean_description}\n"
            else:
                view_comment = ""
            ddl = f"{view_comment}CREATE VIEW {view_name}\nAS {statement}"
            
            # Validate the generated DDL
            if not self._validate_ddl_syntax(ddl):
                logger.error(f"Generated view DDL failed syntax validation for {view_name}")
                return ""
            
            return ddl
        except Exception as e:
            logger.error(f"Error building view DDL: {str(e)}")
            return ""

    def _construct_db_schemas(self, schema_docs: List[Dict], table_docs: List[Dict], column_docs: List[Dict] = None) -> List[Dict]:
        """Construct database schemas from retrieved documents."""
        tables = {}
        if column_docs is None:
            column_docs = []
        logger.info(f"Processing {len(schema_docs)} schema documents, {len(table_docs)} table documents and {len(column_docs)} column documents")
        
        # Process all documents - TABLE_COLUMNS already have all the information we need
        all_docs = schema_docs + table_docs + column_docs
        
        logger.info(f"DEBUG: Processing documents: {len(schema_docs)} schema_docs, {len(table_docs)} table_docs, {len(column_docs)} column_docs")
        
        for doc in all_docs:
            content_dict = self._parse_doc_content(doc)
            logger.info(f"DEBUG: Processing schema doc: {content_dict}")
            
            # Only process TABLE_COLUMNS documents to avoid confusion with TABLE_DESCRIPTION string columns
            if content_dict.get('type') == 'TABLE_DESCRIPTION':
                logger.debug(f"Skipping TABLE_DESCRIPTION document for table {content_dict.get('name', 'unknown')} to avoid string column confusion")
                continue
            elif (content_dict.get('type') == 'TABLE_COLUMNS' and 
                'columns' in content_dict):
                
                # Extract table name from document metadata for TABLE_COLUMNS documents
                table_name = doc.get('metadata', {}).get('name', '') if hasattr(doc, 'get') else ''
                logger.info(f"DEBUG: Processing {content_dict.get('type')} document for table {table_name}")
                
                logger.info(f"DEBUG: Found columns in content_dict: {content_dict.get('columns', [])[:2] if content_dict.get('columns') else 'None'}")
                if not table_name:
                    continue
                    
                # Extract columns from the schema document
                columns = content_dict.get('columns', [])
                logger.debug(f"Found columns for table {table_name}: {columns}")
                logger.debug(f"Columns type: {type(columns)}")
                
                # Process columns to extract proper information
                processed_columns = []
                
                # Process list columns from TABLE_COLUMNS data
                if isinstance(columns, list):
                    # Columns are stored as list of dictionaries (from db_schema.py)
                    logger.debug(f"Processing list columns: {len(columns)} items")
                    for col in columns:
                        if isinstance(col, dict):
                            # Extract comment and description from properties
                            comment = col.get('comment', '')
                            description = ''
                            
                            logger.debug(f"DEBUG: Processing column {col.get('name', '')} in _construct_db_schemas")
                            logger.debug(f"DEBUG: Column has properties: {'properties' in col}")
                            if 'properties' in col:
                                logger.debug(f"DEBUG: Properties: {col['properties']}")
                            
                            if 'properties' in col and isinstance(col['properties'], dict):
                                # Get display name as comment if available
                                if not comment:
                                    comment = col['properties'].get('displayName', '')
                                # Get description
                                description = col['properties'].get('description', '')
                                logger.debug(f"DEBUG: Extracted comment='{comment}', description='{description[:50] if description else 'None'}...'")
                                
                                # Enhanced logging for debugging
                                logger.info(f"DEBUG: Column {col.get('name', '')} properties: {col['properties']}")
                                logger.info(f"DEBUG: Column {col.get('name', '')}: comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                            
                            # Extract primary key and foreign key info from properties if available
                            is_primary_key = col.get('is_primary_key', False)
                            is_foreign_key = col.get('is_foreign_key', False)
                            
                            if 'properties' in col and isinstance(col['properties'], dict):
                                # Handle string values for boolean fields
                                if 'is_primary_key' in col['properties']:
                                    pk_val = col['properties']['is_primary_key']
                                    is_primary_key = pk_val if isinstance(pk_val, bool) else pk_val.lower() == 'true'
                                if 'is_foreign_key' in col['properties']:
                                    fk_val = col['properties']['is_foreign_key']
                                    is_foreign_key = fk_val if isinstance(fk_val, bool) else fk_val.lower() == 'true'
                            
                            # Preserve all MDL properties
                            # Extract data type with better handling
                            column_type = col.get('data_type', col.get('type', 'VARCHAR'))
                            logger.info(f"DEBUG: Column {col.get('name', '')} type extraction: data_type={col.get('data_type')}, type={col.get('type')}, final={column_type}")
                            logger.info(f"DEBUG: Full column object: {col}")
                            
                            processed_column = {
                                "name": col.get('name', ''),
                                "type": column_type,
                                "data_type": column_type,  # Ensure data_type is set for _build_column_defs
                                "comment": comment,
                                "description": description,
                                "is_primary_key": is_primary_key,
                                "is_foreign_key": is_foreign_key,
                                "notNull": col.get('notNull', False),
                                # Preserve all MDL properties
                                "properties": col.get('properties', {}),
                                "isCalculated": col.get('isCalculated', False),
                                "expression": col.get('expression', ''),
                                "relationship": col.get('relationship', {})
                            }
                            
                            # Add any other properties that might exist in the column
                            for key, value in col.items():
                                if key not in processed_column:
                                    processed_column[key] = value
                            
                            processed_columns.append(processed_column)
                        else:
                            # Handle string column names in list
                            processed_columns.append({
                                "name": str(col),
                                "type": "VARCHAR",
                                "comment": "",
                                "is_primary_key": False,
                                "is_foreign_key": False,
                                "notNull": False,
                                # Default MDL properties for string columns
                                "properties": {},
                                "isCalculated": False,
                                "expression": "",
                                "relationship": {}
                            })
                else:
                    logger.warning(f"Unexpected column format for table {table_name}: {type(columns)}")
                    continue
                
                # Create or update table with merged column information
                if table_name not in tables:
                    tables[table_name] = {
                        "name": table_name,
                        "type": content_dict.get('type', 'TABLE'),
                        "description": content_dict.get('description', ''),
                        "columns": processed_columns,
                        "relationships": content_dict.get('relationships', [])
                    }
                    logger.debug(f"Created table {table_name} with {len(processed_columns)} columns")
                else:
                    # Update existing table with additional columns if any, avoiding duplicates
                    existing_columns = tables[table_name].get('columns', [])
                    existing_column_names = {col.get('name', '') for col in existing_columns}
                    
                    # Only add columns that don't already exist
                    new_columns = []
                    for col in processed_columns:
                        col_name = col.get('name', '')
                        if col_name and col_name not in existing_column_names:
                            new_columns.append(col)
                            existing_column_names.add(col_name)
                    
                    if new_columns:
                        existing_columns.extend(new_columns)
                        tables[table_name]['columns'] = existing_columns
                        logger.debug(f"Updated table {table_name} with {len(new_columns)} new columns (skipped {len(processed_columns) - len(new_columns)} duplicates)")
                    else:
                        logger.debug(f"No new columns to add for table {table_name} (all were duplicates)")
            
        
        # Only use TABLE_COLUMNS data - no fallback to string columns to avoid confusion
        if not tables:
            logger.warning("No schema documents with TABLE_COLUMNS data found - this may result in incomplete table schemas")
        
        final_schemas = list(tables.values())
        logger.info(f"Constructed {len(final_schemas)} schemas")
        for schema in final_schemas:
            logger.debug(f"Schema {schema['name']}: {len(schema['columns'])} columns")
        return final_schemas

    async def _find_relevant_schemas_by_query(
        self,
        query: str,
        schema_docs: List[Any],
        project_id: Optional[str] = None
    ) -> List[Dict]:
        """Find the most relevant schemas using ChromaDB semantic search based on the query."""
        if not query or not schema_docs:
            return []
        
        try:
            # Use semantic search to find relevant table descriptions
            table_results = self.table_store.semantic_search(
                query=query,
                k=5,  # Limit to top 5 most relevant tables
                where={"project_id": {"$eq": project_id}} if project_id else None
            )
            
            # Use semantic search to find relevant schema documents
            schema_results = self.schema_store.semantic_search(
                query=query,
                k=5,  # Limit to top 5 most relevant schemas
                where={"project_id": {"$eq": project_id}} if project_id else None
            )
            
            # Combine and deduplicate results
            all_results = table_results + schema_results
            unique_tables = set()
            relevant_schemas = []
            
            for result in all_results:
                table_name = result.get('metadata', {}).get('name', '')
                if table_name and table_name not in unique_tables:
                    unique_tables.add(table_name)
                    relevant_schemas.append(result)
            
            logger.info(f"Found {len(relevant_schemas)} unique relevant schemas for query: {query}")
            return relevant_schemas
            
        except Exception as e:
            logger.error(f"Error in semantic search for relevant schemas: {str(e)}")
            return []
    
    async def _build_focused_ddl(
        self,
        relevant_schemas: List[Dict],
        query: str,
        project_id: Optional[str] = None
    ) -> List[Dict]:
        """Build focused DDL with only relevant columns based on the query."""
        if not relevant_schemas:
            return []
        
        focused_results = []
        
        for schema_doc in relevant_schemas:
            try:
                content_dict = self._parse_doc_content(schema_doc)
                table_name = content_dict.get('name', '')
                doc_type = content_dict.get('type', '')
                
                if not table_name:
                    continue
                
                # Get detailed column information for this table
                table_columns = await self._get_detailed_table_columns(
                    table_name, project_id
                )
                
                if not table_columns:
                    continue
                
                # Identify relevant columns based on query
                relevant_columns = self._identify_relevant_columns(
                    table_columns, query
                )
                
                if not relevant_columns:
                    continue
                
                # Build focused DDL with only relevant columns
                focused_ddl = self._build_focused_table_ddl(
                    table_name, relevant_columns, content_dict.get('description', '')
                )
                
                if focused_ddl:
                    focused_results.append({
                        "table_name": table_name,
                        "table_ddl": focused_ddl,
                        "relationships": content_dict.get('relationships', []),
                        "relevance_score": self._calculate_relevance_score(
                            table_name, relevant_columns, query
                        )
                    })
                    
            except Exception as e:
                logger.error(f"Error building focused DDL for schema: {str(e)}")
                continue
        
        # Sort by relevance score
        focused_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        logger.info(f"Built focused DDL for {len(focused_results)} schemas")
        return focused_results
    
    async def _get_detailed_table_columns(
        self,
        table_name: str,
        project_id: Optional[str] = None
    ) -> List[Dict]:
        """Get detailed column information for a specific table."""
        try:
            # Search for TABLE_COLUMNS documents for this table
            where_clause = {
                "$and": [
                    {"name": {"$eq": table_name}},
                    {"type": {"$eq": "TABLE_COLUMNS"}}
                ]
            }
            
            if project_id:
                where_clause["$and"].insert(0, {"project_id": {"$eq": project_id}})
            
            results = self.schema_store.semantic_search(
                query="",
                k=1,
                where=where_clause
            )
            
            if results:
                content_dict = self._parse_doc_content(results[0])
                return content_dict.get('columns', [])
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting detailed columns for table {table_name}: {str(e)}")
            return []
    
    def _identify_relevant_columns(
        self,
        columns: List[Dict],
        query: str
    ) -> List[Dict]:
        """Identify which columns are most relevant to the query."""
        if not columns or not query:
            return columns
        
        query_lower = query.lower()
        relevant_columns = []
        
        for column in columns:
            column_name = column.get('name', '').lower()
            column_type = column.get('type', '').lower()
            column_comment = column.get('comment', '').lower()
            
            # Calculate relevance score
            score = 0
            
            # Check for direct keyword matches
            query_words = query_lower.split()
            for word in query_words:
                if word in column_name:
                    score += 10
                if word in column_type:
                    score += 5
                if word in column_comment:
                    score += 3
            
            # Always include primary keys and important columns
            if any(keyword in column_name for keyword in ['id', 'key', 'pk', 'primary']):
                score += 15
            
            # Include columns with high relevance score
            if score > 0:
                column['relevance_score'] = score
                relevant_columns.append(column)
        
        # Sort by relevance score and limit to most relevant
        relevant_columns.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Limit to top 20 most relevant columns to keep DDL manageable
        return relevant_columns[:20]
    
    def _build_focused_table_ddl(
        self,
        table_name: str,
        relevant_columns: List[Dict],
        description: str = ""
    ) -> str:
        """Build focused DDL with only relevant columns."""
        if not relevant_columns:
            return ""
        
        ddl_lines = [f"-- Table: {table_name}"]
        if description:
            ddl_lines.append(f"-- Description: {description[:200]}...")
        ddl_lines.append(f"CREATE TABLE {table_name} (")
        
        column_definitions = []
        for column in relevant_columns:
            col_name = column.get('name', '')
            col_type = column.get('type', 'VARCHAR')
            col_comment = column.get('comment', '')
            
            if col_name:
                col_def = f"    {col_name} {col_type}"
                if col_comment:
                    col_def += f" -- {col_comment}"
                column_definitions.append(col_def)
        
        ddl_lines.append(",\n".join(column_definitions))
        ddl_lines.append(");")
        
        return "\n".join(ddl_lines)
    
    def _calculate_relevance_score(
        self,
        table_name: str,
        relevant_columns: List[Dict],
        query: str
    ) -> float:
        """Calculate overall relevance score for a table."""
        if not query:
            return 0.0
        
        query_lower = query.lower()
        table_name_lower = table_name.lower()
        
        score = 0.0
        
        # Table name relevance
        query_words = query_lower.split()
        for word in query_words:
            if word in table_name_lower:
                score += 10.0
        
        # Column relevance
        for column in relevant_columns:
            score += column.get('relevance_score', 0) * 0.1
        
        return score

    def _prune_schemas_intelligently(
        self,
        schemas: List[Dict],
        max_tokens: int,
        query: str = ""
    ) -> List[Dict]:
        """Intelligently prune schemas to fit within token limits while preserving relevance."""
        if not schemas:
            return []
        
        # Sort schemas by relevance to query (simple keyword matching for now)
        query_lower = query.lower() if query else ""
        schema_scores = []
        
        for schema in schemas:
            score = 0
            table_name = schema.get("table_name", "").lower()
            table_ddl = schema.get("table_ddl", "").lower()
            
            # Score based on query keyword matches
            if query_lower:
                if any(word in table_name for word in query_lower.split()):
                    score += 10
                if any(word in table_ddl for word in query_lower.split()):
                    score += 5
            
            # Prioritize tables with more columns (more comprehensive)
            ddl_length = len(table_ddl)
            score += min(ddl_length / 1000, 5)  # Cap at 5 points for length
            
            schema_scores.append((score, schema))
        
        # Sort by score (highest first)
        schema_scores.sort(key=lambda x: x[0], reverse=True)
        
        # Select schemas that fit within token limit
        selected_schemas = []
        current_tokens = 0
        
        for score, schema in schema_scores:
            schema_tokens = len(self._encoding.encode(schema.get("table_ddl", "")))
            
            if current_tokens + schema_tokens <= max_tokens:
                selected_schemas.append(schema)
                current_tokens += schema_tokens
            else:
                # Try to include partial schema if it's the first one
                if not selected_schemas and schema_tokens > 0:
                    # Truncate DDL to fit remaining tokens
                    remaining_tokens = max_tokens - current_tokens
                    if remaining_tokens > 1000:  # Only if we have reasonable space
                        truncated_ddl = self._truncate_ddl(schema.get("table_ddl", ""), remaining_tokens)
                        if truncated_ddl:
                            schema_copy = schema.copy()
                            schema_copy["table_ddl"] = truncated_ddl
                            selected_schemas.append(schema_copy)
                break
        
        logger.info(f"Intelligent pruning: selected {len(selected_schemas)} out of {len(schemas)} schemas")
        logger.info(f"Token usage: {current_tokens} out of {max_tokens}")
        
        return selected_schemas
    
    def _truncate_ddl(self, ddl: str, max_tokens: int) -> str:
        """Truncate DDL to fit within token limit while preserving structure."""
        if not ddl:
            return ""
        
        # Split DDL into lines and truncate from the end
        lines = ddl.split('\n')
        truncated_lines = []
        current_tokens = 0
        
        for line in lines:
            line_tokens = len(self._encoding.encode(line))
            if current_tokens + line_tokens <= max_tokens:
                truncated_lines.append(line)
                current_tokens += line_tokens
            else:
                # Add a truncation notice
                truncated_lines.append("-- ... (truncated for token limit)")
                break
        
        return '\n'.join(truncated_lines)

    def _check_schemas_without_pruning(
        self,
        db_schemas: List[Dict],
        schema_docs: List[Any]
    ) -> Dict:
        retrieval_results = []
        has_calculated_field = False
        has_metric = False
        try:
            for schema in db_schemas:
                if not isinstance(schema, dict):
                    continue
                schema_type = schema.get("type")
                if not schema_type:
                    continue
                if schema_type in ["TABLE", "TABLE_DESCRIPTION", "MODEL"]:
                    table_name = schema.get("name", "")
                    description = schema.get("description", "")
                    columns = schema.get("columns", [])
                    
                    logger.info(f"DEBUG: Building DDL for schema type {schema_type}")
                    logger.info(f"DEBUG: Table name: {table_name}")
                    logger.info(f"DEBUG: Description: {description}")
                    logger.info(f"DEBUG: Columns: {columns}")
                    
                    # Skip DDL generation if no columns are available
                    if not columns or len(columns) == 0:
                        logger.warning(f"DEBUG: Skipping DDL generation for table {table_name} - no columns available")
                        # Still add basic table information without DDL
                        retrieval_results.append({
                            "table_name": table_name,
                            "table_ddl": f"-- Table: {table_name}\n-- Description: {description[:200] if description else 'No description available'}...",
                            "relationships": schema.get("relationships", [])
                        })
                        continue
                    
                    ddl = self._build_table_ddl(table_name, description, columns)
                    
                    logger.info(f"DEBUG: Generated DDL for {table_name}:")
                    logger.info(f"{ddl}")
                    
                    # Only add to results if DDL was successfully generated
                    if ddl:
                        # Extract relationships from schema
                        relationships = schema.get("relationships", [])
                        retrieval_results.append({
                            "table_name": table_name,
                            "table_ddl": ddl,
                            "relationships": relationships
                        })
                    else:
                        logger.warning(f"DEBUG: DDL generation failed for table {table_name}")
            for doc in schema_docs:
                content_dict = self._parse_doc_content(doc)
                doc_type = content_dict.get('type')
                if doc_type == "METRIC":
                    # Extract relationships for metrics
                    ddl = self._build_metric_ddl(content_dict)
                    if ddl:
                        relationships = content_dict.get('relationships', [])
                        retrieval_results.append({
                            "table_name": content_dict.get("name", ""),
                            "table_ddl": ddl,
                            "relationships": relationships
                        })
                        has_metric = True
                elif doc_type == "VIEW":
                    # Extract relationships for views
                    ddl = self._build_view_ddl(content_dict)
                    if ddl:
                        relationships = content_dict.get('relationships', [])
                        retrieval_results.append({
                            "table_name": content_dict.get("name", ""),
                            "table_ddl": ddl,
                            "relationships": relationships
                        })
            table_ddls = [result["table_ddl"] for result in retrieval_results]
            token_count = len(self._encoding.encode(" ".join(table_ddls)))
            if token_count > 100_000 or not self._allow_using_db_schemas_without_pruning:
                return {
                    "db_schemas": [],
                    "tokens": token_count,
                    "has_calculated_field": has_calculated_field,
                    "has_metric": has_metric
                }
            return {
                "db_schemas": retrieval_results,
                "tokens": token_count,
                "has_calculated_field": has_calculated_field,
                "has_metric": has_metric
            }
        except Exception as e:
            logger.error(f"Error in schema check: {str(e)}")
            return {
                "db_schemas": [],
                "tokens": 0,
                "has_calculated_field": False,
                "has_metric": False
            }

    def _format_schemas_as_markdown(self, schemas: List[Dict]) -> str:
        """Format schemas as markdown to reduce token usage."""
        markdown_parts = []
        
        for schema in schemas:
            # Get table name from various possible locations
            table_name = (
                schema.get('table_name') or 
                schema.get('name') or 
                schema.get('metadata', {}).get('name', '') or
                'Unknown'
            )
            
            # Get table DDL from various possible locations
            table_ddl = schema.get('table_ddl', '')
            
            # If no table_ddl, try to extract from content and build DDL
            if not table_ddl and 'content' in schema:
                try:
                    import ast
                    content = schema['content']
                    # Handle string content that might be a dict representation
                    if isinstance(content, str):
                        content_dict = ast.literal_eval(content)
                    else:
                        content_dict = content
                    
                    if isinstance(content_dict, dict):
                        # Try different possible keys for DDL
                        table_ddl = (
                            content_dict.get('ddl') or
                            content_dict.get('table_ddl') or
                            ''
                        )
                        
                        # If still no DDL, try to build it from columns
                        if not table_ddl and content_dict.get('type') == 'TABLE_COLUMNS':
                            columns = content_dict.get('columns', [])
                            if columns and isinstance(columns, list):
                                # Build a simple DDL from columns
                                col_defs = []
                                for col in columns:
                                    if isinstance(col, dict):
                                        col_name = col.get('name', '')
                                        col_type = col.get('data_type', col.get('type', 'VARCHAR'))
                                        if col_name:
                                            col_defs.append(f"  {col_name} {col_type}")
                                
                                if col_defs:
                                    table_ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n);"
                except Exception as e:
                    logger.debug(f"Could not extract DDL from content: {str(e)}")
                    pass
            
            # Format table section
            markdown_parts.append(f"## Table: {table_name}\n")
            
            # If no table_ddl, try to build it from columns in schema
            if not table_ddl:
                columns = schema.get('columns', [])
                if columns and isinstance(columns, list):
                    # Build DDL from columns
                    col_defs = []
                    for col in columns:
                        if isinstance(col, dict):
                            col_name = col.get('name', '')
                            col_type = col.get('data_type', col.get('type', 'VARCHAR'))
                            comment = col.get('comment', '')
                            if col_name:
                                col_def = f"  {col_name} {col_type}"
                                if comment:
                                    # Add comment inline (truncate if too long)
                                    comment_short = comment[:100] + "..." if len(comment) > 100 else comment
                                    col_def += f" -- {comment_short.replace(chr(10), ' ').replace(chr(13), ' ')}"
                                col_defs.append(col_def)
                    
                    if col_defs:
                        table_ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n);"
            
            if table_ddl:
                markdown_parts.append("```sql")
                markdown_parts.append(table_ddl)
                markdown_parts.append("```\n")
            else:
                markdown_parts.append("*DDL not available*\n")
            
            # Add relationships if available
            relationships = schema.get('relationships', [])
            if relationships:
                markdown_parts.append("### Relationships:")
                for rel in relationships:
                    if isinstance(rel, dict):
                        rel_name = rel.get('name', '')
                        rel_models = rel.get('models', [])
                        rel_join_type = rel.get('joinType', '')
                        rel_condition = rel.get('condition', '')
                        
                        if rel_models:
                            models_str = ', '.join(rel_models) if isinstance(rel_models, list) else str(rel_models)
                            markdown_parts.append(f"- **{rel_name}** ({rel_join_type}): {models_str}")
                            if rel_condition:
                                markdown_parts.append(f"  - Condition: {rel_condition}")
                markdown_parts.append("")
            
            markdown_parts.append("")  # Add spacing between tables
        
        return "\n".join(markdown_parts)
    
    def _build_prompt(
        self,
        query: str,
        db_schemas: List[Dict],
        histories: Optional[List[Dict]]
    ) -> str:
        """Build prompt for column selection."""
        try:
            logger.info(f"Building prompt with {len(db_schemas)} schemas")
            
            # Add history context if available
            if histories:
                previous_queries = [history["question"] for history in histories]
                query = "\n".join(previous_queries) + "\n" + query
            
            # Format prompt with the schema DDLs
            try:
                # Enhance schema data with relationship information
                enhanced_schemas = []
                for schema_doc in db_schemas:
                    enhanced_schema = schema_doc.copy()
                    
                    # Extract relationships from the document content if available
                    if 'content' in schema_doc:
                        try:
                            import ast
                            content_dict = ast.literal_eval(schema_doc['content'])
                            if isinstance(content_dict, dict):
                                relationships = content_dict.get('relationships', [])
                                enhanced_schema['relationships'] = relationships
                        except:
                            enhanced_schema['relationships'] = []
                    else:
                        enhanced_schema['relationships'] = []
                    
                    enhanced_schemas.append(enhanced_schema)
                
                # Format schemas as markdown instead of JSON to reduce token usage
                schemas_str = self._format_schemas_as_markdown(enhanced_schemas)
                
                # Create the prompt using the template
                prompt = self._prompt.format(
                    question=query,
                    db_schemas=schemas_str
                )
                logger.info(f"Built prompt with {len(enhanced_schemas)} schemas in markdown format (reduced size)")
                return prompt
                
            except Exception as e:
                logger.error(f"Error formatting prompt: {str(e)}")
                # Return a minimal prompt if formatting fails
                return self._prompt.format(
                    question=query,
                    db_schemas="-- Error formatting schemas"
                )
            
        except Exception as e:
            logger.error(f"Error building prompt: {str(e)}")
            # Return a minimal prompt if there's an error
            return self._prompt.format(
                question=query,
                db_schemas="-- Error building prompt"
            )

    def _analyze_relationships_for_column_selection(
        self,
        selected_tables: Dict[str, set],
        db_schemas: List[Dict]
    ) -> Dict[str, set]:
        """Analyze relationships to suggest additional columns from related tables."""
        enhanced_selection = selected_tables.copy()
        
        for schema in db_schemas:
            table_name = schema.get("name")
            if not table_name or table_name not in selected_tables:
                continue
                
            relationships = schema.get("relationships", [])
            for relationship in relationships:
                models = relationship.get("models", [])
                join_type = relationship.get("joinType", "")
                condition = relationship.get("condition", "")
                
                # Find related tables
                related_tables = [model for model in models if model != table_name]
                
                for related_table in related_tables:
                    # Find the related table schema
                    related_schema = None
                    for s in db_schemas:
                        if s.get("name") == related_table:
                            related_schema = s
                            break
                    
                    if not related_schema:
                        continue
                    
                    # Extract join columns from the condition
                    join_columns = self._extract_join_columns(condition, related_table)
                    
                    # Add join columns to the related table selection
                    if related_table not in enhanced_selection:
                        enhanced_selection[related_table] = set()
                    
                    enhanced_selection[related_table].update(join_columns)
                    
                    # Add some key columns from related tables based on join type
                    if join_type in ["ONE_TO_MANY", "MANY_TO_ONE"]:
                        # Add primary key and some descriptive columns
                        for col in related_schema.get("columns", []):
                            col_name = col.get("name", "") if isinstance(col, dict) else str(col)
                            if col_name and (col_name.endswith("_id") or col_name.endswith("name") or col_name.endswith("title")):
                                enhanced_selection[related_table].add(col_name)
        
        return enhanced_selection
    
    def _extract_join_columns(self, condition: str, table_name: str) -> List[str]:
        """Extract column names from join condition for a specific table."""
        columns = []
        if not condition:
            return columns
            
        # Parse condition like "table1.column1 = table2.column2"
        parts = condition.split(" = ")
        for part in parts:
            if "." in part:
                table_col = part.strip()
                if table_col.startswith(f"{table_name}."):
                    column = table_col.split(".", 1)[1]
                    columns.append(column)
        
        return columns

    def _construct_retrieval_results(
        self,
        column_selection: Dict,
        db_schemas: List[Dict],
        schema_docs: List[Any],
        table_columns_map: Dict[str, List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Construct final retrieval results with selected columns.
        
        Args:
            column_selection: Dictionary containing column selection results from LLM
            db_schemas: List of database schemas
            schema_docs: List of schema documents
            
        Returns:
            Dictionary containing retrieval results and metadata
        """
        if not column_selection or not column_selection.get("results"):
            return {
                "retrieval_results": [],
                "has_calculated_field": False,
                "has_metric": False
            }
            
        # Process column selection
        selected_tables = {}
        for table in column_selection["results"]:
            table_name = table.get("table_name")
            if not table_name:
                continue
                
            table_contents = table.get("table_contents", {})
            if not table_contents:
                continue
                
            # Get columns directly from table_contents
            columns = table_contents.get("columns", [])
            if columns:
                selected_tables[table_name] = set(columns)
        
        # Enhance selection based on relationships
        enhanced_selection = self._analyze_relationships_for_column_selection(
            selected_tables, db_schemas
        )
        logger.info(f"Original selected_tables: {selected_tables}")
        logger.info(f"Enhanced column selection with relationships: {enhanced_selection}")
        
        # Log the difference between original and enhanced selection
        for table_name, original_cols in selected_tables.items():
            enhanced_cols = enhanced_selection.get(table_name, set())
            added_cols = enhanced_cols - original_cols
            if added_cols:
                logger.info(f"Table {table_name}: Added {len(added_cols)} columns from relationships: {added_cols}")
            else:
                logger.info(f"Table {table_name}: No additional columns added from relationships")
        
        retrieval_results = []
        has_calculated_field = False
        has_metric = False
        
        
        # Process table schemas
        for schema in db_schemas:
            if not isinstance(schema, dict):
                continue
                
            table_name = schema.get("name")
            if not table_name or table_name not in enhanced_selection:
                continue
                
            # Use TABLE_COLUMNS data if available, otherwise fall back to schema columns
            selected_columns = enhanced_selection.get(table_name, set())
            
            # Check if we have TABLE_COLUMNS data for this table
            if table_columns_map and table_name in table_columns_map:
                # Use TABLE_COLUMNS data which already has properly formatted comments
                table_columns = table_columns_map[table_name]
                logger.info(f"DEBUG: Using TABLE_COLUMNS data for {table_name} with {len(table_columns)} columns")
                logger.info(f"DEBUG: TABLE_COLUMNS sample: {table_columns[0] if table_columns else 'None'}")
                
                # Filter to only selected columns
                filtered_columns = []
                for col in table_columns:
                    column_name = col.get('name', '')
                    
                    # Only include columns that were selected by the column selection process
                    if column_name not in selected_columns:
                        logger.debug(f"DEBUG: Skipping column {column_name} - not in selected columns")
                        continue
                    
                    # TABLE_COLUMNS already has properly formatted comments from helper functions
                    filtered_columns.append(col)
                    logger.info(f"DEBUG: TABLE_COLUMNS column {column_name}: comment='{col.get('comment', '')[:50] if col.get('comment') else 'None'}...'")
            else:
                logger.info(f"DEBUG: No TABLE_COLUMNS data for {table_name}, using schema columns")
                # Fallback to schema columns (existing logic)
                schema_columns = schema.get("columns", [])
                logger.info(f"DEBUG: Using schema columns for {table_name} with {len(schema_columns)} columns, selected: {len(selected_columns)}")
                
                # Convert schema columns to the format expected by _build_column_defs
                # Only include columns that were selected by the column selection process
                filtered_columns = []
                for col in schema_columns:
                    logger.info(f"DEBUG: Processing column: {col}")
                    if isinstance(col, dict):
                        column_name = col.get('name', '')
                        
                        # Only include columns that were selected by the column selection process
                        if column_name not in selected_columns:
                            logger.debug(f"DEBUG: Skipping column {column_name} - not in selected columns")
                            continue
                        
                        # The comment and description are already processed in _construct_db_schemas
                        # Just use them directly
                        comment = col.get('comment', '')
                        description = col.get('description', '')
                        
                        column_info = {
                            'name': column_name,
                            'data_type': col.get('type', col.get('data_type', 'VARCHAR')),
                            'comment': comment,
                            'description': description,
                            'is_primary_key': col.get('is_primary_key', False),
                            'is_foreign_key': col.get('is_foreign_key', False),
                            'notNull': col.get('notNull', False),
                            # Preserve all MDL properties
                            'properties': col.get('properties', {}),
                            'isCalculated': col.get('isCalculated', False),
                            'expression': col.get('expression', ''),
                            'relationship': col.get('relationship', {})
                        }
                        
                        # Add any other properties that might exist in the column
                        for key, value in col.items():
                            if key not in column_info:
                                column_info[key] = value
                        filtered_columns.append(column_info)
                        logger.info(f"DEBUG: Column {column_name}: comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                    else:
                        # Fallback for string columns - only include if selected
                        col_name = str(col)
                        if col_name not in selected_columns:
                            logger.debug(f"DEBUG: Skipping string column {col_name} - not in selected columns")
                            continue
                            
                        filtered_columns.append({
                            'name': col_name,
                            'data_type': 'VARCHAR',
                            'comment': f'Column {col}',
                            'description': '',
                            'is_primary_key': False,
                            'is_foreign_key': False,
                            'notNull': False,
                            # Default MDL properties for string columns
                            'properties': {},
                            'isCalculated': False,
                            'expression': '',
                            'relationship': {}
                        })
            
            # Build DDL with selected columns only (pruned for efficiency)
            logger.info(f"DEBUG: Building DDL for table {table_name} with {len(filtered_columns)} selected columns")
            logger.info(f"DEBUG: Sample filtered column: {filtered_columns[0] if filtered_columns else 'None'}")
            ddl = self._build_table_ddl(
                table_name,
                schema.get("description", ""),
                filtered_columns
            )
            logger.info(f"selected_tables ddl in table retrieval: {ddl}")
            
            # Only add to results if DDL was successfully generated
            if ddl:
                logger.info(f"DEBUG: Generated DDL for {table_name}:")
                logger.info(f"{ddl}")
                # Extract relationships from table descriptions
                relationships = []
                for doc in schema_docs:
                    try:
                        content = doc.get('content', '')
                        if not content:
                            continue
                            
                        try:
                            content_dict = ast.literal_eval(content)
                        except:
                            continue
                        
                        if not isinstance(content_dict, dict):
                            continue
                            
                        # Check if this is a table description for the current table
                        if (content_dict.get('name') == table_name and 
                            content_dict.get('type') == 'TABLE_DESCRIPTION'):
                            relationships = content_dict.get('relationships', [])
                            break
                    except Exception as e:
                        logger.warning(f"Error extracting relationships: {str(e)}")
                        continue
                
                retrieval_results.append({
                    "table_name": table_name,
                    "table_ddl": ddl,
                    "relationships": relationships
                })
        
        # Process metrics and views
        #print("schema_docs in table retrieval: ", schema_docs)
        for doc in schema_docs:
            try:
                # Get content from document
                content = doc.get('content', '')
                if not content:
                    continue
                    
                try:
                    content_dict = ast.literal_eval(content)
                except:
                    continue
                
                if not isinstance(content_dict, dict):
                    continue
                    
                # Get type and name
                doc_type = content_dict.get('type')
               
                table_name = content_dict.get('name')
                
                if not doc_type or not table_name:
                    continue
                    
                # Only process if table is in enhanced selection
                if table_name not in enhanced_selection:
                    continue
                
                if doc_type == "METRIC" or content_dict.get('mdl_type') == "METRIC":
                    # Extract relationships for metrics
                    ddl = self._build_metric_ddl(content_dict)
                    if ddl:
                        relationships = content_dict.get('relationships', [])
                        retrieval_results.append({
                            "table_name": table_name,
                            "table_ddl": ddl,
                            "relationships": relationships
                        })
                        has_metric = True
                elif doc_type == "VIEW" or content_dict.get('mdl_type') == "VIEW":
                    # Extract relationships for views
                    ddl = self._build_view_ddl(content_dict)
                    if ddl:
                        relationships = content_dict.get('relationships', [])
                        retrieval_results.append({
                            "table_name": table_name,
                            "table_ddl": ddl,
                            "relationships": relationships
                        })
            except Exception as e:
                logger.warning(f"Error processing schema document: {str(e)}")
                continue
                
        # Log summary of DDL content
        logger.info(f"=== DDL CONTENT SUMMARY ===")
        logger.info(f"Total retrieval results: {len(retrieval_results)}")
        for result in retrieval_results:
            table_name = result.get("table_name", "unknown")
            table_ddl = result.get("table_ddl", "")
            logger.info(f"=== DDL for {table_name} ===")
            logger.info(f"{table_ddl}")
            logger.info(f"=== END DDL for {table_name} ===")
        
        logger.info(f"retrieval_results in table retrieval: {retrieval_results}")
        return {
            "retrieval_results": retrieval_results,
            "has_calculated_field": has_calculated_field,
            "has_metric": has_metric
        }


   

if __name__ == "__main__":
    # Example usage
    import chromadb
    from langchain_openai import OpenAIEmbeddings
    from app.settings import get_settings
    import os
    settings = get_settings()
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    
    # Initialize embeddings
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    # Initialize document store and processor
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    doc_store = DocumentChromaStore(
        persistent_client=persistent_client,
        collection_name="table_descriptions2"
    )
    
    processor = TableRetrieval(
        document_store=doc_store,
        embedder=embeddings,
        model_name="gpt-4",
        table_retrieval_size=10,
        table_column_retrieval_size=100,
        allow_using_db_schemas_without_pruning=False
    )
    
    # Example query
    query = "Show me sales data for last month"
    
    # Process the query
    import asyncio
    result = asyncio.run(processor.run(query, project_id="demo_project"))
    print(f"Retrieved tables: {result}")
