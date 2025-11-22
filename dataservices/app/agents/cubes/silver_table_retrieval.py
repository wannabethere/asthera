"""
Silver Table Retrieval Agent

This module provides retrieval functionality for silver tables, similar to retrieval.py
but specifically designed for querying and selecting silver tables to build data marts.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser

from app.storage.documents import DocumentChromaStore
from app.core.dependencies import get_llm, get_doc_store_provider

logger = logging.getLogger("genieml-agents")


def log_llm_call(stage: str, messages: List, response: Any, max_response_length: int = 500):
    """
    Log LLM request and response for debugging.
    
    Args:
        stage: Name of the stage/operation
        messages: List of messages sent to LLM
        response: LLM response object
        max_response_length: Maximum length of response to log (truncate if longer)
    """
    system_msg = next((msg.content for msg in messages if isinstance(msg, SystemMessage)), None)
    user_msg = next((msg.content for msg in messages if isinstance(msg, HumanMessage)), None)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🤖 LLM CALL: {stage}")
    logger.info(f"{'='*80}")
    
    if system_msg:
        logger.debug(f"System Message: {system_msg[:200]}...")
    
    if user_msg:
        user_preview = user_msg[:300] + "..." if len(user_msg) > 300 else user_msg
        logger.info(f"User Prompt Preview: {user_preview}")
    
    if hasattr(response, 'content'):
        response_content = response.content
        if len(response_content) > max_response_length:
            logger.info(f"LLM Response ({len(response_content)} chars, truncated):\n{response_content[:max_response_length]}...")
            logger.debug(f"Full Response:\n{response_content}")
        else:
            logger.info(f"LLM Response ({len(response_content)} chars):\n{response_content}")
    else:
        logger.info(f"LLM Response: {response}")
    
    logger.info(f"{'='*80}\n")


class SilverTableMatch(BaseModel):
    """A matching silver table with relevance information."""
    table_name: str
    relevance_score: float = Field(default=0.0)
    selection_reason: str
    columns: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)


class SilverTableRetrievalResults(BaseModel):
    """Results from silver table retrieval."""
    tables: List[SilverTableMatch]
    query: str
    total_tables_found: int


class SilverTableRetrieval:
    """Retrieves relevant silver tables based on business goals and queries.
    
    Uses a two-stage planner approach:
    1. Stage 1 (Planner): Find candidate tables using semantic search on table descriptions
    2. Stage 2 (Detailed Selection): Analyze full table descriptions to select tables and columns
    """
    
    def __init__(
        self,
        document_store: Optional[DocumentChromaStore] = None,
        embedder: Optional[Any] = None,
        model_name: str = "gpt-4o-mini",
        max_tables: int = 10,
        candidate_table_limit: int = 20
    ):
        """Initialize the silver table retrieval agent.
        
        Args:
            document_store: Optional document store for semantic search
            embedder: Optional text embedder
            model_name: LLM model name
            max_tables: Maximum number of tables to retrieve in final result
            candidate_table_limit: Maximum number of candidate tables to analyze in stage 2
        """
        self.model_name = model_name
        self.max_tables = max_tables
        self.candidate_table_limit = candidate_table_limit
        self._llm = get_llm()
        
        # Initialize document stores if available
        if document_store:
            self.table_store = document_store
        else:
            try:
                self.table_store = get_doc_store_provider().get_store("silver_table_descriptions")
            except:
                self.table_store = None
        
        self.schema_store = None
        try:
            self.schema_store = get_doc_store_provider().get_store("silver_db_schema")
        except:
            pass
        
        self._output_parser = JsonOutputParser(pydantic_object=SilverTableRetrievalResults)
    
    async def retrieve_silver_tables(
        self,
        query: str,
        business_goals: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[str] = None,
        available_silver_tables: Optional[List[Dict[str, Any]]] = None
    ) -> SilverTableRetrievalResults:
        """
        Retrieve relevant silver tables based on query and business goals.
        
        Uses a two-stage planner approach:
        1. Stage 1: Find candidate tables using semantic search on table descriptions
        2. Stage 2: Analyze full table descriptions to select tables and identify columns
        
        Args:
            query: Natural language query describing the data mart goal
            business_goals: Optional list of business goals
            project_id: Optional project ID for filtering
            available_silver_tables: Optional list of available silver table metadata
            
        Returns:
            SilverTableRetrievalResults with matched tables and columns
        """
        logger.info(f"Retrieving silver tables for query: {query}")
        
        # If we have available_silver_tables, use two-stage planner approach
        if available_silver_tables:
            return await self._two_stage_planner_retrieval(
                query=query,
                business_goals=business_goals,
                available_tables=available_silver_tables
            )
        
        # Otherwise, try to use document store with two-stage approach
        if self.table_store:
            return await self._two_stage_document_store_retrieval(
                query=query,
                business_goals=business_goals,
                project_id=project_id
            )
        
        # Fallback: return empty results
        logger.warning("No document store or available tables provided, returning empty results")
        return SilverTableRetrievalResults(
            tables=[],
            query=query,
            total_tables_found=0
        )
    
    async def _two_stage_planner_retrieval(
        self,
        query: str,
        business_goals: Optional[List[Dict[str, Any]]],
        available_tables: List[Dict[str, Any]]
    ) -> SilverTableRetrievalResults:
        """
        Two-stage planner retrieval:
        Stage 1: Find candidate tables using table descriptions only
        Stage 2: Analyze full table descriptions to select tables and columns
        """
        logger.info(f"Stage 1: Finding candidate tables from {len(available_tables)} available tables")
        
        # Stage 1: Find candidate tables using table descriptions only
        candidate_tables = await self._stage1_find_candidate_tables(
            query=query,
            business_goals=business_goals,
            available_tables=available_tables
        )
        
        logger.info(f"Stage 1 complete: Found {len(candidate_tables)} candidate tables")
        
        if not candidate_tables:
            logger.warning("No candidate tables found in stage 1")
            return SilverTableRetrievalResults(
                tables=[],
                query=query,
                total_tables_found=0
            )
        
        # Stage 2: Analyze full table descriptions to select tables and identify columns
        logger.info(f"Stage 2: Analyzing {len(candidate_tables)} candidate tables with full descriptions")
        return await self._stage2_select_tables_and_columns(
            query=query,
            business_goals=business_goals,
            candidate_tables=candidate_tables
        )
    
    async def _stage1_find_candidate_tables(
        self,
        query: str,
        business_goals: Optional[List[Dict[str, Any]]],
        available_tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Stage 1: Find candidate tables using table descriptions only (no columns)."""
        
        system_prompt = """You are a data architect expert at quickly identifying relevant silver tables
        based on table names and descriptions only. Your goal is to filter down to the most relevant
        candidate tables that might be needed to answer the query or achieve the business goal.
        
        Consider:
        1. Table names (keywords matching)
        2. Table descriptions
        3. Business domain alignment
        4. Business use cases
        
        Return a JSON array of table names (not full table objects) that are candidates for further analysis.
        Limit to the top most relevant tables."""
        
        # Format only table names and descriptions (no columns) for efficiency
        tables_summary = []
        for table in available_tables:
            table_summary = {
                "name": table.get("table_name", ""),
                "description": table.get("description", ""),
                "domain": table.get("domain_description", ""),
                "business_use_case": table.get("business_use_case", "")
            }
            tables_summary.append(table_summary)
        
        goals_text = ""
        if business_goals:
            goals_text = "\n".join([
                f"- {goal.get('goal_name', '')}: {goal.get('description', '')}"
                for goal in business_goals
            ])
        
        user_prompt = f"""Find candidate silver tables for this query (return only table names):

Query: {query}

Business Goals:
{goals_text}

Available Silver Tables (names and descriptions only):
{json.dumps(tables_summary, indent=2)}

Return JSON array of candidate table names (limit to top {self.candidate_table_limit}):
[
    "table_name1",
    "table_name2",
    ...
]"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self._llm.invoke(messages)
            log_llm_call("Stage 1: Candidate Table Selection", messages, response)
            
            # Parse response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            candidate_table_names = json.loads(content)
            if not isinstance(candidate_table_names, list):
                candidate_table_names = []
            
            # Limit to candidate_table_limit
            candidate_table_names = candidate_table_names[:self.candidate_table_limit]
            
            # Get full table objects for candidate tables
            candidate_tables = []
            table_name_map = {table.get("table_name", ""): table for table in available_tables}
            
            for table_name in candidate_table_names:
                if table_name in table_name_map:
                    candidate_tables.append(table_name_map[table_name])
            
            logger.info(f"Stage 1: Selected {len(candidate_tables)} candidate tables: {candidate_table_names}")
            return candidate_tables
            
        except Exception as e:
            logger.error(f"Error in stage 1 candidate table selection: {str(e)}")
            # Fallback: return first N tables
            return available_tables[:self.candidate_table_limit]
    
    async def _stage2_select_tables_and_columns(
        self,
        query: str,
        business_goals: Optional[List[Dict[str, Any]]],
        candidate_tables: List[Dict[str, Any]]
    ) -> SilverTableRetrievalResults:
        """Stage 2: Analyze full table descriptions to select tables and identify columns."""
        
        system_prompt = """You are a data architect expert at selecting relevant silver tables and columns
        to build data marts. Analyze the full table descriptions (including columns, relationships, data types)
        to identify which tables and specific columns are needed to answer the query or achieve the goal.
        
        Consider:
        1. Table names and descriptions
        2. Column names, types, and descriptions
        3. Relationships between tables
        4. Business domain alignment
        5. Data grain and aggregation levels
        6. Join requirements based on relationships
        
        Return a JSON object with selected tables, relevance scores, reasoning, and specific columns needed."""
        
        # Format full table information including columns
        tables_info = []
        for table in candidate_tables:
            table_info = {
                "name": table.get("table_name", ""),
                "description": table.get("description", ""),
                "columns": [
                    {
                        "name": col.get("name", ""),
                        "type": col.get("data_type", col.get("type", "")),
                        "description": col.get("description", "")
                    }
                    for col in table.get("columns", [])
                ],
                "domain": table.get("domain_description", ""),
                "business_use_case": table.get("business_use_case", ""),
                "relationships": table.get("relationships", [])
            }
            tables_info.append(table_info)
        
        goals_text = ""
        if business_goals:
            goals_text = "\n".join([
                f"- {goal.get('goal_name', '')}: {goal.get('description', '')}"
                for goal in business_goals
            ])
        
        user_prompt = f"""Select relevant silver tables and specific columns for this query and business goals:

