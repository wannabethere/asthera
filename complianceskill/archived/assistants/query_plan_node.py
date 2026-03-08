"""
Query plan node: break down user question into a plan using general_prompts
(playbook-first, context breakdown rules, assistant-specific entities), then
downstream nodes execute retrieval/processing according to that plan.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.assistants.state import ContextualAssistantState
from app.utils.prompt_generator import get_context_breakdown_system_prompt

logger = logging.getLogger(__name__)


class QueryPlanNode:
    """
    Breaks down the user question into a structured plan (query_type, entities,
    search_questions, metadata_filters) using general_prompts so retrieval/QA
    execute according to the plan.
    """

    def __init__(
        self,
        assistant_type: str,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        include_examples: bool = True,
    ):
        self.assistant_type = assistant_type
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.include_examples = include_examples

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "") or (state.get("user_context") or {}).get("query", "")
        intent_plan = state.get("intent_plan")
        if not query:
            state["query_plan"] = {
                "query_type": "unknown",
                "user_intent": "",
                "identified_entities": [],
                "search_questions": [],
            }
            state["current_node"] = "query_planning"
            state["next_node"] = "retrieve_context"
            return state

        # query_planner intent: table retrieval + calculation plan only; no breakdown LLM, no other entities
        query_types = intent_plan.get("query_types", []) if intent_plan else []
        if intent_plan and "query_planner" in [str(t).lower() for t in (query_types or [])]:
            state["query_plan"] = {
                "query_type": "query_planner",
                "query_types": ["query_planner"],
                "user_intent": query,
                "identified_entities": intent_plan.get("identified_entities", [
                    "table_definitions", "table_descriptions", "schema_descriptions", "db_schema",
                ]),
                "search_questions": [
                    {
                        "entity": "table_descriptions",
                        "question": query,
                        "metadata_filters": {},
                        "response_type": "table_schemas",
                    },
                ],
                "frameworks": [],
                "product_context": intent_plan.get("product_context"),
            }
            state["context_breakdown"] = state["query_plan"]
            state["generic_breakdown"] = {
                "user_intent": query,
                "query_type": "query_planner",
                "identified_entities": state["query_plan"]["identified_entities"],
                "frameworks": [],
            }
            state["current_node"] = "query_planning"
            state["next_node"] = "retrieve_context"
            logger.info(
                f"QueryPlanNode ({self.assistant_type}): query_planner intent — minimal plan (table retrieval only), no other entities"
            )
            return state

        system_prompt = get_context_breakdown_system_prompt(
            include_examples=self.include_examples,
            assistant_type=self.assistant_type,
            intent_plan=intent_plan,
        )
        query_types = []
        if intent_plan:
            query_types = intent_plan.get("query_types") or ([intent_plan.get("query_type")] if intent_plan.get("query_type") else [])
        has_intent = query_types and any(t and str(t).lower() != "unknown" for t in query_types)
        if intent_plan and has_intent:
            output_instruction = (
                "Output ONLY a single JSON object with keys: user_intent, search_questions (list of objects with entity, question, metadata_filters, response_type). "
                "Include frameworks (list) if compliance_framework in query_types; include product_context if product in query_types. "
                "The question may span multiple intents (e.g. metrics and tables for Snyk); generate search_questions for all identified_entities. No markdown, no explanation."
            )
            human_msg = "Question: {query}\n\nGiven intent: {intent_json}\n\nGenerate search_questions and user_intent as JSON."
        else:
            output_instruction = (
                "Output ONLY a single JSON object with keys: query_type, user_intent, identified_entities (list), "
                "search_questions (list of objects with entity, question, metadata_filters, response_type). "
                "For compliance include frameworks (list). For product include product_context. No markdown, no explanation."
            )
            human_msg = "Question: {query}\n\nProvide the context breakdown as JSON."
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + "\n\n" + output_instruction),
            ("human", human_msg),
        ])
        chain = prompt | self.llm

        try:
            invoke_kw = {"query": query}
            if intent_plan and human_msg.count("{intent_json}") > 0:
                import json as _json
                invoke_kw["intent_json"] = _json.dumps(intent_plan, indent=2)
            response = await chain.ainvoke(invoke_kw)
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
                plan = {"query_type": "unknown", "user_intent": query, "identified_entities": [], "search_questions": []}
            if "search_questions" not in plan:
                plan["search_questions"] = []
            if "identified_entities" not in plan and intent_plan:
                plan["identified_entities"] = intent_plan.get("identified_entities", [])
            elif "identified_entities" not in plan:
                plan["identified_entities"] = []
            if "query_type" not in plan and intent_plan:
                plan["query_type"] = intent_plan.get("query_type", "unknown")
            if "query_types" not in plan and intent_plan:
                plan["query_types"] = intent_plan.get("query_types", [plan.get("query_type", "unknown")])
            if "frameworks" not in plan and intent_plan:
                plan["frameworks"] = intent_plan.get("frameworks", [])
            if "product_context" not in plan and intent_plan:
                plan["product_context"] = intent_plan.get("product_context")
            state["query_plan"] = plan
            state["context_breakdown"] = plan
            state["generic_breakdown"] = {
                "user_intent": plan.get("user_intent"),
                "query_type": plan.get("query_type"),
                "identified_entities": plan.get("identified_entities", []),
                "frameworks": plan.get("frameworks", []),
            }
            logger.info(f"QueryPlanNode ({self.assistant_type}): query_type={plan.get('query_type')}, entities={len(plan.get('identified_entities', []))}, search_questions={len(plan.get('search_questions', []))}")
        except Exception as e:
            logger.warning(f"QueryPlanNode: LLM breakdown failed, using fallback: {e}")
            state["query_plan"] = {
                "query_type": "unknown",
                "user_intent": query,
                "identified_entities": [],
                "search_questions": [{"entity": "general", "question": query, "metadata_filters": {}, "response_type": "general"}],
            }
            state["context_breakdown"] = state["query_plan"]
            state["generic_breakdown"] = {"user_intent": query, "query_type": "unknown", "identified_entities": [], "frameworks": []}

        state["current_node"] = "query_planning"
        state["next_node"] = "retrieve_context"
        return state
