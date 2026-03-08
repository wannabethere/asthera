"""
Compliance Assistant nodes: own implementation for real controls, policies, TSC hierarchy.
Separate from Knowledge assistant (which will add impact/risk features later).
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.assistants.state import ContextualAssistantState

logger = logging.getLogger(__name__)

# Max characters per doc when formatting for QA (avoid token overflow but keep content usable)
COMPLIANCE_QA_MAX_CHARS_PER_DOC = 2000


def _build_state_update(state: Dict[str, Any], required_fields: List[str], optional_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    result = {}
    for field in required_fields:
        if field in state:
            result[field] = state[field]
    if optional_fields:
        for field in optional_fields:
            if field in state and state[field] is not None:
                value = state[field]
                if isinstance(value, (list, dict)) and len(value) == 0:
                    continue
                result[field] = value
    return result


TSC_CATEGORIES = {
    "CC1": "Control Environment",
    "CC2": "Communication and Information",
    "CC3": "Risk Assessment",
    "CC4": "Monitoring Activities",
    "CC5": "Control Activities",
    "CC6": "Logical and Physical Access Controls",
    "CC7": "System Operations",
    "CC8": "Change Management",
    "CC9": "Risk Mitigation"
}

HIERARCHY_LEVELS = {
    "framework": ["SOC2", "SOC 2", "HIPAA", "PCI-DSS", "ISO27001", "compliance framework"],
    "tsc": ["trust service criteria", "TSC", "CC1", "CC2", "CC3", "CC4", "CC5", "CC6", "CC7", "CC8", "CC9"],
    "control": ["control", "CC6.1", "CC7.2", "security control"],
    "policy": ["policy", "standard", "company rule"],
    "procedure": ["procedure", "workflow", "process", "how to execute"],
    "user_action": ["user action", "approval", "review", "what people do", "actor", "responsibility"],
    "evidence": ["evidence", "proof", "artifact", "logs", "documentation"],
    "issue": ["issue", "finding", "gap", "failure", "risk", "non-compliance"]
}


def _schemas_from_contextual_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert tables_with_columns from ContextualDataRetrievalAgent to schema shape for QA."""
    tables = result.get("tables_with_columns") or []
    schemas = []
    for t in tables:
        col_meta = t.get("column_metadata")
        if col_meta and isinstance(col_meta, list) and len(col_meta) > 0 and isinstance(col_meta[0], dict):
            column_metadata = list(col_meta)
        else:
            cols = t.get("columns") or []
            column_metadata = [{"column_name": c} for c in cols] if cols and isinstance(cols[0], str) else (cols or [])
        schemas.append({
            "table_name": t.get("table_name", ""),
            "table_ddl": t.get("table_ddl", ""),
            "column_metadata": column_metadata,
            "description": t.get("description", ""),
            "relationships": t.get("relationships", []),
        })
    return schemas


