import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime

import orjson
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent import AgentExecutor
from langchain.agents import Tool

from app.core.engine import Engine
from app.core.provider import EmbedderProvider, DocumentStoreProvider, get_embedder
from app.core.dependencies import get_llm

# Import all the converted tools (existing imports)
from app.agents.nodes.sql.chart_adjustment import (
    ChartAdjustment,
    create_chart_adjustment_tool,
)
from app.agents.nodes.sql.followup_sql_generation_reasoning import (
    FollowUpSQLGenerationReasoning,
    create_followup_sql_reasoning_tool,
)
from app.agents.nodes.sql.followup_sql_generation import (
    FollowUpSQLGeneration,
    create_followup_sql_generation_tool,
)
from app.agents.nodes.sql.intent_classification import (
    IntentClassification,
    create_intent_classification_tool,
)
from app.agents.nodes.sql.misleading_assistance import (
    MisleadingAssistance,
    create_misleading_assistance_tool,
)
from app.agents.nodes.sql.relationship_recommendation import (
    RelationshipRecommendation,
    create_relationship_recommendation_tool
)
from app.agents.nodes.sql.semantics_description import (
    SemanticsDescription,
    create_semantics_description_tool
)

# Import the SQL RAG system
from app.agents.nodes.sql.sql_pipeline import (
    SQLPipeline,
    SQLPipelineFactory,
    SQLRequest,
    SQLResult,
)

# Import the Enhanced SQL RAG components
from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
from app.agents.nodes.sql.scoring_sql_rag_agent import EnhancedSQLRAGAgent
from app.agents.retrieval.retrieval_helper import RetrievalHelper

# Import the new pipeline implementations
from app.agents.pipelines.sql_pipelines import (
    SQLGenerationPipeline,
    SQLBreakdownPipeline,
    SQLReasoningPipeline,
    SQLCorrectionPipeline,
    SQLExpansionPipeline,
    ChartAdjustmentPipeline,
    FollowUpSQLReasoningPipeline,
    FollowUpSQLGenerationPipeline,
    IntentClassificationPipeline,
    MisleadingAssistancePipeline,
    RelationshipRecommendationPipeline,
    SemanticsDescriptionPipeline
)

from app.agents.pipelines.pipeline_container import PipelineContainer

logger = logging.getLogger("lexy-ai-service")


class PipelineType(Enum):
    """Available pipeline types"""
    SQL_GENERATION = "sql_generation"
    SQL_BREAKDOWN = "sql_breakdown"
    SQL_REASONING = "sql_reasoning"
    SQL_ANSWER = "sql_answer"
    SQL_CORRECTION = "sql_correction"
    SQL_EXPANSION = "sql_expansion"
    SQL_GENERATE_TRANSFORM = "sql_generate_transform"
    CHART_ADJUSTMENT = "chart_adjustment"
    FOLLOWUP_SQL_REASONING = "followup_sql_reasoning"
    FOLLOWUP_SQL_GENERATION = "followup_sql_generation"
    INTENT_CLASSIFICATION = "intent_classification"
    MISLEADING_ASSISTANCE = "misleading_assistance"
    RELATIONSHIP_RECOMMENDATION = "relationship_recommendation"
    SEMANTICS_DESCRIPTION = "semantics_description"


@dataclass
class RelevanceScoring:
    """Relevance scoring information"""
    enabled: bool = False
    final_score: float = 0.0
    quality_level: str = "unknown"
    reasoning_components: Dict[str, float] = field(default_factory=dict)
    sql_components: Dict[str, float] = field(default_factory=dict)
    improvement_recommendations: List[str] = field(default_factory=list)
    detected_operation_type: str = "unknown"
    attempt_number: int = 1
    processing_time_seconds: float = 0.0


@dataclass
class PipelineRequest:
    """Universal pipeline request structure"""
    pipeline_type: PipelineType
    query: str = ""
    language: str = "English"
    contexts: List[str] = None
    project_id: str = None
    timeout: float = 30.0
    additional_params: Dict[str, Any] = None
    # Enhanced parameters
    enable_scoring: bool = True
    max_improvement_attempts: int = 3
    quality_threshold: float = 0.6
    schema_context: Dict[str, Any] = None


