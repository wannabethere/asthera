import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import re
import copy

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.agents.nodes.writers.alerts_agent import (
    SQLToAlertAgent, 
    SQLAlertRequest, 
    SQLAlertResult,
    MarkdownJsonOutputParser,
)
from app.agents.pipelines.sql_execution import SQLExecutionPipeline
from app.core.dependencies import create_llm_instances_from_settings

logger = logging.getLogger("lexy-ai-service")

# ---------------------------------------------------------------------------
# Static seed data for orchestrator-level LLM validation.
# These are intentionally small and generic; later you can replace them with
# project-specific examples and session history (passed via pipeline config).
# ---------------------------------------------------------------------------

DEFAULT_LLM_VALIDATION_EXAMPLES: List[Dict[str, Any]] = [
    {
        "name": "count_threshold_ok",
        "input": {
            "alert_request": "Alert me when employee_count > 100",
            "sql_analysis": {"metrics": ["employee_count"], "columns": ["employee_count"]},
            "feed_configuration": {
                "metric": {"measure": "employee_count", "aggregation": "COUNT"},
                "conditions": [{"condition_type": "threshold_value", "operator": ">", "value": 100}],
                "notification": {"schedule_type": "daily"},
            },
        },
        "expected": {
            "keep": True,
            "score": 0.85,
            "reasons": ["Metric grounded in SQL analysis; numeric threshold; valid operator/schedule."],
        },
    },
    {
        "name": "percent_threshold_ok",
        "input": {
            "alert_request": "Alert me when average risk score > 75%",
            "sql_analysis": {"metrics": ["avg_risk_score"], "columns": ["avg_risk_score"]},
            "feed_configuration": {
                "metric": {"measure": "avg_risk_score", "aggregation": "AVG"},
                "conditions": [{"condition_type": "threshold_value", "operator": ">", "value": 75}],
                "notification": {"schedule_type": "daily"},
            },
        },
        "expected": {
            "keep": True,
            "score": 0.75,
            "reasons": ["Percent-style threshold mapped to numeric value; metric present in analysis."],
        },
    },
    {
        "name": "non_numeric_threshold_reject",
        "input": {
            "alert_request": "Alert me when avg time spent > (SELECT AVG(timeSpent) FROM Transcript_csod)",
            "sql_analysis": {"metrics": ["avg_time_spent"], "columns": ["timeSpent"]},
            "feed_configuration": {
                "metric": {"measure": "avg_time_spent", "aggregation": "AVG"},
                "conditions": [{"condition_type": "threshold_value", "operator": ">", "value": "(SELECT AVG(timeSpent) FROM Transcript_csod)"}],
                "notification": {"schedule_type": "daily"},
            },
        },
        "expected": {
            "keep": False,
            "score": 0.2,
            "reasons": ["Threshold is not numeric (SQL expression)"],
        },
    },
]

DEFAULT_LLM_VALIDATION_HISTORY: List[Dict[str, Any]] = [
    {
        "role": "system",
        "content": "Seed history placeholder. Replace with real per-session history later.",
    }
]


