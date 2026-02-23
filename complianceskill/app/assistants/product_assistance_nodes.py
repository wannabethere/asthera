"""
Product assistance nodes: retrieval from product docs, framework, and MDL tables (same style as Knowledge assistant).
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.assistants.state import ContextualAssistantState
from app.utils.serialization import to_native_types

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


class ProductRetrievalNode:
    """Retrieves product docs, features, entities, and MDL/schema info using CollectionFactory (same style as Knowledge retrieval)."""

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

    async def _search_table_descriptions(self, query: str, table_where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search table_descriptions with optional contextual filter (suggested_table_names). Same methodology as data assistance."""
        coll = getattr(self.collection_factory, "schema_collections", {}).get("table_descriptions")
        if not coll:
            return []
        try:
            if table_where:
                results = await coll.hybrid_search(query=query, top_k=self.top_k, where=table_where)
                if results:
                    return results
        except Exception as e:
            logger.debug("[Doc retrieval] table_descriptions where filter failed, falling back to unfiltered: %s", e)
        results = await coll.hybrid_search(query=query, top_k=self.top_k * 2)
        if not table_where or not results:
            return results[: self.top_k]
        # Reorder: suggested tables first (same contextual-edge priority as data assistance)
        suggested_set = set()
        if isinstance(table_where.get("table_name"), dict) and "$in" in table_where["table_name"]:
            suggested_set = set(table_where["table_name"]["$in"])
        in_suggested = [r for r in results if (r.get("metadata") or {}).get("table_name") in suggested_set]
        other = [r for r in results if (r.get("metadata") or {}).get("table_name") not in suggested_set]
        return (in_suggested + other)[: self.top_k]

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "") or (state.get("user_context") or {}).get("query", "")
        if not query:
            state["status"] = "error"
            state["error"] = "No query provided"
            state["product_data"] = {"documents": [], "sources": []}
            state["current_node"] = "product_retrieval"
            state["next_node"] = "product_qa"
            return state

        # Same methodology as DataKnowledgeRetrievalNode: use context_ids and suggested_tables from framework
        user_context = state.get("user_context", {}) or {}
        context_ids = state.get("context_ids", []) or user_context.get("context_ids", [])
        suggested_tables = state.get("suggested_tables", [])
        suggested_table_names = None
        if suggested_tables:
            names = [t.get("table_name") for t in suggested_tables if t.get("table_name")]
            if names:
                suggested_table_names = names
                logger.info("[Doc retrieval] Using %s suggested tables from contextual reasoning: %s", len(names), names[:5])

        query_plan = state.get("query_plan") or state.get("context_breakdown") or {}
        retrieval_query = query
        if query_plan:
            retrieval_query = query_plan.get("user_intent") or query
            search_questions = query_plan.get("search_questions") or []
            if search_questions and isinstance(search_questions[0], dict) and search_questions[0].get("question"):
                retrieval_query = search_questions[0].get("question") or retrieval_query
        search_questions = query_plan.get("search_questions") or []
        use_plan = bool(search_questions and isinstance(search_questions[0], dict))

        # Build filters from contextual edges (same as data assistance)
        feature_where = {}
        if context_ids:
            feature_where["context_id"] = context_ids[0]
        table_where = None
        if suggested_table_names:
            table_where = {"table_name": {"$in": suggested_table_names}}

        documents = []
        sources = []

        logger.info(
            "[Doc retrieval] Product assistant start: query=%s, use_search_plan=%s, top_k=%s, context_ids=%s, suggested_tables=%s",
            (query or "")[:200], use_plan, self.top_k, len(context_ids) if context_ids else 0, len(suggested_table_names) if suggested_table_names else 0,
        )

        try:
            if use_plan:
                for sq in search_questions[:5]:
                    q = sq.get("question") or query
                    filters = sq.get("metadata_filters") or {}
                    entity = (sq.get("entity") or "").lower()
                    if "product" in entity or "product_knowledge" in entity or "product_entities" in entity or "product_descriptions" in entity:
                        if hasattr(self.collection_factory, "search_connectors"):
                            try:
                                logger.info("[Doc retrieval] Query to collection: collection=search_connectors (product), query=%s, top_k=%s", (q or "")[:150], self.top_k)
                                product_results = await self.collection_factory.search_connectors(
                                    query=q, top_k=self.top_k, filters=filters or {"type": "product"}
                                )
                                for r in product_results:
                                    documents.append({"content": r.get("content", ""), "metadata": r.get("metadata", {}), "collection_name": r.get("collection_name", "domain_knowledge"), "score": r.get("combined_score")})
                                if product_results:
                                    sources.append("domain_knowledge (product)")
                                logger.info("[Doc retrieval] Retrieved: collection=search_connectors (product), count=%s, preview=%s", len(product_results), (product_results[0].get("content", "")[:80] + "..." if product_results else "none"))
                            except Exception as e:
                                logger.warning(f"Product search_connectors failed: {e}")
                    if "domain_knowledge" in entity or "features" in entity or not entity:
                        if getattr(self.collection_factory, "domain_collections", {}).get("domain_knowledge"):
                            try:
                                where = {**filters} if filters else {"type": "product"}
                                logger.info("[Doc retrieval] Query to collection: collection=domain_knowledge, query=%s, top_k=%s", (q or "")[:150], self.top_k)
                                domain_results = await self.collection_factory.domain_collections["domain_knowledge"].hybrid_search(query=q, top_k=self.top_k, where=where)
                                for r in domain_results:
                                    documents.append({"content": r.get("content", ""), "metadata": r.get("metadata", {}), "collection_name": "domain_knowledge", "score": r.get("combined_score")})
                                if domain_results:
                                    sources.append("domain_knowledge")
                                logger.info("[Doc retrieval] Retrieved: collection=domain_knowledge, count=%s, preview=%s", len(domain_results), (domain_results[0].get("content", "")[:80] + "..." if domain_results else "none"))
                            except Exception as e:
                                logger.warning(f"Domain product search failed: {e}")
                    if "features" in entity or not entity:
                        if getattr(self.collection_factory, "feature_collections", {}).get("features"):
                            try:
                                logger.info("[Doc retrieval] Query to collection: collection=features, query=%s, top_k=%s, context_id=%s", (q or "")[:150], self.top_k, context_ids[0] if context_ids else None)
                                feat_results = await self.collection_factory.feature_collections["features"].hybrid_search(
                                    query=q, top_k=self.top_k, where=feature_where if feature_where else None
                                )
                                for r in feat_results:
                                    documents.append({"content": r.get("content", ""), "metadata": r.get("metadata", {}), "collection_name": "features", "score": r.get("combined_score")})
                                if feat_results:
                                    sources.append("features")
                                logger.info("[Doc retrieval] Retrieved: collection=features, count=%s, preview=%s", len(feat_results), (feat_results[0].get("content", "")[:80] + "..." if feat_results else "none"))
                            except Exception as e:
                                logger.warning(f"Features search failed: {e}")
                    if "table" in entity or "schema" in entity or not entity:
                        if getattr(self.collection_factory, "schema_collections", {}).get("table_descriptions"):
                            try:
                                schema_results = await self._search_table_descriptions(q, table_where)
                                if schema_results:
                                    for r in schema_results:
                                        documents.append({"content": r.get("content", ""), "metadata": r.get("metadata", {}), "collection_name": "table_descriptions", "score": r.get("combined_score")})
                                    sources.append("table_descriptions")
                                    logger.info("[Doc retrieval] Retrieved: collection=table_descriptions, count=%s (contextual tables=%s)", len(schema_results), bool(table_where))
                            except Exception as e:
                                logger.warning(f"Table descriptions search failed: {e}")
            if not documents:
                use_plan = False
            if not use_plan:
                # Fallback: single query across allowed product sources; use retrieval_query and contextual filters (same as data assistance)
                logger.info("[Doc retrieval] Fallback mode: querying all product collections with retrieval_query=%s, context_ids=%s", (retrieval_query or "")[:200], len(context_ids) if context_ids else 0)
                if hasattr(self.collection_factory, "search_connectors"):
                    try:
                        logger.info("[Doc retrieval] Query to collection: collection=search_connectors (product), query=%s, top_k=%s", (retrieval_query or "")[:150], self.top_k)
                        product_results = await self.collection_factory.search_connectors(
                            query=retrieval_query,
                            top_k=self.top_k,
                            filters={"type": "product"},
                        )
                        for r in product_results:
                            documents.append({
                                "content": r.get("content", ""),
                                "metadata": r.get("metadata", {}),
                                "collection_name": r.get("collection_name", "domain_knowledge"),
                                "score": r.get("combined_score"),
                            })
                        if product_results:
                            sources.append("domain_knowledge (product)")
                        logger.info("[Doc retrieval] Retrieved: collection=search_connectors (product), count=%s, preview=%s", len(product_results), (product_results[0].get("content", "")[:80] + "..." if product_results else "none"))
                    except Exception as e:
                        logger.warning(f"Product search_connectors failed: {e}")

                if "domain_knowledge" in getattr(self.collection_factory, "domain_collections", {}):
                    try:
                        logger.info("[Doc retrieval] Query to collection: collection=domain_knowledge, query=%s, top_k=%s", (retrieval_query or "")[:150], self.top_k)
                        domain_results = await self.collection_factory.domain_collections["domain_knowledge"].hybrid_search(
                            query=retrieval_query,
                            top_k=self.top_k,
                            where={"type": "product"},
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
                        logger.warning(f"Domain product search failed: {e}")

                if getattr(self.collection_factory, "feature_collections", {}).get("features"):
                    try:
                        logger.info("[Doc retrieval] Query to collection: collection=features, query=%s, top_k=%s, context_id=%s", (retrieval_query or "")[:150], self.top_k, context_ids[0] if context_ids else None)
                        feat_results = await self.collection_factory.feature_collections["features"].hybrid_search(
                            query=retrieval_query,
                            top_k=self.top_k,
                            where=feature_where if feature_where else None,
                        )
                        for r in feat_results:
                            documents.append({
                                "content": r.get("content", ""),
                                "metadata": r.get("metadata", {}),
                                "collection_name": "features",
                                "score": r.get("combined_score"),
                            })
                        if feat_results:
                            sources.append("features")
                        logger.info("[Doc retrieval] Retrieved: collection=features, count=%s, preview=%s", len(feat_results), (feat_results[0].get("content", "")[:80] + "..." if feat_results else "none"))
                    except Exception as e:
                        logger.warning(f"Features search failed: {e}")

                schema_results = await self._search_table_descriptions(retrieval_query, table_where)
                if schema_results:
                    for r in schema_results:
                        documents.append({
                            "content": r.get("content", ""),
                            "metadata": r.get("metadata", {}),
                            "collection_name": "table_descriptions",
                            "score": r.get("combined_score"),
                        })
                    sources.append("table_descriptions")
                    logger.info("[Doc retrieval] Retrieved: collection=table_descriptions, count=%s (contextual tables=%s)", len(schema_results), bool(table_where))

            # Dedupe by content hash and limit total
            seen = set()
            unique_docs = []
            for d in documents:
                key = (d.get("content", "")[:200], d.get("collection_name"))
                if key not in seen:
                    seen.add(key)
                    unique_docs.append(d)
            documents = unique_docs[: self.top_k]

            # Ensure msgpack-serializable (e.g. numpy scores -> native float)
            state["product_data"] = to_native_types({
                "documents": documents,
                "sources": list(set(sources)),
                "query": query,
            })
            state["current_node"] = "product_retrieval"
            state["next_node"] = "product_qa"
            logger.info(
                "[Doc retrieval] Product assistant summary: total_docs=%s, sources=%s, query=%s",
                len(documents), list(set(sources)), (query or "")[:100],
            )
        except Exception as e:
            logger.error(f"Product retrieval error: {e}", exc_info=True)
            state["product_data"] = {"documents": [], "sources": [], "query": query}
            state["current_node"] = "product_retrieval"
            state["next_node"] = "product_qa"

        return _build_state_update(
            state,
            required_fields=["product_data", "current_node", "next_node"],
            optional_fields=["status", "error"],
        )


class ProductQANode:
    """Composes answer from product_data (summary or list of documents with summary), same style as KnowledgeQANode."""

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        query = state.get("query", "")
        product_data = state.get("product_data", {})
        documents = product_data.get("documents", [])[:20]
        sources = product_data.get("sources", [])

        context_str = "\n\n---\n\n".join(
            f"[{d.get('collection_name', '')}] {d.get('content', '')[:2000]}"
            for d in documents
        ) or "No product documents retrieved."

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a product documentation assistant. Use the retrieved product docs, features, and schema/MDL information to answer the user's question.

- Prefer a concise summary when the question asks for an overview or "what is".
- When the user asks for a list, "which/where", or about tables/schema: if the context contains multiple tables or schema items, present each in its own markdown table or clearly separated section—do not merge into a single table. Use one table per distinct table/schema entity when there are several.
- When there is only one relevant item, a single table is fine.
- Cite which source (domain_knowledge, features, table_descriptions) the information came from when relevant.
- If little or no relevant context was retrieved, say so and suggest rephrasing or broader terms.
- Use clear markdown formatting."""),
            ("human", """User question: {query}

Retrieved product context (from {sources}):
{context}

Answer based on the above. If the context has multiple tables/schema items, show each in its own table or section. Prefer summary or list format only when a single item is relevant.""")
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "query": query,
            "sources": ", ".join(sources) or "none",
            "context": context_str,
        })
        answer = response.content if hasattr(response, "content") else str(response)

        state["qa_answer"] = answer
        state["qa_sources"] = to_native_types({"documents_count": len(documents), "sources": sources})
        state["qa_confidence"] = float(0.85 if documents else 0.5)
        state["current_node"] = "product_qa"
        state["next_node"] = "writer_agent"
        return _build_state_update(
            state,
            required_fields=["qa_answer", "qa_sources", "qa_confidence", "current_node", "next_node"],
        )