@dataclass
class PipelineResult:
    """Universal pipeline result structure with scoring"""
    pipeline_type: PipelineType
    success: bool
    data: Dict[str, Any] = None
    error: str = None
    metadata: Dict[str, Any] = None
    # Enhanced scoring information
    relevance_scoring: RelevanceScoring = field(default_factory=lambda: RelevanceScoring())
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EnhancedSQLPipelineWrapper:
    """Wrapper that integrates pipeline implementations with enhanced scoring"""
    
    def __init__(
        self,
        engine: Engine,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        document_store_provider: DocumentStoreProvider = None,
        enable_scoring: bool = True,
        relevance_scorer: SQLAdvancedRelevanceScorer = None
    ):
        self.engine = engine
        self.llm = llm
        self.retrieval_helper = retrieval_helper
        self.document_store_provider = document_store_provider
        self.enable_scoring = enable_scoring
        self.relevance_scorer = relevance_scorer or SQLAdvancedRelevanceScorer()
        
        # Initialize pipeline container
        self.pipeline_container = PipelineContainer.initialize()
        
        # Performance tracking
        self.performance_metrics = {
            "total_queries": 0,
            "high_quality_queries": 0,
            "average_score": 0.0,
            "score_history": []
        }
    
    def _get_pipeline(self, pipeline_type: PipelineType) -> Any:
        """Get pipeline from container based on type"""
        pipeline_map = {
            PipelineType.SQL_GENERATION: "sql_generation",
            PipelineType.SQL_BREAKDOWN: "sql_breakdown",
            PipelineType.SQL_REASONING: "sql_reasoning",
            PipelineType.SQL_CORRECTION: "sql_correction",
            PipelineType.SQL_EXPANSION: "sql_expansion",
            PipelineType.SQL_GENERATE_TRANSFORM: "sql_transform",
            PipelineType.CHART_ADJUSTMENT: "chart_adjustment",
            PipelineType.FOLLOWUP_SQL_REASONING: "followup_sql_reasoning",
            PipelineType.FOLLOWUP_SQL_GENERATION: "followup_sql_generation",
            PipelineType.INTENT_CLASSIFICATION: "intent_classification",
            PipelineType.MISLEADING_ASSISTANCE: "misleading_assistance",
            PipelineType.RELATIONSHIP_RECOMMENDATION: "relationship_recommendation",
            PipelineType.SEMANTICS_DESCRIPTION: "semantics_description"
        }
        
        pipeline_name = pipeline_map.get(pipeline_type)
        if not pipeline_name:
            raise ValueError(f"Unsupported pipeline type: {pipeline_type}")
            
        return self.pipeline_container.get_pipeline(pipeline_name)
    
    async def execute_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute a specific pipeline with enhanced scoring"""
        start_time = datetime.now()
        
        try:
            pipeline = self._get_pipeline(request.pipeline_type)
            if not pipeline:
                raise ValueError(f"Pipeline not available: {request.pipeline_type}")
            
            # Prepare pipeline parameters
            params = {
                "query": request.query,
                "language": request.language,
                "contexts": request.contexts,
                "project_id": request.project_id,
                "schema_context": request.schema_context
            }
            
            if request.additional_params:
                params.update(request.additional_params)
            
            logger.info(f"Executing pipeline with params: {params}")
            
            # Execute pipeline
            result = await pipeline.run(**params)
            logger.info(f"Raw pipeline result: {result}")
            
            # Handle SQLGenerationPipeline result structure
            if isinstance(result, dict):
                if result.get("success") is True:
                    # Success case - we have valid data
                    data = result.get("data", {})
                    return PipelineResult(
                        pipeline_type=request.pipeline_type,
                        success=True,
                        data=data,
                        error=None,
                        metadata={
                            "pipeline_type": request.pipeline_type.value,
                            "processing_time": (datetime.now() - start_time).total_seconds(),
                            "operation_type": data.get("operation_type", "generation")
                        },
                        relevance_scoring=RelevanceScoring(
                            enabled=request.enable_scoring,
                            final_score=data.get("final_relevance_score", 0.0),
                            quality_level=data.get("quality_level", "unknown"),
                            processing_time_seconds=(datetime.now() - start_time).total_seconds()
                        )
                    )
                elif result.get("success") is False:
                    # Failure case - we have an error
                    return PipelineResult(
                        pipeline_type=request.pipeline_type,
                        success=False,
                        data=None,
                        error=result.get("error", "No generation results found"),
                        metadata={
                            "pipeline_type": request.pipeline_type.value,
                            "processing_time": (datetime.now() - start_time).total_seconds(),
                            "invalid_sql": result.get("invalid_sql")
                        },
                        relevance_scoring=RelevanceScoring(
                            enabled=request.enable_scoring,
                            processing_time_seconds=(datetime.now() - start_time).total_seconds()
                        )
                    )
            
            # If we get here, the result is in a different format
            # Extract data from result
            result_data = result.get("data", {})
            
            logger.info(f"Result data: {result_data}")
            
            # Create pipeline result with scoring
            scoring = RelevanceScoring(
                enabled=request.enable_scoring,
                final_score=result_data.get("final_relevance_score", 0.0),
                quality_level=result_data.get("quality_level", "unknown"),
                processing_time_seconds=(datetime.now() - start_time).total_seconds()
            )
            
            # Update performance metrics if scoring is enabled
            if request.enable_scoring:
                self._update_performance_metrics(scoring)
            
            # Check if we have a valid SQL result
            has_valid_sql = bool(result_data.get("sql"))
            logger.info(f"Has valid SQL: {has_valid_sql}")
            
            pipeline_result = PipelineResult(
                pipeline_type=request.pipeline_type,
                success=has_valid_sql,
                data=result_data if has_valid_sql else None,
                error="No generation results found" if not has_valid_sql else None,
                metadata={
                    "pipeline_type": request.pipeline_type.value,
                    "processing_time": scoring.processing_time_seconds,
                    "operation_type": result_data.get("operation_type", "generation")
                },
                relevance_scoring=scoring
            )
            
            logger.info(f"Final pipeline result: {pipeline_result}")
            return pipeline_result
            
        except Exception as e:
            logger.error(f"Error executing pipeline {request.pipeline_type.value}: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e),
                relevance_scoring=RelevanceScoring(enabled=request.enable_scoring)
            )
    
    def _update_performance_metrics(self, scoring: RelevanceScoring):
        """Update performance tracking metrics"""
        self.performance_metrics["total_queries"] += 1
        
        final_score = scoring.final_score
        self.performance_metrics["score_history"].append(final_score)
        
        # Update average score
        scores = self.performance_metrics["score_history"]
        self.performance_metrics["average_score"] = sum(scores) / len(scores)
        
        # Update high quality count (threshold: 0.6)
        if final_score >= 0.6:
            self.performance_metrics["high_quality_queries"] += 1
    
    def get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics"""
        return {
            "total_queries": self.performance_metrics["total_queries"],
            "high_quality_queries": self.performance_metrics["high_quality_queries"],
            "average_score": self.performance_metrics["average_score"],
            "score_history": self.performance_metrics["score_history"],
            "high_quality_rate": (
                self.performance_metrics["high_quality_queries"] / 
                self.performance_metrics["total_queries"] 
                if self.performance_metrics["total_queries"] > 0 else 0
            )
        }
    
    def update_schema_context(self, schema_context: Dict[str, Any]):
        """Update schema context for all pipelines"""
        for pipeline in self.pipelines.values():
            if hasattr(pipeline, "update_schema_context"):
                pipeline.update_schema_context(schema_context)


