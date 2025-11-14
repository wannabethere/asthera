import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm, get_doc_store_provider
from app.agents.nodes.writers.dashboard_agent import (
    ConditionalFormattingAgent,
    ConditionalFormattingRetriever
)
from app.agents.nodes.writers.dashboard_models import (
    DashboardConfiguration,
    ActionType,
    FilterType
)
from app.agents.nodes.sql.sql_pipeline import SQLPipeline, SQLResult
from app.agents.pipelines.sql_execution import SQLExecutionPipeline

logger = logging.getLogger("lexy-ai-service")


class ConditionalFormattingPipeline(AgentPipeline):
    """
    Dedicated standalone pipeline for processing conditional formatting requests.
    
    This pipeline is designed to be used independently from dashboard flows,
    allowing both to be enhanced separately without coupling.
    
    This pipeline:
    1. Uses ConditionalFormattingAgent to create an intent plan
    2. Processes SQL-related filters using SQLPipeline for expansion
    3. Applies chart-related filters and formatting
    4. Handles time filters intelligently using LLM agents
    
    Note: This pipeline is separate from EnhancedDashboardPipeline to allow
    independent enhancement and evolution of conditional formatting features.
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        document_store_provider: Any = None,
        sql_pipeline: Optional[SQLPipeline] = None,
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
            "max_retry_attempts": 3,
            "timeout_seconds": 60,
            "enable_caching": True,
            "cache_ttl_seconds": 3600,
            "enable_validation": True,
            "enable_optimization": True,
            "enable_sql_expansion": True,
            "enable_chart_adjustments": True,
            "enable_time_filter_processing": True
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize conditional formatting agent
        if not document_store_provider:
            document_store_provider = get_doc_store_provider()
        
        # Create the retriever first
        retriever = ConditionalFormattingRetriever(retrieval_helper)
        
        self._conditional_formatting_agent = ConditionalFormattingAgent(
            llm=llm,
            retriever=retriever,
            document_store_provider=document_store_provider
        )
        
        # Initialize SQL pipeline if not provided
        if sql_pipeline:
            self._sql_pipeline = sql_pipeline
        else:
            from app.core.provider import DocumentStoreProvider
            from app.agents.nodes.sql.sql_pipeline import SQLPipelineFactory
            doc_store = document_store_provider if isinstance(document_store_provider, DocumentStoreProvider) else None
            self._sql_pipeline = SQLPipelineFactory.create_pipeline(
                engine=engine,
                doc_store=doc_store,
                use_rag=True
            )
        
        # Initialize SQL execution pipeline if not provided
        if sql_execution_pipeline:
            self._sql_execution_pipeline = sql_execution_pipeline
        else:
            self._sql_execution_pipeline = SQLExecutionPipeline(
                name="sql_execution_for_conditional_formatting",
                version="1.0.0",
                description="SQL execution pipeline for conditional formatting",
                llm=llm,
                retrieval_helper=retrieval_helper,
                engine=engine,
                dry_run=False
            )
            # Set initialized flag for SQL execution pipeline
            self._sql_execution_pipeline._initialized = True
        
        # Initialize chart adjustment pipeline
        from app.agents.pipelines.sql_pipelines import ChartAdjustmentPipeline
        self._chart_adjustment_pipeline = ChartAdjustmentPipeline(
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine,
            use_enhanced_agent=True,
            chart_config={"type": "enhanced_vega_lite"}  # Default to enhanced Vega-Lite
        )
        
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
        
        logger.info(f"Conditional Formatting Pipeline Status - {status}: {details}")

    async def run(
        self,
        natural_language_query: str,
        dashboard_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process conditional formatting request for a dashboard
        
        Args:
            natural_language_query: Natural language query for conditional formatting
            dashboard_context: Context about dashboard charts and columns
            project_id: Project identifier
            additional_context: Additional context for formatting
            time_filters: Time-based filters (will be processed by agent if provided)
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing conditional formatting configuration and metadata
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not natural_language_query or not natural_language_query.strip():
            raise ValueError("Natural language query cannot be empty")
        
        if not dashboard_context:
            raise ValueError("Dashboard context cannot be empty")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Create intent plan using ConditionalFormattingAgent
            self._send_status_update(
                status_callback,
                "intent_planning_started",
                {
                    "query": natural_language_query,
                    "project_id": project_id
                }
            )
            
            # Process the conditional formatting request using the agent
            agent_result = await self._conditional_formatting_agent.process_conditional_formatting_request(
                query=natural_language_query,
                dashboard_context=dashboard_context,
                project_id=project_id,
                additional_context=additional_context,
                time_filters=time_filters
            )
            
            if not agent_result.get("success", False):
                error_msg = agent_result.get("error", "Unknown error in conditional formatting agent")
                self._send_status_update(
                    status_callback,
                    "intent_planning_failed",
                    {
                        "error": error_msg,
                        "project_id": project_id
                    }
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "chart_configurations": {},
                    "metadata": {
                        "project_id": project_id,
                        "query": natural_language_query,
                        "error": error_msg
                    }
                }
            
            # Extract configuration from agent result
            dashboard_config: DashboardConfiguration = agent_result.get("configuration")
            chart_configurations = agent_result.get("chart_configurations", {})
            
            self._send_status_update(
                status_callback,
                "intent_planning_completed",
                {
                    "total_filters": len(dashboard_config.filters) if dashboard_config else 0,
                    "total_conditional_formats": len(dashboard_config.conditional_formats) if dashboard_config else 0,
                    "has_time_filters": bool(dashboard_config.time_filters) if dashboard_config else False,
                    "project_id": project_id
                }
            )
            
            # Step 2: Process time filters early (before SQL expansion) so they can be included in SQL expansion requests
            processed_time_filters = None
            if (self._configuration.get("enable_time_filter_processing", True) and 
                dashboard_config and 
                dashboard_config.time_filters):
                
                self._send_status_update(
                    status_callback,
                    "time_filter_processing_started",
                    {
                        "project_id": project_id,
                        "time_filters": dashboard_config.time_filters
                    }
                )
                
                processed_time_filters = await self._process_time_filters(
                    time_filters=dashboard_config.time_filters,
                    dashboard_context=dashboard_context,
                    project_id=project_id,
                    status_callback=status_callback,
                    **kwargs
                )
                
                self._send_status_update(
                    status_callback,
                    "time_filter_processing_completed",
                    {
                        "project_id": project_id
                    }
                )
            
            # Step 3: Process SQL-related filters and expansions (now with time filters available)
            sql_expansions = {}
            if self._configuration.get("enable_sql_expansion", True) and dashboard_config:
                self._send_status_update(
                    status_callback,
                    "sql_expansion_started",
                    {
                        "project_id": project_id,
                        "total_filters": len(dashboard_config.filters),
                        "has_time_filters": bool(processed_time_filters)
                    }
                )
                
                sql_expansions = await self._process_sql_expansions(
                    dashboard_config=dashboard_config,
                    dashboard_context=dashboard_context,
                    project_id=project_id,
                    processed_time_filters=processed_time_filters,  # Pass processed time filters
                    status_callback=status_callback,
                    **kwargs
                )
                
                self._send_status_update(
                    status_callback,
                    "sql_expansion_completed",
                    {
                        "project_id": project_id,
                        "expansions_count": len(sql_expansions)
                    }
                )
            
            # Step 4: Execute expanded SQL queries using SQLExecutionPipeline
            executed_sql_results = {}
            if self._configuration.get("enable_sql_expansion", True) and sql_expansions:
                self._send_status_update(
                    status_callback,
                    "sql_execution_started",
                    {
                        "project_id": project_id,
                        "total_expansions": len(sql_expansions)
                    }
                )
                
                executed_sql_results = await self._execute_expanded_sql_queries(
                    sql_expansions=sql_expansions,
                    dashboard_context=dashboard_context,
                    project_id=project_id,
                    status_callback=status_callback,
                    **kwargs
                )
                
                self._send_status_update(
                    status_callback,
                    "sql_execution_completed",
                    {
                        "project_id": project_id,
                        "executed_count": len(executed_sql_results)
                    }
                )
            
            # Step 5: Apply chart adjustments using ChartAdjustmentPipeline
            adjusted_chart_configurations = chart_configurations.copy()  # Initialize with original configurations
            if self._configuration.get("enable_chart_adjustments", True) and dashboard_config:
                self._send_status_update(
                    status_callback,
                    "chart_adjustment_started",
                    {
                        "project_id": project_id,
                        "total_conditional_formats": len(dashboard_config.conditional_formats) if dashboard_config else 0
                    }
                )
                
                adjusted_chart_configurations = await self._apply_chart_adjustments(
                    chart_configurations=chart_configurations,
                    dashboard_config=dashboard_config,
                    dashboard_context=dashboard_context,
                    executed_sql_results=executed_sql_results,
                    project_id=project_id,
                    status_callback=status_callback,
                    **kwargs
                )
                
                self._send_status_update(
                    status_callback,
                    "chart_adjustment_completed",
                    {
                        "project_id": project_id,
                        "adjusted_count": len(adjusted_chart_configurations)
                    }
                )
            
            # Step 6: Update chart configurations with SQL expansions, time filters, and chart adjustments
            enhanced_chart_configurations = self._enhance_chart_configurations(
                chart_configurations=adjusted_chart_configurations if adjusted_chart_configurations else chart_configurations,
                sql_expansions=sql_expansions,
                time_filters=processed_time_filters,
                dashboard_config=dashboard_config
            )
            
            # Calculate execution time
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # Update metrics
            self._metrics.update({
                "last_execution": {
                    "execution_time": execution_time,
                    "total_filters": len(dashboard_config.filters) if dashboard_config else 0,
                    "total_conditional_formats": len(dashboard_config.conditional_formats) if dashboard_config else 0,
                    "sql_expansions_count": len(sql_expansions),
                    "has_time_filters": bool(processed_time_filters)
                },
                "total_executions": self._metrics.get("total_executions", 0) + 1
            })
            
            # Prepare final result
            result = {
                "success": True,
                "configuration": dashboard_config,
                "chart_configurations": enhanced_chart_configurations,
                "sql_expansions": sql_expansions,
                "executed_sql_results": executed_sql_results,  # Include executed SQL results
                "time_filters": processed_time_filters,
                "metadata": {
                    "project_id": project_id,
                    "query": natural_language_query,
                    "dashboard_context": dashboard_context,
                    "additional_context": additional_context,
                    "execution_time_seconds": execution_time,
                    "generated_at": end_time.isoformat(),
                    "sql_expansions_count": len(sql_expansions),
                    "executed_sql_count": len(executed_sql_results),
                    "chart_adjustments_applied": len(adjusted_chart_configurations) > 0
                }
            }
            
            self._send_status_update(
                status_callback,
                "conditional_formatting_completed",
                {
                    "project_id": project_id,
                    "execution_time": execution_time,
                    "total_chart_configs": len(enhanced_chart_configurations)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in conditional formatting pipeline: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            self._send_status_update(
                status_callback,
                "conditional_formatting_error",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            
            self._metrics.update({
                "last_error": str(e),
                "total_errors": self._metrics.get("total_errors", 0) + 1
            })
            
            raise

    async def _process_sql_expansions(
        self,
        dashboard_config: DashboardConfiguration,
        dashboard_context: Dict[str, Any],
        project_id: str,
        processed_time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        Process SQL expansions for filters that require SQL modifications
        
        Args:
            dashboard_config: The dashboard configuration from the agent
            dashboard_context: Context about dashboard charts
            project_id: Project identifier
            status_callback: Status update callback
            **kwargs: Additional arguments
            
        Returns:
            Dictionary mapping chart_id or query_id to SQL expansion configurations
        """
        sql_expansions = {}
        
        try:
            # Get charts from dashboard context
            charts = dashboard_context.get("charts", [])
            
            # Process regular filters that require SQL expansion
            for filter_obj in dashboard_config.filters:
                # Check if this filter should trigger SQL expansion
                if filter_obj.filter_type in [FilterType.column_filter, FilterType.time_filter]:
                    # Find related charts/queries for this filter
                    related_charts = self._find_related_charts_for_filter(
                        filter_obj=filter_obj,
                        charts=charts,
                        dashboard_context=dashboard_context
                    )
                    
                    for chart_id, chart_info in related_charts.items():
                        if chart_id not in sql_expansions:
                            sql_expansions[chart_id] = {
                                "where_conditions": [],
                                "time_filters": {},
                                "chart_id": chart_id
                            }
                        
                        # Build WHERE condition from filter
                        where_condition = self._build_where_condition_from_filter(filter_obj)
                        if where_condition:
                            sql_expansions[chart_id]["where_conditions"].append(where_condition)
                        
                        # Add time filter if applicable
                        if filter_obj.filter_type == FilterType.time_filter:
                            sql_expansions[chart_id]["time_filters"].update(
                                self._extract_time_filter_from_filter(filter_obj)
                            )
            
            # Process time_filters - use processed_time_filters if available (from early processing), otherwise use dashboard_config.time_filters
            time_filters_to_apply = processed_time_filters if processed_time_filters else dashboard_config.time_filters
            if time_filters_to_apply:
                # Find all charts that should have time filters applied
                # For now, apply to all charts, but can be made more specific
                for chart in charts:
                    chart_id = chart.get("chart_id") or chart.get("id")
                    if chart_id:
                        if chart_id not in sql_expansions:
                            sql_expansions[chart_id] = {
                                "where_conditions": [],
                                "time_filters": {},
                                "chart_id": chart_id
                            }
                        # Add time filters to the expansion config
                        sql_expansions[chart_id]["time_filters"].update(time_filters_to_apply)
            
            # For each chart with SQL expansion, use SQLPipeline to expand the SQL
            for chart_id, expansion_config in sql_expansions.items():
                chart_info = next(
                    (c for c in charts if c.get("chart_id") == chart_id or c.get("id") == chart_id),
                    None
                )
                
                # Try to get SQL from chart_info - check multiple possible fields
                original_sql = None
                if chart_info:
                    original_sql = chart_info.get("sql") or chart_info.get("sql_query")
                
                if original_sql:
                    # Use SQLPipeline to expand SQL if we have conditions or time filters
                    has_conditions = expansion_config.get("where_conditions") and len(expansion_config.get("where_conditions", [])) > 0
                    has_time_filters = expansion_config.get("time_filters") and len(expansion_config.get("time_filters", {})) > 0
                    
                    if has_conditions or has_time_filters:
                        try:
                            logger.info(f"Expanding SQL for chart {chart_id} with conditions: {has_conditions}, time_filters: {has_time_filters}")
                            
                            # Create adjustment request for SQL expansion
                            adjustment_request = self._create_sql_expansion_request(
                                original_sql=original_sql,
                                expansion_config=expansion_config,
                                filter_description=f"Applied filters for chart {chart_id}"
                            )
                            
                            # Use SQLPipeline expand_sql method (direct call, not SQLRequest)
                            expansion_result: SQLResult = await self._sql_pipeline.expand_sql(
                                adjustment_request=adjustment_request,
                                original_sql=original_sql,
                                contexts=[]  # Can be enhanced with schema contexts
                            )
                            
                            if expansion_result.success and expansion_result.data:
                                expanded_sql = expansion_result.data.get("expanded_sql") or expansion_result.data.get("sql", original_sql)
                                sql_expansions[chart_id]["expanded_sql"] = expanded_sql
                                sql_expansions[chart_id]["original_sql"] = original_sql
                                sql_expansions[chart_id]["expansion_metadata"] = expansion_result.metadata
                                
                                logger.info(f"Successfully expanded SQL for chart {chart_id}")
                                
                                self._send_status_update(
                                    status_callback,
                                    "sql_expansion_applied",
                                    {
                                        "chart_id": chart_id,
                                        "project_id": project_id,
                                        "has_expanded_sql": True
                                    }
                                )
                            else:
                                error_msg = expansion_result.error or "Unknown error"
                                logger.warning(f"SQL expansion failed for chart {chart_id}: {error_msg}")
                                sql_expansions[chart_id]["expansion_error"] = error_msg
                                
                        except Exception as e:
                            logger.error(f"Error expanding SQL for chart {chart_id}: {str(e)}")
                            import traceback
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            sql_expansions[chart_id]["expansion_error"] = str(e)
                    else:
                        logger.info(f"Skipping SQL expansion for chart {chart_id} - no conditions or time filters to apply")
            else:
                    logger.warning(f"Chart {chart_id} has no SQL query to expand")
            
            return sql_expansions
            
        except Exception as e:
            logger.error(f"Error processing SQL expansions: {str(e)}")
            return sql_expansions

    async def _process_time_filters(
        self,
        time_filters: Dict[str, Any],
        dashboard_context: Dict[str, Any],
        project_id: str,
        status_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process time filters intelligently using LLM agents
        
        Args:
            time_filters: Time filter configuration from dashboard config
            dashboard_context: Context about dashboard charts
            project_id: Project identifier
            status_callback: Status update callback
            **kwargs: Additional arguments
            
        Returns:
            Processed time filter configuration
        """
        try:
            # The time filters are already processed by the ConditionalFormattingAgent
            # This method can be extended to do additional processing if needed
            # For example, validating date ranges, normalizing formats, etc.
            
            processed_filters = time_filters.copy()
            
            # Validate and normalize time filters
            if "start_date" in processed_filters and "end_date" in processed_filters:
                # Ensure dates are in proper format
                # Can add validation logic here
                pass
            
            if "period" in processed_filters:
                # Normalize period values
                period = processed_filters["period"]
                valid_periods = ["last_30_days", "last_7_days", "current_month", "current_year", "last_quarter"]
                if period not in valid_periods:
                    logger.warning(f"Unknown period value: {period}")
            
            return processed_filters
            
        except Exception as e:
            logger.error(f"Error processing time filters: {str(e)}")
            return time_filters

    def _find_related_charts_for_filter(
        self,
        filter_obj: Any,
        charts: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Find charts that are related to a specific filter"""
        related_charts = {}
        
        column_name = filter_obj.column_name if hasattr(filter_obj, 'column_name') else None
        
        if not column_name:
            return related_charts
        
        # Find charts that use this column
        for chart in charts:
            chart_id = chart.get("chart_id") or chart.get("id")
            chart_columns = chart.get("columns", [])
            available_columns = dashboard_context.get("available_columns", [])
            
            # Check if chart uses this column
            if column_name in chart_columns or column_name in available_columns:
                related_charts[chart_id] = chart
        
        return related_charts

    def _build_where_condition_from_filter(self, filter_obj: Any) -> Optional[str]:
        """Build a WHERE condition string from a filter object"""
        try:
            column_name = filter_obj.column_name if hasattr(filter_obj, 'column_name') else None
            operator = filter_obj.operator.value if hasattr(filter_obj.operator, 'value') else str(filter_obj.operator)
            value = filter_obj.value if hasattr(filter_obj, 'value') else None
            
            if not column_name or not operator:
                return None
            
            # Map operators to SQL conditions
            operator_map = {
                "equals": "=",
                "not_equals": "!=",
                "greater_than": ">",
                "less_than": "<",
                "greater_equal": ">=",
                "less_equal": "<=",
                "contains": "LIKE",
                "not_contains": "NOT LIKE",
                "starts_with": "LIKE",
                "ends_with": "LIKE",
                "in": "IN",
                "not_in": "NOT IN",
                "is_null": "IS NULL",
                "is_not_null": "IS NOT NULL"
            }
            
            sql_operator = operator_map.get(operator, "=")
            
            # Build condition based on operator
            if operator in ["is_null", "is_not_null"]:
                return f"{column_name} {sql_operator}"
            elif operator in ["contains", "not_contains"]:
                return f"{column_name} {sql_operator} '%{value}%'"
            elif operator == "starts_with":
                return f"{column_name} LIKE '{value}%'"
            elif operator == "ends_with":
                return f"{column_name} LIKE '%{value}'"
            elif operator in ["in", "not_in"]:
                if isinstance(value, list):
                    values_str = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in value])
                    return f"{column_name} {sql_operator} ({values_str})"
                else:
                    return f"{column_name} {sql_operator} ('{value}')"
            else:
                # Standard comparison operators
                value_str = f"'{value}'" if isinstance(value, str) else str(value)
                return f"{column_name} {sql_operator} {value_str}"
                
        except Exception as e:
            logger.error(f"Error building WHERE condition: {str(e)}")
            return None

    def _extract_time_filter_from_filter(self, filter_obj: Any) -> Dict[str, Any]:
        """Extract time filter information from a filter object"""
        time_filter = {}
        
        try:
            if hasattr(filter_obj, 'value'):
                value = filter_obj.value
            elif hasattr(filter_obj, 'time_filters'):
                return filter_obj.time_filters
            
            # Try to extract time information from value
            if isinstance(value, dict):
                time_filter.update(value)
            elif isinstance(value, str):
                # Try to parse period strings
                if "last_30_days" in value.lower():
                    time_filter["period"] = "last_30_days"
                elif "last_7_days" in value.lower():
                    time_filter["period"] = "last_7_days"
                elif "current_month" in value.lower():
                    time_filter["period"] = "current_month"
                elif "current_year" in value.lower():
                    time_filter["period"] = "current_year"
            
        except Exception as e:
            logger.error(f"Error extracting time filter: {str(e)}")
        
        return time_filter

    async def _execute_expanded_sql_queries(
        self,
        sql_expansions: Dict[str, Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        project_id: str,
        status_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute expanded SQL queries using SQLExecutionPipeline
        
        Args:
            sql_expansions: Dictionary of SQL expansions with expanded_sql
            dashboard_context: Context about dashboard charts
            project_id: Project identifier
            status_callback: Status update callback
            **kwargs: Additional arguments
            
        Returns:
            Dictionary mapping chart_id to execution results
        """
        executed_results = {}
        
        try:
            charts = dashboard_context.get("charts", [])
            
            for chart_id, expansion_config in sql_expansions.items():
                expanded_sql = expansion_config.get("expanded_sql")
                
                if not expanded_sql:
                    logger.warning(f"No expanded SQL for chart {chart_id}, skipping execution")
                    continue
                
                try:
                    logger.info(f"Executing expanded SQL for chart {chart_id}")
                    
                    # Execute SQL using SQLExecutionPipeline
                    execution_result = await self._sql_execution_pipeline.run(
                        sql=expanded_sql,
                        project_id=project_id,
                        configuration={"dry_run": False}
                    )
                    
                    if execution_result.get("post_process"):
                        executed_results[chart_id] = {
                            "success": True,
                            "data": execution_result["post_process"].get("data", []),
                            "columns": execution_result["post_process"].get("columns", []),
                            "row_count": len(execution_result["post_process"].get("data", [])),
                            "execution_metadata": execution_result.get("metadata", {})
                        }
                        
                        self._send_status_update(
                            status_callback,
                            "sql_execution_success",
                            {
                                "chart_id": chart_id,
                                "project_id": project_id,
                                "row_count": executed_results[chart_id]["row_count"]
                            }
                        )
                    else:
                        executed_results[chart_id] = {
                            "success": False,
                            "error": "No data returned from SQL execution"
                        }
                        
                except Exception as e:
                    logger.error(f"Error executing expanded SQL for chart {chart_id}: {str(e)}")
                    executed_results[chart_id] = {
                        "success": False,
                        "error": str(e)
                    }
            
            return executed_results
            
        except Exception as e:
            logger.error(f"Error executing expanded SQL queries: {str(e)}")
            return executed_results

    async def _apply_chart_adjustments(
        self,
        chart_configurations: Dict[str, Dict[str, Any]],
        dashboard_config: DashboardConfiguration,
        dashboard_context: Dict[str, Any],
        executed_sql_results: Dict[str, Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        Apply chart adjustments using ChartAdjustmentPipeline
        
        Args:
            chart_configurations: Chart configurations with chart_adjustment entries
            dashboard_config: Dashboard configuration with conditional formats
            dashboard_context: Context about dashboard charts
            executed_sql_results: Results from SQL execution
            project_id: Project identifier
            status_callback: Status update callback
            **kwargs: Additional arguments
            
        Returns:
            Dictionary mapping chart_id to adjusted chart configurations
        """
        adjusted_configurations = chart_configurations.copy()
        
        try:
            charts = dashboard_context.get("charts", [])
            
            # Process each conditional format that requires chart adjustment
            if dashboard_config and dashboard_config.conditional_formats:
                for conditional_format in dashboard_config.conditional_formats:
                    chart_id = conditional_format.chart_id
                    
                    # Check if this conditional format requires chart adjustment
                    if not conditional_format.formatting_rules:
                        continue
                    
                    formatting_rules = conditional_format.formatting_rules
                    # Apply chart adjustments for chart-level formatting (color, font_weight, font_style, etc.)
                    has_chart_level_formatting = (
                        "color" in formatting_rules or
                        "font_weight" in formatting_rules or
                        "font_style" in formatting_rules or
                        "font_size" in formatting_rules
                    )
                    if not has_chart_level_formatting:
                        continue
                    
                    # Find the chart info
                    chart_info = next(
                        (c for c in charts if c.get("chart_id") == chart_id or c.get("id") == chart_id),
                        None
                    )
                    
                    if not chart_info:
                        logger.warning(f"Chart {chart_id} not found in dashboard context")
                        continue
                    
                    # Get chart schema
                    chart_schema = chart_info.get("chart_schema") or chart_info.get("chart_config", {}).get("chart_schema", {})
                    
                    if not chart_schema:
                        logger.warning(f"No chart schema found for chart {chart_id}")
                        continue
                    
                    # Get SQL query (use expanded SQL if available, otherwise original)
                    sql_query = chart_info.get("sql") or chart_info.get("sql_query", "")
                    
                    # Get sample data (use executed SQL results if available, otherwise from chart_info)
                    sample_data = {}
                    if chart_id in executed_sql_results and executed_sql_results[chart_id].get("success"):
                        result_data = executed_sql_results[chart_id]
                        # Convert data to the format expected by chart adjustment pipeline
                        data_rows = result_data.get("data", [])[:10]  # First 10 rows for chart adjustment
                        columns = result_data.get("columns", [])
                        
                        # Ensure data is in the right format (list of dicts)
                        if data_rows and isinstance(data_rows[0], dict):
                            sample_data = {
                                "columns": columns,
                                "data": data_rows
                            }
                        else:
                            # Convert list of lists to list of dicts if needed
                            sample_data = {
                                "columns": columns,
                                "data": [dict(zip(columns, row)) for row in data_rows] if data_rows else []
                            }
                    elif chart_info.get("sample_data"):
                        sample_data = chart_info["sample_data"]
                        # Ensure it has the right structure
                        if not isinstance(sample_data, dict):
                            sample_data = {"columns": [], "data": []}
                        if "columns" not in sample_data:
                            sample_data["columns"] = []
                        if "data" not in sample_data:
                            sample_data["data"] = []
                    else:
                        logger.warning(f"No sample data available for chart {chart_id} adjustment")
                        continue
                    
                    # Create adjustment option from conditional format
                    from app.agents.nodes.sql.utils.chart_models import ChartAdjustmentOption
                    
                    adjustment_option = ChartAdjustmentOption(
                        query=conditional_format.description or f"Apply formatting: {formatting_rules}",
                        chart_type=chart_schema.get("mark", {}).get("type", "bar"),
                        color=formatting_rules.get("color"),
                        font_weight=formatting_rules.get("font_weight"),
                        font_style=formatting_rules.get("font_style"),
                        font_size=formatting_rules.get("font_size"),
                        title=None,
                        x_axis=None,
                        y_axis=None
                    )
                    
                    try:
                        logger.info(f"Applying chart adjustment for chart {chart_id}")
                        
                        # Call ChartAdjustmentPipeline
                        adjustment_result = await self._chart_adjustment_pipeline.run(
                            query=conditional_format.description or f"Apply formatting to chart {chart_id}",
                            sql=sql_query,
                            adjustment_option=adjustment_option,
                            chart_schema=chart_schema,
                            data=sample_data,
                            language="English"
                        )
                        
                        if adjustment_result.get("success", False):
                            # Extract adjusted chart schema
                            adjusted_schema = None
                            if adjustment_result.get("post_process", {}).get("results", {}).get("chart_schema"):
                                adjusted_schema = adjustment_result["post_process"]["results"]["chart_schema"]
                            elif adjustment_result.get("data", {}).get("chart_schema"):
                                adjusted_schema = adjustment_result["data"]["chart_schema"]
                            elif adjustment_result.get("data", {}).get("chart_config"):
                                adjusted_schema = adjustment_result["data"]["chart_config"]
                            
                            if adjusted_schema:
                                # Update chart configuration with adjusted schema
                                if chart_id not in adjusted_configurations:
                                    adjusted_configurations[chart_id] = {
                                        "chart_id": chart_id,
                                        "actions": []
                                    }
                                
                                adjusted_configurations[chart_id]["adjusted_chart_schema"] = adjusted_schema
                                adjusted_configurations[chart_id]["chart_adjustment_result"] = {
                                    "success": True,
                                    "reasoning": adjustment_result.get("post_process", {}).get("results", {}).get("reasoning") or adjustment_result.get("data", {}).get("reasoning", ""),
                                    "chart_type": adjustment_result.get("post_process", {}).get("results", {}).get("chart_type") or adjustment_result.get("data", {}).get("chart_type", "")
                                }
                                
                                self._send_status_update(
                                    status_callback,
                                    "chart_adjustment_applied",
                                    {
                                        "chart_id": chart_id,
                                        "project_id": project_id
                                    }
                                )
                            else:
                                logger.warning(f"No adjusted chart schema returned for chart {chart_id}")
                        else:
                            error_msg = adjustment_result.get("error", "Unknown error")
                            logger.warning(f"Chart adjustment failed for chart {chart_id}: {error_msg}")
                            
                            if chart_id not in adjusted_configurations:
                                adjusted_configurations[chart_id] = {
                                    "chart_id": chart_id,
                                    "actions": []
                                }
                            
                            adjusted_configurations[chart_id]["chart_adjustment_result"] = {
                                "success": False,
                                "error": error_msg
                            }
                            
                    except Exception as e:
                        logger.error(f"Error applying chart adjustment for chart {chart_id}: {str(e)}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        
                        if chart_id not in adjusted_configurations:
                            adjusted_configurations[chart_id] = {
                                "chart_id": chart_id,
                                "actions": []
                            }
                        
                        adjusted_configurations[chart_id]["chart_adjustment_result"] = {
                            "success": False,
                            "error": str(e)
                        }
            
            return adjusted_configurations
            
        except Exception as e:
            logger.error(f"Error applying chart adjustments: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return adjusted_configurations

    def _create_sql_expansion_request(
        self,
        original_sql: str,
        expansion_config: Dict[str, Any],
        filter_description: str
    ) -> str:
        """Create a natural language request for SQL expansion with time filters included in natural language"""
        where_conditions = expansion_config.get("where_conditions", [])
        time_filters = expansion_config.get("time_filters", {})
        
        # Build comprehensive filter description including time filters
        filter_descriptions = []
        if filter_description:
            filter_descriptions.append(filter_description)
        
        # Include time filters in natural language format (processed early, so they're ready)
        if time_filters:
            time_filter_description = self._format_time_filter_for_sql_expansion(time_filters)
            if time_filter_description:
                filter_descriptions.append(time_filter_description)
        
        # Create the main request
        if filter_descriptions:
            request_parts = [f"Expand the following SQL query to include the following filters: {'; '.join(filter_descriptions)}"]
        else:
            request_parts = ["Expand the following SQL query to include the following filters:"]
        
        # Add WHERE conditions if any (for reference, but time filters should be in natural language)
        if where_conditions:
            request_parts.append(f"Additional WHERE conditions: {', '.join(where_conditions)}")
        
        request_parts.append(f"\nOriginal SQL:\n{original_sql}")
        
        return "\n".join(request_parts)
    
    def _format_time_filter_for_sql_expansion(self, time_filters: Dict[str, Any]) -> str:
        """Format time filters as natural language for SQL expansion request"""
        try:
            period = time_filters.get("period", "")
            description = time_filters.get("description", "")
            start_date = time_filters.get("start_date")
            end_date = time_filters.get("end_date")
            
            # Prefer description if available (it's already in natural language)
            if description:
                return description
            
            # Otherwise, format based on period
            if period:
                # Convert period to natural language
                period_map = {
                    "last_30_days": "the last 30 days",
                    "last_7_days": "the last 7 days",
                    "last_6_months": "the last 6 months",
                    "last_quarter": "the last quarter",
                    "current_month": "the current month",
                    "current_year": "the current year"
                }
                period_desc = period_map.get(period, period)
                
                # Create a clear natural language description
                if start_date and end_date:
                    return f"Filter to show only records from {period_desc} (from {start_date} to {end_date})"
                else:
                    return f"Filter to show only records from {period_desc}"
            
            # Fallback to date range if no period
            if start_date and end_date:
                return f"Filter to show only records from {start_date} to {end_date}"
            elif start_date:
                return f"Filter to show only records from {start_date} onwards"
            elif end_date:
                return f"Filter to show only records up to {end_date}"
            
            # No time filter information available
            return ""
        except Exception as e:
            logger.error(f"Error formatting time filter for SQL expansion: {str(e)}")
            return ""

    def _enhance_chart_configurations(
        self,
        chart_configurations: Dict[str, Dict[str, Any]],
        sql_expansions: Dict[str, Dict[str, Any]],
        time_filters: Optional[Dict[str, Any]],
        dashboard_config: DashboardConfiguration
    ) -> Dict[str, Dict[str, Any]]:
        """Enhance chart configurations with SQL expansions, time filters, and chart adjustments"""
        enhanced = chart_configurations.copy()
        
        # Add SQL expansion information to relevant chart configurations
        for chart_id, expansion_config in sql_expansions.items():
            if chart_id in enhanced:
                enhanced[chart_id]["sql_expansion"] = expansion_config
                # Mark that SQL expansion action should be applied
                if "actions" not in enhanced[chart_id]:
                    enhanced[chart_id]["actions"] = []
                if ActionType.SQL_EXPANSION.value not in enhanced[chart_id]["actions"]:
                    enhanced[chart_id]["actions"].append(ActionType.SQL_EXPANSION.value)
            else:
                # Create new configuration for this chart
                enhanced[chart_id] = {
                    "chart_id": chart_id,
                    "actions": [ActionType.SQL_EXPANSION.value],
                    "sql_expansion": expansion_config
                }
        
        # Add time filters to chart configurations
        if time_filters:
            for chart_id in enhanced.keys():
                if "time_filters" not in enhanced[chart_id]:
                    enhanced[chart_id]["time_filters"] = time_filters
        
        # Process conditional formats and add chart adjustments
        if dashboard_config and dashboard_config.conditional_formats:
            for conditional_format in dashboard_config.conditional_formats:
                chart_id = conditional_format.chart_id
                
                # Initialize chart configuration if it doesn't exist
                if chart_id not in enhanced:
                    enhanced[chart_id] = {
                        "chart_id": chart_id,
                        "actions": [],
                        "filters": []
                    }
                
                # Add conditional format to filters list
                if "filters" not in enhanced[chart_id]:
                    enhanced[chart_id]["filters"] = []
                enhanced[chart_id]["filters"].append({
                    "format_id": conditional_format.format_id,
                    "condition": {
                        "filter_id": conditional_format.condition.filter_id if conditional_format.condition else None,
                        "filter_type": conditional_format.condition.filter_type.value if conditional_format.condition and hasattr(conditional_format.condition.filter_type, 'value') else str(conditional_format.condition.filter_type) if conditional_format.condition else None,
                        "column_name": conditional_format.condition.column_name if conditional_format.condition else None,
                        "operator": conditional_format.condition.operator.value if conditional_format.condition and hasattr(conditional_format.condition.operator, 'value') else str(conditional_format.condition.operator) if conditional_format.condition else None,
                        "value": conditional_format.condition.value if conditional_format.condition else None
                    },
                    "formatting_rules": conditional_format.formatting_rules,
                    "description": conditional_format.description
                })
                
                # Check if this conditional format requires chart adjustment (e.g., font_weight changes)
                if conditional_format.formatting_rules:
                    formatting_rules = conditional_format.formatting_rules
                    # If formatting includes chart-level changes (like font_weight), add chart adjustment
                    if "font_weight" in formatting_rules or "font_style" in formatting_rules or "font_size" in formatting_rules:
                        if "chart_adjustment" not in enhanced[chart_id]:
                            enhanced[chart_id]["chart_adjustment"] = {
                                "adjustment_type": "conditional_format",
                                "condition": {
                                    "filter_id": conditional_format.condition.filter_id if conditional_format.condition else None,
                                    "filter_type": conditional_format.condition.filter_type.value if conditional_format.condition and hasattr(conditional_format.condition.filter_type, 'value') else str(conditional_format.condition.filter_type) if conditional_format.condition else None,
                                    "column_name": conditional_format.condition.column_name if conditional_format.condition else None,
                                    "operator": conditional_format.condition.operator.value if conditional_format.condition and hasattr(conditional_format.condition.operator, 'value') else str(conditional_format.condition.operator) if conditional_format.condition else None,
                                    "value": conditional_format.condition.value if conditional_format.condition else None
                                },
                                "formatting": formatting_rules,
                                "description": conditional_format.description
                            }
                        else:
                            # Merge formatting rules if chart adjustment already exists
                            existing_formatting = enhanced[chart_id]["chart_adjustment"].get("formatting", {})
                            existing_formatting.update(formatting_rules)
                            enhanced[chart_id]["chart_adjustment"]["formatting"] = existing_formatting
                        
                        # Mark that chart adjustment action should be applied
                        if "actions" not in enhanced[chart_id]:
                            enhanced[chart_id]["actions"] = []
                        if ActionType.CHART_ADJUSTMENT.value not in enhanced[chart_id]["actions"]:
                            enhanced[chart_id]["actions"].append(ActionType.CHART_ADJUSTMENT.value)
        
        return enhanced


# Optional adapter to use ConditionalFormattingPipeline as a service interface
class ConditionalFormattingPipelineAdapter:
    """
    Adapter to use ConditionalFormattingPipeline as a service interface
    for EnhancedDashboardPipeline if needed, while keeping flows separate.
    """
    def __init__(self, pipeline: ConditionalFormattingPipeline):
        self._pipeline = pipeline
    
    async def process_conditional_formatting_request(
        self,
        query: str,
        dashboard_context: Dict[str, Any],
        project_id: str = "default",
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Adapter method to match service interface"""
        result = await self._pipeline.run(
            natural_language_query=query,
            dashboard_context=dashboard_context,
            project_id=project_id,
            additional_context=additional_context,
            time_filters=time_filters
        )
        return result
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics from the pipeline"""
        return self._pipeline.get_metrics()


# Factory function for creating conditional formatting pipeline
def create_conditional_formatting_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    document_store_provider: Any = None,
    sql_pipeline: Optional[SQLPipeline] = None,
    sql_execution_pipeline: Optional[SQLExecutionPipeline] = None,
    **kwargs
) -> ConditionalFormattingPipeline:
    """
    Factory function to create a conditional formatting pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        document_store_provider: Document store provider (optional, will use default if not provided)
        sql_pipeline: Existing SQL pipeline (optional, will create if not provided)
        sql_execution_pipeline: Existing SQL execution pipeline (optional, will create if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        ConditionalFormattingPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return ConditionalFormattingPipeline(
        name="conditional_formatting_pipeline",
        version="1.0.0",
        description="Pipeline for processing conditional formatting requests using LLM agents",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        document_store_provider=document_store_provider,
        sql_pipeline=sql_pipeline,
        sql_execution_pipeline=sql_execution_pipeline,
        **kwargs
    )
