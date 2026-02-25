"""
Calculation Planner Node

Plans how to calculate derived fields and metrics from tables retrieved by contextual
data retrieval. Produces field instructions and metric instructions (for SQL Planner
handoff) and optionally suggests a silver time series table with natural language
calculation steps (mean, lag, lead, trend, etc.).
"""
import json
import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.assistants.state import ContextualAssistantState
from app.utils.prompts.calculation_planner_prompts import (
    FIELD_AND_METRIC_CALCULATION_SYSTEM,
    FIELD_AND_METRIC_CALCULATION_OUTPUT_FORMAT,
    SILVER_TIME_SERIES_SYSTEM,
    SILVER_TIME_SERIES_OUTPUT_FORMAT,
    get_field_metric_calculation_user_prompt,
    get_silver_time_series_user_prompt,
)

logger = logging.getLogger(__name__)


def _format_schemas_for_planner(schemas: List[Dict[str, Any]]) -> str:
    """Format schemas for calculation planner prompts (table name, DDL, columns)."""
    if not schemas:
        return "No table schemas available."
    parts = []
    for s in schemas:
        table_name = s.get("table_name", "Unknown")
        table_ddl = s.get("table_ddl", "")
        desc = s.get("description", "")
        col_meta = s.get("column_metadata") or []
        parts.append(f"Table: {table_name}")
        if desc:
            parts.append(desc)
        if table_ddl:
            parts.append(table_ddl)
        if col_meta and isinstance(col_meta[0], dict):
            parts.append("Columns:")
            for c in col_meta:
                name = c.get("column_name", "")
                typ = c.get("type", "")
                d = (c.get("description") or c.get("display_name", "")) or ""
                parts.append(f"  - {name}" + (f" ({typ})" if typ else "") + (f": {d}" if d else ""))
        parts.append("")
    return "\n".join(parts).strip()


class CalculationPlannerNode:
    """
    Node that plans field instructions, metric instructions, and optional silver
    time series suggestion from retrieved tables. Output is intended for SQL Planner
    (text-to-SQL) handoff.
    """

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        include_silver_time_series: bool = True,
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.include_silver_time_series = include_silver_time_series

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Produce calculation_plan from data_knowledge schemas and user query."""
        query = state.get("query", "")
        data_knowledge = state.get("data_knowledge") or {}
        schemas = data_knowledge.get("schemas") or []

        if not query:
            state["calculation_plan"] = {
                "field_instructions": [],
                "metric_instructions": [],
                "silver_time_series_suggestion": None,
                "reasoning": "No user query provided.",
            }
            return state

        if not schemas:
            state["calculation_plan"] = {
                "field_instructions": [],
                "metric_instructions": [],
                "silver_time_series_suggestion": None,
                "reasoning": "No table schemas available from retrieval; cannot plan calculations.",
            }
            return state

        schema_text = _format_schemas_for_planner(schemas)
        calculation_plan: Dict[str, Any] = {
            "field_instructions": [],
            "metric_instructions": [],
            "silver_time_series_suggestion": None,
            "reasoning": "",
        }

        # 1) Field and metric calculation instructions (always run when we have schemas)
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", FIELD_AND_METRIC_CALCULATION_SYSTEM + FIELD_AND_METRIC_CALCULATION_OUTPUT_FORMAT),
                ("human", get_field_metric_calculation_user_prompt()),
            ])
            chain = prompt | self.llm
            response = await chain.ainvoke({"query": query, "schema_text": schema_text})
            text = _extract_json_from_response(response)
            if text:
                data = json.loads(text)
                calculation_plan["field_instructions"] = data.get("field_instructions") or []
                calculation_plan["metric_instructions"] = data.get("metric_instructions") or []
                if data.get("reasoning"):
                    calculation_plan["reasoning"] = data["reasoning"]
            logger.info(
                f"CalculationPlannerNode: field_instructions={len(calculation_plan['field_instructions'])}, "
                f"metric_instructions={len(calculation_plan['metric_instructions'])}"
            )
        except Exception as e:
            logger.warning(f"CalculationPlannerNode: field/metric planning failed: {e}", exc_info=True)
            calculation_plan["reasoning"] = (calculation_plan.get("reasoning") or "") + f" Field/metric planning error: {e}."

        # 2) Silver time series suggestion + calculation steps (optional)
        if self.include_silver_time_series:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", SILVER_TIME_SERIES_SYSTEM + SILVER_TIME_SERIES_OUTPUT_FORMAT),
                    ("human", get_silver_time_series_user_prompt()),
                ])
                chain = prompt | self.llm
                response = await chain.ainvoke({"query": query, "schema_text": schema_text})
                text = _extract_json_from_response(response)
                if text:
                    data = json.loads(text)
                    calculation_plan["silver_time_series_suggestion"] = {
                        "suggest_silver_table": data.get("suggest_silver_table", False),
                        "silver_table_suggestion": data.get("silver_table_suggestion"),
                        "calculation_steps": data.get("calculation_steps") or [],
                        "advanced_functions_used": data.get("advanced_functions_used") or [],
                        "reasoning": data.get("reasoning", ""),
                    }
                    logger.info(
                        f"CalculationPlannerNode: silver suggestion={bool(calculation_plan['silver_time_series_suggestion'].get('suggest_silver_table'))}, "
                        f"steps={len(calculation_plan['silver_time_series_suggestion'].get('calculation_steps', []))}"
                    )
            except Exception as e:
                logger.warning(f"CalculationPlannerNode: silver time series planning failed: {e}", exc_info=True)
                calculation_plan["silver_time_series_suggestion"] = {
                    "suggest_silver_table": False,
                    "reasoning": str(e),
                }

        state["calculation_plan"] = calculation_plan
        return state


def _extract_json_from_response(response: Any) -> Optional[str]:
    """Extract JSON string from LLM response, stripping markdown code blocks if present."""
    text = response.content if hasattr(response, "content") else str(response)
    text = (text or "").strip()
    if text.startswith("```"):
        for start in ("```json\n", "```\n"):
            if text.startswith(start):
                text = text[len(start) :]
                break
        if text.endswith("```"):
            text = text[:-3].strip()
    return text or None
