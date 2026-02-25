import json
import logging
from typing import Any, Dict, List, Optional

from cachetools import TTLCache

logger = logging.getLogger("genieml-agents")


class SqlFunction:
    """Represents a SQL function with its parameters, return type, examples, and instructions."""

    _expr: str = None
    _definition: dict = None

    def __init__(self, definition: dict, examples: Optional[List[Dict]] = None, instructions: Optional[List[Dict]] = None):
        """Initialize a SQL function from its definition.

        Args:
            definition: Dictionary containing function definition
            examples: Optional list of usage example dicts (question, description, sql, etc.)
            instructions: Optional list of instruction dicts (content, section, function_name, etc.)
        """
        self._definition = definition
        self._examples = examples or []
        self._instructions = instructions or []

        def _extract() -> tuple:
            name = definition.get("name", "")
            if not name:
                _param_types = "any"
            else:
                _param_types = definition.get("param_types") or definition.get("param_type") or "any"
            param_types = _param_types.split(",") if isinstance(_param_types, str) else (_param_types or [])
            return_type = definition.get("return_type") or definition.get("returns") or "any"
            if isinstance(return_type, list):
                return_type = "any"
            return name, param_types, str(return_type)

        def _param_expr(param_type: str, index: int) -> str:
            if param_type == "any":
                return "any"
            param_type = str(param_type).strip()
            param_name = f"${index}"
            return f"{param_name}: {param_type}"

        name, param_types, return_type = _extract()
        params = [_param_expr(t, i) for i, t in enumerate(param_types)]
        param_str = ", ".join(params)
        self._expr = f"{name}({param_str}) -> {return_type}"

    def __str__(self):
        return self._expr

    def __repr__(self):
        return self._expr


