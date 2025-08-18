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
2. For each table, provide a clear and concise reasoning for why specific columns are selected.
3. List each reason as part of a step-by-step chain of thought, justifying the inclusion of each column.
4. If a "." is included in columns, put the name before the first dot into chosen columns.
5. The number of columns chosen must match the number of reasoning.
6. Final chosen columns must be only column names, don't prefix it with table names.
7. If the chosen column is a child column of a STRUCT type column, choose the parent column instead of the child column.

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
### Database Schema in chroma stored documents json format  ###

{db_schemas}

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
        document_store: DocumentChromaStore,
        embedder: Any,
        model_name: str = "gpt-4o-mini",
        table_retrieval_size: int = 10,
        table_column_retrieval_size: int = 100,
        allow_using_db_schemas_without_pruning: bool = False,
    ) -> None:
        """Initialize the table retrieval processor.
        
        Args:
            document_store: The Chroma document store instance
            embedder: The text embedder instance
            model_name: Name of the LLM model to use
            table_retrieval_size: Maximum number of tables to retrieve
            table_column_retrieval_size: Maximum number of columns to retrieve
            allow_using_db_schemas_without_pruning: Whether to allow using full schemas
        """
        
        self._embedder = embedder
        self._table_retrieval_size = table_retrieval_size
        self._table_column_retrieval_size = table_column_retrieval_size
        self._allow_using_db_schemas_without_pruning = allow_using_db_schemas_without_pruning
        self.table_store = get_doc_store_provider().get_store("table_description")
        self.schema_store = get_doc_store_provider().get_store("db_schema")
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
        logger.info(f"Table retrieval is running... for {project_id}")
        logger.info(f"DEBUG: TableRetrieval.run() called with project_id: {project_id}")
        logger.info(f"DEBUG: project_id type: {type(project_id)}")
        logger.info(f"DEBUG: project_id value: {repr(project_id)}")
        
        try:
            # Add debug logging
            logger.info(f"DEBUG: TableRetrieval.run() - about to call _retrieve_table_descriptions with project_id: {project_id}")
            
            # Get table descriptions
            table_docs = await self._retrieve_table_descriptions(
                query, tables, project_id
            )
            #print("table_docs in run table retrieval", table_docs)
            if not table_docs:
                return {
                    "retrieval_results": [],
                    "has_calculated_field": False,
                    "has_metric": False
                }
           
            # Get schema information
            schema_docs = await self._retrieve_schemas(
                table_docs, project_id
            )
            
            
            metrics = await self._retrieve_metrics(query, tables, project_id)
            views = await self._retrieve_views(query, tables, project_id)
           

            # Combine all
            schema_docs = schema_docs + metrics + views
            
            # Construct database schemas
            db_schemas = self._construct_db_schemas(schema_docs, table_docs)
            
            
            # Check if we can use schemas without pruning
            schema_check = self._check_schemas_without_pruning(
                db_schemas, schema_docs
            )
            
            if schema_check["db_schemas"]:
                return {
                    "retrieval_results": schema_check["db_schemas"],
                    "has_calculated_field": schema_check["has_calculated_field"],
                    "has_metric": schema_check["has_metric"]
                }
            
           
            #logger.info(f"query in run table retrieval: {schema_docs}")
            if query:
                # Build prompt with schemas
                prompt = self._build_prompt(query, schema_docs, histories)
                # Get column selection from LLM
                column_selection = await self._get_column_selection(prompt)
                #print("column_selection", column_selection)
                # Construct final results with selected columns
                return self._construct_retrieval_results(
                    column_selection, db_schemas, schema_docs
                )
            
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
                if doc_type not in ['TABLE', 'TABLE_DESCRIPTION', 'MODEL', 'TABLE_SCHEMA', 'TABLE_COLUMNS']:
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
            if project_id:
                where = {"$and": [{"project_id": {"$eq": project_id}},{"type": {"$eq": "METRIC"}}]}
            where = {"project_id": {"$eq": project_id}}
            #where = None
            if query:
                # Get query embedding
                #embedding_result = await self._embedder.aembed_query(query)
                # Get results from document store
                if where:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=30,
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
            if project_id:
                where = {"$and": [{"project_id": {"$eq": project_id}},{"type": {"$eq": "VIEW"}}]}
            where = {"project_id": {"$eq": project_id}}
            #where = None
            if query:
                # Get query embedding
                #embedding_result = await self._embedder.aembed_query(query)
                # Get results from document store
                if where:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=30,
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
            logger.info(f"DEBUG: _retrieve_table_descriptions called with project_id: {project_id}")
            logger.info(f"DEBUG: project_id type: {type(project_id)}")
            logger.info(f"DEBUG: project_id value: {repr(project_id)}")
            
            where = {"type": {"$eq": 'TABLE_SCHEMA'}}
            if project_id:
                where = {"$and": [{"project_id": {"$eq": project_id}},{"type": {"$eq": "TABLE_SCHEMA"}}]}
            
            logger.info(f"DEBUG: _retrieve_table_descriptions - final where clause: {where}")
            #where = None
            if query:
                # Get query embedding
                #embedding_result = await self._embedder.aembed_query(query)
                # Get results from document store
                if where:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=30,
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
                        ast.literal_eval(item['content']).get('type') == 'TABLE_DESCRIPTION' and
                        ast.literal_eval(item['content']).get('mdl_type') == 'TABLE_SCHEMA'
                    )
                    or (
                        isinstance(item.get('metadata'), dict) and
                        item['metadata'].get('type') == 'TABLE_DESCRIPTION' and
                        item['metadata'].get('mdl_type') == 'TABLE_SCHEMA'
                    )
                )
            ]
            
            logger.info(f"DEBUG: _retrieve_table_descriptions - filtered {len(results)} results down to {len(filtered_results)} results")
            
            # Extract table names
            #table_names = self._extract_table_names(results)
            #print("table_names in retrieve_table_descriptions", table_names)
           
            # Results are already a list of documents
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
        results = []  # Initialize results at the start
        
        if not table_names:
            # Always create a valid where clause for TABLE_SCHEMA type
            where = {"type": {"$eq": 'TABLE_SCHEMA'}}
            if project_id:
                where = {"$and": [{"project_id": {"$eq": project_id}}, {"type": {"$eq": 'TABLE_SCHEMA'}}]}
            
            # Add debug logging for where clause
            logger.info(f"DEBUG: _retrieve_schemas - project_id: {project_id}")
            logger.info(f"DEBUG: _retrieve_schemas - where clause: {where}")
            logger.info(f"DEBUG: _retrieve_schemas - where clause type: {type(where)}")
            
            # Perform search with empty table names - where is guaranteed to be valid here
            results = self.schema_store.semantic_search(
                query="",
                k=10,
                where=where
            )
        else:
            for table_name in table_names:
                where = {"$and": [{"name": {"$eq": table_name}}, {"type": {"$eq": 'TABLE_SCHEMA'}}]}
                if project_id:
                    where = {
                        "$and": [
                            {"project_id": {"$eq": project_id}},
                            {"name": {"$eq": table_name}},
                            {"type": {"$eq": 'TABLE_SCHEMA'}}
                        ]
                    }    
                
                # Add debug logging for where clause
                logger.info(f"DEBUG: _retrieve_schemas - table_name: {table_name}, project_id: {project_id}")
                logger.info(f"DEBUG: _retrieve_schemas - where clause: {where}")
                
                # Use schema store's semantic search
                tresults = self.schema_store.semantic_search(
                    query="",  # Empty query since we're filtering by table names
                    k=10,
                    where=where
                )
                results.extend(tresults)
        
        #logger.info(f"results in retrieve_schemas: {json.dumps(results, indent=4)}")        
        if not results:
            return []
        
        return results

    def _parse_doc_content(self, doc) -> dict:
        """Safely parse the 'content' field from a document and return a dict."""
        content = doc.get('content', '')
        if not content:
            return {}
        try:
            content = content.strip("'").strip('"')
            return ast.literal_eval(content)
        except Exception as e:
            logger.warning(f"Failed to parse content: {content} | Error: {str(e)}")
            return {}

    def _is_table_doc(self, content_dict) -> bool:
        return content_dict.get('type') in ['TABLE_SCHEMA', 'TABLE_DESCRIPTION', 'MODEL','METRIC','VIEW']

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

    def _build_column_defs(self, columns, default_type="STRING"):
        col_defs = []
        for col in columns:
            # If col['name'] is a stringified dict, parse it
            if isinstance(col, dict) and isinstance(col.get('name'), str) and col['name'].strip().startswith("{'type': 'COLUMN'"):
                try:
                    col_info = ast.literal_eval(col['name'])
                    name = col_info.get('name', '')
                    dtype = col_info.get('data_type', default_type)
                    comment = col_info.get('comment', '')
                except Exception as e:
                    logger.warning(f"Failed to parse column name as dict: {col['name']} | Error: {str(e)}")
                    name = col.get('name', '')
                    dtype = col.get('data_type', default_type)
                    comment = col.get('comment', '')
            elif isinstance(col, dict):
                name = col.get('name', '')
                dtype = col.get('data_type', default_type)
                comment = col.get('comment', '')
            else:
                name = str(col)
                dtype = default_type
                comment = ''
            col_def = f"{name} {dtype}"
            if comment:
                if comment.strip().startswith("--"):
                    col_def += f"\n{comment.strip()}"
                else:
                    col_def += f" -- {comment}"
            col_defs.append(col_def)
        return col_defs if col_defs else [f"id {default_type}"]

    def _build_table_ddl(self, table_name, description, columns):
        col_defs = self._build_column_defs(columns)
        #print("col_defs in build_table_ddl: ", col_defs)
        table_comment = f"-- {description}\n" if description else ""
        return f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + "\n);"

    def _build_metric_ddl(self, content_dict):
        table_name = content_dict.get("name", "")
        description = content_dict.get("description", "")
        columns = content_dict.get("columns", [])
        if not columns:
            columns = [
                {"name": "metric_name", "data_type": "STRING", "comment": "Name of the metric"},
                {"name": "metric_value", "data_type": "FLOAT", "comment": "Value of the metric"},
                {"name": "dimension", "data_type": "STRING", "comment": "Dimension being measured"},
                {"name": "timestamp", "data_type": "TIMESTAMP", "comment": "When the metric was calculated"}
            ]
        col_defs = self._build_column_defs(columns, default_type="FLOAT")
        table_comment = f"-- {description}\n" if description else ""
        return f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + "\n);"

    def _build_view_ddl(self, content_dict):
        view_name = content_dict.get("name", "")
        description = content_dict.get("description", "")
        statement = content_dict.get("statement", "")
        view_comment = f"-- {description}\n" if description else ""
        return f"{view_comment}CREATE VIEW {view_name}\nAS {statement}"

    def _construct_db_schemas(self, column_docs: List[Dict], table_docs: List[Dict]) -> List[Dict]:
        """Construct database schemas from retrieved documents."""
        tables = {}
        logger.info(f"Processing {len(table_docs)} table documents and {len(column_docs)} column documents")
        # Collect all tables from table docs
        for doc in table_docs:
            content_dict = self._parse_doc_content(doc)
            if not self._is_table_doc(content_dict):
                continue
            table_name = self._extract_table_name(doc, content_dict)
            if not table_name:
                continue
            description = content_dict.get('description', '')
            if table_name not in tables:
                tables[table_name] = {
                    "name": table_name,
                    "type": content_dict.get('type', 'TABLE'),
                    "description": description,
                    "columns": []
                }
        # Process column documents
        for doc in column_docs:
            content_dict = self._parse_doc_content(doc)
            if not self._is_column_doc(content_dict):
                continue
            table_name = doc.get('metadata', {}).get('name')
            if not table_name or table_name not in tables:
                continue
            columns = self._extract_columns(content_dict)
            for col_name in columns:
                if col_name:
                    tables[table_name]["columns"].append({
                        "name": col_name,
                        "data_type": "STRING",
                        "comment": "",
                        "is_primary_key": False
                    })
        final_schemas = list(tables.values())
        logger.info(f"Constructed {len(final_schemas)} schemas")
        return final_schemas

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
                    ddl = self._build_table_ddl(schema.get("name", ""), schema.get("description", ""), schema.get("columns", []))
                    retrieval_results.append({
                        "table_name": schema.get("name", ""),
                        "table_ddl": ddl
                    })
            for doc in schema_docs:
                content_dict = self._parse_doc_content(doc)
                doc_type = content_dict.get('type')
                if doc_type == "METRIC":
                    retrieval_results.append({
                        "table_name": content_dict.get("name", ""),
                        "table_ddl": self._build_metric_ddl(content_dict)
                    })
                    has_metric = True
                elif doc_type == "VIEW":
                    retrieval_results.append({
                        "table_name": content_dict.get("name", ""),
                        "table_ddl": self._build_view_ddl(content_dict)
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
                # Join DDLs with newlines to create a single string
                #print("db_schemas", db_schemas)
                import json
                schemas_str = json.dumps(db_schemas)
                
                # Create the prompt using the template
                prompt = self._prompt.format(
                    question=query,
                    db_schemas=schemas_str
                )
                logger.info(f"Built prompt with {len(db_schemas)} schemas")
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

    def _construct_retrieval_results(
        self,
        column_selection: Dict,
        db_schemas: List[Dict],
        schema_docs: List[Any]
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
        
        retrieval_results = []
        has_calculated_field = False
        has_metric = False
        
        
        # Process table schemas
        for schema in db_schemas:
            if not isinstance(schema, dict):
                continue
                
            table_name = schema.get("name")
            if not table_name or table_name not in selected_tables:
                continue
                
            # Get selected columns for this table
            
            selected_column_names = selected_tables[table_name]
           
            # Filter the schema's columns to only those selected
            all_columns = schema.get("columns", [])
            filtered_columns = []
            for col in all_columns:
                # Handle stringified dict columns
                if isinstance(col, dict) and isinstance(col.get('name'), str) and col['name'].strip().startswith("{'type': 'COLUMN'"):
                    try:
                        col_info = ast.literal_eval(col['name'])
                        col_name = col_info.get('name', '')
                    except Exception:
                        col_name = col.get('name', '')
                elif isinstance(col, dict):
                    col_name = col.get('name', '')
                else:
                    col_name = str(col)
                if col_name in selected_column_names:
                    filtered_columns.append(col)
            # Build DDL with filtered columns
            ddl = self._build_table_ddl(
                table_name,
                schema.get("description", ""),
                filtered_columns
            )
            #logger.info(f"selected_tables ddl in table retrieval: {ddl}")
            retrieval_results.append({
                "table_name": table_name,
                "table_ddl": ddl
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
                    
                # Only process if table is in selected tables
                if table_name not in selected_tables:
                    continue
                
                if doc_type == "METRIC" or content_dict.get('mdl_type') == "METRIC":
                    retrieval_results.append({
                        "table_name": table_name,
                        "table_ddl": self._build_metric_ddl(content_dict)
                    })
                    has_metric = True
                elif doc_type == "VIEW" or content_dict.get('mdl_type') == "VIEW":
                    retrieval_results.append({
                        "table_name": table_name,
                        "table_ddl": self._build_view_ddl(content_dict)
                    })
            except Exception as e:
                logger.warning(f"Error processing schema document: {str(e)}")
                continue
                
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
