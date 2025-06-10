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
        
        try:
            # Get table descriptions
            table_docs = await self._retrieve_table_descriptions(
                query, tables, project_id
            )
            
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
            
            
            # Construct database schemas
            db_schemas = self._construct_db_schemas(schema_docs,table_docs)
            
            
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
            
            #print("schema_check in run table retrieval table_docs", table_docs)
            #print("schema_check in run table retrieval schema_check", schema_check)
            #print("schema_check in run table retrieval db_schemas", db_schemas)
            #print("schema_check in run table retrieval schema_docs", schema_docs)
            
            # If we need to prune, use LLM to select relevant columns
            if query:
                # Build prompt with schemas
                prompt = self._build_prompt(query, schema_docs, histories)
                # Get column selection from LLM
                column_selection = await self._get_column_selection(prompt)
                print("column_selection", column_selection)
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

    async def _retrieve_table_descriptions(
        self,
        query: str,
        tables: Optional[List[str]],
        project_id: Optional[str]
    ) -> List[Any]:
        """Retrieve table descriptions from the document store."""
        try:
            where = {"type": {"$eq": 'TABLE_DESCRIPTION'}}
            if project_id:
                where = {"$and": [{"project_id": {"$eq": project_id}},{"type":"TABLE_DESCRIPTION"}]}
            
            if query:
                # Get query embedding
                embedding_result = await self._embedder.aembed_query(query)
                # Get results from document store
                if where:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=30,
                        where=where,
                        query_embedding=embedding_result
                    )
                else:
                    results = self.table_store.semantic_search(
                        query=query,
                        k=100,
                        where=where
                    )
            
            if not results:
                return []
            #print("results", results)
            
            # Extract table names
            #table_names = self._extract_table_names(results)
            #print("Extracted table names:", table_names)
           
            # Results are already a list of documents
            return results
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
            where = {"type": {"$eq": 'MODEL'}}
            if project_id:
                where = {"$and": [{"project_id": {"$eq": project_id}}, {"type": {"$eq": 'MODEL'}}]}
            # Perform search with empty table names
            if where:
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
                # Use schema store's semantic search
                tresults = self.schema_store.semantic_search(
                    query="",  # Empty query since we're filtering by table names
                    k=10,
                    where=where
                )
                results.extend(tresults)
                
        if not results:
            return []
        
        return results

    def _construct_db_schemas(self, column_docs: List[Dict], table_docs: List[Dict]) -> List[Dict]:
        """Construct database schemas from retrieved documents."""
        # Dictionary to store tables and their columns
        tables = {}
        
        logger.info(f"Processing {len(table_docs)} table documents and {len(column_docs)} column documents")
        
        # First pass: collect all tables from table docs
        for doc in table_docs:
            try:
                content = doc.get('content', '')
                if not content:
                    continue
                
                # Parse the content string into a dictionary
                try:
                    # Clean up the content string by removing any extra quotes
                    content = content.strip("'").strip('"')
                    content_dict = ast.literal_eval(content)
                except:
                    logger.warning(f"Failed to parse content: {content}")
                    continue
                
                if not isinstance(content_dict, dict):
                    continue
                
                # Handle table definitions
                if content_dict.get('type') in ['TABLE_SCHEMA', 'TABLE_DESCRIPTION', 'MODEL']:
                    table_name = content_dict.get('name')
                    if not table_name:
                        logger.warning("Skipping table as no name found")
                        continue
                        
                    # Extract description from comment if available
                    description = content_dict.get('description', '')
    
                    # Initialize table if not exists
                    if table_name not in tables:
                        tables[table_name] = {
                            "name": table_name,
                            "type": content_dict.get('type', 'TABLE'),
                            "description": description,
                            "columns": []
                        }
                        logger.info(f"Initialized table {table_name} with description: {description}")
                
            except Exception as e:
                logger.warning(f"Error processing table document: {str(e)}")
                continue
        
        #print("column_docs in construct_db_schemas: ", json.dumps(column_docs, indent=2))
        # Second pass: process column documents
        for doc in column_docs:
            try:
                content = doc.get('content', '')
                if not content:
                    continue
                
                # Parse the content string into a dictionary
                try:
                    content = content.strip("'").strip('"')
                    content_dict = ast.literal_eval(content)
                except:
                    logger.warning(f"Failed to parse column content: {content}")
                    continue
                
                if not isinstance(content_dict, dict):
                    continue

                # Handle columns
                if content_dict.get('type') in ['TABLE_COLUMNS', 'COLUMNS']:
                    table_name = doc.get('metadata', {}).get('name')
                    if not table_name:
                        logger.warning("Skipping columns as no table name found in metadata")
                        continue
                    
                    columns = content_dict.get('columns', '')
                    if not columns:
                        continue

                    # Handle both string and list types for columns
                    if isinstance(columns, str):
                        column_names = [col.strip() for col in columns.split(',')]
                    elif isinstance(columns, list):
                        column_names = [col.strip() if isinstance(col, str) else str(col) for col in columns]
                    else:
                        logger.warning(f"Unexpected type for columns: {type(columns)}")
                        continue

                    # Add columns to the table if it exists
                    if table_name in tables:
                        for col_name in column_names:
                            if col_name:
                                tables[table_name]["columns"].append({
                                    "name": col_name,
                                    "data_type": "STRING",
                                    "comment": "",
                                    "is_primary_key": False
                                })
                                logger.debug(f"Added column {col_name} to table {table_name}")
                    else:
                        logger.warning(f"Table {table_name} not found when processing columns")
                
            except Exception as e:
                logger.warning(f"Error processing column document: {str(e)}")
                continue
        
        # Convert tables dictionary to list
        final_schemas = list(tables.values())
        logger.info(f"Constructed {len(final_schemas)} schemas")
        
        return final_schemas
        

    def _check_schemas_without_pruning(
        self,
        db_schemas: List[Dict],
        schema_docs: List[Any]
    ) -> Dict:
        """Check if schemas can be used without pruning."""
        retrieval_results = []
        has_calculated_field = False
        has_metric = False
        
        try:
            # Process table schemas
            for schema in db_schemas:
                if not isinstance(schema, dict):
                    continue
                    
                # Get schema type from metadata or content
                schema_type = schema.get("type")
                if not schema_type:
                    continue
                
                if schema_type == "TABLE" or schema_type == "TABLE_DESCRIPTION" or schema_type == "MODEL":
                    ddl, _has_calculated_field = self._build_table_ddl(schema)
                    retrieval_results.append({
                        "table_name": schema.get("name", ""),
                        "table_ddl": ddl
                    })
                    has_calculated_field = has_calculated_field or _has_calculated_field
            
            # Process metrics and views
            for doc in schema_docs:
                try:
                    # Get content from metadata or parse page_content
                    content = doc.get('content', '')
                    if not content:
                        continue
                        
                    try:
                        content_dict = ast.literal_eval(content)
                    except:
                        continue
                    
                    if not isinstance(content_dict, dict):
                        continue
                        
                    # Get type from content
                    doc_type = content_dict.get('type')
                    if not doc_type:
                        continue
                    
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
                except Exception as e:
                    logger.warning(f"Error processing schema document: {str(e)}")
                    continue
            
            # Check token count
            
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
            
            # Build schema DDLs
            """ schema_ddls = []
            processed_tables = set()  # Track processed tables to avoid duplicates
            
            for schema in db_schemas:
                if not isinstance(schema, dict):
                    logger.warning(f"Invalid schema format: {schema}")
                    continue
                
                try:
                    # Extract table name and content
                    table_name = schema.get('metadata', {}).get('name')
                    if not table_name or table_name in processed_tables:
                        continue
                        
                    # Parse content string into dict
                    content = schema.get('content', '')
                    if not content:
                        continue
                        
                    try:
                        content_dict = ast.literal_eval(content)
                    except:
                        logger.warning(f"Failed to parse content: {content}")
                        continue
                    
                    if not isinstance(content_dict, dict):
                        continue
                    
                    # Build schema string
                    description = content_dict.get('description', '')
                    columns = content_dict.get('columns', '')
                    
                    # Create schema string
                    schema_str = f"-- {description}\nCREATE TABLE {table_name} (\n"
                    if isinstance(columns, str):
                        # Handle string columns
                        col_list = [col.strip() for col in columns.split(',')]
                        schema_str += "  " + ",\n  ".join([f"{col} STRING" for col in col_list]) + "\n);"
                    else:
                        # Handle list/dict columns
                        schema_str += "  id STRING\n);"
                    
                    schema_ddls.append(schema_str)
                    processed_tables.add(table_name)
                        
                except Exception as e:
                    logger.warning(f"Error processing schema: {str(e)}")
                    continue
            
            if not schema_ddls:
                logger.warning("No valid schemas were found")
                return self._prompt.format(
                    question=query,
                    db_schemas="-- No valid schemas found"
                )
            print("db_schemas", db_schemas)
            print("schema_ddls", schema_ddls) """
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
            
            selected_columns = selected_tables[table_name]
            
            # Build DDL with selected columns
            ddl, _has_calculated_field = self._build_table_ddl(
                schema,
                columns=selected_columns
            )
            logger.info(f"selected_tables ddl in table retrieval: {ddl}")
            retrieval_results.append({
                "table_name": table_name,
                "table_ddl": ddl
            })
            has_calculated_field = has_calculated_field or _has_calculated_field
        
        # Process metrics and views
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
                
                if doc_type == "METRIC":
                    retrieval_results.append({
                        "table_name": table_name,
                        "table_ddl": self._build_metric_ddl(content_dict)
                    })
                    has_metric = True
                elif doc_type == "VIEW":
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

    def _build_table_ddl(
        self,
        schema: Dict,
        columns: Optional[set] = None,
        tables: Optional[set] = None
    ) -> tuple[str, bool]:
        """Build table DDL with optional column filtering.
        
        Args:
            schema: Dictionary containing table schema information
            columns: Optional set of column names to include
            tables: Optional set of table names to include
            
        Returns:
            Tuple of (DDL string, has_calculated_field boolean)
        """
        try:
            has_calculated_field = False
            filtered_columns = []
            
            # Get table name and description
            table_name = schema.get("name", "")
            if not table_name:
                return "", False
                
            description = schema.get("description", "")
            
            # Get columns from schema
            schema_columns = schema.get("columns", [])
            print("schema_columns in retrieval", schema_columns)
            # Process columns
            for column in schema_columns:
                if not isinstance(column, dict):
                    continue
                    
                # Parse the column name which is stored as a string
                try:
                    col_info = ast.literal_eval(column.get("name", "{}"))
                    if not isinstance(col_info, dict):
                        continue
                        
                    col_name = col_info.get("name", "")
                    if not col_name:
                        continue
                    
                    # Skip if column filtering is enabled and column not in set
                    if columns is not None and col_name not in columns:
                        continue
                        
                    # Handle nested columns (with dots)
                    if "." in col_name:
                        parent_column = col_name.split(".")[0]
                        if columns is not None and parent_column not in columns:
                            continue
                            
                    # Check for calculated fields
                    if "Calculated Field" in column.get("comment", ""):
                        has_calculated_field = True
                    
                    # Get column type and comment
                    col_type = col_info.get("data_type", "STRING")
                    col_comment = col_info.get("comment", "")
                    
                    # Build column definition
                    col_def = f"{col_name} {col_type}"
                    if col_comment:
                        col_def = f"-- {col_comment}\n{col_def}"
                    
                    filtered_columns.append(col_def)
                    
                except Exception as e:
                    logger.warning(f"Error parsing column info: {str(e)}")
                    continue
            
            # If no valid columns were found, add at least one default column
            if not filtered_columns:
                filtered_columns = ["id STRING"]
            
            # Build table DDL
            table_comment = f"-- {description}\n" if description else ""
            ddl = f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(filtered_columns) + "\n);"
            
            return ddl, has_calculated_field
            
        except Exception as e:
            logger.error(f"Error building table DDL: {str(e)}")
            # Return a minimal valid DDL
            return f"CREATE TABLE {schema.get('name', 'unknown')} (\n  id STRING\n);", False

    def _build_metric_ddl(self, content: Dict) -> str:
        """Build metric DDL."""
        try:
            table_name = content.get("name", "")
            description = content.get("description", "")
            
            # Get columns from content or metadata
            columns = content.get("columns", [])
            if not columns and isinstance(content.get("metadata"), dict):
                columns = content["metadata"].get("columns", [])
            
            # If no columns found, create default metric columns
            if not columns:
                columns = [
                    {"name": "metric_name", "data_type": "STRING", "comment": "Name of the metric"},
                    {"name": "metric_value", "data_type": "FLOAT", "comment": "Value of the metric"},
                    {"name": "dimension", "data_type": "STRING", "comment": "Dimension being measured"},
                    {"name": "timestamp", "data_type": "TIMESTAMP", "comment": "When the metric was calculated"}
                ]
            
            columns_ddl = []
            for column in columns:
                if not isinstance(column, dict):
                    continue
                    
                col_name = column.get("name", "")
                if not col_name:
                    continue
                    
                col_comment = column.get("comment", "")
                col_type = column.get("data_type", "STRING")
                col_def = f"{col_name} {col_type}"
                if col_comment:
                    col_def = f"-- {col_comment}\n{col_def}"
                
                columns_ddl.append(col_def)
            
            # If no valid columns were found, add at least one default column
            if not columns_ddl:
                columns_ddl = ["metric_value FLOAT"]
            
            table_comment = f"-- {description}\n" if description else ""
            return f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(columns_ddl) + "\n);"
            
        except Exception as e:
            logger.error(f"Error building metric DDL: {str(e)}")
            # Return a minimal valid DDL with default columns
            return f"CREATE TABLE {content.get('name', 'unknown')} (\n  metric_value FLOAT\n);"

    def _build_view_ddl(self, content: Dict) -> str:
        """Build view DDL."""
        try:
            view_name = content.get("name", "")
            description = content.get("description", "")
            statement = content.get("statement", "")
            
            view_comment = f"-- {description}\n" if description else ""
            return f"{view_comment}CREATE VIEW {view_name}\nAS {statement}"
            
        except Exception as e:
            logger.error(f"Error building view DDL: {str(e)}")
            return f"CREATE VIEW {content.get('name', 'unknown')} AS SELECT 1;"


   

if __name__ == "__main__":
    # Example usage
    import chromadb
    from langchain_openai import OpenAIEmbeddings
    from app.settings import get_settings
    import os
    os.environ["OPENAI_API_KEY"] = "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"
    settings = get_settings()
    
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
