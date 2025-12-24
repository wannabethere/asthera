from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import re

from app.services.servicebase import BaseService
from app.agents.pipelines.pipeline_container import PipelineContainer


def parse_alert_request(alert_request: str) -> Dict[str, Any]:
    """
    Parse alert request text to extract threshold values, condition types, and metrics.
    
    Args:
        alert_request: Natural language alert request text
        
    Returns:
        Dictionary containing parsed values:
        - condition_type: The type of condition (greaterthan, lessthan, etc.)
        - threshold_value: The numeric threshold value
        - metric_name: The metric being monitored
        - operator: The comparison operator
    """
    if not alert_request:
        return {
            "condition_type": "greaterthan",
            "threshold_value": "0",
            "metric_name": "default_metric",
            "operator": ">"
        }
    
    # Convert to lowercase for easier matching
    text = alert_request.lower()
    
    # Extract numeric threshold value
    threshold_value = "0"
    number_patterns = [
        r'greater than (\d+(?:,\d{3})*(?:\.\d+)?)',
        r'less than (\d+(?:,\d{3})*(?:\.\d+)?)',
        r'above (\d+(?:,\d{3})*(?:\.\d+)?)',
        r'below (\d+(?:,\d{3})*(?:\.\d+)?)',
        r'exceeds (\d+(?:,\d{3})*(?:\.\d+)?)',
        r'(\d+(?:,\d{3})*(?:\.\d+)?) or more',
        r'(\d+(?:,\d{3})*(?:\.\d+)?) or less',
        r'(\d+(?:,\d{3})*(?:\.\d+)?) or higher',
        r'(\d+(?:,\d{3})*(?:\.\d+)?) or lower',
        r'(\d+(?:,\d{3})*(?:\.\d+)?)%',  # Handle percentage values
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*percent',  # Handle "50 percent"
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*%',  # Handle "50 %"
    ]
    
    for pattern in number_patterns:
        match = re.search(pattern, text)
        if match:
            threshold_value = match.group(1).replace(',', '')  # Remove commas
            break
    
    # Determine condition type and operator
    condition_type = "greaterthan"
    operator = ">"
    
    if any(word in text for word in ['greater than', 'above', 'exceeds', 'more than', 'higher than']):
        condition_type = "greaterthan"
        operator = ">"
    elif any(word in text for word in ['less than', 'below', 'lower than']):
        condition_type = "lessthan"
        operator = "<"
    elif any(word in text for word in ['equal to', 'equals', 'exactly']):
        condition_type = "equals"
        operator = "="
    elif any(word in text for word in ['not equal', 'not equals', 'different from']):
        condition_type = "notequals"
        operator = "!="
    
    # Extract metric name (look for common patterns)
    metric_name = "default_metric"
    metric_patterns = [
        r'(\w+_count)',
        r'(\w+_total)',
        r'(\w+_value)',
        r'(\w+_amount)',
        r'(\w+_number)',
        r'count of (\w+)',
        r'total (\w+)',
        r'number of (\w+)',
        r'(\w+)\s+is\s+greater\s+than',  # "user_count is greater than"
        r'(\w+)\s+is\s+less\s+than',     # "user_count is less than"
        r'(\w+)\s+is\s+above',           # "user_count is above"
        r'(\w+)\s+is\s+below',           # "user_count is below"
        r'(\w+)\s+exceeds',              # "user_count exceeds"
    ]
    
    for pattern in metric_patterns:
        match = re.search(pattern, text)
        if match:
            metric_name = match.group(1)
            break
    
    # Convert threshold_value to float if possible
    try:
        threshold_value_float = float(threshold_value)
    except (ValueError, TypeError) as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to convert threshold value '{threshold_value}' to float: {e}. Using default value 0.0")
        threshold_value_float = 0.0
    
    # Detect if this should be treated as a percentage based on the text
    threshold_type = "default"
    if any(indicator in text for indicator in ['%', 'percent', 'percentage']):
        threshold_type = "percentage"
    elif any(indicator in text for indicator in ['ratio', 'proportion']):
        threshold_type = "ratio"
    
    return {
        "condition_type": condition_type,
        "threshold_value": threshold_value_float,
        "threshold_type": threshold_type,
        "metric_name": metric_name,
        "operator": operator
    }


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

    # New: structured alert payloads that frontends can store/replay as-is (e.g. for /alerts/validate-condition)
    generated_alert_requests: Optional[List[Dict[str, Any]]] = None
    
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
    notification_groups: Optional[List[Dict[str, Any]]] = None


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
        from app.agents.pipelines.writers.feed_management_pipeline import FeedConfiguration, FeedStatus, AlertCombination as FeedAlertCombination, FeedPriority
        
        # Convert AlertCombination objects from alert_service to feed_management_pipeline format
        feed_alert_combinations = []
        for alert_combination in request.alert_combinations:
            # Convert AlertPriority to FeedPriority
            feed_priority = FeedPriority(alert_combination.priority.value) if alert_combination.priority else FeedPriority.MEDIUM
            
            feed_alert_combination = FeedAlertCombination(
                alert_request=alert_combination.alert_request,
                sql_query=alert_combination.sql_query,
                natural_language_query=alert_combination.natural_language_query,
                alert_id=alert_combination.alert_id,
                alert_name=alert_combination.alert_name,
                configuration=alert_combination.configuration,
                priority=feed_priority,
                tags=alert_combination.tags
            )
            feed_alert_combinations.append(feed_alert_combination)
        
        # Convert AlertPriority to FeedPriority for the feed
        feed_priority = FeedPriority(request.priority.value) if request.priority else FeedPriority.MEDIUM
        
        feed_config = FeedConfiguration(
            feed_id=request.feed_id,
            feed_name=request.feed_name,
            description=request.description,
            project_id=request.project_id,
            data_description=request.data_description,
            alert_sets=request.alert_sets,
            alert_combinations=feed_alert_combinations,
            global_configuration=request.global_configuration,
            notification_settings=request.notification_settings,
            schedule_settings=request.schedule_settings,
            status=FeedStatus.PENDING,
            priority=feed_priority,
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
    
    async def validate_alert_condition(
        self,
        sql_query: str,
        condition_type: str,
        operator: str,
        threshold_value: float,
        project_id: str,
        threshold_type: str = "default",
        metric_column: Optional[str] = None,
        use_cache: bool = True,
        overall_condition_logic: str = "any_met"
    ) -> Dict[str, Any]:
        """Validate an alert condition by executing SQL and checking threshold conditions.
        
        Args:
            sql_query: SQL query to execute for validation
            condition_type: Type of condition to validate
            operator: Threshold operator (>, <, >=, <=, =, !=)
            threshold_value: Threshold value to compare against
            project_id: Project identifier for data source access
            threshold_type: Type of threshold value interpretation
            metric_column: Specific column to extract value from (if None, uses first numeric column)
            use_cache: Whether to use caching for SQL execution
            overall_condition_logic: Logic for determining overall condition status
                - "any_met": Condition met if ANY row meets the condition (default)
                - "all_met": Condition met if ALL rows meet the condition
                - "majority_met": Condition met if majority of rows meet the condition
                - "percentage_met": Condition met if specified percentage of rows meet the condition
                
        Returns:
            Dictionary containing validation results
        """
        try:
            # Get the pipeline container to access the SQL execution pipeline
            from app.agents.pipelines.pipeline_container import PipelineContainer
            pipeline_container = PipelineContainer.get_instance()
            
            # Get the SQL execution pipeline which uses the configured engine
            sql_execution_pipeline = pipeline_container.get_pipeline("sql_execution")
            if not sql_execution_pipeline:
                return {
                    "is_valid": False,
                    "current_value": None,
                    "threshold_value": None,
                    "condition_met": None,
                    "error_message": "SQL execution pipeline not available",
                    "validation_timestamp": datetime.now(),
                    "execution_time_ms": None
                }
            
            # Execute the SQL query using the pipeline
            execution_result = await sql_execution_pipeline.run(
                sql=sql_query,
                project_id=project_id,
                configuration={"dry_run": False, "use_cache": use_cache}
            )
            
            # Check if execution was successful
            if not execution_result.get("post_process"):
                return {
                    "is_valid": False,
                    "current_value": None,
                    "threshold_value": None,
                    "condition_met": None,
                    "error_message": "SQL execution failed: No data returned",
                    "validation_timestamp": datetime.now(),
                    "execution_time_ms": None
                }
            
            post_process = execution_result["post_process"]
            
            # Check for execution errors - the SQL execution pipeline returns data directly
            # If there's an error, it will be in the result structure
            if "error" in post_process:
                error_msg = post_process.get("error", "SQL execution failed")
                return {
                    "is_valid": False,
                    "current_value": None,
                    "threshold_value": None,
                    "condition_met": None,
                    "error_message": f"SQL execution failed: {error_msg}",
                    "validation_timestamp": datetime.now(),
                    "execution_time_ms": None
                }
            
            # Extract data from the result
            data = post_process.get("data", [])
            if not data:
                return {
                    "is_valid": False,
                    "current_value": None,
                    "threshold_value": None,
                    "condition_met": None,
                    "error_message": "No data returned from SQL query",
                    "validation_timestamp": datetime.now(),
                    "execution_time_ms": None
                }
            
            # Convert threshold value to float
            try:
                threshold_value_float = float(threshold_value)
            except (ValueError, TypeError):
                return {
                    "is_valid": False,
                    "current_value": None,
                    "threshold_value": None,
                    "condition_met": None,
                    "error_message": f"Invalid threshold value: {threshold_value}",
                    "validation_timestamp": datetime.now(),
                    "execution_time_ms": None
                }
            
            # Process threshold value based on threshold type
            processed_threshold_value = self._process_threshold_value(
                threshold_value_float, 
                threshold_type, 
                data
            )
            
            # Process all rows and check conditions
            validation_results = []
            condition_met_rows = []
            condition_not_met_rows = []
            
            # Debug information
            debug_info = {
                "total_rows_processed": len(data),
                "rows_with_numeric_values": 0,
                "rows_skipped": 0,
                "rows_skipped_data_type_mismatch": 0,
                "rows_skipped_conversion_error": 0,
                "sample_data_types": {},
                "data_type_validation_errors": []
            }
            
            for i, row in enumerate(data):
                # Determine which column to use for validation
                current_value = None
                raw_value = None
                
                if metric_column and metric_column in row:
                    raw_value = row[metric_column]
                else:
                    # Find first numeric column
                    for key, value in row.items():
                        if value is not None:
                            raw_value = value
                            break
                
                if raw_value is None:
                    # Skip rows without values
                    debug_info["rows_skipped"] += 1
                    continue
                
                # Track data types for debugging
                if i < 3:  # Only track first few rows for debugging
                    debug_info["sample_data_types"][f"row_{i}"] = {
                        "raw_value": raw_value,
                        "type": type(raw_value).__name__,
                        "metric_column": metric_column
                    }
                
                # Try to convert to numeric value
                try:
                    # Handle different data types
                    if isinstance(raw_value, (int, float)):
                        current_value = float(raw_value)
                    elif isinstance(raw_value, str):
                        # Try to convert string to float
                        current_value = float(raw_value)
                    else:
                        # Try to convert other types to float
                        current_value = float(raw_value)
                except (ValueError, TypeError) as e:
                    # Skip rows that can't be converted to numeric
                    debug_info["rows_skipped"] += 1
                    debug_info["rows_skipped_conversion_error"] += 1
                    debug_info["data_type_validation_errors"].append({
                        "row_index": i,
                        "error": f"Conversion error: {str(e)}",
                        "raw_value": raw_value,
                        "raw_value_type": type(raw_value).__name__,
                        "condition_type": condition_type
                    })
                    continue
                
                if current_value is None:
                    # Skip rows without numeric values
                    debug_info["rows_skipped"] += 1
                    continue
                
                # Track successful numeric conversion
                debug_info["rows_with_numeric_values"] += 1
                
                # Validate data type compatibility before evaluation
                try:
                    self._validate_data_type_compatibility(
                        condition_type=condition_type,
                        current_value=current_value,
                        operator=operator,
                        threshold_value=processed_threshold_value,
                        row_data=row
                    )
                except ValueError as e:
                    # Skip rows with incompatible data types
                    debug_info["rows_skipped"] += 1
                    debug_info["rows_skipped_data_type_mismatch"] += 1
                    debug_info["data_type_validation_errors"].append({
                        "row_index": i,
                        "error": str(e),
                        "current_value": current_value,
                        "current_value_type": type(current_value).__name__,
                        "condition_type": condition_type,
                        "operator": operator
                    })
                    continue
                
                # Evaluate the condition for this row based on condition type
                condition_met = False
                try:
                    condition_met = self._evaluate_condition_by_type(
                        condition_type=condition_type,
                        current_value=current_value,
                        operator=operator,
                        threshold_value=processed_threshold_value,
                        row_data=row
                    )
                except (TypeError, ValueError) as e:
                    # Skip rows that can't be compared
                    debug_info["rows_skipped"] += 1
                    debug_info["data_type_validation_errors"].append({
                        "row_index": i,
                        "error": f"Evaluation error: {str(e)}",
                        "current_value": current_value,
                        "current_value_type": type(current_value).__name__,
                        "condition_type": condition_type,
                        "operator": operator
                    })
                    continue
                
                # Store result for this row
                row_result = {
                    "row_index": i,
                    "row_data": row,
                    "current_value": current_value,
                    "condition_met": condition_met,
                    "threshold_value": processed_threshold_value,
                    "original_threshold_value": threshold_value_float,
                    "threshold_type": threshold_type
                }
                validation_results.append(row_result)
                
                if condition_met:
                    condition_met_rows.append(row_result)
                else:
                    condition_not_met_rows.append(row_result)
            
            if not validation_results:
                # Provide more detailed error information
                sample_row = data[0] if data else {}
                available_columns = list(sample_row.keys()) if sample_row else []
                sample_values = {k: f"{v} ({type(v).__name__})" for k, v in sample_row.items()} if sample_row else {}
                
                return {
                    "is_valid": False,
                    "current_value": None,
                    "threshold_value": threshold_value_float,
                    "condition_met": None,
                    "error_message": f"No numeric values found in result. Available columns: {available_columns}. Sample values: {sample_values}. Metric column: {metric_column}. Debug info: {debug_info}",
                    "validation_timestamp": datetime.now(),
                    "execution_time_ms": None
                }
            
            # Determine overall validation status based on configurable logic
            overall_condition_met = self._determine_overall_condition_status(
                condition_met_rows, 
                condition_not_met_rows, 
                overall_condition_logic
            )
            overall_is_valid = True  # The validation process itself was successful
            
            # Calculate summary statistics
            total_rows = len(validation_results)
            condition_met_count = len(condition_met_rows)
            condition_not_met_count = len(condition_not_met_rows)
            
            # Get representative current value (first row's value)
            representative_value = validation_results[0]["current_value"] if validation_results else None
            
            return {
                "is_valid": overall_is_valid,
                "current_value": representative_value,
                "threshold_value": processed_threshold_value,
                "original_threshold_value": threshold_value_float,
                "threshold_type": threshold_type,
                "condition_met": overall_condition_met,
                "error_message": None,
                "validation_timestamp": datetime.now(),
                "execution_time_ms": None,
                # Additional detailed results
                "validation_summary": {
                    "total_rows": total_rows,
                    "condition_met_count": condition_met_count,
                    "condition_not_met_count": condition_not_met_count,
                    "condition_met_rate": (condition_met_count / total_rows * 100) if total_rows > 0 else 0
                },
                "condition_not_met_rows": condition_not_met_rows,
                "condition_met_rows": condition_met_rows,
                "all_results": validation_results,
                # Debug information
                "debug_info": debug_info
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "current_value": None,
                "threshold_value": None,
                "condition_met": None,
                "error_message": f"Validation error: {str(e)}",
                "validation_timestamp": datetime.now(),
                "execution_time_ms": None
            }
    
    async def validate_threshold_condition(
        self,
        sql_query: str,
        operator: str,
        threshold_value: float,
        project_id: str,
        threshold_type: str = "default",
        metric_column: Optional[str] = None,
        use_cache: bool = True,
        overall_condition_logic: str = "any_met"
    ) -> Dict[str, Any]:
        """Validate a simple threshold condition.
        
        Args:
            sql_query: SQL query to execute for validation
            operator: Threshold operator (>, <, >=, <=, =, !=)
            threshold_value: Threshold value to compare against
            project_id: Project identifier for data source access
            metric_column: Specific column to extract value from (if None, uses first numeric column)
            use_cache: Whether to use caching for SQL execution
            
        Returns:
            Dictionary containing validation results
        """
        return await self.validate_alert_condition(
            sql_query=sql_query,
            condition_type="threshold_value",
            operator=operator,
            threshold_value=threshold_value,
            project_id=project_id,
            threshold_type=threshold_type,
            metric_column=metric_column,
            use_cache=use_cache,
            overall_condition_logic=overall_condition_logic
        )
    
    def _evaluate_condition_by_type(
        self,
        condition_type: str,
        current_value: Any,
        operator: str,
        threshold_value: float,
        row_data: Dict[str, Any]
    ) -> bool:
        """Evaluate condition based on the condition type.
        
        Args:
            condition_type: Type of condition (threshold_value, intelligent_arima, string_match, etc.)
            current_value: Current value to evaluate
            operator: Comparison operator
            threshold_value: Threshold value for comparison
            row_data: Full row data for advanced conditions
            
        Returns:
            Boolean indicating if condition is met
        """
        if condition_type == "threshold_value":
            return self._evaluate_threshold_condition(current_value, operator, threshold_value)
        elif condition_type == "intelligent_arima":
            return self._evaluate_arima_condition(current_value, operator, threshold_value, row_data)
        elif condition_type == "string_match":
            return self._evaluate_string_condition(current_value, operator, threshold_value, row_data)
        elif condition_type == "threshold_change":
            return self._evaluate_change_condition(current_value, operator, threshold_value, row_data)
        elif condition_type == "threshold_percent_change":
            return self._evaluate_percent_change_condition(current_value, operator, threshold_value, row_data)
        else:
            # Default to threshold condition for unknown types
            return self._evaluate_threshold_condition(current_value, operator, threshold_value)
    
    def _evaluate_threshold_condition(
        self,
        current_value: float,
        operator: str,
        threshold_value: float
    ) -> bool:
        """Evaluate basic threshold conditions.
        
        Args:
            current_value: Current numeric value
            operator: Comparison operator (>, <, >=, <=, =, !=)
            threshold_value: Threshold value for comparison
            
        Returns:
            Boolean indicating if condition is met
        """
        if operator == ">":
            return current_value > threshold_value
        elif operator == "<":
            return current_value < threshold_value
        elif operator == ">=":
            return current_value >= threshold_value
        elif operator == "<=":
            return current_value <= threshold_value
        elif operator == "=":
            return abs(current_value - threshold_value) < 1e-9
        elif operator == "!=":
            return abs(current_value - threshold_value) >= 1e-9
        else:
            raise ValueError(f"Unsupported operator: {operator}")
    
    def _evaluate_arima_condition(
        self,
        current_value: float,
        operator: str,
        threshold_value: float,
        row_data: Dict[str, Any]
    ) -> bool:
        """Evaluate intelligent ARIMA-based conditions.
        
        Args:
            current_value: Current value
            operator: Comparison operator
            threshold_value: Threshold value
            row_data: Full row data for time series analysis
            
        Returns:
            Boolean indicating if condition is met
        """
        # TODO: Implement ARIMA-based anomaly detection
        # This would analyze time series patterns and detect anomalies
        # For now, fall back to threshold condition
        return self._evaluate_threshold_condition(current_value, operator, threshold_value)
    
    def _evaluate_string_condition(
        self,
        current_value: str,
        operator: str,
        threshold_value: str,
        row_data: Dict[str, Any]
    ) -> bool:
        """Evaluate string matching conditions.
        
        Args:
            current_value: Current string value
            operator: String operator (contains, starts_with, ends_with, equals, regex)
            threshold_value: String pattern to match against
            row_data: Full row data for context
            
        Returns:
            Boolean indicating if condition is met
        """
        if operator == "contains":
            return threshold_value.lower() in current_value.lower()
        elif operator == "starts_with":
            return current_value.lower().startswith(threshold_value.lower())
        elif operator == "ends_with":
            return current_value.lower().endswith(threshold_value.lower())
        elif operator == "equals":
            return current_value.lower() == threshold_value.lower()
        elif operator == "regex":
            import re
            return bool(re.search(threshold_value, current_value, re.IGNORECASE))
        elif operator == "not_contains":
            return threshold_value.lower() not in current_value.lower()
        else:
            raise ValueError(f"Unsupported string operator: {operator}")
    
    def _evaluate_change_condition(
        self,
        current_value: float,
        operator: str,
        threshold_value: float,
        row_data: Dict[str, Any]
    ) -> bool:
        """Evaluate absolute change conditions.
        
        Args:
            current_value: Current value
            operator: Change operator (increased_by, decreased_by, changed_by)
            threshold_value: Change threshold
            row_data: Full row data (should contain previous_value)
            
        Returns:
            Boolean indicating if condition is met
        """
        previous_value = row_data.get("previous_value")
        if previous_value is None:
            # If no previous value, can't evaluate change
            return False
        
        try:
            previous_value = float(previous_value)
            change = current_value - previous_value
            
            if operator == "increased_by":
                return change >= threshold_value
            elif operator == "decreased_by":
                return change <= -threshold_value
            elif operator == "changed_by":
                return abs(change) >= threshold_value
            else:
                raise ValueError(f"Unsupported change operator: {operator}")
        except (ValueError, TypeError):
            return False
    
    def _evaluate_percent_change_condition(
        self,
        current_value: float,
        operator: str,
        threshold_value: float,
        row_data: Dict[str, Any]
    ) -> bool:
        """Evaluate percentage change conditions.
        
        Args:
            current_value: Current value
            operator: Change operator (increased_by_percent, decreased_by_percent, changed_by_percent)
            threshold_value: Percentage change threshold
            row_data: Full row data (should contain previous_value)
            
        Returns:
            Boolean indicating if condition is met
        """
        previous_value = row_data.get("previous_value")
        if previous_value is None or previous_value == 0:
            # If no previous value or zero, can't evaluate percentage change
            return False
        
        try:
            previous_value = float(previous_value)
            percent_change = ((current_value - previous_value) / previous_value) * 100
            
            if operator == "increased_by_percent":
                return percent_change >= threshold_value
            elif operator == "decreased_by_percent":
                return percent_change <= -threshold_value
            elif operator == "changed_by_percent":
                return abs(percent_change) >= threshold_value
            else:
                raise ValueError(f"Unsupported percent change operator: {operator}")
        except (ValueError, TypeError, ZeroDivisionError):
            return False
    
    def _determine_overall_condition_status(
        self,
        condition_met_rows: List[Dict[str, Any]],
        condition_not_met_rows: List[Dict[str, Any]],
        overall_condition_logic: str
    ) -> bool:
        """Determine overall condition status based on configurable logic.
        
        Args:
            condition_met_rows: Rows where condition was met
            condition_not_met_rows: Rows where condition was not met
            overall_condition_logic: Logic for determining overall status
            
        Returns:
            Boolean indicating if overall condition is met
        """
        total_rows = len(condition_met_rows) + len(condition_not_met_rows)
        condition_met_count = len(condition_met_rows)
        
        if total_rows == 0:
            return False
        
        if overall_condition_logic == "any_met":
            # Condition met if ANY row meets the condition
            return condition_met_count > 0
        elif overall_condition_logic == "all_met":
            # Condition met if ALL rows meet the condition
            return condition_met_count == total_rows
        elif overall_condition_logic == "majority_met":
            # Condition met if majority of rows meet the condition
            return condition_met_count > (total_rows / 2)
        elif overall_condition_logic == "percentage_met":
            # Condition met if specified percentage of rows meet the condition
            # For now, default to 50% threshold, but this could be made configurable
            return (condition_met_count / total_rows) >= 0.5
        else:
            # Default to "any_met" for unknown logic
            return condition_met_count > 0
    
    def _process_threshold_value(
        self,
        threshold_value: float,
        threshold_type: str,
        data: List[Dict[str, Any]]
    ) -> float:
        """Process threshold value based on threshold type.
        
        Args:
            threshold_value: Original threshold value
            threshold_type: Type of threshold interpretation
            data: Data rows for context (used for percentile calculations)
            
        Returns:
            Processed threshold value for comparison
        """
        if threshold_type == "default":
            return threshold_value
        elif threshold_type == "percentage":
            # Convert percentage to decimal (divide by 100)
            return threshold_value / 100.0
        elif threshold_type == "ratio":
            # Keep as is (0-1 range)
            return threshold_value
        elif threshold_type == "percentile":
            # Calculate percentile from data
            return self._calculate_percentile(threshold_value, data)
        elif threshold_type == "multiplier":
            # Use as multiplier factor
            return threshold_value
        elif threshold_type == "absolute":
            # Use absolute value
            return abs(threshold_value)
        else:
            # Default to original value for unknown types
            return threshold_value
    
    def _calculate_percentile(
        self,
        percentile: float,
        data: List[Dict[str, Any]]
    ) -> float:
        """Calculate percentile value from data.
        
        Args:
            percentile: Percentile value (0-100)
            data: Data rows to calculate percentile from
            
        Returns:
            Calculated percentile value
        """
        if not data:
            return 0.0
        
        # Extract numeric values from data
        values = []
        for row in data:
            for key, value in row.items():
                if value is not None:
                    try:
                        values.append(float(value))
                    except (ValueError, TypeError):
                        continue
        
        if not values:
            return 0.0
        
        # Sort values
        values.sort()
        
        # Calculate percentile
        n = len(values)
        if n == 1:
            return values[0]
        
        # Calculate index
        index = (percentile / 100.0) * (n - 1)
        
        # Interpolate between values
        lower_index = int(index)
        upper_index = min(lower_index + 1, n - 1)
        
        if lower_index == upper_index:
            return values[lower_index]
        
        # Linear interpolation
        weight = index - lower_index
        return values[lower_index] * (1 - weight) + values[upper_index] * weight
    
    def _validate_data_type_compatibility(
        self,
        condition_type: str,
        current_value: Any,
        operator: str,
        threshold_value: Any,
        row_data: Dict[str, Any]
    ) -> None:
        """Validate that data types are compatible with the condition type.
        
        Args:
            condition_type: Type of condition being evaluated
            current_value: Current value to validate
            operator: Operator being used
            threshold_value: Threshold value to validate
            row_data: Full row data for context
            
        Raises:
            ValueError: If data types are incompatible with condition type
        """
        if condition_type == "threshold_value":
            self._validate_threshold_data_types(current_value, threshold_value, operator)
        elif condition_type == "intelligent_arima":
            self._validate_arima_data_types(current_value, threshold_value, operator, row_data)
        elif condition_type == "string_match":
            self._validate_string_data_types(current_value, threshold_value, operator)
        elif condition_type == "threshold_change":
            self._validate_change_data_types(current_value, threshold_value, operator, row_data)
        elif condition_type == "threshold_percent_change":
            self._validate_percent_change_data_types(current_value, threshold_value, operator, row_data)
        else:
            # Default to threshold validation for unknown types
            self._validate_threshold_data_types(current_value, threshold_value, operator)
    
    def _validate_threshold_data_types(
        self,
        current_value: Any,
        threshold_value: Any,
        operator: str
    ) -> None:
        """Validate data types for threshold conditions.
        
        Args:
            current_value: Current value (must be numeric)
            threshold_value: Threshold value (must be numeric)
            operator: Operator being used
            
        Raises:
            ValueError: If values are not numeric
        """
        # Validate current value is numeric
        if not isinstance(current_value, (int, float)):
            raise ValueError(f"Threshold condition requires numeric current_value, got {type(current_value).__name__}: {current_value}")
        
        # Validate threshold value is numeric
        if not isinstance(threshold_value, (int, float)):
            raise ValueError(f"Threshold condition requires numeric threshold_value, got {type(threshold_value).__name__}: {threshold_value}")
        
        # Validate operator is supported for numeric comparison
        numeric_operators = {">", "<", ">=", "<=", "=", "!="}
        if operator not in numeric_operators:
            raise ValueError(f"Threshold condition operator '{operator}' not supported. Supported operators: {numeric_operators}")
    
    def _validate_arima_data_types(
        self,
        current_value: Any,
        threshold_value: Any,
        operator: str,
        row_data: Dict[str, Any]
    ) -> None:
        """Validate data types for ARIMA conditions.
        
        Args:
            current_value: Current value (must be numeric)
            threshold_value: Threshold value (must be numeric)
            operator: Operator being used
            row_data: Row data (should contain time series data)
            
        Raises:
            ValueError: If data types are incompatible
        """
        # Validate current value is numeric
        if not isinstance(current_value, (int, float)):
            raise ValueError(f"ARIMA condition requires numeric current_value, got {type(current_value).__name__}: {current_value}")
        
        # Validate threshold value is numeric
        if not isinstance(threshold_value, (int, float)):
            raise ValueError(f"ARIMA condition requires numeric threshold_value, got {type(threshold_value).__name__}: {threshold_value}")
        
        # Validate row data contains time series information
        required_fields = ["timestamp", "value"]  # Adjust based on your time series structure
        missing_fields = [field for field in required_fields if field not in row_data]
        if missing_fields:
            raise ValueError(f"ARIMA condition requires time series data. Missing fields: {missing_fields}")
        
        # Validate operator is supported for ARIMA
        arima_operators = {"anomaly_detected", "trend_break", "seasonal_anomaly", "forecast_deviation"}
        if operator not in arima_operators:
            raise ValueError(f"ARIMA condition operator '{operator}' not supported. Supported operators: {arima_operators}")
    
    def _validate_string_data_types(
        self,
        current_value: Any,
        threshold_value: Any,
        operator: str
    ) -> None:
        """Validate data types for string conditions.
        
        Args:
            current_value: Current value (must be string)
            threshold_value: Threshold value (must be string)
            operator: Operator being used
            
        Raises:
            ValueError: If values are not strings
        """
        # Validate current value is string
        if not isinstance(current_value, str):
            raise ValueError(f"String condition requires string current_value, got {type(current_value).__name__}: {current_value}")
        
        # Validate threshold value is string
        if not isinstance(threshold_value, str):
            raise ValueError(f"String condition requires string threshold_value, got {type(threshold_value).__name__}: {threshold_value}")
        
        # Validate operator is supported for string comparison
        string_operators = {"contains", "starts_with", "ends_with", "equals", "regex", "not_contains"}
        if operator not in string_operators:
            raise ValueError(f"String condition operator '{operator}' not supported. Supported operators: {string_operators}")
    
    def _validate_change_data_types(
        self,
        current_value: Any,
        threshold_value: Any,
        operator: str,
        row_data: Dict[str, Any]
    ) -> None:
        """Validate data types for change conditions.
        
        Args:
            current_value: Current value (must be numeric)
            threshold_value: Threshold value (must be numeric)
            operator: Operator being used
            row_data: Row data (should contain previous_value)
            
        Raises:
            ValueError: If data types are incompatible
        """
        # Validate current value is numeric
        if not isinstance(current_value, (int, float)):
            raise ValueError(f"Change condition requires numeric current_value, got {type(current_value).__name__}: {current_value}")
        
        # Validate threshold value is numeric
        if not isinstance(threshold_value, (int, float)):
            raise ValueError(f"Change condition requires numeric threshold_value, got {type(threshold_value).__name__}: {threshold_value}")
        
        # Validate previous value exists and is numeric
        previous_value = row_data.get("previous_value")
        if previous_value is None:
            raise ValueError("Change condition requires 'previous_value' in row data")
        
        try:
            float(previous_value)
        except (ValueError, TypeError):
            raise ValueError(f"Change condition requires numeric previous_value, got {type(previous_value).__name__}: {previous_value}")
        
        # Validate operator is supported for change comparison
        change_operators = {"increased_by", "decreased_by", "changed_by"}
        if operator not in change_operators:
            raise ValueError(f"Change condition operator '{operator}' not supported. Supported operators: {change_operators}")
    
    def _validate_percent_change_data_types(
        self,
        current_value: Any,
        threshold_value: Any,
        operator: str,
        row_data: Dict[str, Any]
    ) -> None:
        """Validate data types for percent change conditions.
        
        Args:
            current_value: Current value (must be numeric)
            threshold_value: Threshold value (must be numeric)
            operator: Operator being used
            row_data: Row data (should contain previous_value)
            
        Raises:
            ValueError: If data types are incompatible
        """
        # Validate current value is numeric
        if not isinstance(current_value, (int, float)):
            raise ValueError(f"Percent change condition requires numeric current_value, got {type(current_value).__name__}: {current_value}")
        
        # Validate threshold value is numeric
        if not isinstance(threshold_value, (int, float)):
            raise ValueError(f"Percent change condition requires numeric threshold_value, got {type(threshold_value).__name__}: {threshold_value}")
        
        # Validate previous value exists and is numeric
        previous_value = row_data.get("previous_value")
        if previous_value is None:
            raise ValueError("Percent change condition requires 'previous_value' in row data")
        
        try:
            prev_val = float(previous_value)
            if prev_val == 0:
                raise ValueError("Percent change condition requires non-zero previous_value to avoid division by zero")
        except (ValueError, TypeError):
            raise ValueError(f"Percent change condition requires numeric previous_value, got {type(previous_value).__name__}: {previous_value}")
        
        # Validate operator is supported for percent change comparison
        percent_change_operators = {"increased_by_percent", "decreased_by_percent", "changed_by_percent"}
        if operator not in percent_change_operators:
            raise ValueError(f"Percent change condition operator '{operator}' not supported. Supported operators: {percent_change_operators}")


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
            
            # Convert AlertSet to AlertCombination (using alert_service AlertCombination)
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
            metadata=alert_response.metadata
        )
    
    def _parse_notification_groups_from_alert_request(self, alert_request: str) -> List[Dict[str, Any]]:
        """Parse alert request text to extract multiple notification groups
        
        Args:
            alert_request: The alert request text containing notification instructions
            
        Returns:
            List of notification group dictionaries
        """
        notification_groups = []
        
        # Split the alert request into lines and process each notification instruction
        lines = alert_request.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or not any(keyword in line.lower() for keyword in ['notify', 'alert', 'send']):
                continue
                
            # Extract notification type and target
            notification_group = {
                "type": "email",  # default
                "targets": [],
                "condition": "",
                "message": ""
            }
            
            # Check for Slack notifications
            if 'slack' in line.lower():
                notification_group["type"] = "slack"
                # Extract team name if available
                if 'learn team' in line.lower():
                    notification_group["targets"] = ["learn_team"]
                elif 'talent team' in line.lower():
                    notification_group["targets"] = ["talent_team"]
                else:
                    notification_group["targets"] = ["default_slack_channel"]
            
            # Check for Teams notifications
            elif 'teams' in line.lower():
                notification_group["type"] = "teams"
                if 'learn team' in line.lower():
                    notification_group["targets"] = ["learn_team"]
                elif 'talent team' in line.lower():
                    notification_group["targets"] = ["talent_team"]
                else:
                    notification_group["targets"] = ["default_teams_channel"]
            
            # Check for email notifications (CSOD Learn Team should be email)
            elif 'csod learn team' in line.lower() or 'csod' in line.lower():
                notification_group["type"] = "email"
                notification_group["targets"] = ["csod_learn_team@company.com"]
            elif any(keyword in line.lower() for keyword in ['email', '@', 'team']):
                notification_group["type"] = "email"
                # Extract email addresses or team names
                if 'learn team' in line.lower():
                    notification_group["targets"] = ["learn_team@company.com"]
                elif 'talent team' in line.lower():
                    notification_group["targets"] = ["talent_team@company.com"]
                else:
                    notification_group["targets"] = ["default@company.com"]
            
            # Extract condition from the line
            if 'greater than' in line.lower() or '>' in line:
                if '40%' in line:
                    notification_group["condition"] = "percentage > 40%"
                elif '20%' in line:
                    notification_group["condition"] = "percentage <= 20%"
            elif 'drops to' in line.lower() or 'drops' in line.lower():
                if '20%' in line:
                    notification_group["condition"] = "percentage <= 20%"
            elif 'exceed' in line.lower():
                if '90 days' in line:
                    notification_group["condition"] = "completion_days > 90"
            
            # Set default message
            notification_group["message"] = f"Alert condition met: {notification_group['condition']}"
            
            if notification_group["targets"]:
                notification_groups.append(notification_group)
        
        return notification_groups

    def convert_service_response_to_compatibility(
        self, 
        service_response: AlertResponse
    ) -> AlertResponseCompatibility:
        """Convert internal AlertResponse back to AlertResponseCompatibility format"""
        
        # Extract information from the service response
        result = service_response.result
        metadata = service_response.metadata
        
        # Handle clarification-required responses coming from the alert orchestrator pipeline
        if isinstance(result, dict) and result.get("status") == "clarification_required":
            clarification = result.get("clarification") or {}
            questions = clarification.get("questions") or clarification.get("clarification_questions") or []
            if isinstance(questions, str):
                questions = [questions]

            summary = "Clarification required to create this alert."
            if questions:
                summary = f"{summary} Questions: " + " | ".join(str(q) for q in questions)

            return AlertResponseCompatibility(
                type="clarification_required",
                question=str(questions[0]) if questions else "Clarification required",
                alertname="Clarification Required",
                summary=summary,
                reasoning="The request appears ambiguous; please answer the clarification questions so the alert can be created accurately.",
                conditions=[],
                notificationgroup="default",
                project_id=result.get("project_id") or metadata.get("project_id"),
                session_id=metadata.get("session_id"),
                service_created=False,
                service_metadata={
                    "status": "clarification_required",
                    "clarification": clarification,
                    "query_index": result.get("query_index"),
                },
                created_at=datetime.now(),
            )
        
        # Handle alert orchestrator pipeline response format
        if "post_process" in result:
            post_process = result["post_process"]
            alert_results = post_process.get("alert_results", [])
            orchestration_metadata = post_process.get("orchestration_metadata", {})
            combined_feed_configs = post_process.get("combined_feed_configurations", {}) or {}
            combined_sql_analysis = post_process.get("combined_sql_analysis")
            
            # Extract alert information from the first alert result
            alert_name = "Generated Alert"
            summary = "Alert generated from service"
            reasoning = "Alert created using alert service"
            conditions = []
            notification_group = "default"
            
            # If no alerts were generated, return an informative response instead of a dummy default condition.
            if not alert_results:
                combined_summary = post_process.get("combined_feed_configurations", {}).get("summary")
                summary_text = "No alerts generated"
                if isinstance(combined_summary, str):
                    summary_text = combined_summary
                elif isinstance(combined_summary, dict) and combined_summary.get("summary"):
                    summary_text = str(combined_summary.get("summary"))

                project_id = orchestration_metadata.get("project_id") or metadata.get("project_id")
                session_id = metadata.get("session_id")

                return AlertResponseCompatibility(
                    type="no_alerts_generated",
                    question="No alerts generated from alert service",
                    alertname="No Alerts Generated",
                    summary=summary_text,
                    reasoning="All generated candidates were filtered out (e.g., low confidence) or no valid alert configuration could be produced.",
                    conditions=[],
                    notificationgroup="default",
                    project_id=project_id,
                    session_id=session_id,
                    feed_id=result.get("feed_id"),
                    feed_name=result.get("feed_name"),
                    global_configuration=result.get("global_configuration", {}),
                    notification_settings=result.get("notification_settings"),
                    schedule_settings=result.get("schedule_settings"),
                    priority=result.get("priority", AlertPriority.MEDIUM),
                    tags=result.get("tags", []),
                    # Keep response compact: don't embed raw orchestrator payload.
                    metadata={
                        "combined_feed_configurations": {
                            "summary": combined_feed_configs.get("summary"),
                            "feeds_count": len(combined_feed_configs.get("feeds", []) or []),
                        },
                        "combined_sql_analysis": combined_sql_analysis,
                        "orchestration_metadata": orchestration_metadata,
                    },
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    service_created=False,
                    service_metadata={
                        "pipeline_name": metadata.get("pipeline_name"),
                        "pipeline_version": metadata.get("pipeline_version"),
                        "execution_timestamp": metadata.get("execution_timestamp"),
                        # orchestration details moved to `metadata` to avoid duplication
                    },
                )

            # First try to get from alert_results
            if alert_results:
                # Build compatibility `conditions[]` from *all* generated alert results, so multi-clause requests
                # (split into multiple alert_results) surface multiple conditions.
                conditions = []
                summaries: List[str] = []

                valid_schedules = ["daily", "weekly", "monthly", "quarterly", "yearly", "custom", "never"]
                timecolumn_map = {
                    "Daily": "rolling",
                    "Weekly": "weekly",
                    "Monthly": "monthly",
                    "Quarterly": "quarterly",
                    "Yearly": "yearly",
                }
                operator_map = {
                    ">": "greaterthan",
                    ">=": "greaterthan",
                    "<": "lessthan",
                    "<=": "lessthan",
                    "=": "equals",
                    "!=": "notequals",
                }
                operator_alias_map = {
                    "ThresholdOperator.GREATER_THAN": ">",
                    "ThresholdOperator.GREATER_EQUAL": ">=",
                    "ThresholdOperator.LESS_THAN": "<",
                    "ThresholdOperator.LESS_EQUAL": "<=",
                    "ThresholdOperator.EQUALS": "=",
                    "ThresholdOperator.NOT_EQUALS": "!=",
                }

                for ar_idx, alert_dict in enumerate(alert_results):
                    feed_config = alert_dict.get("feed_configuration", {}) or {}
                    metric = feed_config.get("metric", {}) or {}
                    notification = feed_config.get("notification", {}) or {}

                    metric_name = metric.get("measure", "default_metric")
                    alert_title = notification.get("metric_name", "Generated Alert")

                    schedule_type = notification.get("schedule_type", "daily")
                    schedule = schedule_type if schedule_type in valid_schedules else "daily"

                    resolution = metric.get("resolution", "Daily")
                    timecolumn = timecolumn_map.get(resolution, "rolling")

                    conditions_list = feed_config.get("conditions", [])
                    if not conditions_list and feed_config.get("condition"):
                        conditions_list = [feed_config.get("condition")]

                    if not isinstance(conditions_list, list):
                        conditions_list = []

                    for cond_idx, cond in enumerate(conditions_list):
                        if not isinstance(cond, dict):
                            continue
                        operator = cond.get("operator", ">")
                        if not isinstance(operator, str) and hasattr(operator, "value"):
                            operator = operator.value
                        if isinstance(operator, str) and operator in operator_alias_map:
                            operator = operator_alias_map[operator]
                        cond_value = cond.get("value", 0)
                        condition_type = operator_map.get(operator, "greaterthan")
                        
                        condition_name = alert_title
                        if len(alert_results) > 1:
                            condition_name = f"{alert_title} ({metric_name})"
                        if len(conditions_list) > 1:
                            condition_name = f"{condition_name} - Condition {cond_idx + 1}"
                        
                        conditions.append(
                            Condition(
                                conditionType=condition_type,
                                metricselected=metric_name,
                                schedule=schedule,
                                timecolumn=timecolumn,
                                value=str(cond_value) if cond_value is not None else None,
                                alert_id=f"generated_alert_{ar_idx}_{cond_idx}",
                                alert_name=condition_name,
                                priority=AlertPriority.MEDIUM,
                                created_at=datetime.now(),
                            )
                        )

                        summaries.append(f"{metric_name} {operator} {cond_value}")

                if len(alert_results) == 1:
                    alert_name = alert_results[0].get("feed_configuration", {}).get("notification", {}).get("metric_name", "Generated Alert")
                else:
                    alert_name = f"{len(alert_results)} Alerts Generated"

                summary = "Alerts: " + "; ".join(summaries[:6]) if summaries else "Alerts generated from service"
                reasoning = "Alerts generated from service (one per clause when split)."

                # Build a replayable request list (matches /alerts/validate-condition new format)
                generated_alert_requests: List[Dict[str, Any]] = []
                for alert_dict in alert_results:
                    input_ctx = alert_dict.get("input") or {}
                    sql = input_ctx.get("sql")
                    nlq = input_ctx.get("natural_language_query")
                    proposed_alert = alert_dict.get("feed_configuration")
                    if sql and proposed_alert:
                        generated_alert_requests.append(
                            {
                                "sql": sql,
                                "proposed_alert": proposed_alert,
                                "project_id": orchestration_metadata.get("project_id") or metadata.get("project_id"),
                                "business_context": nlq,
                            }
                        )
            else:
                # If no alert_results, try to extract from the pipeline result directly
                # This handles the case where the alert agent returns the configuration directly
                if hasattr(service_response, 'result') and 'feed_configuration' in str(service_response.result):
                    # The result contains a LexyFeedConfiguration object
                    # We need to extract the condition information from it
                    try:
                        # Parse the string representation to extract the condition value
                        result_str = str(service_response.result)
                        
                        # Extract condition value using regex
                        import re
                        value_match = re.search(r'value=(\d+)', result_str)
                        condition_type_match = re.search(r'condition_type=<AlertConditionType\.(\w+):', result_str)
                        operator_match = re.search(r'operator=<ThresholdOperator\.(\w+):', result_str)
                        metric_match = re.search(r'measure=\'([^\']+)\'', result_str)
                        schedule_type_match = re.search(r'schedule_type=<ScheduleType\.(\w+):', result_str)
                        resolution_match = re.search(r'resolution=\'([^\']+)\'', result_str)
                        
                        condition_value = value_match.group(1) if value_match else "0"
                        condition_type = condition_type_match.group(1).lower() if condition_type_match else "threshold_value"
                        operator = operator_match.group(1) if operator_match else ">"
                        metric_name = metric_match.group(1) if metric_match else "default_metric"
                        schedule_type = schedule_type_match.group(1).lower() if schedule_type_match else "scheduled"
                        resolution = resolution_match.group(1) if resolution_match else "Daily"
                        
                        # Map operator to condition type format
                        operator_map = {
                            ">": "greaterthan",
                            ">=": "greaterthan",  # Greater than or equal maps to greaterthan
                            "<": "lessthan",
                            "<=": "lessthan",     # Less than or equal maps to lessthan
                            "=": "equals",
                            "!=": "notequals"
                        }
                        mapped_condition_type = operator_map.get(operator, "greaterthan")
                        
                        # Use schedule_type directly from LLM response
                        # The LLM now generates the correct schedule format directly
                        valid_schedules = ["daily", "weekly", "monthly", "quarterly", "yearly", "custom", "never"]
                        schedule = schedule_type if schedule_type in valid_schedules else "daily"
                        
                        # Map resolution to timecolumn format
                        timecolumn_map = {
                            "Daily": "rolling",
                            "Weekly": "weekly",
                            "Monthly": "monthly",
                            "Quarterly": "quarterly",
                            "Yearly": "yearly"
                        }
                        timecolumn = timecolumn_map.get(resolution, "rolling")
                        
                        conditions = [Condition(
                            conditionType=mapped_condition_type,
                            metricselected=metric_name,
                            schedule=schedule,
                            timecolumn=timecolumn,
                            value=condition_value,
                            alert_id="generated_alert",
                            alert_name="Generated Alert",
                            priority=AlertPriority.MEDIUM,
                            created_at=datetime.now()
                        )]
                        
                        alert_name = "Generated Alert"
                        summary = f"Alert for {metric_name} with threshold {condition_value}"
                        reasoning = "Alert generated from service"
                        
                    except Exception as e:
                        # Fallback to default condition
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
            
            # Extract service-managed fields
            project_id = orchestration_metadata.get("project_id")
            session_id = metadata.get("session_id")
            
            # Extract notification groups from metadata
            notification_groups = metadata.get("notification_groups", [])
            
            service_metadata = {
                "pipeline_name": metadata.get("pipeline_name"),
                "pipeline_version": metadata.get("pipeline_version"),
                "execution_timestamp": metadata.get("execution_timestamp"),
                # keep compact; orchestration details are returned in `metadata`
            }
            
        else:
            # Fallback to original format for backward compatibility
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
            
            # Extract notification groups from metadata
            notification_groups = metadata.get("notification_groups", [])
            
            service_metadata = {
                "pipeline_name": metadata.get("pipeline_name"),
                "pipeline_version": metadata.get("pipeline_version"),
                "execution_timestamp": metadata.get("execution_timestamp"),
                "notification_groups": notification_groups
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
        
        # Create a descriptive notification group name based on the parsed groups
        if notification_groups:
            group_types = [group.get("type", "unknown") for group in notification_groups]
            notification_group_name = f"multi_channel_{'_'.join(set(group_types))}"
        else:
            notification_group_name = notification_group
            
        return AlertResponseCompatibility(
            type="finished",
            question="Generated from alert service",
            alertname=alert_name,
            summary=summary,
            reasoning=reasoning,
            conditions=conditions,
            notificationgroup=notification_group_name,
            generated_alert_requests=generated_alert_requests if 'generated_alert_requests' in locals() and generated_alert_requests else None,
            # Service-managed fields
            project_id=project_id,
            session_id=session_id,
            feed_id=result.get("feed_id"),
            feed_name=result.get("feed_name"),
            global_configuration=result.get("global_configuration", {}),
            notification_settings=result.get("notification_settings"),
            schedule_settings=result.get("schedule_settings"),
            priority=result.get("priority", AlertPriority.MEDIUM),
            tags=result.get("tags", []),
            # Keep response compact: only expose high-signal artifacts.
            metadata={
                "combined_feed_configurations": {
                    "summary": combined_feed_configs.get("summary"),
                    "feeds": combined_feed_configs.get("feeds", []),
                },
                "combined_sql_analysis": combined_sql_analysis,
                "orchestration_metadata": orchestration_metadata,
            },
            created_at=datetime.now(),
            updated_at=datetime.now(),
            service_created=service_response.success,
            service_metadata=service_metadata,
            notification_groups=notification_groups if notification_groups else None
        )
    
    async def process_alert_create(
        self, 
        alert_create: AlertCreate,
        project_id: Optional[str] = None
    ) -> AlertResponseCompatibility:
        """Process an AlertCreate request and return a compatibility response
        
        This method handles the full flow from AlertCreate to service response
        and back to compatibility format using the alert orchestrator pipeline.
        """
        # Use provided project_id or fall back to default
        project_id = project_id or alert_create.project_id or self.default_project_id
        
        try:
            # Parse the alert request to extract multiple notification groups
            # The alert_request should contain the natural language instructions
            alert_request_text = alert_create.input
            notification_groups = self._parse_notification_groups_from_alert_request(alert_request_text)
            
            # Prefer structured values when provided (e.g., from `/alerts/service/create-single`)
            ctx = alert_create.additional_context or {}
            sql_query = (
                ctx.get("sql")
                or ctx.get("sql_query")
                or ctx.get("query_sql")
            )
            natural_language_query = (
                ctx.get("natural_language_query")
                or ctx.get("nlq")
                or ctx.get("query")
            )
            alert_request = (
                ctx.get("alert_request")
                or ctx.get("alert")
                or ctx.get("alert_text")
            )

            # Fallback: if not provided, fall back to the raw input blob
            sql_query = sql_query or alert_create.input
            natural_language_query = natural_language_query or alert_create.input
            alert_request = alert_request or alert_create.input

            sql_queries = [sql_query]
            
            # Create an AlertRequest for the alert service
            alert_request_obj = AlertRequest(
                request_type=AlertRequestType.SINGLE_ALERT,
                sql_queries=sql_queries,
                natural_language_query=natural_language_query,
                alert_request=alert_request,
                project_id=project_id,
                data_description=alert_create.data_description,
                session_id=alert_create.session_id,
                additional_context=alert_create.additional_context,
                configuration=alert_create.configuration
            )
            
            # Process through the alert service using the orchestrator pipeline
            service_response = await self.alert_service.process_request(alert_request_obj)
            
            # Add notification groups to the service metadata
            if hasattr(service_response, 'metadata'):
                service_response.metadata['notification_groups'] = notification_groups
            else:
                service_response.metadata = {'notification_groups': notification_groups}
            
            # Convert the service response to compatibility format
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
