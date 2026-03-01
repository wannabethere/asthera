"""
RetrievalHelper — adapter around MDLRetrievalService (mdl_service).

Exposes the interface expected by ContextualDataRetrievalAgent:
- retrieve_from_mdl_stores
- get_database_schemas

The retrieval logic lives in mdl_service; this module provides the adapter.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.retrieval.mdl_service import MDLRetrievalService

logger = logging.getLogger(__name__)

# Map MDL_PREVIEW_STORES store names to MDLRetrievalService methods
_STORE_TO_MDL_METHOD = {
    "mdl_metrics": "search_metrics_registry",
    "mdl_key_concepts": "search_db_schema",
    "mdl_patterns": "search_table_descriptions",
    "mdl_evidences": "search_db_schema",
    "mdl_fields": "search_db_schema",
    "mdl_edges_table": "search_db_schema",
    "mdl_edges_column": "search_table_descriptions",
    "mdl_category_enrichment": "search_metrics_registry",
}


class RetrievalHelper:
    """
    Adapter around MDLRetrievalService for ContextualDataRetrievalAgent.
    Retrieval logic is in mdl_service (MDLRetrievalService).
    """

    def __init__(self, mdl_service: Optional[MDLRetrievalService] = None):
        self._mdl = mdl_service or MDLRetrievalService()

    async def retrieve_from_mdl_stores(
        self,
        store_queries: List[Dict[str, str]],
        product_name: Optional[str] = None,
        categories: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve from MDL stores via MDLRetrievalService.
        Returns dict keyed by store name with list of {content, metadata}.
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        project_id = product_name  # product_name often used as project_id

        # Group queries by store
        by_store: Dict[str, List[str]] = {}
        for sq in store_queries:
            store = (sq.get("store") or "").strip()
            query = (sq.get("query") or "").strip()
            if store and query:
                by_store.setdefault(store, []).append(query)

        if not by_store:
            return result

        limit = min(top_k, 15)
        tasks = []
        store_keys = []

        for store, queries in by_store.items():
            method_name = _STORE_TO_MDL_METHOD.get(store, "search_db_schema")
            method = getattr(self._mdl, method_name, None)
            if not method or not callable(method):
                logger.debug(f"RetrievalHelper: no method for store {store}, using search_db_schema")
                method = self._mdl.search_db_schema

            # Use first query per store (or merge later)
            q = queries[0] if queries else ""
            if method_name == "search_metrics_registry":
                tasks.append(method(query=q, limit=limit, project_id=project_id))
            else:
                tasks.append(method(query=q, limit=limit, project_id=project_id))
            store_keys.append(store)

        try:
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.warning(f"RetrievalHelper.retrieve_from_mdl_stores failed: {e}")
            return result

        for store, raw in zip(store_keys, gathered):
            if isinstance(raw, Exception):
                logger.warning(f"RetrievalHelper: {store} failed: {raw}")
                result[store] = []
                continue

            docs = []
            for item in (raw or []):
                if hasattr(item, "metadata"):
                    meta = dict(getattr(item, "metadata", {}) or {})
                    content = (
                        getattr(item, "metric_definition", None)
                        or getattr(item, "description", None)
                        or getattr(item, "schema_ddl", None)
                        or getattr(item, "content", "")
                        or ""
                    )
                    if hasattr(item, "metric_name"):
                        meta["metric_name"] = getattr(item, "metric_name", "")
                    if hasattr(item, "table_name"):
                        meta["table_name"] = getattr(item, "table_name", "")
                    docs.append({"content": content, "metadata": meta})
                elif isinstance(item, dict):
                    docs.append({
                        "content": item.get("content", ""),
                        "metadata": item.get("metadata", {}),
                    })
            result[store] = docs

        return result

    async def get_database_schemas(
        self,
        project_id: str,
        table_retrieval: Optional[Dict[str, Any]] = None,
        query: Optional[str] = None,
        tables: Optional[List[str]] = None,
        session_cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch table schemas with columns via MDLRetrievalService.
        Returns {schemas: [{table_name, column_metadata, table_ddl, relationships, description}]}.
        """
        opts = table_retrieval or {}
        limit_schema = opts.get("table_retrieval_size", 15)
        limit_cols = opts.get("table_column_retrieval_size", 100)
        q = query or ""

        if session_cache and "schemas" in session_cache:
            return {"schemas": session_cache["schemas"]}

        schemas_task = self._mdl.search_db_schema(
            query=q, limit=limit_schema, project_id=project_id
        )
        descs_task = self._mdl.search_table_descriptions(
            query=q, limit=limit_schema, project_id=project_id
        )

        try:
            db_schemas, table_descs = await asyncio.gather(schemas_task, descs_task)
        except Exception as e:
            logger.warning(f"RetrievalHelper.get_database_schemas failed: {e}")
            return {"schemas": []}

        by_table: Dict[str, Dict[str, Any]] = {}
        for s in db_schemas or []:
            name = getattr(s, "table_name", "") or (s.metadata.get("name") if hasattr(s, "metadata") else "")
            if not name:
                continue
            cols = getattr(s, "columns", []) or (getattr(s, "metadata", {}) or {}).get("columns", []) or []
            col_meta = []
            for c in cols[:limit_cols]:
                if isinstance(c, dict):
                    col_meta.append({"column_name": c.get("name") or c.get("column_name", "") or str(c)})
                else:
                    col_meta.append({"column_name": str(c)})
            by_table[name] = {
                "table_name": name,
                "column_metadata": col_meta,
                "table_ddl": getattr(s, "schema_ddl", ""),
                "relationships": [],
                "description": "",
            }

        for d in table_descs or []:
            name = getattr(d, "table_name", "") or (d.metadata.get("name") if hasattr(d, "metadata") else "")
            if not name:
                continue
            if name in by_table:
                by_table[name]["description"] = getattr(d, "description", "") or ""
                by_table[name]["relationships"] = getattr(d, "relationships", []) or []
            else:
                by_table[name] = {
                    "table_name": name,
                    "column_metadata": [],
                    "table_ddl": "",
                    "relationships": getattr(d, "relationships", []) or [],
                    "description": getattr(d, "description", "") or "",
                }

        requested_set = {t.strip().lower() for t in (tables or []) if t}
        schemas_list = list(by_table.values())
        if requested_set:
            first = [x for x in schemas_list if (x.get("table_name") or "").strip().lower() in requested_set]
            rest = [x for x in schemas_list if (x.get("table_name") or "").strip().lower() not in requested_set]
            schemas_list = first + rest

        out = {"schemas": schemas_list}
        if session_cache is not None:
            session_cache["schemas"] = schemas_list
        return out
