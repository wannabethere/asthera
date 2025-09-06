from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from app.services.servicebase import BaseService
from app.agents.pipelines.pipeline_container import PipelineContainer


class AlertRequestType(str, Enum):
    """Type of alert request"""
    SINGLE_ALERT = "single_alert"
    FEED_MANAGEMENT = "feed_management"


class AlertPriority(str, Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SingleAlertRequest(BaseModel):
    """Request model for creating a single alert"""
    request_type: AlertRequestType = AlertRequestType.SINGLE_ALERT
    sql_queries: List[str] = Field(..., description="List of SQL queries to analyze for alert generation")
    natural_language_query: str = Field(..., description="Natural language description of the queries")
    alert_request: str = Field(..., description="Natural language description of the desired alert")
    project_id: str = Field(..., description="Project identifier")
    data_description: Optional[str] = Field(default=None, description="Description of the data being analyzed")
    session_id: Optional[str] = Field(default=None, description="Session identifier for tracking")
    additional_context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for alert generation")
    configuration: Optional[Dict[str, Any]] = Field(default=None, description="Pipeline configuration overrides")


class AlertSet(BaseModel):
    """Individual alert set configuration for feed management"""
    alert_id: str = Field(..., description="Unique identifier for the alert")
    alert_name: str = Field(..., description="Human-readable name for the alert")
    sql_query: str = Field(..., description="SQL query for the alert")
    natural_language_query: str = Field(..., description="Natural language description of the query")
    alert_request: str = Field(..., description="Natural language description of the alert requirements")
    configuration: Optional[Dict[str, Any]] = Field(default=None, description="Additional configuration for the alert")
    priority: AlertPriority = Field(default=AlertPriority.MEDIUM, description="Priority level of the alert")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the alert")


class AlertCombination(BaseModel):
    """Alert combination containing alert request, SQL, and natural language query"""
    alert_request: str = Field(..., description="Natural language description of the alert requirements")
    sql_query: str = Field(..., description="SQL query for the alert")
    natural_language_query: str = Field(..., description="Natural language description of the query")
    alert_id: Optional[str] = Field(default=None, description="Optional unique identifier for the alert")
    alert_name: Optional[str] = Field(default=None, description="Optional human-readable name for the alert")
    configuration: Optional[Dict[str, Any]] = Field(default=None, description="Additional configuration for the alert")
    priority: AlertPriority = Field(default=AlertPriority.MEDIUM, description="Priority level of the alert")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the alert")


class FeedManagementRequest(BaseModel):
    """Request model for feed management"""
    request_type: AlertRequestType = AlertRequestType.FEED_MANAGEMENT
    feed_id: str = Field(..., description="Unique identifier for the feed")
    feed_name: str = Field(..., description="Human-readable name for the feed")
    description: Optional[str] = Field(default=None, description="Description of the feed")
    project_id: str = Field(..., description="Project identifier")
    data_description: Optional[str] = Field(default=None, description="Description of the data being monitored")
    alert_sets: List[AlertSet] = Field(default_factory=list, description="List of alert sets in this feed (legacy)")
    alert_combinations: List[AlertCombination] = Field(default_factory=list, description="List of alert combinations")
    global_configuration: Optional[Dict[str, Any]] = Field(default=None, description="Global configuration for all alerts in the feed")
    notification_settings: Optional[Dict[str, Any]] = Field(default=None, description="Global notification settings")
    schedule_settings: Optional[Dict[str, Any]] = Field(default=None, description="Global schedule settings")
    priority: AlertPriority = Field(default=AlertPriority.MEDIUM, description="Overall priority of the feed")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the feed")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the feed")
    configuration: Optional[Dict[str, Any]] = Field(default=None, description="Pipeline configuration overrides")


