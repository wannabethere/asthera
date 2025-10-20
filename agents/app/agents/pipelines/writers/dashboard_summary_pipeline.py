import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm, get_doc_store_provider

logger = logging.getLogger("lexy-ai-service")


class DashboardSummaryPipeline(AgentPipeline):
    """Pipeline for generating overall executive summary and insights for entire dashboard"""
    
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
            "timeout_seconds": 120,
            "enable_caching": True,
            "cache_ttl_seconds": 3600,
            "enable_validation": True,
            "enable_optimization": True,
            "include_trend_analysis": True,
            "include_correlation_analysis": True,
            "include_recommendations": True,
            "max_summary_length": 2000,
            "max_insights_count": 10
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize document store provider if not provided
        if not document_store_provider:
            document_store_provider = get_doc_store_provider()
        
        self._document_store_provider = document_store_provider
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
        dashboard_components: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate overall executive summary and insights for the entire dashboard
        
        Args:
            dashboard_components: List of dashboard components with their data and summaries
            dashboard_context: Overall dashboard context and metadata
            project_id: Project identifier
            additional_context: Additional context for summary generation
            status_callback: Callback for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing overall executive summary and insights
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not dashboard_components or not isinstance(dashboard_components, list):
            raise ValueError("Dashboard components must be a non-empty list")
        
        if not dashboard_context:
            raise ValueError("Dashboard context is required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "dashboard_summary_generation_started",
            {
                "project_id": project_id,
                "total_components": len(dashboard_components),
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            # Extract component summaries and insights
            component_summaries = self._extract_component_summaries(dashboard_components)
            
            # Generate overall executive summary
            executive_summary = await self._generate_executive_summary(
                component_summaries=component_summaries,
                dashboard_context=dashboard_context,
                additional_context=additional_context,
                project_id=project_id,
                status_callback=status_callback
            )
            
            # Generate overall insights
            insights = await self._generate_insights(
                component_summaries=component_summaries,
                dashboard_context=dashboard_context,
                additional_context=additional_context,
                project_id=project_id,
                status_callback=status_callback
            )
            
            # Generate trend analysis if enabled
            trend_analysis = None
            if self._configuration["include_trend_analysis"]:
                trend_analysis = await self._generate_trend_analysis(
                    dashboard_components=dashboard_components,
                    dashboard_context=dashboard_context,
                    project_id=project_id,
                    status_callback=status_callback
                )
            
            # Generate correlation analysis if enabled
            correlation_analysis = None
            if self._configuration["include_correlation_analysis"]:
                correlation_analysis = await self._generate_correlation_analysis(
                    dashboard_components=dashboard_components,
                    dashboard_context=dashboard_context,
                    project_id=project_id,
                    status_callback=status_callback
                )
            
            # Generate recommendations if enabled
            recommendations = None
            if self._configuration["include_recommendations"]:
                recommendations = await self._generate_recommendations(
                    component_summaries=component_summaries,
                    dashboard_context=dashboard_context,
                    insights=insights,
                    project_id=project_id,
                    status_callback=status_callback
                )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                total_components=len(dashboard_components),
                execution_time=total_execution_time,
                project_id=project_id
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "dashboard_summary_generation_completed",
                {
                    "project_id": project_id,
                    "execution_time": total_execution_time,
                    "summary_length": len(executive_summary) if executive_summary else 0,
                    "insights_count": len(insights) if insights else 0
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": True,
                    "global_executive_summary": executive_summary,
                    "global_insights": insights,
                    "trend_analysis": trend_analysis,
                    "correlation_analysis": correlation_analysis,
                    "recommendations": recommendations,
                    "dashboard_insights": {
                        "total_components": len(dashboard_components),
                        "summary_generation_time": total_execution_time,
                        "generated_at": end_time.isoformat(),
                        "pipeline_version": self.version
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
            logger.error(f"Error in dashboard summary generation: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "dashboard_summary_generation_error",
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

    def _extract_component_summaries(self, dashboard_components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract summaries and key data from dashboard components"""
        component_summaries = []
        
        for i, component in enumerate(dashboard_components):
            summary_data = {
                "component_id": component.get("id"),
                "component_type": component.get("type", "question"),
                "question": component.get("question", ""),
                "executive_summary": component.get("executive_summary", ""),
                "reasoning": component.get("reasoning", ""),
                "data_count": component.get("data_count", 0),
                "sequence": component.get("sequence", i + 1),
                "chart_type": component.get("chart", {}).get("chart_type", ""),
                "data_sample": component.get("sample_data", {}).get("data", [])[:5],  # First 5 rows
                "columns": component.get("sample_data", {}).get("columns", []),
                "insights": component.get("overview", {}).get("insights", ""),
                "validation_success": component.get("validation_results", {}).get("validation_success", False)
            }
            component_summaries.append(summary_data)
        
        return component_summaries

    async def _generate_executive_summary(
        self,
        component_summaries: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> str:
        """Generate overall executive summary for the dashboard"""
        
        self._send_status_update(
            status_callback,
            "executive_summary_generation_started",
            {"project_id": project_id}
        )
        
        try:
            # Prepare context for LLM
            context_parts = []
            
            # Add dashboard context
            context_parts.append(f"Dashboard Title: {dashboard_context.get('title', 'Dashboard')}")
            context_parts.append(f"Dashboard Description: {dashboard_context.get('description', '')}")
            context_parts.append(f"Total Components: {len(component_summaries)}")
            
            # Add component summaries
            context_parts.append("\nComponent Summaries:")
            for i, summary in enumerate(component_summaries):
                context_parts.append(f"\nComponent {i + 1} ({summary['component_type']}):")
                context_parts.append(f"Question: {summary['question']}")
                if summary['executive_summary']:
                    context_parts.append(f"Summary: {summary['executive_summary']}")
                if summary['insights']:
                    context_parts.append(f"Insights: {summary['insights']}")
                context_parts.append(f"Data Count: {summary['data_count']}")
            
            # Add additional context if provided
            if additional_context:
                context_parts.append(f"\nAdditional Context: {additional_context}")
            
            # Create prompt for executive summary generation
            prompt = f"""
            Based on the following dashboard components and their summaries, generate a comprehensive executive summary for the entire dashboard.
            
            Context:
            {chr(10).join(context_parts)}
            
            Please provide:
            1. A high-level overview of what this dashboard shows
            2. Key findings and insights across all components
            3. Overall performance or status indicators
            4. Critical trends or patterns identified
            5. Executive-level recommendations based on the data
            
            Keep the summary concise but comprehensive, suitable for executive consumption.
            Maximum length: {self._configuration['max_summary_length']} characters.
            """
            
            # Generate summary using LLM
            response = await self._llm.ainvoke(prompt)
            executive_summary = response.content if hasattr(response, 'content') else str(response)
            
            self._send_status_update(
                status_callback,
                "executive_summary_generation_completed",
                {
                    "project_id": project_id,
                    "summary_length": len(executive_summary)
                }
            )
            
            return executive_summary
            
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            self._send_status_update(
                status_callback,
                "executive_summary_generation_failed",
                {"error": str(e), "project_id": project_id}
            )
            return "Executive summary generation failed due to an error."

    async def _generate_insights(
        self,
        component_summaries: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> List[str]:
        """Generate overall insights for the dashboard"""
        
        self._send_status_update(
            status_callback,
            "insights_generation_started",
            {"project_id": project_id}
        )
        
        try:
            # Prepare context for insights generation
            context_parts = []
            
            # Add dashboard context
            context_parts.append(f"Dashboard: {dashboard_context.get('title', 'Dashboard')}")
            context_parts.append(f"Components: {len(component_summaries)}")
            
            # Add key data points from components
            context_parts.append("\nKey Data Points:")
            for summary in component_summaries:
                if summary['data_count'] > 0:
                    context_parts.append(f"- {summary['question']}: {summary['data_count']} records")
            
            # Add component insights
            context_parts.append("\nComponent Insights:")
            for summary in component_summaries:
                if summary['insights']:
                    context_parts.append(f"- {summary['question']}: {summary['insights']}")
            
            # Create prompt for insights generation
            prompt = f"""
            Based on the following dashboard data, generate {self._configuration['max_insights_count']} key insights that provide valuable business intelligence.
            
            Context:
            {chr(10).join(context_parts)}
            
            Please provide insights that:
            1. Identify patterns and trends across the data
            2. Highlight anomalies or outliers
            3. Suggest business implications
            4. Point to areas requiring attention
            5. Identify opportunities for improvement
            
            Format each insight as a clear, actionable statement.
            """
            
            # Generate insights using LLM
            response = await self._llm.ainvoke(prompt)
            insights_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse insights into list
            insights = [insight.strip() for insight in insights_text.split('\n') if insight.strip()]
            insights = insights[:self._configuration['max_insights_count']]
            
            self._send_status_update(
                status_callback,
                "insights_generation_completed",
                {
                    "project_id": project_id,
                    "insights_count": len(insights)
                }
            )
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            self._send_status_update(
                status_callback,
                "insights_generation_failed",
                {"error": str(e), "project_id": project_id}
            )
            return ["Insights generation failed due to an error."]

    async def _generate_trend_analysis(
        self,
        dashboard_components: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Generate trend analysis across dashboard components"""
        
        self._send_status_update(
            status_callback,
            "trend_analysis_generation_started",
            {"project_id": project_id}
        )
        
        try:
            # Analyze trends across components
            trend_analysis = {
                "overall_trends": [],
                "component_trends": {},
                "data_quality_indicators": {},
                "performance_metrics": {}
            }
            
            # Simple trend analysis based on data counts and validation results
            total_data_points = sum(comp.get("data_count", 0) for comp in dashboard_components)
            successful_validations = sum(1 for comp in dashboard_components if comp.get("validation_results", {}).get("validation_success", False))
            
            trend_analysis["performance_metrics"] = {
                "total_data_points": total_data_points,
                "successful_validations": successful_validations,
                "validation_success_rate": successful_validations / len(dashboard_components) if dashboard_components else 0
            }
            
            self._send_status_update(
                status_callback,
                "trend_analysis_generation_completed",
                {"project_id": project_id}
            )
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"Error generating trend analysis: {e}")
            self._send_status_update(
                status_callback,
                "trend_analysis_generation_failed",
                {"error": str(e), "project_id": project_id}
            )
            return {"error": "Trend analysis generation failed"}

    async def _generate_correlation_analysis(
        self,
        dashboard_components: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Generate correlation analysis across dashboard components"""
        
        self._send_status_update(
            status_callback,
            "correlation_analysis_generation_started",
            {"project_id": project_id}
        )
        
        try:
            # Simple correlation analysis
            correlation_analysis = {
                "component_correlations": {},
                "data_patterns": [],
                "cross_component_insights": []
            }
            
            # Analyze correlations between components
            for i, comp1 in enumerate(dashboard_components):
                for j, comp2 in enumerate(dashboard_components[i+1:], i+1):
                    correlation_key = f"component_{i+1}_vs_component_{j+1}"
                    correlation_analysis["component_correlations"][correlation_key] = {
                        "correlation_strength": "medium",  # Placeholder
                        "insights": f"Components {i+1} and {j+1} show related data patterns"
                    }
            
            self._send_status_update(
                status_callback,
                "correlation_analysis_generation_completed",
                {"project_id": project_id}
            )
            
            return correlation_analysis
            
        except Exception as e:
            logger.error(f"Error generating correlation analysis: {e}")
            self._send_status_update(
                status_callback,
                "correlation_analysis_generation_failed",
                {"error": str(e), "project_id": project_id}
            )
            return {"error": "Correlation analysis generation failed"}

    async def _generate_recommendations(
        self,
        component_summaries: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        insights: List[str],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> List[str]:
        """Generate actionable recommendations based on dashboard analysis"""
        
        self._send_status_update(
            status_callback,
            "recommendations_generation_started",
            {"project_id": project_id}
        )
        
        try:
            # Prepare context for recommendations
            context_parts = [
                f"Dashboard: {dashboard_context.get('title', 'Dashboard')}",
                f"Total Components: {len(component_summaries)}",
                f"Key Insights: {', '.join(insights[:3])}"  # First 3 insights
            ]
            
            # Create prompt for recommendations
            prompt = f"""
            Based on the following dashboard analysis, generate 5 actionable recommendations for business stakeholders.
            
            Context:
            {chr(10).join(context_parts)}
            
            Please provide recommendations that:
            1. Address data quality issues if any
            2. Suggest process improvements
            3. Recommend additional analysis or monitoring
            4. Propose strategic actions based on findings
            5. Suggest dashboard enhancements
            
            Format each recommendation as a clear, actionable statement.
            """
            
            # Generate recommendations using LLM
            response = await self._llm.ainvoke(prompt)
            recommendations_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse recommendations into list
            recommendations = [rec.strip() for rec in recommendations_text.split('\n') if rec.strip()]
            recommendations = recommendations[:5]  # Limit to 5 recommendations
            
            self._send_status_update(
                status_callback,
                "recommendations_generation_completed",
                {
                    "project_id": project_id,
                    "recommendations_count": len(recommendations)
                }
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            self._send_status_update(
                status_callback,
                "recommendations_generation_failed",
                {"error": str(e), "project_id": project_id}
            )
            return ["Recommendations generation failed due to an error."]

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
        logger.info(f"Dashboard Summary Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        total_components: int,
        execution_time: float,
        project_id: str
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "total_components": total_components,
                "execution_time": execution_time,
                "project_id": project_id,
                "timestamp": datetime.now().isoformat()
            },
            "total_executions": self._metrics.get("total_executions", 0) + 1,
            "total_components_processed": self._metrics.get("total_components_processed", 0) + total_components,
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
            "timestamp": datetime.now().isoformat()
        }


# Factory function for creating dashboard summary pipeline
def create_dashboard_summary_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    document_store_provider: Any = None,
    **kwargs
) -> DashboardSummaryPipeline:
    """
    Factory function to create a dashboard summary pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        document_store_provider: Document store provider instance (optional)
        **kwargs: Additional configuration options
    
    Returns:
        DashboardSummaryPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    if not document_store_provider:
        document_store_provider = get_doc_store_provider()
    
    return DashboardSummaryPipeline(
        name="dashboard_summary_pipeline",
        version="1.0.0",
        description="Pipeline for generating overall executive summary and insights for entire dashboard",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        document_store_provider=document_store_provider,
        **kwargs
    )
