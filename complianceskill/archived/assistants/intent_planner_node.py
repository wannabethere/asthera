"""
Intent Planner Node
Runs before the query plan (breakdown) to classify the question type and identify relevant entities.
The breakdown step then uses this intent to build intent-specific search questions and filters.
"""
import json
import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.assistants.state import ContextualAssistantState
from app.utils.prompts.general_prompts import get_intent_planner_system_prompt

logger = logging.getLogger(__name__)


class IntentPlannerNode:
    """
    Classifies the user question into query_type (mdl, policy, risk_control, compliance_framework, product, domain_knowledge, unknown)
    and identifies which entities from the Available Entities table are relevant.
    Writes state["intent_plan"] for the QueryPlanNode to use when building the breakdown.
    """

    def __init__(
        self,
        assistant_type: str,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
    ):
        self.assistant_type = assistant_type
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "") or (state.get("user_context") or {}).get("query", "")
        user_context = state.get("user_context") or {}
        # Request-level intent: query_planner = table retrieval + calculation plan only; no other entities
        query_planner_intent = state.get("query_planner_intent") or user_context.get("query_planner_intent") is True

        if not query:
            state["intent_plan"] = {
                "query_type": "unknown",
                "query_types": ["unknown"],
                "identified_entities": [],
                "frameworks": [],
                "product_context": None,
            }
            state["current_node"] = "intent_planner"
            state["next_node"] = "query_planning"
            return state

        if query_planner_intent:
            # No LLM: intent is table retrieval only, handoff to SQL Planner; no policy/compliance/other entities
            state["intent_plan"] = {
                "query_type": "query_planner",
                "query_types": ["query_planner"],
                "identified_entities": [
                    "table_definitions",
                    "table_descriptions",
                    "schema_descriptions",
                    "db_schema",
                ],
                "frameworks": [],
                "product_context": user_context.get("product_context"),
            }
            state["current_node"] = "intent_planner"
            state["next_node"] = "query_planning"
            logger.info(
                f"IntentPlannerNode ({self.assistant_type}): query_planner_intent from request — query_types=['query_planner'], "
                "entities=table/schema only (no other entities fetched)"
            )
            return state

        system_prompt = get_intent_planner_system_prompt(assistant_type=self.assistant_type)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Question: {query}\n\nOutput only the JSON object."),
        ])
        chain = prompt | self.llm

        try:
            response = await chain.ainvoke({"query": query})
            text = response.content if hasattr(response, "content") else str(response)
            text = text.strip()
            if text.startswith("```"):
                for start in ("```json\n", "```\n"):
                    if text.startswith(start):
                        text = text[len(start):]
                        break
                if text.endswith("```"):
                    text = text[:-3].strip()
            plan = json.loads(text)
            if not isinstance(plan, dict):
                plan = {"query_types": ["unknown"], "identified_entities": []}
            # Support both query_types (list) and legacy query_type (string)
            query_types = plan.get("query_types")
            if not query_types and plan.get("query_type") is not None:
                query_types = [plan.get("query_type")]
            if not query_types:
                query_types = ["unknown"]
            if isinstance(query_types, str):
                query_types = [query_types]
            query_types = [str(t).strip() for t in query_types if t]
            if not query_types:
                query_types = ["unknown"]
            # Primary query_type = first non-unknown for backward compat, else first
            primary = next((t for t in query_types if str(t).lower() != "unknown"), query_types[0] if query_types else "unknown")
            intent_plan = {
                "query_type": primary,
                "query_types": query_types,
                "identified_entities": list(dict.fromkeys(plan.get("identified_entities") or [])),
                "frameworks": plan.get("frameworks") or [],
                "product_context": plan.get("product_context"),
            }
            state["intent_plan"] = intent_plan
            logger.info(
                f"IntentPlannerNode ({self.assistant_type}): query_types={intent_plan['query_types']}, "
                f"entities={len(intent_plan['identified_entities'])}, frameworks={len(intent_plan['frameworks'])}"
            )
        except Exception as e:
            logger.warning(f"IntentPlannerNode: LLM failed, using fallback: {e}")
            state["intent_plan"] = {
                "query_type": "unknown",
                "query_types": ["unknown"],
                "identified_entities": [],
                "frameworks": [],
                "product_context": None,
            }

        state["current_node"] = "intent_planner"
        state["next_node"] = "query_planning"
        return state