class AlertOrchestratorPipeline(AgentPipeline):
    """Orchestrator pipeline that coordinates alert/feed generation from SQL queries and natural language requests"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        alert_agent: Optional[SQLToAlertAgent] = None,
        llm_settings: Optional[Dict[str, Any]] = None,
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
            "enable_sql_analysis": True,
            "enable_alert_generation": True,
            "enable_critique": True,
            "enable_refinement": True,
            "enable_validation": True,
            "enable_metrics": True,
            "default_confidence_threshold": 0.8,
            "enable_sample_data_fetch": True,
            "sample_data_limit": 10,
            # Use LLM to split multi-condition alert requests into sub-requests
            "enable_llm_alert_request_split": True,
            "max_alert_request_splits": 5,
            # Optional orchestrator-level LLM validation (in addition to the agent's internal critique/confidence)
            "enable_llm_validation": False,
            "llm_validation_only_when_below_threshold": True,
            "llm_validation_keep_threshold": 0.6,
            # Hooks for evaluation later
            "llm_validation_examples": copy.deepcopy(DEFAULT_LLM_VALIDATION_EXAMPLES),
            "llm_validation_history": copy.deepcopy(DEFAULT_LLM_VALIDATION_HISTORY),
        }
        
        self._metrics = {}
        self._engine = engine
        
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
            
            sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm = create_llm_instances_from_settings(llm_settings)
            
            self._alert_agent = SQLToAlertAgent(
                sql_parser_llm=sql_parser_llm,
                alert_generator_llm=alert_generator_llm,
                critic_llm=critic_llm,
                refiner_llm=refiner_llm
            )
        else:
            self._alert_agent = alert_agent
        
        # Initialize SQL execution pipeline if not provided
        if not sql_execution_pipeline:
            self._sql_execution_pipeline = SQLExecutionPipeline(
                name="sql_execution_for_alerts",
                version="1.0.0",
                description="SQL execution pipeline for fetching sample data for alert generation",
                llm=llm,
                retrieval_helper=retrieval_helper,
                engine=engine
            )
        else:
            self._sql_execution_pipeline = sql_execution_pipeline
        
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
        sql_queries: List[str],
        natural_language_query: str,
        alert_request: str,
        project_id: str,
        data_description: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Orchestrate the complete alert/feed generation workflow
        
        Args:
            sql_queries: List of SQL queries to analyze for alert generation
            natural_language_query: Natural language description of the queries
            alert_request: Natural language description of the desired alert
            project_id: Project identifier
            data_description: Optional description of the data being analyzed
            session_id: Optional session identifier for tracking
            additional_context: Additional context for alert generation
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing complete alert results with feed configurations
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not sql_queries or not isinstance(sql_queries, list):
            raise ValueError("SQL queries must be a non-empty list")
        
        if not natural_language_query or not alert_request:
            raise ValueError("Natural language query and alert request are required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "alert_orchestration_started",
            {
                "project_id": project_id,
                "total_queries": len(sql_queries),
                "session_id": session_id,
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            alert_results = []
            alert_result_group_keys: List[str] = []
            alert_result_requests: List[str] = []
            alert_result_input_by_id: Dict[int, Dict[str, Any]] = {}
            combined_sql_analysis = None
            any_split = False
            
            # Step 1: Process each SQL query for alert generation
            for i, sql_query in enumerate(sql_queries):
                self._send_status_update(
                    status_callback,
                    "sql_analysis_started",
                    {
                        "project_id": project_id,
                        "query_index": i,
                        "total_queries": len(sql_queries)
                    }
                )
                
                # Fetch sample data for this SQL query
                sample_data = None
                if self._configuration.get("enable_sample_data_fetch", True):
                    self._send_status_update(
                        status_callback,
                        "sample_data_fetch_started",
                        {
                            "project_id": project_id,
                            "query_index": i
                        }
                    )
                    
                    sample_data = await self._fetch_sample_data(sql_query, project_id, **kwargs)
                    
                    self._send_status_update(
                        status_callback,
                        "sample_data_fetch_completed",
                        {
                            "project_id": project_id,
                            "query_index": i,
                            "sample_data_available": sample_data is not None,
                            "sample_size": len(sample_data.get("data", [])) if sample_data else 0
                        }
                    )
                
                # Split the alert request into multiple sub-requests when the user specifies multiple conditions
                # (e.g., "X > 100 OR Y > 75%"). This allows generating separate alert configurations per metric.
                sub_requests = await self._split_alert_request(
                    alert_request=alert_request,
                    sql_query=sql_query,
                    natural_language_query=natural_language_query,
                )
                if len(sub_requests) > 1:
                    any_split = True
                if len(sub_requests) > 1:
                    self._send_status_update(
                        status_callback,
                        "alert_request_split",
                        {"project_id": project_id, "query_index": i, "sub_requests": sub_requests},
                    )

                # Generate alert configuration(s)
                if self._configuration["enable_alert_generation"]:
                    for j, sub_alert_request in enumerate(sub_requests):
                        alert_request_obj = SQLAlertRequest(
                            sql=sql_query,
                            query=natural_language_query,
                            project_id=project_id,
                            data_description=data_description,
                            configuration=additional_context,
                            alert_request=sub_alert_request,
                            session_id=f"{session_id}_{i}_{j}" if session_id else None,
                            sample_data=sample_data,
                        )

                        alert_result = await self._alert_agent.generate_alert(alert_request_obj)

                        # Check if clarification is needed
                        if alert_result.clarification and alert_result.clarification.needs_clarification:
                            self._send_status_update(
                                status_callback,
                                "clarification_required",
                                {
                                    "project_id": project_id,
                                    "query_index": i,
                                    "sub_request_index": j,
                                    "clarification_questions": alert_result.clarification.clarification_questions,
                                    "ambiguous_elements": alert_result.clarification.ambiguous_elements,
                                    "suggested_improvements": alert_result.clarification.suggested_improvements,
                                },
                            )
                            # Return clarification response immediately
                            return {
                                "status": "clarification_required",
                                "project_id": project_id,
                                "query_index": i,
                                "sub_request_index": j,
                                "clarification": {
                                    "questions": alert_result.clarification.clarification_questions,
                                    "ambiguous_elements": alert_result.clarification.ambiguous_elements,
                                    "suggested_improvements": alert_result.clarification.suggested_improvements,
                                },
                                "alert_results": [],
                                "sql_analysis": None,
                                "execution_time": (datetime.now() - start_time).total_seconds(),
                            }

                        alert_results.append(alert_result)
                        alert_result_group_keys.append(f"{i}:{j}")
                        alert_result_requests.append(sub_alert_request)
                        alert_result_input_by_id[id(alert_result)] = {
                            "sql": sql_query,
                            "natural_language_query": natural_language_query,
                            "alert_request": sub_alert_request,
                            "project_id": project_id,
                            "query_index": i,
                            "sub_request_index": j,
                            "data_description": data_description,
                        }

                        # Combine SQL analysis from multiple generated alerts
                        if combined_sql_analysis is None:
                            combined_sql_analysis = alert_result.sql_analysis
                        else:
                            combined_sql_analysis = self._merge_sql_analyses(
                                combined_sql_analysis,
                                alert_result.sql_analysis,
                            )

                        self._send_status_update(
                            status_callback,
                            "sql_analysis_completed",
                            {
                                "project_id": project_id,
                                "query_index": i,
                                "sub_request_index": j,
                                "confidence_score": alert_result.confidence_score,
                                "alert_type": alert_result.feed_configuration.conditions[0].condition_type.value
                                if alert_result.feed_configuration and alert_result.feed_configuration.conditions
                                else "unknown",
                            },
                        )
                else:
                    # Skip alert generation if disabled
                    self._send_status_update(
                        status_callback,
                        "sql_analysis_skipped",
                        {
                            "project_id": project_id,
                            "query_index": i,
                            "reason": "alert_generation_disabled"
                        }
                    )
            
            # Step 2: Validate and refine results if needed
            if self._configuration["enable_validation"] and alert_results:
                self._send_status_update(
                    status_callback,
                    "alert_validation_started",
                    {"project_id": project_id, "total_alerts": len(alert_results)}
                )
                
                validated_results = await self._validate_alert_results(
                    alert_results, 
                    project_id, 
                    status_callback,
                    group_keys=alert_result_group_keys if any_split else None,
                    alert_requests=alert_result_requests if any_split else None,
                    natural_language_query=natural_language_query,
                )
                # If everything was filtered out by confidence, keep the best candidate instead of returning zero alerts.
                if not validated_results and alert_results:
                    best = max(alert_results, key=lambda r: r.confidence_score)
                    validated_results = [best]
                    self._send_status_update(
                        status_callback,
                        "alert_validation_all_filtered_using_best",
                        {
                            "project_id": project_id,
                            "best_confidence_score": best.confidence_score,
                            "threshold": self._configuration.get("default_confidence_threshold", 0.8),
                        },
                )
                
                self._send_status_update(
                    status_callback,
                    "alert_validation_completed",
                    {
                        "project_id": project_id,
                        "validated_alerts": len(validated_results),
                        "filtered_alerts": len(alert_results) - len(validated_results)
                    }
                )
            else:
                validated_results = alert_results
            
            # Step 3: Generate combined feed configurations
            combined_feed_configs = self._generate_combined_feed_configurations(
                validated_results, 
                project_id
            )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                total_queries=len(sql_queries),
                total_alerts=len(validated_results),
                execution_time=total_execution_time,
                project_id=project_id,
                average_confidence=sum(r.confidence_score for r in validated_results) / len(validated_results) if validated_results else 0.0
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "alert_orchestration_completed",
                {
                    "project_id": project_id,
                    "execution_time": total_execution_time,
                    "total_alerts_generated": len(validated_results),
                    "average_confidence": sum(r.confidence_score for r in validated_results) / len(validated_results) if validated_results else 0.0
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": True,
                    "alert_results": [
                        self._alert_result_to_dict(result, alert_result_input_by_id.get(id(result)))
                        for result in validated_results
                    ],
                    "combined_feed_configurations": combined_feed_configs,
                    "combined_sql_analysis": combined_sql_analysis.dict() if combined_sql_analysis else None,
                    "orchestration_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "total_queries_processed": len(sql_queries),
                        "total_alerts_generated": len(validated_results),
                        "average_confidence_score": sum(r.confidence_score for r in validated_results) / len(validated_results) if validated_results else 0.0,
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
            logger.error(f"Error in alert orchestration pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "alert_orchestration_error",
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

    def _split_alert_request_regex(self, alert_request: str) -> List[str]:
        """Split a single alert_request into multiple sub-requests when it contains OR clauses.

        This is intentionally simple: it preserves the user's wording but isolates each clause
        so the agent can pick the correct metric + threshold without mixing multiple metrics
        into one feed configuration.
        """
        if not alert_request or not isinstance(alert_request, str):
            return [alert_request]

        # Normalize spacing but keep original content
        text = alert_request.strip()
        if not text:
            return [alert_request]

        # Detect a common "instruction prefix" like "Alert me when" so we can
        # ensure each split clause remains a complete, standalone instruction.
        prefix_including_when: Optional[str] = None
        m = re.match(r"^(.*?\bwhen\b)\s+", text, flags=re.IGNORECASE)
        if m:
            prefix_including_when = m.group(1).strip()

        # Split on standalone "or" (case-insensitive). We do not split on "and" because
        # AND is often intended as multiple conditions on the same metric.
        parts = re.split(r"\s+\bor\b\s+", text, flags=re.IGNORECASE)
        cleaned_parts: List[str] = []
        for p in parts:
            if not p:
                continue
            s = p.strip().strip(" .;")
            if not s:
                continue

            # Remove leading "either" (common pattern: "either X or Y")
            s = re.sub(r"^\s*either\s+", "", s, flags=re.IGNORECASE).strip()

            # Trim surrounding parentheses, e.g. "(A > 1)" -> "A > 1"
            while s.startswith("(") and s.endswith(")") and len(s) > 2:
                s = s[1:-1].strip()

            # If the first clause includes the full instruction but subsequent clauses don't,
            # make them complete by reusing the prefix (e.g. "Alert me when").
            if prefix_including_when:
                s_lower = s.lower()
                if not s_lower.startswith(prefix_including_when.lower()):
                    if s_lower.startswith("when "):
                        # "when X" -> "<prefix before when> when X" is tricky; simplest and safe:
                        # if prefix is "Alert me when", replace by "Alert me " + "when X"
                        # by removing trailing "when" from the prefix.
                        prefix_before_when = re.sub(r"\bwhen\b\s*$", "", prefix_including_when, flags=re.IGNORECASE).strip()
                        if prefix_before_when:
                            s = f"{prefix_before_when} {s}"
                    else:
                        s = f"{prefix_including_when} {s}"

            cleaned_parts.append(s.strip(" .;"))

        # De-duplicate while preserving order
        deduped: List[str] = []
        seen = set()
        for s in cleaned_parts:
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(s)

        return deduped if deduped else [alert_request]

    async def _split_alert_request(self, alert_request: str, sql_query: str, natural_language_query: str) -> List[str]:
        """LLM-based splitter for alert_request with regex fallback."""
        if not alert_request or not isinstance(alert_request, str):
            return [alert_request]

        text = alert_request.strip()
        if not text:
            return [alert_request]

        if not self._configuration.get("enable_llm_alert_request_split", True):
            return self._split_alert_request_regex(alert_request)

        # If there's no OR, avoid an LLM call and keep the request intact.
        if re.search(r"\bor\b", text, flags=re.IGNORECASE) is None:
            return [text]

        max_splits = int(self._configuration.get("max_alert_request_splits", 5) or 5)
        if max_splits < 1:
            max_splits = 1

        try:
            system_msg = SystemMessage(
                content=(
                    "You split alert requests into separate sub-requests.\n"
                    "Return ONLY valid JSON with schema: {\"sub_requests\": [\"...\", \"...\"]}.\n"
                    "Rules:\n"
                    "- Split ONLY on OR semantics.\n"
                    "- Do NOT split on AND.\n"
                    "- Each sub_request must be a complete instruction, ideally starting with 'Alert me when ...'.\n"
                    "- Preserve thresholds exactly (numbers/percents); do not invent values.\n"
                    "- If the request does not contain multiple OR clauses, return a single-item list with the original request.\n"
                    f"- Return at most {max_splits} sub_requests.\n"
                )
            )
            user_msg = HumanMessage(
                content=(
                    f"SQL context (do not copy into output):\n{sql_query}\n\n"
                    f"Natural language query context:\n{natural_language_query}\n\n"
                    f"Alert request:\n{text}\n\n"
                    "Return JSON now."
                )
            )

            msg = await self._llm.ainvoke([system_msg, user_msg])
            content = msg.content if isinstance(msg, AIMessage) else getattr(msg, "content", str(msg))

            parsed = MarkdownJsonOutputParser().parse(content)
            sub_requests = parsed.get("sub_requests")
            if isinstance(sub_requests, str):
                sub_requests = [sub_requests]
            if not isinstance(sub_requests, list):
                raise ValueError("LLM did not return `sub_requests` list")

            cleaned: List[str] = []
            for s in sub_requests:
                if s is None:
                    continue
                st = str(s).strip()
                if st:
                    cleaned.append(st)

            if not cleaned:
                raise ValueError("LLM returned empty sub_requests")

            cleaned = cleaned[:max_splits]
            if len(cleaned) == 1:
                return [text]
            return cleaned

        except Exception as e:
            logger.warning(f"LLM split failed; falling back to regex split. Error: {e}")
            return self._split_alert_request_regex(alert_request)

    def _merge_sql_analyses(self, analysis1, analysis2):
        """Merge two SQL analysis objects"""
        from app.agents.nodes.writers.alerts_agent import SQLAnalysis
        
        return SQLAnalysis(
            tables=list(set(analysis1.tables + analysis2.tables)),
            columns=list(set(analysis1.columns + analysis2.columns)),
            metrics=list(set(analysis1.metrics + analysis2.metrics)),
            dimensions=list(set(analysis1.dimensions + analysis2.dimensions)),
            filters=analysis1.filters + analysis2.filters,
            aggregations=analysis1.aggregations + analysis2.aggregations
        )

    async def _validate_alert_results(
        self, 
        alert_results: List[SQLAlertResult], 
        project_id: str,
        status_callback: Optional[Callable],
        group_keys: Optional[List[str]] = None,
        alert_requests: Optional[List[str]] = None,
        natural_language_query: Optional[str] = None,
    ) -> List[SQLAlertResult]:
        """Validate alert results based on confidence threshold and other criteria"""
        
        confidence_threshold = self._configuration.get("default_confidence_threshold", 0.6)
        validated_results: List[SQLAlertResult] = []
        enable_llm_validation = bool(self._configuration.get("enable_llm_validation", False))
        only_when_below = bool(self._configuration.get("llm_validation_only_when_below_threshold", True))
        keep_threshold = float(self._configuration.get("llm_validation_keep_threshold", 0.6) or 0.6)

        async def llm_keep(i: int, r: SQLAlertResult) -> bool:
            if not enable_llm_validation:
                return False
            if only_when_below and r.confidence_score >= confidence_threshold:
                return False

            req = None
            if alert_requests and i < len(alert_requests):
                req = alert_requests[i]

            verdict = await self._llm_validate_alert_result(
                result=r,
                alert_request=req,
                natural_language_query=natural_language_query,
            )

            score = float(verdict.get("score", 0.0) or 0.0)
            keep = bool(verdict.get("keep", False)) or score >= keep_threshold
            self._send_status_update(
                status_callback,
                "llm_validation_result",
                {
                    "project_id": project_id,
                    "alert_index": i,
                    "keep": keep,
                    "score": score,
                    "reasons": verdict.get("reasons", []),
                },
            )
            return keep

        # If we have group_keys (used for multi-clause split requests), ensure we keep at least one result per group.
        if group_keys and len(group_keys) == len(alert_results):
            groups: Dict[str, List[tuple[int, SQLAlertResult]]] = {}
            for idx, (k, r) in enumerate(zip(group_keys, alert_results)):
                groups.setdefault(k, []).append((idx, r))

            kept_indices: set[int] = set()
            for k, items in groups.items():
                above = [(idx, r) for idx, r in items if r.confidence_score >= confidence_threshold]
                if above:
                    for idx, _r in above:
                        kept_indices.add(idx)
                else:
                    # Try LLM validation first; if any pass, keep the best passing.
                    passing: List[tuple[int, SQLAlertResult]] = []
                    if enable_llm_validation:
                        for idx, r in items:
                            if await llm_keep(idx, r):
                                passing.append((idx, r))

                    if passing:
                        idx_best, best = max(passing, key=lambda t: t[1].confidence_score)
                        kept_indices.add(idx_best)
                    else:
                        idx_best, best = max(items, key=lambda t: t[1].confidence_score)
                        kept_indices.add(idx_best)
                    self._send_status_update(
                        status_callback,
                        "alert_group_kept_best_low_confidence",
                        {
                            "project_id": project_id,
                            "group_key": k,
                            "best_confidence_score": best.confidence_score,
                            "threshold": confidence_threshold,
                        },
                    )

            for idx in sorted(kept_indices):
                validated_results.append(alert_results[idx])

            # Emit low-confidence status updates for any kept result under threshold (visibility, not filtering)
            for idx in sorted(kept_indices):
                r = alert_results[idx]
                if r.confidence_score < confidence_threshold:
                    self._send_status_update(
                        status_callback,
                        "alert_kept_low_confidence_due_to_group",
                        {
                            "project_id": project_id,
                            "alert_index": idx,
                            "confidence_score": r.confidence_score,
                            "threshold": confidence_threshold,
                        },
                    )

            return validated_results
        
        for i, result in enumerate(alert_results):
            # Check confidence threshold
            if result.confidence_score >= confidence_threshold:
                validated_results.append(result)
            else:
                # Orchestrator-level LLM validation can keep low-confidence results
                if await llm_keep(i, result):
                    validated_results.append(result)
                    continue
                self._send_status_update(
                    status_callback,
                    "alert_filtered_low_confidence",
                    {
                        "project_id": project_id,
                        "alert_index": i,
                        "confidence_score": result.confidence_score,
                        "threshold": confidence_threshold
                    }
                )
        
        return validated_results

    async def _llm_validate_alert_result(
        self,
        result: SQLAlertResult,
        alert_request: Optional[str],
        natural_language_query: Optional[str],
    ) -> Dict[str, Any]:
        """Orchestrator-level LLM validation hook.

        Intentionally extensible: you can feed examples/history later via config.
        """
        if not result.feed_configuration or not result.sql_analysis:
            return {"keep": False, "score": 0.0, "reasons": ["Missing feed_configuration or sql_analysis"]}

        examples = self._configuration.get("llm_validation_examples") or []
        history = self._configuration.get("llm_validation_history") or []

        system_msg = SystemMessage(
            content=(
                "You validate generated alert configurations.\n"
                "Return ONLY valid JSON with schema:\n"
                "{\n"
                '  \"keep\": true|false,\n'
                '  \"score\": 0.0-1.0,\n'
                '  \"reasons\": [\"...\"],\n'
                '  \"suggested_changes\": [\"...\"]\n'
                "}\n"
                "Be strict about:\n"
                "- Threshold conditions must have numeric values\n"
                "- Metric/measure should be grounded in SQL analysis metrics/columns\n"
                "- Schedule type should be one of daily/weekly/monthly/quarterly/yearly/custom/never\n"
            )
        )

        payload = {
            "natural_language_query": natural_language_query,
            "alert_request": alert_request,
            "sql_analysis": result.sql_analysis.dict(),
            "feed_configuration": result.feed_configuration.dict(),
            "critic_confidence_score": result.confidence_score,
            "critic_notes": result.critique_notes,
            "critic_suggestions": result.suggestions,
            "examples": examples,
            "history": history,
        }

        user_msg = HumanMessage(content=f"Validate:\n{payload}\n\nReturn JSON now.")
        msg = await self._llm.ainvoke([system_msg, user_msg])
        content = msg.content if isinstance(msg, AIMessage) else getattr(msg, "content", str(msg))
        parsed = MarkdownJsonOutputParser().parse(content)

        keep = bool(parsed.get("keep", False))
        try:
            score = float(parsed.get("score", 0.0) or 0.0)
        except Exception:
            score = 0.0
        reasons = parsed.get("reasons", [])
        if isinstance(reasons, str):
            reasons = [reasons]
        suggested_changes = parsed.get("suggested_changes", [])
        if isinstance(suggested_changes, str):
            suggested_changes = [suggested_changes]

        return {
            "keep": keep,
            "score": max(0.0, min(1.0, score)),
            "reasons": reasons if isinstance(reasons, list) else [],
            "suggested_changes": suggested_changes if isinstance(suggested_changes, list) else [],
        }

    def _generate_combined_feed_configurations(
        self, 
        alert_results: List[SQLAlertResult], 
        project_id: str
    ) -> Dict[str, Any]:
        """Generate combined feed configurations from multiple alert results"""
        
        if not alert_results:
            return {"feeds": [], "summary": "No alerts generated"}
        
        # Group alerts by condition type
        alerts_by_type = {}
        for result in alert_results:
            if result.feed_configuration and result.feed_configuration.conditions:
                # Use the first condition for grouping
                condition_type = result.feed_configuration.conditions[0].condition_type.value
                if condition_type not in alerts_by_type:
                    alerts_by_type[condition_type] = []
                alerts_by_type[condition_type].append(result)
        
        # Create combined configurations
        combined_configs = {
            "feeds": [],
            "summary": {
                "total_feeds": len(alert_results),
                "condition_types": list(alerts_by_type.keys()),
                "average_confidence": sum(r.confidence_score for r in alert_results) / len(alert_results)
            }
        }
        
        # Convert each alert result to API payload format
        for result in alert_results:
            api_payload = self._alert_agent.create_lexy_api_payload(result)
            combined_configs["feeds"].append(api_payload)
        
        return combined_configs

    def _alert_result_to_dict(self, result: SQLAlertResult, input_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Convert SQLAlertResult to dictionary format"""
        out: Dict[str, Any] = {
            "feed_configuration": result.feed_configuration.dict() if result.feed_configuration else None,
            "sql_analysis": result.sql_analysis.dict() if result.sql_analysis else None,
            "confidence_score": result.confidence_score,
            "critique_notes": result.critique_notes,
            "suggestions": result.suggestions,
        }
        if input_context:
            out["input"] = input_context
        return out

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
        logger.info(f"Alert Orchestrator Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        total_queries: int,
        total_alerts: int,
        execution_time: float,
        project_id: str,
        average_confidence: float
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "total_queries": total_queries,
                "total_alerts": total_alerts,
                "execution_time": execution_time,
                "project_id": project_id,
                "average_confidence": average_confidence,
                "timestamp": datetime.now().isoformat()
            },
            "total_executions": self._metrics.get("total_executions", 0) + 1,
            "total_queries_processed": self._metrics.get("total_queries_processed", 0) + total_queries,
            "total_alerts_generated": self._metrics.get("total_alerts_generated", 0) + total_alerts,
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
            "alert_agent_available": self._alert_agent is not None,
            "timestamp": datetime.now().isoformat()
        }

    def enable_sql_analysis(self, enabled: bool) -> None:
        """Enable or disable SQL analysis"""
        self._configuration["enable_sql_analysis"] = enabled
        logger.info(f"SQL analysis {'enabled' if enabled else 'disabled'}")

    def enable_alert_generation(self, enabled: bool) -> None:
        """Enable or disable alert generation"""
        self._configuration["enable_alert_generation"] = enabled
        logger.info(f"Alert generation {'enabled' if enabled else 'disabled'}")

    def enable_validation(self, enabled: bool) -> None:
        """Enable or disable validation"""
        self._configuration["enable_validation"] = enabled
        logger.info(f"Validation {'enabled' if enabled else 'disabled'}")

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold for alert validation"""
        if 0.0 <= threshold <= 1.0:
            self._configuration["default_confidence_threshold"] = threshold
            logger.info(f"Confidence threshold set to {threshold}")
        else:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")

    def enable_sample_data_fetch(self, enabled: bool) -> None:
        """Enable or disable sample data fetching for alert generation"""
        self._configuration["enable_sample_data_fetch"] = enabled
        logger.info(f"Sample data fetch {'enabled' if enabled else 'disabled'}")

    def set_sample_data_limit(self, limit: int) -> None:
        """Set the limit for sample data rows to fetch"""
        if limit > 0:
            self._configuration["sample_data_limit"] = limit
            logger.info(f"Sample data limit set to {limit}")
        else:
            raise ValueError("Sample data limit must be greater than 0")

    async def _fetch_sample_data(self, sql_query: str, project_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch sample data from SQL query execution"""
        if not self._configuration.get("enable_sample_data_fetch", True):
            return None
        
        try:
            # Clean the SQL query first to remove any wrapping text
            from app.core.engine import clean_generation_result
            cleaned_sql = clean_generation_result(sql_query)
            
            # Create a sample SQL query with LIMIT
            sample_limit = self._configuration.get("sample_data_limit", 10)
            
            # Check if the SQL already has a LIMIT clause
            if 'LIMIT' in cleaned_sql.upper():
                # If it already has a LIMIT, use the original query
                sample_sql = cleaned_sql
            else:
                # Add LIMIT to the cleaned SQL
                sample_sql = f"{cleaned_sql} LIMIT {sample_limit}"
            
            logger.info(f"Executing sample data query: {sample_sql[:100]}...")
            
            # Execute the sample query
            result = await self._sql_execution_pipeline.run(
                sql=sample_sql,
                project_id=project_id,
                configuration={"dry_run": False},
                **kwargs
            )
            
            if result.get("post_process", {}).get("data"):
                data = result["post_process"]["data"]
                if data:
                    # Convert to the format expected by the alert agent
                    columns = list(data[0].keys()) if data else []
                    
                    # Add additional metadata for better SQL parsing
                    sample_data = {
                        "columns": columns,
                        "data": data,
                        "row_count": len(data),
                        "sample_limit": sample_limit,
                        "original_sql": sql_query,
                        "cleaned_sql": cleaned_sql,
                        "executed_sql": sample_sql
                    }
                    
                    logger.info(f"Successfully fetched {len(data)} sample rows with columns: {columns}")
                    return sample_data
            
            logger.warning("No data returned from sample query")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to fetch sample data for alert generation: {str(e)}")
            return None


# Factory function for creating alert orchestrator pipeline
def create_alert_orchestrator_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    alert_agent: Optional[SQLToAlertAgent] = None,
    llm_settings: Optional[Dict[str, Any]] = None,
    sql_execution_pipeline: Optional[SQLExecutionPipeline] = None,
    **kwargs
) -> AlertOrchestratorPipeline:
    """
    Factory function to create an alert orchestrator pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        alert_agent: SQL-to-Alert agent instance (optional, will create default if not provided)
        llm_settings: LLM configuration settings (optional, will use defaults if not provided)
        sql_execution_pipeline: SQL execution pipeline instance (optional, will create default if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        AlertOrchestratorPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return AlertOrchestratorPipeline(
        name="alert_orchestrator_pipeline",
        version="1.0.0",
        description="Orchestrator pipeline that coordinates alert/feed generation from SQL queries and natural language requests",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        alert_agent=alert_agent,
        llm_settings=llm_settings,
        sql_execution_pipeline=sql_execution_pipeline,
        **kwargs
    )
