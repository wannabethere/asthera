import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import json

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm

try:
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

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
            
            # Check if we have enough successful data, or if we should use LLM with existing thread component data
            successful_queries = sum(1 for r in query_results.values() if r.get("success") and r.get("data"))
            total_queries_count = len(query_results)
            
            # If most queries failed, try to build report from existing thread component data using LLM
            if successful_queries == 0 or (total_queries_count > 0 and successful_queries / total_queries_count < 0.5):
                logger.info(f"Most SQL queries failed ({successful_queries}/{total_queries_count}). Attempting to build report from existing thread component data using LLM")
                self._send_status_update(
                    status_callback,
                    "building_report_from_existing_data",
                    {
                        "project_id": project_id,
                        "successful_queries": successful_queries,
                        "total_queries": total_queries_count
                    }
                )
                
                # Try to build report from existing thread component data
                existing_data_report = await self._build_report_from_existing_data(
                    report_queries, query_results, enhanced_context, project_id
                )
                
                if existing_data_report:
                    logger.info("Successfully built report from existing thread component data")
                    # Use the LLM-generated report
                    formatted_results = existing_data_report.get("formatted_results", query_results)
                    insights = existing_data_report.get("insights", [])
                    recommendations = existing_data_report.get("recommendations", [])
                else:
                    logger.warning("Could not build report from existing data, proceeding with available data")
                    # Step 2: Apply conditional formatting if available
                    formatted_results = await self._apply_conditional_formatting(
                        query_results, enhanced_context, project_id
                    )
                    
                    # Step 3: Generate data insights and summaries (will use existing insights)
                    insights = await self._generate_data_insights(
                        formatted_results, enhanced_context, project_id
                    )
                    
                    # Step 4: Generate recommendations
                    recommendations = await self._generate_recommendations(
                        formatted_results, insights, enhanced_context, project_id
                    )
            else:
                # Normal flow: SQL queries succeeded
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
        """Execute SQL queries and collect results with fallback to existing chart data"""
        query_results = {}
        
        for i, query_info in enumerate(report_queries):
            try:
                query_id = query_info.get("id", f"query_{i}")
                sql_query = query_info.get("sql", "")
                query_name = query_info.get("name", f"Query {i+1}")
                
                if not sql_query:
                    logger.warning(f"Empty SQL query for {query_id}")
                    continue
                
                # Execute the query using the engine directly to avoid batch processing issues
                # Use aiohttp session for compatibility
                import aiohttp
                
                async with aiohttp.ClientSession() as session:
                    success, result = await self._engine.execute_sql(
                        sql_query,
                        session,
                        dry_run=False,
                        use_cache=False,  # Disable caching to avoid empty results
                        timeout=self._configuration["timeout_seconds"]
                    )
                    
                    if not success or not result.get("data"):
                        # SQL query failed - try to use existing chart data as fallback
                        logger.warning(f"SQL query failed for {query_id}, attempting to use existing chart data")
                        result = self._extract_data_from_existing_charts(query_info, query_id)
                        
                        if result["success"]:
                            logger.info(f"Successfully used existing chart data for {query_id}")
                        else:
                            logger.error(f"No fallback data available for {query_id}")
                    else:
                        # Ensure result has the expected structure
                        if not isinstance(result, dict):
                            result = {"data": [], "columns": [], "execution_time": 0}
                        
                        result["success"] = True
                        result["error"] = None
                
                query_results[query_id] = {
                    "name": query_name,
                    "sql": sql_query,
                    "data": result.get("data", []),
                    "columns": result.get("columns", []),
                    "row_count": len(result.get("data", [])),
                    "execution_time": result.get("execution_time", 0),
                    "success": result.get("success", False),
                    "error": result.get("error"),
                    "chart_schema": result.get("chart_schema", {}),
                    "chart_type": result.get("chart_type", ""),
                    "reasoning": result.get("reasoning", ""),
                    "data_source": result.get("data_source", "sql_execution"),
                    "fallback_used": result.get("fallback_used", False)
                }
                
                logger.info(f"Executed query {query_id}: {len(result.get('data', []))} rows")
                
            except Exception as e:
                logger.error(f"Error executing query {i}: {str(e)}")
                
                # Try fallback even in case of exception
                try:
                    fallback_result = self._extract_data_from_existing_charts(query_info, f"query_{i}")
                    if fallback_result["success"]:
                        logger.info(f"Used fallback data for query {i} after exception")
                        query_results[f"query_{i}"] = {
                            "name": f"Query {i+1}",
                            "sql": query_info.get("sql", ""),
                            "data": fallback_result.get("data", []),
                            "columns": fallback_result.get("columns", []),
                            "row_count": len(fallback_result.get("data", [])),
                            "execution_time": 0,
                            "success": True,
                            "error": None,
                            "chart_schema": fallback_result.get("chart_schema", {}),
                            "chart_type": fallback_result.get("chart_type", ""),
                            "reasoning": fallback_result.get("reasoning", ""),
                            "data_source": fallback_result.get("data_source", "fallback"),
                            "fallback_used": True
                        }
                    else:
                        raise e  # Re-raise if fallback also failed
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed for query {i}: {str(fallback_error)}")
                    query_results[f"query_{i}"] = {
                        "name": f"Query {i+1}",
                        "sql": query_info.get("sql", ""),
                        "data": [],
                        "columns": [],
                        "row_count": 0,
                        "execution_time": 0,
                        "success": False,
                        "error": str(e),
                        "data_source": "error",
                        "fallback_used": False
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
            
            try:
                formatted_data = []
                data = result.get("data", [])
                columns = result.get("columns", [])
                
                if not data:
                    formatted_results[query_id] = {
                        **result,
                        "data": [],
                        "formatted": True
                    }
                    continue
                
                # Check if data is already in dict format (from pandas to_dict) or list format
                if isinstance(data[0], dict):
                    # Data is already in dict format
                    for row in data:
                        formatted_row = {}
                        for col_name in columns:
                            value = row.get(col_name, None)
                            
                            # Apply formatting rules if available
                            if col_name in formatting_rules:
                                rule = formatting_rules[col_name]
                                formatted_value = self._apply_formatting_rule(value, rule)
                                formatted_row[col_name] = formatted_value
                            else:
                                formatted_row[col_name] = value
                        
                        formatted_data.append(formatted_row)
                else:
                    # Data is in list format (list of lists)
                    for row in data:
                        formatted_row = {}
                        for col_idx, col_name in enumerate(columns):
                            value = row[col_idx] if isinstance(row, (list, tuple)) and col_idx < len(row) else None
                            
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
            except Exception as e:
                logger.error(f"Error applying conditional formatting for query {query_id}: {e}", exc_info=True)
                # Return unformatted result if formatting fails
                formatted_results[query_id] = result
        
        return formatted_results

    def _extract_data_from_existing_charts(self, query_info: Dict[str, Any], query_id: str) -> Dict[str, Any]:
        """Extract data from existing chart configurations when SQL queries fail"""
        try:
            # Check for chart_config with data_sample
            chart_config = query_info.get("chart_config", {})
            data_sample = chart_config.get("data_sample", {})
            
            if data_sample and data_sample.get("data"):
                # Convert data_sample to the expected format
                data = data_sample["data"]
                columns = data_sample.get("columns", [])
                
                # Convert data to row format (list of lists)
                formatted_data = []
                for row in data:
                    if isinstance(row, dict):
                        # Convert dict to list based on column order
                        formatted_row = [row.get(col, None) for col in columns]
                        formatted_data.append(formatted_row)
                    else:
                        formatted_data.append(row)
                
                return {
                    "data": formatted_data,
                    "columns": columns,
                    "execution_time": 0,
                    "success": True,
                    "error": None,
                    "chart_schema": chart_config.get("chart_schema", {}),
                    "chart_type": chart_config.get("chart_type", ""),
                    "reasoning": chart_config.get("reasoning", ""),
                    "data_source": "existing_chart_data",
                    "fallback_used": True
                }
            
            # Check for chart_schema with data
            chart_schema = query_info.get("chart_schema", {})
            if chart_schema and chart_schema.get("data", {}).get("values"):
                values = chart_schema["data"]["values"]
                if values:
                    # Extract columns from the first value
                    columns = list(values[0].keys()) if values else []
                    
                    # Convert to row format
                    formatted_data = []
                    for value in values:
                        formatted_row = [value.get(col, None) for col in columns]
                        formatted_data.append(formatted_row)
                    
                    return {
                        "data": formatted_data,
                        "columns": columns,
                        "execution_time": 0,
                        "success": True,
                        "error": None,
                        "chart_schema": chart_schema,
                        "chart_type": chart_schema.get("mark", {}).get("type", ""),
                        "reasoning": "Data extracted from existing chart schema",
                        "data_source": "chart_schema",
                        "fallback_used": True
                    }
            
            # No fallback data available
            return {
                "data": [],
                "columns": [],
                "execution_time": 0,
                "success": False,
                "error": "No fallback data available",
                "data_source": "none",
                "fallback_used": False
            }
            
        except Exception as e:
            logger.error(f"Error extracting data from existing charts for {query_id}: {e}")
            return {
                "data": [],
                "columns": [],
                "execution_time": 0,
                "success": False,
                "error": f"Fallback extraction failed: {str(e)}",
                "data_source": "error",
                "fallback_used": False
            }

    def _extract_existing_insights_from_workflow(self, report_queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract existing insights and summaries from workflow components when SQL fails"""
        insights = []
        
        try:
            for i, query_info in enumerate(report_queries):
                # Check for existing overview/insights in chart_config
                chart_config = query_info.get("chart_config", {})
                overview = chart_config.get("overview", {})
                
                if overview and isinstance(overview, dict):
                    overview_text = overview.get("overview", "")
                    if overview_text:
                        # Extract insights from the overview text
                        insight = {
                            "id": f"insight_{i}",
                            "title": f"Analysis for {query_info.get('name', f'Query {i+1}')}",
                            "description": overview_text,
                            "source": "existing_workflow_data",
                            "query_id": query_info.get("id", f"query_{i}"),
                            "data_source": "workflow_overview"
                        }
                        insights.append(insight)
                        logger.info(f"Extracted existing insight for query {i}")
                
                # Check for reasoning in chart_config
                reasoning = chart_config.get("reasoning", "")
                if reasoning and reasoning not in [insight.get("description", "") for insight in insights]:
                    reasoning_insight = {
                        "id": f"reasoning_{i}",
                        "title": f"Analysis Reasoning for {query_info.get('name', f'Query {i+1}')}",
                        "description": reasoning,
                        "source": "existing_chart_reasoning",
                        "query_id": query_info.get("id", f"query_{i}"),
                        "data_source": "chart_reasoning"
                    }
                    insights.append(reasoning_insight)
                    logger.info(f"Extracted reasoning insight for query {i}")
            
            logger.info(f"Extracted {len(insights)} existing insights from workflow data")
            return insights
            
        except Exception as e:
            logger.error(f"Error extracting existing insights from workflow: {e}")
            return []

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

    async def _build_report_from_existing_data(
        self,
        report_queries: List[Dict[str, Any]],
        query_results: Dict[str, Any],
        enhanced_context: Dict[str, Any],
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Build report from existing thread component data using LLM when SQL fails"""
        try:
            if not LANGCHAIN_AVAILABLE or not self._llm:
                logger.warning("LangChain not available or LLM not initialized, cannot build report from existing data")
                return None
            
            # Extract all available data from thread components
            existing_data_summary = self._extract_existing_component_data(report_queries, query_results)
            
            if not existing_data_summary or not existing_data_summary.get("has_data"):
                logger.warning("No existing component data found to build report from")
                return None
            
            logger.info(f"Building report from existing data: {len(existing_data_summary.get('components', []))} components found")
            
            # Generate insights using LLM (or extract existing ones)
            insights = await self._generate_llm_insights(existing_data_summary, project_id)
            
            # If no insights generated, try to extract from existing workflow
            if not insights:
                insights = self._extract_existing_insights_from_workflow(report_queries)
            
            # Generate recommendations using LLM (or extract existing ones)
            recommendations = await self._generate_llm_recommendations(existing_data_summary, insights, project_id)
            
            # Process formatted results from existing data
            formatted_results = await self._format_existing_component_data(
                report_queries, query_results, enhanced_context
            )
            
            return {
                "formatted_results": formatted_results,
                "insights": insights,
                "recommendations": recommendations,
                "data_source": "existing_thread_components"
            }
            
        except Exception as e:
            logger.error(f"Error building report from existing data: {e}", exc_info=True)
            return None

    def _extract_existing_component_data(
        self,
        report_queries: List[Dict[str, Any]],
        query_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract all available data from thread components"""
        components_data = []
        has_data = False
        
        for i, query_info in enumerate(report_queries):
            query_id = query_info.get("id", f"query_{i}")
            component_data = {
                "query_id": query_id,
                "query_name": query_info.get("name", f"Query {i+1}"),
                "sql": query_info.get("sql", ""),
                "chart_config": query_info.get("chart_config", {}),
                "chart_schema": query_info.get("chart_schema", {}),
                "overview": query_info.get("overview", {}),
                "reasoning": query_info.get("reasoning", ""),
                "executive_summary": query_info.get("executive_summary", ""),
                "data_overview": query_info.get("data_overview", {}),
                "visualization_data": query_info.get("visualization_data", {}),
                "sample_data": query_info.get("sample_data", {}),
                "chart_type": query_info.get("chart_type", ""),
                "data_count": query_info.get("data_count", 0)
            }
            
            # Also check query_results for any fallback data
            if query_id in query_results:
                result = query_results[query_id]
                if result.get("fallback_used"):
                    component_data.update({
                        "chart_schema": result.get("chart_schema", component_data.get("chart_schema", {})),
                        "chart_type": result.get("chart_type", component_data.get("chart_type", "")),
                        "reasoning": result.get("reasoning", component_data.get("reasoning", "")),
                        "data": result.get("data", [])
                    })
            
            # Check if this component has useful data
            has_useful_data = (
                component_data.get("chart_config") or
                component_data.get("chart_schema") or
                component_data.get("overview") or
                component_data.get("reasoning") or
                component_data.get("executive_summary") or
                component_data.get("data_overview") or
                component_data.get("visualization_data") or
                component_data.get("sample_data") or
                component_data.get("data")
            )
            
            if has_useful_data:
                has_data = True
                components_data.append(component_data)
        
        return {
            "components": components_data,
            "has_data": has_data,
            "total_components": len(components_data)
        }

    async def _generate_llm_insights(
        self,
        existing_data_summary: Dict[str, Any],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Generate insights from existing component data using LLM"""
        insights = []
        
        try:
            if not self._llm:
                return insights
            
            components = existing_data_summary.get("components", [])
            if not components:
                return insights
            
            # Extract existing insights from components first
            for component in components:
                if component.get("reasoning"):
                    insights.append({
                        "id": f"insight_{component.get('query_id')}",
                        "type": "existing_reasoning",
                        "query_name": component.get("query_name", "Unknown"),
                        "insight": component.get("reasoning"),
                        "source": "thread_component_reasoning",
                        "query_id": component.get("query_id")
                    })
                
                if component.get("executive_summary"):
                    insights.append({
                        "id": f"summary_{component.get('query_id')}",
                        "type": "executive_summary",
                        "query_name": component.get("query_name", "Unknown"),
                        "insight": component.get("executive_summary"),
                        "source": "thread_component_summary",
                        "query_id": component.get("query_id")
                    })
                
                if component.get("overview"):
                    overview = component.get("overview")
                    if isinstance(overview, dict):
                        overview_text = overview.get("overview", "") or str(overview)
                    else:
                        overview_text = str(overview)
                    
                    if overview_text:
                        insights.append({
                            "id": f"overview_{component.get('query_id')}",
                            "type": "overview",
                            "query_name": component.get("query_name", "Unknown"),
                            "insight": overview_text,
                            "source": "thread_component_overview",
                            "query_id": component.get("query_id")
                        })
            
            # Use LLM to generate additional insights if we have chart/visualization data
            if LANGCHAIN_AVAILABLE:
                insight_prompt = PromptTemplate(
                    input_variables=["components_data"],
                    template="""You are a data analyst generating insights from existing visualization and chart data.

Given the following component data from thread components (charts, visualizations, data summaries that were previously generated):

{components_data}

Analyze the data and generate 3-5 key insights. Focus on:
1. Patterns and trends visible in the charts/data
2. Key observations about the data
3. Notable findings or anomalies
4. Business implications

Format as a JSON array of insights, each with:
- "type": "llm_generated"
- "title": "Brief title"
- "description": "Detailed insight description"
- "query_id": "which query/component this relates to"

Return ONLY valid JSON array, no markdown formatting.
"""
                )
                
                # Format components data for LLM
                components_str = json.dumps(components, indent=2, default=str)
                
                chain = insight_prompt | self._llm | StrOutputParser()
                response = await chain.ainvoke({"components_data": components_str})
                
                # Parse JSON response
                try:
                    if "```json" in response:
                        json_start = response.find("```json") + 7
                        json_end = response.find("```", json_start)
                        if json_end != -1:
                            response = response[json_start:json_end].strip()
                    elif "```" in response:
                        json_start = response.find("```") + 3
                        json_end = response.find("```", json_start)
                        if json_end != -1:
                            response = response[json_start:json_end].strip()
                    
                    llm_insights = json.loads(response)
                    if isinstance(llm_insights, list):
                        insights.extend(llm_insights)
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse LLM insight response as JSON: {e}")
            
            logger.info(f"Generated {len(insights)} insights from existing component data")
            
        except Exception as e:
            logger.error(f"Error generating LLM insights: {e}", exc_info=True)
        
        return insights

    async def _generate_llm_recommendations(
        self,
        existing_data_summary: Dict[str, Any],
        insights: List[Dict[str, Any]],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Generate recommendations from existing data and insights using LLM"""
        recommendations = []
        
        try:
            if not self._llm or not insights:
                return recommendations
            
            # Extract existing recommendations from data_overview if available
            components = existing_data_summary.get("components", [])
            for component in components:
                data_overview = component.get("data_overview", {})
                if isinstance(data_overview, dict) and data_overview.get("recommendations"):
                    recs = data_overview.get("recommendations")
                    if isinstance(recs, list):
                        recommendations.extend([
                            {
                                "type": "existing",
                                "priority": "medium",
                                "query_name": component.get("query_name", "Unknown"),
                                "recommendation": rec if isinstance(rec, str) else rec.get("text", str(rec)),
                                "source": "data_overview",
                                "query_id": component.get("query_id")
                            }
                            for rec in recs
                        ])
            
            # Use LLM to generate additional recommendations
            if LANGCHAIN_AVAILABLE and insights:
                rec_prompt = PromptTemplate(
                    input_variables=["insights", "components_summary"],
                    template="""You are a business analyst generating actionable recommendations based on data insights.

Given the following insights generated from existing data:

{insights}

And component summary:
{components_summary}

Generate 3-5 actionable recommendations. Each recommendation should:
1. Be specific and actionable
2. Address the findings in the insights
3. Be relevant to business decision-making

Format as a JSON array of recommendations, each with:
- "type": "llm_recommendation"
- "priority": "high" | "medium" | "low"
- "recommendation": "Detailed recommendation text"
- "action": "Specific action to take"

Return ONLY valid JSON array, no markdown formatting.
"""
                )
                
                insights_str = json.dumps(insights, indent=2, default=str)
                components_summary = f"Total components: {existing_data_summary.get('total_components', 0)}"
                
                chain = rec_prompt | self._llm | StrOutputParser()
                response = await chain.ainvoke({
                    "insights": insights_str,
                    "components_summary": components_summary
                })
                
                # Parse JSON response
                try:
                    if "```json" in response:
                        json_start = response.find("```json") + 7
                        json_end = response.find("```", json_start)
                        if json_end != -1:
                            response = response[json_start:json_end].strip()
                    elif "```" in response:
                        json_start = response.find("```") + 3
                        json_end = response.find("```", json_start)
                        if json_end != -1:
                            response = response[json_start:json_end].strip()
                    
                    llm_recs = json.loads(response)
                    if isinstance(llm_recs, list):
                        recommendations.extend(llm_recs)
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse LLM recommendation response as JSON: {e}")
            
            logger.info(f"Generated {len(recommendations)} recommendations from existing data")
            
        except Exception as e:
            logger.error(f"Error generating LLM recommendations: {e}", exc_info=True)
        
        return recommendations

    async def _format_existing_component_data(
        self,
        report_queries: List[Dict[str, Any]],
        query_results: Dict[str, Any],
        enhanced_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format existing component data into the expected formatted_results structure"""
        formatted_results = {}
        
        for i, query_info in enumerate(report_queries):
            query_id = query_info.get("id", f"query_{i}")
            
            # Try to get data from query_results first (may have fallback data)
            result = query_results.get(query_id, {})
            
            # Extract data from various sources
            data = result.get("data", [])
            
            # If no data, try to extract from component fields
            if not data:
                chart_config = query_info.get("chart_config", {})
                data_sample = chart_config.get("data_sample", {})
                if data_sample and data_sample.get("data"):
                    data = data_sample["data"]
                    if data and isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], dict):
                            # Already in dict format
                            pass
                        else:
                            # Convert to dict format
                            columns = data_sample.get("columns", [])
                            data = [
                                {col: row[idx] if idx < len(row) else None for idx, col in enumerate(columns)}
                                for row in data
                            ]
                    else:
                        data = []
            
            formatted_results[query_id] = {
                "name": query_info.get("name", f"Query {i+1}"),
                "sql": query_info.get("sql", ""),
                "data": data if isinstance(data, list) else [],
                "columns": result.get("columns", query_info.get("chart_config", {}).get("data_sample", {}).get("columns", [])),
                "row_count": len(data) if isinstance(data, list) else 0,
                "execution_time": 0,
                "success": len(data) > 0 if isinstance(data, list) else False,
                "error": None,
                "chart_schema": result.get("chart_schema", query_info.get("chart_schema", {})),
                "chart_type": result.get("chart_type", query_info.get("chart_type", "")),
                "reasoning": result.get("reasoning", query_info.get("reasoning", "")),
                "data_source": "existing_thread_component",
                "fallback_used": True
            }
        
        return formatted_results

    async def _generate_data_insights(
        self,
        formatted_results: Dict[str, Any],
        enhanced_context: Dict[str, Any],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Generate insights from the formatted data, with fallback to existing workflow insights"""
        insights = []
        
        if not self._configuration["enable_data_summarization"]:
            return insights
        
        try:
            # Check if we have any successful results with data
            has_successful_data = any(
                result.get("success") and result.get("data") 
                for result in formatted_results.values()
            )
            
            # If no successful data, try to extract existing insights from workflow
            if not has_successful_data:
                logger.info("No successful SQL data found, extracting existing insights from workflow")
                # Extract report queries from enhanced context or use a fallback
                report_queries = enhanced_context.get("original_context", {}).get("queries", [])
                if not report_queries:
                    # Try to reconstruct from formatted_results
                    report_queries = [
                        {"id": query_id, "name": result.get("name", query_id), "chart_config": {}}
                        for query_id, result in formatted_results.items()
                    ]
                
                existing_insights = self._extract_existing_insights_from_workflow(report_queries)
                insights.extend(existing_insights)
                logger.info(f"Added {len(existing_insights)} existing insights from workflow")
            
            # Generate insights from successful data
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
            if not data or not isinstance(data[0], dict):
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
            if not data or len(data) < 2 or not isinstance(data[0], dict):
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
