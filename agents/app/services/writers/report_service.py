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
                "simple_report": self.pipeline_container.get_pipeline("simple_report_generation")
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
                "simple_report": None
            }
        
        # Configuration cache and execution history
        self._configuration_cache = {}
        self._execution_history = []
        self._report_templates = {}
        
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
            report_context = self._create_report_context_from_workflow(workflow_info, report_queries)
            
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
            
            for comp in workflow_components:
                # Convert workflow component type to report component type
                component_type = self._map_workflow_component_type(comp.get("component_type"))
                
                # Create ThreadComponentData
                thread_component = ThreadComponentData(
                    id=comp.get("id", f"component_{len(components)}"),
                    name=comp.get("question", f"Component {comp.get('sequence_order', len(components))}"),
                    type=component_type,
                    content=comp.get("description", ""),
                    metadata={
                        "workflow_component": True,
                        "sequence_order": comp.get("sequence_order", 0),
                        "original_type": comp.get("component_type"),
                        "configuration": comp.get("configuration", {}),
                        "alert_config": comp.get("alert_config"),
                        "chart_config": comp.get("chart_config"),
                        "table_config": comp.get("table_config")
                    }
                )
                
                components.append(thread_component)
            
            # Sort by sequence order
            components.sort(key=lambda x: x.metadata.get("sequence_order", 0))
            
            return components
            
        except Exception as e:
            logger.error(f"Error extracting thread components from workflow: {e}")
            return []
    
    def _map_workflow_component_type(self, workflow_type: str) -> ComponentType:
        """Map workflow component types to report component types"""
        type_mapping = {
            "question": ComponentType.TEXT,
            "description": ComponentType.TEXT,
            "overview": ComponentType.TEXT,
            "chart": ComponentType.CHART,
            "table": ComponentType.TABLE,
            "metric": ComponentType.METRIC,
            "insight": ComponentType.TEXT,
            "narrative": ComponentType.TEXT,
            "alert": ComponentType.ALERT
        }
        
        return type_mapping.get(workflow_type.lower(), ComponentType.TEXT)
    
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
    
    def _create_report_context_from_workflow(
        self, 
        workflow_info: Dict[str, Any], 
        report_queries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create report context from workflow data"""
        try:
            metadata = workflow_info.get("workflow_metadata", {})
            
            # Extract available columns from queries
            available_columns = set()
            data_types = {}
            
            for query in report_queries:
                if "data_description" in query:
                    # Try to extract column information from description
                    desc = query["data_description"].lower()
                    if "region" in desc:
                        available_columns.add("region")
                        data_types["region"] = "categorical"
                    if "sales" in desc or "amount" in desc:
                        available_columns.add("sales")
                        data_types["sales"] = "numeric"
                    if "date" in desc or "time" in desc:
                        available_columns.add("date")
                        data_types["date"] = "datetime"
                    if "performance" in desc or "score" in desc:
                        available_columns.add("performance_score")
                        data_types["performance_score"] = "numeric"
            
            # Create report context
            context = {
                "title": metadata.get("report_title", f"Report from Workflow {workflow_info.get('id', 'Unknown')}"),
                "description": metadata.get("report_description", "Report generated from workflow configuration"),
                "sections": metadata.get("report_sections", ["overview", "analysis", "conclusions"]),
                "available_columns": list(available_columns),
                "data_types": data_types,
                "workflow_id": workflow_info.get("id"),
                "workflow_state": workflow_info.get("state"),
                "workflow_metadata": metadata
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Error creating report context from workflow: {e}")
            # Return basic context
            return {
                "title": "Report from Workflow",
                "description": "Report generated from workflow configuration",
                "sections": ["overview", "analysis", "conclusions"],
                "available_columns": [],
                "data_types": {},
                "workflow_id": workflow_info.get("id", "unknown")
            }
    
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
                name=component_name.replace("_", " ").title(),
                type=ComponentType.TEXT,
                content=f"Generate {component_name.replace('_', ' ')} content",
                metadata={"template_component": True}
            )
            components.append(component)
        
        return components
    
    def _create_default_components(self) -> List[ThreadComponentData]:
        """Create default thread components"""
        return [
            ThreadComponentData(
                id="component_executive_summary",
                name="Executive Summary",
                type=ComponentType.TEXT,
                content="Generate executive summary content",
                metadata={"default_component": True}
            ),
            ThreadComponentData(
                id="component_key_findings",
                name="Key Findings",
                type=ComponentType.TEXT,
                content="Generate key findings content",
                metadata={"default_component": True}
            ),
            ThreadComponentData(
                id="component_recommendations",
                name="Recommendations",
                type=ComponentType.TEXT,
                content="Generate recommendations content",
                metadata={"default_component": True}
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
