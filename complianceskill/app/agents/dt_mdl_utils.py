"""
MDL Utilities for Detection & Triage Workflow

Utility functions for MDL (Metadata Layer) operations, including column pruning
and schema manipulation.
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def prune_columns_from_schemas(
    schemas: List[Dict[str, Any]],
    user_query: str,
    reasoning: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Prune columns from MDL schemas based on user query and optional reasoning.
    
    Uses LLM to select only relevant columns from each schema, reducing token usage
    and improving focus for downstream calculation planning.
    
    This function is similar to TableRetrieval._get_column_selection() but works
    directly with MDL schema dictionaries rather than document store results.
    
    Args:
        schemas: List of schema dicts with table_name, table_ddl, column_metadata, etc.
        user_query: User's natural language query
        reasoning: Optional reasoning context (e.g., from SQL reasoning step)
    
    Returns:
        List of pruned schemas with only relevant columns. Returns original schemas
        on error or if no columns are selected.
    """
    if not schemas:
        return schemas
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        
        # Column selection system prompt (similar to TableRetrieval)
        system_prompt = """### TASK ###
You are a highly skilled data analyst. Your goal is to examine the provided database schema, interpret the posed question, and identify the specific columns from the relevant tables required to construct an accurate SQL query.

### INSTRUCTIONS ###
1. Carefully analyze the schema and identify the essential tables and columns needed to answer the question.
1.1 ***Please select as many columns as possible even if they might not be fully relevant to the question. There are other downstream agents that will filter out the irrelevant columns.***
1.2 ***IMPORTANT: Consider relationships between tables when selecting columns. If a table has relationships with other tables, consider including relevant columns from related tables that might be needed for joins.***

2. For each table, provide a clear and concise reasoning for why specific columns are selected.

3. List each reason as part of a step-by-step chain of thought, justifying the inclusion of each column.

4. Final chosen columns must be only column names, don't prefix it with table names.

5. When analyzing relationships, consider the join type and the join condition to understand which columns are likely to be used in joins.

### FINAL ANSWER FORMAT ###

Please provide your response as a JSON object, structured as follows:
{{
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
        ...
    ]
}}

### ADDITIONAL NOTES ###
- Each table key must list only the columns relevant to answering the question.
- Provide a reasoning list (`chain_of_thought_reasoning`) for each table, explaining why each column is necessary.
- Provide the reason of selecting the table in (`table_selection_reason`) for each table.
- Be logical, concise, and ensure the output strictly follows the required JSON format.
- Use table name used in the "Create Table" statement, don't use "alias".
- Match Column names with the definition in the "Create Table" statement.
- Match Table names with the definition in the "Create Table" statement.
** Please always response with JSON Format thinking like JSON Expert otherwise all my downstream application will fail.
** dont add any json tag or additional ``` to the response. This is very important."""
        
        # Format schemas for prompt
        schemas_text = ""
        for schema in schemas:
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            desc = schema.get("description", "")
            col_meta = schema.get("column_metadata", [])
            
            schemas_text += f"\n### Table: {table_name} ###\n"
            if desc:
                schemas_text += f"Description: {desc}\n"
            if table_ddl:
                schemas_text += f"{table_ddl}\n"
            if col_meta and isinstance(col_meta, list) and len(col_meta) > 0:
                schemas_text += "Columns:\n"
                for c in col_meta:
                    if isinstance(c, dict):
                        name = c.get("column_name") or c.get("name", "")
                        typ = c.get("type") or c.get("data_type", "")
                        d = (c.get("description") or c.get("display_name", "")) or ""
                        schemas_text += f"  - {name}" + (f" ({typ})" if typ else "") + (f": {d}" if d else "") + "\n"
                    else:
                        schemas_text += f"  - {c}\n"
            schemas_text += "\n"
        
        # Build user prompt
        reasoning_section = ""
        if reasoning:
            reasoning_section = f"\n### REASONING CONTEXT ###\n{reasoning}\n"
        
        user_prompt = f"""### Database Schema (Markdown Format) ###

{schemas_text}
{reasoning_section}
### USER QUESTION ###
{user_query}

### TABLE SELECTION STRATEGY ###
1. Analyze the user question to understand the specific information being requested.
2. Select tables that are relevant to answering the question.
3. Once tables are identified, select columns from those tables that are needed to answer the question.
"""
        
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt),
        ])
        chain = prompt | llm
        
        # Run async LLM call
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Event loop is already running - use ThreadPoolExecutor to run in separate thread
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    # With nest_asyncio, we can use run_until_complete even if loop is running
                    response = loop.run_until_complete(chain.ainvoke({}))
                except (ImportError, RuntimeError):
                    # nest_asyncio not available or failed, use ThreadPoolExecutor
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, chain.ainvoke({}))
                        response = future.result(timeout=300)  # 5 minute timeout
            else:
                response = loop.run_until_complete(chain.ainvoke({}))
        except RuntimeError:
            # No event loop exists, create new one
            response = asyncio.run(chain.ainvoke({}))
        
        # Parse response
        content = response.content.strip() if hasattr(response, "content") else str(response)
        
        # Handle markdown code blocks
        if content.startswith('```json'):
            first_block = content.find('```')
            last_block = content.rfind('```')
            if first_block >= 0 and last_block > first_block:
                content = content[first_block:last_block]
                content = content.replace('```json', '').replace('```', '').strip()
        
        # Parse JSON
        try:
            column_selection = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON object
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    column_selection = json.loads(content[start_idx:end_idx])
                except json.JSONDecodeError:
                    logger.warning("Failed to parse column selection response, returning original schemas")
                    return schemas
            else:
                logger.warning("No valid JSON found in column selection response, returning original schemas")
                return schemas
        
        # Build mapping of table_name -> selected columns
        selected_columns_map = {}
        for result in column_selection.get("results", []):
            table_name = result.get("table_name", "")
            if not table_name:
                continue
            table_contents = result.get("table_contents", {})
            columns = table_contents.get("columns", []) if isinstance(table_contents, dict) else []
            if columns:
                selected_columns_map[table_name] = set(columns)
        
        if not selected_columns_map:
            logger.warning("No columns selected by LLM, returning original schemas")
            return schemas
        
        # Prune columns from schemas
        pruned_schemas = []
        for schema in schemas:
            table_name = schema.get("table_name", "")
            selected_columns = selected_columns_map.get(table_name)
            
            if not selected_columns:
                # No selection for this table - keep all columns
                logger.info(f"No column selection for table '{table_name}', keeping all columns")
                pruned_schemas.append(schema)
                continue
            
            # Create pruned schema
            pruned_schema = schema.copy()
            
            # Filter column_metadata
            original_cols = schema.get("column_metadata", [])
            if original_cols:
                pruned_cols = []
                for col in original_cols:
                    if isinstance(col, dict):
                        col_name = col.get("column_name") or col.get("name", "")
                        if col_name in selected_columns:
                            pruned_cols.append(col)
                    elif isinstance(col, str) and col in selected_columns:
                        pruned_cols.append(col)
                pruned_schema["column_metadata"] = pruned_cols
                logger.info(f"Pruned table '{table_name}': {len(original_cols)} -> {len(pruned_cols)} columns")
            
            # Optionally prune DDL (keep for now, calculation planner may need it)
            # The DDL contains all columns, but column_metadata is what's used for planning
            
            pruned_schemas.append(pruned_schema)
        
        logger.info(f"Column pruning complete: {len(schemas)} schemas, {len(selected_columns_map)} tables pruned")
        return pruned_schemas
        
    except Exception as e:
        logger.error(f"Column pruning failed: {e}", exc_info=True)
        # Return original schemas on error
        logger.warning("Returning original schemas due to pruning error")
        return schemas
