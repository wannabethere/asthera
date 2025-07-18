from typing import Dict, Any, Optional
import logging
from app.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from langchain_openai import ChatOpenAI
from app.core.provider import get_cache_provider
import json

logger = logging.getLogger("lexy-ai-service")

## TODO: Fix all the dependencies on document stores to use Retrieval Helper, we should not be using DocumentStoreProvider directly. 
# TODO: Improvements Caching Fast Query fetching.
class RetrievalPipeline(AgentPipeline):
    """Unified pipeline for all retrieval types using RetrievalHelper"""
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        self._configuration = {
            "similarity_threshold": 0.2,
            "top_k": 10,
            "max_retrieval_size": 10,
            "cache_ttl": 3600  # Default cache TTL of 1 hour
        }
        self._metrics = {}
        self._cache = get_cache_provider().get_cache()

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def get_configuration(self) -> Dict[str, Any]:
        return self._configuration.copy()

    def update_configuration(self, config: Dict[str, Any]) -> None:
        self._configuration.update(config)

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        self._metrics.clear()

    def _generate_cache_key(self, retrieval_type: str, **kwargs) -> str:
        """Generate a unique cache key based on retrieval parameters"""
        # Create a deterministic key by sorting kwargs
        sorted_kwargs = dict(sorted(kwargs.items()))
        key_data = {
            "retrieval_type": retrieval_type,
            **sorted_kwargs
        }
        return f"retrieval:{json.dumps(key_data, sort_keys=True)}"

    async def run(self, retrieval_type: str, **kwargs) -> Dict[str, Any]:
        """
        Run the unified retrieval pipeline with caching support.
        Args:
            retrieval_type: One of 'historical_questions', 'instructions', 'sql_pairs', 'database_schemas'
            **kwargs: Arguments for the specific retrieval
        Returns:
            Dict with retrieval results
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")

        try:
            query = kwargs.get("query", "")
            project_id = kwargs.get("project_id")
            
            # Generate cache key
            print("kwargs in retrieval pipeline: ", kwargs)
            print("retrieval_type in retrieval pipeline: ", retrieval_type)
            print("query in retrieval pipeline: ", query)
            print("project_id in retrieval pipeline: ", project_id)
            cache_key = self._generate_cache_key(
                retrieval_type=retrieval_type,
                **kwargs
            )
            
            # Try to get from cache first
            cached_result = await self._cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for retrieval type: {retrieval_type}")
                self._metrics.update({
                    "cache_hit": True,
                    "last_query": query,
                    "last_project_id": project_id,
                    "success": True
                })
                return cached_result

            # If not in cache, proceed with normal retrieval
            result = None
            if retrieval_type == "historical_questions":
                result = await self._retrieval_helper.get_historical_questions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=kwargs.get("similarity_threshold", self._configuration["similarity_threshold"])
                )
                formatted_result = {"formatted_output": {"documents": result.get("historical_questions", [])}, "metadata": result}

            elif retrieval_type == "instructions":
                result = await self._retrieval_helper.get_instructions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=kwargs.get("similarity_threshold", self._configuration["similarity_threshold"]),
                    top_k=kwargs.get("top_k", self._configuration["top_k"])
                )
                formatted_result = {"formatted_output": {"documents": result.get("instructions", [])}, "metadata": result}

            elif retrieval_type == "sql_pairs":
                result = await self._retrieval_helper.get_sql_pairs(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=kwargs.get("similarity_threshold", self._configuration["similarity_threshold"]),
                    max_retrieval_size=kwargs.get("max_retrieval_size", self._configuration["max_retrieval_size"])
                )
                formatted_result = {"formatted_output": {"documents": result.get("sql_pairs", [])}, "metadata": result}

            elif retrieval_type == "database_schemas":
                result = await self._retrieval_helper.get_database_schemas(
                    project_id=project_id,
                    table_retrieval=kwargs.get("table_retrieval", {}),
                    query=query,
                    histories=kwargs.get("histories"),
                    tables=kwargs.get("tables")
                )
                formatted_result = {"formatted_output": {"documents": result.get("schemas", [])}, "metadata": result}
            elif retrieval_type == "metrics":
                result = await self._retrieval_helper.get_metrics(
                    project_id=project_id,
                    query=query,
                    tables=kwargs.get("tables")
                )
                formatted_result = {"formatted_output": {"documents": result.get("metrics", [])}, "metadata": result}
            elif retrieval_type == "views":
                result = await self._retrieval_helper.get_views(
                    project_id=project_id,
                    query=query,
                    tables=kwargs.get("tables")
                )
                formatted_result = {"formatted_output": {"documents": result.get("views", [])}, "metadata": result}
            else:
                raise ValueError(f"Unknown retrieval_type: {retrieval_type}")

            # Update metrics
            self._metrics.update({
                "cache_hit": False,
                "last_query": query,
                "last_project_id": project_id,
                "results_count": len(result.get("documents", [])),
                "success": True
            })

            # Cache the result
            await self._cache.set(
                cache_key,
                formatted_result,
                ttl=self._configuration.get("cache_ttl")
            )

            return formatted_result

        except Exception as e:
            logger.error(f"Error in retrieval pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise 

