import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from uuid import uuid4
from enum import Enum

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from pydantic import BaseModel, Field

logger = logging.getLogger("lexy-ai-service")


class FeedStatus(str, Enum):
    """Feed status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"
    PENDING = "pending"


class FeedPriority(str, Enum):
    """Feed priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSet(BaseModel):
    """Individual alert set configuration"""
    alert_id: str = Field(..., description="Unique identifier for the alert")
    alert_name: str = Field(..., description="Human-readable name for the alert")
    sql_query: str = Field(..., description="SQL query for the alert")
    natural_language_query: str = Field(..., description="Natural language description of the query")
    alert_request: str = Field(..., description="Natural language description of the alert requirements")
    configuration: Optional[Dict[str, Any]] = Field(default=None, description="Additional configuration for the alert")
    priority: FeedPriority = Field(default=FeedPriority.MEDIUM, description="Priority level of the alert")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the alert")


class AlertCombination(BaseModel):
    """Alert combination containing alert request, SQL, and natural language query"""
    alert_request: str = Field(..., description="Natural language description of the alert requirements")
    sql_query: str = Field(..., description="SQL query for the alert")
    natural_language_query: str = Field(..., description="Natural language description of the query")
    alert_id: Optional[str] = Field(default=None, description="Optional unique identifier for the alert")
    alert_name: Optional[str] = Field(default=None, description="Optional human-readable name for the alert")
    configuration: Optional[Dict[str, Any]] = Field(default=None, description="Additional configuration for the alert")
    priority: FeedPriority = Field(default=FeedPriority.MEDIUM, description="Priority level of the alert")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the alert")


class FeedConfiguration(BaseModel):
    """Feed configuration for managing multiple alerts"""
    feed_id: str = Field(..., description="Unique identifier for the feed")
    feed_name: str = Field(..., description="Human-readable name for the feed")
    description: Optional[str] = Field(default=None, description="Description of the feed")
    project_id: str = Field(..., description="Project identifier")
    data_description: Optional[str] = Field(default=None, description="Description of the data being monitored")
    alert_sets: List[AlertSet] = Field(default_factory=list, description="List of alert sets in this feed (legacy)")
    alert_combinations: List[AlertCombination] = Field(default_factory=list, description="List of alert combinations [alert_request, sql, natural_language_query]")
    global_configuration: Optional[Dict[str, Any]] = Field(default=None, description="Global configuration for all alerts in the feed")
    notification_settings: Optional[Dict[str, Any]] = Field(default=None, description="Global notification settings")
    schedule_settings: Optional[Dict[str, Any]] = Field(default=None, description="Global schedule settings")
    status: FeedStatus = Field(default=FeedStatus.PENDING, description="Current status of the feed")
    priority: FeedPriority = Field(default=FeedPriority.MEDIUM, description="Overall priority of the feed")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the feed")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the feed")


class FeedProcessingResult(BaseModel):
    """Result of processing a single alert set"""
    alert_id: str
    alert_name: str
    success: bool
    feed_configuration: Optional[Dict[str, Any]] = None
    sql_analysis: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    critique_notes: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    priority: FeedPriority = FeedPriority.MEDIUM


class FeedManagementResult(BaseModel):
    """Complete result of feed management processing"""
    feed_id: str
    feed_name: str
    project_id: str
    total_alerts: int
    successful_alerts: int
    failed_alerts: int
    processing_results: List[FeedProcessingResult]
    combined_feed_configurations: Dict[str, Any]
    global_metadata: Dict[str, Any]
    execution_time: float
    status: FeedStatus
    created_at: datetime
    updated_at: datetime