Query: {query}

Business Goals:
{goals_text}

Candidate Silver Tables (with full column details):
{json.dumps(tables_info, indent=2)}

Return JSON with this structure:
{{
    "tables": [
        {{
            "table_name": "table_name",
            "relevance_score": 0.0-1.0,
            "selection_reason": "Why this table is relevant",
            "columns": ["column1", "column2", ...],
            "column_selection_reasoning": {{
                "column1": "Why column1 is needed",
                "column2": "Why column2 is needed"
            }},
            "relationships": []
        }}
    ],
    "query": "{query}",
    "total_tables_found": <number>
}}"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self._llm.invoke(messages)
            log_llm_call("Stage 2: Table and Column Selection", messages, response, max_response_length=1000)
            
            # Parse response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            result = json.loads(content)
            
            # Convert to Pydantic models
            tables = []
            for table_data in result.get("tables", []):
                # Limit to max_tables
                if len(tables) >= self.max_tables:
                    break
                
                tables.append(SilverTableMatch(
                    table_name=table_data.get("table_name", ""),
                    relevance_score=table_data.get("relevance_score", 0.0),
                    selection_reason=table_data.get("selection_reason", ""),
                    columns=table_data.get("columns", []),
                    relationships=table_data.get("relationships", [])
                ))
            
            logger.info(f"Stage 2: Selected {len(tables)} tables with {sum(len(t.columns) for t in tables)} total columns")
            
            return SilverTableRetrievalResults(
                tables=tables,
                query=query,
                total_tables_found=len(tables)
            )
            
        except Exception as e:
            logger.error(f"Error in stage 2 table and column selection: {str(e)}")
            return SilverTableRetrievalResults(
                tables=[],
                query=query,
                total_tables_found=0
            )
    
    async def _two_stage_document_store_retrieval(
        self,
        query: str,
        business_goals: Optional[List[Dict[str, Any]]],
        project_id: Optional[str]
    ) -> SilverTableRetrievalResults:
        """
        Two-stage retrieval from document store:
        Stage 1: Find candidate tables using semantic search on table descriptions
        Stage 2: Get full table descriptions and analyze to select tables and columns
        """
        logger.info(f"Stage 1: Finding candidate tables from document store")
        
        try:
            where_clause = {"type": {"$eq": "SILVER_TABLE_DESCRIPTION"}}
            if project_id and project_id != "default":
                where_clause = {
                    "$and": [
                        {"project_id": {"$eq": project_id}},
                        {"type": {"$eq": "SILVER_TABLE_DESCRIPTION"}}
                    ]
                }
            
            # Stage 1: Perform semantic search to find candidate tables
            # Use candidate_table_limit to get more candidates for stage 2 analysis
            candidate_results = self.table_store.semantic_search(
                query=query,
                k=self.candidate_table_limit,
                where=where_clause
            )
            
            logger.info(f"Stage 1: Found {len(candidate_results)} candidate tables from document store")
            
            if not candidate_results:
                return SilverTableRetrievalResults(
                    tables=[],
                    query=query,
                    total_tables_found=0
                )
            
            # Stage 2: Get full table descriptions and analyze
            candidate_tables = []
            for result in candidate_results:
                try:
                    content = result.get('content', '')
                    if isinstance(content, str):
                        content_dict = json.loads(content) if content.startswith('{') else {}
                    else:
                        content_dict = content
                    
                    table_name = content_dict.get('name', '') or result.get('metadata', {}).get('name', '')
                    if table_name:
                        candidate_tables.append({
                            "table_name": table_name,
                            "description": content_dict.get('description', ''),
                            "columns": content_dict.get('columns', []),
                            "domain_description": content_dict.get('domain', ''),
                            "business_use_case": content_dict.get('business_use_case', ''),
                            "relationships": content_dict.get('relationships', []),
                            "relevance_score": result.get('score', 0.0)
                        })
                except Exception as e:
                    logger.warning(f"Error processing candidate result: {str(e)}")
                    continue
            
            # Now use stage 2 to select tables and columns
            logger.info(f"Stage 2: Analyzing {len(candidate_tables)} candidate tables with full descriptions")
            return await self._stage2_select_tables_and_columns(
                query=query,
                business_goals=business_goals,
                candidate_tables=candidate_tables
            )
            
        except Exception as e:
            logger.error(f"Error in two-stage document store retrieval: {str(e)}")
            return SilverTableRetrievalResults(
                tables=[],
                query=query,
                total_tables_found=0
            )