class ComplianceRetrievalNode:
    """Retrieves policy/controls/risks/edges via PolicyRetrievalAgent. Optionally runs contextual table retrieval when intent includes table_related."""

    def __init__(
        self,
        policy_retrieval_agent: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        framework: str = "SOC2",
        contextual_data_retrieval_agent: Optional[Any] = None,
        retrieval_helper: Optional[Any] = None,
    ):
        self.policy_retrieval_agent = policy_retrieval_agent
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.framework = (framework or "SOC2").upper()
        self.contextual_data_retrieval_agent = contextual_data_retrieval_agent
        self.retrieval_helper = retrieval_helper

    def _extract_framework(self, query: str, user_context: Dict[str, Any]) -> Optional[str]:
        if user_context.get("framework"):
            return str(user_context["framework"]).upper()
        query_lower = query.lower()
        for fw in ["SOC2", "SOC 2", "GDPR", "HIPAA", "PCI-DSS", "PCI DSS", "ISO27001", "NIST"]:
            if fw.lower() in query_lower:
                return fw.upper()
        return self.framework

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "") or (state.get("user_context") or {}).get("query", "")
        user_context = state.get("user_context", {}) or {}

        if not query:
            state["status"] = "error"
            state["error"] = "No query provided"
            state["compliance_data"] = {
                "summary": "",
                "documents": [],
                "edges": [],
                "store_results": {},
                "framework": self.framework,
                "breakdown": {},
                "schemas": [],
            }
            state["current_node"] = "compliance_retrieval"
            state["next_node"] = "compliance_qa"
            return _build_state_update(
                state,
                required_fields=["compliance_data", "current_node", "next_node"],
                optional_fields=["status", "error"],
            )

        query_plan = state.get("query_plan") or state.get("context_breakdown") or {}
        plan_frameworks = query_plan.get("frameworks")
        if plan_frameworks and isinstance(plan_frameworks, list) and len(plan_frameworks) > 0:
            framework = str(plan_frameworks[0]).upper()
        else:
            framework = self._extract_framework(query, user_context) or self.framework
        search_query = query_plan.get("user_intent") or query
        search_questions = query_plan.get("search_questions") or []
        if search_questions and isinstance(search_questions[0], dict) and search_questions[0].get("question"):
            search_query = search_questions[0].get("question") or search_query
        product_name = (user_context.get("product") or user_context.get("project_id") or state.get("project_id")) or None

        try:
            result = await self.policy_retrieval_agent.run(
                user_question=search_query,
                product_name=product_name,
                include_summary=True,
            )
            state["compliance_data"] = {
                "summary": result.get("summary", ""),
                "documents": result.get("documents", []),
                "edges": result.get("edges", []),
                "store_results": result.get("store_results", {}),
                "framework": framework,
                "breakdown": result.get("breakdown", {}),
                "schemas": [],
            }
            state["current_node"] = "compliance_retrieval"
            state["next_node"] = "compliance_qa"

            intent_plan = state.get("intent_plan") or {}
            query_types = intent_plan.get("query_types") or []
            wants_tables = "table_related" in query_types or "tables" in str(query_types).lower()
            project_id = state.get("project_id") or product_name
            if wants_tables and project_id and self.contextual_data_retrieval_agent:
                try:
                    session_cache = state.get("retrieval_session_cache")
                    if session_cache is None:
                        state["retrieval_session_cache"] = {}
                        session_cache = state["retrieval_session_cache"]
                    table_result = await self.contextual_data_retrieval_agent.run(
                        user_question=search_query,
                        product_name=project_id,
                        project_id=project_id,
                        include_table_schemas=True,
                        include_summary=False,
                        session_cache=session_cache,
                    )
                    schemas = _schemas_from_contextual_result(table_result)
                    state["compliance_data"]["schemas"] = schemas
                    if state.get("data_knowledge") is None:
                        state["data_knowledge"] = {}
                    state["data_knowledge"]["schemas"] = schemas
                    logger.info("Compliance retrieval: added %d tables from contextual table retrieval", len(schemas))
                except Exception as te:
                    logger.warning("Compliance table retrieval failed: %s", te)

            logger.info(
                "Compliance retrieval (policy agent): %d documents, %d edges, framework=%s",
                len(result.get("documents", [])),
                len(result.get("edges", [])),
                framework,
            )
        except Exception as e:
            logger.error(f"Compliance retrieval error: {e}", exc_info=True)
            state["compliance_data"] = {
                "summary": f"Retrieval failed: {e}",
                "documents": [],
                "edges": [],
                "store_results": {},
                "framework": framework,
                "breakdown": {},
                "schemas": [],
            }
            state["current_node"] = "compliance_retrieval"
            state["next_node"] = "compliance_qa"

        return _build_state_update(
            state,
            required_fields=["compliance_data", "current_node", "next_node"],
            optional_fields=["status", "error"],
        )


def _format_store_docs_for_qa(store_results: Dict[str, List[Dict]], max_chars: int = COMPLIANCE_QA_MAX_CHARS_PER_DOC) -> str:
    """Format retrieved store docs (controls, risks, etc.) so the QA LLM can cite specific items."""
    parts = []
    for store_name, docs in (store_results or {}).items():
        if not docs:
            continue
        label = store_name.replace("_new", "").replace("_", " ").title()
        parts.append(f"### {label}")
        for i, doc in enumerate(docs[:15], 1):
            content = (doc.get("content") or "").strip()
            meta = doc.get("metadata") or {}
            if content:
                if len(content) > max_chars:
                    content = content[:max_chars] + "..."
                parts.append(f"\n**Item {i}:**\n{content}")
            if meta:
                meta_str = ", ".join(f"{k}={v}" for k, v in list(meta.items())[:8])
                parts.append(f"  [Metadata: {meta_str}]")
        parts.append("")
    return "\n".join(parts).strip() or "(No retrieved content)"


