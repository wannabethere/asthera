"""
Retrieval v2 - Using Unified Storage from Indexing2

This module provides table retrieval capabilities using the unified storage
system from indexing2, offering enhanced document retrieval with business context.

Features:
- Unified document retrieval using StorageManager
- Natural language search for table discovery
- Enhanced schema construction with business context
- Column metadata retrieval with enhanced descriptions
- Support for metrics and views
"""

import logging
import json
import ast
import tiktoken
from typing import Any, Dict, List, Optional

import orjson
from langchain_core.documents import Document as LangchainDocument
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langchain_openai import OpenAIEmbeddings

from app.indexing2.storage_manager import StorageManager
from app.indexing2.natural_language_search import NaturalLanguageSearch
from app.indexing2.document_builder import DocumentBuilder
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_llm, get_doc_store_provider

logger = logging.getLogger("genieml-agents")


# Prompt templates for column selection
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
### Database Schema in chroma stored documents json format  ###

{db_schemas}

### RELATIONSHIP INFORMATION ###
Each table may include a "relationships" field that contains information about how this table relates to other tables. 
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


class TableRetrieval2:
    """Retrieves and processes table information based on queries using unified storage."""
    
    def __init__(
        self,
        document_store: Optional[DocumentChromaStore] = None,
        embedder: Optional[Any] = None,
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
        logger.info("Initializing TableRetrieval2 with unified storage")
        
        self._embedder = embedder or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=get_settings().OPENAI_API_KEY
        )
        self._table_retrieval_size = table_retrieval_size
        self._table_column_retrieval_size = table_column_retrieval_size
        self._allow_using_db_schemas_without_pruning = allow_using_db_schemas_without_pruning
        
        # Use provided document_store or get from provider
        if document_store:
            logger.info("Using provided document store for TableRetrieval2")
            self.table_store = document_store
            self.schema_store = document_store
        else:
            logger.info("Getting document stores from provider")
            document_stores = get_doc_store_provider().stores
            self.table_store = document_stores.get("table_description", document_store)
            self.schema_store = document_stores.get("db_schema", document_store)
        
        # Initialize LLM
        settings = get_settings()
        self._llm = get_llm()
        
        # Set encoding based on model
        if "gpt-4o" in model_name or "gpt-4o-mini" in model_name:
            self._encoding = tiktoken.get_encoding("o200k_base")
        else:
            self._encoding = tiktoken.get_encoding("cl100k_base")
        
        # Initialize unified storage components
        self.storage_manager = StorageManager(
            document_store=self.table_store,
            embedder=self._embedder,
            enable_tfidf=True
        )
        
        self.natural_language_search = NaturalLanguageSearch()
        self.document_builder = DocumentBuilder()
        
        # Initialize prompt template for column selection
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", table_columns_selection_system_prompt),
            ("user", table_columns_selection_user_prompt_template)
        ])
        
        # Initialize output parser
        self._output_parser = JsonOutputParser(pydantic_object=RetrievalResults)
        
        logger.info("TableRetrieval2 initialized successfully with document store: {}".format(
            "provided" if document_store else "from provider"
        ))
    
    async def run(
        self,
        query: str = "",
        tables: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        histories: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Retrieve and process table information using unified storage.
        
        This method always uses LLM-based column selection when tables are found
        to ensure consistent behavior and optimal column selection.
        
        Args:
            query: The query string to search for similar tables
            tables: Optional list of specific tables to retrieve
            project_id: Optional project ID to filter results
            histories: Optional list of previous queries
            
        Returns:
            Dictionary containing retrieval results and metadata
        """
        logger.info(f"Table retrieval v2 is running for project: {project_id}")
        
        try:
            # Try natural language search first
            if query:
                logger.info("Using natural language search for table discovery")
                search_results = await self.storage_manager.search_tables_by_natural_language(
                    query=query,
                    project_id=project_id,
                    top_k=self._table_retrieval_size
                )
                
                logger.info(f"Found {len(search_results)} relevant tables via natural language search")
                
                if search_results:
                    # Convert search results to schema format for column selection
                    db_schemas = self._convert_search_results_to_schemas(search_results)
                    
                    # Use LLM to prune tables and columns based on the user's query
                    logger.info(f"Found {len(search_results)} tables. Using LLM to prune to relevant tables and columns for query.")
                    return await self._run_with_column_selection(query, db_schemas, histories, search_results)
            
            # Fallback to direct ChromaDB semantic search
            logger.info("Falling back to direct ChromaDB semantic search")
            direct_results = await self._search_chromadb_directly(query, tables, project_id)
            
            if direct_results:
                # Convert to schema format
                db_schemas = self._convert_search_results_to_schemas(direct_results)
                
                # Check if we fetched all tables (if so, we fetched all tables and should prune them with LLM)
                # or if we have results from query-based search, still use LLM to prune columns
                logger.info(f"Found {len(direct_results)} tables. Using LLM to prune to relevant tables and columns for query.")
                
                # Always use LLM-based column selection for optimal table retrieval (consistent behavior)
                return await self._run_with_column_selection(query, db_schemas, histories, direct_results)
            
            # If no results found, return empty
            logger.warning("No tables found in database")
            return {
                "retrieval_results": [],
                "has_calculated_field": False,
                "has_metric": False
            }
            
        except Exception as e:
            logger.error(f"Error in table retrieval v2: {str(e)}")
            return {
                "retrieval_results": [],
                "has_calculated_field": False,
                "has_metric": False
            }
    
    async def _search_chromadb_directly(
        self,
        query: str = "",
        tables: Optional[List[str]] = None,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search directly in ChromaDB when natural language search is not available.
        
        If no results are found for the query, fetches ALL tables in the database
        so they can be pruned by the LLM based on the user's query.
        """
        results = []
        
        try:
            # Use the document store for direct semantic search
            if self.table_store:
                logger.info("Searching directly in ChromaDB document store")
                
                # Documents use 'type' field in metadata
                where_clause = {"type": {"$eq": "TABLE_SCHEMA"}}
                if project_id and project_id != "default":
                    where_clause = {"$and": [{"project_id": {"$eq": project_id}}, {"type": {"$eq": "TABLE_SCHEMA"}}]}
                
                logger.info(f"Searching with where clause: {where_clause}")
                
                # Perform semantic search with the query
                chroma_results = self.table_store.semantic_search(
                    query=query,
                    k=self._table_retrieval_size,
                    where=where_clause
                )
                
                logger.info(f"Found {len(chroma_results)} results from query-based ChromaDB search")
                
                # If no results from query-based search, get all tables to prune with LLM
                if not chroma_results:
                    logger.info("No results from query-based search, fetching all tables to prune with LLM based on user's query")
                    chroma_results = self.table_store.semantic_search(
                        query="",  # Empty query to get all tables
                        k=100,  # Get more results
                        where=where_clause
                    )
                    logger.info(f"Found {len(chroma_results)} total tables - LLM will prune these to relevant tables for the query")
                
                # Convert ChromaDB results to our format
                for doc in chroma_results:
                    try:
                        # Unified storage documents have content as a dictionary
                        content = doc.get('content', '{}')
                        metadata = doc.get('metadata', {})
                        
                        # Try to parse content as JSON
                        try:
                            if isinstance(content, str):
                                content_dict = json.loads(content)
                            else:
                                content_dict = content
                        except:
                            content_dict = {}
                        
                        # Extract table information from unified storage format
                        table_name = metadata.get('table_name', content_dict.get('name', ''))
                        display_name = metadata.get('display_name', content_dict.get('properties', {}).get('displayName', ''))
                        description = metadata.get('description', content_dict.get('properties', {}).get('description', ''))
                        business_purpose = content_dict.get('properties', {}).get('businessPurpose', '')
                        
                        # Extract columns and relationships
                        columns = content_dict.get('columns', [])
                        relationships = content_dict.get('relationships', [])
                        
                        # Build result in the format expected by _build_retrieval_results_from_search
                        result = {
                            "table_name": table_name,
                            "display_name": display_name,
                            "description": description,
                            "business_purpose": business_purpose,
                            "metadata": {
                                "columns": columns,
                                "relationships": relationships,
                                "type": "TABLE_SCHEMA"
                            },
                            "relevance_score": 1.0  # Default score for direct search
                        }
                        
                        results.append(result)
                        
                    except Exception as e:
                        logger.warning(f"Error processing ChromaDB result: {str(e)}")
                        continue
                
                logger.info(f"Found {len(results)} results from direct ChromaDB search")
                
        except Exception as e:
            logger.error(f"Error in direct ChromaDB search: {str(e)}")
        
        return results
    
    async def _build_retrieval_results_from_direct_search(
        self,
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build retrieval results from direct ChromaDB search results."""
        # Use the same method as natural language search results
        return await self._build_retrieval_results_from_search(search_results)
    
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
                            content_dict = ast.literal_eval(schema_doc['content'])
                            if isinstance(content_dict, dict):
                                relationships = content_dict.get('relationships', [])
                                enhanced_schema['relationships'] = relationships
                        except:
                            enhanced_schema['relationships'] = []
                    else:
                        # Ensure relationships are included if they exist in the schema
                        if 'relationships' not in enhanced_schema:
                            enhanced_schema['relationships'] = schema_doc.get('relationships', [])
                    
                    enhanced_schemas.append(enhanced_schema)
                
                # Join DDLs with newlines to create a single string
                schemas_str = json.dumps(enhanced_schemas)
                
                # Create the prompt using the template
                prompt = self._prompt.format(
                    question=query,
                    db_schemas=schemas_str
                )
                logger.info(f"Built prompt with {len(enhanced_schemas)} schemas including relationships")
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
    
    def _convert_search_results_to_schemas(self, search_results: List[Dict[str, Any]]) -> List[Dict]:
        """Convert search results to schema format for column selection."""
        schemas = []
        for result in search_results:
            table_name = result.get("table_name", "")
            if not table_name:
                continue
            
            description = result.get("description", "")
            business_purpose = result.get("business_purpose", "")
            columns = result.get("metadata", {}).get("columns", [])
            relationships = result.get("metadata", {}).get("relationships", [])
            
            schema = {
                "name": table_name,
                "description": description or business_purpose,
                "type": "TABLE",
                "columns": columns,
                "relationships": relationships
            }
            schemas.append(schema)
        
        return schemas
    
    def _should_use_column_selection(self, db_schemas: List[Dict]) -> bool:
        """Determine if we should use LLM-based column selection.
        
        NOTE: This method is not currently used as we always call the LLM for column
        selection to ensure consistent behavior. It is kept for potential future
        optimization if needed.
        
        Use column selection if:
        1. We have multiple tables
        2. Total column count exceeds threshold
        """
        if len(db_schemas) <= 1:
            return False
        
        total_columns = sum(len(schema.get("columns", [])) for schema in db_schemas)
        
        # Use column selection if we have many columns across tables
        return total_columns > 50
    
    async def _run_with_column_selection(
        self,
        query: str,
        db_schemas: List[Dict],
        histories: Optional[List[Dict]],
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run retrieval with LLM-based column selection."""
        try:
            # Build prompt with schemas
            prompt = self._build_prompt(query, db_schemas, histories)
            
            # Get column selection from LLM
            column_selection = await self._get_column_selection(prompt)
            logger.info(f"Column selection result: {column_selection}")
            
            # Construct final results with selected columns
            return self._construct_retrieval_results_with_column_selection(
                column_selection, db_schemas, search_results
            )
        except Exception as e:
            logger.error(f"Error in column selection: {str(e)}")
            # Fallback to direct results
            return await self._build_retrieval_results_from_search(search_results)
    
    def _construct_retrieval_results_with_column_selection(
        self,
        column_selection: Dict,
        db_schemas: List[Dict],
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Construct final retrieval results with selected columns.
        
        This method follows the same pattern as retrieval.py:
        1. Parse LLM column selection results
        2. Enhance selection with relationship-based columns
        3. Filter columns from search results
        4. Build DDL using _build_table_ddl() (same as retrieval.py)
        """
        logger.info(f"DEBUG: _construct_retrieval_results_with_column_selection called with column_selection: {column_selection}")
        logger.info(f"DEBUG: search_results count: {len(search_results)}")
        
        if not column_selection or not column_selection.get("results"):
            # Fallback to direct results
            logger.warning(f"DEBUG: Column selection failed or empty, falling back to direct results. column_selection: {column_selection}")
            return {
                "retrieval_results": [],
                "has_calculated_field": False,
                "has_metric": False
            }
        
        # Process column selection from LLM
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
        
        logger.info(f"DEBUG: selected_tables from LLM: {selected_tables}")
        
        # Enhance selection based on relationships (same as retrieval.py)
        enhanced_selection = self._analyze_relationships_for_column_selection(
            selected_tables, db_schemas
        )
        
        logger.info(f"DEBUG: enhanced_selection after relationships: {enhanced_selection}")
        
        retrieval_results = []
        has_calculated_field = False
        has_metric = False
        
        # Build results with selected columns
        for result in search_results:
            table_name = result.get("table_name", "")
            logger.info(f"DEBUG: Processing result for table: {table_name}")
            if not table_name or table_name not in enhanced_selection:
                logger.info(f"DEBUG: Skipping table {table_name} (not in enhanced_selection)")
                continue
            
            # Get all columns from search result
            metadata = result.get("metadata", {})
            all_columns = metadata.get("columns", [])
            logger.info(f"DEBUG: Found {len(all_columns)} columns for table {table_name}")
            
            # Filter to only selected columns
            selected_column_names = enhanced_selection.get(table_name, set())
            filtered_columns = [
                col for col in all_columns
                if col.get("name", "") in selected_column_names
            ]
            logger.info(f"DEBUG: Filtered to {len(filtered_columns)} columns for table {table_name}")
            
            # Check for calculated fields
            for column in filtered_columns:
                if column.get("is_calculated", False):
                    has_calculated_field = True
                    break
            
            # Check for metrics
            if metadata.get("type") == "METRIC":
                has_metric = True
            
            # Build DDL with selected columns using the same method as retrieval.py
            description = result.get("description", "") or result.get("business_purpose", "")
            table_ddl = self._build_table_ddl(
                table_name, description, filtered_columns
            )
            
            logger.info(f"table_ddl in build_table_ddl for {table_name}: {json.dumps(filtered_columns, indent=2)}")
            # Preserve comment field as 'comments' for ddl_chunker compatibility
            for col in filtered_columns:
                if 'comment' in col and 'comments' not in col:
                    col['comments'] = col['comment']
            
            if table_ddl:
                retrieval_results.append({
                    "table_name": table_name,
                    "table_ddl": table_ddl,
                    "relationships": metadata.get("relationships", []),
                    "column_metadata": filtered_columns
                })
        
        return {
            "retrieval_results": retrieval_results,
            "has_calculated_field": has_calculated_field,
            "has_metric": has_metric
        }
    
    async def _build_retrieval_results_from_search(
        self,
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build retrieval results from natural language search results."""
        retrieval_results = []
        has_calculated_field = False
        has_metric = False
        
        for result in search_results:
            try:
                table_name = result.get("table_name", "")
                display_name = result.get("display_name", "")
                description = result.get("description", "")
                business_purpose = result.get("business_purpose", "")
                metadata = result.get("metadata", {})
                
                # Extract columns
                columns = metadata.get("columns", [])
                
                # Build table DDL
                table_ddl = self._build_table_ddl_from_metadata(
                    table_name, description, business_purpose, columns
                )
                
                if not table_ddl:
                    continue
                
                # Check for calculated fields
                for column in columns:
                    if column.get("is_calculated", False):
                        has_calculated_field = True
                        break
                
                # Check for metrics
                if metadata.get("type") == "METRIC":
                    has_metric = True
                
                # Preserve comment field as 'comments' for ddl_chunker compatibility
                for col in columns:
                    if 'comment' in col and 'comments' not in col:
                        col['comments'] = col['comment']
                
                # Build retrieval result
                retrieval_result = {
                    "table_name": table_name,
                    "table_ddl": table_ddl,
                    "relationships": metadata.get("relationships", []),
                    "column_metadata": columns
                }
                
                retrieval_results.append(retrieval_result)
                
            except Exception as e:
                logger.warning(f"Error processing search result: {str(e)}")
                continue
        
        return {
            "retrieval_results": retrieval_results,
            "has_calculated_field": has_calculated_field,
            "has_metric": has_metric
        }
    
    async def _retrieve_specific_tables(
        self,
        tables: List[str],
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve specific tables by name."""
        results = []
        
        for table_name in tables:
            try:
                # Search for the specific table
                search_results = await self.storage_manager.search_tables_by_natural_language(
                    query=table_name,
                    project_id=project_id,
                    top_k=1
                )
                
                if search_results and search_results[0].get("table_name") == table_name:
                    results.append(search_results[0])
                    
            except Exception as e:
                logger.warning(f"Error retrieving table {table_name}: {str(e)}")
                continue
        
        return results
    
    def _build_table_ddl_from_metadata(
        self,
        table_name: str,
        description: str,
        business_purpose: str,
        columns: List[Dict[str, Any]]
    ) -> str:
        """Build table DDL from metadata."""
        try:
            ddl_parts = []
            
            # Add description
            if description:
                ddl_parts.append(f"-- {description}")
            
            # Add business purpose
            if business_purpose:
                ddl_parts.append(f"-- Purpose: {business_purpose}")
            
            # Build CREATE TABLE statement
            ddl_parts.append(f"CREATE TABLE {table_name} (")
            
            # Add column definitions
            for i, column in enumerate(columns):
                col_def = self._build_column_def(column)
                ddl_parts.append(f"  {col_def}{',' if i < len(columns) - 1 else ''}")
            
            ddl_parts.append(");")
            
            return "\n".join(ddl_parts)
            
        except Exception as e:
            logger.error(f"Error building DDL from metadata: {str(e)}")
            return ""
    
    def _build_column_def(self, column: Dict[str, Any]) -> str:
        """Build column definition from column metadata."""
        try:
            name = column.get("name", "")
            data_type = column.get("data_type", column.get("type", "VARCHAR"))
            
            # Get display name or comment
            display_name = column.get("display_name", "")
            description = column.get("business_description", column.get("description", ""))
            
            # Build column definition
            col_def = f"{name} {data_type}"
            
            # Add comment if available
            if display_name or description:
                comment = display_name or description
                col_def += f" -- {comment}"
            
            # Add NOT NULL if required
            if not column.get("is_nullable", True):
                col_def += " NOT NULL"
            
            # Add constraints
            if column.get("is_primary_key", False):
                col_def += " PRIMARY KEY"
            
            return col_def
            
        except Exception as e:
            logger.error(f"Error building column def: {str(e)}")
            return ""
    
    def _check_has_calculated_field(self, columns: List[Dict[str, Any]]) -> bool:
        """Check if any column is a calculated field."""
        for column in columns:
            if column.get("is_calculated", False):
                return True
        return False
    
    def _check_has_metric(self, metadata: Dict[str, Any]) -> bool:
        """Check if this is a metric."""
        return metadata.get("type") == "METRIC"
    
    def _build_table_ddl(self, table_name, description, columns):
        """Build table DDL using the same logic as retrieval.py."""
        try:
            logger.debug(f"Building DDL for table {table_name}")
            logger.debug(f"Description: {description[:100] if description else 'None'}...")
            logger.debug(f"Columns type: {type(columns)}, length: {len(columns) if columns else 0}")
            logger.debug(f"Columns sample: {columns[:2] if columns else 'None'}")
            
            col_defs = self._build_column_defs(columns)
            logger.debug(f"Generated column definitions: {col_defs}")
            
            # Clean description for SQL comment
            if description:
                # Remove problematic characters
                clean_description = description.replace('\n', ' ').replace('\r', ' ').strip()
                # Remove or replace problematic characters that could cause SQL issues
                clean_description = clean_description.replace('(', '[').replace(')', ']')
                # No truncation - keep full description
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
    
    def _build_column_defs(self, columns, default_type="VARCHAR"):
        """Build column definitions using the same logic as retrieval.py."""
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
                    
                    # Get comment and description from direct fields or properties
                    # Priority: 1) pre-formatted 'comment' field, 2) properties, 3) generate from name
                    comment = col.get('comment', '')
                    description = col.get('description', '')
                    
                    # Check if we have a pre-formatted comment (includes newlines and -- markers)
                    has_preformatted_comment = comment and ('--' in comment or '\n' in comment)
                    
                    if not has_preformatted_comment and 'properties' in col and isinstance(col['properties'], dict):
                        # Only extract from properties if we don't have a pre-formatted comment
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
                    # Check if this is a pre-formatted comment with -- markers
                    if ('--' in comment or '\n' in comment):
                        # Extract meaningful text from pre-formatted comment
                        # Look for displayName and description patterns
                        lines = comment.split('\n')
                        extracted_parts = []
                        for line in lines:
                            line = line.strip()
                            if line and line.startswith('--'):
                                line = line.replace('--', '').strip()
                                # Extract displayName: value or description: value
                                if 'displayName:' in line:
                                    extracted_parts.append(line.split('displayName:')[1].strip())
                                elif 'description:' in line and 'displayName:' not in line:
                                    extracted_parts.append(line.split('description:')[1].strip())
                        if extracted_parts:
                            comment_parts.extend(extracted_parts)
                        else:
                            # Fallback: just clean and use
                            clean_comment = comment.strip().replace('\n', ' ').replace('\r', ' ').replace('--', '').strip()
                            if clean_comment:
                                comment_parts.append(clean_comment)
                    else:
                        clean_comment = comment.strip().replace('\n', ' ').replace('\r', ' ')
                        if clean_comment:
                            comment_parts.append(clean_comment)
                
                if description:
                    clean_description = description.strip().replace('\n', ' ').replace('\r', ' ')
                    if clean_description:
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


# Test function
async def main():
    """Test the TableRetrieval2 functionality."""
    try:
        from langchain_openai import OpenAIEmbeddings
        from app.settings import get_settings
        
        settings = get_settings()
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        retrieval = TableRetrieval2(
            embedder=embeddings,
            model_name="gpt-4o-mini"
        )
        
        query = "Show me sales data"
        result = await retrieval.run(query, project_id="test_project")
        
        logger.info(f"Retrieval result: {result}")
        
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

