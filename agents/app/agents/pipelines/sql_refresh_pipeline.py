import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
# Removed unused imports - now using agent's internal methods

logger = logging.getLogger("lexy-ai-service")


class SQLRefreshPipeline(AgentPipeline):
    """Pipeline for refreshing SQL queries with current date/time parameters"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        sql_rag_agent: Optional[SQLRAGAgent] = None
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            retrieval_helper=retrieval_helper,
            engine=engine
        )
        
        self._sql_rag_agent = sql_rag_agent
        self._engine = engine
        self._configuration = {
            "enable_time_refresh": True,
            "preserve_query_structure": True,
            "update_only_dynamic_params": True
        }
        self._metrics = {}
        self._initialized = True
    
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
    
    async def run(
        self,
        sql_query: str,
        original_question: str,
        project_id: str,
        schema_contexts: Optional[List[str]] = None,
        relationships: Optional[List[Dict]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refresh SQL query with current date/time parameters
        
        Args:
            sql_query: Original SQL query to refresh
            original_question: Original question that generated the SQL
            project_id: Project identifier
            schema_contexts: Optional schema contexts (will be retrieved if not provided)
            relationships: Optional table relationships
            status_callback: Optional callback for status updates
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing refreshed SQL query and metadata
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        if not self._sql_rag_agent:
            raise RuntimeError("SQL RAG Agent is required for SQL refresh")
        
        try:
            start_time = datetime.now()
            
            self._send_status_update(
                status_callback,
                "sql_refresh_started",
                {
                    "project_id": project_id,
                    "original_question": original_question,
                    "start_time": start_time.isoformat()
                }
            )
            
            # Use the agent's refresh method
            from app.agents.nodes.sql.sql_rag_agent import SQLOperationType
            
            refresh_result = await self._sql_rag_agent.process_sql_request(
                operation=SQLOperationType.REFRESH,
                query=original_question,
                sql=sql_query,
                original_question=original_question,
                project_id=project_id,
                existing_reasoning=kwargs.get("existing_reasoning", ""),
                schema_contexts=schema_contexts,
                relationships=relationships,
                **kwargs
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Add duration to metadata
            if refresh_result.get("success"):
                if "metadata" not in refresh_result:
                    refresh_result["metadata"] = {}
                refresh_result["metadata"]["duration_seconds"] = duration
            
            self._send_status_update(
                status_callback,
                "sql_refresh_completed",
                {
                    "project_id": project_id,
                    "success": refresh_result.get("success", False),
                    "duration_seconds": duration,
                    "original_sql_length": len(sql_query),
                    "refreshed_sql_length": len(refresh_result.get("refreshed_sql", "")) if refresh_result.get("success") else 0
                }
            )
            
            return refresh_result
            
        except Exception as e:
            logger.error(f"Error refreshing SQL query: {e}")
            self._send_status_update(
                status_callback,
                "sql_refresh_failed",
                {
                    "project_id": project_id,
                    "error": str(e),
                    "original_question": original_question
                }
            )
            raise
    
# Removed helper methods - now using agent's internal methods
    
    def _send_status_update(
        self,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]],
        status: str,
        details: Dict[str, Any]
    ):
        """Send status update via callback if provided"""
        if status_callback:
            try:
                status_callback(status, details)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
        logger.info(f"SQL Refresh Pipeline - {status}: {details}")


def create_sql_refresh_pipeline(
    engine: Engine,
    llm: Any,
    retrieval_helper: RetrievalHelper,
    sql_rag_agent: Optional[SQLRAGAgent] = None
) -> SQLRefreshPipeline:
    """Factory function to create SQL refresh pipeline"""
    from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent
    
    if not sql_rag_agent:
        from app.core.dependencies import get_doc_store_provider
        doc_store_provider = get_doc_store_provider()
        
        sql_rag_agent = SQLRAGAgent(
            llm=llm,
            engine=engine,
            document_store_provider=doc_store_provider,
            retrieval_helper=retrieval_helper
        )
    
    pipeline = SQLRefreshPipeline(
        name="sql_refresh",
        version="1.0",
        description="Pipeline for refreshing SQL queries with current date/time parameters",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        sql_rag_agent=sql_rag_agent
    )
    
    return pipeline

