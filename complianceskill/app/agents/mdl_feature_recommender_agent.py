"""
MDL Feature Recommender Agent

Flow:
1. Retrieve tables (caller does this; MDL table retrieval returns tables and columns).
2. Retrieve metrics related to the topic from the metric/feature store (entities with
   source_content_type=metrics), using the source question (topic) as the primary query.
3. Ask the LLM to recommend metrics using the tables and columns information (schema_contexts)
   so suggested metrics align with the displayed schema.

Supports multiple batch retrieval calls (e.g. 10 at a time) and collects/deduplicates results.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

logger = logging.getLogger(__name__)

# Default batch size per retrieval call and max number of batch calls
DEFAULT_TOP_K_PER_BATCH = 10
DEFAULT_MAX_BATCH_CALLS = 10


class MDLFeatureRecommenderAgent:
    """
    Agent that:
    1. Takes tables (and optionally full schema_contexts: tables + columns) from MDL table retrieval
    2. Retrieves metrics related to the topic from the metric/feature store (source_question as primary query)
    3. Asks LLM to recommend metrics using the tables and columns information so recommendations
       can be applied to or derived from the displayed schema
    """

    def __init__(
        self,
        collection_factory: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        top_k_per_batch: int = DEFAULT_TOP_K_PER_BATCH,
        max_batch_calls: int = DEFAULT_MAX_BATCH_CALLS,
    ):
        """
        Initialize the MDL feature recommender agent.

        Args:
            collection_factory: CollectionFactory for entities (metrics collection)
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            top_k_per_batch: Number of results per retrieval batch (default 10)
            max_batch_calls: Maximum number of retrieval batches (default 10)
        """
        self.collection_factory = collection_factory
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        self.top_k_per_batch = top_k_per_batch
        self.max_batch_calls = max_batch_calls

    def _normalize_tables_retrieved(
        self,
        tables_retrieved: List[Any],
    ) -> tuple[List[str], List[Dict[str, Any]]]:
        """
        Normalize tables_retrieved so we support both list-of-strings (table names)
        and list-of-dicts (with table_name or metadata.table_name).
        Returns (table_names, entries_for_summary) so retrieval and LLM use the same displayed tables.
        """
        table_names = []
        entries_for_summary = []
        seen = set()
        for t in tables_retrieved or []:
            if isinstance(t, str):
                name = t.strip()
                if name and name not in seen:
                    seen.add(name)
                    table_names.append(name)
                    entries_for_summary.append({"table_name": name})
            elif isinstance(t, dict):
                name = t.get("table_name") or (t.get("metadata") or {}).get("table_name")
                if name and name not in seen:
                    seen.add(name)
                    table_names.append(name)
                entries_for_summary.append(t)
        return table_names, entries_for_summary

    def _build_retrieval_queries(
        self,
        source_question: str,
        table_names: List[str],
        table_entries: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Build query strings for batch retrieval. Topic (source_question) is primary so we
        retrieve metrics related to the topic; table names/categories add diversity.
        """
        queries = []
        # Primary: topic (user question) so we get metrics related to the topic
        if source_question and source_question.strip():
            queries.append(source_question.strip())
        # Secondary: table names and categories for diversity
        if table_names:
            queries.append(" ".join(table_names))
            for name in table_names[: self.max_batch_calls - 2]:
                queries.append(name)
        table_categories = []
        for t in table_entries or []:
            cat = (t.get("metadata") or {}).get("categories")
            if isinstance(cat, list) and cat:
                table_categories.extend(cat)
            elif isinstance(cat, str) and cat and cat not in table_categories:
                table_categories.append(cat)
        if table_categories:
            queries.append(" ".join(table_categories[:10]))
        if not queries:
            queries = ["security metrics features risk impact likelihood"]
        return queries[: self.max_batch_calls]

    async def _retrieve_metrics_batch(
        self,
        query: str,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve one batch of metrics/features from entities collection."""
        collection = self.collection_factory.get_collection_by_store_name("entities")
        if not collection or not hasattr(collection, "hybrid_search"):
            logger.warning("MDLFeatureRecommenderAgent: entities collection or hybrid_search not available")
            return []
        filters = dict(where or {})
        filters["source_content_type"] = "metrics"
        try:
            results = await collection.hybrid_search(
                query=query,
                top_k=self.top_k_per_batch,
                where=filters,
            )
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"MDLFeatureRecommenderAgent: batch retrieval failed: {e}")
            return []

    async def retrieve_metrics_and_features(
        self,
        source_question: str,
        tables_retrieved: List[Any],
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve metrics/features from the metrics collection in batches.
        Runs up to max_batch_calls queries (each top_k_per_batch results), merges and deduplicates by id/name.
        Queries are built from the displayed tables first so suggested metrics align with those tables.

        Args:
            source_question: Original question used for table retrieval
            tables_retrieved: List of table names (strings) or table entries (dict with table_name/metadata.table_name)
            where: Optional extra metadata filters for retrieval

        Returns:
            List of unique feature/metric items (content + metadata), order preserved (first occurrence).
        """
        table_names, table_entries = self._normalize_tables_retrieved(tables_retrieved)
        queries = self._build_retrieval_queries(source_question, table_names, table_entries)
        seen_keys = set()
        collected = []

        async def run_batch(q: str) -> List[Dict[str, Any]]:
            return await self._retrieve_metrics_batch(q, where=where)

        batch_results = await asyncio.gather(*[run_batch(q) for q in queries], return_exceptions=True)

        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.warning(f"MDLFeatureRecommenderAgent: batch {i} error: {result}")
                continue
            for item in result or []:
                meta = item.get("metadata") or {}
                key = meta.get("id") or meta.get("name") or meta.get("metricTitle")
                if not key:
                    key = item.get("content", "")[:80]
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    collected.append({
                        "content": item.get("content", ""),
                        "metadata": meta,
                    })
        logger.info(f"MDLFeatureRecommenderAgent: retrieved {len(collected)} unique metrics/features from {len(queries)} batch queries")
        return collected

    async def suggest_features_with_categories(
        self,
        source_question: str,
        tables_retrieved: List[Any],
        retrieved_features: List[Dict[str, Any]],
        schema_contexts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to recommend metrics given the topic, tables/columns info (schema_contexts), and candidate metrics.

        Args:
            source_question: User question (topic)
            tables_retrieved: Tables displayed (list of table names or table entries)
            retrieved_features: Metrics/features from retrieve_metrics_and_features (topic-based)
            schema_contexts: Optional list of table+column descriptions (DDL or schema text from MDL table retrieval).
                            When provided, the LLM uses this to recommend metrics that can be applied to or derived from these tables/columns.

        Returns:
            Dict with suggested_features and categories_used.
        """
        try:
            table_names, _ = self._normalize_tables_retrieved(tables_retrieved)
            tables_summary = table_names[:20]
            # Tables and columns information from MDL table retrieval (used to generate metrics)
            schema_text = ""
            if schema_contexts and isinstance(schema_contexts, list):
                schema_text = "\n\n".join((s or "").strip() for s in schema_contexts[:30] if s)
            if not schema_text and tables_summary:
                schema_text = "Tables: " + ", ".join(tables_summary)

            features_summary = []
            for f in (retrieved_features or [])[:50]:
                meta = f.get("metadata") or {}
                features_summary.append({
                    "name": meta.get("name") or meta.get("metricTitle"),
                    "displayName": meta.get("displayName") or meta.get("metricTitle"),
                    "category": meta.get("category"),
                    "subCategory": meta.get("subCategory"),
                    "featureType": meta.get("featureType") or meta.get("entity_type"),
                    "featureCategory": meta.get("featureCategory"),
                    "metricDescription": (meta.get("metricDescription") or meta.get("description") or "")[:200],
                })
            system_prompt = """You are an expert at recommending security/metrics features for analytics and monitoring.

Given:
1. The user's question (topic)
2. The tables and columns information (schema) that was retrieved for the user – table names, column names, types, and descriptions
3. Candidate metrics/features from the metric/feature store (related to the topic)

Your task is to recommend which metrics/features are most relevant to the topic AND can be applied to or derived from the given tables and columns. Use the schema (tables and columns) to decide which metrics make sense for this data. Group suggestions by category.
Categories are buckets of features (e.g. "SOC2 – Access & Hardening", "Raw Risk Metrics", "Monitoring Agent Evidence").
Use the category and subCategory from the candidate features when suggesting; you may suggest a subset and add a short rationale tying each to the schema where relevant.

Output JSON with:
- suggested_features: List of suggested feature objects. Each must include: name, displayName, category, subCategory, featureType, featureCategory, and optionally rationale (one line, e.g. which table/column it applies to).
- categories_used: List of category names (the buckets you used to group suggestions)."""
            human_template = """Topic (user question): {source_question}

Tables and columns (schema from MDL table retrieval – use this to generate/recommend metrics):
{schema_contexts}

Candidate metrics/features (from metric store, topic-related): {features_summary}

Recommend metrics that are relevant to the topic and that can be applied to or derived from the above tables and columns. Return JSON with suggested_features and categories_used."""
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_template),
            ])
            chain = prompt | self.llm | self.json_parser
            result = await chain.ainvoke({
                "source_question": source_question,
                "schema_contexts": schema_text or "None",
                "features_summary": json.dumps(features_summary, indent=2) if features_summary else "None",
            })
            suggested = result.get("suggested_features") or []
            categories_used = result.get("categories_used") or []
            logger.info(f"MDLFeatureRecommenderAgent: LLM suggested {len(suggested)} features in {len(categories_used)} categories")
            return {
                "suggested_features": suggested,
                "categories_used": categories_used,
                "source_question": source_question,
            }
        except Exception as e:
            logger.error(f"MDLFeatureRecommenderAgent: suggest_features_with_categories error: {e}", exc_info=True)
            return {
                "suggested_features": [],
                "categories_used": [],
                "source_question": source_question,
                "error": str(e),
            }

    async def run(
        self,
        source_question: str,
        tables_retrieved: List[Any],
        where: Optional[Dict[str, Any]] = None,
        schema_contexts: Optional[List[str]] = None,
        unified_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Full pipeline: retrieve metrics related to the topic, then LLM recommends using tables/columns info.

        Flow: (1) Caller retrieves tables (MDL table retrieval returns tables + columns).
        (2) We retrieve metrics related to the topic from the metric store.
        (3) LLM recommends metrics using schema_contexts (tables and columns) to generate relevant suggestions.

        Args:
            source_question: User question (topic) – used as primary query for metrics retrieval
            tables_retrieved: List of table names (strings) or table entries (dicts) from table retrieval
            where: Optional extra filters for metrics retrieval
            schema_contexts: Optional list of table+column descriptions (DDL/schema from MDL table retrieval).
                             Used by the LLM to recommend metrics that apply to this schema.
            unified_context: Optional dict; if provided and schema_contexts is None, schema_contexts is taken
                             from unified_context.get("schema_contexts").

        Returns:
            Dict with retrieved_features, suggested_features, categories_used, source_question.
        """
        if schema_contexts is None and unified_context:
            schema_contexts = unified_context.get("schema_contexts")
        retrieved = await self.retrieve_metrics_and_features(
            source_question=source_question,
            tables_retrieved=tables_retrieved,
            where=where,
        )
        suggestion = await self.suggest_features_with_categories(
            source_question=source_question,
            tables_retrieved=tables_retrieved,
            retrieved_features=retrieved,
            schema_contexts=schema_contexts,
        )
        return {
            "retrieved_features": retrieved,
            "suggested_features": suggestion.get("suggested_features", []),
            "categories_used": suggestion.get("categories_used", []),
            "source_question": source_question,
            "error": suggestion.get("error"),
        }
