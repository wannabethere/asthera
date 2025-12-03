import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import datetime
import orjson
import json
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.schema import AIMessage, HumanMessage, SystemMessage

from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent, SQLOperationType
from app.core.engine import Engine
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.agents.nodes.sql.utils.sql_prompts import (
    Configuration,
    SQL_GENERATION_MODEL_KWARGS,
    TEXT_TO_SQL_RULES,
    construct_instructions,
    sql_generation_system_prompt,
    calculated_field_instructions,
    metric_instructions
)
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger("lexy-ai-service")


class TransformType(Enum):
    """Types of transformations that can be applied"""
    CALCULATED_COLUMN = "calculated_column"
    METRIC = "metric"
    COLUMN_TRANSFORMATION = "column_transformation"
    AGGREGATION_TRANSFORMATION = "aggregation_transformation"


class TransformSQLRAGAgent(SQLRAGAgent):
    """
    Specialized SQL RAG Agent for generating dynamic column transformations
    
    This agent handles:
    - Creating calculated columns
    - Generating metric-based transformations
    - Applying column transformations
    - Using knowledge, instructions, SQL functions, and examples
    """
    
    def __init__(
        self,
        llm,
        engine: Engine,
        embeddings=None,
        max_iterations: int = 5,
        document_store_provider: DocumentStoreProvider = None,
        retrieval_helper: RetrievalHelper = None,
        **kwargs
    ):
        """Initialize Transform SQL RAG Agent"""
        super().__init__(
            llm=llm,
            engine=engine,
            embeddings=embeddings,
            max_iterations=max_iterations,
            document_store_provider=document_store_provider,
            retrieval_helper=retrieval_helper,
            **kwargs
        )
        
        # Transform-specific cache
        self._transform_knowledge_cache = {}
        self._sql_functions_cache = {}
    
    async def _generate_transform_reasoning(
        self,
        query: str,
        knowledge: Optional[List[str]] = None,
        contexts: List[str] = None,
        language: str = "English",
        project_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate reasoning plan for transform operations
        
        This determines:
        1. If calculated columns need to be created
        2. If it's a metric type transformation
        3. If it's a column transformation
        4. What SQL functions/examples to use
        
        Args:
            query: Natural language question
            knowledge: Additional knowledge context
            contexts: Schema contexts
            language: Language for reasoning
            unified_context: Pre-retrieved unified context (optional)
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with reasoning plan including:
            - transform_type: Type of transformation needed
            - calculated_columns: List of calculated columns to create
            - metric_info: Metric information if applicable
            - transformation_steps: Step-by-step transformation plan
            - sql_functions_needed: SQL functions required
            - examples_to_use: Relevant examples
        """
        try:
            # Get project_id from parameter or kwargs
            project_id = project_id or kwargs.get("project_id")
            if not project_id:
                raise ValueError("project_id is required")
            
            # Use unified context if provided, otherwise retrieve
            unified_context = kwargs.get("unified_context")
            if unified_context:
                transform_metadata = {
                    "instructions": unified_context.get("instructions", []),
                    "sql_pairs": unified_context.get("sql_pairs", []),
                    "calculated_fields": unified_context.get("calculated_fields", []),
                    "sql_functions": unified_context.get("sql_functions", []),  # Use SQL functions from unified context
                    "knowledge": unified_context.get("knowledge", knowledge or [])
                }
                contexts = unified_context.get("schema_contexts", contexts or [])
            else:
                # Fallback: retrieve if not provided
                transform_metadata = await self._retrieve_transform_metadata(
                    query=query,
                    project_id=project_id,
                    knowledge=knowledge or []
                )
            
            # Build reasoning prompt
            reasoning_prompt = self._build_transform_reasoning_prompt(
                query=query,
                knowledge=transform_metadata.get("knowledge", knowledge or []),
                contexts=contexts or [],
                language=language,
                transform_metadata=transform_metadata,
                **kwargs
            )
            
            # Generate reasoning using LLM
            system_prompt = self._get_transform_reasoning_system_prompt()
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=reasoning_prompt)
            ]
            
            prompt = ChatPromptTemplate.from_messages(messages)
            chain = prompt | self.llm
            
            result = await chain.ainvoke(
                {
                    "system_prompt": system_prompt,
                    "user_prompt": reasoning_prompt
                },
                **SQL_GENERATION_MODEL_KWARGS
            )
            
            # Extract reasoning from result
            reasoning_content = result.content if hasattr(result, 'content') else str(result)
            
            # Parse reasoning to extract structured information
            reasoning_plan = self._parse_transform_reasoning(reasoning_content, transform_metadata)
            
            logger.info(f"Generated transform reasoning plan: {reasoning_plan.get('transform_type')}")
            
            return {
                "success": True,
                "reasoning": reasoning_content,
                "reasoning_plan": reasoning_plan,
                "metadata": transform_metadata
            }
            
        except Exception as e:
            logger.error(f"Error generating transform reasoning: {e}")
            return {
                "success": False,
                "reasoning": "",
                "reasoning_plan": {},
                "error": str(e)
            }
    
    async def _retrieve_transform_metadata(
        self,
        query: str,
        project_id: str,
        knowledge: List[str] = None,
        unified_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Retrieve metadata specific to transform operations.
        Uses unified_context if provided to avoid duplicate retrievals.
        
        Args:
            query: User query
            project_id: Project ID
            knowledge: Additional knowledge
            unified_context: Pre-retrieved unified context (optional)
            
        Returns:
            Dictionary with transform metadata
        """
        try:
            # If unified context is provided, use it (avoids duplicate retrievals)
            if unified_context:
                return {
                    "instructions": unified_context.get("instructions", []),
                    "sql_pairs": unified_context.get("sql_pairs", []),
                    "calculated_fields": unified_context.get("calculated_fields", []),
                    "sql_functions": await self._retrieve_sql_functions(query, project_id),
                    "knowledge": unified_context.get("knowledge", knowledge or [])
                }
            
            # Otherwise, retrieve metadata (fallback)
            # Use cached metadata from parent class if available
            metadata = await self._retrieve_and_cache_metadata(
                query=query,
                project_id=project_id,
                similarity_threshold=0.3,
                max_retrieval_size=5,
                top_k=5
            )
            
            # Retrieve calculated fields (metrics removed for now)
            calculated_fields = await self._retrieve_calculated_fields(
                query=query,
                project_id=project_id
            )
            
            # Retrieve SQL functions
            sql_functions = await self._retrieve_sql_functions(
                query=query,
                project_id=project_id
            )
            
            return {
                "instructions": metadata.get("instructions", []),
                "sql_pairs": metadata.get("sql_pairs", []),
                "calculated_fields": calculated_fields,
                "sql_functions": sql_functions,
                "knowledge": knowledge or []
            }
            
        except Exception as e:
            logger.error(f"Error retrieving transform metadata: {e}")
            return {
                "instructions": [],
                "sql_pairs": [],
                "calculated_fields": [],
                "sql_functions": [],
                "knowledge": knowledge or []
            }
    
    async def _retrieve_calculated_fields(
        self,
        query: str,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve calculated fields from the knowledge base"""
        # TODO: Implement retrieval of calculated fields
        # This might involve querying a specific collection or metadata store
        return []
    
    async def _retrieve_sql_functions(
        self,
        query: str,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant SQL functions based on the query"""
        # TODO: Implement retrieval of SQL functions
        # This might involve querying a functions knowledge base
        return []
    
    def _get_transform_reasoning_system_prompt(self) -> str:
        """Get system prompt for transform reasoning generation"""
        return f"""
### TASK ###
You are an expert SQL data analyst specializing in dynamic column transformations and calculated fields.
You analyze user questions to determine what type of transformation is needed and create a detailed reasoning plan.

{calculated_field_instructions}

{metric_instructions}

### TRANSFORMATION TYPES ###
1. **CALCULATED_COLUMN**: Creating new columns from existing columns using calculations
   - Examples: "revenue_per_customer", "age_from_birthdate", "full_name_from_first_last"
   - Use the calculated field instructions above to understand how to work with calculated fields
   
2. **METRIC**: Creating metric-based aggregations with dimensions and measures
   - Examples: "total_sales_by_region", "average_order_value_by_month"
   - Use the metric instructions above to understand how to work with metrics
   
3. **COLUMN_TRANSFORMATION**: Transforming existing columns (formatting, type conversion, etc.)
   - Examples: "format_date", "convert_currency", "normalize_text"
   
4. **AGGREGATION_TRANSFORMATION**: Creating aggregations with transformations
   - Examples: "sum_with_conditions", "weighted_average", "conditional_count"

### REASONING PLAN REQUIREMENTS ###
Your reasoning plan must identify:
1. **Transform Type**: Which type of transformation is needed
2. **Source Columns**: Which existing columns will be used
3. **Target Columns**: What new columns/expressions need to be created
4. **Calculation Logic**: Step-by-step calculation approach
5. **SQL Functions**: Which SQL functions will be needed
6. **Dependencies**: Any dependencies between transformations
7. **Metric Structure**: If metric type, identify dimensions and measures

### OUTPUT FORMAT ###
Provide a structured reasoning plan in JSON format:
{{
    "transform_type": "<CALCULATED_COLUMN|METRIC|COLUMN_TRANSFORMATION|AGGREGATION_TRANSFORMATION>",
    "source_columns": ["column1", "column2"],
    "target_columns": ["new_column1", "new_column2"],
    "calculation_steps": [
        {{
            "step": 1,
            "description": "Step description",
            "sql_expression": "SQL expression for this step"
        }}
    ],
    "sql_functions_needed": ["SUM", "CASE", "DATE_TRUNC"],
    "is_metric": true/false,
    "metric_dimensions": ["dimension1", "dimension2"] if is_metric,
    "metric_measures": ["measure1", "measure2"] if is_metric
}}
"""
    
    def _build_transform_reasoning_prompt(
        self,
        query: str,
        knowledge: List[str],
        contexts: List[str],
        language: str,
        transform_metadata: Dict[str, Any],
        **kwargs
    ) -> str:
        """Build the prompt for transform reasoning generation"""
        
        project_id = kwargs.get("project_id")
        config = Configuration(**kwargs.get("configuration", {}))
        
        # Combine all contexts
        all_contexts = list(contexts) if contexts else []
        
        # Add instructions from metadata
        instructions_list = transform_metadata.get("instructions", [])
        for instruction in instructions_list:
            if hasattr(instruction, 'content'):
                all_contexts.append(instruction.content)
            else:
                all_contexts.append(str(instruction))
        
        # Add SQL pairs as examples
        sql_pairs = transform_metadata.get("sql_pairs", [])
        if sql_pairs:
            for pair in sql_pairs[:3]:
                if isinstance(pair, dict):
                    all_contexts.append(f"Question: {pair.get('question', '')}\nSQL: {pair.get('sql', '')}")
        
        # Load project-specific instructions
        project_instructions = []
        if project_id:
            project_instructions = self._load_project_instructions(project_id)
        
        # Use construct_instructions to get calculated fields and metrics instructions
        has_calculated_field = any("Calculated Field" in ctx for ctx in all_contexts)
        has_metric = any("metric" in ctx.lower() for ctx in all_contexts)
        
        instructions = construct_instructions(
            configuration=config,
            has_calculated_field=has_calculated_field,
            has_metric=has_metric,
            instructions=project_instructions
        )
        
        # Format additional metadata (metrics removed for now)
        calculated_fields_text = ""
        if transform_metadata.get("calculated_fields"):
            calculated_fields_text = "\n### EXISTING CALCULATED FIELDS ###\n"
            for field in transform_metadata["calculated_fields"][:3]:
                if isinstance(field, dict):
                    calculated_fields_text += f"- {field.get('name', '')}: {field.get('expression', '')}\n"
        
        knowledge_text = ""
        if knowledge:
            knowledge_text = "\n### ADDITIONAL KNOWLEDGE ###\n"
            for k in knowledge:
                knowledge_text += f"- {k}\n"
        
        sql_functions_text = ""
        if transform_metadata.get("sql_functions"):
            sql_functions_text = "\n### AVAILABLE SQL FUNCTIONS ###\n"
            for func in transform_metadata["sql_functions"][:10]:  # Show more functions (up to 10)
                if isinstance(func, dict):
                    name = func.get('name', '')
                    description = func.get('description', '')
                    usage = func.get('usage', '')
                    parameters = func.get('parameters', [])
                    returns = func.get('returns', '')
                    
                    # Format function information
                    func_info = f"- {name}"
                    if description:
                        func_info += f": {description}"
                    if parameters:
                        params_str = ", ".join([str(p) for p in parameters[:3]])  # Show first 3 params
                        func_info += f"\n  Parameters: {params_str}"
                    if returns:
                        func_info += f"\n  Returns: {returns}"
                    if usage:
                        func_info += f"\n  Usage: {usage}"
                    sql_functions_text += func_info + "\n"
        
        prompt = f"""
{instructions}

### DATABASE SCHEMA ###
{chr(10).join(contexts) if contexts else "No schema context provided"}

{calculated_fields_text}
{knowledge_text}
{sql_functions_text}

### USER QUESTION ###
{query}

### CURRENT TIME ###
{config.show_current_time()}

### TASK ###
Analyze the user's question and determine:
1. What type of transformation is needed (CALCULATED_COLUMN, METRIC, COLUMN_TRANSFORMATION, or AGGREGATION_TRANSFORMATION)
2. Which columns from the schema will be used
3. What new calculated columns or transformations need to be created
4. What SQL functions and logic are required
5. If this is a metric, identify dimensions and measures

Use the calculated field and metric instructions above to guide your reasoning.

Generate a detailed reasoning plan in the specified JSON format.
"""
        return prompt
    
    def _parse_transform_reasoning(
        self,
        reasoning_content: str,
        transform_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse the reasoning content to extract structured information"""
        try:
            # Try to extract JSON from the reasoning
            import re
            json_match = re.search(r'\{[\s\S]*\}', reasoning_content)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # Fallback: Extract information using heuristics
            reasoning_lower = reasoning_content.lower()
            
            transform_type = TransformType.COLUMN_TRANSFORMATION.value
            if "metric" in reasoning_lower or "aggregation" in reasoning_lower:
                transform_type = TransformType.METRIC.value
            elif "calculated" in reasoning_lower or "compute" in reasoning_lower:
                transform_type = TransformType.CALCULATED_COLUMN.value
            
            return {
                "transform_type": transform_type,
                "source_columns": [],
                "target_columns": [],
                "calculation_steps": [],
                "sql_functions_needed": [],
                "is_metric": transform_type == TransformType.METRIC.value
            }
            
        except Exception as e:
            logger.error(f"Error parsing transform reasoning: {e}")
            return {
                "transform_type": TransformType.COLUMN_TRANSFORMATION.value,
                "source_columns": [],
                "target_columns": [],
                "calculation_steps": [],
                "sql_functions_needed": [],
                "is_metric": False
            }
    
    async def _retrieve_refined_schema_based_on_reasoning(
        self,
        query: str,
        reasoning_plan: Dict[str, Any],
        unified_context: Dict[str, Any],
        project_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Retrieve refined schema based on reasoning plan.
        This method extracts necessary columns from the reasoning plan and retrieves
        only the relevant schema information for those columns.
        
        Args:
            query: Original user query
            reasoning_plan: The reasoning plan from step 1
            unified_context: The unified context from initial retrieval
            project_id: Project ID
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with refined schema contexts containing only necessary columns
        """
        try:
            logger.info("=== RETRIEVING REFINED SCHEMA BASED ON REASONING ===")
            
            # Extract necessary information from reasoning plan
            source_columns = reasoning_plan.get("source_columns", [])
            target_columns = reasoning_plan.get("target_columns", [])
            calculation_steps = reasoning_plan.get("calculation_steps", [])
            
            # Extract column names from calculation steps
            step_columns = []
            for step in calculation_steps:
                if isinstance(step, dict):
                    sql_expression = step.get("sql_expression", "")
                    if sql_expression:
                        # Extract column names from SQL expressions
                        import re
                        # Pattern to match column references (table.column or just column)
                        column_patterns = [
                            r'\b(\w+)\.(\w+)\b',  # table.column
                            r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b(?=\s*(?:,|\)|$|AS|FROM|WHERE|GROUP|ORDER|HAVING))',  # standalone column names
                        ]
                        for pattern in column_patterns:
                            matches = re.findall(pattern, sql_expression, re.IGNORECASE)
                            if matches:
                                if isinstance(matches[0], tuple):
                                    # table.column format
                                    step_columns.extend([f"{m[0]}.{m[1]}" for m in matches if len(m) == 2])
                                else:
                                    # standalone column - filter out SQL keywords
                                    sql_keywords = {'select', 'where', 'group', 'order', 'having', 'union', 'as', 'on', 'and', 'or', 'not', 'null', 'is', 'in', 'like', 'between', 'from', 'join', 'inner', 'left', 'right', 'outer', 'case', 'when', 'then', 'else', 'end', 'sum', 'count', 'avg', 'min', 'max'}
                                    valid_columns = [m for m in matches if m.lower() not in sql_keywords and len(m) > 1]
                                    step_columns.extend(valid_columns)
            
            # Combine all column references
            all_column_refs = set(source_columns + target_columns + step_columns)
            
            # Extract table names from column references
            column_based_tables = set()
            for col_ref in all_column_refs:
                if '.' in col_ref:
                    table_name = col_ref.split('.')[0]
                    column_based_tables.add(table_name)
                else:
                    # If no table prefix, we'll need to search across all tables
                    # Use tables from unified context
                    column_based_tables.update(unified_context.get("table_names", []))
            
            # Get existing table names from unified context
            existing_tables = set(unified_context.get("table_names", []))
            
            # Combine tables (use existing tables if no specific column-based tables found)
            tables_to_retrieve = list(column_based_tables) if column_based_tables else list(existing_tables)
            
            # Create a refined query that mentions the necessary columns and tables
            # This helps the retrieval system focus on the relevant schema information
            refined_query_parts = [query]
            
            # Add column information to help retrieval
            if all_column_refs:
                # Format column references for the query
                column_list = list(all_column_refs)[:20]  # Limit to avoid query being too long
                refined_query_parts.append(f"Required columns: {', '.join(column_list)}")
            
            if tables_to_retrieve:
                refined_query_parts.append(f"Tables: {', '.join(tables_to_retrieve)}")
            
            if source_columns:
                refined_query_parts.append(f"Source columns: {', '.join(source_columns[:10])}")  # Limit to first 10
            if target_columns:
                refined_query_parts.append(f"Target columns: {', '.join(target_columns[:10])}")  # Limit to first 10
            
            # Add transform type for context
            transform_type = reasoning_plan.get("transform_type", "")
            if transform_type:
                refined_query_parts.append(f"Transform type: {transform_type}")
            
            refined_query = " ".join(refined_query_parts)
            
            logger.info(f"Refined query: {refined_query}")
            logger.info(f"Tables to retrieve: {tables_to_retrieve}")
            logger.info(f"Column references: {all_column_refs}")
            
            # Retrieve refined schema with column focus
            schema_result = await self.retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval={
                    "table_retrieval_size": len(tables_to_retrieve) if tables_to_retrieve else 10,
                    "table_column_retrieval_size": 100,  # Still get all columns, but query is refined
                    "allow_using_db_schemas_without_pruning": False
                },
                query=refined_query,  # Use refined query that mentions columns
                tables=tables_to_retrieve if tables_to_retrieve else None,
                histories=kwargs.get("histories")
            )
            
            # Extract refined schema contexts
            refined_schema_contexts = []
            refined_relationships = []
            refined_table_names = []
            
            for schema in schema_result.get("schemas", []):
                if isinstance(schema, dict):
                    table_ddl = schema.get("table_ddl", "")
                    if table_ddl:
                        # Optionally filter DDL to only include relevant columns
                        # For now, we'll use the full DDL but the query refinement should help
                        refined_schema_contexts.append(table_ddl)
                    
                    table_name = schema.get("table_name", "")
                    if table_name:
                        refined_table_names.append(table_name)
                    
                    table_relationships = schema.get("relationships", [])
                    if table_relationships:
                        refined_relationships.extend(table_relationships)
            
            logger.info(f"=== REFINED SCHEMA RETRIEVED ===")
            logger.info(f"Refined schema contexts: {len(refined_schema_contexts)}")
            logger.info(f"Refined table names: {len(refined_table_names)}")
            logger.info(f"Refined relationships: {len(refined_relationships)}")
            
            return {
                "schema_contexts": refined_schema_contexts,
                "table_names": refined_table_names,
                "relationships": refined_relationships,
                "column_references": list(all_column_refs),
                "tables_retrieved": tables_to_retrieve
            }
            
        except Exception as e:
            logger.error(f"Error retrieving refined schema: {e}")
            # Return original unified context schema if refinement fails
            return {
                "schema_contexts": unified_context.get("schema_contexts", []),
                "table_names": unified_context.get("table_names", []),
                "relationships": unified_context.get("relationships", []),
                "column_references": [],
                "tables_retrieved": []
            }
    
    async def _generate_transform_sql(
        self,
        query: str,
        reasoning_plan: Dict[str, Any],
        contexts: List[str],
        knowledge: Optional[List[str]] = None,
        project_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate SQL with transformations based on reasoning plan
        
        This follows a similar pattern to _handle_sql_generation but with
        transform-specific logic. Uses unified context if provided.
        """
        try:
            # Get project_id from parameter or kwargs
            project_id = project_id or kwargs.get("project_id")
            if not project_id:
                raise ValueError("project_id is required")
            
            # Use unified context if provided (should be from process_transform_request)
            unified_context = kwargs.get("unified_context")
            if unified_context:
                schema_contexts = unified_context.get("schema_contexts", contexts or [])
                relationships = unified_context.get("relationships", [])
                transform_metadata = {
                    "instructions": unified_context.get("instructions", []),
                    "sql_pairs": unified_context.get("sql_pairs", []),
                    "calculated_fields": unified_context.get("calculated_fields", []),
                    "sql_functions": unified_context.get("sql_functions", []),  # Use SQL functions from unified context
                    "knowledge": unified_context.get("knowledge", knowledge or [])
                }
            else:
                # Fallback: retrieve if not provided
                schema_result = await self.retrieval_helper.get_database_schemas(
                    project_id=project_id,
                    table_retrieval={
                        "table_retrieval_size": 10,
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": False
                    },
                    query=query,
                    tables=None,
                    histories=None
                )
                
                schema_contexts = []
                relationships = []
                for schema in schema_result.get("schemas", []):
                    if isinstance(schema, dict):
                        table_ddl = schema.get("table_ddl", "")
                        if table_ddl:
                            schema_contexts.append(table_ddl)
                        
                        table_relationships = schema.get("relationships", [])
                        if table_relationships:
                            relationships.extend(table_relationships)
                
                # Retrieve transform metadata
                transform_metadata = await self._retrieve_transform_metadata(
                    query=query,
                    project_id=project_id,
                    knowledge=knowledge or []
                )
            
            # Build transform SQL generation prompt using same pattern as _generate_sql_internal
            # Combine all contexts similar to _generate_sql_internal
            all_contexts = list(schema_contexts)
            
            # Add instructions from metadata
            instructions_list = transform_metadata.get("instructions", [])
            for instruction in instructions_list:
                if hasattr(instruction, 'content'):
                    all_contexts.append(instruction.content)
                else:
                    all_contexts.append(str(instruction))
            
            # Add SQL pairs as examples
            sql_pairs = transform_metadata.get("sql_pairs", [])
            if sql_pairs:
                for pair in sql_pairs:
                    if isinstance(pair, dict):
                        all_contexts.append(f"Question: {pair.get('question', '')}\nSQL: {pair.get('sql', '')}")
            
            # Create configuration object
            config = Configuration(**kwargs.get("configuration", {}))
            
            # Load project-specific instructions
            project_instructions = self._load_project_instructions(project_id)
            
            # Construct instructions using existing function (includes calculated fields and metrics)
            # Use unified context flags if available
            if unified_context:
                has_calculated_field = unified_context.get("has_calculated_field", False)
                has_metric = unified_context.get("has_metric", False)
            else:
                has_calculated_field = any("Calculated Field" in ctx for ctx in all_contexts)
                has_metric = any("metric" in ctx.lower() for ctx in all_contexts)
            
            instructions = construct_instructions(
                configuration=config,
                has_calculated_field=has_calculated_field,
                has_metric=has_metric,
                instructions=project_instructions
            )
            
            # Add reasoning plan
            reasoning_json = json.dumps(reasoning_plan, indent=2)
            instructions += f"\n### TRANSFORM REASONING PLAN ###\n{reasoning_json}\n"
            instructions += "\n###IMPORTANT **Please ensure to use all the reasoning steps to answer the question and dont skip any steps if not results will be broken**"
            
            # Add relationships if available
            if relationships:
                relationships_context = self._format_relationships_for_sql_generation(relationships)
                instructions += f"\n### TABLE RELATIONSHIPS ###\n{relationships_context}\n"
            
            # Add knowledge if provided
            knowledge_list = transform_metadata.get("knowledge", knowledge or [])
            if knowledge_list:
                knowledge_text = "\n".join([f"- {k}" for k in knowledge_list])
                instructions += f"\n### ADDITIONAL KNOWLEDGE ###\n{knowledge_text}\n"
            
            # Add SQL functions if available
            sql_functions_list = transform_metadata.get("sql_functions", [])
            if sql_functions_list:
                sql_functions_text = "\n### AVAILABLE SQL FUNCTIONS ###\n"
                for func in sql_functions_list[:10]:  # Show up to 10 functions
                    if isinstance(func, dict):
                        name = func.get('name', '')
                        description = func.get('description', '')
                        usage = func.get('usage', '')
                        parameters = func.get('parameters', [])
                        returns = func.get('returns', '')
                        
                        # Format function information
                        func_info = f"- {name}"
                        if description:
                            func_info += f": {description}"
                        if parameters:
                            params_str = ", ".join([str(p) for p in parameters[:3]])  # Show first 3 params
                            func_info += f"\n  Parameters: {params_str}"
                        if returns:
                            func_info += f"\n  Returns: {returns}"
                        if usage:
                            func_info += f"\n  Usage: {usage}"
                        sql_functions_text += func_info + "\n"
                instructions += sql_functions_text + "\n"
            
            # Add table names if available from unified context
            if unified_context and unified_context.get("table_names"):
                instructions += f"\n### AVAILABLE TABLES ###\n{chr(10).join(unified_context['table_names'])}\n"
            
            # Add query and contexts (following same pattern as _generate_sql_internal)
            instructions += f"\n### DATABASE SCHEMA ###\n{chr(10).join(all_contexts)}\n\n### QUESTION ###\nUser's Question: {query}\nCurrent Time: {config.show_current_time()}\n\nLet's think step by step."
            
            # Generate SQL using LLM with existing system prompt
            messages = [
                SystemMessage(content=sql_generation_system_prompt),
                HumanMessage(content=instructions)
            ]
            
            prompt = ChatPromptTemplate.from_messages(messages)
            chain = prompt | self.llm
            
            result = await chain.ainvoke(
                {
                    "system_prompt": sql_generation_system_prompt,
                    "user_prompt": instructions
                },
                **SQL_GENERATION_MODEL_KWARGS
            )
            
            # Extract SQL from result
            sql_content = ""
            if hasattr(result, 'content'):
                extracted_data = self._extract_sql_from_content(result.content)
                sql_content = extracted_data["sql"]
            
            if not sql_content:
                return {
                    "valid_generation_results": [],
                    "invalid_generation_results": [{
                        "sql": "",
                        "type": "TRANSFORM_GENERATION_ERROR",
                        "error": "No valid SQL found in LLM response"
                    }]
                }
            
            # Post-process the SQL
            try:
                sql_json = json.dumps({
                    "sql": sql_content,
                    "parsed_entities": extracted_data.get("parsed_entities", {})
                })
                
                post_processed_result = await self.gen_processor.run(
                    [sql_json],
                    timeout=kwargs.get("timeout", 30.0),
                    project_id=project_id
                )
                
                return {
                    "valid_generation_results": [{
                        "sql": sql_content,
                        "parsed_entities": extracted_data.get("parsed_entities", {}),
                        "reasoning_plan": reasoning_plan,
                        "transform_type": reasoning_plan.get("transform_type"),
                        "type": "TRANSFORM_GENERATION_SUCCESS"
                    }],
                    "invalid_generation_results": []
                }
                
            except Exception as e:
                logger.error(f"Error in post-processing transform SQL: {e}")
                return {
                    "valid_generation_results": [],
                    "invalid_generation_results": [{
                        "sql": sql_content,
                        "type": "TRANSFORM_POST_PROCESSING_ERROR",
                        "error": str(e)
                    }]
                }
                
        except Exception as e:
            logger.error(f"Error generating transform SQL: {e}")
            return {
                "valid_generation_results": [],
                "invalid_generation_results": [{
                    "sql": "",
                    "type": "TRANSFORM_GENERATION_ERROR",
                    "error": str(e)
                }]
            }
    
    def _get_transform_sql_system_prompt(self) -> str:
        """Get system prompt for transform SQL generation - uses existing sql_generation_system_prompt"""
        # Use the existing SQL generation system prompt as base, with transform-specific additions
        return f"""
You are an expert SQL developer specializing in creating dynamic column transformations and calculated fields.
Given a user's question, database schema, reasoning plan, and knowledge base, generate ANSI SQL queries that create the necessary transformations.

{sql_generation_system_prompt}

### TRANSFORMATION REQUIREMENTS ###
1. **CALCULATED_COLUMN**: Create new columns using calculations from existing columns
   - Follow the calculated field instructions provided in the context
   - Use existing calculated fields when available instead of recreating them
   
2. **METRIC**: Create metric-based aggregations with proper dimensions and measures
   - Follow the metric instructions provided in the context
   - Use existing metrics when available
   
3. **COLUMN_TRANSFORMATION**: Transform existing columns (formatting, conversions, etc.)
4. **AGGREGATION_TRANSFORMATION**: Create aggregations with custom transformations

### FINAL ANSWER FORMAT ###
The final answer must be an ANSI SQL query in JSON format:
{{
    "sql": <SQL_QUERY_STRING>,
    "parsed_entities": {{
        "column_filters": [],
        "time_filters": [],
        "aggregations": [],
        "group_by_columns": [],
        "calculated_columns": [],
        "transformations": []
    }}
}}
"""
    
    def _build_transform_sql_prompt(
        self,
        query: str,
        reasoning_plan: Dict[str, Any],
        schema_contexts: List[str],
        knowledge: List[str],
        transform_metadata: Dict[str, Any],
        relationships: List[Dict] = None,
        **kwargs
    ) -> str:
        """
        Build the prompt for transform SQL generation
        Note: This method is kept for backward compatibility but the actual prompt
        building is now done inline in _generate_transform_sql to match the pattern
        used in _generate_sql_internal
        """
        # This method is deprecated - prompt building is now done inline
        # Keeping for backward compatibility
        reasoning_json = json.dumps(reasoning_plan, indent=2)
        knowledge_text = "\n".join([f"- {k}" for k in knowledge]) if knowledge else "None"
        config = Configuration(**kwargs.get("configuration", {}))
        
        return f"""
### TRANSFORM REASONING PLAN ###
{reasoning_json}

### DATABASE SCHEMA ###
{chr(10).join(schema_contexts)}

### ADDITIONAL KNOWLEDGE ###
{knowledge_text}

### QUESTION ###
User's Question: {query}
Current Time: {config.show_current_time()}

### TASK ###
Generate an ANSI SQL query that implements the transformations specified in the reasoning plan.
"""
    
    async def _retrieve_unified_transform_context(
        self,
        query: str,
        project_id: str,
        knowledge: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Retrieve unified context once for all transform operations.
        This method retrieves and caches all necessary data to avoid duplicate calls.
        
        Process:
        1. Retrieve instructions and SQL pairs first to extract table hints
        2. Extract table names from instructions and SQL examples
        3. Combine query-based tables with instruction-based tables (universal set)
        4. Retrieve database schemas for the combined table set
        5. Retrieve all metadata (instructions, examples, metrics, etc.) in parallel
        6. Cache and return unified context
        
        The unified context is then reused across:
        - Reasoning plan generation
        - SQL generation
        - All subsequent operations
        
        Args:
            query: Natural language question
            project_id: Project ID
            knowledge: Additional knowledge context
            **kwargs: Additional arguments (histories, etc.)
            
        Returns:
            Dictionary containing:
            - schema_contexts: Combined schema DDLs (universal set)
            - table_names: All unique table names
            - relationships: Table relationships
            - instructions: Retrieved instructions
            - sql_pairs: SQL examples
            - metrics: Available metrics
            - calculated_fields: Calculated fields
            - knowledge: Knowledge base entries
            - has_calculated_field: Boolean flag
            - has_metric: Boolean flag
            - metadata: Cached metadata
        """
        try:
            logger.info("=== RETRIEVING UNIFIED TRANSFORM CONTEXT ===")
            logger.info(f"Query: {query}")
            logger.info(f"Project ID: {project_id}")
            
            # Step 1: Retrieve instructions and SQL pairs in parallel to get table hints
            instructions_result, sql_pairs_result = await asyncio.gather(
                self.retrieval_helper.get_instructions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=0.3,
                    top_k=5
                ),
                self.retrieval_helper.get_sql_pairs(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=0.3,
                    max_retrieval_size=5
                ),
                return_exceptions=True
            )
            
            # Extract table names from instructions using retrieval helper
            # Instead of parsing SQL, we query each instruction to get relevant tables from Chroma
            # This handles natural language instructions like "How to calculate integer strength level scores using int_strength_level_metadata?"
            instruction_tables = set()
            instructions_list = instructions_result.get("documents", []) if not isinstance(instructions_result, Exception) and instructions_result else []
            
            # Process instructions in parallel to get tables
            instruction_table_tasks = []
            for instruction in instructions_list:
                # Extract content from instruction (handle different formats)
                content = None
                if hasattr(instruction, 'content'):
                    content = instruction.content
                elif hasattr(instruction, 'page_content'):
                    content = instruction.page_content
                elif isinstance(instruction, dict):
                    # Handle dict format - check for 'question', 'content', or 'instruction' fields
                    content = instruction.get('question') or instruction.get('content') or instruction.get('instruction') or str(instruction)
                else:
                    content = str(instruction)
                
                # Use the instruction content as a query to get relevant tables from Chroma
                if content and content.strip():
                    logger.info(f"Querying tables for instruction: {content[:100]}...")
                    task = self.retrieval_helper.get_database_schemas(
                        project_id=project_id,
                        table_retrieval={
                            "table_retrieval_size": 5,  # Smaller size for instruction queries
                            "table_column_retrieval_size": 50,
                            "allow_using_db_schemas_without_pruning": False
                        },
                        query=content,  # Use instruction content/question as query
                        tables=None,
                        histories=None
                    )
                    instruction_table_tasks.append(task)
            
            # Execute all table retrieval tasks in parallel
            if instruction_table_tasks:
                logger.info(f"Retrieving tables for {len(instruction_table_tasks)} instructions")
                instruction_schema_results = await asyncio.gather(*instruction_table_tasks, return_exceptions=True)
                
                # Extract table names from each result
                for i, schema_result in enumerate(instruction_schema_results):
                    if isinstance(schema_result, Exception):
                        logger.warning(f"Error retrieving tables for instruction {i}: {schema_result}")
                        continue
                    
                    schemas = schema_result.get("schemas", [])
                    for schema in schemas:
                        if isinstance(schema, dict):
                            table_name = schema.get("table_name", "")
                            if table_name:
                                instruction_tables.add(table_name)
                                logger.info(f"Found table from instruction: {table_name}")
            
            logger.info(f"Extracted {len(instruction_tables)} unique tables from instructions: {list(instruction_tables)}")
            
            # Extract table names from SQL pairs
            sql_pairs = sql_pairs_result.get("sql_pairs", []) if not isinstance(sql_pairs_result, Exception) and sql_pairs_result else []
            sql_pair_tables = set()
            for pair in sql_pairs:
                if isinstance(pair, dict):
                    sql = pair.get("sql", "")
                    if sql:
                        import re
                        patterns = [
                            r'(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)',
                            r'(\w+)\.\w+',
                            r'FROM\s+(\w+)\s+AS',
                            r'JOIN\s+(\w+)'
                        ]
                        for pattern in patterns:
                            matches = re.findall(pattern, sql, re.IGNORECASE)
                            sql_keywords = {'select', 'where', 'group', 'order', 'having', 'union', 'as', 'on', 'and', 'or', 'not', 'null', 'is', 'in', 'like', 'between'}
                            valid_tables = [m for m in matches if m.lower() not in sql_keywords and len(m) > 1]
                            sql_pair_tables.update(valid_tables)
            
            # Extract table names from histories if provided
            history_tables = set()
            histories = kwargs.get("histories")
            if histories:
                for history in histories:
                    if isinstance(history, dict):
                        sql = history.get("sql", "")
                    elif hasattr(history, 'sql'):
                        sql = history.sql
                    else:
                        continue
                    
                    if sql:
                        import re
                        patterns = [
                            r'(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)',
                            r'(\w+)\.\w+',
                            r'FROM\s+(\w+)\s+AS',
                            r'JOIN\s+(\w+)'
                        ]
                        for pattern in patterns:
                            matches = re.findall(pattern, sql, re.IGNORECASE)
                            sql_keywords = {'select', 'where', 'group', 'order', 'having', 'union', 'as', 'on', 'and', 'or', 'not', 'null', 'is', 'in', 'like', 'between'}
                            valid_tables = [m for m in matches if m.lower() not in sql_keywords and len(m) > 1]
                            history_tables.update(valid_tables)
            
            # Combine all table names (query-based + instruction-based + SQL pair-based + history-based)
            # This creates the universal set of tables needed
            all_table_hints = list(instruction_tables | sql_pair_tables | history_tables)
            logger.info(f"Extracted {len(instruction_tables)} tables from instructions, {len(sql_pair_tables)} from SQL pairs, {len(history_tables)} from histories")
            logger.info(f"Combined table hints (universal set): {all_table_hints}")
            
            # Step 2: Retrieve database schemas (will use query + table hints)
            schema_result = await self.retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval={
                    "table_retrieval_size": 10,
                    "table_column_retrieval_size": 100,
                    "allow_using_db_schemas_without_pruning": False
                },
                query=query,
                tables=all_table_hints if all_table_hints else None,  # Pass table hints
                histories=kwargs.get("histories")
            )
            
            # Step 3: Retrieve additional metadata and SQL functions in parallel
            metadata_result, sql_functions_result = await asyncio.gather(
                self._retrieve_and_cache_metadata(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=0.3,
                    max_retrieval_size=5,
                    top_k=5
                ),
                self.retrieval_helper.get_sql_functions(
                    query=query,
                    project_id=project_id,
                    k=10,
                    similarity_threshold=0.5,
                    max_results=10
                ),
                return_exceptions=True
            )
            
            # Extract SQL functions from result
            sql_functions = []
            if not isinstance(sql_functions_result, Exception) and sql_functions_result:
                sql_functions = sql_functions_result.get("sql_functions", [])
                logger.info(f"Retrieved {len(sql_functions)} SQL functions")
            else:
                logger.warning(f"Error retrieving SQL functions: {sql_functions_result}")
            
            # Retrieve calculated fields (metrics removed for now)
            calculated_fields = await self._retrieve_calculated_fields(
                query=query,
                project_id=project_id
            )
            
            # Extract schema contexts and relationships
            schema_contexts = []
            relationships = []
            table_names = []
            
            for schema in schema_result.get("schemas", []):
                if isinstance(schema, dict):
                    table_ddl = schema.get("table_ddl", "")
                    if table_ddl:
                        schema_contexts.append(table_ddl)
                    
                    table_name = schema.get("table_name", "")
                    if table_name:
                        table_names.append(table_name)
                    
                    table_relationships = schema.get("relationships", [])
                    if table_relationships:
                        relationships.extend(table_relationships)
            
            # Combine all metadata into unified context (metrics and views removed for now)
            unified_context = {
                "schema_contexts": schema_contexts,
                "table_names": table_names,
                "relationships": relationships,
                "instructions": instructions_list,
                "sql_pairs": sql_pairs,
                "sql_functions": sql_functions,  # SQL functions retrieved from retrieval helper
                "calculated_fields": calculated_fields,
                "knowledge": knowledge or [],
                "histories": kwargs.get("histories"),
                "has_calculated_field": any("Calculated Field" in ctx for ctx in schema_contexts),
                "has_metric": False,  # Metrics removed for now
                "metadata": metadata_result
            }
            
            logger.info(f"=== UNIFIED CONTEXT RETRIEVED ===")
            logger.info(f"Schema contexts: {len(schema_contexts)}")
            logger.info(f"Table names: {len(table_names)}")
            logger.info(f"Relationships: {len(relationships)}")
            logger.info(f"Instructions: {len(instructions_list)}")
            logger.info(f"SQL pairs: {len(sql_pairs)}")
            logger.info(f"SQL functions: {len(sql_functions)}")
            
            return unified_context
            
        except Exception as e:
            logger.error(f"Error retrieving unified transform context: {e}")
            return {
                "schema_contexts": [],
                "table_names": [],
                "relationships": [],
                "instructions": [],
                "sql_pairs": [],
                "sql_functions": [],  # SQL functions empty on error
                "calculated_fields": [],
                "knowledge": knowledge or [],
                "has_calculated_field": False,
                "has_metric": False,  # Metrics removed for now
                "metadata": {}
            }
    
    async def process_transform_request(
        self,
        query: str,
        knowledge: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Main entry point for transform SQL generation
        
        Process:
        1. Retrieve unified context (schemas, instructions, examples, etc.) once
        2. Generate reasoning plan using unified context
        3. Retrieve refined schema based on reasoning plan (only necessary columns)
        4. Generate transform SQL using reasoning plan and refined schema
        
        Args:
            query: Natural language question
            knowledge: Additional knowledge context
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with transform SQL results
        """
        try:
            project_id = kwargs.get("project_id")
            if not project_id:
                raise ValueError("project_id is required")
            
            # Remove project_id from kwargs to avoid duplicate argument error
            kwargs_for_context = {k: v for k, v in kwargs.items() if k != "project_id"}
            
            # Step 1: Retrieve unified context once (cached and reused)
            logger.info("Step 1: Retrieving unified transform context")
            unified_context = await self._retrieve_unified_transform_context(
                query=query,
                project_id=project_id,
                knowledge=knowledge,
                **kwargs_for_context
            )
            
            # Step 2: Generate reasoning plan using unified context
            logger.info("Step 2: Generating transform reasoning plan")
            # Remove arguments that are passed explicitly to avoid duplicate argument errors
            kwargs_for_reasoning = {k: v for k, v in kwargs.items() if k not in ["contexts", "language", "project_id"]}
            reasoning_result = await self._generate_transform_reasoning(
                query=query,
                knowledge=knowledge,
                contexts=unified_context["schema_contexts"],
                language=kwargs.get("language", "English"),
                project_id=project_id,  # Pass project_id explicitly
                unified_context=unified_context,
                **kwargs_for_reasoning
            )
            
            if not reasoning_result.get("success", False):
                return {
                    "success": False,
                    "error": "Failed to generate reasoning plan",
                    "reasoning_error": reasoning_result.get("error")
                }
            
            reasoning_plan = reasoning_result.get("reasoning_plan", {})
            
            # Step 3: Retrieve refined schema based on reasoning plan (only necessary columns)
            logger.info("Step 3: Retrieving refined schema based on reasoning plan")
            # Remove arguments that are passed explicitly to avoid duplicate argument errors
            kwargs_for_refined = {k: v for k, v in kwargs.items() if k != "project_id"}
            refined_schema_context = await self._retrieve_refined_schema_based_on_reasoning(
                query=query,
                reasoning_plan=reasoning_plan,
                unified_context=unified_context,
                project_id=project_id,
                **kwargs_for_refined
            )
            
            # Update unified context with refined schema
            if refined_schema_context:
                unified_context["schema_contexts"] = refined_schema_context.get("schema_contexts", unified_context["schema_contexts"])
                unified_context["table_names"] = refined_schema_context.get("table_names", unified_context["table_names"])
                unified_context["relationships"] = refined_schema_context.get("relationships", unified_context["relationships"])
                logger.info(f"Refined schema: {len(refined_schema_context.get('schema_contexts', []))} contexts, {len(refined_schema_context.get('table_names', []))} tables")
            
            # Step 4: Generate transform SQL using reasoning plan and refined schema
            logger.info("Step 4: Generating transform SQL with refined schema")
            # Remove arguments that are passed explicitly to avoid duplicate argument errors
            kwargs_for_sql = {k: v for k, v in kwargs.items() if k not in ["contexts", "knowledge", "project_id"]}
            sql_result = await self._generate_transform_sql(
                query=query,
                reasoning_plan=reasoning_plan,
                contexts=unified_context["schema_contexts"],
                knowledge=knowledge,
                project_id=project_id,  # Pass project_id explicitly
                unified_context=unified_context,
                **kwargs_for_sql
            )
            
            # Standardize result format
            standardized_result = {
                "success": bool(sql_result.get("valid_generation_results")),
                "data": {
                    "sql": "",
                    "type": "TRANSFORM_GENERATION_SUCCESS",
                    "reasoning": reasoning_result.get("reasoning", ""),
                    "reasoning_plan": reasoning_plan,
                    "transform_type": reasoning_plan.get("transform_type"),
                    "parsed_entities": {}
                },
                "error": None
            }
            
            # Add valid generation results if available
            if sql_result.get("valid_generation_results"):
                valid_result = sql_result["valid_generation_results"][0]
                standardized_result["data"]["sql"] = valid_result.get("sql", "")
                standardized_result["data"]["parsed_entities"] = valid_result.get("parsed_entities", {})
            
            # Add error if no valid results
            if not standardized_result["success"]:
                standardized_result["error"] = "Failed to generate valid transform SQL"
                if sql_result.get("invalid_generation_results"):
                    standardized_result["error"] = sql_result["invalid_generation_results"][0].get("error", "Unknown error")
            
            return standardized_result
            
        except Exception as e:
            logger.error(f"Error in transform request processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }


# Factory function
def create_transform_sql_rag_agent(
    llm,
    engine: Engine,
    document_store_provider: DocumentStoreProvider = None,
    **kwargs
) -> TransformSQLRAGAgent:
    """Factory function to create Transform SQL RAG agent"""
    return TransformSQLRAGAgent(
        llm=llm,
        engine=engine,
        document_store_provider=document_store_provider,
        **kwargs
    )