class FeedManagementPipeline(AgentPipeline):
    """Pipeline for managing multiple sets of alerts with feed IDs and configurations"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        alert_agent: Optional[Any] = None,
        llm_settings: Optional[Dict[str, Any]] = None
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
            "enable_parallel_processing": True,
            "enable_validation": True,
            "enable_metrics": True,
            "max_concurrent_alerts": 10,
            "default_confidence_threshold": 0.8,
            "enable_global_configuration": True,
            "enable_notification_aggregation": True
        }
        
        self._metrics = {}
        self._engine = engine
        self._feed_registry = {}  # In-memory feed registry
        
        # Initialize alert agent if not provided
        if not alert_agent:
            if not llm_settings:
                llm_settings = {
                    "model_name": "gpt-4o-mini",
                    "sql_parser_temp": 0.0,
                    "alert_generator_temp": 0.1,
                    "critic_temp": 0.0,
                    "refiner_temp": 0.2
                }
            
            # Import here to avoid circular imports
            from app.agents.nodes.writers.alerts_agent import SQLToAlertAgent
            from app.core.dependencies import create_llm_instances_from_settings
            sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm = create_llm_instances_from_settings()
            
            self._alert_agent = SQLToAlertAgent(
                sql_parser_llm=sql_parser_llm,
                alert_generator_llm=alert_generator_llm,
                critic_llm=critic_llm,
                refiner_llm=refiner_llm
            )
        else:
            self._alert_agent = alert_agent
        
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
        feed_configuration: FeedConfiguration,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process a feed configuration with multiple alert sets
        
        Args:
            feed_configuration: FeedConfiguration object containing all alert sets and settings
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing complete feed management results
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not feed_configuration.alert_sets and not feed_configuration.alert_combinations:
            raise ValueError("Feed configuration must contain at least one alert set or alert combination")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Calculate total alerts (combinations + legacy alert_sets)
        total_alerts = len(feed_configuration.alert_combinations) + len(feed_configuration.alert_sets)
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "feed_processing_started",
            {
                "feed_id": feed_configuration.feed_id,
                "feed_name": feed_configuration.feed_name,
                "project_id": feed_configuration.project_id,
                "total_alerts": total_alerts,
                "alert_combinations": len(feed_configuration.alert_combinations),
                "legacy_alert_sets": len(feed_configuration.alert_sets),
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            # Register feed in memory registry
            self._register_feed(feed_configuration)
            
            # Process alert combinations and legacy alert sets
            if self._configuration["enable_parallel_processing"]:
                processing_results = await self._process_alerts_parallel(
                    feed_configuration, 
                    status_callback
                )
            else:
                processing_results = await self._process_alerts_sequential(
                    feed_configuration, 
                    status_callback
                )
            
            # Generate combined feed configurations
            combined_configurations = self._generate_combined_feed_configurations(
                processing_results, 
                feed_configuration
            )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            successful_alerts = sum(1 for result in processing_results if result.success)
            failed_alerts = len(processing_results) - successful_alerts
            
            # Update internal metrics
            self._update_metrics(
                feed_id=feed_configuration.feed_id,
                total_alerts=total_alerts,
                successful_alerts=successful_alerts,
                failed_alerts=failed_alerts,
                execution_time=total_execution_time,
                project_id=feed_configuration.project_id
            )
            
            # Create final result
            feed_result = FeedManagementResult(
                feed_id=feed_configuration.feed_id,
                feed_name=feed_configuration.feed_name,
                project_id=feed_configuration.project_id,
                total_alerts=total_alerts,
                successful_alerts=successful_alerts,
                failed_alerts=failed_alerts,
                processing_results=processing_results,
                combined_feed_configurations=combined_configurations,
                global_metadata=self._generate_global_metadata(feed_configuration, processing_results),
                execution_time=total_execution_time,
                status=FeedStatus.ACTIVE if successful_alerts > 0 else FeedStatus.ERROR,
                created_at=start_time,
                updated_at=end_time
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "feed_processing_completed",
                {
                    "feed_id": feed_configuration.feed_id,
                    "project_id": feed_configuration.project_id,
                    "execution_time": total_execution_time,
                    "successful_alerts": successful_alerts,
                    "failed_alerts": failed_alerts,
                    "status": feed_result.status.value
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": True,
                    "feed_management_result": feed_result.dict(),
                    "orchestration_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "feed_id": feed_configuration.feed_id,
                        "project_id": feed_configuration.project_id,
                        "parallel_processing_enabled": self._configuration["enable_parallel_processing"],
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
            logger.error(f"Error in feed management pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "feed_processing_error",
                {
                    "error": str(e),
                    "feed_id": feed_configuration.feed_id,
                    "project_id": feed_configuration.project_id
                }
            )
            
            # Update metrics with error
            self._metrics.update({
                "last_error": str(e),
                "total_errors": self._metrics.get("total_errors", 0) + 1
            })
            
            raise

    def _register_feed(self, feed_configuration: FeedConfiguration) -> None:
        """Register feed in memory registry"""
        self._feed_registry[feed_configuration.feed_id] = {
            "configuration": feed_configuration,
            "registered_at": datetime.now(),
            "status": FeedStatus.PENDING
        }

    async def _process_alerts_parallel(
        self, 
        feed_configuration: FeedConfiguration, 
        status_callback: Optional[Callable]
    ) -> List[FeedProcessingResult]:
        """Process alert combinations and legacy alert sets in parallel"""
        max_concurrent = self._configuration.get("max_concurrent_alerts", 10)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single_alert_combination(alert_combination: AlertCombination) -> FeedProcessingResult:
            async with semaphore:
                return await self._process_single_alert_combination(alert_combination, feed_configuration, status_callback)
        
        async def process_single_alert_set(alert_set: AlertSet) -> FeedProcessingResult:
            async with semaphore:
                return await self._process_single_alert_set(alert_set, feed_configuration, status_callback)
        
        # Create tasks for all alert combinations and legacy alert sets
        tasks = []
        
        # Process alert combinations
        for alert_combination in feed_configuration.alert_combinations:
            tasks.append(process_single_alert_combination(alert_combination))
        
        # Process legacy alert sets
        for alert_set in feed_configuration.alert_sets:
            tasks.append(process_single_alert_set(alert_set))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        task_index = 0
        
        # Handle alert combination results
        for i, result in enumerate(results[:len(feed_configuration.alert_combinations)]):
            if isinstance(result, Exception):
                alert_combination = feed_configuration.alert_combinations[i]
                error_result = FeedProcessingResult(
                    alert_id=alert_combination.alert_id or f"combination_{i}",
                    alert_name=alert_combination.alert_name or f"Alert Combination {i+1}",
                    success=False,
                    error_message=str(result),
                    priority=alert_combination.priority
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        # Handle legacy alert set results
        for i, result in enumerate(results[len(feed_configuration.alert_combinations):]):
            if isinstance(result, Exception):
                alert_set = feed_configuration.alert_sets[i]
                error_result = FeedProcessingResult(
                    alert_id=alert_set.alert_id,
                    alert_name=alert_set.alert_name,
                    success=False,
                    error_message=str(result),
                    priority=alert_set.priority
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        return processed_results

    async def _process_alerts_sequential(
        self, 
        feed_configuration: FeedConfiguration, 
        status_callback: Optional[Callable]
    ) -> List[FeedProcessingResult]:
        """Process alert combinations and legacy alert sets sequentially"""
        results = []
        
        # Process alert combinations first
        for alert_combination in feed_configuration.alert_combinations:
            result = await self._process_single_alert_combination(alert_combination, feed_configuration, status_callback)
            results.append(result)
        
        # Process legacy alert sets
        for alert_set in feed_configuration.alert_sets:
            result = await self._process_single_alert_set(alert_set, feed_configuration, status_callback)
            results.append(result)
        
        return results

    async def _process_single_alert_combination(
        self, 
        alert_combination: AlertCombination, 
        feed_configuration: FeedConfiguration,
        status_callback: Optional[Callable]
    ) -> FeedProcessingResult:
        """Process a single alert combination"""
        start_time = datetime.now()
        
        # Generate alert_id and alert_name if not provided
        alert_id = alert_combination.alert_id or f"combination_{uuid4().hex[:8]}"
        alert_name = alert_combination.alert_name or f"Alert Combination {alert_id}"
        
        self._send_status_update(
            status_callback,
            "alert_processing_started",
            {
                "feed_id": feed_configuration.feed_id,
                "alert_id": alert_id,
                "alert_name": alert_name,
                "type": "alert_combination"
            }
        )
        
        try:
            # Create alert request
            from app.agents.nodes.writers.alerts_agent import SQLAlertRequest
            
            alert_request = SQLAlertRequest(
                sql=alert_combination.sql_query,
                query=alert_combination.natural_language_query,
                project_id=feed_configuration.project_id,
                data_description=feed_configuration.data_description,
                configuration=self._merge_configurations(
                    feed_configuration.global_configuration,
                    alert_combination.configuration
                ),
                alert_request=alert_combination.alert_request,
                session_id=f"{feed_configuration.feed_id}_{alert_id}"
            )
            
            # Generate alert configuration
            alert_result = await self._alert_agent.generate_alert(alert_request)
            
            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Create processing result
            result = FeedProcessingResult(
                alert_id=alert_id,
                alert_name=alert_name,
                success=True,
                feed_configuration=alert_result.feed_configuration.dict(),
                sql_analysis=alert_result.sql_analysis.dict(),
                confidence_score=alert_result.confidence_score,
                critique_notes=alert_result.critique_notes,
                suggestions=alert_result.suggestions,
                processing_time=processing_time,
                priority=alert_combination.priority
            )
            
            self._send_status_update(
                status_callback,
                "alert_processing_completed",
                {
                    "feed_id": feed_configuration.feed_id,
                    "alert_id": alert_id,
                    "success": True,
                    "confidence_score": alert_result.confidence_score,
                    "processing_time": processing_time,
                    "type": "alert_combination"
                }
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            error_result = FeedProcessingResult(
                alert_id=alert_id,
                alert_name=alert_name,
                success=False,
                error_message=str(e),
                processing_time=processing_time,
                priority=alert_combination.priority
            )
            
            self._send_status_update(
                status_callback,
                "alert_processing_failed",
                {
                    "feed_id": feed_configuration.feed_id,
                    "alert_id": alert_id,
                    "error": str(e),
                    "processing_time": processing_time,
                    "type": "alert_combination"
                }
            )
            
            return error_result

    async def _process_single_alert_set(
        self, 
        alert_set: AlertSet, 
        feed_configuration: FeedConfiguration,
        status_callback: Optional[Callable]
    ) -> FeedProcessingResult:
        """Process a single alert set"""
        start_time = datetime.now()
        
        self._send_status_update(
            status_callback,
            "alert_processing_started",
            {
                "feed_id": feed_configuration.feed_id,
                "alert_id": alert_set.alert_id,
                "alert_name": alert_set.alert_name,
                "type": "legacy_alert_set"
            }
        )
        
        try:
            # Create alert request
            from app.agents.nodes.writers.alerts_agent import SQLAlertRequest
            
            alert_request = SQLAlertRequest(
                sql=alert_set.sql_query,
                query=alert_set.natural_language_query,
                project_id=feed_configuration.project_id,
                data_description=feed_configuration.data_description,
                configuration=self._merge_configurations(
                    feed_configuration.global_configuration,
                    alert_set.configuration
                ),
                alert_request=alert_set.alert_request,
                session_id=f"{feed_configuration.feed_id}_{alert_set.alert_id}"
            )
            
            # Generate alert configuration
            alert_result = await self._alert_agent.generate_alert(alert_request)
            
            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Create processing result
            result = FeedProcessingResult(
                alert_id=alert_set.alert_id,
                alert_name=alert_set.alert_name,
                success=True,
                feed_configuration=alert_result.feed_configuration.dict(),
                sql_analysis=alert_result.sql_analysis.dict(),
                confidence_score=alert_result.confidence_score,
                critique_notes=alert_result.critique_notes,
                suggestions=alert_result.suggestions,
                processing_time=processing_time,
                priority=alert_set.priority
            )
            
            self._send_status_update(
                status_callback,
                "alert_processing_completed",
                {
                    "feed_id": feed_configuration.feed_id,
                    "alert_id": alert_set.alert_id,
                    "success": True,
                    "confidence_score": alert_result.confidence_score,
                    "processing_time": processing_time,
                    "type": "legacy_alert_set"
                }
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            error_result = FeedProcessingResult(
                alert_id=alert_set.alert_id,
                alert_name=alert_set.alert_name,
                success=False,
                error_message=str(e),
                processing_time=processing_time,
                priority=alert_set.priority
            )
            
            self._send_status_update(
                status_callback,
                "alert_processing_failed",
                {
                    "feed_id": feed_configuration.feed_id,
                    "alert_id": alert_set.alert_id,
                    "error": str(e),
                    "processing_time": processing_time,
                    "type": "legacy_alert_set"
                }
            )
            
            return error_result

    def _merge_configurations(
        self, 
        global_config: Optional[Dict[str, Any]], 
        alert_config: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Merge global and alert-specific configurations"""
        if not global_config and not alert_config:
            return None
        
        merged = {}
        if global_config:
            merged.update(global_config)
        if alert_config:
            merged.update(alert_config)
        
        return merged

    def _generate_combined_feed_configurations(
        self, 
        processing_results: List[FeedProcessingResult], 
        feed_configuration: FeedConfiguration
    ) -> Dict[str, Any]:
        """Generate combined feed configurations from processing results"""
        successful_results = [r for r in processing_results if r.success]
        
        if not successful_results:
            return {
                "feeds": [],
                "summary": {
                    "total_feeds": 0,
                    "successful_feeds": 0,
                    "failed_feeds": len(processing_results),
                    "feed_id": feed_configuration.feed_id
                }
            }
        
        # Group by priority
        priority_groups = {}
        for result in successful_results:
            priority = result.priority.value
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(result)
        
        # Create combined configurations
        combined_configs = {
            "feeds": [],
            "summary": {
                "total_feeds": len(processing_results),
                "successful_feeds": len(successful_results),
                "failed_feeds": len(processing_results) - len(successful_results),
                "feed_id": feed_configuration.feed_id,
                "priority_distribution": {k: len(v) for k, v in priority_groups.items()},
                "average_confidence": sum(r.confidence_score for r in successful_results) / len(successful_results) if successful_results else 0.0
            },
            "global_settings": {
                "notification_settings": feed_configuration.notification_settings,
                "schedule_settings": feed_configuration.schedule_settings,
                "global_configuration": feed_configuration.global_configuration
            }
        }
        
        # Convert each successful result to API payload format
        for result in successful_results:
            if result.feed_configuration:
                # Import the required models
                from app.agents.nodes.writers.alerts_agent import LexyFeedConfiguration, LexyFeedMetric, LexyFeedCondition, LexyFeedNotification, SQLAnalysis, SQLAlertResult
                
                # Reconstruct the Pydantic models from dictionaries
                metric = LexyFeedMetric(**result.feed_configuration["metric"])
                condition = LexyFeedCondition(**result.feed_configuration["condition"])
                notification = LexyFeedNotification(**result.feed_configuration["notification"])
                
                feed_config = LexyFeedConfiguration(
                    metric=metric,
                    condition=condition,
                    notification=notification,
                    column_selection=result.feed_configuration["column_selection"]
                )
                
                sql_analysis = SQLAnalysis(**result.sql_analysis)
                
                # Create proper SQLAlertResult
                sql_alert_result = SQLAlertResult(
                    feed_configuration=feed_config,
                    sql_analysis=sql_analysis,
                    confidence_score=result.confidence_score,
                    critique_notes=result.critique_notes,
                    suggestions=result.suggestions
                )
                
                api_payload = self._alert_agent.create_lexy_api_payload(sql_alert_result)
                combined_configs["feeds"].append(api_payload)
        
        return combined_configs

    def _generate_global_metadata(
        self, 
        feed_configuration: FeedConfiguration, 
        processing_results: List[FeedProcessingResult]
    ) -> Dict[str, Any]:
        """Generate global metadata for the feed"""
        successful_results = [r for r in processing_results if r.success]
        
        return {
            "feed_metadata": {
                "feed_id": feed_configuration.feed_id,
                "feed_name": feed_configuration.feed_name,
                "description": feed_configuration.description,
                "project_id": feed_configuration.project_id,
                "tags": feed_configuration.tags,
                "priority": feed_configuration.priority.value,
                "status": feed_configuration.status.value
            },
            "processing_metadata": {
                "total_alerts": len(processing_results),
                "successful_alerts": len(successful_results),
                "failed_alerts": len(processing_results) - len(successful_results),
                "success_rate": len(successful_results) / len(processing_results) if processing_results else 0.0,
                "average_confidence": sum(r.confidence_score for r in successful_results) / len(successful_results) if successful_results else 0.0,
                "average_processing_time": sum(r.processing_time for r in processing_results) / len(processing_results) if processing_results else 0.0
            },
            "alert_metadata": [
                {
                    "alert_id": r.alert_id,
                    "alert_name": r.alert_name,
                    "success": r.success,
                    "confidence_score": r.confidence_score,
                    "processing_time": r.processing_time,
                    "priority": r.priority.value
                }
                for r in processing_results
            ]
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
        logger.info(f"Feed Management Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        feed_id: str,
        total_alerts: int,
        successful_alerts: int,
        failed_alerts: int,
        execution_time: float,
        project_id: str
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "feed_id": feed_id,
                "total_alerts": total_alerts,
                "successful_alerts": successful_alerts,
                "failed_alerts": failed_alerts,
                "execution_time": execution_time,
                "project_id": project_id,
                "timestamp": datetime.now().isoformat()
            },
            "total_executions": self._metrics.get("total_executions", 0) + 1,
            "total_feeds_processed": self._metrics.get("total_feeds_processed", 0) + 1,
            "total_alerts_processed": self._metrics.get("total_alerts_processed", 0) + total_alerts,
            "total_successful_alerts": self._metrics.get("total_successful_alerts", 0) + successful_alerts,
            "total_failed_alerts": self._metrics.get("total_failed_alerts", 0) + failed_alerts,
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
            "feed_registry_size": len(self._feed_registry),
            "registered_feeds": list(self._feed_registry.keys()),
            "timestamp": datetime.now().isoformat()
        }

    def get_feed_registry(self) -> Dict[str, Any]:
        """Get the current feed registry"""
        return self._feed_registry.copy()

    def get_feed_by_id(self, feed_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific feed by ID"""
        return self._feed_registry.get(feed_id)

    def enable_parallel_processing(self, enabled: bool) -> None:
        """Enable or disable parallel processing"""
        self._configuration["enable_parallel_processing"] = enabled
        logger.info(f"Parallel processing {'enabled' if enabled else 'disabled'}")

    def set_max_concurrent_alerts(self, max_concurrent: int) -> None:
        """Set maximum number of concurrent alerts"""
        if max_concurrent > 0:
            self._configuration["max_concurrent_alerts"] = max_concurrent
            logger.info(f"Max concurrent alerts set to {max_concurrent}")
        else:
            raise ValueError("Max concurrent alerts must be greater than 0")

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold for alert validation"""
        if 0.0 <= threshold <= 1.0:
            self._configuration["default_confidence_threshold"] = threshold
            logger.info(f"Confidence threshold set to {threshold}")
        else:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")


# Factory function for creating feed management pipeline
def create_feed_management_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    alert_agent: Optional[Any] = None,
    llm_settings: Optional[Dict[str, Any]] = None,
    **kwargs
) -> FeedManagementPipeline:
    """
    Factory function to create a feed management pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        alert_agent: SQL-to-Alert agent instance (optional, will create default if not provided)
        llm_settings: LLM configuration settings (optional, will use defaults if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        FeedManagementPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return FeedManagementPipeline(
        name="feed_management_pipeline",
        version="1.0.0",
        description="Pipeline for managing multiple sets of alerts with feed IDs and configurations",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        alert_agent=alert_agent,
        llm_settings=llm_settings,
        **kwargs
    )
