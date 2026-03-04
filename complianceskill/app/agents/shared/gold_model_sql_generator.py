"""
Shared SQL Generator for Gold Models

Generates dbt-compatible SQL for gold models based on gold model plans.
Used by both DT and CSOD workflows.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.core.dependencies import get_llm
from app.agents.gold_model_plan_generator import GoldModelPlan

logger = logging.getLogger(__name__)


class GeneratedGoldModelSQL(BaseModel):
    """A generated gold model with SQL."""

    name: str = Field(..., description="Name of the gold model (dbt model name)")
    sql_query: str = Field(..., description="Complete SQL query for the dbt model")
    description: Optional[str] = Field(
        None, description="Description of what this model does"
    )
    materialization: str = Field(
        ..., description="dbt materialization strategy (table, view, incremental)"
    )
    expected_columns: List[str] = Field(
        default_factory=list, description="List of expected output column names"
    )


class GoldModelSQLResponse(BaseModel):
    """Response containing generated SQL for gold models."""

    models: List[GeneratedGoldModelSQL] = Field(
        ..., description="List of generated gold models with SQL"
    )
    artifact_name: Optional[str] = Field(
        None,
        description="Name for the DBT artifact containing these models",
    )


class GoldModelSQLGenerator:
    """
    Generates SQL for gold models based on gold model plans.
    
    Uses LLM with structured output to generate dbt-compatible SQL queries.
    """

    def __init__(
        self,
        temperature: float = 0.0,
        max_tokens: int = 16384,  # Increased default to handle larger SQL responses
        model: Optional[str] = None,
    ):
        """
        Initialize the SQL generator.
        
        Args:
            temperature: Temperature for LLM generation (default: 0.0 for deterministic SQL)
            max_tokens: Maximum tokens for LLM response (default: 16384, increased to handle complex SQL)
            model: Optional model override (uses default from get_llm if None)
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = model

    def _build_system_prompt(self) -> str:
        """Build the system prompt for SQL generation (concise to reduce token usage)."""
        return """You are an expert in generating dbt-compatible SQL queries for gold-layer models.

**CRITICAL RULES:**
- Use `source('silver', '<table_name>')` for silver tables, `ref('<model_name>')` for gold models
- Start with {{ config(materialized='...', unique_key='...', incremental_strategy='merge', on_schema_change='append_new_columns') }}
- Use actual newlines, NOT "\\n" strings
- POSTGRES SQL syntax only
- Only use columns from provided schemas
- QUALIFY column names with table aliases
- GROUP BY: every SELECT column must be in GROUP BY or inside an aggregate
- CAST date/time to TIMESTAMP WITH TIME ZONE
- Include connection_id filtering
- For incremental: add WHERE is_incremental() check
- NO DELETE/UPDATE/INSERT, NO FILTER(WHERE), NO EXTRACT(EPOCH), NO HAVING without GROUP BY

Generate complete, executable SQL that produces all expected_columns.
"""

    def _build_prompt(
        self,
        gold_model_plan: GoldModelPlan,
        silver_tables_info: Optional[List[Dict[str, Any]]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Build the prompt for SQL generation.
        
        Args:
            gold_model_plan: The gold model plan containing specifications
            silver_tables_info: Optional list of silver tables with schemas
            examples: Optional list of example SQL queries for reference
        """
        if not gold_model_plan.specifications:
            return "No gold model specifications provided."

        # Format specifications
        specifications_text = "\n\n".join(
            f"**Model {i + 1}: {spec.name}**\n"
            f"- Description: {spec.description}\n"
            f"- Materialization: {spec.materialization}\n"
            f"- Source Tables: {', '.join(spec.source_tables)}\n"
            f"- Expected Columns: {', '.join(col.name for col in spec.expected_columns)}\n"
            f"- Mapped Metrics: {', '.join(set().union(*[col.mapped_metrics or [] for col in spec.expected_columns])) if any(col.mapped_metrics for col in spec.expected_columns) else 'N/A'}"
            for i, spec in enumerate(gold_model_plan.specifications)
        )

        # Format source columns for each specification
        source_columns_text = ""
        for spec in gold_model_plan.specifications:
            if spec.source_columns:
                source_columns_text += f"\n**Source Columns for {spec.name}:**\n"
                for src_col in spec.source_columns:
                    source_columns_text += f"- {src_col.table_name}.{src_col.column_name} ({src_col.usage or 'direct mapping'})\n"

        # Format silver table schemas if available
        table_schemas_text = ""
        if silver_tables_info:
            table_schemas_text = "\n\n**Available Silver Table Schemas:**\n\n"
            for table_info in silver_tables_info:
                table_name = table_info.get("table_name", "unknown")
                table_schemas_text += f"**Table: {table_name}**\n"
                
                # Add column metadata if available
                column_metadata = table_info.get("column_metadata", [])
                if column_metadata:
                    for col in column_metadata[:20]:  # Limit to first 20 columns
                        if isinstance(col, dict):
                            col_name = col.get("column_name") or col.get("name", "")
                            col_type = col.get("type") or col.get("data_type", "")
                            col_desc = col.get("description") or col.get("comment", "")
                            if col_name:
                                table_schemas_text += f"- {col_name}: {col_type}"
                                if col_desc:
                                    table_schemas_text += f" -- {col_desc[:80]}"
                                table_schemas_text += "\n"
                table_schemas_text += "\n"

        # Format examples if provided
        examples_text = ""
        if examples:
            examples_text = "\n\n**Example SQL Queries (for reference):**\n\n"
            for i, example in enumerate(examples[:3], 1):  # Limit to first 3 examples
                example_name = example.get("name", f"Example {i}")
                example_sql = example.get("sql", "")
                if example_sql:
                    examples_text += f"**{example_name}:**\n```sql\n{example_sql}\n```\n\n"

        prompt = f"""Generate SQL queries for the following gold model specifications:

{specifications_text}
{source_columns_text}
{table_schemas_text}
{examples_text}
**Additional Context:**
{gold_model_plan.reasoning}

**IMPORTANT:**
- Generate complete, executable SQL queries for each model specification
- Use the table schemas provided above to reference the correct columns
- Each SQL query MUST start with a config block using proper Jinja2 syntax
- Use actual newlines in your SQL output, NOT literal "\\n" escape sequences
- Use proper dbt macros for all table references: source() for silver tables, ref() for gold models
- Ensure all expected_columns are included in the SELECT statement
- For incremental models, add WHERE clause with is_incremental() check when appropriate
- Include connection_id filtering for multi-tenant isolation

Generate an artifact_name that describes this set of models (e.g., "Vulnerability Management Gold Models", "Security Compliance Dashboard Models").
"""

        return prompt

    def _build_single_model_prompt(
        self,
        spec,
        silver_tables_info: Optional[List[Dict[str, Any]]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        reasoning: Optional[str] = None,
    ) -> str:
        """
        Build a prompt for generating SQL for a single model specification.
        This reduces token usage by focusing on one model at a time.
        """
        # Format single specification (concise to save tokens)
        # Truncate description if too long
        desc = spec.description[:400] + "..." if len(spec.description) > 400 else spec.description
        # Limit expected columns display to first 20
        expected_cols_display = ', '.join(col.name for col in spec.expected_columns[:20])
        if len(spec.expected_columns) > 20:
            expected_cols_display += f" ... (+{len(spec.expected_columns) - 20} more)"
        
        specifications_text = f"""**Model: {spec.name}**
- Description: {desc}
- Materialization: {spec.materialization}
- Source Tables: {', '.join(spec.source_tables)}
- Expected Columns ({len(spec.expected_columns)}): {expected_cols_display}"""

        # Format source columns for this specification only (concise)
        source_columns_text = ""
        if spec.source_columns:
            # Group by table to make it more concise
            cols_by_table = {}
            for src_col in spec.source_columns:
                table = src_col.table_name
                if table not in cols_by_table:
                    cols_by_table[table] = []
                cols_by_table[table].append(f"{src_col.column_name} ({src_col.usage or 'map'})")
            
            source_columns_text = "\n\n**Source Columns:**\n"
            for table, cols in cols_by_table.items():
                source_columns_text += f"- {table}: {', '.join(cols[:10])}{'...' if len(cols) > 10 else ''}\n"

        # Format only relevant silver table schemas (those used by this spec)
        table_schemas_text = ""
        if silver_tables_info:
            # Filter to only tables used by this specification
            used_tables = set(spec.source_tables)
            relevant_tables = [
                t for t in silver_tables_info
                if t.get("table_name") in used_tables
            ]
            
            if relevant_tables:
                table_schemas_text = "\n\n**Silver Table Schemas:**\n\n"
                for table_info in relevant_tables:
                    table_name = table_info.get("table_name", "unknown")
                    table_schemas_text += f"**Table: {table_name}**\n"
                    
                    # Add column metadata if available - only include columns actually used in source_columns
                    column_metadata = table_info.get("column_metadata", [])
                    if column_metadata and spec.source_columns:
                        # Only include columns that are actually used in source_columns to reduce token usage
                        used_columns = {
                            (src_col.table_name, src_col.column_name)
                            for src_col in spec.source_columns
                            if src_col.table_name == table_name
                        }
                        
                        # Also include columns from expected_columns that might be in this table
                        expected_col_names = {col.name for col in spec.expected_columns}
                        
                        for col in column_metadata:
                            if isinstance(col, dict):
                                col_name = col.get("column_name") or col.get("name", "")
                                if not col_name:
                                    continue
                                
                                # Include if it's in source_columns or expected_columns
                                is_used = (table_name, col_name) in used_columns or col_name in expected_col_names
                                if is_used:
                                    col_type = col.get("type") or col.get("data_type", "")
                                    # Don't include description to save tokens
                                    table_schemas_text += f"- {col_name}: {col_type}\n"
                    table_schemas_text += "\n"

        # Format examples if provided (limit to 1 and truncate to reduce tokens)
        examples_text = ""
        if examples:
            examples_text = "\n\n**Example SQL (reference):**\n"
            # Use only the first example and truncate if too long
            example = examples[0]
            example_sql = example.get("sql", "")
            if example_sql:
                # Truncate example SQL if it's too long (keep first 1500 chars to save tokens)
                if len(example_sql) > 1500:
                    example_sql = example_sql[:1500] + "\n... (truncated for brevity)"
                examples_text += f"```sql\n{example_sql}\n```\n"

        # Truncate reasoning if too long to reduce prompt size
        reasoning_text = ""
        if reasoning:
            # Limit reasoning to 400 characters to save tokens
            truncated_reasoning = reasoning[:400] + "..." if len(reasoning) > 400 else reasoning
            reasoning_text = f"\n**Context:** {truncated_reasoning}"

        prompt = f"""Generate SQL for gold model: {spec.name}

{specifications_text}
{source_columns_text}
{table_schemas_text}
{examples_text}
{reasoning_text}

**Requirements:**
- Start with {{ config(materialized='{spec.materialization}') }}
- Use source('silver', '<table>') for silver tables, ref('<model>') for gold models
- Include all expected_columns in SELECT
- Add WHERE is_incremental() for incremental models
- Include connection_id filtering
- Use actual newlines, NOT "\\n"
"""

        return prompt

    async def _generate_single_model(
        self,
        spec,
        silver_tables_info: Optional[List[Dict[str, Any]]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        reasoning: Optional[str] = None,
    ) -> GeneratedGoldModelSQL:
        """
        Generate SQL for a single model specification.
        This reduces token usage by processing one model at a time.
        """
        # Get LLM instance
        llm = get_llm(
            temperature=self.temperature,
            model=self.model,
        )
        
        # Set max_tokens on the LLM instance if supported
        # Use a higher limit for SQL generation (SQL queries can be very long)
        # OpenAI models support up to 16384 tokens for completion
        sql_max_tokens = max(self.max_tokens, 16384)  # Ensure at least 16k tokens for SQL responses
        if hasattr(llm, 'max_tokens'):
            llm.max_tokens = sql_max_tokens
            logger.debug(f"Set max_tokens to {sql_max_tokens} for SQL generation (model: {self.model or 'default'})")
        elif hasattr(llm, 'max_output_tokens'):
            llm.max_output_tokens = sql_max_tokens
            logger.debug(f"Set max_output_tokens to {sql_max_tokens} for SQL generation")

        # Use structured output for single model
        structured_model = llm.with_structured_output(GeneratedGoldModelSQL)

        # Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_single_model_prompt(
            spec, silver_tables_info, examples, reasoning
        )

        try:
            # Build full prompt with system prompt included
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # Log prompt size for debugging (optional, don't fail if tiktoken not available)
            try:
                import tiktoken
                encoding = tiktoken.encoding_for_model("gpt-4")
                prompt_tokens = len(encoding.encode(full_prompt))
                logger.debug(f"SQL generation prompt size: ~{prompt_tokens} tokens for model {spec.name}")
            except (ImportError, Exception):
                # Fallback if tiktoken not available or fails
                prompt_tokens = len(full_prompt) // 4  # Rough estimate
                logger.debug(f"SQL generation prompt size: ~{prompt_tokens} tokens (estimated) for model {spec.name}")
            
            # Invoke LLM to generate SQL for single model
            response = await structured_model.ainvoke([HumanMessage(content=full_prompt)])

            generated_model = GeneratedGoldModelSQL.model_validate(response)
            
            logger.info(f"Generated SQL for model: {generated_model.name}")
            return generated_model

        except Exception as e:
            logger.exception(f"Error generating SQL for model {spec.name}: %s", str(e))
            raise

    async def generate(
        self,
        gold_model_plan: GoldModelPlan,
        silver_tables_info: Optional[List[Dict[str, Any]]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
    ) -> GoldModelSQLResponse:
        """
        Generate SQL for gold models based on the gold model plan.
        
        Args:
            gold_model_plan: The gold model plan containing specifications
            silver_tables_info: Optional list of silver tables with schemas
            examples: Optional list of example SQL queries for reference
            
        Returns:
            GoldModelSQLResponse with generated SQL queries
        """
        logger.info(
            f"Generating SQL for {len(gold_model_plan.specifications or [])} gold models"
        )

        if not gold_model_plan.requires_gold_model:
            logger.info("Gold models not required, returning empty response")
            return GoldModelSQLResponse(models=[], artifact_name=None)

        if not gold_model_plan.specifications:
            logger.warning("Gold model plan requires models but no specifications provided")
            return GoldModelSQLResponse(models=[], artifact_name=None)

        # Generate SQL for each model specification separately to reduce token usage
        # This prevents hitting token limits when generating multiple complex models
        generated_models = []
        
        for i, spec in enumerate(gold_model_plan.specifications, 1):
            logger.info(f"Generating SQL for model {i}/{len(gold_model_plan.specifications)}: {spec.name}")
            try:
                generated_model = await self._generate_single_model(
                    spec=spec,
                    silver_tables_info=silver_tables_info,
                    examples=examples,
                    reasoning=gold_model_plan.reasoning,
                )
                generated_models.append(generated_model)
            except Exception as e:
                logger.error(f"Failed to generate SQL for model {spec.name}: {e}")
                # Continue with other models even if one fails
                # Optionally create a placeholder model
                generated_models.append(GeneratedGoldModelSQL(
                    name=spec.name,
                    sql_query=f"-- Error generating SQL for {spec.name}: {str(e)}",
                    description=spec.description,
                    materialization=spec.materialization,
                    expected_columns=[col.name for col in spec.expected_columns],
                ))

        # Generate artifact name based on the models
        artifact_name = self._generate_artifact_name(gold_model_plan)

        sql_response = GoldModelSQLResponse(
            models=generated_models,
            artifact_name=artifact_name,
        )

        logger.info(
            f"Generated SQL for {len(generated_models)}/{len(gold_model_plan.specifications)} gold models"
        )

        return sql_response

    def _generate_artifact_name(self, gold_model_plan: GoldModelPlan) -> str:
        """
        Generate an artifact name based on the gold model plan.
        """
        if not gold_model_plan.specifications:
            return None
        
        # Try to infer a meaningful name from the first model
        first_model = gold_model_plan.specifications[0]
        model_name = first_model.name.lower()
        
        # Extract domain/keywords from model name
        if "vulnerability" in model_name or "vuln" in model_name:
            return "Vulnerability Management Gold Models"
        elif "security" in model_name:
            return "Security Compliance Gold Models"
        elif "compliance" in model_name:
            return "Compliance Dashboard Gold Models"
        elif "detection" in model_name:
            return "Detection & Triage Gold Models"
        else:
            # Use a generic name based on number of models
            if len(gold_model_plan.specifications) == 1:
                return f"{first_model.name} Gold Model"
            else:
                return f"Gold Models ({len(gold_model_plan.specifications)} models)"