class SqlFunctions:
    """
    Manages SQL functions retrieval from independent collections:
    - core_ds_functions: function definitions
    - core_ds_function_examples: usage examples (1-2 per function)
    - core_ds_function_instructions: complex rules, constraints, per-function instructions
    Falls back to sql_functions (project-specific) when core collections are not available.
    """

    def __init__(
        self,
        document_store: Any,
        document_stores: Optional[Dict[str, Any]] = None,
        engine_timeout: Optional[float] = 30.0,
        ttl: Optional[int] = 60 * 60 * 24,
    ) -> None:
        """Initialize the SQL functions manager.

        Args:
            document_store: Primary store (sql_functions) for backward compatibility
            document_stores: Optional dict with core_ds_functions, core_ds_function_examples,
                            core_ds_function_instructions. When present, used for combined retrieval.
            engine_timeout: Timeout for engine operations in seconds
            ttl: Time-to-live for cache in seconds
        """
        self._document_store = document_store
        self._stores = document_stores or {}
        self._cache = TTLCache(maxsize=100, ttl=ttl)
        self._engine_timeout = engine_timeout

    def _get_functions_store(self) -> Any:
        """Primary store for function definitions: core_ds_functions if available, else sql_functions."""
        return self._stores.get("core_ds_functions") or self._document_store

    def _get_examples_store(self) -> Optional[Any]:
        return self._stores.get("core_ds_function_examples")

    def _get_instructions_store(self) -> Optional[Any]:
        return self._stores.get("core_ds_function_instructions")

    def _is_using_core_ds(self) -> bool:
        return bool(self._stores.get("core_ds_functions"))

    def _build_function_definition(self, result: Dict) -> Dict:
        """Build definition dict for SqlFunction from search result (works for DS_FUNCTION and SQL_FUNCTION)."""
        metadata = result.get("metadata", {})
        content = result.get("content", "")

        if metadata and metadata.get("name"):
            defn = dict(metadata)
            if "return_type" not in defn and "returns" in defn:
                defn["return_type"] = defn["returns"]
            return defn

        if content:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and parsed.get("name"):
                    defn = dict(parsed)
                    defn["param_types"] = defn.get("param_types") or ",".join(
                        p.get("type", "any") if isinstance(p, dict) else str(p).split(":")[-1].strip()
                        for p in defn.get("parameters", [])
                    )
                    defn["return_type"] = defn.get("return_type") or defn.get("returns", "any")
                    return defn
            except json.JSONDecodeError:
                pass

        return {}

    def _search_examples_for_function(self, function_name: str, max_examples: int = 2) -> List[Dict]:
        """Fetch 1-2 usage examples for a function from core_ds_function_examples."""
        store = self._get_examples_store()
        if not store or not function_name:
            return []

        try:
            where = {"function_name": {"$eq": function_name}}
            if hasattr(store, "semantic_search"):
                results = store.semantic_search(
                    query=f"{function_name} usage example",
                    k=max_examples,
                    where=where,
                )
            else:
                return []

            examples = []
            for r in results:
                content = r.get("content", "")
                meta = r.get("metadata", {})
                examples.append({
                    "function_name": meta.get("function_name", function_name),
                    "question": meta.get("question", ""),
                    "description": content[:500] if content else "",
                    "content": content,
                    "metadata": meta,
                })
            return examples[:max_examples]
        except Exception as e:
            logger.debug(f"Could not fetch examples for {function_name}: {e}")
            return []

    def _search_instructions_for_functions(
        self, query: Optional[str], function_names: List[str], k: int = 5
    ) -> List[Dict]:
        """Fetch relevant instructions: general + function-specific if any."""
        store = self._get_instructions_store()
        if not store:
            return []

        collected = []
        search_query = query or "SQL function usage rules constraints"

        try:
            if hasattr(store, "semantic_search"):
                results = store.semantic_search(query=search_query, k=k)
                for r in results:
                    meta = r.get("metadata", {})
                    fn = meta.get("function_name")
                    if fn and fn in function_names:
                        collected.append({"content": r.get("content", ""), "metadata": meta, "scope": "function"})
                    elif not fn or meta.get("section") in ("meta_critical_rules", "installation_order", "jsonb_input_contracts"):
                        collected.append({"content": r.get("content", ""), "metadata": meta, "scope": "general"})
        except Exception as e:
            logger.debug(f"Could not fetch instructions: {e}")

        return collected[:k]

    async def run(
        self,
        query: Optional[str] = None,
        data_source: Optional[str] = None,
        project_id: Optional[str] = None,
        k: int = 10,
        similarity_threshold: float = 0.7,
        max_results: int = 3,
        max_examples_per_function: int = 2,
        include_instructions: bool = True,
    ) -> List[SqlFunction]:
        """
        Retrieve SQL functions, optionally with 1-2 usage examples and relevant instructions per function.

        When using core_ds_* collections:
        - Searches core_ds_functions for matching functions
        - For each function, fetches 1-2 examples from core_ds_function_examples
        - Fetches relevant instructions from core_ds_function_instructions (general + function-specific)

        Args:
            query: Natural language query (uses semantic search when provided)
            data_source: Filter by data source (ignored for core_ds; used for sql_functions)
            project_id: Filter by project (ignored for core_ds; used for sql_functions)
            k: Number of candidate results from semantic search
            similarity_threshold: Minimum similarity (0-1)
            max_results: Max functions to return
            max_examples_per_function: Examples to fetch per function (1-2)
            include_instructions: Whether to fetch instructions

        Returns:
            List of SqlFunction with _examples and _instructions attached when available
        """
        logger.info(
            f"SQL Functions Retrieval (query: {query or 'all'}, core_ds: {self._is_using_core_ds()}, "
            f"threshold: {similarity_threshold}, max: {max_results})"
        )

        try:
            cache_key = f"{query or 'all'}_{data_source or 'all'}_{project_id or 'all'}_{similarity_threshold}_{max_results}_{max_examples_per_function}_{include_instructions}"
            if cache_key in self._cache:
                logger.debug(f"Cache hit for SQL functions")
                return self._cache[cache_key]

            store = self._get_functions_store()
            use_core_ds = self._is_using_core_ds()

            if query:
                where_conditions = []
                if use_core_ds:
                    where_conditions.append({"type": {"$eq": "DS_FUNCTION"}})
                else:
                    where_conditions.append({"type": {"$eq": "SQL_FUNCTION"}})
                    if data_source:
                        where_conditions.append({"data_source": {"$eq": data_source}})
                    if project_id and project_id != "default":
                        where_conditions.append({"project_id": {"$eq": project_id}})

                where_clause = {"$and": where_conditions} if len(where_conditions) > 1 else (where_conditions[0] if where_conditions else None)

                if hasattr(store, "semantic_search"):
                    search_results = store.semantic_search(query=query, k=k, where=where_clause)
                else:
                    search_results = []

                if not search_results:
                    logger.info(f"No SQL functions found for query: {query}")
                    return []

                sql_functions = []
                function_names = []

                for result in search_results:
                    score = result.get("score", 1.0)
                    similarity = 1.0 - score if score <= 1.0 else 0.0
                    if similarity < similarity_threshold:
                        continue

                    defn = self._build_function_definition(result)
                    if not defn:
                        continue

                    try:
                        func_name = defn.get("name", "")
                        function_names.append(func_name)

                        examples = []
                        if self._get_examples_store() and max_examples_per_function > 0:
                            examples = self._search_examples_for_function(func_name, max_examples_per_function)

                        instructions = []
                        if include_instructions and self._get_instructions_store():
                            instructions = self._search_instructions_for_functions(query, [func_name], k=3)

                        sql_func = SqlFunction(definition=defn, examples=examples, instructions=instructions)
                        sql_func._similarity = similarity
                        sql_functions.append(sql_func)

                        if len(sql_functions) >= max_results:
                            break
                    except Exception as e:
                        logger.warning(f"Error creating SqlFunction: {e}")
                        continue

                self._cache[cache_key] = sql_functions
                return sql_functions
            else:
                where_conditions = []
                if use_core_ds:
                    where_conditions.append({"type": {"$eq": "DS_FUNCTION"}})
                else:
                    where_conditions.append({"type": {"$eq": "SQL_FUNCTION"}})
                    if data_source:
                        where_conditions.append({"data_source": {"$eq": data_source}})
                    if project_id and project_id != "default":
                        where_conditions.append({"project_id": {"$eq": project_id}})

                where_clause = {"$and": where_conditions} if len(where_conditions) > 1 else (where_conditions[0] if where_conditions else None)

                if hasattr(store, "semantic_search"):
                    search_results = store.semantic_search(
                        query="SQL function definition",
                        k=max_results * 2,
                        where=where_clause,
                    )
                    documents = [{"content": r.get("content", ""), "metadata": r.get("metadata", {})} for r in search_results]
                elif hasattr(store, "collection") and store.collection:
                    try:
                        raw = store.collection.get(where=where_clause, limit=max_results * 2)
                        docs_list = raw.get("documents", [])
                        metas_list = raw.get("metadatas", [])
                        documents = [{"content": docs_list[i] if i < len(docs_list) else "", "metadata": metas_list[i] if i < len(metas_list) else {}} for i in range(max(len(docs_list), len(metas_list)))]
                    except Exception:
                        documents = []
                else:
                    documents = []

                if not documents:
                    return []

                sql_functions = []
                for item in documents[:max_results]:
                    metadata = item.get("metadata", {})
                    content = item.get("content", "")
                    if not metadata and content:
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict):
                                metadata = parsed
                        except (json.JSONDecodeError, TypeError):
                            pass

                    defn = self._build_function_definition({"metadata": metadata, "content": content})
                    if not defn:
                        continue

                    try:
                        func_name = defn.get("name", "")
                        examples = []
                        if self._get_examples_store() and max_examples_per_function > 0:
                            examples = self._search_examples_for_function(func_name, max_examples_per_function)
                        instructions = []
                        if include_instructions and self._get_instructions_store():
                            instructions = self._search_instructions_for_functions(None, [func_name], k=3)
                        sql_func = SqlFunction(definition=defn, examples=examples, instructions=instructions)
                        sql_functions.append(sql_func)
                    except Exception as e:
                        logger.warning(f"Error creating SqlFunction: {e}")

                self._cache[cache_key] = sql_functions
                return sql_functions

        except Exception as e:
            logger.error(f"Error retrieving SQL functions: {str(e)}")
            raise
