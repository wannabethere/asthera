import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import asdict
import json
from pathlib import Path

from app.agents.pipelines.writers.report_orchestrator_pipeline import ReportOrchestratorPipeline, create_report_orchestrator_pipeline
from app.agents.nodes.writers.report_writing_agent import (
    ReportWritingAgent, 
    ReportWorkflowData, 
    ThreadComponentData, 
    WriterActorType, 
    BusinessGoal,
    ComponentType
)
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.servicebase import BaseService
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.services.workflow_integration import get_workflow_integration_service



logger = logging.getLogger("lexy-ai-service")


class ReportService(BaseService):
    """Pure API service for report operations that delegates to agent pipelines"""
    
    def __init__(self, engine: Engine = None):
        """Initialize report service as a pure API layer"""
        # Initialize BaseService with empty pipelines dict (we'll use agent pipelines directly)
        super().__init__(pipelines={})
        
        self._engine = engine
        self._llm = get_llm()
        
        # Initialize the report orchestrator pipeline
        try:
            self._report_orchestrator = create_report_orchestrator_pipeline(
                engine=engine,
                llm=self._llm
            )
            logger.info("Report Orchestrator Pipeline initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Report Orchestrator Pipeline: {e}")
            self._report_orchestrator = None
        
        # Initialize report writing agent
        try:
            self._report_writing_agent = ReportWritingAgent(llm=self._llm)
            logger.info("Report Writing Agent initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Report Writing Agent: {e}")
            self._report_writing_agent = None
        
        # Agent pipeline registry for report operations
        try:
            self.pipeline_container = PipelineContainer.initialize()
            self._agent_pipelines = {
                "conditional_formatting": self.pipeline_container.get_pipeline("conditional_formatting_generation"),
                "simple_report": self.pipeline_container.get_pipeline("simple_report_generation"),
                "sql_refresh": self.pipeline_container.get_pipeline("sql_refresh")
            }
            
            # Validate that required agent pipelines are available
            for pipeline_name, pipeline in self._agent_pipelines.items():
                if pipeline is None:
                    logger.warning(f"Agent pipeline '{pipeline_name}' is not available - report functionality may be limited")
                else:
                    logger.info(f"Agent pipeline '{pipeline_name}' initialized successfully")
                    
        except Exception as e:
            logger.error(f"Error initializing report agent pipelines: {e}")
            self._agent_pipelines = {
                "conditional_formatting": None,
                "simple_report": None,
                "sql_refresh": None
            }
        
        # Configuration cache and execution history
        self._configuration_cache = {}
        self._execution_history = []
        self._report_templates = {}
        
        # Initialize workflow integration service
        self._workflow_integration = get_workflow_integration_service()
        
        # Initialize default report templates
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Initialize default report templates"""
        self._report_templates = {
            "executive_summary": {
                "name": "Executive Summary Report",
                "description": "High-level summary for executives and stakeholders",
                "components": [
                    "executive_overview",
                    "key_metrics",
                    "trends_analysis",
                    "recommendations"
                ],
                "writer_actor": WriterActorType.EXECUTIVE,
                "business_goal": BusinessGoal(
                    primary_objective="Strategic decision making",
                    target_audience=["executives", "stakeholders"],
                    decision_context="High-level strategic planning",
                    success_metrics=["strategic alignment", "decision quality"],
                    timeframe="quarterly"
                )
            },
            "detailed_analysis": {
                "name": "Detailed Analysis Report",
                "description": "Comprehensive analysis with detailed insights",
                "components": [
                    "executive_summary",
                    "methodology",
                    "detailed_findings",
                    "data_analysis",
                    "conclusions",
                    "appendix"
                ],
                "writer_actor": WriterActorType.ANALYST,
                "business_goal": BusinessGoal(
                    primary_objective="Operational insights",
                    target_audience=["operations team", "managers"],
                    decision_context="Day-to-day operational decisions",
                    success_metrics=["efficiency", "productivity"],
                    timeframe="weekly"
                )
            },
            "performance_review": {
                "name": "Performance Review Report",
                "description": "Performance metrics and analysis report",
                "components": [
                    "performance_overview",
                    "kpi_analysis",
                    "trends",
                    "benchmarks",
                    "action_items"
                ],
                "writer_actor": WriterActorType.ANALYST,
                "business_goal": BusinessGoal(
                    primary_objective="Performance optimization",
                    target_audience=["performance team", "management"],
                    decision_context="Performance improvement decisions",
                    success_metrics=["performance metrics", "optimization results"],
                    timeframe="monthly"
                )
            },
            "trend_analysis": {
                "name": "Trend Analysis Report",
                "description": "Analysis of trends and patterns over time",
                "components": [
                    "trend_overview",
                    "seasonal_patterns",
                    "forecasting",
                    "drivers_analysis",
                    "future_outlook"
                ],
                "writer_actor": WriterActorType.DATA_SCIENTIST,
                "business_goal": BusinessGoal(
                    primary_objective="Trend analysis",
                    target_audience=["data scientists", "analysts"],
                    decision_context="Trend-based strategic decisions",
                    success_metrics=["trend accuracy", "prediction quality"],
                    timeframe="quarterly"
                )
            }
        }
    
    async def generate_report_from_workflow(
        self,
        workflow_data: Union[Dict[str, Any], str],
        report_queries: List[Dict[str, Any]],
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a report using workflow data - delegates to agent pipelines
        
        Args:
            workflow_data: Workflow data as dict or JSON file path
            report_queries: List of SQL queries for report data
            project_id: Project identifier
            natural_language_query: Natural language query for conditional formatting (optional)
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            
        Returns:
            Dictionary containing complete report results
        """
        try:
            # Parse workflow data (simplified - no database models)
            workflow_info = self._parse_workflow_data(workflow_data)
            
            if not workflow_info:
                raise ValueError("Invalid workflow data provided")
            
            # Extract components and configuration from workflow
            thread_components = self._extract_thread_components_from_workflow(workflow_info)
            writer_actor = self._determine_writer_actor_from_workflow(workflow_info)
            business_goal = self._determine_business_goal_from_workflow(workflow_info)
            
            # Create report context from workflow
            report_context = self._create_report_context_from_workflow_data(workflow_info)
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "workflow_report_generation_started",
                {
                    "project_id": project_id,
                    "workflow_id": workflow_info.get("id"),
                    "workflow_state": workflow_info.get("state"),
                    "total_components": len(thread_components),
                    "total_queries": len(report_queries)
                }
            )
            
            # Delegate to agent pipeline for processing
            result = await self.generate_comprehensive_report(
                report_queries=report_queries,
                project_id=project_id,
                report_context=report_context,
                natural_language_query=natural_language_query,
                custom_components=thread_components,
                writer_actor=writer_actor,
                business_goal=business_goal,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=status_callback,
                configuration=configuration
            )
            
            # Add workflow metadata to result
            result["workflow_metadata"] = {
                "workflow_id": workflow_info.get("id"),
                "workflow_state": workflow_info.get("state"),
                "workflow_type": "report_workflow",
                "components_processed": len(thread_components),
                "workflow_source": workflow_info.get("source", "unknown")
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in workflow-based report generation: {e}")
            self._send_status_update(
                status_callback,
                "workflow_report_generation_failed",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            raise
    
    def _parse_workflow_data(
        self, 
        workflow_data: Union[Dict[str, Any], str]
    ) -> Optional[Dict[str, Any]]:
        """Parse workflow data from various input formats (no database dependencies)"""
        
        try:
            if isinstance(workflow_data, str):
                # Assume it's a file path
                if Path(workflow_data).exists():
                    return self._load_workflow_from_json_file(workflow_data)
                else:
                    # Try to parse as JSON string
                    return json.loads(workflow_data)
            
            elif isinstance(workflow_data, dict):
                # Already a dictionary
                workflow_data["source"] = "dict_input"
                return workflow_data
            
            else:
                logger.error(f"Unsupported workflow data type: {type(workflow_data)}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing workflow data: {e}")
            return None
    
    def _load_workflow_from_json_file(self, file_path: str) -> Dict[str, Any]:
        """Load workflow data from JSON file"""
        try:
            with open(file_path, 'r') as f:
                workflow_data = json.load(f)
                workflow_data["source"] = "json_file"
                return workflow_data
        except Exception as e:
            logger.error(f"Error loading workflow from JSON file {file_path}: {e}")
            raise
    

    
    def _extract_thread_components_from_workflow(self, workflow_info: Dict[str, Any]) -> List[ThreadComponentData]:
        """Extract thread components from workflow data and convert to ThreadComponentData"""
        components = []
        
        try:
            workflow_components = workflow_info.get("thread_components", [])
            logger.info(f"Found {len(workflow_components)} workflow components")
            
            # Check if we have a final_result at the top level (data summarization pipeline output)
            final_result = workflow_info.get("final_result")
            if final_result:
                # Check if final_result contains chart data
                chart_schema = final_result.get('post_process', {}).get('visualization', {}).get('chart_schema')
                has_chart_data = bool(chart_schema)
                logger.info(f"Found final_result at top level, has_chart_data: {has_chart_data}")
                
                if has_chart_data:
                    # Prioritize data summarization pipeline output with chart data
                    logger.info("Creating dynamic components from data summarization pipeline output with chart data")
                    components = self._create_dynamic_components_from_final_result(final_result)
                    return components
                elif not workflow_components:
                    # Fallback: no workflow_components but we have final_result
                    logger.info("No workflow components found, creating from final_result")
                    components = self._create_dynamic_components_from_final_result(final_result)
                    return components
            
            # If no thread components, try to create them from query results
            if not workflow_components:
                logger.info("No workflow components found, creating from query results")
                components = self._create_components_from_query_results(workflow_info)
            else:
                for comp in workflow_components:
                    # Convert workflow component type to report component type
                    component_type = self._map_workflow_component_type(comp.get("component_type"))
                    
                    # Create ThreadComponentData
                    thread_component = ThreadComponentData(
                        id=comp.get("id", f"component_{len(components)}"),
                        component_type=component_type,
                        sequence_order=comp.get("sequence_order", 0),
                        question=comp.get("question", f"Component {comp.get('sequence_order', len(components))}"),
                        description=comp.get("description", ""),
                        overview=comp.get("overview"),
                        chart_config=comp.get("chart_config"),
                        table_config=comp.get("table_config"),
                        configuration=comp.get("configuration", {}),
                        final_result=comp.get("final_result")
                    )
                    
                    components.append(thread_component)
            
            # Sort by sequence order
            components.sort(key=lambda x: x.sequence_order)
            
            return components
            
        except Exception as e:
            logger.error(f"Error extracting thread components from workflow: {e}")
            return []
    
    def _create_dynamic_components_from_final_result(self, final_result: Dict[str, Any]) -> List[ThreadComponentData]:
        """Create thread components dynamically from final_result data"""
        components = []
        
        try:
            # Extract metadata from final_result
            post_process = final_result.get('post_process', {})
            visualization = post_process.get('visualization', {})
            chart_schema = visualization.get('chart_schema', {})
            executive_summary = post_process.get('executive_summary', '')
            data_overview = post_process.get('data_overview', {})
            
            # Determine component type based on available data
            component_type = ComponentType.CHART
            if chart_schema:
                component_type = ComponentType.CHART
            elif data_overview:
                component_type = ComponentType.TABLE
            else:
                component_type = ComponentType.OVERVIEW
            
            # Extract dynamic title and description from executive summary or chart data
            title = self._extract_dynamic_title(executive_summary, chart_schema)
            description = self._extract_dynamic_description(executive_summary, chart_schema, data_overview)
            
            # Create component with dynamic information
            thread_component = ThreadComponentData(
                id="dynamic_analysis_component",
                component_type=component_type,
                sequence_order=0,
                question=title,
                description=description,
                overview=data_overview,
                chart_config=chart_schema,
                table_config=None,
                configuration={},
                final_result=final_result
            )
            
            components.append(thread_component)
            logger.info(f"Created dynamic component: {title} with type: {component_type.value}")
            
            return components
            
        except Exception as e:
            logger.error(f"Error creating dynamic components from final_result: {e}")
            return []
    
    def _extract_dynamic_title(self, executive_summary: str, chart_schema: Dict[str, Any]) -> str:
        """Extract dynamic title from executive summary or chart data"""
        try:
            # Try to extract title from executive summary
            if executive_summary:
                # Look for patterns like "analysis of", "report on", etc.
                lines = executive_summary.split('\n')
                for line in lines:
                    line = line.strip()
                    if 'analysis' in line.lower() and ('completion' in line.lower() or 'training' in line.lower()):
                        # Extract the main subject
                        if 'completion' in line.lower():
                            return "Training Completion Analysis"
                        elif 'performance' in line.lower():
                            return "Performance Analysis"
                        elif 'training' in line.lower():
                            return "Training Analysis"
            
            # Try to extract title from chart schema
            if chart_schema and 'title' in chart_schema:
                return chart_schema['title']
            
            # Look at chart data to determine title
            if chart_schema and 'data' in chart_schema and 'values' in chart_schema['data']:
                values = chart_schema['data']['values']
                if values:
                    # Check field names to determine analysis type
                    first_item = values[0] if values else {}
                    if 'completion_rate' in first_item:
                        return "Training Completion Analysis"
                    elif 'performance' in first_item:
                        return "Performance Analysis"
                    elif 'sales' in first_item:
                        return "Sales Analysis"
                    elif 'revenue' in first_item:
                        return "Revenue Analysis"
            
            # Default fallback
            return "Data Analysis"
            
        except Exception as e:
            logger.error(f"Error extracting dynamic title: {e}")
            return "Data Analysis"
    
    def _extract_dynamic_description(self, executive_summary: str, chart_schema: Dict[str, Any], data_overview: Dict[str, Any]) -> str:
        """Extract dynamic description from executive summary, chart data, or data overview"""
        try:
            # Try to extract description from executive summary
            if executive_summary:
                # Look for the first meaningful sentence
                sentences = executive_summary.split('.')
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) > 20 and ('analysis' in sentence.lower() or 'report' in sentence.lower()):
                        return sentence
            
            # Try to extract from chart schema
            if chart_schema and 'data' in chart_schema and 'values' in chart_schema['data']:
                values = chart_schema['data']['values']
                if values:
                    first_item = values[0] if values else {}
                    if 'completion_rate' in first_item:
                        return "Analysis of training completion rates across different positions"
                    elif 'performance' in first_item:
                        return "Analysis of performance metrics across different roles"
                    elif 'sales' in first_item:
                        return "Analysis of sales data across different categories"
                    elif 'revenue' in first_item:
                        return "Analysis of revenue data across different segments"
            
            # Try to extract from data overview
            if data_overview:
                total_rows = data_overview.get('total_rows', 0)
                if total_rows > 0:
                    return f"Analysis of {total_rows} data points across different categories"
            
            # Default fallback
            return "Analysis of data across different categories"
            
        except Exception as e:
            logger.error(f"Error extracting dynamic description: {e}")
            return "Analysis of data across different categories"
    
    def _create_components_from_query_results(self, workflow_info: Dict[str, Any]) -> List[ThreadComponentData]:
        """Create thread components from query results when no thread components exist"""
        components = []
        
        try:
            # Look for query results in the workflow data
            query_results = workflow_info.get("query_results", {})
            if not query_results:
                # Try to find query results in nested structures
                report_results = workflow_info.get("report_results", {})
                if report_results:
                    query_results = report_results.get("query_results", {})
            
            # Also check for data summarization pipeline output
            final_result = workflow_info.get("final_result")
            if final_result and not query_results:
                logger.info("Found data summarization pipeline output, creating dynamic components from final_result")
                components = self._create_dynamic_components_from_final_result(final_result)
                return components
            
            if query_results:
                for query_id, query_data in query_results.items():
                    # Determine component type based on query data
                    component_type = ComponentType.CHART  # Default to chart for visualization
                    
                    # Extract chart schema from query data
                    chart_schema = query_data.get("chart_schema", {})
                    
                    # Create meaningful question and description based on the query
                    question = query_data.get("name", f"Query {query_id}")
                    if "completion" in question.lower() or "completion" in str(query_data.get("sql", "")).lower():
                        question = "Training Completion Analysis"
                        description = "Analysis of training completion rates across different positions"
                    else:
                        description = f"Analysis of {query_data.get('name', 'training data')}"
                    
                    # Create ThreadComponentData from query result
                    thread_component = ThreadComponentData(
                        id=f"query_{query_id}",
                        component_type=component_type,
                        sequence_order=0,
                        question=question,
                        description=description,
                        overview=None,
                        chart_config=chart_schema,
                        table_config=None,
                        configuration={},
                        final_result={
                            "post_process": {
                                "visualization": {
                                    "chart_schema": chart_schema
                                },
                                "executive_summary": f"Analysis of {question}",
                                "data_overview": {
                                    "total_rows": query_data.get("row_count", 0),
                                    "columns": query_data.get("columns", [])
                                }
                            }
                        } if chart_schema else None
                    )
                    
                    logger.info(f"Created thread component: {thread_component.id} with chart_data: {chart_schema is not None}")
                    components.append(thread_component)
            else:
                # Create a default component if no query results
                thread_component = ThreadComponentData(
                    id="default_analysis",
                    component_type=ComponentType.CHART,
                    sequence_order=0,
                    question="Training Completion Analysis",
                    description="Analysis of training completion rates across positions",
                    overview=None,
                    chart_config=None,
                    table_config=None,
                    configuration={},
                    final_result=None
                )
                components.append(thread_component)
            
            return components
            
        except Exception as e:
            logger.error(f"Error creating components from query results: {e}")
            return []
    
    def _map_workflow_component_type(self, workflow_type: str) -> ComponentType:
        """Map workflow component types to report component types"""
        type_mapping = {
            "question": ComponentType.QUESTION,
            "description": ComponentType.DESCRIPTION,
            "overview": ComponentType.OVERVIEW,
            "chart": ComponentType.CHART,
            "table": ComponentType.TABLE,
            "metric": ComponentType.METRIC,
            "insight": ComponentType.INSIGHT,
            "narrative": ComponentType.NARRATIVE,
            "alert": ComponentType.ALERT
        }
        
        return type_mapping.get(workflow_type.lower(), ComponentType.QUESTION)
    
    def _determine_writer_actor_from_workflow(self, workflow_info: Dict[str, Any]) -> WriterActorType:
        """Determine writer actor from workflow metadata"""
        try:
            metadata = workflow_info.get("workflow_metadata", {})
            
            # Check for explicit writer actor configuration
            if "writer_actor" in metadata:
                actor_name = metadata["writer_actor"].upper()
                try:
                    return WriterActorType[actor_name]
                except KeyError:
                    logger.warning(f"Unknown writer actor: {actor_name}")
            
            # Determine from workflow state or type
            workflow_state = workflow_info.get("state", "").lower()
            if "executive" in workflow_state or "summary" in workflow_state:
                return WriterActorType.EXECUTIVE
            elif "performance" in workflow_state or "kpi" in workflow_state:
                return WriterActorType.ANALYST
            elif "trend" in workflow_state or "forecast" in workflow_state:
                return WriterActorType.DATA_SCIENTIST
            else:
                return WriterActorType.ANALYST
                
        except Exception as e:
            logger.error(f"Error determining writer actor from workflow: {e}")
            return WriterActorType.ANALYST
    
    def _determine_business_goal_from_workflow(self, workflow_info: Dict[str, Any]) -> BusinessGoal:
        """Determine business goal from workflow metadata"""
        try:
            metadata = workflow_info.get("workflow_metadata", {})
            
            # Check for explicit business goal configuration
            if "business_goal" in metadata:
                goal_config = metadata["business_goal"]
                if isinstance(goal_config, dict):
                    return BusinessGoal(**goal_config)
                else:
                    logger.warning(f"Business goal should be a dict, got: {type(goal_config)}")
            
            # Determine from workflow state or type
            workflow_state = workflow_info.get("state", "").lower()
            if "executive" in workflow_state or "summary" in workflow_state:
                return BusinessGoal(
                    primary_objective="Strategic decision making",
                    target_audience=["executives", "stakeholders"],
                    decision_context="High-level strategic planning",
                    success_metrics=["strategic alignment", "decision quality"],
                    timeframe="quarterly"
                )
            elif "performance" in workflow_state or "kpi" in workflow_state:
                return BusinessGoal(
                    primary_objective="Performance optimization",
                    target_audience=["performance team", "management"],
                    decision_context="Performance improvement decisions",
                    success_metrics=["performance metrics", "optimization results"],
                    timeframe="monthly"
                )
            elif "trend" in workflow_state or "forecast" in workflow_state:
                return BusinessGoal(
                    primary_objective="Trend analysis",
                    target_audience=["data scientists", "analysts"],
                    decision_context="Trend-based strategic decisions",
                    success_metrics=["trend accuracy", "prediction quality"],
                    timeframe="quarterly"
                )
            else:
                return BusinessGoal(
                    primary_objective="Operational insights",
                    target_audience=["operations team", "managers"],
                    decision_context="Day-to-day operational decisions",
                    success_metrics=["efficiency", "productivity"],
                    timeframe="weekly"
                )
                
        except Exception as e:
            logger.error(f"Error determining business goal from workflow: {e}")
            return BusinessGoal(
                primary_objective="Operational insights",
                target_audience=["operations team", "managers"],
                decision_context="Day-to-day operational decisions",
                success_metrics=["efficiency", "productivity"],
                timeframe="weekly"
            )
    
    
    async def generate_comprehensive_report(
        self,
        report_queries: List[Dict[str, Any]],
        project_id: str,
        report_context: Dict[str, Any],
        natural_language_query: Optional[str] = None,
        report_template: Optional[str] = None,
        custom_components: Optional[List[ThreadComponentData]] = None,
        writer_actor: Optional[WriterActorType] = None,
        business_goal: Optional[BusinessGoal] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive report using the ReportOrchestratorPipeline
        
        Args:
            report_queries: List of SQL queries for report data
            project_id: Project identifier
            report_context: Context about report structure and requirements
            natural_language_query: Natural language query for conditional formatting (optional)
            report_template: Predefined report template to use (optional)
            custom_components: Custom thread components for report generation (optional)
            writer_actor: Writer actor type for report generation (optional)
            business_goal: Business goal configuration (optional)
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            
        Returns:
            Dictionary containing complete report results
        """
        try:
            if not self._report_orchestrator:
                raise RuntimeError("Report Orchestrator Pipeline is not available")
            
            # Determine thread components, writer actor, and business goal
            thread_components, writer_actor, business_goal = self._resolve_report_configuration(
                report_template, custom_components, writer_actor, business_goal
            )
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "report_generation_started",
                {
                    "project_id": project_id,
                    "total_queries": len(report_queries),
                    "report_template": report_template,
                    "has_conditional_formatting": bool(natural_language_query),
                    "writer_actor": str(writer_actor) if writer_actor else None,
                    "business_goal": str(business_goal) if business_goal else None
                }
            )
            
            # Execute the report orchestrator pipeline
            result = await self._report_orchestrator.run(
                report_queries=report_queries,
                natural_language_query=natural_language_query,
                report_context=report_context,
                project_id=project_id,
                thread_components=thread_components,
                writer_actor=writer_actor,
                business_goal=business_goal,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=self._create_nested_status_callback(status_callback, "report_orchestrator"),
                configuration=configuration
            )
            
            # Store execution history
            self._store_execution_history(
                project_id=project_id,
                report_template=report_template,
                total_queries=len(report_queries),
                result=result,
                writer_actor=writer_actor,
                business_goal=business_goal
            )
            
            # Add chart schema information to response metadata if available
            self._add_chart_schemas_to_response(result)
            
            # Add global executive summary to result
            if result:
                result = self._add_global_executive_summary_to_result(result, report_context)
            else:
                logger.warning("No result found to add global executive summary")
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "report_generation_completed",
                {
                    "project_id": project_id,
                    "success": result.get("post_process", {}).get("success", False),
                    "conditional_formatting_applied": result.get("post_process", {}).get("orchestration_metadata", {}).get("conditional_formatting_applied", False),
                    "comprehensive_report_generated": result.get("post_process", {}).get("orchestration_metadata", {}).get("comprehensive_report_generated", False)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive report generation: {e}")
            self._send_status_update(
                status_callback,
                "report_generation_failed",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            raise
    
    async def generate_simple_report(
        self,
        report_queries: List[Dict[str, Any]],
        project_id: str,
        report_context: Dict[str, Any],
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Generate a simple report without comprehensive components using agent pipelines
        
        Args:
            report_queries: List of SQL queries for report data
            project_id: Project identifier
            report_context: Context about report structure and requirements
            natural_language_query: Natural language query for conditional formatting (optional)
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback function for status updates
            
        Returns:
            Dictionary containing simple report results
        """
        try:
            if not self._agent_pipelines["simple_report"]:
                raise RuntimeError("Simple Report Generation Pipeline is not available")
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "simple_report_generation_started",
                {
                    "project_id": project_id,
                    "total_queries": len(report_queries)
                }
            )
            
            # Execute simple report generation using agent pipeline
            result = await self._agent_pipelines["simple_report"].run(
                report_queries=report_queries,
                enhanced_context=report_context,
                project_id=project_id,
                status_callback=self._create_nested_status_callback(status_callback, "simple_report")
            )
            
            # Store execution history
            self._store_execution_history(
                project_id=project_id,
                report_template="simple",
                total_queries=len(report_queries),
                result=result
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "simple_report_generation_completed",
                {
                    "project_id": project_id,
                    "success": result.get("post_process", {}).get("success", False)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in simple report generation: {e}")
            self._send_status_update(
                status_callback,
                "simple_report_generation_failed",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            raise
    
    async def generate_conditional_formatting_only(
        self,
        natural_language_query: str,
        report_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Generate only conditional formatting without executing report queries using agent pipelines
        
        Args:
            natural_language_query: Natural language query for conditional formatting
            report_context: Context about report structure and requirements
            project_id: Project identifier
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback function for status updates
            
        Returns:
            Dictionary containing conditional formatting configuration
        """
        try:
            if not self._agent_pipelines["conditional_formatting"]:
                raise RuntimeError("Conditional Formatting Generation Pipeline is not available")
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "conditional_formatting_generation_started",
                {
                    "project_id": project_id,
                    "query": natural_language_query
                }
            )
            
            # Execute conditional formatting generation using agent pipeline
            result = await self._agent_pipelines["conditional_formatting"].run(
                natural_language_query=natural_language_query,
                dashboard_context=report_context,  # Reuse dashboard context structure
                project_id=project_id,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=self._create_nested_status_callback(status_callback, "conditional_formatting")
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "conditional_formatting_generation_completed",
                {
                    "project_id": project_id,
                    "success": result.get("post_process", {}).get("success", False)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in conditional formatting generation: {e}")
            self._send_status_update(
                status_callback,
                "conditional_formatting_generation_failed",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            raise
    
    def _resolve_report_configuration(
        self,
        report_template: Optional[str],
        custom_components: Optional[List[ThreadComponentData]],
        writer_actor: Optional[WriterActorType],
        business_goal: Optional[BusinessGoal]
    ) -> tuple[List[ThreadComponentData], WriterActorType, BusinessGoal]:
        """Resolve report configuration from template or custom settings"""
        
        # If custom components are provided, use them
        if custom_components:
            thread_components = custom_components
        elif report_template and report_template in self._report_templates:
            # Use predefined template
            template = self._report_templates[report_template]
            thread_components = self._create_components_from_template(template["components"])
            writer_actor = writer_actor or template["writer_actor"]
            business_goal = business_goal or template["business_goal"]
        else:
            # Use default configuration
            thread_components = self._create_default_components()
            writer_actor = writer_actor or WriterActorType.ANALYST
            business_goal = business_goal or BusinessGoal(
                primary_objective="Operational insights",
                target_audience=["operations team", "managers"],
                decision_context="Day-to-day operational decisions",
                success_metrics=["efficiency", "productivity"],
                timeframe="weekly"
            )
        
        return thread_components, writer_actor, business_goal
    
    def _create_components_from_template(self, component_names: List[str]) -> List[ThreadComponentData]:
        """Create thread components from template component names"""
        components = []
        
        for component_name in component_names:
            component = ThreadComponentData(
                id=f"component_{component_name}",
                component_type=ComponentType.QUESTION,
                sequence_order=0,
                question=component_name.replace("_", " ").title(),
                description=f"Generate {component_name.replace('_', ' ')} content"
            )
            components.append(component)
        
        return components
    
    def _create_default_components(self) -> List[ThreadComponentData]:
        """Create default thread components"""
        return [
            ThreadComponentData(
                id="component_executive_summary",
                component_type=ComponentType.OVERVIEW,
                sequence_order=0,
                question="Executive Summary",
                description="Generate executive summary content"
            ),
            ThreadComponentData(
                id="component_key_findings",
                component_type=ComponentType.INSIGHT,
                sequence_order=1,
                question="Key Findings",
                description="Generate key findings content"
            ),
            ThreadComponentData(
                id="component_recommendations",
                component_type=ComponentType.NARRATIVE,
                sequence_order=2,
                question="Recommendations",
                description="Generate recommendations content"
            )
        ]
    
    def get_available_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get available report templates"""
        return self._report_templates.copy()
    
    def add_custom_template(
        self,
        template_name: str,
        template_config: Dict[str, Any]
    ) -> bool:
        """Add a custom report template"""
        try:
            required_fields = ["name", "description", "components", "writer_actor", "business_goal"]
            for field in required_fields:
                if field not in template_config:
                    logger.error(f"Missing required field '{field}' in template config")
                    return False
            
            self._report_templates[template_name] = template_config.copy()
            logger.info(f"Custom template '{template_name}' added successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error adding custom template: {e}")
            return False
    
    def remove_template(self, template_name: str) -> bool:
        """Remove a report template"""
        try:
            if template_name in self._report_templates:
                del self._report_templates[template_name]
                logger.info(f"Template '{template_name}' removed successfully")
                return True
            else:
                logger.warning(f"Template '{template_name}' not found")
                return False
                
        except Exception as e:
            logger.error(f"Error removing template: {e}")
            return False
    
    def validate_report_configuration(
        self,
        report_queries: List[Dict[str, Any]],
        report_context: Dict[str, Any],
        natural_language_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate report configuration and queries"""
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        try:
            # Validate report queries
            for i, query_data in enumerate(report_queries):
                query_validation = self._validate_single_query(query_data, i)
                if not query_validation["valid"]:
                    validation_result["valid"] = False
                    validation_result["issues"].extend(query_validation["issues"])
                
                if query_validation["warnings"]:
                    validation_result["warnings"].extend(query_validation["warnings"])
                
                if query_validation["recommendations"]:
                    validation_result["recommendations"].extend(query_validation["recommendations"])
            
            # Validate report context
            context_validation = self._validate_report_context(report_context)
            if not context_validation["valid"]:
                validation_result["valid"] = False
                validation_result["issues"].extend(context_validation["issues"])
            
            # Validate natural language query if provided
            if natural_language_query:
                query_validation = self._validate_natural_language_query(natural_language_query)
                if not query_validation["valid"]:
                    validation_result["valid"] = False
                    validation_result["issues"].extend(query_validation["issues"])
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error in report configuration validation: {e}")
            validation_result["valid"] = False
            validation_result["issues"].append(f"Validation error: {str(e)}")
            return validation_result
    
    def _validate_single_query(self, query_data: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Validate a single report query"""
        validation = {"valid": True, "issues": [], "warnings": [], "recommendations": []}
        
        # Check required fields
        required_fields = ["sql", "query"]
        for field in required_fields:
            if field not in query_data or not query_data[field]:
                validation["valid"] = False
                validation["issues"].append(f"Query {index}: Missing required field '{field}'")
        
        # Check SQL syntax (basic validation)
        if "sql" in query_data and query_data["sql"]:
            sql = query_data["sql"].strip()
            if not sql.endswith(";"):
                validation["warnings"].append(f"Query {index}: SQL should end with semicolon")
            
            if "select" not in sql.lower():
                validation["valid"] = False
                validation["issues"].append(f"Query {index}: SQL must contain SELECT statement")
        
        return validation
    
    def _validate_report_context(self, report_context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate report context structure"""
        validation = {"valid": True, "issues": [], "warnings": [], "recommendations": []}
        
        # Check required fields
        if "title" not in report_context:
            validation["warnings"].append("Missing 'title' field in report context")
        
        if "description" not in report_context:
            validation["warnings"].append("Missing 'description' field in report context")
        
        # Validate structure
        if "sections" in report_context:
            sections = report_context["sections"]
            if not isinstance(sections, list):
                validation["valid"] = False
                validation["issues"].append("'sections' field must be a list")
        
        return validation
    
    def _validate_natural_language_query(self, query: str) -> Dict[str, Any]:
        """Validate natural language query"""
        validation = {"valid": True, "issues": [], "warnings": [], "recommendations": []}
        
        if not query or not query.strip():
            validation["valid"] = False
            validation["issues"].append("Natural language query cannot be empty")
        
        if len(query.strip()) < 10:
            validation["warnings"].append("Natural language query seems too short, consider providing more detail")
        
        return validation
    
    def _create_nested_status_callback(
        self,
        parent_callback: Optional[Callable[[str, Dict[str, Any]], None]],
        prefix: str
    ) -> Callable[[str, Dict[str, Any]], None]:
        """Create a nested status callback with prefix"""
        def nested_callback(status: str, details: Dict[str, Any] = None):
            if parent_callback:
                try:
                    parent_callback(f"{prefix}_{status}", details or {})
                except Exception as e:
                    logger.error(f"Error in nested status callback: {e}")
        
        return nested_callback
    
    async def _refresh_sql_queries(
        self,
        report_queries: List[Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Refresh SQL queries with current date/time parameters
        
        Args:
            report_queries: List of report query dictionaries
            project_id: Project identifier
            status_callback: Optional callback for status updates
            
        Returns:
            List of refreshed report queries
        """
        if not self._agent_pipelines.get("sql_refresh"):
            logger.warning("SQL refresh pipeline not available, skipping query refresh")
            return report_queries
        
        refreshed_queries = []
        
        try:
            self._send_status_update(
                status_callback,
                "sql_refresh_started",
                {
                    "project_id": project_id,
                    "total_queries": len(report_queries)
                }
            )
            
            for i, query_data in enumerate(report_queries):
                sql = query_data.get("sql", "")
                original_question = query_data.get("query", "")
                existing_reasoning = query_data.get("reasoning", "")
                
                if not sql or not sql.strip():
                    logger.warning(f"Query {i} has no SQL, skipping refresh")
                    refreshed_queries.append(query_data)
                    continue
                
                try:
                    # Refresh the SQL query with existing reasoning
                    refresh_result = await self._agent_pipelines["sql_refresh"].run(
                        sql_query=sql,
                        original_question=original_question,
                        project_id=project_id,
                        existing_reasoning=existing_reasoning,
                        status_callback=self._create_nested_status_callback(
                            status_callback, f"sql_refresh_query_{i}"
                        )
                    )
                    
                    if refresh_result.get("success") and refresh_result.get("refreshed_sql"):
                        # Update the query with refreshed SQL
                        updated_query = query_data.copy()
                        updated_query["sql"] = refresh_result["refreshed_sql"]
                        updated_query["original_sql"] = sql  # Keep original for reference
                        updated_query["refresh_metadata"] = refresh_result.get("metadata", {})
                        refreshed_queries.append(updated_query)
                        logger.info(f"Refreshed SQL query {i} successfully")
                    else:
                        logger.warning(f"SQL refresh failed for query {i}, using original")
                        refreshed_queries.append(query_data)
                        
                except Exception as e:
                    logger.error(f"Error refreshing SQL query {i}: {e}")
                    # Use original query on error
                    refreshed_queries.append(query_data)
            
            self._send_status_update(
                status_callback,
                "sql_refresh_completed",
                {
                    "project_id": project_id,
                    "total_queries": len(report_queries),
                    "refreshed_queries": len([q for q in refreshed_queries if "refresh_metadata" in q])
                }
            )
            
            return refreshed_queries
            
        except Exception as e:
            logger.error(f"Error in SQL refresh process: {e}")
            self._send_status_update(
                status_callback,
                "sql_refresh_failed",
                {
                    "project_id": project_id,
                    "error": str(e)
                }
            )
            # Return original queries on error
            return report_queries
    
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
        logger.info(f"Report Service - {status}: {details}")
    
    def _store_execution_history(
        self,
        project_id: str,
        report_template: Optional[str],
        total_queries: int,
        result: Dict[str, Any],
        writer_actor: Optional[WriterActorType] = None,
        business_goal: Optional[BusinessGoal] = None
    ):
        """Store execution history for analytics"""
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "project_id": project_id,
            "report_template": report_template,
            "total_queries": total_queries,
            "success": result.get("post_process", {}).get("success", False),
            "writer_actor": str(writer_actor) if writer_actor else None,
            "business_goal": str(business_goal) if business_goal else None,
            "conditional_formatting_applied": result.get("post_process", {}).get("orchestration_metadata", {}).get("conditional_formatting_applied", False),
            "comprehensive_report_generated": result.get("post_process", {}).get("orchestration_metadata", {}).get("comprehensive_report_generated", False)
        }
        
        self._execution_history.append(history_entry)
        
        # Keep only last 100 entries
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]
    
    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent execution history"""
        return self._execution_history[-limit:] if self._execution_history else []
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all report agent pipelines"""
        return {
            "report_orchestrator": {
                "available": self._report_orchestrator is not None,
                "initialized": self._report_orchestrator.is_initialized if self._report_orchestrator else False
            },
            "report_writing_agent": {
                "available": self._report_writing_agent is not None,
                "initialized": True
            },
            "conditional_formatting": {
                "available": self._agent_pipelines.get("conditional_formatting") is not None,
                "initialized": True
            },
            "simple_report": {
                "available": self._agent_pipelines.get("simple_report") is not None,
                "initialized": True
            },
            "pipeline_container": {
                "available": self.pipeline_container is not None,
                "pipeline_count": len(self.pipeline_container._pipelines) if self.pipeline_container else 0
            },
            "report_templates": {
                "total_templates": len(self._report_templates),
                "available_templates": list(self._report_templates.keys())
            },
            "execution_history": {
                "total_entries": len(self._execution_history),
                "recent_entries": len(self._execution_history[-10:]) if self._execution_history else 0
            }
        }
    
    async def render_report_from_workflow_db(
        self,
        workflow_id: str,
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        render_options: Optional[Dict[str, Any]] = None,
        report_template: Optional[str] = None,
        writer_actor: Optional[str] = None,
        business_goal: Optional[str] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Render report from workflow database model
        
        Args:
            workflow_id: Workflow ID from database
            project_id: Project identifier
            natural_language_query: Natural language query for conditional formatting
            additional_context: Additional context for rendering
            time_filters: Time-based filters
            render_options: Options for rendering (preview, full, etc.)
            report_template: Report template to use
            writer_actor: Writer actor type
            business_goal: Business goal configuration
            status_callback: Callback for status updates
            
        Returns:
            Complete report result with workflow-driven configuration
        """
        try:
            # Use workflow integration service to render report
            workflow_result = await self._workflow_integration.render_dashboard_from_workflow(
                workflow_id=workflow_id,
                project_id=project_id,
                natural_language_query=natural_language_query,
                additional_context=additional_context,
                time_filters=time_filters,
                render_options=render_options
            )
            
            if not workflow_result.get("success"):
                raise ValueError(workflow_result.get("error", f"Failed to render workflow {workflow_id}"))
            
            # Extract data from workflow result
            report_queries = workflow_result["dashboard_queries"]  # Reuse dashboard queries structure
            report_context = workflow_result["dashboard_context"]  # Reuse dashboard context structure
            
            # Convert dashboard context to report context
            report_context = self._convert_dashboard_to_report_context(report_context)
            
            # Determine writer actor and business goal
            writer_actor_type = self._parse_writer_actor(writer_actor)
            business_goal_obj = self._parse_business_goal(business_goal)
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "workflow_report_rendering_started",
                {
                    "workflow_id": workflow_id,
                    "project_id": project_id,
                    "total_queries": len(report_queries),
                    "workflow_state": workflow_result.get("workflow_metadata", {}).get("state"),
                    "render_mode": render_options.get("mode", "full") if render_options else "full",
                    "report_template": report_template,
                    "writer_actor": str(writer_actor_type) if writer_actor_type else None
                }
            )
            
            # Generate comprehensive report
            result = await self.generate_comprehensive_report(
                report_queries=report_queries,
                project_id=project_id,
                report_context=report_context,
                natural_language_query=natural_language_query,
                report_template=report_template,
                writer_actor=writer_actor_type,
                business_goal=business_goal_obj,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=status_callback
            )
            
            # Add workflow metadata to result
            result["workflow_metadata"] = {
                "workflow_id": workflow_id,
                "workflow_state": workflow_result.get("workflow_metadata", {}).get("state"),
                "workflow_type": "report_workflow",
                "report_template": report_template,
                "workflow_source": "database",
                "render_options": render_options or {},
                "transformed_at": workflow_result.get("transformed_at")
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error rendering report from workflow DB: {e}")
            self._send_status_update(
                status_callback,
                "workflow_report_rendering_failed",
                {
                    "error": str(e),
                    "workflow_id": workflow_id,
                    "project_id": project_id
                }
            )
            raise
    
    def _convert_dashboard_to_report_context(self, dashboard_context: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dashboard context to report context format"""
        try:
            return {
                "title": dashboard_context.get("title", "Report from Workflow"),
                "description": dashboard_context.get("description", "Report generated from workflow configuration"),
                "sections": ["executive_summary", "analysis", "conclusions", "recommendations"],
                "available_columns": dashboard_context.get("available_columns", []),
                "data_types": dashboard_context.get("data_types", {}),
                "workflow_id": dashboard_context.get("workflow_id"),
                "workflow_state": dashboard_context.get("workflow_state"),
                "workflow_metadata": dashboard_context.get("workflow_metadata", {}),
                "template": dashboard_context.get("template"),
                "layout": dashboard_context.get("layout"),
                "charts": dashboard_context.get("charts", []),
                "components": dashboard_context.get("components", [])
            }
        except Exception as e:
            logger.error(f"Error converting dashboard to report context: {e}")
            return {
                "title": "Report from Workflow",
                "description": "Report generated from workflow configuration",
                "sections": ["executive_summary", "analysis", "conclusions"],
                "available_columns": [],
                "data_types": {},
                "workflow_id": dashboard_context.get("workflow_id", "unknown")
            }
    
    def _parse_writer_actor(self, writer_actor: Optional[Union[str, Dict[str, Any]]]) -> Optional[WriterActorType]:
        """Parse writer actor string or dict to WriterActorType enum"""
        if not writer_actor:
            return None
        
        try:
            # Handle dict input
            if isinstance(writer_actor, dict):
                # Extract the actual actor type from the dict
                actor_value = writer_actor.get("actor_type") or writer_actor.get("type") or str(writer_actor)
                if actor_value and actor_value != "string":
                    return WriterActorType[actor_value.upper()]
                else:
                    logger.warning(f"Invalid writer actor dict: {writer_actor}")
                    return None
            
            # Handle string input
            if isinstance(writer_actor, str) and writer_actor != "string":
                return WriterActorType[writer_actor.upper()]
            
            logger.warning(f"Invalid writer actor: {writer_actor}")
            return None
            
        except KeyError:
            logger.warning(f"Unknown writer actor: {writer_actor}")
            return None
    
    def _parse_business_goal(self, business_goal: Optional[Union[str, Dict[str, Any]]]) -> Optional[BusinessGoal]:
        """Parse business goal string or dict to BusinessGoal object"""
        if not business_goal:
            return None
        
        try:
            # Handle dict input
            if isinstance(business_goal, dict):
                # Check if it's a valid business goal dict
                if "primary_objective" in business_goal or "goal_name" in business_goal:
                    # Map the dict fields to BusinessGoal fields
                    goal_data = {
                        "primary_objective": business_goal.get("primary_objective") or business_goal.get("objective") or business_goal.get("goal_name", "Operational insights"),
                        "target_audience": business_goal.get("target_audience") or ["operations team", "managers"],
                        "decision_context": business_goal.get("decision_context") or "Day-to-day operational decisions",
                        "success_metrics": business_goal.get("success_metrics") or business_goal.get("metrics") or ["efficiency", "productivity"],
                        "timeframe": business_goal.get("timeframe") or "weekly"
                    }
                    return BusinessGoal(**goal_data)
                else:
                    logger.warning(f"Invalid business goal dict structure: {business_goal}")
                    return None
            
            # Handle string input
            if isinstance(business_goal, str):
                # If it's a JSON string, parse it
                if business_goal.startswith("{"):
                    import json
                    goal_dict = json.loads(business_goal)
                    return self._parse_business_goal(goal_dict)
                else:
                    # Simple string mapping
                    goal_mapping = {
                        "strategic": BusinessGoal(
                            primary_objective="Strategic decision making",
                            target_audience=["executives", "stakeholders"],
                            decision_context="High-level strategic planning",
                            success_metrics=["strategic alignment", "decision quality"],
                            timeframe="quarterly"
                        ),
                        "operational": BusinessGoal(
                            primary_objective="Operational insights",
                            target_audience=["operations team", "managers"],
                            decision_context="Day-to-day operational decisions",
                            success_metrics=["efficiency", "productivity"],
                            timeframe="weekly"
                        ),
                        "performance": BusinessGoal(
                            primary_objective="Performance optimization",
                            target_audience=["performance team", "management"],
                            decision_context="Performance improvement decisions",
                            success_metrics=["performance metrics", "optimization results"],
                            timeframe="monthly"
                        )
                    }
                    return goal_mapping.get(business_goal.lower())
            
            logger.warning(f"Invalid business goal type: {type(business_goal)}")
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing business goal: {e}")
            return None
    
    async def get_workflow_components(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get workflow components for a specific workflow"""
        try:
            # Use workflow integration service to get components
            components = await self._workflow_integration.fetch_workflow_components(workflow_id)
            
            # Format components for API response
            formatted_components = []
            for comp in components:
                formatted_comp = {
                    "component_id": comp.get("id"),
                    "component_type": comp.get("component_type"),
                    "question": comp.get("question"),
                    "description": comp.get("description"),
                    "sequence_order": comp.get("sequence_order"),
                    "configuration": comp.get("configuration", {}),
                    "chart_config": comp.get("chart_config", {}),
                    "table_config": comp.get("table_config", {}),
                    "alert_config": comp.get("alert_config", {}),
                    "sql": comp.get("sql", ""),
                    "query": comp.get("query", ""),
                    "data_description": comp.get("data_description", "")
                }
                formatted_components.append(formatted_comp)
            
            return formatted_components
            
        except Exception as e:
            logger.error(f"Error getting workflow components: {e}")
            return []
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status and metadata"""
        try:
            # Use workflow integration service to get status
            status = await self._workflow_integration.get_workflow_status(workflow_id)
            return status
            
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": str(e)
            }
    
    async def preview_report_from_workflow(
        self,
        workflow_id: str,
        preview_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Preview report from workflow without full rendering"""
        try:
            # Use workflow integration service to render report
            workflow_result = await self._workflow_integration.render_dashboard_from_workflow(
                workflow_id=workflow_id,
                project_id="preview_project",
                natural_language_query=None,
                additional_context={"preview_mode": True},
                time_filters={},
                render_options=preview_options or {}
            )
            
            if not workflow_result.get("success"):
                raise ValueError(workflow_result.get("error", f"Failed to preview workflow {workflow_id}"))
            
            # Extract data from workflow result
            report_queries = workflow_result["dashboard_queries"]
            report_context = workflow_result["dashboard_context"]
            
            # Convert dashboard context to report context
            report_context = self._convert_dashboard_to_report_context(report_context)
            
            # Limit queries for preview
            max_preview_queries = preview_options.get("max_queries", 2) if preview_options else 2
            report_queries = report_queries[:max_preview_queries]
            
            # Generate simple report for preview
            result = await self.generate_simple_report(
                report_queries=report_queries,
                project_id="preview_project",
                report_context=report_context
            )
            
            # Add preview metadata
            result["preview_metadata"] = {
                "workflow_id": workflow_id,
                "preview_mode": True,
                "total_queries_previewed": len(report_queries),
                "preview_options": preview_options or {}
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error previewing report from workflow: {e}")
            raise
    
    async def render_report_from_workflow_data(
        self,
        workflow_data: Dict[str, Any],
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        render_options: Optional[Dict[str, Any]] = None,
        report_template: Optional[str] = None,
        writer_actor: Optional[str] = None,
        business_goal: Optional[str] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Render report from workflow data passed in request
        
        Args:
            workflow_data: Complete workflow data from request
            project_id: Project identifier
            natural_language_query: Natural language query for conditional formatting
            additional_context: Additional context for rendering
            time_filters: Time-based filters
            render_options: Options for rendering (preview, full, etc.)
            report_template: Report template to use
            writer_actor: Writer actor type
            business_goal: Business goal configuration
            status_callback: Callback for status updates
            
        Returns:
            Complete report result with workflow-driven configuration
        """
        try:
            # Extract workflow information
            workflow_id = workflow_data.get("workflow_id")
            workflow_state = workflow_data.get("state")
            thread_components = workflow_data.get("thread_components", [])
            workflow_metadata = workflow_data.get("workflow_metadata", {})
            
            # Debug: Log the workflow data structure
            logger.info(f"Workflow data keys: {list(workflow_data.keys())}")
            logger.info(f"Thread components count: {len(thread_components)}")
            if thread_components:
                logger.info(f"First component keys: {list(thread_components[0].keys()) if thread_components else 'None'}")
            
            # Handle case where workflow data might have a different structure
            # Check for final_result in various locations
            final_result = None
            if "final_result" in workflow_data:
                final_result = workflow_data["final_result"]
                logger.info("Found final_result at top level")
            elif "report_data" in workflow_data and "report_results" in workflow_data["report_data"]:
                report_results = workflow_data["report_data"]["report_results"]
                if "final_result" in report_results:
                    final_result = report_results["final_result"]
                    logger.info("Found final_result in report_data.report_results")
            
            # Check if we have data summarization pipeline output with chart data
            has_chart_data = False
            if final_result:
                chart_schema = final_result.get('post_process', {}).get('visualization', {}).get('chart_schema')
                has_chart_data = bool(chart_schema)
                logger.info(f"Final result contains chart data: {has_chart_data}")
            
            if final_result and has_chart_data:
                # This is data summarization pipeline output with chart data - prioritize it
                logger.info("Detected data summarization pipeline output with chart data - creating dynamic components")
                
                # Dynamically extract information from final_result
                thread_components = self._create_dynamic_components_from_final_result(final_result)
                logger.info(f"Created {len(thread_components)} dynamic components from final_result")
                for i, comp in enumerate(thread_components):
                    logger.info(f"Dynamic component {i}: id={comp.id}, type={comp.component_type}, "
                              f"has_chart_config={bool(comp.chart_config)}, has_final_result={bool(comp.final_result)}")
            elif not thread_components and final_result:
                # Fallback: no thread_components but we have final_result
                logger.info("No thread components found, creating from final_result")
                thread_components = self._create_dynamic_components_from_final_result(final_result)
            
            # Transform workflow data to report format
            report_queries = self._extract_queries_from_workflow_components(thread_components)
            
            # Refresh SQL queries with current date/time
            report_queries = await self._refresh_sql_queries(
                report_queries=report_queries,
                project_id=project_id,
                status_callback=status_callback
            )
            
            report_context = self._create_report_context_from_workflow_data(workflow_data)
            
            # Determine writer actor and business goal
            writer_actor_type = self._parse_writer_actor(writer_actor or workflow_metadata.get("writer_actor"))
            business_goal_obj = self._parse_business_goal(business_goal or workflow_metadata.get("business_goal"))
            
            # Convert dictionary thread components to ThreadComponentData objects
            converted_thread_components = []
            for i, comp in enumerate(thread_components):
                if isinstance(comp, dict):
                    # Convert dictionary to ThreadComponentData
                    thread_component = ThreadComponentData(
                        id=comp.get("id", f"component_{i}"),
                        component_type=self._map_workflow_component_type(comp.get("component_type", "question")),
                        sequence_order=comp.get("sequence_order", i),
                        question=comp.get("question", f"Component {i}"),
                        description=comp.get("description", ""),
                        overview=comp.get("overview"),
                        chart_config=comp.get("chart_config"),
                        table_config=comp.get("table_config"),
                        configuration=comp.get("configuration", {}),
                        final_result=comp.get("final_result"),
                        metadata=comp.get("metadata", {})  # Preserve metadata
                    )
                    converted_thread_components.append(thread_component)
                else:
                    # Already a ThreadComponentData object
                    converted_thread_components.append(comp)
            
            thread_components = converted_thread_components
            
            # Debug logging
            logger.info(f"Writer actor type: {writer_actor_type}")
            logger.info(f"Business goal object: {business_goal_obj}")
            logger.info(f"Thread components count: {len(thread_components)}")
            for i, comp in enumerate(thread_components):
                logger.info(f"Thread component {i}: id={comp.id}, type={comp.component_type}, has_chart_config={bool(comp.chart_config)}")
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "workflow_report_rendering_started",
                {
                    "workflow_id": workflow_id,
                    "project_id": project_id,
                    "total_queries": len(report_queries),
                    "workflow_state": workflow_state,
                    "render_mode": render_options.get("mode", "full") if render_options else "full",
                    "total_components": len(thread_components),
                    "report_template": report_template,
                    "writer_actor": str(writer_actor_type) if writer_actor_type else None
                }
            )
            
            # Generate comprehensive report
            result = await self.generate_comprehensive_report(
                report_queries=report_queries,
                project_id=project_id,
                report_context=report_context,
                natural_language_query=natural_language_query,
                report_template=report_template,
                custom_components=thread_components,  # Pass the thread components created from final_result
                writer_actor=writer_actor_type,
                business_goal=business_goal_obj,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=status_callback
            )
            
            # Add workflow metadata to result
            result["workflow_metadata"] = {
                "workflow_id": workflow_id,
                "workflow_state": workflow_state,
                "workflow_type": "report_workflow",
                "workflow_source": "request_data",
                "total_components": len(thread_components),
                "report_template": report_template,
                "writer_actor": str(writer_actor_type) if writer_actor_type else None,
                "business_goal": str(business_goal_obj) if business_goal_obj else None,
                "dashboard_template": workflow_metadata.get("dashboard_template"),
                "dashboard_layout": workflow_metadata.get("dashboard_layout"),
                "refresh_rate": workflow_metadata.get("refresh_rate")
            }
            
            # Add chart schema information to response metadata if available
            self._add_chart_schemas_to_response(result)
            
            # Format the result similar to dashboard structure but for reports (point-in-time)
            formatted_result = self._format_report_output_like_dashboard(result, workflow_data, thread_components, project_id)
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error rendering report from workflow data: {e}")
            self._send_status_update(
                status_callback,
                "workflow_report_rendering_failed",
                {
                    "error": str(e),
                    "workflow_id": workflow_data.get("workflow_id"),
                    "project_id": project_id
                }
            )
            raise
    
    def _extract_queries_from_workflow_components(self, thread_components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract report queries from workflow thread components"""
        queries = []
        
        try:
            logger.info(f"Processing {len(thread_components)} thread components for report extraction")
            for i, component in enumerate(thread_components):
                component_type = component.get("component_type", "").lower()
                has_sql_query = bool(component.get("sql_query"))
                has_final_result = bool(component.get("final_result"))
                
                logger.info(f"Component {i}: type='{component_type}', has_sql_query={has_sql_query}, has_final_result={has_final_result}")
                
                # Handle data summarization pipeline output format
                if has_final_result and component.get("final_result"):
                    final_result = component.get("final_result", {})
                    logger.info(f"Processing component {i} as data summarization result")
                    
                    # Extract data from final_result structure
                    post_process = final_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    
                    query_data = {
                        "chart_schema": chart_schema,
                        "sql": component.get("sql_query", ""),  # May be empty for data summarization
                        "query": component.get("question", "Data Analysis"),
                        "data_description": component.get("description", "Data analysis results"),
                        "component_type": component_type or "data_analysis",
                        "sequence_order": component.get("sequence_order", i),
                        "configuration": component.get("configuration", {}),
                        "chart_config": component.get("chart_config", {}),
                        "table_config": component.get("table_config", {}),
                        "alert_config": component.get("alert_config", {}),
                        "executive_summary": post_process.get("executive_summary", ""),
                        "data_overview": post_process.get("data_overview", {}),
                        "visualization_data": visualization,
                        "sample_data": component.get("sample_data", {}),
                        "thread_metadata": component.get("thread_metadata", {}),
                        "reasoning": component.get("reasoning"),
                        "data_count": component.get("data_count"),
                        "validation_results": component.get("validation_results", {}),
                        "final_result": final_result  # Include the full result for report generation
                    }
                    queries.append(query_data)
                    
                # Handle traditional SQL query components
                elif component.get("sql_query") and component_type in ["chart", "table", "metric", "sql_summary", "question"]:
                    logger.info(f"Processing component {i} as valid query component")
                    query_data = {
                        "chart_schema": component.get("chart_schema", {}),
                        "sql": component.get("sql_query", ""),
                        "query": component.get("question", ""),
                        "data_description": component.get("description", ""),
                        "component_type": component_type,
                        "sequence_order": component.get("sequence_order", 0),
                        "configuration": component.get("configuration", {}),
                        "chart_config": component.get("chart_config", {}),
                        "table_config": component.get("table_config", {}),
                        "alert_config": component.get("alert_config", {}),
                        "executive_summary": component.get("executive_summary"),
                        "data_overview": component.get("data_overview", {}),
                        "visualization_data": component.get("visualization_data", {}),
                        "sample_data": component.get("sample_data", {}),
                        "thread_metadata": component.get("thread_metadata", {}),
                        "reasoning": component.get("reasoning"),
                        "data_count": component.get("data_count"),
                        "validation_results": component.get("validation_results", {})
                    }
                    queries.append(query_data)
                else:
                    logger.info(f"Skipping component {i}: type='{component_type}', has_sql_query={has_sql_query}, has_final_result={has_final_result}")
            
            # Sort by sequence order
            queries.sort(key=lambda x: x.get("sequence_order", 0))
            
            logger.info(f"Extracted {len(queries)} report queries from workflow components")
            return queries
            
        except Exception as e:
            logger.error(f"Error extracting queries from workflow components: {e}")
            return []
    
    def _create_report_context_from_workflow_data(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create report context from workflow data"""
        try:
            workflow_metadata = workflow_data.get("workflow_metadata", {})
            thread_components = workflow_data.get("thread_components", [])
            
            # Handle case where workflow data might have a different structure
            if not thread_components and "final_result" in workflow_data:
                # This might be data summarization pipeline output
                logger.info("Creating report context from data summarization pipeline output")
                thread_components = [ThreadComponentData(
                    id="data_analysis_component",
                    component_type=ComponentType.CHART,
                    sequence_order=0,
                    question="Data Analysis",
                    description="Data analysis results",
                    final_result=workflow_data["final_result"]
                )]
            
            # Extract available columns from components
            available_columns = set()
            data_types = {}
            
            for component in thread_components:
                # Handle ThreadComponentData objects
                if hasattr(component, 'overview') and component.overview:
                    overview = component.overview
                    if "columns" in overview:
                        for col in overview["columns"]:
                            available_columns.add(col.get("name", ""))
                            data_types[col.get("name", "")] = col.get("type", "string")
                elif hasattr(component, 'final_result') and component.final_result:
                    # Extract columns from final_result structure
                    final_result = component.final_result
                    post_process = final_result.get("post_process", {})
                    data_overview = post_process.get("data_overview", {})
                    if "columns" in data_overview:
                        for col in data_overview["columns"]:
                            available_columns.add(col.get("name", ""))
                            data_types[col.get("name", "")] = col.get("type", "string")
                # Handle dict components (fallback)
                elif isinstance(component, dict):
                    if component.get("data_overview"):
                        overview = component["data_overview"]
                        if "columns" in overview:
                            for col in overview["columns"]:
                                available_columns.add(col.get("name", ""))
                                data_types[col.get("name", "")] = col.get("type", "string")
                    elif component.get("final_result"):
                        # Extract columns from final_result structure
                        final_result = component["final_result"]
                        post_process = final_result.get("post_process", {})
                        data_overview = post_process.get("data_overview", {})
                        if "columns" in data_overview:
                            for col in data_overview["columns"]:
                                available_columns.add(col.get("name", ""))
                                data_types[col.get("name", "")] = col.get("type", "string")
            
            # Create report context
            context = {
                "title": workflow_metadata.get("report_title", f"Report from Workflow {workflow_data.get('workflow_id')}"),
                "description": workflow_metadata.get("report_description", "Report generated from workflow configuration"),
                "sections": workflow_metadata.get("report_sections", ["executive_summary", "analysis", "conclusions", "recommendations"]),
                "available_columns": list(available_columns),
                "data_types": data_types,
                "workflow_id": workflow_data.get("workflow_id"),
                "workflow_state": workflow_data.get("state"),
                "workflow_metadata": workflow_metadata,
                "total_components": len(thread_components),
                "template": workflow_metadata.get("dashboard_template", "default"),
                "layout": workflow_metadata.get("dashboard_layout", "grid"),
                "refresh_rate": workflow_metadata.get("refresh_rate", 300),
                "charts": [comp for comp in thread_components if comp.get("component_type") in ["chart", "sql_summary"]],
                "tables": [comp for comp in thread_components if comp.get("component_type") == "table"],
                "metrics": [comp for comp in thread_components if comp.get("component_type") == "metric"],
                "alerts": [comp for comp in thread_components if comp.get("component_type") == "alert"]
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Error creating report context from workflow data: {e}")
            # Return basic context
            return {
                "title": "Report from Workflow",
                "description": "Report generated from workflow configuration",
                "sections": ["executive_summary", "analysis", "conclusions"],
                "available_columns": [],
                "data_types": {},
                "workflow_id": workflow_data.get("workflow_id", "unknown"),
                "workflow_state": workflow_data.get("state", "unknown"),
                "total_components": len(workflow_data.get("thread_components", []))
            }

    def _add_chart_schemas_to_response(self, result: Dict[str, Any]) -> None:
        """Add chart schema information to response metadata if available"""
        try:
            # Safely navigate the nested structure
            post_process = result.get("post_process", {})
            comprehensive_report = post_process.get("comprehensive_report")
            
            if not comprehensive_report:
                logger.info("No comprehensive report found in response")
                return
            
            report_outline = comprehensive_report.get("report_outline")
            if not report_outline:
                logger.info("No report outline found in comprehensive report")
                return
            
            sections = report_outline.get("sections", [])
            if not sections:
                logger.info("No sections found in report outline")
                return
            
            chart_schemas = []
            for section in sections:
                # Check both chart_schema and chart_data fields
                chart_schema = section.get("chart_schema") or section.get("chart_data")
                if chart_schema:
                    chart_schemas.append({
                        "section_title": section.get("title"),
                        "component_id": section.get("component_id"),
                        "component_type": section.get("component_type"),
                        "chart_schema": chart_schema,
                        "has_chart_data": bool(section.get("chart_data")),
                        "has_chart_schema": bool(section.get("chart_schema"))
                    })
            
            if chart_schemas:
                result["chart_schemas"] = chart_schemas
                logger.info(f"Added {len(chart_schemas)} chart schemas to response metadata")
                # Log details for debugging
                for chart_info in chart_schemas:
                    logger.info(f"Chart schema for section '{chart_info['section_title']}': "
                              f"has_chart_data={chart_info['has_chart_data']}, "
                              f"has_chart_schema={chart_info['has_chart_schema']}")
            else:
                logger.info("No chart schemas found in report sections")
                
        except Exception as e:
            logger.error(f"Error adding chart schemas to response: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _format_report_output_like_dashboard(
        self,
        result: Dict[str, Any],
        workflow_data: Dict[str, Any],
        thread_components: List[Any],
        project_id: str
    ) -> Dict[str, Any]:
        """
        Format report output similar to dashboard structure but for point-in-time reports
        
        Args:
            result: Original report result from orchestrator pipeline
            workflow_data: Workflow data from request
            thread_components: Thread components from workflow
            project_id: Project identifier
            
        Returns:
            Formatted report output similar to dashboard structure
        """
        try:
            # Extract report data from result
            post_process = result.get("post_process", {})
            report_results = post_process.get("report_results", {})
            enhanced_context = post_process.get("enhanced_context", {})
            report_summary = post_process.get("report_summary")
            orchestration_metadata = post_process.get("orchestration_metadata", {})
            
            # Generate report ID and metadata
            report_id = f"report_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            workflow_id = workflow_data.get("workflow_id", "")
            workflow_metadata = workflow_data.get("workflow_metadata", {})
            
            # Build formatted components similar to dashboard structure
            formatted_components = []
            component_positions = {}
            
            # Extract query results for components
            query_results = report_results.get("query_results", {})
            
            for i, component in enumerate(thread_components):
                # Handle both ThreadComponentData objects and dictionaries
                if hasattr(component, 'id'):
                    # ThreadComponentData object
                    component_id = getattr(component, 'id', f"component_{i}")
                    component_type = getattr(component, 'component_type', "question")
                    # Convert to dictionary for consistent processing
                    component_dict = {
                        "id": component_id,
                        "component_type": component_type,
                        "chart": getattr(component, 'chart_config', {}),
                        "table": getattr(component, 'table_config', {}),
                        "metadata": getattr(component, 'metadata', {}),
                        "overview": getattr(component, 'overview', {}),
                        "question": getattr(component, 'question', ""),
                        "sequence_order": getattr(component, 'sequence_order', i + 1),
                        "reasoning": getattr(component, 'reasoning', ""),
                        "sql_query": getattr(component, 'sql_query', ""),
                        "data_count": getattr(component, 'data_count', 0),
                        "description": getattr(component, 'description', ""),
                        "sample_data": getattr(component, 'sample_data', {}),
                        "chart_schema": getattr(component, 'chart_schema', {}),
                        "configuration": getattr(component, 'configuration', {}),
                        "data_overview": getattr(component, 'data_overview', {}),
                        "is_configured": getattr(component, 'is_configured', False),
                        "executive_summary": getattr(component, 'executive_summary', ""),
                        "validation_results": getattr(component, 'validation_results', {}),
                        "visualization_data": getattr(component, 'visualization_data', {})
                    }
                else:
                    # Dictionary
                    component_id = component.get("id", f"component_{i}")
                    component_type = component.get("component_type", "question")
                    component_dict = component
                
                # Find matching query result
                query_result = None
                for query_id, result_data in query_results.items():
                    if result_data.get("query_index") == i or result_data.get("component_id") == component_id:
                        query_result = result_data
                        break
                
                # Build component similar to dashboard structure
                formatted_component = {
                    "id": component_id,
                    "type": component_type,
                    "chart": component_dict.get("chart", {}),
                    "table": component_dict.get("table", {}),
                    "metadata": component_dict.get("metadata", {}),
                    "overview": component_dict.get("overview", {}),
                    "question": component_dict.get("question", ""),
                    "sequence": component_dict.get("sequence_order", i + 1),
                    "reasoning": component_dict.get("reasoning", ""),
                    "sql_query": component_dict.get("sql_query", ""),
                    "data_count": component_dict.get("data_count", 0),
                    "description": component_dict.get("description", ""),
                    "sample_data": component_dict.get("sample_data", {}),
                    "chart_schema": component_dict.get("chart_schema", {}),
                    "configuration": component_dict.get("configuration", {}),
                    "data_overview": component_dict.get("data_overview"),
                    "is_configured": component_dict.get("is_configured", False),
                    "executive_summary": component_dict.get("executive_summary", ""),
                    "validation_results": component_dict.get("validation_results", {}),
                    "visualization_data": component_dict.get("visualization_data", {})
                }
                
                # Add query result data if available
                if query_result:
                    formatted_component.update({
                        "data_count": query_result.get("row_count", 0),
                        "sample_data": {
                            "data": query_result.get("data", []),
                            "columns": query_result.get("columns", [])
                        },
                        "chart_schema": query_result.get("chart_schema", {}),
                        "reasoning": query_result.get("reasoning", ""),
                        "data_source": query_result.get("data_source", "sql_execution"),
                        "fallback_used": query_result.get("fallback_used", False)
                    })
                
                formatted_components.append(formatted_component)
                
                # Extract positioning information
                component_metadata = formatted_component.get("metadata", {})
                if component_metadata and "position" in component_metadata:
                    component_positions[component_id] = {
                        "position": component_metadata["position"],
                        "ui_visibility": component_metadata.get("ui_visibility", {}),
                        "size": component_metadata.get("size", {})
                    }
            
            # Build report configuration similar to dashboard config
            report_config = {
                "report_id": report_id,
                "report_name": workflow_metadata.get("report_title", f"Report from Workflow {workflow_id}"),
                "report_description": workflow_metadata.get("report_description", "Report generated from workflow configuration"),
                "report_type": "Point-in-Time",  # Key difference from dashboard
                "generated_at": datetime.now().isoformat(),
                "workflow_id": workflow_id,
                "project_id": project_id,
                "template": workflow_metadata.get("dashboard_template", "default"),
                "layout": workflow_metadata.get("dashboard_layout", "grid"),
                "refresh_rate": 0,  # Reports don't refresh
                "component_positions": component_positions,
                "total_components": len(formatted_components)
            }
            
            # Build the main report data structure
            report_data = {
                "report_id": report_id,
                "report_name": report_config["report_name"],
                "report_description": report_config["report_description"],
                "ReportType": "Point-in-Time",  # Key difference from dashboard
                "content": {
                    "status": "rendered",
                    "components": formatted_components
                },
                "generated_at": report_config["generated_at"],
                "workflow_id": workflow_id,
                "project_id": project_id
            }
            
            # Build the final response structure similar to dashboard
            formatted_output = {
                "success": True,
                "report_data": report_data,  # Similar to dashboard_data
                "enhanced_report": enhanced_context,  # Similar to enhanced_dashboard
                "report_config": report_config,  # Similar to dashboard_config
                "metadata": {
                    "project_id": project_id,
                    "workflow_id": workflow_id,
                    "total_queries": len(query_results),
                    "conditional_formatting_applied": bool(enhanced_context.get("conditional_formatting_rules")),
                    "report_template": workflow_metadata.get("dashboard_template"),
                    "timestamp": datetime.now().isoformat(),
                    "orchestration_metadata": orchestration_metadata,
                    "report_type": "point_in_time",
                    "generated_at": report_config["generated_at"]
                }
            }
            
            # Add global executive summary from report summary if available
            if report_summary:
                # Extract the actual summary text if report_summary is a dictionary
                if isinstance(report_summary, dict):
                    summary_text = report_summary.get("global_executive_summary", "") or report_summary.get("summary", "") or str(report_summary)
                else:
                    summary_text = str(report_summary)
                formatted_output["global_executive_summary"] = summary_text
            else:
                # Generate a basic executive summary for reports
                total_components = len(formatted_components)
                report_name = report_config["report_name"]
                
                formatted_output["global_executive_summary"] = f"**REPORT OVERVIEW**\n\n**{report_name}** (Workflow: {workflow_id})\n\nThis point-in-time report provides comprehensive analysis across {total_components} component(s), generated on {report_config['generated_at']}. The report delivers actionable insights based on data analysis at the time of generation.\n\n**Key Focus Areas:**\n- Performance metrics and completion rates\n- Data-driven insights for strategic planning\n- Actionable recommendations for improvement\n\n**Report Type:** Point-in-Time Analysis"
            
            # Add workflow metadata
            formatted_output["workflow_metadata"] = result.get("workflow_metadata", {})
            
            logger.info(f"Formatted report output with {len(formatted_components)} components")
            return formatted_output
            
        except Exception as e:
            logger.error(f"Error formatting report output like dashboard: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Return a basic structure if formatting fails
            return {
                "success": True,
                "report_data": {
                    "report_id": f"report_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "report_name": "Report",
                    "ReportType": "Point-in-Time",
                    "content": {"status": "rendered", "components": []}
                },
                "metadata": {
                    "project_id": project_id,
                    "error": str(e),
                    "report_type": "point_in_time"
                }
            }
    
    def _format_report_output_with_global_summary(
        self,
        result: Dict[str, Any],
        workflow_data: Dict[str, Any],
        thread_components: List[Any]
    ) -> Dict[str, Any]:
        """
        Format report output with global executive summary and component positioning
        
        Args:
            result: Original report result from orchestrator pipeline
            workflow_data: Workflow data from request
            thread_components: Thread components from workflow
            
        Returns:
            Formatted report output with global executive summary and component positioning
        """
        try:
            # Extract report data from result
            post_process = result.get("post_process", {})
            comprehensive_report = post_process.get("comprehensive_report", {})
            report_outline = comprehensive_report.get("report_outline", {})
            sections = report_outline.get("sections", [])
            
            # Extract component positioning information from thread components
            component_positions = {}
            for component in thread_components:
                component_metadata = None
                component_id = component.id if hasattr(component, 'id') else component.get("id", "")
                
                # Check for metadata in ThreadComponentData objects
                if hasattr(component, 'metadata') and component.metadata:
                    component_metadata = component.metadata
                # Check for metadata in dictionary components
                elif isinstance(component, dict) and component.get("metadata"):
                    component_metadata = component["metadata"]
                
                # Also check for thread_metadata in the component if it's a dict
                if not component_metadata and isinstance(component, dict) and component.get("thread_metadata"):
                    component_metadata = component["thread_metadata"]
                
                if component_metadata and "position" in component_metadata:
                    component_positions[component_id] = {
                        "position": component_metadata["position"],
                        "ui_visibility": component_metadata.get("ui_visibility", {}),
                        "project_id": component_metadata.get("project_id", ""),
                        "data_description": component_metadata.get("data_description", ""),
                        "processing_stats": component_metadata.get("processing_stats", {})
                    }
                    logger.info(f"Extracted positioning for report component {component_id}: {component_metadata.get('position', {})}")
                else:
                    logger.warning(f"No positioning metadata found for report component {component_id}. Available metadata keys: {list(component_metadata.keys()) if component_metadata else 'None'}")
                    # Add a default position if no metadata is available
                    component_positions[component_id] = {
                        "position": {"x": 0, "y": 0, "width": 400, "height": 300},
                        "ui_visibility": {"visible": True, "collapsed": False},
                        "project_id": workflow_data.get("project_id", ""),
                        "data_description": f"Component {component_id}",
                        "processing_stats": {}
                    }
                    logger.info(f"Added default positioning for report component {component_id}")
            
            # Generate global executive summary if not present
            global_executive_summary = None
            if sections:
                # Try to extract from first section's executive summary
                first_section = sections[0]
                if first_section.get("executive_summary"):
                    # Use first section's executive summary as global summary
                    global_executive_summary = first_section.get("executive_summary")
                elif first_section.get("content"):
                    # Try to extract from content
                    content = first_section.get("content", "")
                    if isinstance(content, str) and len(content) > 50:
                        global_executive_summary = content
                else:
                    # Generate a basic summary from available data
                    total_sections = len(sections)
                    workflow_id = workflow_data.get("workflow_id", "")
                    report_title = workflow_data.get("workflow_metadata", {}).get("report_title", "Report")
                    
                    global_executive_summary = f"**REPORT OVERVIEW**\n\n**{report_title}** (Workflow: {workflow_id})\n\nThis report provides comprehensive analysis across {total_sections} section(s), delivering actionable insights for organizational decision-making.\n\n**Key Focus Areas:**\n- Data analysis and insights\n- Performance metrics and trends\n- Strategic recommendations and next steps"
            
            # Add global executive summary to result
            if global_executive_summary:
                result["global_executive_summary"] = global_executive_summary
                logger.info("Added global executive summary to report response")
            
            # Create report configuration with component positioning
            report_config = {
                "template": workflow_data.get("workflow_metadata", {}).get("dashboard_template", "default"),
                "layout": workflow_data.get("workflow_metadata", {}).get("dashboard_layout", "grid"),
                "refresh_rate": workflow_data.get("workflow_metadata", {}).get("refresh_rate", 300),
                "component_positions": component_positions,
                "total_components": len(thread_components),
                "project_id": workflow_data.get("project_id", ""),
                "workflow_id": workflow_data.get("workflow_id", ""),
                "created_at": datetime.now().isoformat()
            }
            
            # Add report configuration to result
            result["report_config"] = report_config
            logger.info(f"Added report configuration with {len(component_positions)} component positions")
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting report output with global summary: {e}")
            # Return original result if formatting fails
            return result
    
    def _add_global_executive_summary_to_result(
        self,
        result: Dict[str, Any],
        report_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add global executive summary to report result
        
        Args:
            result: Report result from orchestrator pipeline
            report_context: Report context information
            
        Returns:
            Report result with global executive summary added
        """
        try:
            # Check if result is None
            if result is None:
                logger.warning("Result is None, cannot add global executive summary")
                return {}
            
            # Check if report_context is None
            if report_context is None:
                logger.warning("Report context is None, using default values")
                report_context = {}
            
            # Extract report data from result
            post_process = result.get("post_process", {})
            comprehensive_report = post_process.get("comprehensive_report", {})
            report_outline = comprehensive_report.get("report_outline", {})
            sections = report_outline.get("sections", [])
            
            # Generate global executive summary if not present
            global_executive_summary = None
            if sections:
                # Try to extract from first section's executive summary
                first_section = sections[0]
                if first_section.get("executive_summary"):
                    # Use first section's executive summary as global summary
                    global_executive_summary = first_section.get("executive_summary")
                elif first_section.get("content"):
                    # Try to extract from content
                    content = first_section.get("content", "")
                    if isinstance(content, str) and len(content) > 50:
                        global_executive_summary = content
                else:
                    # Generate a basic summary from available data
                    total_sections = len(sections)
                    report_title = report_context.get("title", "Report")
                    
                    global_executive_summary = f"**REPORT OVERVIEW**\n\n**{report_title}**\n\nThis report provides comprehensive analysis across {total_sections} section(s), delivering actionable insights for organizational decision-making.\n\n**Key Focus Areas:**\n- Data analysis and insights\n- Performance metrics and trends\n- Strategic recommendations and next steps"
            
            # Add global executive summary to result
            if global_executive_summary:
                result["global_executive_summary"] = global_executive_summary
                logger.info("Added global executive summary to report result")
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding global executive summary to result: {e}")
            # Return original result if formatting fails
            return result

    def clear_cache(self):
        """Clear configuration and execution caches"""
        self._configuration_cache.clear()
        self._execution_history.clear()
        # Also clear the BaseService cache
        super().clear_cache()


# Note: Factory function moved to SQLServiceContainer.create_report_service()


# Example usage
async def example_report_service_usage():
    """Example of using the refactored report service as a pure API layer"""
    
    # Get report service from service container
    # Note: In production, this would be injected via dependency injection
    # For this example, we'll create the service directly
    report_service = ReportService()
    
    # Sample report queries
    report_queries = [
        {
            "sql": "SELECT region, SUM(sales_amount) as sales, COUNT(*) as transactions FROM sales_data GROUP BY region",
            "query": "Show sales and transaction count by region",
            "data_description": "Sales data aggregated by region"
        },
        {
            "sql": "SELECT date, AVG(performance_score) as avg_score FROM performance_data GROUP BY date ORDER BY date",
            "query": "Show average performance score over time",
            "data_description": "Performance trends over time"
        },
        {
            "sql": "SELECT category, SUM(profit) as total_profit FROM sales_data GROUP BY category ORDER BY total_profit DESC",
            "query": "Show profit by category",
            "data_description": "Profit analysis by product category"
        }
    ]
    
    # Report context
    report_context = {
        "title": "Q4 Sales Performance Report",
        "description": "Comprehensive analysis of Q4 sales performance across regions and categories",
        "sections": [
            "executive_summary",
            "regional_analysis",
            "performance_trends",
            "category_insights",
            "recommendations"
        ],
        "available_columns": ["date", "region", "sales", "quantity", "profit", "category", "status"],
        "data_types": {
            "date": "datetime",
            "region": "categorical",
            "sales": "numeric",
            "quantity": "numeric",
            "profit": "numeric",
            "category": "categorical",
            "status": "categorical"
        }
    }
    
    # Natural language formatting query
    natural_language_query = """
    Highlight regions with sales above $100,000 in green and below $50,000 in red.
    Filter performance data to show only scores above 75.
    Emphasize categories with profit margins above 20%.
    """
    
    # Status callback
    def status_callback(status: str, details: Dict[str, Any]):
        print(f"Status: {status} - {details}")
    
    # Generate comprehensive report using executive summary template
    result = await report_service.generate_comprehensive_report(
        report_queries=report_queries,
        project_id="q4_sales_report",
        report_context=report_context,
        natural_language_query=natural_language_query,
        report_template="executive_summary",
        additional_context={"user_id": "user123", "report_period": "Q4 2024"},
        time_filters={"period": "last_quarter"},
        status_callback=status_callback
    )
    
    print("Report Service Result:")
    print(f"Success: {result.get('post_process', {}).get('success', False)}")
    print(f"Conditional formatting applied: {result.get('post_process', {}).get('orchestration_metadata', {}).get('conditional_formatting_applied', False)}")
    print(f"Comprehensive report generated: {result.get('post_process', {}).get('orchestration_metadata', {}).get('comprehensive_report_generated', False)}")
    
    return result


if __name__ == "__main__":
    # Run example
    import asyncio
    asyncio.run(example_report_service_usage())