class AlertRequest(BaseModel):
    """Union request model that can handle both single alerts and feed management"""
    request_type: AlertRequestType = Field(..., description="Type of alert request")
    
    # Single alert fields
    sql_queries: Optional[List[str]] = Field(default=None, description="List of SQL queries for single alert")
    natural_language_query: Optional[str] = Field(default=None, description="Natural language description for single alert")
    alert_request: Optional[str] = Field(default=None, description="Alert request for single alert")
    project_id: str = Field(..., description="Project identifier")
    data_description: Optional[str] = Field(default=None, description="Description of the data")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    additional_context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    
    # Feed management fields
    feed_id: Optional[str] = Field(default=None, description="Feed identifier for feed management")
    feed_name: Optional[str] = Field(default=None, description="Feed name for feed management")
    description: Optional[str] = Field(default=None, description="Feed description")
    alert_sets: List[AlertSet] = Field(default_factory=list, description="Alert sets for feed management")
    alert_combinations: List[AlertCombination] = Field(default_factory=list, description="Alert combinations for feed management")
    global_configuration: Optional[Dict[str, Any]] = Field(default=None, description="Global configuration")
    notification_settings: Optional[Dict[str, Any]] = Field(default=None, description="Notification settings")
    schedule_settings: Optional[Dict[str, Any]] = Field(default=None, description="Schedule settings")
    priority: AlertPriority = Field(default=AlertPriority.MEDIUM, description="Priority level")
    tags: List[str] = Field(default_factory=list, description="Tags")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    
    # Common fields
    configuration: Optional[Dict[str, Any]] = Field(default=None, description="Pipeline configuration overrides")


class AlertResponse(BaseModel):
    """Response model for alert service"""
    success: bool = Field(..., description="Whether the request was successful")
    request_type: AlertRequestType = Field(..., description="Type of request that was processed")
    result: Dict[str, Any] = Field(..., description="The processing result")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the processing")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the response")



# =============================================================================
# COMPATIBILITY MODELS FOR MAIN.PY INTEGRATION
# =============================================================================

class Condition(BaseModel):
    """Compatibility model for main.py Condition - matches the original structure with optional service fields"""
    conditionType: str
    metricselected: str
    schedule: str
    timecolumn: str
    value: Optional[str] = None
    
    # Optional service-managed fields
    alert_id: Optional[str] = None
    alert_name: Optional[str] = None
    sql_query: Optional[str] = None
    natural_language_query: Optional[str] = None
    alert_request: Optional[str] = None
    priority: Optional[AlertPriority] = None
    tags: Optional[List[str]] = None
    configuration: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AlertResponseCompatibility(BaseModel):
    """Compatibility model for main.py AlertResponse - matches the original structure with optional service fields"""
    type: str
    question: str
    alertname: str
    summary: str
    reasoning: str
    conditions: List[Condition]
    notificationgroup: str
    
    # Optional service-managed fields
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    feed_id: Optional[str] = None
    feed_name: Optional[str] = None
    global_configuration: Optional[Dict[str, Any]] = None
    notification_settings: Optional[Dict[str, Any]] = None
    schedule_settings: Optional[Dict[str, Any]] = None
    priority: Optional[AlertPriority] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    service_created: Optional[bool] = None
    service_metadata: Optional[Dict[str, Any]] = None


class Configs(BaseModel):
    """Compatibility model for main.py Configs - matches the original structure with optional service fields"""
    conditionTypes: List[str]
    notificationgroups: List[str]  
    schedule: List[str]
    timecolumn: List[str]
    availableMetrics: List[str]
    question: str
    
    # Optional service-managed fields
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    global_configuration: Optional[Dict[str, Any]] = None
    notification_settings: Optional[Dict[str, Any]] = None
    schedule_settings: Optional[Dict[str, Any]] = None
    priority: Optional[AlertPriority] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        # Allow extra fields and be more flexible with validation
        extra = "forbid"
        str_strip_whitespace = True


class AlertCreate(BaseModel):
    """Compatibility model for main.py AlertCreate - matches the original structure with optional service fields"""
    input: str
    config: Optional[Configs] = None
    session_id: Optional[str] = None  # For multi-turn conversations
    
    # Optional service-managed fields
    project_id: Optional[str] = None
    data_description: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None
    priority: Optional[AlertPriority] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        # Be more flexible with field names
        extra = "forbid"


