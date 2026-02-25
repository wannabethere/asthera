"""
Policy Retrieval Agent
LangChain-style agent that breaks down policy-related questions by policy preview stores,
retrieves via RetrievalHelper (same interface as MDL stores; policy stores are in CollectionFactory),
summarizes the information, and returns retrieved documents and edges.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from app.utils.prompts.policy_retrieval_prompts import (
    get_policy_retrieval_system_prompt,
    get_policy_retrieval_examples_text,
    get_policy_retrieval_summary_prompt,
)

logger = logging.getLogger(__name__)

# Max characters per retrieved doc to include in summary context (avoid token overflow)
SUMMARY_CONTEXT_MAX_CHARS_PER_DOC = 600

# Policy preview store names (must match CollectionFactory policy_preview_collections)
POLICY_PREVIEW_STORES = [
    "controls_new",
    "risks_new",
    "key_concepts_new",
    "identifiers_new",
    "framework_docs_new",
    "edges_new",
]


class PolicyRetrievalAgent:
    """
    Agent that processes policy-related questions by:
    1. Breaking down the question by policy entities/stores (LLM).
    2. Generating a sub-question per relevant store.
    3. Retrieving from all relevant policy stores in parallel via RetrievalHelper.
    4. Summarizing retrieved content (LLM).
    5. Returning retrieved documents, edges (from edges_new), and summary.
    """

    def __init__(
        self,
        retrieval_helper: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        top_k_per_store: int = 10,
    ):
        """
        Args:
            retrieval_helper: RetrievalHelper instance. Used for policy store retrieval via
                retrieve_from_mdl_stores (CollectionFactory must include policy preview stores:
                controls_new, risks_new, key_concepts_new, identifiers_new, framework_docs_new, edges_new).
            llm: Optional LLM for breakdown and summary steps.
            model_name: Model name if llm not provided.
            top_k_per_store: Max documents to retrieve per store (default 10).
        """
        self.retrieval_helper = retrieval_helper
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.top_k_per_store = top_k_per_store
        self._parser = JsonOutputParser()

    async def breakdown_question(
        self,
        user_question: str,
        product_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to break down the user question into store-specific retrieval queries.

        Returns:
            Dict with store_queries (list of {store, query}), product_name, categories.
        """
        system = (
            get_policy_retrieval_system_prompt()
            + "\n\nExamples:\n"
            + get_policy_retrieval_examples_text()
        )
        human = (
            "User question: {user_question}\n"
            "Product (if known): {product_name}\n\n"
            "Output valid JSON with: store_queries (list of {{ \"store\": \"<store_name>\", \"query\": \"<sub-question>\" }}), "
            "product_name (string or null), categories (list of strings or empty)."
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            ("human", human),
        ])
        chain = prompt | self.llm | self._parser
        try:
            result = await chain.ainvoke({
                "user_question": user_question,
                "product_name": product_name or "",
            })
        except Exception as e:
            logger.warning(f"Policy breakdown LLM failed, using fallback: {e}")
            result = {
                "store_queries": [
                    {"store": "controls_new", "query": user_question},
                    {"store": "key_concepts_new", "query": user_question},
                    {"store": "edges_new", "query": user_question},
                ],
                "product_name": product_name,
                "categories": [],
            }

        store_queries = result.get("store_queries") or []
        normalized = []
        for sq in store_queries:
            store = (sq.get("store") or "").strip()
            query = (sq.get("query") or user_question).strip()
            if store in POLICY_PREVIEW_STORES and query:
                normalized.append({"store": store, "query": query})
        result["store_queries"] = normalized
        result["product_name"] = result.get("product_name") or product_name
        result["categories"] = result.get("categories") or []
        return result

    async def retrieve_from_stores(
        self,
        store_queries: List[Dict[str, str]],
        product_name: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve from policy preview stores in parallel via RetrievalHelper.
        Uses retrieve_from_mdl_stores (policy store names are resolved by CollectionFactory).
        Returns dict keyed by store name.
        """
        if not self.retrieval_helper or not hasattr(
            self.retrieval_helper, "retrieve_from_mdl_stores"
        ):
            logger.warning(
                "PolicyRetrievalAgent: retrieval_helper or retrieve_from_mdl_stores not available"
            )
            return {}
        return await self.retrieval_helper.retrieve_from_mdl_stores(
            store_queries=store_queries,
            product_name=product_name,
            categories=categories,
            top_k=self.top_k_per_store,
        )

    def _build_summary_context(
        self,
        store_results: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Build a condensed context string for the summary LLM."""
        parts = []
        for store, docs in store_results.items():
            if not docs:
                continue
            parts.append(f"### {store}")
            for doc in docs[:5]:
                content = (doc.get("content") or "").strip()
                if content:
                    if len(content) > SUMMARY_CONTEXT_MAX_CHARS_PER_DOC:
                        content = (
                            content[:SUMMARY_CONTEXT_MAX_CHARS_PER_DOC] + "..."
                        )
                    parts.append(content)
                meta = doc.get("metadata") or {}
                if meta:
                    meta_str = ", ".join(
                        f"{k}={v}" for k, v in list(meta.items())[:6]
                    )
                    parts.append(f"  [metadata: {meta_str}]")
            parts.append("")
        return "\n".join(parts).strip() or "(No retrieved content)"

    def _extract_edges(
        self,
        store_results: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Extract edge documents from edges_new store for explicit return."""
        edges_docs = store_results.get("edges_new") or []
        return [
            {"content": d.get("content", ""), "metadata": d.get("metadata", {})}
            for d in edges_docs
        ]

    def _flatten_documents(
        self,
        store_results: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Flatten store_results into a list of docs with store name in metadata."""
        out = []
        for store, docs in store_results.items():
            for d in docs:
                row = dict(d)
                meta = dict(row.get("metadata") or {})
                meta["_store"] = store
                row["metadata"] = meta
                out.append(row)
        return out

    async def _generate_summary_markdown(
        self,
        user_question: str,
        store_results: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Call LLM to produce a markdown summary of policy docs and edges."""
        context_blob = self._build_summary_context(store_results)
        system_prompt, human_template = get_policy_retrieval_summary_prompt()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_template),
        ])
        chain = prompt | self.llm
        try:
            msg = await chain.ainvoke({
                "user_question": user_question,
                "context_blob": context_blob,
            })
            summary = msg.content if hasattr(msg, "content") else str(msg)
            return (summary or "").strip()
        except Exception as e:
            logger.warning(f"Policy summary LLM failed: {e}")
            fallback = [
                f"Retrieved from {len(store_results)} stores: "
                + ", ".join(store_results.keys())
            ]
            return ". ".join(fallback)

    async def run(
        self,
        user_question: str,
        product_name: Optional[str] = None,
        include_summary: bool = True,
    ) -> Dict[str, Any]:
        """
        Full pipeline: breakdown → parallel retrieval → optional summary (LLM).
        Returns retrieved documents, edges, and summary.

        Args:
            user_question: The policy-related question.
            product_name: Optional product/tenant for filtering.
            include_summary: If True, call LLM to generate markdown summary.

        Returns:
            Dict with:
            - breakdown: result of breakdown_question
            - store_results: dict store_name -> list of retrieved docs (content, metadata)
            - documents: flattened list of all retrieved docs with metadata._store
            - edges: list of docs from edges_new (content, metadata)
            - summary: LLM-generated markdown summary (or short fallback)
        """
        breakdown = await self.breakdown_question(user_question, product_name)
        store_queries = breakdown.get("store_queries") or []
        product = breakdown.get("product_name") or product_name
        categories = breakdown.get("categories") or []

        store_results = await self.retrieve_from_stores(
            store_queries, product, categories
        )

        edges = self._extract_edges(store_results)
        documents = self._flatten_documents(store_results)

        if include_summary:
            summary = await self._generate_summary_markdown(
                user_question, store_results
            )
        else:
            summary = (
                f"Retrieved from {len(store_results)} stores: "
                + ", ".join(store_results.keys())
                + f". {len(documents)} documents, {len(edges)} edges."
            )

        return {
            "breakdown": breakdown,
            "store_results": store_results,
            "documents": documents,
            "edges": edges,
            "summary": summary,
            "user_question": user_question,
        }
