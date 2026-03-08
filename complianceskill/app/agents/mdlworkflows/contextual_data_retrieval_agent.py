"""
Contextual Data Retrieval Agent
LangChain-style agent that breaks down data-related questions by MDL entities/collections,
retrieves from MDL preview stores in parallel, and returns summarized context with tables and columns.
Column pruning is skipped when the user's question is column-specific.
"""
import asyncio
import re
import logging
from typing import Dict, List, Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from app.utils.prompts.data_retrieval_prompts import (
    get_data_retrieval_system_prompt,
    get_data_retrieval_examples_text,
    get_data_retrieval_summary_prompt,
    get_data_retrieval_score_prune_prompt,
)

logger = logging.getLogger(__name__)

# No truncation: include full content so summary nodes do not remove information
SUMMARY_CONTEXT_MAX_CHARS_PER_DOC = None

# MDL preview store names (must match ingest_preview_files / RetrievalHelper MDL stores)
MDL_PREVIEW_STORES = [
    "mdl_key_concepts",
    "mdl_patterns",
    "mdl_evidences",
    "mdl_fields",
    "mdl_metrics",
    "mdl_edges_table",
    "mdl_edges_column",
    "mdl_category_enrichment",
]


def _extract_table_names_from_question(question: str) -> List[str]:
    """Extract table names from a question when user asks about columns in specific table(s).
    E.g. 'What columns are in the DirectVulnerabilities table, issues' -> ['DirectVulnerabilities', 'Issues']
    """
    if not question or not isinstance(question, str):
        return []
    names = []
    # "in the X table" or "for the X table" or "in X table"
    for m in re.finditer(r"\b(?:in|for)\s+(?:the\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+table\b", question, re.IGNORECASE):
        names.append(m.group(1))
    # "X table, Y" or "X table and Y" (second table name after comma/and)
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+table\s*[,]\s*([A-Za-z_][A-Za-z0-9_]*)", question, re.IGNORECASE):
        if m.group(1) not in names:
            names.append(m.group(1))
        # Capitalize second name as table name (e.g. issues -> Issues)
        second = m.group(2).strip()
        if second and second not in names:
            names.append(second[0].upper() + second[1:] if len(second) > 1 else second.upper())
    return list(dict.fromkeys(names))  # preserve order, dedupe