def _format_edges_for_qa(edges: List[Dict], max_chars: int = 800) -> str:
    """Format edges for QA context."""
    if not edges:
        return "(No relationship edges)"
    parts = []
    for i, e in enumerate(edges[:20], 1):
        content = (e.get("content") or "").strip()
        meta = e.get("metadata") or {}
        if content:
            parts.append(f"{i}. {content[:max_chars]}" + ("..." if len(content) > max_chars else ""))
        elif meta:
            parts.append(f"{i}. {meta}")
    return "\n".join(parts) or "(No edge content)"


def _format_schemas_for_qa(schemas: List[Dict], max_tables: int = 10) -> str:
    """Format table schemas for QA when table retrieval was run."""
    if not schemas:
        return ""
    parts = ["### Relevant database tables (from table retrieval)"]
    for s in schemas[:max_tables]:
        name = s.get("table_name", s.get("name", "Unknown"))
        desc = (s.get("description") or "").strip()
        ddl = (s.get("table_ddl") or "").strip()
        parts.append(f"\n**{name}**" + (f": {desc}" if desc else ""))
        if ddl:
            parts.append(ddl[:1500] + ("..." if len(ddl) > 1500 else ""))
    return "\n".join(parts)


class ComplianceQANode:
    """Answers using retrieved controls, risks, and edges so the response cites specific items from the vector store."""

    def __init__(self, llm: Optional[ChatOpenAI] = None, model_name: str = "gpt-4o"):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "")
        compliance_data = state.get("compliance_data", {})
        summary = compliance_data.get("summary", "")
        documents = compliance_data.get("documents", [])
        edges = compliance_data.get("edges", [])
        framework = compliance_data.get("framework", "SOC2")
        store_results = compliance_data.get("store_results", {})
        deep_research_review = state.get("deep_research_review", {})
        data_knowledge = state.get("data_knowledge", {})
        schemas = data_knowledge.get("schemas", []) or compliance_data.get("schemas", [])

        retrieved_context = _format_store_docs_for_qa(store_results)
        edges_text = _format_edges_for_qa(edges)
        schemas_text = _format_schemas_for_qa(schemas) if schemas else ""

        if documents or edges or schemas:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a compliance expert. Answer the user's question using ONLY the retrieved controls, risks, and other policy content below. You MUST cite specific control IDs, risk names, and details from the retrieved content—do not give a generic answer. If the user asks about tables or data, use the Relevant database tables section when provided. Format your response in clear Markdown with headers and lists where appropriate."""),
                ("human", """Framework: {framework}

User question: {query}

## Retrieved controls, risks, and policy content (use these specifically)

{retrieved_context}

## Relationship edges

{edges_text}
{schemas_section}

Answer the question by citing the specific controls, risks, and content above. Do not invent or generalize—reference the retrieved items by name/ID."""),
            ])
            schema_section = "\n\n" + schemas_text if schemas_text else ""
            try:
                chain = prompt | self.llm
                response = await chain.ainvoke({
                    "framework": framework,
                    "query": query,
                    "retrieved_context": retrieved_context,
                    "edges_text": edges_text,
                    "schemas_section": schema_section,
                })
                answer = response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                logger.warning(f"ComplianceQANode LLM failed, using summary fallback: {e}")
                answer = summary or "No policy content was retrieved for this question."
        else:
            answer = summary or "No policy content was retrieved for this question."

        answer += f"\n\n*Retrieved: {len(documents)} document(s) from stores: {', '.join(store_results.keys()) or '—'}; {len(edges)} edge(s).*"

        if deep_research_review and deep_research_review.get("summary"):
            answer += "\n\n## Deep research (URL-based)\n\n" + (deep_research_review.get("summary", ""))
            rec = deep_research_review.get("recommended_features", [])
            plan = deep_research_review.get("evidence_gathering_plan", [])
            if rec or plan:
                answer += f"\n\n*Deep research: {len(rec)} recommended control(s), {len(plan)} evidence-gathering step(s).*"

        state["qa_answer"] = answer
        state["qa_sources"] = {
            "documents_count": len(documents),
            "edges_count": len(edges),
            "framework": framework,
            "stores": list(store_results.keys()),
            "deep_research_used": bool(deep_research_review and deep_research_review.get("summary")),
            "schemas_count": len(schemas),
        }
        state["qa_confidence"] = 0.9 if (documents or edges or (deep_research_review and deep_research_review.get("summary")) or schemas) else 0.5
        state["current_node"] = "compliance_qa"
        state["next_node"] = "writer_agent"
        return _build_state_update(
            state,
            required_fields=["qa_answer", "qa_sources", "qa_confidence", "current_node", "next_node"],
        )
