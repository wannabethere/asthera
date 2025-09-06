import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.nodes.writers.alerts_agent import (
    SQLToAlertAgent, 
    SQLAlertRequest, 
    SQLAlertResult,
)
from app.agents.pipelines.sql_execution import SQLExecutionPipeline
from app.core.dependencies import create_llm_instances_from_settings

logger = logging.getLogger("lexy-ai-service")


class AlertOrchestratorPipeline(AgentPipeline):
    """Orchestrator pipeline that coordinates alert/feed generation from SQL queries and natural language requests"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        alert_agent: Optional[SQLToAlertAgent] = None,
        llm_settings: Optional[Dict[str, Any]] = None,
        sql_execution_pipeline: Optional[SQLExecutionPipeline] = None
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            retrieval_helper=retrieval_helper,
            engine=engine
        )
        
        self._configuration = {
            "enable_sql_analysis": True,
            "enable_alert_generation": True,
            "enable_critique": True,
            "enable_refinement": True,
            "enable_validation": True,
            "enable_metrics": True,
            "default_confidence_threshold": 0.8,
            "enable_sample_data_fetch": True,
            "sample_data_limit": 10
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize alert agent if not provided
        if not alert_agent:
            if not llm_settings:
                llm_settings = {
                    "model_name": "gemini-2.0-flash",
                    "sql_parser_temp": 0.0,
                    "alert_generator_temp": 0.1,
                    "critic_temp": 0.0,
                    "refiner_temp": 0.2
                }
            
            sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm = create_llm_instances_from_settings(llm_settings)
            
            self._alert_agent = SQLToAlertAgent(
                sql_parser_llm=sql_parser_llm,
                alert_generator_llm=alert_generator_llm,
                critic_llm=critic_llm,
                refiner_llm=refiner_llm
            )
        else:
            self._alert_agent = alert_agent
        
        # Initialize SQL execution pipeline if not provided
        if not sql_execution_pipeline:
            self._sql_execution_pipeline = SQLExecutionPipeline(
                name="sql_execution_for_alerts",
                version="1.0.0",
                description="SQL execution pipeline for fetching sample data for alert generation",
                llm=llm,
                retrieval_helper=retrieval_helper,
                engine=engine
            )
        else:
            self._sql_execution_pipeline = sql_execution_pipeline
        
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
        sql_queries: List[str],
        natural_language_query: str,
        alert_request: str,
        project_id: str,
        data_description: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Orchestrate the complete alert/feed generation workflow
        
        Args:
            sql_queries: List of SQL queries to analyze for alert generation
            natural_language_query: Natural language description of the queries
            alert_request: Natural language description of the desired alert
            project_id: Project identifier
            data_description: Optional description of the data being analyzed
            session_id: Optional session identifier for tracking
            additional_context: Additional context for alert generation
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing complete alert results with feed configurations
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not sql_queries or not isinstance(sql_queries, list):
            raise ValueError("SQL queries must be a non-empty list")
        
        if not natural_language_query or not alert_request:
            raise ValueError("Natural language query and alert request are required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "alert_orchestration_started",
            {
                "project_id": project_id,
                "total_queries": len(sql_queries),
                "session_id": session_id,
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            alert_results = []
            combined_sql_analysis = None
            
            # Step 1: Process each SQL query for alert generation
            for i, sql_query in enumerate(sql_queries):
                self._send_status_update(
                    status_callback,
                    "sql_analysis_started",
                    {
                        "project_id": project_id,
                        "query_index": i,
                        "total_queries": len(sql_queries)
                    }
                )
                
                # Fetch sample data for this SQL query
                sample_data = None
                if self._configuration.get("enable_sample_data_fetch", True):
                    self._send_status_update(
                        status_callback,
                        "sample_data_fetch_started",
                        {
                            "project_id": project_id,
                            "query_index": i
                        }
                    )
                    
                    sample_data = await self._fetch_sample_data(sql_query, project_id, **kwargs)
                    
                    self._send_status_update(
                        status_callback,
                        "sample_data_fetch_completed",
                        {
                            "project_id": project_id,
                            "query_index": i,
                            "sample_data_available": sample_data is not None,
                            "sample_size": len(sample_data.get("data", [])) if sample_data else 0
                        }
                    )
                
                # Create alert request for this SQL query
                alert_request_obj = SQLAlertRequest(
                    sql=sql_query,
                    query=natural_language_query,
                    project_id=project_id,
                    data_description=data_description,
                    configuration=additional_context,
                    alert_request=alert_request,
                    session_id=f"{session_id}_{i}" if session_id else None,
                    sample_data=sample_data
                )
                
                # Generate alert configuration
                if self._configuration["enable_alert_generation"]:
                    alert_result = await self._alert_agent.generate_alert(alert_request_obj)
                    alert_results.append(alert_result)
                    
                    # Combine SQL analysis from multiple queries
                    if combined_sql_analysis is None:
                        combined_sql_analysis = alert_result.sql_analysis
                    else:
                        # Merge analysis from multiple queries
                        combined_sql_analysis = self._merge_sql_analyses(
                            combined_sql_analysis, 
                            alert_result.sql_analysis
                        )
                    
                    self._send_status_update(
                        status_callback,
                        "sql_analysis_completed",
                        {
                            "project_id": project_id,
                            "query_index": i,
                            "confidence_score": alert_result.confidence_score,
                            "alert_type": alert_result.feed_configuration.condition.condition_type.value
                        }
                    )
                else:
                    # Skip alert generation if disabled
                    self._send_status_update(
                        status_callback,
                        "sql_analysis_skipped",
                        {
                            "project_id": project_id,
                            "query_index": i,
                            "reason": "alert_generation_disabled"
                        }
                    )
            
            # Step 2: Validate and refine results if needed
            if self._configuration["enable_validation"] and alert_results:
                self._send_status_update(
                    status_callback,
                    "alert_validation_started",
                    {"project_id": project_id, "total_alerts": len(alert_results)}
                )
                
                validated_results = await self._validate_alert_results(
                    alert_results, 
                    project_id, 
                    status_callback
                )
                
                self._send_status_update(
                    status_callback,
                    "alert_validation_completed",
                    {
                        "project_id": project_id,
                        "validated_alerts": len(validated_results),
                        "filtered_alerts": len(alert_results) - len(validated_results)
                    }
                )
            else:
                validated_results = alert_results
            
            # Step 3: Generate combined feed configurations
            combined_feed_configs = self._generate_combined_feed_configurations(
                validated_results, 
                project_id
            )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                total_queries=len(sql_queries),
                total_alerts=len(validated_results),
                execution_time=total_execution_time,
                project_id=project_id,
                average_confidence=sum(r.confidence_score for r in validated_results) / len(validated_results) if validated_results else 0.0
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "alert_orchestration_completed",
                {
                    "project_id": project_id,
                    "execution_time": total_execution_time,
                    "total_alerts_generated": len(validated_results),
                    "average_confidence": sum(r.confidence_score for r in validated_results) / len(validated_results) if validated_results else 0.0
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": True,
                    "alert_results": [self._alert_result_to_dict(result) for result in validated_results],
                    "combined_feed_configurations": combined_feed_configs,
                    "combined_sql_analysis": combined_sql_analysis.dict() if combined_sql_analysis else None,
                    "orchestration_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "total_queries_processed": len(sql_queries),
                        "total_alerts_generated": len(validated_results),
                        "average_confidence_score": sum(r.confidence_score for r in validated_results) / len(validated_results) if validated_results else 0.0,
                        "validation_enabled": self._configuration["enable_validation"]
                    }
                },
                "metadata": {
                    "pipeline_name": self.name,
                    "pipeline_version": self.version,
                    "execution_timestamp": end_time.isoformat(),
                    "configuration_used": self._configuration.copy()
                }
            }
            
            return final_response
            
        except Exception as e:
            logger.error(f"Error in alert orchestration pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "alert_orchestration_error",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            
            # Update metrics with error
            self._metrics.update({
                "last_error": str(e),
                "total_errors": self._metrics.get("total_errors", 0) + 1
            })
            
            raise

    def _merge_sql_analyses(self, analysis1, analysis2):
        """Merge two SQL analysis objects"""
        from app.agents.nodes.writers.alerts_agent import SQLAnalysis
        
        return SQLAnalysis(
            tables=list(set(analysis1.tables + analysis2.tables)),
            columns=list(set(analysis1.columns + analysis2.columns)),
            metrics=list(set(analysis1.metrics + analysis2.metrics)),
            dimensions=list(set(analysis1.dimensions + analysis2.dimensions)),
            filters=analysis1.filters + analysis2.filters,
            aggregations=analysis1.aggregations + analysis2.aggregations
        )

    async def _validate_alert_results(
        self, 
        alert_results: List[SQLAlertResult], 
        project_id: str,
        status_callback: Optional[Callable]
    ) -> List[SQLAlertResult]:
        """Validate alert results based on confidence threshold and other criteria"""
        
        confidence_threshold = self._configuration.get("default_confidence_threshold", 0.8)
        validated_results = []
        
        for i, result in enumerate(alert_results):
            # Check confidence threshold
            if result.confidence_score >= confidence_threshold:
                validated_results.append(result)
            else:
                self._send_status_update(
                    status_callback,
                    "alert_filtered_low_confidence",
                    {
                        "project_id": project_id,
                        "alert_index": i,
                        "confidence_score": result.confidence_score,
                        "threshold": confidence_threshold
                    }
                )
        
        return validated_results

    def _generate_combined_feed_configurations(
        self, 
        alert_results: List[SQLAlertResult], 
        project_id: str
    ) -> Dict[str, Any]:
        """Generate combined feed configurations from multiple alert results"""
        
        if not alert_results:
            return {"feeds": [], "summary": "No alerts generated"}
        
        # Group alerts by condition type
        alerts_by_type = {}
        for result in alert_results:
            condition_type = result.feed_configuration.condition.condition_type.value
            if condition_type not in alerts_by_type:
                alerts_by_type[condition_type] = []
            alerts_by_type[condition_type].append(result)
        
        # Create combined configurations
        combined_configs = {
            "feeds": [],
            "summary": {
                "total_feeds": len(alert_results),
                "condition_types": list(alerts_by_type.keys()),
                "average_confidence": sum(r.confidence_score for r in alert_results) / len(alert_results)
            }
        }
        
        # Convert each alert result to API payload format
        for result in alert_results:
            api_payload = self._alert_agent.create_lexy_api_payload(result)
            combined_configs["feeds"].append(api_payload)
        
        return combined_configs

    def _alert_result_to_dict(self, result: SQLAlertResult) -> Dict[str, Any]:
        """Convert SQLAlertResult to dictionary format"""
        return {
            "feed_configuration": result.feed_configuration.dict(),
            "sql_analysis": result.sql_analysis.dict(),
            "confidence_score": result.confidence_score,
            "critique_notes": result.critique_notes,
            "suggestions": result.suggestions
        }

    def _send_status_update(
        self,
        status_callback: Optional[Callable],
        status: str,
        details: Dict[str, Any]
    ) -> None:
        """Send status update via callback if available"""
        if status_callback:
            try:
                status_callback(status, details)
            except Exception as e:
                logger.error(f"Error in status callback: {str(e)}")
        
        # Also log the status update
        logger.info(f"Alert Orchestrator Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        total_queries: int,
        total_alerts: int,
        execution_time: float,
        project_id: str,
        average_confidence: float
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "total_queries": total_queries,
                "total_alerts": total_alerts,
                "execution_time": execution_time,
                "project_id": project_id,
                "average_confidence": average_confidence,
                "timestamp": datetime.now().isoformat()
            },
            "total_executions": self._metrics.get("total_executions", 0) + 1,
            "total_queries_processed": self._metrics.get("total_queries_processed", 0) + total_queries,
            "total_alerts_generated": self._metrics.get("total_alerts_generated", 0) + total_alerts,
            "total_execution_time": self._metrics.get("total_execution_time", 0) + execution_time
        })
        
        # Calculate average execution time
        total_executions = self._metrics["total_executions"]
        if total_executions > 0:
            self._metrics["average_execution_time"] = self._metrics["total_execution_time"] / total_executions

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get detailed execution statistics"""
        return {
            "pipeline_metrics": self._metrics.copy(),
            "configuration": self._configuration.copy(),
            "alert_agent_available": self._alert_agent is not None,
            "timestamp": datetime.now().isoformat()
        }

    def enable_sql_analysis(self, enabled: bool) -> None:
        """Enable or disable SQL analysis"""
        self._configuration["enable_sql_analysis"] = enabled
        logger.info(f"SQL analysis {'enabled' if enabled else 'disabled'}")

    def enable_alert_generation(self, enabled: bool) -> None:
        """Enable or disable alert generation"""
        self._configuration["enable_alert_generation"] = enabled
        logger.info(f"Alert generation {'enabled' if enabled else 'disabled'}")

    def enable_validation(self, enabled: bool) -> None:
        """Enable or disable validation"""
        self._configuration["enable_validation"] = enabled
        logger.info(f"Validation {'enabled' if enabled else 'disabled'}")

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold for alert validation"""
        if 0.0 <= threshold <= 1.0:
            self._configuration["default_confidence_threshold"] = threshold
            logger.info(f"Confidence threshold set to {threshold}")
        else:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")

    def enable_sample_data_fetch(self, enabled: bool) -> None:
        """Enable or disable sample data fetching for alert generation"""
        self._configuration["enable_sample_data_fetch"] = enabled
        logger.info(f"Sample data fetch {'enabled' if enabled else 'disabled'}")

    def set_sample_data_limit(self, limit: int) -> None:
        """Set the limit for sample data rows to fetch"""
        if limit > 0:
            self._configuration["sample_data_limit"] = limit
            logger.info(f"Sample data limit set to {limit}")
        else:
            raise ValueError("Sample data limit must be greater than 0")

    async def _fetch_sample_data(self, sql_query: str, project_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch sample data from SQL query execution"""
        if not self._configuration.get("enable_sample_data_fetch", True):
            return None
        
        try:
            # Create a sample SQL query with LIMIT
            sample_limit = self._configuration.get("sample_data_limit", 10)
            sample_sql = f"SELECT * FROM ({sql_query}) as sample_query LIMIT {sample_limit}"
            
            # Execute the sample query
            result = await self._sql_execution_pipeline.run(
                sql=sample_sql,
                project_id=project_id,
                configuration={"dry_run": False},
                **kwargs
            )
            
            if result.get("post_process", {}).get("data"):
                data = result["post_process"]["data"]
                if data:
                    # Convert to the format expected by the alert agent
                    columns = list(data[0].keys()) if data else []
                    return {
                        "columns": columns,
                        "data": data
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to fetch sample data for alert generation: {str(e)}")
            return None


# Factory function for creating alert orchestrator pipeline
def create_alert_orchestrator_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    alert_agent: Optional[SQLToAlertAgent] = None,
    llm_settings: Optional[Dict[str, Any]] = None,
    sql_execution_pipeline: Optional[SQLExecutionPipeline] = None,
    **kwargs
) -> AlertOrchestratorPipeline:
    """
    Factory function to create an alert orchestrator pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        alert_agent: SQL-to-Alert agent instance (optional, will create default if not provided)
        llm_settings: LLM configuration settings (optional, will use defaults if not provided)
        sql_execution_pipeline: SQL execution pipeline instance (optional, will create default if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        AlertOrchestratorPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return AlertOrchestratorPipeline(
        name="alert_orchestrator_pipeline",
        version="1.0.0",
        description="Orchestrator pipeline that coordinates alert/feed generation from SQL queries and natural language requests",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        alert_agent=alert_agent,
        llm_settings=llm_settings,
        sql_execution_pipeline=sql_execution_pipeline,
        **kwargs
    )
