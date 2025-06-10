from typing import Dict, Any, Optional
import logging
from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from langchain_openai import ChatOpenAI

logger = logging.getLogger("lexy-ai-service")

class TableDescriptionPipeline(AgentPipeline):
    """Pipeline for retrieving table descriptions"""
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
        self._configuration = {"top_k": 5}
        self._metrics = {}

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

    async def run(self, table_name: str, project_id: str, configuration: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        try:
            # Example: Use retrieval_helper to get table description
            result = await self._retrieval_helper.get_table_description(
                table_name=table_name,
                project_id=project_id,
                top_k=configuration.get("top_k", 5) if configuration else self._configuration["top_k"]
            )
            self._metrics.update({"last_table": table_name, "last_project_id": project_id, "success": bool(result)})
            return {"post_process": result, "metadata": {"project_id": project_id, "table_name": table_name}}
        except Exception as e:
            logger.error(f"Error in table description pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise 