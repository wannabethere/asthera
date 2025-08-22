import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import json

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm

logger = logging.getLogger("lexy-ai-service")


class SimpleReportGenerationPipeline(AgentPipeline):
    """Simple pipeline for generating basic reports from SQL queries and enhanced context"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine
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
            "max_rows_per_query": 10000,
            "enable_data_summarization": True,
            "enable_insight_generation": True,
            "enable_recommendations": True
        }
        
        self._metrics = {}
        self._engine = engine
        self._llm = llm
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
        report_queries: List[Dict[str, Any]],
        enhanced_context: Dict[str, Any],
        project_id: str,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a simple report from SQL queries and enhanced context
        
        Args:
            report_queries: List of SQL queries for report data
            enhanced_context: Enhanced context with conditional formatting and instructions
            project_id: Project identifier
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing the generated report
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not report_queries or not isinstance(report_queries, list):
            raise ValueError("Report queries must be a non-empty list")
        
        if not enhanced_context:
            raise ValueError("Enhanced context is required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "simple_report_generation_started",
            {
                "project_id": project_id,
                "total_queries": len(report_queries),
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            # Step 1: Execute SQL queries and collect data
            self._send_status_update(
                status_callback,
                "executing_sql_queries",
                {"project_id": project_id, "total_queries": len(report_queries)}
            )
            
            query_results = await self._execute_report_queries(report_queries, project_id)
            
            # Step 2: Apply conditional formatting if available
            formatted_results = await self._apply_conditional_formatting(
                query_results, enhanced_context, project_id
            )
            
            # Step 3: Generate data insights and summaries
            insights = await self._generate_data_insights(
                formatted_results, enhanced_context, project_id
            )
            
            # Step 4: Generate recommendations
            recommendations = await self._generate_recommendations(
                formatted_results, insights, enhanced_context, project_id
            )
            
            # Step 5: Compile final report
            final_report = await self._compile_final_report(
                formatted_results, insights, recommendations, enhanced_context, project_id
            )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                total_queries=len(report_queries),
                execution_time=total_execution_time,
                project_id=project_id,
                total_rows_processed=sum(len(result.get("data", [])) for result in query_results.values()),
                insights_generated=len(insights),
                recommendations_generated=len(recommendations)
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "simple_report_generation_completed",
                {
                    "project_id": project_id,
                    "execution_time": total_execution_time,
                    "total_rows_processed": sum(len(result.get("data", [])) for result in query_results.values()),
                    "insights_generated": len(insights),
                    "recommendations_generated": len(recommendations)
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": True,
                    "report": final_report,
                    "query_results": query_results,
                    "formatted_results": formatted_results,
                    "insights": insights,
                    "recommendations": recommendations,
                    "generation_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "total_queries": len(report_queries),
                        "total_rows_processed": sum(len(result.get("data", [])) for result in query_results.values())
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
            logger.error(f"Error in simple report generation pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "simple_report_generation_error",
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

    async def _execute_report_queries(
        self,
        report_queries: List[Dict[str, Any]],
        project_id: str
    ) -> Dict[str, Any]:
        """Execute SQL queries and collect results"""
        query_results = {}
        
        for i, query_info in enumerate(report_queries):
            try:
                query_id = query_info.get("id", f"query_{i}")
                sql_query = query_info.get("sql", "")
                query_name = query_info.get("name", f"Query {i+1}")
                
                if not sql_query:
                    logger.warning(f"Empty SQL query for {query_id}")
                    continue
                
                # Execute the query using the engine
                result = await self._engine.execute_query(
                    sql_query,
                    timeout=self._configuration["timeout_seconds"]
                )
                
                query_results[query_id] = {
                    "name": query_name,
                    "sql": sql_query,
                    "data": result.get("data", []),
                    "columns": result.get("columns", []),
                    "row_count": len(result.get("data", [])),
                    "execution_time": result.get("execution_time", 0),
                    "success": result.get("success", False),
                    "error": result.get("error")
                }
                
                logger.info(f"Executed query {query_id}: {len(result.get('data', []))} rows")
                
            except Exception as e:
                logger.error(f"Error executing query {i}: {str(e)}")
                query_results[f"query_{i}"] = {
                    "name": f"Query {i+1}",
                    "sql": query_info.get("sql", ""),
                    "data": [],
                    "columns": [],
                    "row_count": 0,
                    "execution_time": 0,
                    "success": False,
                    "error": str(e)
                }
        
        return query_results

    async def _apply_conditional_formatting(
        self,
        query_results: Dict[str, Any],
        enhanced_context: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Apply conditional formatting to query results"""
        formatted_results = {}
        
        # Extract conditional formatting rules from enhanced context
        formatting_rules = enhanced_context.get("conditional_formatting_rules", {})
        
        for query_id, result in query_results.items():
            if not result.get("success") or not result.get("data"):
                formatted_results[query_id] = result
                continue
            
            formatted_data = []
            data = result.get("data", [])
            columns = result.get("columns", [])
            
            for row in data:
                formatted_row = {}
                for col_idx, col_name in enumerate(columns):
                    value = row[col_idx] if col_idx < len(row) else None
                    
                    # Apply formatting rules if available
                    if col_name in formatting_rules:
                        rule = formatting_rules[col_name]
                        formatted_value = self._apply_formatting_rule(value, rule)
                        formatted_row[col_name] = formatted_value
                    else:
                        formatted_row[col_name] = value
                
                formatted_data.append(formatted_row)
            
            formatted_results[query_id] = {
                **result,
                "data": formatted_data,
                "formatted": True
            }
        
        return formatted_results

    def _apply_formatting_rule(self, value: Any, rule: Dict[str, Any]) -> Any:
        """Apply a single formatting rule to a value"""
        try:
            rule_type = rule.get("type", "default")
            
            if rule_type == "number_format":
                # Apply number formatting
                decimal_places = rule.get("decimal_places", 2)
                if isinstance(value, (int, float)):
                    return round(float(value), decimal_places)
            
            elif rule_type == "date_format":
                # Apply date formatting
                date_format = rule.get("format", "%Y-%m-%d")
                if value and hasattr(value, "strftime"):
                    return value.strftime(date_format)
            
            elif rule_type == "conditional_color":
                # Apply conditional color formatting
                conditions = rule.get("conditions", [])
                for condition in conditions:
                    if self._evaluate_condition(value, condition):
                        return {
                            "value": value,
                            "color": condition.get("color", "default"),
                            "style": condition.get("style", "normal")
                        }
            
            elif rule_type == "text_transform":
                # Apply text transformation
                transform = rule.get("transform", "none")
                if isinstance(value, str):
                    if transform == "uppercase":
                        return value.upper()
                    elif transform == "lowercase":
                        return value.lower()
                    elif transform == "titlecase":
                        return value.title()
            
        except Exception as e:
            logger.warning(f"Error applying formatting rule: {e}")
        
        return value

    def _evaluate_condition(self, value: Any, condition: Dict[str, Any]) -> bool:
        """Evaluate a conditional formatting condition"""
        try:
            operator = condition.get("operator", "equals")
            threshold = condition.get("threshold")
            
            if operator == "equals":
                return value == threshold
            elif operator == "not_equals":
                return value != threshold
            elif operator == "greater_than":
                return value > threshold
            elif operator == "less_than":
                return value < threshold
            elif operator == "greater_than_or_equal":
                return value >= threshold
            elif operator == "less_than_or_equal":
                return value <= threshold
            elif operator == "contains":
                return str(threshold) in str(value)
            elif operator == "not_contains":
                return str(threshold) not in str(value)
            
        except Exception as e:
            logger.warning(f"Error evaluating condition: {e}")
        
        return False

    async def _generate_data_insights(
        self,
        formatted_results: Dict[str, Any],
        enhanced_context: Dict[str, Any],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Generate insights from the formatted data"""
        insights = []
        
        if not self._configuration["enable_data_summarization"]:
            return insights
        
        try:
            for query_id, result in formatted_results.items():
                if not result.get("success") or not result.get("data"):
                    continue
                
                data = result.get("data", [])
                if not data:
                    continue
                
                # Generate basic statistical insights
                insight = await self._generate_statistical_insight(
                    data, result.get("name", query_id), project_id
                )
                if insight:
                    insights.append(insight)
                
                # Generate trend insights if applicable
                trend_insight = await self._generate_trend_insight(
                    data, result.get("name", query_id), project_id
                )
                if trend_insight:
                    insights.append(trend_insight)
        
        except Exception as e:
            logger.error(f"Error generating data insights: {e}")
        
        return insights

    async def _generate_statistical_insight(
        self,
        data: List[Dict[str, Any]],
        query_name: str,
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Generate statistical insights from data"""
        try:
            if not data:
                return None
            
            # Extract numeric columns
            numeric_columns = []
            for col_name, value in data[0].items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    numeric_columns.append(col_name)
            
            if not numeric_columns:
                return None
            
            # Calculate basic statistics
            stats = {}
            for col_name in numeric_columns:
                values = [row.get(col_name, 0) for row in data if row.get(col_name) is not None]
                if values:
                    stats[col_name] = {
                        "count": len(values),
                        "sum": sum(values),
                        "average": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values)
                    }
            
            if not stats:
                return None
            
            return {
                "type": "statistical",
                "query_name": query_name,
                "insight": f"Statistical summary for {query_name}",
                "details": stats,
                "generated_at": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error generating statistical insight: {e}")
            return None

    async def _generate_trend_insight(
        self,
        data: List[Dict[str, Any]],
        query_name: str,
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Generate trend insights from data"""
        try:
            if not data or len(data) < 2:
                return None
            
            # Look for date/time columns
            date_columns = []
            for col_name, value in data[0].items():
                if isinstance(value, str) and any(char.isdigit() for char in str(value)):
                    # Simple heuristic for date columns
                    date_columns.append(col_name)
            
            if not date_columns:
                return None
            
            # For now, return a basic trend insight
            return {
                "type": "trend",
                "query_name": query_name,
                "insight": f"Trend analysis available for {query_name}",
                "details": {
                    "date_columns_found": date_columns,
                    "data_points": len(data)
                },
                "generated_at": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error generating trend insight: {e}")
            return None

    async def _generate_recommendations(
        self,
        formatted_results: Dict[str, Any],
        insights: List[Dict[str, Any]],
        enhanced_context: Dict[str, Any],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on data and insights"""
        recommendations = []
        
        if not self._configuration["enable_recommendations"]:
            return recommendations
        
        try:
            # Generate recommendations based on data volume
            for query_id, result in formatted_results.items():
                if not result.get("success"):
                    continue
                
                row_count = result.get("row_count", 0)
                query_name = result.get("name", query_id)
                
                if row_count > 10000:
                    recommendations.append({
                        "type": "performance",
                        "priority": "high",
                        "query_name": query_name,
                        "recommendation": f"Consider pagination or filtering for {query_name} (currently {row_count} rows)",
                        "action": "Implement pagination or add WHERE clauses to reduce data volume"
                    })
                
                elif row_count == 0:
                    recommendations.append({
                        "type": "data_quality",
                        "priority": "medium",
                        "query_name": query_name,
                        "recommendation": f"No data returned for {query_name}",
                        "action": "Verify query logic and data availability"
                    })
            
            # Generate recommendations based on insights
            for insight in insights:
                if insight.get("type") == "statistical":
                    stats = insight.get("details", {})
                    for col_name, col_stats in stats.items():
                        if col_stats.get("count", 0) > 0:
                            avg_value = col_stats.get("average", 0)
                            if avg_value < 0:
                                recommendations.append({
                                    "type": "business_logic",
                                    "priority": "medium",
                                    "query_name": insight.get("query_name", "Unknown"),
                                    "recommendation": f"Negative average value detected for {col_name}",
                                    "action": "Review business logic for negative values"
                                })
        
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return recommendations

    async def _compile_final_report(
        self,
        formatted_results: Dict[str, Any],
        insights: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        enhanced_context: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Compile the final report from all components"""
        try:
            # Calculate summary statistics
            total_queries = len(formatted_results)
            successful_queries = sum(1 for r in formatted_results.values() if r.get("success"))
            total_rows = sum(r.get("row_count", 0) for r in formatted_results.values())
            
            report = {
                "report_id": f"report_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "project_id": project_id,
                "generated_at": datetime.now().isoformat(),
                "summary": {
                    "total_queries": total_queries,
                    "successful_queries": successful_queries,
                    "failed_queries": total_queries - successful_queries,
                    "total_rows_processed": total_rows,
                    "insights_generated": len(insights),
                    "recommendations_generated": len(recommendations)
                },
                "query_results": formatted_results,
                "insights": insights,
                "recommendations": recommendations,
                "enhanced_context": enhanced_context,
                "metadata": {
                    "pipeline_name": self.name,
                    "pipeline_version": self.version,
                    "configuration_used": self._configuration.copy()
                }
            }
            
            return report
        
        except Exception as e:
            logger.error(f"Error compiling final report: {e}")
            return {
                "error": f"Failed to compile report: {str(e)}",
                "generated_at": datetime.now().isoformat()
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
        logger.info(f"Simple Report Generation Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        total_queries: int,
        execution_time: float,
        project_id: str,
        total_rows_processed: int,
        insights_generated: int,
        recommendations_generated: int
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "total_queries": total_queries,
                "execution_time": execution_time,
                "project_id": project_id,
                "total_rows_processed": total_rows_processed,
                "insights_generated": insights_generated,
                "recommendations_generated": recommendations_generated,
                "timestamp": datetime.now().isoformat()
            },
            "total_executions": self._metrics.get("total_executions", 0) + 1,
            "total_queries_processed": self._metrics.get("total_queries_processed", 0) + total_queries,
            "total_execution_time": self._metrics.get("total_execution_time", 0) + execution_time,
            "total_rows_processed": self._metrics.get("total_rows_processed", 0) + total_rows_processed,
            "total_insights_generated": self._metrics.get("total_insights_generated", 0) + insights_generated,
            "total_recommendations_generated": self._metrics.get("total_recommendations_generated", 0) + recommendations_generated
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

    def enable_data_summarization(self, enabled: bool) -> None:
        """Enable or disable data summarization"""
        self._configuration["enable_data_summarization"] = enabled
        logger.info(f"Data summarization {'enabled' if enabled else 'disabled'}")

    def enable_insight_generation(self, enabled: bool) -> None:
        """Enable or disable insight generation"""
        self._configuration["enable_insight_generation"] = enabled
        logger.info(f"Insight generation {'enabled' if enabled else 'disabled'}")

    def enable_recommendations(self, enabled: bool) -> None:
        """Enable or disable recommendation generation"""
        self._configuration["enable_recommendations"] = enabled
        logger.info(f"Recommendations {'enabled' if enabled else 'disabled'}")


# Factory function for creating simple report generation pipeline
def create_simple_report_generation_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    **kwargs
) -> SimpleReportGenerationPipeline:
    """
    Factory function to create a simple report generation pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        SimpleReportGenerationPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return SimpleReportGenerationPipeline(
        name="simple_report_generation_pipeline",
        version="1.0.0",
        description="Simple pipeline for generating basic reports from SQL queries and enhanced context",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        **kwargs
    )