class ContextualDataRetrievalAgent:
    """
    Agent that processes data-related questions by:
    1. Breaking down the question by MDL entities/collections (LLM).
    2. Generating a sub-question per relevant store.
    3. Retrieving from all relevant stores in parallel.
    4. Optionally fetching full table/column context via retrieval_helper.
    5. Summarizing and returning store results plus tables with columns.
    Column pruning is not applied when the question is column-specific.
    """

    def __init__(
        self,
        retrieval_helper: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        top_k_per_store: int = 10,
        max_tables: Optional[int] = 10,
        max_metrics: Optional[int] = 10,
    ):
        """
        Args:
            retrieval_helper: RetrievalHelper instance. Used for get_database_schemas (tables + columns)
                and for MDL store retrieval via retrieve_from_mdl_stores (ensure RetrievalHelper was
                constructed with collection_factory for MDL preview stores).
            llm: Optional LLM for breakdown step.
            model_name: Model name if llm not provided.
            top_k_per_store: Max documents to retrieve per store (default 10).
            max_tables: Max tables to keep after LLM scoring/prune (default 10). None = no pruning.
            max_metrics: Max metrics to keep after LLM scoring/prune (default 10). None = no pruning.
        """
        self.retrieval_helper = retrieval_helper
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.top_k_per_store = top_k_per_store
        self.max_tables = max_tables
        self.max_metrics = max_metrics
        self._parser = JsonOutputParser()

    async def breakdown_question(
        self,
        user_question: str,
        product_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to break down the user question into store-specific retrieval queries.

        Returns:
            Dict with store_queries (list of {store, query}), is_column_specific, product_name, categories.
        """
        system = get_data_retrieval_system_prompt() + "\n\nExamples:\n" + get_data_retrieval_examples_text()
        human = (
            "User question: {user_question}\n"
            "Product (if known): {product_name}\n\n"
            "Output valid JSON with: store_queries (list of {{ \"store\": \"<store_name>\", \"query\": \"<sub-question>\" }}), "
            "is_column_specific (boolean), requested_table_names (list of table names the user asked about, e.g. [\"DirectVulnerabilities\", \"Issues\"] or []), "
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
            logger.warning(f"Breakdown LLM failed, using fallback: {e}")
            result = {
                "store_queries": [
                    {"store": "mdl_key_concepts", "query": user_question},
                    {"store": "mdl_patterns", "query": user_question},
                ],
                "is_column_specific": "column" in user_question.lower() or "field" in user_question.lower(),
                "requested_table_names": _extract_table_names_from_question(user_question),
                "product_name": product_name,
                "categories": [],
            }

        store_queries = result.get("store_queries") or []
        # Normalize store names and filter to known MDL preview stores
        normalized = []
        for sq in store_queries:
            store = (sq.get("store") or "").strip()
            query = (sq.get("query") or user_question).strip()
            if store in MDL_PREVIEW_STORES and query:
                normalized.append({"store": store, "query": query})
        result["store_queries"] = normalized
        result["is_column_specific"] = bool(result.get("is_column_specific"))
        requested = result.get("requested_table_names")
        if isinstance(requested, list) and requested:
            result["requested_table_names"] = [str(t).strip() for t in requested if t]
        else:
            result["requested_table_names"] = _extract_table_names_from_question(user_question) if result.get("is_column_specific") else []
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
        Retrieve from MDL preview stores in parallel via RetrievalHelper. Returns dict keyed by store name.
        """
        if not self.retrieval_helper or not hasattr(self.retrieval_helper, "retrieve_from_mdl_stores"):
            logger.warning("ContextualDataRetrievalAgent: retrieval_helper or retrieve_from_mdl_stores not available")
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
        tables_with_columns: List[Dict[str, Any]],
    ) -> str:
        """Build full context for the summary LLM without removing any information."""
        parts = []
        for store, docs in store_results.items():
            if not docs:
                continue
            parts.append(f"### {store}")
            for doc in docs:
                content = (doc.get("content") or "").strip()
                if content:
                    if SUMMARY_CONTEXT_MAX_CHARS_PER_DOC is not None and len(content) > SUMMARY_CONTEXT_MAX_CHARS_PER_DOC:
                        content = content[:SUMMARY_CONTEXT_MAX_CHARS_PER_DOC] + "..."
                    parts.append(content)
                meta = doc.get("metadata") or {}
                if meta:
                    meta_str = ", ".join(f"{k}={v}" for k, v in meta.items())
                    parts.append(f"  [metadata: {meta_str}]")
            parts.append("")
        if tables_with_columns:
            parts.append("### Tables with columns")
            for t in tables_with_columns:
                name = t.get("table_name", "")
                col_meta = t.get("column_metadata") or []
                if col_meta and isinstance(col_meta[0], dict):
                    col_lines = []
                    for c in col_meta:
                        nm = c.get("column_name", "")
                        typ = c.get("type", "")
                        desc = (c.get("description") or c.get("display_name", "")) or ""
                        col_lines.append(f"  - {nm}" + (f" ({typ})" if typ else "") + (f": {desc}" if desc else ""))
                    parts.append(f"- **{name}**:\n" + "\n".join(col_lines))
                else:
                    cols = t.get("columns", [])
                    parts.append(f"- **{name}**: {', '.join(cols)}")
        return "\n".join(parts).strip() or "(No retrieved content)"

    def _prioritize_requested_tables(
        self,
        tables: List[Dict[str, Any]],
        requested_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Put tables whose names are in requested_names first (case-insensitive), preserve order of the rest."""
        requested_set = {n.strip().lower() for n in requested_names if n}
        if not requested_set:
            return tables
        first = [t for t in tables if (t.get("table_name") or "").strip().lower() in requested_set]
        rest = [t for t in tables if (t.get("table_name") or "").strip().lower() not in requested_set]
        return first + rest

    def _extract_metrics_from_store_results(
        self,
        store_results: Dict[str, List[Dict[str, Any]]],
    ) -> List[str]:
        """Extract metric names/descriptions from mdl_metrics store for score-and-prune input."""
        metrics_docs = store_results.get("mdl_metrics") or []
        seen = set()
        out = []
        for doc in metrics_docs:
            content = (doc.get("content") or "").strip()[:200]
            meta = doc.get("metadata") or {}
            name = meta.get("metric_name") or meta.get("name") or content.split("\n")[0] if content else ""
            if name and name not in seen:
                seen.add(name)
                out.append(name)
        return out

    async def _score_and_prune_tables(
        self,
        user_question: str,
        tables_with_columns: List[Dict[str, Any]],
        store_results: Dict[str, List[Dict[str, Any]]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Call LLM to score tables and metrics by relevance, then prune to max_tables and max_metrics.
        Returns (pruned_tables, pruned_metrics_list, scoring_result).
        """
        if not self.max_tables and not self.max_metrics:
            return tables_with_columns, [], {"scored_tables": [], "scored_metrics": []}

        tables_blob = "\n".join(
            f"- {t.get('table_name', '')}: {', '.join((t.get('columns') or [])[:15])}"
            for t in tables_with_columns
        ) if tables_with_columns else "(none)"
        metrics_list = self._extract_metrics_from_store_results(store_results)
        metrics_blob = "\n".join(f"- {m}" for m in metrics_list) if metrics_list else "(none)"

        system_prompt, human_template = get_data_retrieval_score_prune_prompt()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_template),
        ])
        chain = prompt | self.llm | self._parser
        try:
            result = await chain.ainvoke({
                "user_question": user_question,
                "tables_blob": tables_blob,
                "metrics_blob": metrics_blob,
            })
        except Exception as e:
            logger.warning(f"Score-and-prune LLM failed: {e}")
            return tables_with_columns, [], {"scored_tables": [], "scored_metrics": []}

        scored_tables = result.get("scored_tables") or []
        scored_metrics = result.get("scored_metrics") or []
        table_name_to_score = {s.get("table_name", ""): s for s in scored_tables}
        table_name_to_score.pop("", None)

        # Sort by score descending and take top max_tables
        scored_tables_sorted = sorted(
            scored_tables,
            key=lambda x: (x.get("score") if isinstance(x.get("score"), (int, float)) else 0),
            reverse=True,
        )
        if self.max_tables is not None and self.max_tables >= 0:
            scored_tables_sorted = scored_tables_sorted[: self.max_tables]
        top_table_names_ordered = [s.get("table_name", "") for s in scored_tables_sorted]
        top_table_names_set = {n for n in top_table_names_ordered if n}

        pruned_tables = []
        for t in tables_with_columns:
            name = t.get("table_name", "")
            if name not in top_table_names_set:
                continue
            row = dict(t)
            info = table_name_to_score.get(name, {})
            row["score"] = info.get("score")
            row["score_reason"] = info.get("reason", "")
            pruned_tables.append(row)
        order = {n: i for i, n in enumerate(top_table_names_ordered)}
        pruned_tables.sort(key=lambda x: order.get(x.get("table_name", ""), 999))

        # Prune metrics to top max_metrics
        scored_metrics_sorted = sorted(
            scored_metrics,
            key=lambda x: (x.get("score") if isinstance(x.get("score"), (int, float)) else 0),
            reverse=True,
        )
        if self.max_metrics is not None and self.max_metrics >= 0:
            scored_metrics_sorted = scored_metrics_sorted[: self.max_metrics]
        pruned_metrics_list = scored_metrics_sorted

        scoring_result = {
            "scored_tables": scored_tables,
            "scored_metrics": scored_metrics,
            "pruned_table_names": top_table_names_ordered,
            "pruned_metrics_count": len(pruned_metrics_list),
        }
        return pruned_tables, pruned_metrics_list, scoring_result

    async def _generate_summary_markdown(
        self,
        user_question: str,
        store_results: Dict[str, List[Dict[str, Any]]],
        tables_with_columns: List[Dict[str, Any]],
    ) -> str:
        """Call LLM to produce a markdown summary explaining tables, metrics, key concepts, etc."""
        context_blob = self._build_summary_context(store_results, tables_with_columns)
        system_prompt, human_template = get_data_retrieval_summary_prompt()
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
            logger.warning(f"Summary LLM failed: {e}")
            fallback = [f"Retrieved from {len(store_results)} stores: " + ", ".join(store_results.keys())]
            if tables_with_columns:
                fallback.append("Tables: " + ", ".join(t.get("table_name", "") for t in tables_with_columns))
            return ". ".join(fallback)

    async def run(
        self,
        user_question: str,
        product_name: Optional[str] = None,
        project_id: Optional[str] = None,
        include_table_schemas: bool = True,
        include_summary: bool = True,
        session_cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Full pipeline: breakdown → parallel retrieval → table/column context → score & prune (LLM) → optional summary (LLM).

        Args:
            user_question: The data-related question.
            product_name: Optional product (e.g. Snyk) for filtering.
            project_id: Optional project_id for retrieval_helper.get_database_schemas.
            include_table_schemas: If True and retrieval_helper is set, fetch table schemas (with columns; no pruning when is_column_specific).
            include_summary: If True, call LLM to generate markdown summary; if False, use a short non-LLM summary (e.g. when caller will summarize by user action).
            session_cache: Optional dict to reuse retrieved tables/schemas within the session (passed to get_database_schemas).

        Returns:
            Dict with:
            - breakdown: result of breakdown_question
            - store_results: dict store_name -> list of retrieved docs (content, metadata)
            - tables_with_columns: list of tables (with columns, table_ddl?, score?, score_reason?) pruned to max_tables
            - pruned_metrics: list of scored metrics (top max_metrics)
            - scoring_result: scored_tables, scored_metrics, pruned_table_names, pruned_metrics_count
            - summary: LLM-generated markdown summary (tables, metrics, key concepts, compliance/frameworks)
        """
        breakdown = await self.breakdown_question(user_question, product_name)
        store_queries = breakdown.get("store_queries") or []
        is_column_specific = breakdown.get("is_column_specific", False)
        requested_table_names: List[str] = breakdown.get("requested_table_names") or []
        product = breakdown.get("product_name") or product_name
        categories = breakdown.get("categories") or []

        # Parallel retrieval from MDL preview stores via RetrievalHelper
        store_results = await self.retrieve_from_stores(store_queries, product, categories)

        tables_with_columns: List[Dict[str, Any]] = []
        if include_table_schemas and self.retrieval_helper and hasattr(self.retrieval_helper, "get_database_schemas"):
            pid = project_id or product
            if pid:
                table_retrieval = {
                    "table_retrieval_size": 15,
                    "table_column_retrieval_size": 100,
                    "allow_using_db_schemas_without_pruning": is_column_specific,
                }
                try:
                    schema_result = await self.retrieval_helper.get_database_schemas(
                        project_id=pid,
                        table_retrieval=table_retrieval,
                        query=user_question,
                        tables=requested_table_names if requested_table_names else None,
                        session_cache=session_cache,
                    )
                    for s in schema_result.get("schemas") or []:
                        col_meta = s.get("column_metadata") or []
                        tables_with_columns.append({
                            "table_name": s.get("table_name", ""),
                            "columns": [c.get("column_name", "") for c in col_meta if isinstance(c, dict)],
                            "column_metadata": col_meta,
                            "table_ddl": s.get("table_ddl", ""),
                            "relationships": s.get("relationships", []),
                            "description": s.get("description", ""),
                        })
                except Exception as e:
                    logger.warning(f"get_database_schemas failed: {e}")

        # When user asked about specific table(s) (column-specific), put those tables first
        if requested_table_names and tables_with_columns:
            tables_with_columns = self._prioritize_requested_tables(
                tables_with_columns, requested_table_names
            )

        # Score and prune: LLM scores tables and metrics, keep top max_tables / max_metrics
        pruned_tables = tables_with_columns
        pruned_metrics: List[Dict[str, Any]] = []
        scoring_result: Dict[str, Any] = {}
        has_candidates = bool(tables_with_columns) or bool(self._extract_metrics_from_store_results(store_results))
        if has_candidates and (self.max_tables is not None or self.max_metrics is not None):
            pruned_tables, pruned_metrics, scoring_result = await self._score_and_prune_tables(
                user_question, tables_with_columns, store_results
            )
        # After pruning, again put requested tables first so QA answers with the asked-for table
        if requested_table_names and pruned_tables:
            pruned_tables = self._prioritize_requested_tables(pruned_tables, requested_table_names)

        # Summary: LLM markdown when include_summary else short non-LLM line
        if include_summary:
            summary = await self._generate_summary_markdown(
                user_question, store_results, pruned_tables
            )
        else:
            parts = [f"Retrieved from {len(store_results)} stores: " + ", ".join(store_results.keys())]
            if pruned_tables:
                parts.append("Tables: " + ", ".join(t.get("table_name", "") for t in pruned_tables))
            summary = ". ".join(parts)

        return {
            "breakdown": breakdown,
            "store_results": store_results,
            "tables_with_columns": pruned_tables,
            "pruned_metrics": pruned_metrics,
            "scoring_result": scoring_result,
            "summary": summary,
            "user_question": user_question,
            "is_column_specific": is_column_specific,
        }
