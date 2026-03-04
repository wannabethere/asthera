"""
Workflow-agnostic calculation planner node.

This node plans field instructions and metric instructions from resolved metrics + MDL schemas.
It is designed to work with standardized state formats and should not contain workflow-specific logic.

Inputs (from normalized state):
    - resolved_metrics: List[Dict] - standardized metric format
    - mdl_schemas: List[Dict] - standardized schema format
    - user_query: str
    - data_enrichment: Dict with metrics_intent
    - data_science_insights: Optional[List[Dict]] - optional insights with SQL functions
    - needs_calculation: bool

Outputs:
    - calculation_plan: Dict with field_instructions, metric_instructions, silver_time_series_suggestion, reasoning
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.agents.prompt_loader import load_prompt
from app.agents.state import EnhancedCompliancePipelineState
from .state_normalization import normalize_state_for_calculation_planner

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
        if col_meta and isinstance(col_meta, list) and len(col_meta) > 0:
            parts.append("Columns:")
            for c in col_meta:
                if isinstance(c, dict):
                    name = c.get("column_name") or c.get("name", "")
                    typ = c.get("type") or c.get("data_type", "")
                    d = (c.get("description") or c.get("display_name", "")) or ""
                    parts.append(f"  - {name}" + (f" ({typ})" if typ else "") + (f": {d}" if d else ""))
                else:
                    parts.append(f"  - {c}")
        parts.append("")
    return "\n".join(parts).strip()


def _format_metrics_for_planner(metrics: List[Dict[str, Any]]) -> str:
    """Format resolved metrics for calculation planner prompts."""
    if not metrics:
        return "No resolved metrics available."
    parts = []
    for m in metrics:
        metric_id = m.get("metric_id", "")
        name = m.get("name", "")
        description = m.get("description", "")
        category = m.get("category", "")
        kpis = m.get("kpis", [])
        trends = m.get("trends", [])
        natural_language_question = m.get("natural_language_question", "")
        source_schemas = m.get("source_schemas", [])
        data_capability = m.get("data_capability", "")
        
        parts.append(f"Metric: {name} ({metric_id})")
        if description:
            parts.append(f"  Description: {description}")
        if category:
            parts.append(f"  Category: {category}")
        if kpis:
            parts.append(f"  KPIs: {', '.join(kpis) if isinstance(kpis, list) else str(kpis)}")
        if trends:
            parts.append(f"  Trends: {', '.join(trends) if isinstance(trends, list) else str(trends)}")
        if natural_language_question:
            parts.append(f"  Natural Language Question: {natural_language_question}")
        if source_schemas:
            parts.append(f"  Source Schemas: {', '.join(source_schemas) if isinstance(source_schemas, list) else str(source_schemas)}")
        if data_capability:
            parts.append(f"  Data Capability: {data_capability}")
        parts.append("")
    return "\n".join(parts).strip()


def _format_data_science_insights_for_planner(insights: List[Dict[str, Any]]) -> str:
    """Format data science insights for calculation planner prompts."""
    if not insights:
        return ""
    parts = []
    parts.append("Data Science Insights (with SQL functions):")
    for insight in insights:
        insight_id = insight.get("insight_id", "")
        insight_name = insight.get("insight_name", "")
        insight_type = insight.get("insight_type", "")
        sql_function = insight.get("sql_function", "")
        target_metric_id = insight.get("target_metric_id", "")
        target_table_name = insight.get("target_table_name", "")
        description = insight.get("description", "")
        parameters = insight.get("parameters", {})
        business_value = insight.get("business_value", "")
        
        parts.append(f"  Insight: {insight_name} ({insight_id})")
        parts.append(f"    Type: {insight_type}")
        parts.append(f"    SQL Function: {sql_function}")
        parts.append(f"    Target Metric: {target_metric_id}")
        parts.append(f"    Target Table: {target_table_name}")
        parts.append(f"    Description: {description}")
        if parameters:
            parts.append(f"    Parameters: {json.dumps(parameters, indent=6)}")
        parts.append(f"    Business Value: {business_value}")
        parts.append("")
    return "\n".join(parts).strip()


def _extract_json_from_response(response: Any) -> Optional[str]:
    """Extract JSON string from LLM response, stripping markdown code blocks if present."""
    text = response.content if hasattr(response, "content") else str(response)
    text = (text or "").strip()
    if text.startswith("```"):
        for start in ("```json\n", "```\n"):
            if text.startswith(start):
                text = text[len(start):]
                break
        if text.endswith("```"):
            text = text[:-3].strip()
    return text or None


def calculation_planner_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Workflow-agnostic calculation planner node.
    
    Plans field instructions and metric instructions from resolved metrics + MDL schemas.
    This node expects normalized state (use normalize_state_for_calculation_planner before calling).
    
    Note: This node should only run if needs_calculation is True.
    If needs_calculation is False, this node will skip planning and return empty instructions.
    """
    try:
        logger.info("Calculation planner node executing (workflow-agnostic)")
        
        # Normalize state to standardized format
        normalized = normalize_state_for_calculation_planner(state)
        
        # Check if calculation is needed
        needs_calculation = normalized.get("needs_calculation", True)
        
        if not needs_calculation:
            logger.info("Calculation planning skipped: needs_calculation=False")
            state["calculation_plan"] = {
                "field_instructions": [],
                "metric_instructions": [],
                "silver_time_series_suggestion": None,
                "reasoning": state.get("calculation_assessment_reasoning", "Calculation not needed based on assessment."),
            }
            
            state["messages"].append(AIMessage(
                content="Calculation planning skipped: Query does not require calculation planning."
            ))
            return state
        
        # Extract normalized inputs
        resolved_metrics = normalized["resolved_metrics"]
        mdl_schemas = normalized["mdl_schemas"]
        user_query = normalized["user_query"]
        data_enrichment = normalized["data_enrichment"]
        data_science_insights = normalized.get("data_science_insights", [])
        metrics_intent = data_enrichment.get("metrics_intent", "current_state")
        
        # Validate inputs
        if not user_query:
            state["calculation_plan"] = {
                "field_instructions": [],
                "metric_instructions": [],
                "silver_time_series_suggestion": None,
                "reasoning": "No user query provided.",
            }
            return state
        
        if not mdl_schemas:
            state["calculation_plan"] = {
                "field_instructions": [],
                "metric_instructions": [],
                "silver_time_series_suggestion": None,
                "reasoning": "No table schemas available from schema resolution; cannot plan calculations.",
            }
            return state
        
        # Load prompt
        prompt_text = load_prompt("15_calculation_planner")
        # Escape curly braces to prevent ChatPromptTemplate from treating
        # JSON examples in the prompt as template variables
        prompt_text = prompt_text.replace("{", "{{").replace("}", "}}")
        
        # Format inputs for prompts
        schema_text = _format_schemas_for_planner(mdl_schemas)
        metrics_text = _format_metrics_for_planner(resolved_metrics)
        insights_text = _format_data_science_insights_for_planner(data_science_insights)
        
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        
        calculation_plan: Dict[str, Any] = {
            "field_instructions": [],
            "metric_instructions": [],
            "silver_time_series_suggestion": None,
            "reasoning": "",
        }
        
        # Build user message with formatted inputs
        user_message = f"""User question or intent: {user_query}

Resolved metrics from metrics registry:
{metrics_text}
{chr(10) + insights_text if insights_text else ""}

Table schema(s) from schema resolution:

{schema_text}

Produce field_instructions and metric_instructions for the SQL Planner. Use the resolved metrics to guide what KPIs and trends should be calculated. Map the metrics' KPIs and trends to actual table columns from the schemas.{" When data science insights are provided, incorporate the SQL functions and their parameters into the calculation instructions." if insights_text else ""} Output only the JSON object."""
        
        # Escape curly braces in user_message as well to prevent template parsing
        user_message_escaped = user_message.replace("{", "{{").replace("}", "}}")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_text),
            ("human", user_message_escaped),
        ])
        chain = prompt | llm
        
        # Use asyncio to run async LLM chain in sync context
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
        text = _extract_json_from_response(response)
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                logger.warning(f"CalculationPlannerNode: JSON parse error: {e}. Attempting to clean JSON...")
                # Try to clean and fix common JSON issues
                # Remove trailing commas before closing braces/brackets
                cleaned_text = re.sub(r',(\s*[}\]])', r'\1', text)
                # Remove single-line comments
                cleaned_text = re.sub(r'//.*?$', '', cleaned_text, flags=re.MULTILINE)
                # Remove multi-line comments
                cleaned_text = re.sub(r'/\*.*?\*/', '', cleaned_text, flags=re.DOTALL)
                # Try to extract JSON object if wrapped in other text
                json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                if json_match:
                    cleaned_text = json_match.group(0)
                
                try:
                    data = json.loads(cleaned_text)
                    logger.info("CalculationPlannerNode: Successfully parsed JSON after cleaning")
                except json.JSONDecodeError as e2:
                    logger.error(f"CalculationPlannerNode: Failed to parse JSON even after cleaning: {e2}")
                    logger.debug(f"Cleaned JSON text (first 500 chars): {cleaned_text[:500]}")
                    # Set empty defaults to allow workflow to continue
                    data = {
                        "field_instructions": [],
                        "metric_instructions": [],
                        "reasoning": f"JSON parsing failed: {str(e2)}. Original error: {str(e)}"
                    }
            
            calculation_plan["field_instructions"] = data.get("field_instructions") or []
            calculation_plan["metric_instructions"] = data.get("metric_instructions") or []
            # Check if silver time series was included in the response (if trends were requested)
            if metrics_intent == "trend" and data.get("silver_time_series_suggestion"):
                calculation_plan["silver_time_series_suggestion"] = data.get("silver_time_series_suggestion")
            if data.get("reasoning"):
                calculation_plan["reasoning"] = data["reasoning"]
        
        logger.info(
            f"CalculationPlannerNode: field_instructions={len(calculation_plan['field_instructions'])}, "
            f"metric_instructions={len(calculation_plan['metric_instructions'])}"
        )
        
        # Log if we got a silver suggestion
        if calculation_plan.get("silver_time_series_suggestion"):
            logger.info(
                f"CalculationPlannerNode: silver suggestion={bool(calculation_plan['silver_time_series_suggestion'].get('suggest_silver_table'))}, "
                f"steps={len(calculation_plan['silver_time_series_suggestion'].get('calculation_steps', []))}"
            )
        
        state["calculation_plan"] = calculation_plan
        
        silver_suggestion = calculation_plan.get("silver_time_series_suggestion")
        silver_suggested = bool(
            silver_suggestion and 
            isinstance(silver_suggestion, dict) and
            silver_suggestion.get("suggest_silver_table", False)
        )
        state["messages"].append(AIMessage(
            content=f"Calculation planning complete. Generated {len(calculation_plan.get('field_instructions', []))} field instructions, "
                   f"{len(calculation_plan.get('metric_instructions', []))} metric instructions. "
                   f"Silver table suggested: {silver_suggested}"
        ))
        
    except Exception as e:
        logger.error(f"Calculation planner failed: {e}", exc_info=True)
        state["error"] = f"Calculation planner failed: {str(e)}"
        state["calculation_plan"] = {
            "field_instructions": [],
            "metric_instructions": [],
            "silver_time_series_suggestion": None,
            "reasoning": f"Error: {str(e)}"
        }
    
    return state