class AlertService(BaseService[AlertRequest, AlertResponse]):
    """Service for handling alert creation and feed management"""
    
    def __init__(self, pipeline_container: Optional[PipelineContainer] = None):
        """Initialize the alert service.
        
        Args:
            pipeline_container: Pipeline container instance (optional, will get singleton if not provided)
            
        Raises:
            ValueError: If required pipelines are not available
            RuntimeError: If pipeline container cannot be initialized
        """
        self._pipeline_container = pipeline_container or PipelineContainer.get_instance()
        
        # Validate that required pipelines are available
        self._validate_required_pipelines()
        
        super().__init__(pipelines={})
    
    def _validate_required_pipelines(self):
        """Validate that all required pipelines are available.
        
        Note: This validation is lenient and will only warn about missing pipelines
        rather than failing completely, as some pipelines may not be available
        due to import errors or configuration issues.
        """
        required_pipelines = ["alert_orchestrator", "feed_management"]
        missing_pipelines = []
        
        for pipeline_name in required_pipelines:
            try:
                pipeline = self._pipeline_container.get_pipeline(pipeline_name)
                if pipeline is None:
                    missing_pipelines.append(pipeline_name)
            except Exception as e:
                missing_pipelines.append(f"{pipeline_name} (error: {str(e)})")
        
        if missing_pipelines:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"AlertService: Some required pipelines are missing or unavailable: {', '.join(missing_pipelines)}. "
                f"Alert service will start with limited functionality. Please ensure all required pipelines are properly configured."
            )
            # Don't raise an error, just log a warning
    
    def _get_alert_orchestrator_pipeline(self):
        """Get the alert orchestrator pipeline with validation.
        
        Returns:
            The alert orchestrator pipeline or None if not available
            
        Raises:
            RuntimeError: If the pipeline is not available
        """
        try:
            pipeline = self._pipeline_container.get_pipeline("alert_orchestrator")
            if pipeline is None:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("alert_orchestrator pipeline is not available")
            return pipeline
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to get alert_orchestrator pipeline: {str(e)}")
            return None
    
    def _get_feed_management_pipeline(self):
        """Get the feed management pipeline with validation.
        
        Returns:
            The feed management pipeline or None if not available
            
        Raises:
            RuntimeError: If the pipeline is not available
        """
        try:
            pipeline = self._pipeline_container.get_pipeline("feed_management")
            if pipeline is None:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("feed_management pipeline is not available")
            return pipeline
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to get feed_management pipeline: {str(e)}")
            return None
    
    async def _process_request_impl(self, request: AlertRequest) -> Dict[str, Any]:
        """Process the alert request based on its type.
        
        Args:
            request: Alert request to process
            
        Returns:
            Processing result
        """
        if request.request_type == AlertRequestType.SINGLE_ALERT:
            return await self._process_single_alert(request)
        elif request.request_type == AlertRequestType.FEED_MANAGEMENT:
            return await self._process_feed_management(request)
        else:
            raise ValueError(f"Unsupported request type: {request.request_type}")
    
    async def _process_single_alert(self, request: AlertRequest) -> Dict[str, Any]:
        """Process a single alert request.
        
        Args:
            request: Single alert request
            
        Returns:
            Alert generation result
        """
        # Validate required fields for single alert
        if not request.sql_queries or not request.natural_language_query or not request.alert_request:
            raise ValueError("sql_queries, natural_language_query, and alert_request are required for single alert requests")
        
        # Get the alert orchestrator pipeline
        alert_orchestrator = self._get_alert_orchestrator_pipeline()
        
        if alert_orchestrator is None:
            raise RuntimeError("Alert orchestrator pipeline is not available. Please ensure the pipeline is properly configured.")
        
        # Execute the alert orchestration
        result = await alert_orchestrator.run(
            sql_queries=request.sql_queries,
            natural_language_query=request.natural_language_query,
            alert_request=request.alert_request,
            project_id=request.project_id,
            data_description=request.data_description,
            session_id=request.session_id,
            additional_context=request.additional_context,
            configuration=request.configuration
        )
        
        return result
    
    async def _process_feed_management(self, request: AlertRequest) -> Dict[str, Any]:
        """Process a feed management request.
        
        Args:
            request: Feed management request
            
        Returns:
            Feed management result
        """
        # Validate required fields for feed management
        if not request.feed_id or not request.feed_name:
            raise ValueError("feed_id and feed_name are required for feed management requests")
        
        if not request.alert_sets and not request.alert_combinations:
            raise ValueError("At least one alert_set or alert_combination is required for feed management requests")
        
        # Get the feed management pipeline
        feed_management = self._get_feed_management_pipeline()
        
        if feed_management is None:
            raise RuntimeError("Feed management pipeline is not available. Please ensure the pipeline is properly configured.")
        
        # Convert request to FeedConfiguration format
        from app.agents.pipelines.writers.feed_management_pipeline import FeedConfiguration, FeedStatus
        
        feed_config = FeedConfiguration(
            feed_id=request.feed_id,
            feed_name=request.feed_name,
            description=request.description,
            project_id=request.project_id,
            data_description=request.data_description,
            alert_sets=request.alert_sets,
            alert_combinations=request.alert_combinations,
            global_configuration=request.global_configuration,
            notification_settings=request.notification_settings,
            schedule_settings=request.schedule_settings,
            status=FeedStatus.PENDING,
            priority=request.priority,
            tags=request.tags,
            metadata=request.metadata
        )
        
        # Execute the feed management
        result = await feed_management.run(
            feed_configuration=feed_config,
            configuration=request.configuration
        )
        
        return result
    
    def _create_response(self, event_id: str, result: Dict[str, Any]) -> AlertResponse:
        """Create a response object from the processing result.
        
        Args:
            event_id: Unique identifier for the request
            result: Processing result
            
        Returns:
            Alert response object
        """
        # Determine request type from result
        request_type = AlertRequestType.SINGLE_ALERT
        if "feed_management_result" in result.get("post_process", {}):
            request_type = AlertRequestType.FEED_MANAGEMENT
        
        return AlertResponse(
            success=result.get("post_process", {}).get("success", False),
            request_type=request_type,
            result=result,
            metadata={
                "event_id": event_id,
                "pipeline_name": result.get("metadata", {}).get("pipeline_name", "unknown"),
                "pipeline_version": result.get("metadata", {}).get("pipeline_version", "unknown"),
                "execution_timestamp": result.get("metadata", {}).get("execution_timestamp", datetime.now().isoformat())
            }
        )
    
    async def create_single_alert(
        self,
        sql_queries: List[str],
        natural_language_query: str,
        alert_request: str,
        project_id: str,
        data_description: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> AlertResponse:
        """Convenience method for creating a single alert.
        
        Args:
            sql_queries: List of SQL queries to analyze
            natural_language_query: Natural language description of the queries
            alert_request: Natural language description of the desired alert
            project_id: Project identifier
            data_description: Optional description of the data
            session_id: Optional session identifier
            additional_context: Optional additional context
            configuration: Optional pipeline configuration
            
        Returns:
            Alert response
        """
        request = AlertRequest(
            request_type=AlertRequestType.SINGLE_ALERT,
            sql_queries=sql_queries,
            natural_language_query=natural_language_query,
            alert_request=alert_request,
            project_id=project_id,
            data_description=data_description,
            session_id=session_id,
            additional_context=additional_context,
            configuration=configuration
        )
        
        return await self.process_request(request)
    
    async def create_feed(
        self,
        feed_id: str,
        feed_name: str,
        project_id: str,
        alert_combinations: List[AlertCombination],
        description: Optional[str] = None,
        data_description: Optional[str] = None,
        alert_sets: Optional[List[AlertSet]] = None,
        global_configuration: Optional[Dict[str, Any]] = None,
        notification_settings: Optional[Dict[str, Any]] = None,
        schedule_settings: Optional[Dict[str, Any]] = None,
        priority: AlertPriority = AlertPriority.MEDIUM,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> AlertResponse:
        """Convenience method for creating a feed.
        
        Args:
            feed_id: Unique identifier for the feed
            feed_name: Human-readable name for the feed
            project_id: Project identifier
            alert_combinations: List of alert combinations
            description: Optional feed description
            data_description: Optional data description
            alert_sets: Optional legacy alert sets
            global_configuration: Optional global configuration
            notification_settings: Optional notification settings
            schedule_settings: Optional schedule settings
            priority: Priority level
            tags: Optional tags
            metadata: Optional metadata
            configuration: Optional pipeline configuration
            
        Returns:
            Alert response
        """
        request = AlertRequest(
            request_type=AlertRequestType.FEED_MANAGEMENT,
            feed_id=feed_id,
            feed_name=feed_name,
            project_id=project_id,
            description=description,
            data_description=data_description,
            alert_sets=alert_sets or [],
            alert_combinations=alert_combinations,
            global_configuration=global_configuration,
            notification_settings=notification_settings,
            schedule_settings=schedule_settings,
            priority=priority,
            tags=tags or [],
            metadata=metadata,
            configuration=configuration
        )
        
        return await self.process_request(request)



class AlertServiceCompatibility:
    """Compatibility wrapper to provide main.py interface while using alert_service.py functionality"""
    
    def __init__(self, alert_service: 'AlertService', default_project_id: Optional[str] = None):
        """Initialize with an existing AlertService instance
        
        Args:
            alert_service: The AlertService instance to use
            default_project_id: Default project ID to use when not provided
        """
        self.alert_service = alert_service
        self.default_project_id = default_project_id or "default_project"
    
    def convert_condition_to_alert_set(self, condition: Condition, alert_id: str, alert_name: str) -> AlertSet:
        """Convert a Condition to an AlertSet for internal processing"""
        # Use provided SQL query or generate a basic one
        sql_query = condition.sql_query or f"""
        SELECT {condition.metricselected} 
        FROM your_table 
        WHERE {condition.metricselected} {self._get_sql_operator(condition.conditionType)} {condition.value or 'NULL'}
        """
        
        # Use provided natural language query or generate one
        natural_language_query = condition.natural_language_query or f"Monitor {condition.metricselected} with {condition.conditionType} condition"
        
        # Use provided alert request or generate one
        alert_request = condition.alert_request or f"Alert when {condition.metricselected} {condition.conditionType} {condition.value or 'anomaly'}"
        
        # Merge provided configuration with generated one
        base_config = {
            "schedule": condition.schedule,
            "timecolumn": condition.timecolumn,
            "condition_type": condition.conditionType,
            "metric": condition.metricselected,
            "value": condition.value
        }
        configuration = {**base_config, **(condition.configuration or {})}
        
        return AlertSet(
            alert_id=alert_id,
            alert_name=alert_name,
            sql_query=sql_query,
            natural_language_query=natural_language_query,
            alert_request=alert_request,
            configuration=configuration,
            priority=condition.priority or AlertPriority.MEDIUM,
            tags=condition.tags or []
        )
    
    def _get_sql_operator(self, condition_type: str) -> str:
        """Convert condition type to SQL operator"""
        operator_map = {
            "greaterthan": ">",
            "lessthan": "<",
            "equals": "=",
            "contains": "LIKE",
            "notlike": "NOT LIKE",
            "anomalydetection": "IS NOT NULL"  # Placeholder for anomaly detection
        }
        return operator_map.get(condition_type.lower(), "=")
    
    async def create_alerts_from_response(
        self, 
        alert_response: AlertResponseCompatibility, 
        project_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AlertResponse:
        """Convert AlertResponseCompatibility to internal AlertResponse format"""
        
        # Use provided project_id or fall back to default
        project_id = project_id or alert_response.project_id or self.default_project_id
        session_id = session_id or alert_response.session_id
        
        # Convert conditions to alert combinations
        alert_combinations = []
        for i, condition in enumerate(alert_response.conditions):
            # Use provided alert_id or generate one
            alert_id = condition.alert_id or f"{alert_response.alertname.lower().replace(' ', '_')}_{i}"
            alert_name = condition.alert_name or f"{alert_response.alertname} - Condition {i+1}"
            
            alert_set = self.convert_condition_to_alert_set(condition, alert_id, alert_name)
            
            # Convert AlertSet to AlertCombination
            alert_combination = AlertCombination(
                alert_request=alert_response.reasoning,
                sql_query=alert_set.sql_query,
                natural_language_query=alert_set.natural_language_query,
                alert_id=alert_id,
                alert_name=alert_set.alert_name,
                configuration=alert_set.configuration,
                priority=alert_set.priority,
                tags=alert_set.tags + [alert_response.type, alert_response.notificationgroup]
            )
            alert_combinations.append(alert_combination)
        
        # Use provided feed_id/feed_name or generate them
        feed_id = alert_response.feed_id or f"compatibility_feed_{alert_response.alertname.lower().replace(' ', '_')}"
        feed_name = alert_response.feed_name or f"Compatibility Feed: {alert_response.alertname}"
        
        # Merge global configuration
        base_global_config = {
            "notification_group": alert_response.notificationgroup,
            "original_type": alert_response.type,
            "original_question": alert_response.question
        }
        global_configuration = {**base_global_config, **(alert_response.global_configuration or {})}
        
        return await self.alert_service.create_feed(
            feed_id=feed_id,
            feed_name=feed_name,
            project_id=project_id,
            alert_combinations=alert_combinations,
            description=alert_response.summary,
            global_configuration=global_configuration,
            notification_settings=alert_response.notification_settings,
            schedule_settings=alert_response.schedule_settings,
            priority=alert_response.priority or AlertPriority.MEDIUM,
            tags=alert_response.tags or [],
            metadata=alert_response.metadata,
            session_id=session_id
        )
    
    def convert_service_response_to_compatibility(
        self, 
        service_response: AlertResponse
    ) -> AlertResponseCompatibility:
        """Convert internal AlertResponse back to AlertResponseCompatibility format"""
        
        # Extract information from the service response
        result = service_response.result
        metadata = service_response.metadata
        
        # Try to extract alert information from the result and metadata
        alert_name = "Generated Alert"
        summary = "Alert generated from service"
        reasoning = "Alert created using alert service"
        conditions = []
        notification_group = "default"
        
        # Extract from result metadata if available
        if "metadata" in result:
            result_metadata = result["metadata"]
            alert_name = result_metadata.get("alert_name", alert_name)
            summary = result_metadata.get("summary", summary)
            reasoning = result_metadata.get("reasoning", reasoning)
            notification_group = result_metadata.get("notification_group", notification_group)
        
        # Extract service-managed fields
        project_id = metadata.get("event_id")  # Using event_id as project identifier
        session_id = metadata.get("session_id")
        feed_id = result.get("feed_id")
        feed_name = result.get("feed_name")
        global_configuration = result.get("global_configuration", {})
        notification_settings = result.get("notification_settings")
        schedule_settings = result.get("schedule_settings")
        priority = result.get("priority", AlertPriority.MEDIUM)
        tags = result.get("tags", [])
        service_metadata = {
            "pipeline_name": metadata.get("pipeline_name"),
            "pipeline_version": metadata.get("pipeline_version"),
            "execution_timestamp": metadata.get("execution_timestamp")
        }
        
        # Create a basic condition if none exist
        if not conditions:
            conditions = [Condition(
                conditionType="greaterthan",
                metricselected="default_metric",
                schedule="daily",
                timecolumn="rolling",
                value="0",
                alert_id="default_alert",
                alert_name="Default Alert",
                priority=AlertPriority.MEDIUM,
                created_at=datetime.now()
            )]
        
        return AlertResponseCompatibility(
            type="finished",
            question="Generated from alert service",
            alertname=alert_name,
            summary=summary,
            reasoning=reasoning,
            conditions=conditions,
            notificationgroup=notification_group,
            # Service-managed fields
            project_id=project_id,
            session_id=session_id,
            feed_id=feed_id,
            feed_name=feed_name,
            global_configuration=global_configuration,
            notification_settings=notification_settings,
            schedule_settings=schedule_settings,
            priority=priority,
            tags=tags,
            metadata=result,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            service_created=service_response.success,
            service_metadata=service_metadata
        )
    
    async def process_alert_create(
        self, 
        alert_create: AlertCreate,
        project_id: Optional[str] = None
    ) -> AlertResponseCompatibility:
        """Process an AlertCreate request and return a compatibility response
        
        This method handles the full flow from AlertCreate to service response
        and back to compatibility format.
        """
        # Use provided project_id or fall back to default
        project_id = project_id or alert_create.project_id or self.default_project_id
        
        # Create a basic AlertResponseCompatibility from the AlertCreate
        # This is a simplified version - in practice, you'd use your AI service
        # to generate the actual alert response
        alert_response = AlertResponseCompatibility(
            type="finished",
            question=alert_create.config.question if alert_create.config else "Generated from input",
            alertname=f"Alert for: {alert_create.input[:50]}...",
            summary=f"Alert generated from: {alert_create.input}",
            reasoning="Generated from user input",
            conditions=[
                Condition(
                    conditionType="greaterthan",
                    metricselected="default_metric",
                    schedule="daily",
                    timecolumn="rolling",
                    value="0"
                )
            ],
            notificationgroup="default",
            # Service-managed fields
            project_id=project_id,
            session_id=alert_create.session_id,
            global_configuration=alert_create.configuration,
            priority=alert_create.priority,
            tags=alert_create.tags,
            metadata=alert_create.metadata,
            created_at=datetime.now()
        )
        
        # Process through the service
        try:
            service_response = await self.create_alerts_from_response(
                alert_response=alert_response,
                project_id=project_id,
                session_id=alert_create.session_id
            )
            
            # Convert back to compatibility format
            return self.convert_service_response_to_compatibility(service_response)
            
        except Exception as e:
            # Return a basic compatibility response with error info
            return AlertResponseCompatibility(
                type="error",
                question=alert_create.config.question if alert_create.config else "Error processing request",
                alertname="Error Alert",
                summary=f"Error processing alert: {str(e)}",
                reasoning="Service error occurred",
                conditions=[],
                notificationgroup="default",
                project_id=project_id,
                session_id=alert_create.session_id,
                service_created=False,
                service_metadata={"error": str(e)},
                created_at=datetime.now()
            )


# =============================================================================
# CONVENIENCE FUNCTIONS FOR EASY INTEGRATION
# =============================================================================

def create_compatibility_wrapper(alert_service: AlertService, default_project_id: Optional[str] = None) -> AlertServiceCompatibility:
    """Create a compatibility wrapper for an existing AlertService instance
    
    Args:
        alert_service: The AlertService instance (must be properly initialized)
        default_project_id: Default project ID to use when not provided
        
    Returns:
        AlertServiceCompatibility instance
        
    Raises:
        ValueError: If the alert_service is not properly initialized
    """
    if not isinstance(alert_service, AlertService):
        raise ValueError("alert_service must be an instance of AlertService")
    
    return AlertServiceCompatibility(alert_service, default_project_id)


def create_alert_service_with_compatibility(
    pipeline_container: Optional[PipelineContainer] = None, 
    default_project_id: Optional[str] = None
) -> tuple[AlertService, AlertServiceCompatibility]:
    """Create both AlertService and compatibility wrapper instances
    
    Args:
        pipeline_container: Pipeline container instance (optional, will get singleton if not provided)
        default_project_id: Default project ID to use when not provided
        
    Returns:
        Tuple of (AlertService, AlertServiceCompatibility) instances
        
    Raises:
        ValueError: If required pipelines are not available
        RuntimeError: If pipeline container cannot be initialized
    """
    try:
        alert_service = AlertService(pipeline_container)
        compatibility_wrapper = AlertServiceCompatibility(alert_service, default_project_id)
        return alert_service, compatibility_wrapper
    except Exception as e:
        raise RuntimeError(f"Failed to create AlertService with compatibility: {str(e)}")


def create_alert_service_safe(
    pipeline_container: Optional[PipelineContainer] = None,
    default_project_id: Optional[str] = None,
    required_pipelines: Optional[List[str]] = None
) -> tuple[AlertService, AlertServiceCompatibility, bool]:
    """Create AlertService with compatibility wrapper, returning success status
    
    This is a safe version that doesn't raise exceptions but returns a success flag.
    
    Args:
        pipeline_container: Pipeline container instance (optional, will get singleton if not provided)
        default_project_id: Default project ID to use when not provided
        required_pipelines: List of required pipelines (defaults to ["alert_orchestrator", "feed_management"])
        
    Returns:
        Tuple of (AlertService, AlertServiceCompatibility, success_flag)
        If success_flag is False, the first two values will be None
    """
    try:
        alert_service = AlertService(pipeline_container)
        compatibility_wrapper = AlertServiceCompatibility(alert_service, default_project_id)
        return alert_service, compatibility_wrapper, True
    except Exception as e:
        print(f"Warning: Failed to create AlertService: {str(e)}")
        return None, None, False


# =============================================================================
# ALERT COMPATIBILITY SERVICE
# =============================================================================

class AlertCompatibilityService(BaseService[AlertCreate, AlertResponseCompatibility]):
    """Service for handling alert compatibility requests from main.py integration"""
    
    def __init__(self, alert_service: AlertService, default_project_id: Optional[str] = None):
        """Initialize the alert compatibility service.
        
        Args:
            alert_service: The underlying AlertService instance
            default_project_id: Default project ID to use when not provided
        """
        self.alert_service = alert_service
        self.compatibility_wrapper = AlertServiceCompatibility(alert_service, default_project_id)
        super().__init__(pipelines={})
    
    async def _process_request_impl(self, request: AlertCreate) -> Dict[str, Any]:
        """Process an AlertCreate request and return a compatibility response.
        
        Args:
            request: AlertCreate request to process
            
        Returns:
            Processing result as AlertResponseCompatibility
        """
        try:
            # Process the alert create request through the compatibility wrapper
            result = await self.compatibility_wrapper.process_alert_create(request)
            
            return {
                "success": True,
                "result": result.dict(),
                "metadata": {
                    "service_type": "alert_compatibility",
                    "processed_at": datetime.now().isoformat(),
                    "project_id": result.project_id,
                    "session_id": result.session_id
                }
            }
            
        except Exception as e:
            # Return error response
            error_response = AlertResponseCompatibility(
                type="error",
                question=request.config.question if request.config else "Error processing request",
                alertname="Error Alert",
                summary=f"Error processing alert: {str(e)}",
                reasoning="Service error occurred",
                conditions=[],
                notificationgroup="default",
                project_id=request.project_id or self.compatibility_wrapper.default_project_id,
                session_id=request.session_id,
                service_created=False,
                service_metadata={"error": str(e), "error_type": type(e).__name__},
                created_at=datetime.now()
            )
            
            return {
                "success": False,
                "result": error_response.dict(),
                "metadata": {
                    "service_type": "alert_compatibility",
                    "processed_at": datetime.now().isoformat(),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }
    
    def _create_response(self, event_id: str, result: Dict[str, Any]) -> AlertResponseCompatibility:
        """Create a response object from the processing result.
        
        Args:
            event_id: Unique identifier for the request
            result: Processing result
            
        Returns:
            AlertResponseCompatibility object
        """
        # Extract the result data
        result_data = result.get("result", {})
        metadata = result.get("metadata", {})
        
        # Create AlertResponseCompatibility from the result data
        return AlertResponseCompatibility(**result_data)
    
    async def process_alert_create(
        self, 
        alert_create: AlertCreate,
        project_id: Optional[str] = None
    ) -> AlertResponseCompatibility:
        """Convenience method for processing AlertCreate requests.
        
        Args:
            alert_create: AlertCreate request to process
            project_id: Optional project ID override
            
        Returns:
            AlertResponseCompatibility response
        """
        # Override project_id if provided
        if project_id:
            alert_create.project_id = project_id
        
        # Process the request
        response = await self.process_request(alert_create)
        return response
    
    async def create_alerts_from_response(
        self, 
        alert_response: AlertResponseCompatibility, 
        project_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AlertResponseCompatibility:
        """Create alerts from AlertResponseCompatibility and return compatibility response.
        
        Args:
            alert_response: AlertResponseCompatibility to process
            project_id: Optional project ID override
            session_id: Optional session ID override
            
        Returns:
            AlertResponseCompatibility response
        """
        try:
            # Process through the underlying service
            service_response = await self.compatibility_wrapper.create_alerts_from_response(
                alert_response, project_id, session_id
            )
            
            # Convert back to compatibility format
            return self.compatibility_wrapper.convert_service_response_to_compatibility(service_response)
            
        except Exception as e:
            # Return error response
            return AlertResponseCompatibility(
                type="error",
                question=alert_response.question,
                alertname="Error Alert",
                summary=f"Error creating alerts: {str(e)}",
                reasoning="Service error occurred",
                conditions=alert_response.conditions,
                notificationgroup=alert_response.notificationgroup,
                project_id=project_id or alert_response.project_id,
                session_id=session_id or alert_response.session_id,
                service_created=False,
                service_metadata={"error": str(e), "error_type": type(e).__name__},
                created_at=datetime.now()
            )
    
    def get_underlying_alert_service(self) -> AlertService:
        """Get the underlying AlertService instance.
        
        Returns:
            The underlying AlertService instance
        """
        return self.alert_service
    
    def get_compatibility_wrapper(self) -> AlertServiceCompatibility:
        """Get the compatibility wrapper instance.
        
        Returns:
            The AlertServiceCompatibility wrapper instance
        """
        return self.compatibility_wrapper