class EnhancedUnifiedPipelineSystem:
    """Enhanced unified system with integrated relevance scoring"""
    
    def __init__(
        self,
        engine: Engine,
        embedder_provider: EmbedderProvider = None,
        document_store_provider: DocumentStoreProvider = None,
        use_rag: bool = True,
        enable_sql_scoring: bool = True,
        scoring_config_path: str = None,
        **kwargs
    ):
        self.engine = engine
        self.document_store_provider = document_store_provider
        self.use_rag = use_rag
        self.enable_sql_scoring = enable_sql_scoring
        
        # Initialize LLM and embeddings
        self.llm = get_llm()
        self.embeddings = get_embedder()
        
        # Initialize SQL pipeline
        self.sql_pipeline = SQLPipelineFactory.create_pipeline(
            engine=engine,
            doc_store=document_store_provider,
            use_rag=use_rag,
            embeddings=self.embeddings,
            **kwargs
        )
        
        # Initialize enhanced SQL wrapper with scoring
        self.enhanced_sql_wrapper = None
        if enable_sql_scoring:
            relevance_scorer = SQLAdvancedRelevanceScorer(
                config_file_path=scoring_config_path
            )
            self.enhanced_sql_wrapper = EnhancedSQLPipelineWrapper(
                engine=engine,
                llm=self.llm,
                retrieval_helper=RetrievalHelper(),
                document_store_provider=document_store_provider,
                enable_scoring=True,
                relevance_scorer=relevance_scorer
            )
        
        # Initialize other pipelines
        self.pipelines = self._initialize_pipelines()
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Initialize unified agent
        self.agent = self._initialize_agent()
        
        # Global schema context for scoring
        self.schema_context = {}
    
    def _initialize_pipelines(self) -> Dict[PipelineType, Any]:
        """Initialize all individual pipelines"""
        pipelines = {}
        
        try:
            # Use PipelineContainer to initialize pipelines
            pipeline_container = PipelineContainer.initialize()
            
            # Get all required pipelines
            required_pipelines = [
                PipelineType.CHART_ADJUSTMENT,
                PipelineType.FOLLOWUP_SQL_REASONING,
                PipelineType.FOLLOWUP_SQL_GENERATION,
                PipelineType.MISLEADING_ASSISTANCE,
                PipelineType.RELATIONSHIP_RECOMMENDATION,
                PipelineType.SEMANTICS_DESCRIPTION,
                PipelineType.INTENT_CLASSIFICATION
            ]
            
            # Get each pipeline from the container
            for pipeline_type in required_pipelines:
                try:
                    pipelines[pipeline_type] = pipeline_container.get_pipeline(pipeline_type.value)
                except KeyError as e:
                    logger.warning(f"Pipeline {pipeline_type.value} not found in container: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error initializing pipelines: {e}")
            # Log more detailed error information
            logger.error(f"Error details: {str(e)}")
            logger.error(f"Available pipeline types: {[pt.value for pt in PipelineType]}")
        
        return pipelines
    
    def _initialize_tools(self) -> List[Tool]:
        """Initialize all Langchain tools"""
        tools = []
        
        try:
            tools.append(create_chart_adjustment_tool(self.document_store_provider))
            tools.append(create_followup_sql_reasoning_tool(self.document_store_provider))
            tools.append(create_followup_sql_generation_tool(self.document_store_provider))
            tools.append(create_misleading_assistance_tool(self.document_store_provider))
            tools.append(create_relationship_recommendation_tool(self.document_store_provider))
            tools.append(create_semantics_description_tool(self.document_store_provider))
            tools.append(create_intent_classification_tool(self.document_store_provider))
        
        except Exception as e:
            logger.error(f"Error initializing tools: {e}")
        
        return tools
    
    def _initialize_agent(self) -> Optional[AgentExecutor]:
        """Initialize the unified Langchain agent with modern patterns"""
        try:
            if not self.tools:
                logger.warning("No tools available for agent initialization")
                return None
            
            # Initialize agent using the correct pattern
            agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,
                early_stopping_method="generate"
            )
            
            return agent
        except Exception as e:
            logger.error(f"Error initializing agent: {e}")
            return None
    
    def set_scoring_configuration(self, config_path: str):
        """Update scoring configuration"""
        if self.enhanced_sql_wrapper:
            self.enhanced_sql_wrapper.relevance_scorer = SQLAdvancedRelevanceScorer(
                config_file_path=config_path,
                schema_context=self.schema_context
            )
    
    async def execute_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute a specific pipeline with enhanced scoring capabilities"""
        try:
            logger.info(f"Executing pipeline: {request.pipeline_type.value} (scoring: {request.enable_scoring})")
            
            # Add global schema context if not provided
            if not request.schema_context and self.schema_context:
                request.schema_context = self.schema_context
            
            # Handle SQL pipelines with enhanced scoring
            if request.pipeline_type in [
                PipelineType.SQL_GENERATION,
                PipelineType.SQL_BREAKDOWN,
                PipelineType.SQL_REASONING,
                PipelineType.SQL_ANSWER,
                PipelineType.SQL_CORRECTION,
                PipelineType.SQL_EXPANSION,
                PipelineType.SQL_GENERATE_TRANSFORM,
            ]:
                return await self._execute_enhanced_sql_pipeline(request)
            
            # Handle other pipelines (same as original)
            else:
                return await self._execute_individual_pipeline(request)
                
        except Exception as e:
            logger.error(f"Error executing pipeline {request.pipeline_type.value}: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e),
                relevance_scoring=RelevanceScoring(enabled=request.enable_scoring)
            )
    
    async def _execute_enhanced_sql_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute SQL-related pipelines with enhanced scoring using modern patterns"""
        try:
            if request.enable_scoring and self.enhanced_sql_wrapper:
                # Use enhanced SQL wrapper with scoring
                if request.pipeline_type == PipelineType.SQL_GENERATION:
                    return await self.enhanced_sql_wrapper.execute_pipeline(request)
                elif request.pipeline_type == PipelineType.SQL_CORRECTION:
                    return await self.enhanced_sql_wrapper.execute_pipeline(request)
                elif request.pipeline_type == PipelineType.SQL_BREAKDOWN:
                    return await self.enhanced_sql_wrapper.execute_pipeline(request)
                else:
                    # For other SQL operations, fall back to regular pipeline
                    return await self._execute_regular_sql_pipeline(request)
            else:
                # Use regular SQL pipeline without scoring
                return await self._execute_regular_sql_pipeline(request)
        
        except Exception as e:
            logger.error(f"Error in enhanced SQL pipeline execution: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e),
                relevance_scoring=RelevanceScoring(enabled=request.enable_scoring)
            )
    
    async def _execute_regular_sql_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute regular SQL pipeline without scoring (original implementation)"""
        try:
            sql_request = SQLRequest(
                query=request.query,
                language=request.language,
                contexts=request.contexts,
                project_id=request.project_id,
                timeout=request.timeout
            )
            
            if request.pipeline_type == PipelineType.SQL_GENERATION:
                result = await self.sql_pipeline.generate_sql(sql_request)
            elif request.pipeline_type == PipelineType.SQL_REASONING:
                result = await self.sql_pipeline.generate_reasoning(sql_request)
            elif request.pipeline_type == PipelineType.SQL_BREAKDOWN:
                sql = request.additional_params.get("sql", "") if request.additional_params else ""
                result = await self.sql_pipeline.breakdown_sql(sql_request, sql)
            elif request.pipeline_type == PipelineType.SQL_ANSWER:
                sql = request.additional_params.get("sql", "") if request.additional_params else ""
                sql_data = request.additional_params.get("sql_data", {}) if request.additional_params else {}
                result = await self.sql_pipeline.generate_answer(sql_request, sql, sql_data)
            elif request.pipeline_type == PipelineType.SQL_CORRECTION:
                sql = request.additional_params.get("sql", "") if request.additional_params else ""
                error_message = request.additional_params.get("error_message", "") if request.additional_params else ""
                result = await self.sql_pipeline.correct_sql(sql, error_message, request.contexts or [])
            elif request.pipeline_type == PipelineType.SQL_EXPANSION:
                original_sql = request.additional_params.get("original_sql", "") if request.additional_params else ""
                result = await self.sql_pipeline.expand_sql(request.query, original_sql, request.contexts or [])
            elif request.pipeline_type == PipelineType.SQL_GENERATE_TRANSFORM:
                knowledge = request.additional_params.get("knowledge", []) if request.additional_params else []
                result = await self.sql_pipeline.generate_transform_sql(
                    request.query,
                    knowledge=knowledge,
                    contexts=request.contexts or [],
                    project_id=request.project_id,
                    timeout=request.timeout
                )
            else:
                raise ValueError(f"Unsupported SQL pipeline type: {request.pipeline_type}")
            
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=result.success,
                data=result.data,
                error=result.error,
                metadata=result.metadata,
                relevance_scoring=RelevanceScoring(enabled=False)
            )
            
        except Exception as e:
            logger.error(f"Error in regular SQL pipeline execution: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e),
                relevance_scoring=RelevanceScoring(enabled=False)
            )
    
    async def _execute_individual_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute individual non-SQL pipelines using modern patterns"""
        try:
            pipeline = self.pipelines.get(request.pipeline_type)
            if not pipeline:
                raise ValueError(f"Pipeline not available: {request.pipeline_type}")
            
            params = self._prepare_pipeline_params(request)
            
            # Call run method directly with params
            result = await pipeline.run(**params)
            
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=True,
                data=result,
                metadata={"pipeline_type": request.pipeline_type.value},
                relevance_scoring=RelevanceScoring(enabled=False)
            )
            
        except Exception as e:
            logger.error(f"Error in individual pipeline execution: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e),
                relevance_scoring=RelevanceScoring(enabled=False)
            )
    
    def _prepare_pipeline_params(self, request: PipelineRequest) -> Dict[str, Any]:
        """Prepare parameters for specific pipeline types (same as original)"""
        base_params = {
            "query": request.query,
            "language": request.language,
        }
        
        if request.additional_params:
            base_params.update(request.additional_params)
        
        if request.pipeline_type == PipelineType.INTENT_CLASSIFICATION:
            base_params.update({"project_id": request.project_id})
        elif request.pipeline_type == PipelineType.MISLEADING_ASSISTANCE:
            base_params.update({"db_schemas": request.contexts or []})
        elif request.pipeline_type in [PipelineType.FOLLOWUP_SQL_REASONING, PipelineType.FOLLOWUP_SQL_GENERATION]:
            base_params.update({"contexts": request.contexts or []})
        
        return base_params
    
    async def execute_complete_workflow_with_scoring(
        self,
        query: str,
        language: str = "English",
        contexts: List[str] = None,
        project_id: str = None,
        enable_scoring: bool = True,
        quality_threshold: float = 0.6,
        schema_context: Dict[str, Any] = None
    ) -> Dict[str, PipelineResult]:
        """Execute complete workflow with enhanced scoring capabilities"""
        results = {}
        
        try:
            # Step 1: Intent classification
            intent_request = PipelineRequest(
                pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                query=query,
                language=language,
                contexts=contexts,
                project_id=project_id,
                enable_scoring=False  # Intent classification doesn't need SQL scoring
            )
            
            intent_result = await self.execute_pipeline(intent_request)
            results["intent_classification"] = intent_result
            
            if not intent_result.success:
                return results
            
            intent = intent_result.data.get("intent", "TEXT_TO_SQL")
            
            # Step 2: Execute appropriate pipeline based on intent with scoring
            if intent == "TEXT_TO_SQL":
                sql_results = await self._execute_enhanced_sql_workflow(
                    query, language, contexts, project_id, enable_scoring, 
                    quality_threshold, schema_context
                )
                results.update(sql_results)
                
            elif intent == "MISLEADING_QUERY":
                misleading_request = PipelineRequest(
                    pipeline_type=PipelineType.MISLEADING_ASSISTANCE,
                    query=query,
                    language=language,
                    contexts=contexts or [],
                    enable_scoring=False
                )
                
                misleading_result = await self.execute_pipeline(misleading_request)
                results["misleading_assistance"] = misleading_result
                
            elif intent == "ANALYSIS_HELPER":
                # Handle analysis helper intent
                results["analysis_helper"] = PipelineResult(
                    pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                    success=True,
                    data={
                        "intent": "ANALYSIS_HELPER",
                        "message": "Analysis helper intent detected - providing analytical guidance and metric recommendations",
                        "suggested_actions": [
                            "Provide available metrics and KPIs",
                            "Suggest analysis approaches",
                            "Recommend relevant data columns"
                        ]
                    },
                    relevance_scoring=RelevanceScoring(enabled=False)
                )
                
            elif intent == "QUESTION_SUGGESTION":
                # Handle question suggestion intent
                results["question_suggestion"] = PipelineResult(
                    pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                    success=True,
                    data={
                        "intent": "QUESTION_SUGGESTION",
                        "message": "Question suggestion intent detected - providing example queries and analysis questions",
                        "suggested_actions": [
                            "Generate example SQL queries",
                            "Suggest analytical questions",
                            "Provide data exploration ideas"
                        ]
                    },
                    relevance_scoring=RelevanceScoring(enabled=False)
                )
                
            else:
                # Handle other intents (GENERAL, USER_GUIDE, etc.)
                results["general_response"] = PipelineResult(
                    pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                    success=True,
                    data={"message": f"Handling {intent} intent"},
                    relevance_scoring=RelevanceScoring(enabled=False)
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in enhanced complete workflow: {e}")
            results["error"] = PipelineResult(
                pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                success=False,
                error=str(e),
                relevance_scoring=RelevanceScoring(enabled=False)
            )
            return results
    
    async def _execute_enhanced_sql_workflow(
        self,
        query: str,
        language: str,
        contexts: List[str],
        project_id: str,
        enable_scoring: bool,
        quality_threshold: float,
        schema_context: Dict[str, Any]
    ) -> Dict[str, PipelineResult]:
        """Execute complete SQL workflow with enhanced scoring"""
        results = {}
        
        # Generate SQL with scoring
        sql_request = PipelineRequest(
            pipeline_type=PipelineType.SQL_GENERATION,
            query=query,
            language=language,
            contexts=contexts,
            project_id=project_id,
            enable_scoring=enable_scoring,
            quality_threshold=quality_threshold,
            schema_context=schema_context,
            max_improvement_attempts=3
        )
        
        sql_result = await self.execute_pipeline(sql_request)
        results["sql_generation"] = sql_result
        
        
        # If SQL generation was successful, break it down with scoring
        if sql_result.success and sql_result.data.get("sql"):
            breakdown_request = PipelineRequest(
                pipeline_type=PipelineType.SQL_BREAKDOWN,
                query=query,
                language=language,
                additional_params={"sql": sql_result.data["sql"]},
                enable_scoring=enable_scoring,
                schema_context=schema_context
            )
            
            breakdown_result = await self.execute_pipeline(breakdown_request)
            results["sql_breakdown"] = breakdown_result
        
        # Generate reasoning with scoring (if not already included)
        reasoning_request = PipelineRequest(
            pipeline_type=PipelineType.SQL_REASONING,
            query=query,
            language=language,
            contexts=contexts,
            project_id=project_id,
            enable_scoring=enable_scoring,
            schema_context=schema_context
        )
        
        reasoning_result = await self.execute_pipeline(reasoning_request)
        results["sql_reasoning"] = reasoning_result
        
        return results
    
    def get_system_analytics(self) -> Dict[str, Any]:
        """Get comprehensive system analytics including scoring metrics"""
        analytics = {
            "sql_scoring_enabled": self.enable_sql_scoring,
            "total_pipelines": len(self.pipelines),
            "available_pipeline_types": [pt.value for pt in PipelineType],
            "timestamp": datetime.now().isoformat()
        }
        
        if self.enhanced_sql_wrapper:
            sql_analytics = self.enhanced_sql_wrapper.get_performance_analytics()
            analytics["sql_scoring_analytics"] = sql_analytics
        
        return analytics
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """Get quality summary across all scored operations"""
        if not self.enhanced_sql_wrapper:
            return {"message": "SQL scoring not enabled"}
        
        analytics = self.enhanced_sql_wrapper.get_performance_analytics()
        
        summary = {
            "overall_quality": {
                "total_queries": analytics.get("total_queries", 0),
                "average_score": analytics.get("average_score", 0.0),
                "high_quality_rate": analytics.get("high_quality_rate", 0.0)
            },
            "quality_distribution": analytics.get("quality_distribution", {}),
            "recent_trend": analytics.get("recent_trend", {}),
            "improvement_areas": analytics.get("improvement_areas", [])
        }
        
        return summary


# Enhanced Factory
class EnhancedPipelineFactory:
    """Enhanced factory for creating pipeline systems with scoring"""
    
    @staticmethod
    def create_enhanced_unified_system(
        engine: Engine,
        embedder_provider: EmbedderProvider = None,
        document_store_provider: DocumentStoreProvider = None,
        use_rag: bool = True,
        enable_sql_scoring: bool = True,
        scoring_config_path: str = None,
        **kwargs
    ) -> EnhancedUnifiedPipelineSystem:
        """Create an enhanced unified pipeline system with scoring"""
        return EnhancedUnifiedPipelineSystem(
            engine=engine,
            embedder_provider=embedder_provider,
            document_store_provider=document_store_provider,
            use_rag=use_rag,
            enable_sql_scoring=enable_sql_scoring,
            scoring_config_path=scoring_config_path,
            **kwargs
        )


# Enhanced convenience functions
async def enhanced_sql_analysis(
    query: str,
    schema_documents: List[str],
    engine: Engine,
    language: str = "English",
    enable_scoring: bool = True,
    schema_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Enhanced SQL analysis with scoring capabilities"""
    system = EnhancedPipelineFactory.create_enhanced_unified_system(
        engine=engine,
        use_rag=True,
        enable_sql_scoring=enable_scoring
    )
    
   
    
    request = PipelineRequest(
        pipeline_type=PipelineType.SQL_GENERATION,
        query=query,
        language=language,
        contexts=schema_documents,
        enable_scoring=enable_scoring,
        schema_context=schema_context
    )
    
    result = await system.execute_pipeline(request)
    
    # Return enhanced result with scoring information
    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "relevance_scoring": {
            "enabled": result.relevance_scoring.enabled,
            "final_score": result.relevance_scoring.final_score,
            "quality_level": result.relevance_scoring.quality_level,
            "reasoning_components": result.relevance_scoring.reasoning_components,
            "sql_components": result.relevance_scoring.sql_components,
            "improvement_recommendations": result.relevance_scoring.improvement_recommendations,
            "detected_operation_type": result.relevance_scoring.detected_operation_type,
            "processing_time_seconds": result.relevance_scoring.processing_time_seconds
        },
        "metadata": result.metadata,
        "timestamp": result.timestamp
    }


async def complete_enhanced_analysis(
    query: str,
    schema_documents: List[str],
    engine: Engine,
    embedder_provider: EmbedderProvider = None,
    document_store_provider: DocumentStoreProvider = None,
    language: str = "English",
    enable_scoring: bool = True,
    schema_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Complete enhanced data analysis workflow with scoring"""
    system = EnhancedPipelineFactory.create_enhanced_unified_system(
        engine=engine,
        embedder_provider=embedder_provider,
        document_store_provider=document_store_provider,
        use_rag=True,
        enable_sql_scoring=enable_scoring
    )
    
    system.initialize_knowledge_base(
        schema_documents=schema_documents,
        schema_context=schema_context
    )
    
    results = await system.execute_complete_workflow_with_scoring(
        query=query,
        language=language,
        contexts=schema_documents,
        enable_scoring=enable_scoring,
        schema_context=schema_context
    )
    
    # Format results to include scoring information
    formatted_results = {}
    for step, result in results.items():
        formatted_results[step] = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "relevance_scoring": {
                "enabled": result.relevance_scoring.enabled,
                "final_score": result.relevance_scoring.final_score,
                "quality_level": result.relevance_scoring.quality_level,
                "improvement_recommendations": result.relevance_scoring.improvement_recommendations
            } if result.relevance_scoring.enabled else None
        }
    
    return formatted_results


if __name__ == "__main__":
    # Enhanced example usage
    async def enhanced_example_usage():
        from app.core.provider import EmbedderProvider, DocumentStoreProvider
        from app.core.engine_provider import EngineProvider
        
       
        engine = EngineProvider.get_engine()
        embedder_provider = EmbedderProvider()
        document_store_provider = DocumentStoreProvider()
        
        # Create enhanced unified system
        system = EnhancedPipelineFactory.create_enhanced_unified_system(
            engine=engine,
            embedder_provider=embedder_provider,
            document_store_provider=document_store_provider,
            enable_sql_scoring=True
        )
        
        # Set up schema context for better scoring
        schema_context = {
            "schema": {
                "customers": ["id", "name", "email", "signup_date"],
                "orders": ["id", "customer_id", "total", "order_date"]
            }
        }
        
        # Initialize knowledge base
        schema_docs = [
            "CREATE TABLE customers (id INT, name VARCHAR, email VARCHAR, signup_date DATE)",
            "CREATE TABLE orders (id INT, customer_id INT, total DECIMAL, order_date DATE)"
        ]
        
        system.initialize_knowledge_base(
            schema_documents=schema_docs,
            schema_context=schema_context
        )
        
        # Execute enhanced workflow with scoring
        results = await system.execute_complete_workflow_with_scoring(
            query="Show me the top customers by order value in the last month",
            language="English",
            contexts=schema_docs,
            enable_scoring=True,
            schema_context=schema_context
        )
        
        print("Enhanced Complete Workflow Results with Scoring:")
        for step, result in results.items():
            print(f"\n{step.upper()}:")
            print(f"Success: {result.success}")
            
            if result.success and result.data:
                print("Data:", orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode())
            
            if result.relevance_scoring.enabled:
                print(f"Relevance Score: {result.relevance_scoring.final_score:.3f}")
                print(f"Quality Level: {result.relevance_scoring.quality_level}")
                if result.relevance_scoring.improvement_recommendations:
                    print("Recommendations:")
                    for rec in result.relevance_scoring.improvement_recommendations:
                        print(f"  • {rec}")
            
            if result.error:
                print(f"Error: {result.error}")
        
        # Get system analytics
        analytics = system.get_system_analytics()
        print(f"\nSystem Analytics:")
        print(orjson.dumps(analytics, option=orjson.OPT_INDENT_2).decode())
        
        # Get quality summary
        quality_summary = system.get_quality_summary()
        print(f"\nQuality Summary:")
        print(orjson.dumps(quality_summary, option=orjson.OPT_INDENT_2).decode())

    # asyncio.run(enhanced_example_usage())