import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm, get_doc_store_provider
from app.agents.nodes.writers.dashboard_agent import ConditionalFormattingAgent

logger = logging.getLogger("lexy-ai-service")


class ConditionalFormattingGenerationPipeline(AgentPipeline):
    """Pipeline for generating conditional formatting configurations without applying them"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        document_store_provider: Any = None
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
            "generate_sql_expansions": True,
            "generate_chart_adjustments": True
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize conditional formatting agent
        if not document_store_provider:
            document_store_provider = get_doc_store_provider()
        
        # Create the retriever first
        from app.agents.nodes.writers.dashboard_agent import ConditionalFormattingRetriever
        retriever = ConditionalFormattingRetriever(retrieval_helper)
        
        self._conditional_formatting_agent = ConditionalFormattingAgent(
            llm=llm,
            retriever=retriever,
            document_store_provider=document_store_provider
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
        Generate conditional formatting configuration for a dashboard
        
        Args:
            natural_language_query: Natural language query for conditional formatting
            dashboard_context: Context about dashboard charts and columns
            project_id: Project identifier
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing generated conditional formatting configuration
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
            raise ValueError("Dashboard context is required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "conditional_formatting_generation_started",
            {
                "project_id": project_id,
                "query_length": len(natural_language_query),
                "dashboard_charts_count": len(dashboard_context.get("charts", [])),
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            # Step 1: Validate dashboard context
            if self._configuration["enable_validation"]:
                self._send_status_update(
                    status_callback,
                    "validation_started",
                    {"project_id": project_id}
                )
                
                validation_result = self._validate_dashboard_context(dashboard_context)
                if not validation_result["valid"]:
                    raise ValueError(f"Dashboard context validation failed: {validation_result['issues']}")
                
                self._send_status_update(
                    status_callback,
                    "validation_completed",
                    {"project_id": project_id, "valid": True}
                )
            
            # Step 2: Generate conditional formatting configuration
            self._send_status_update(
                status_callback,
                "generation_started",
                {"project_id": project_id}
            )
            
            result = await self._conditional_formatting_agent.process_conditional_formatting_request(
                query=natural_language_query,
                dashboard_context=dashboard_context,
                project_id=project_id,
                additional_context=additional_context,
                time_filters=time_filters
            )
            
            # Step 3: Optimize configuration if enabled
            if self._configuration["enable_optimization"] and result.get("success"):
                self._send_status_update(
                    status_callback,
                    "optimization_started",
                    {"project_id": project_id}
                )
                
                result = await self._optimize_configuration(result, dashboard_context)
                
                self._send_status_update(
                    status_callback,
                    "optimization_completed",
                    {"project_id": project_id}
                )
            
            # Step 4: Prepare enhanced dashboard JSON
            enhanced_dashboard = self._prepare_enhanced_dashboard_json(
                dashboard_context, 
                result.get("chart_configurations", {}),
                project_id
            )
            
            # Calculate execution metrics
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                success=result.get("success", False),
                execution_time=execution_time,
                project_id=project_id
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "conditional_formatting_generation_completed",
                {
                    "project_id": project_id,
                    "execution_time": execution_time,
                    "success": result.get("success", False),
                    "chart_configurations_count": len(result.get("chart_configurations", {})),
                    "enhanced_dashboard_generated": True
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": result.get("success", False),
                    "configuration": result.get("configuration"),
                    "chart_configurations": result.get("chart_configurations", {}),
                    "enhanced_dashboard": enhanced_dashboard,
                    "metadata": result.get("metadata", {}),
                    "execution_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "execution_time_seconds": execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id
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
            logger.error(f"Error in conditional formatting generation pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "conditional_formatting_generation_error",
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

    def _prepare_enhanced_dashboard_json(
        self,
        dashboard_context: Dict[str, Any],
        chart_configurations: Dict[str, Dict[str, Any]],
        project_id: str
    ) -> Dict[str, Any]:
        """Prepare enhanced dashboard JSON with conditional formatting rules"""
        
        enhanced_dashboard = {
            "project_id": project_id,
            "generated_at": datetime.now().isoformat(),
            "original_context": dashboard_context,
            "conditional_formatting_rules": chart_configurations,
            "execution_instructions": {}
        }
        
        # Generate execution instructions for each chart
        for chart_id, config in chart_configurations.items():
            chart_instructions = {
                "chart_id": chart_id,
                "sql_expansions": [],
                "chart_adjustments": [],
                "conditional_formats": []
            }
            
            # Extract SQL expansion instructions
            if "sql_expansion" in config:
                sql_expansion = config["sql_expansion"]
                if "where_conditions" in sql_expansion:
                    chart_instructions["sql_expansions"].append({
                        "type": "where_conditions",
                        "conditions": sql_expansion["where_conditions"]
                    })
                
                if "time_filters" in sql_expansion:
                    chart_instructions["sql_expansions"].append({
                        "type": "time_filters",
                        "filters": sql_expansion["time_filters"]
                    })
            
            # Extract chart adjustment instructions
            if "chart_adjustment" in config:
                chart_instructions["chart_adjustments"].append({
                    "type": "chart_adjustment",
                    "config": config["chart_adjustment"]
                })
            
            # Extract conditional format instructions
            if "conditional_formats" in config:
                chart_instructions["conditional_formats"] = config["conditional_formats"]
            
            enhanced_dashboard["execution_instructions"][chart_id] = chart_instructions
        
        return enhanced_dashboard

    def _validate_dashboard_context(self, dashboard_context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dashboard context structure"""
        validation = {"valid": True, "issues": []}
        
        # Check required fields
        if "charts" not in dashboard_context:
            validation["valid"] = False
            validation["issues"].append("Missing 'charts' field in dashboard context")
        
        if "available_columns" not in dashboard_context:
            validation["valid"] = False
            validation["issues"].append("Missing 'available_columns' field in dashboard context")
        
        # Validate charts structure
        if "charts" in dashboard_context:
            charts = dashboard_context["charts"]
            if not isinstance(charts, list):
                validation["valid"] = False
                validation["issues"].append("'charts' field must be a list")
            else:
                for i, chart in enumerate(charts):
                    if not isinstance(chart, dict):
                        validation["valid"] = False
                        validation["issues"].append(f"Chart {i} must be a dictionary")
                    elif "chart_id" not in chart:
                        validation["valid"] = False
                        validation["issues"].append(f"Chart {i}: Missing chart_id")
        
        return validation

    async def _optimize_configuration(
        self,
        result: Dict[str, Any],
        dashboard_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize the generated configuration for better performance"""
        try:
            configuration = result.get("configuration")
            if not configuration:
                return result
            
            # Optimize chart configurations
            chart_configurations = result.get("chart_configurations", {})
            optimized_configurations = {}
            
            for chart_id, config in chart_configurations.items():
                optimized_config = self._optimize_single_chart_config(config, chart_id, dashboard_context)
                optimized_configurations[chart_id] = optimized_config
            
            # Update result with optimized configurations
            result["chart_configurations"] = optimized_configurations
            result["metadata"]["optimization_applied"] = True
            
            return result
            
        except Exception as e:
            logger.warning(f"Configuration optimization failed: {e}")
            return result

    def _optimize_single_chart_config(
        self,
        config: Dict[str, Any],
        chart_id: str,
        dashboard_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize configuration for a single chart"""
        optimized_config = config.copy()
        
        # Optimize SQL expansion conditions
        if "sql_expansion" in optimized_config:
            sql_expansion = optimized_config["sql_expansion"]
            
            # Consolidate WHERE conditions
            if "where_conditions" in sql_expansion:
                where_conditions = sql_expansion["where_conditions"]
                # Remove duplicate conditions
                unique_conditions = list(dict.fromkeys(where_conditions))
                if len(unique_conditions) != len(where_conditions):
                    sql_expansion["where_conditions"] = unique_conditions
                    optimized_config["metadata"] = optimized_config.get("metadata", {})
                    optimized_config["metadata"]["conditions_consolidated"] = True
        
        # Add optimization metadata
        optimized_config["optimization_metadata"] = {
            "optimized_at": datetime.now().isoformat(),
            "chart_id": chart_id,
            "optimizations_applied": ["condition_consolidation"]
        }
        
        return optimized_config

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
        logger.info(f"Conditional Formatting Generation Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        success: bool,
        execution_time: float,
        project_id: str
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "success": success,
                "execution_time": execution_time,
                "project_id": project_id,
                "timestamp": datetime.now().isoformat()
            },
            "total_executions": self._metrics.get("total_executions", 0) + 1,
            "successful_executions": self._metrics.get("successful_executions", 0) + (1 if success else 0),
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
            "agent_metrics": self._conditional_formatting_agent.get_metrics() if hasattr(self._conditional_formatting_agent, 'get_metrics') else {},
            "timestamp": datetime.now().isoformat()
        }

    def enable_validation(self, enabled: bool) -> None:
        """Enable or disable validation"""
        self._configuration["enable_validation"] = enabled
        logger.info(f"Validation {'enabled' if enabled else 'disabled'}")

    def enable_optimization(self, enabled: bool) -> None:
        """Enable or disable optimization"""
        self._configuration["enable_optimization"] = enabled
        logger.info(f"Optimization {'enabled' if enabled else 'disabled'}")


# Factory function for creating conditional formatting generation pipeline
def create_conditional_formatting_generation_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    document_store_provider: Any = None,
    **kwargs
) -> ConditionalFormattingGenerationPipeline:
    """
    Factory function to create a conditional formatting generation pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        document_store_provider: Document store provider (optional, will use default if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        ConditionalFormattingGenerationPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return ConditionalFormattingGenerationPipeline(
        name="conditional_formatting_generation_pipeline",
        version="1.0.0",
        description="Pipeline for generating conditional formatting configurations without applying them",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        document_store_provider=document_store_provider,
        **kwargs
    )
