"""
Domain Knowledge assistance nodes: retrieval from domain_knowledge, entities, playbooks
per general_prompts (domain_knowledge_assistant – domains and docs).
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.assistants.state import ContextualAssistantState

logger = logging.getLogger(__name__)


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


class DomainKnowledgeRetrievalNode:
    """Retrieves domain docs, entities, playbooks using CollectionFactory (same pattern as product/compliance)."""

    def __init__(
        self,
        collection_factory: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        top_k: int = 10,
    ):
        self.collection_factory = collection_factory
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.top_k = top_k

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "") or (state.get("user_context") or {}).get("query", "")
        if not query:
            state["status"] = "error"
            state["error"] = "No query provided"
            state["domain_knowledge_data"] = {"documents": [], "sources": []}
            state["current_node"] = "domain_knowledge_retrieval"
            state["next_node"] = "qa_agent"
            return state

        query_plan = state.get("query_plan") or state.get("context_breakdown") or {}
        search_questions = query_plan.get("search_questions") or []
        use_plan = bool(search_questions and isinstance(search_questions[0], dict))

        documents = []
        sources = []

        logger.info(
            "[Doc retrieval] Domain knowledge assistant start: query=%s, use_search_plan=%s, top_k=%s, search_questions=%s",
            (query or "")[:200], use_plan, self.top_k, len(search_questions) if use_plan else 0,
        )

        try:
            if use_plan:
                for sq in search_questions[:5]:
                    q = sq.get("question") or query
                    filters = sq.get("metadata_filters") or {}
                    entity = (sq.get("entity") or "").lower()
                    if "domain_knowledge" in entity or "playbook" in entity or "procedure" in entity or not entity:
                        if getattr(self.collection_factory, "domain_collections", {}).get("domain_knowledge"):
                            try:
                                where = {**filters} if filters else {}
                                logger.info("[Doc retrieval] Query to collection: collection=domain_knowledge, query=%s, top_k=%s", (q or "")[:150], self.top_k)
                                domain_results = await self.collection_factory.domain_collections["domain_knowledge"].hybrid_search(
                                    query=q, top_k=self.top_k, where=where
                                )
                                for r in domain_results:
                                    documents.append({
                                        "content": r.get("content", ""),
                                        "metadata": r.get("metadata", {}),
                                        "collection_name": "domain_knowledge",
                                        "score": r.get("combined_score"),
                                    })
                                if domain_results:
                                    sources.append("domain_knowledge")
                                logger.info("[Doc retrieval] Retrieved: collection=domain_knowledge, count=%s, preview=%s", len(domain_results), (domain_results[0].get("content", "")[:80] + "..." if domain_results else "none"))
                            except Exception as e:
                                logger.warning(f"Domain knowledge search failed: {e}")
                    if "entities" in entity or "entity" in entity or not entity:
                        if getattr(self.collection_factory, "domain_collections", {}).get("entities"):
                            try:
                                where = {**filters} if filters else {}
                                logger.info("[Doc retrieval] Query to collection: collection=entities, query=%s, top_k=5", (q or "")[:150])
                                entity_results = await self.collection_factory.domain_collections["entities"].hybrid_search(
                                    query=q, top_k=5, where=where
                                )
                                for r in entity_results:
                                    documents.append({
                                        "content": r.get("content", ""),
                                        "metadata": r.get("metadata", {}),
                                        "collection_name": "entities",
                                        "score": r.get("combined_score"),
                                    })
                                if entity_results:
                                    sources.append("entities")
                                logger.info("[Doc retrieval] Retrieved: collection=entities, count=%s, preview=%s", len(entity_results), (entity_results[0].get("content", "")[:80] + "..." if entity_results else "none"))
                            except Exception as e:
                                logger.warning(f"Entities search failed: {e}")
                    if "compliance_controls" in entity:
                        if getattr(self.collection_factory, "compliance_collections", {}).get("compliance_controls"):
                            try:
                                where = {**filters} if filters else {}
                                logger.info("[Doc retrieval] Query to collection: collection=compliance_controls, query=%s, top_k=5", (q or "")[:150])
                                ctrl_results = await self.collection_factory.compliance_collections["compliance_controls"].hybrid_search(
                                    query=q, top_k=5, where=where
                                )
                                for r in ctrl_results:
                                    documents.append({
                                        "content": r.get("content", ""),
                                        "metadata": r.get("metadata", {}),
                                        "collection_name": "compliance_controls",
                                        "score": r.get("combined_score"),
                                    })
                                if ctrl_results:
                                    sources.append("compliance_controls")
                                logger.info("[Doc retrieval] Retrieved: collection=compliance_controls, count=%s, preview=%s", len(ctrl_results), (ctrl_results[0].get("content", "")[:80] + "..." if ctrl_results else "none"))
                            except Exception as e:
                                logger.warning(f"Compliance controls search failed: {e}")
            if not documents:
                use_plan = False
            if not use_plan:
                logger.info("[Doc retrieval] Domain knowledge fallback: querying all collections with query=%s", (query or "")[:200])
                if getattr(self.collection_factory, "domain_collections", {}).get("domain_knowledge"):
                    try:
                        logger.info("[Doc retrieval] Query to collection: collection=domain_knowledge, query=%s, top_k=%s", (query or "")[:150], self.top_k)
                        domain_results = await self.collection_factory.domain_collections["domain_knowledge"].hybrid_search(
                            query=query, top_k=self.top_k
                        )
                        for r in domain_results:
                            documents.append({
                                "content": r.get("content", ""),
                                "metadata": r.get("metadata", {}),
                                "collection_name": "domain_knowledge",
                                "score": r.get("combined_score"),
                            })
                        if domain_results:
                            sources.append("domain_knowledge")
                        logger.info("[Doc retrieval] Retrieved: collection=domain_knowledge, count=%s, preview=%s", len(domain_results), (domain_results[0].get("content", "")[:80] + "..." if domain_results else "none"))
                    except Exception as e:
                        logger.warning(f"Domain knowledge search failed: {e}")
                if getattr(self.collection_factory, "domain_collections", {}).get("entities"):
                    try:
                        logger.info("[Doc retrieval] Query to collection: collection=entities, query=%s, top_k=5", (query or "")[:150])
                        entity_results = await self.collection_factory.domain_collections["entities"].hybrid_search(
                            query=query, top_k=5
                        )
                        for r in entity_results:
                            documents.append({
                                "content": r.get("content", ""),
                                "metadata": r.get("metadata", {}),
                                "collection_name": "entities",
                                "score": r.get("combined_score"),
                            })
                        if entity_results:
                            sources.append("entities")
                        logger.info("[Doc retrieval] Retrieved: collection=entities, count=%s, preview=%s", len(entity_results), (entity_results[0].get("content", "")[:80] + "..." if entity_results else "none"))
                    except Exception as e:
                        logger.warning(f"Entities search failed: {e}")

            seen = set()
            unique_docs = []
            for d in documents:
                key = (d.get("content", "")[:200], d.get("collection_name"))
                if key not in seen:
                    seen.add(key)
                    unique_docs.append(d)
            documents = unique_docs[: self.top_k]

            state["domain_knowledge_data"] = {
                "documents": documents,
                "sources": list(set(sources)),
                "query": query,
            }
            state["current_node"] = "domain_knowledge_retrieval"
            state["next_node"] = "qa_agent"
            logger.info(
                "[Doc retrieval] Domain knowledge summary: total_docs=%s, sources=%s, query=%s",
                len(documents), list(set(sources)), (query or "")[:100],
            )
        except Exception as e:
            logger.error(f"Domain knowledge retrieval error: {e}", exc_info=True)
            state["domain_knowledge_data"] = {"documents": [], "sources": [], "query": query}
            state["current_node"] = "domain_knowledge_retrieval"
            state["next_node"] = "qa_agent"

        return _build_state_update(
            state,
            required_fields=["domain_knowledge_data", "current_node", "next_node"],
            optional_fields=["status", "error"],
        )


class DomainKnowledgeQANode:
    """Composes answer from domain_knowledge_data (summary or list with summary)."""

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "")
        domain_data = state.get("domain_knowledge_data", {})
        documents = domain_data.get("documents", [])[:10]
        sources = domain_data.get("sources", [])

        context_str = "\n\n---\n\n".join(
            f"[{d.get('collection_name', '')}] {d.get('content', '')[:2000]}"
            for d in documents
        ) or "No domain documents retrieved."

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a domain knowledge assistant. Use the retrieved domain docs, playbooks, entities, and compliance references to answer the user's question.

- Target roles: knowledge manager, security engineer, HR compliance officer.
- Prefer a concise summary when the question asks for an overview or "what is".
- When the user asks for a list or "which/where", structure the response as a list or table.
- Cite which source (domain_knowledge, entities, compliance_controls) the information came from when relevant.
- If little or no relevant context was retrieved, say so and suggest rephrasing or broader terms.
- Use clear markdown formatting."""),
            ("human", """User question: {query}

Retrieved domain context (from {sources}):
{context}

Answer based on the above. Prefer summary or list format as appropriate.""")
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "query": query,
            "sources": ", ".join(sources) or "none",
            "context": context_str,
        })
        answer = response.content if hasattr(response, "content") else str(response)

        state["qa_answer"] = answer
        state["qa_sources"] = {"documents_count": len(documents), "sources": sources}
        state["qa_confidence"] = 0.85 if documents else 0.5
        state["current_node"] = "qa_agent"
        state["next_node"] = "writer_agent"
        return _build_state_update(
            state,
            required_fields=["qa_answer", "qa_sources", "qa_confidence", "current_node", "next_node"],
        )
