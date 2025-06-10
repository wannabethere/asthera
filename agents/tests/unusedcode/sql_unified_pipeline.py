import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

import orjson
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent import AgentExecutor
from langchain.agents import Tool

from src.core.engine import Engine
from src.core.provider import LLMProvider, EmbedderProvider, DocumentStoreProvider

# Import all the converted tools
from src.pipelines.generation.chart_adjustment import (
    ChartAdjustment,
    create_chart_adjustment_tool,
)
from src.pipelines.generation.followup_sql_generation_reasoning import (
    FollowUpSQLGenerationReasoning,
    create_followup_sql_reasoning_tool,
)
from src.pipelines.generation.followup_sql_generation import (
    FollowUpSQLGeneration,
    create_followup_sql_generation_tool,
)
from src.pipelines.generation.intent_classification import (
    IntentClassification,
    create_intent_classification_tool,
)
from src.pipelines.generation.misleading_assistance import (
    MisleadingAssistance,
    create_misleading_assistance_tool,
)
from src.pipelines.generation.relationship_recommendation import (
    RelationshipRecommendation,
    create_relationship_recommendation_tool,
)
from src.pipelines.generation.semantics_description import (
    SemanticsDescription,
    create_semantics_description_tool,
)

# Import the SQL RAG system
from src.pipelines.generation.utils.sql_interface import (
    SQLPipeline,
    SQLPipelineFactory,
    SQLRequest,
    SQLResult,
)

logger = logging.getLogger("wren-ai-service")


class PipelineType(Enum):
    """Available pipeline types"""
    SQL_GENERATION = "sql_generation"
    SQL_BREAKDOWN = "sql_breakdown"
    SQL_REASONING = "sql_reasoning"
    SQL_ANSWER = "sql_answer"
    SQL_CORRECTION = "sql_correction"
    SQL_EXPANSION = "sql_expansion"
    CHART_ADJUSTMENT = "chart_adjustment"
    FOLLOWUP_SQL_REASONING = "followup_sql_reasoning"
    FOLLOWUP_SQL_GENERATION = "followup_sql_generation"
    INTENT_CLASSIFICATION = "intent_classification"
    MISLEADING_ASSISTANCE = "misleading_assistance"
    RELATIONSHIP_RECOMMENDATION = "relationship_recommendation"
    SEMANTICS_DESCRIPTION = "semantics_description"


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


@dataclass
class PipelineResult:
    """Universal pipeline result structure"""
    pipeline_type: PipelineType
    success: bool
    data: Dict[str, Any] = None
    error: str = None
    metadata: Dict[str, Any] = None


class UnifiedPipelineSystem:
    """Unified system for all pipeline operations using Langchain"""
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        engine: Engine,
        embedder_provider: EmbedderProvider = None,
        document_store_provider: DocumentStoreProvider = None,
        wren_ai_docs: List[dict] = None,
        use_rag: bool = True,
        **kwargs
    ):
        self.llm_provider = llm_provider
        self.engine = engine
        self.embedder_provider = embedder_provider
        self.document_store_provider = document_store_provider
        self.wren_ai_docs = wren_ai_docs or []
        self.use_rag = use_rag
        
        # Initialize SQL pipeline
        self.sql_pipeline = SQLPipelineFactory.create_pipeline(
            llm_provider="custom",  # We'll pass our own LLM
            engine=engine,
            use_rag=use_rag,
            llm=llm_provider.get_llm(),
            **kwargs
        )
        
        # Initialize individual pipelines
        self.pipelines = self._initialize_pipelines()
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Initialize unified agent
        self.agent = self._initialize_agent()

    def _initialize_pipelines(self) -> Dict[PipelineType, Any]:
        """Initialize all individual pipelines"""
        pipelines = {}
        
        try:
            # Chart adjustment
            pipelines[PipelineType.CHART_ADJUSTMENT] = ChartAdjustment(self.llm_provider)
            
            # Follow-up SQL reasoning
            pipelines[PipelineType.FOLLOWUP_SQL_REASONING] = FollowUpSQLGenerationReasoning(
                self.llm_provider
            )
            
            # Follow-up SQL generation
            pipelines[PipelineType.FOLLOWUP_SQL_GENERATION] = FollowUpSQLGeneration(
                self.llm_provider, self.engine
            )
            
            # Misleading assistance
            pipelines[PipelineType.MISLEADING_ASSISTANCE] = MisleadingAssistance(
                self.llm_provider
            )
            
            # Relationship recommendation
            pipelines[PipelineType.RELATIONSHIP_RECOMMENDATION] = RelationshipRecommendation(
                self.llm_provider, self.engine
            )
            
            # Semantics description
            pipelines[PipelineType.SEMANTICS_DESCRIPTION] = SemanticsDescription(
                self.llm_provider
            )
            
            # Intent classification (requires additional providers)
            if self.embedder_provider and self.document_store_provider:
                pipelines[PipelineType.INTENT_CLASSIFICATION] = IntentClassification(
                    self.llm_provider,
                    self.embedder_provider,
                    self.document_store_provider,
                    self.wren_ai_docs
                )
            
        except Exception as e:
            logger.error(f"Error initializing pipelines: {e}")
        
        return pipelines

    def _initialize_tools(self) -> List[Tool]:
        """Initialize all Langchain tools"""
        tools = []
        
        try:
            # SQL tools are handled by the SQL pipeline
            # Add individual pipeline tools
            
            tools.append(create_chart_adjustment_tool(self.llm_provider))
            tools.append(create_followup_sql_reasoning_tool(self.llm_provider))
            tools.append(create_followup_sql_generation_tool(self.llm_provider, self.engine))
            tools.append(create_misleading_assistance_tool(self.llm_provider))
            tools.append(create_relationship_recommendation_tool(self.llm_provider, self.engine))
            tools.append(create_semantics_description_tool(self.llm_provider))
            
            if self.embedder_provider and self.document_store_provider:
                tools.append(create_intent_classification_tool(
                    self.llm_provider,
                    self.embedder_provider,
                    self.document_store_provider,
                    self.wren_ai_docs
                ))
            
        except Exception as e:
            logger.error(f"Error initializing tools: {e}")
        
        return tools

    def _initialize_agent(self) -> Optional[AgentExecutor]:
        """Initialize the unified Langchain agent"""
        try:
            if not self.tools:
                logger.warning("No tools available for agent initialization")
                return None
            
            agent = initialize_agent(
                tools=self.tools,
                llm=self.llm_provider.get_llm(),
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

    def initialize_knowledge_base(
        self,
        schema_documents: List[str] = None,
        sql_samples: List[Dict[str, str]] = None
    ):
        """Initialize knowledge base for RAG"""
        if self.sql_pipeline and hasattr(self.sql_pipeline, 'initialize_knowledge_base'):
            self.sql_pipeline.initialize_knowledge_base(
                schema_documents=schema_documents,
                sql_samples=sql_samples
            )

    async def execute_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute a specific pipeline"""
        try:
            logger.info(f"Executing pipeline: {request.pipeline_type.value}")
            
            # Handle SQL pipelines through SQL pipeline system
            if request.pipeline_type in [
                PipelineType.SQL_GENERATION,
                PipelineType.SQL_BREAKDOWN,
                PipelineType.SQL_REASONING,
                PipelineType.SQL_ANSWER,
                PipelineType.SQL_CORRECTION,
                PipelineType.SQL_EXPANSION,
            ]:
                return await self._execute_sql_pipeline(request)
            
            # Handle other pipelines
            else:
                return await self._execute_individual_pipeline(request)
                
        except Exception as e:
            logger.error(f"Error executing pipeline {request.pipeline_type.value}: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e)
            )

    async def _execute_sql_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute SQL-related pipelines"""
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
            else:
                raise ValueError(f"Unsupported SQL pipeline type: {request.pipeline_type}")
            
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=result.success,
                data=result.data,
                error=result.error,
                metadata=result.metadata
            )
            
        except Exception as e:
            logger.error(f"Error in SQL pipeline execution: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e)
            )

    async def _execute_individual_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """Execute individual non-SQL pipelines"""
        try:
            pipeline = self.pipelines.get(request.pipeline_type)
            if not pipeline:
                raise ValueError(f"Pipeline not available: {request.pipeline_type}")
            
            # Prepare parameters based on pipeline type
            params = self._prepare_pipeline_params(request)
            
            # Execute the pipeline
            result = await pipeline.run(**params)
            
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=True,
                data=result,
                metadata={"pipeline_type": request.pipeline_type.value}
            )
            
        except Exception as e:
            logger.error(f"Error in individual pipeline execution: {e}")
            return PipelineResult(
                pipeline_type=request.pipeline_type,
                success=False,
                error=str(e)
            )

    def _prepare_pipeline_params(self, request: PipelineRequest) -> Dict[str, Any]:
        """Prepare parameters for specific pipeline types"""
        base_params = {
            "query": request.query,
            "language": request.language,
        }
        
        # Add additional parameters based on pipeline type
        if request.additional_params:
            base_params.update(request.additional_params)
        
        # Pipeline-specific parameter handling
        if request.pipeline_type == PipelineType.INTENT_CLASSIFICATION:
            base_params.update({
                "project_id": request.project_id,
            })
        elif request.pipeline_type == PipelineType.MISLEADING_ASSISTANCE:
            base_params.update({
                "db_schemas": request.contexts or [],
            })
        elif request.pipeline_type == PipelineType.FOLLOWUP_SQL_REASONING:
            base_params.update({
                "contexts": request.contexts or [],
            })
        elif request.pipeline_type == PipelineType.FOLLOWUP_SQL_GENERATION:
            base_params.update({
                "contexts": request.contexts or [],
            })
        
        return base_params

    async def execute_agent_query(self, query: str) -> Dict[str, Any]:
        """Execute a query using the unified agent"""
        try:
            if not self.agent:
                return {
                    "success": False,
                    "error": "Agent not initialized"
                }
            
            result = await self.agent.arun(query)
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error in agent execution: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def execute_complete_workflow(
        self,
        query: str,
        language: str = "English",
        contexts: List[str] = None,
        project_id: str = None,
    ) -> Dict[str, PipelineResult]:
        """Execute a complete workflow including intent classification and appropriate pipeline"""
        results = {}
        
        try:
            # Step 1: Intent classification
            intent_request = PipelineRequest(
                pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                query=query,
                language=language,
                contexts=contexts,
                project_id=project_id
            )
            
            intent_result = await self.execute_pipeline(intent_request)
            results["intent_classification"] = intent_result
            
            if not intent_result.success:
                return results
            
            intent = intent_result.data.get("intent", "TEXT_TO_SQL")
            
            # Step 2: Execute appropriate pipeline based on intent
            if intent == "TEXT_TO_SQL":
                # Execute SQL generation workflow
                sql_results = await self._execute_sql_workflow(
                    query, language, contexts, project_id
                )
                results.update(sql_results)
                
            elif intent == "MISLEADING_QUERY":
                # Execute misleading assistance
                misleading_request = PipelineRequest(
                    pipeline_type=PipelineType.MISLEADING_ASSISTANCE,
                    query=query,
                    language=language,
                    contexts=contexts or []
                )
                
                misleading_result = await self.execute_pipeline(misleading_request)
                results["misleading_assistance"] = misleading_result
                
            elif intent == "GENERAL":
                # For general queries, we might want to provide schema information
                # This can be customized based on requirements
                results["general_response"] = PipelineResult(
                    pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                    success=True,
                    data={"message": "General information about your data"}
                )
                
            elif intent == "USER_GUIDE":
                # Provide user guide information
                results["user_guide"] = PipelineResult(
                    pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                    success=True,
                    data={"message": "User guide information"}
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in complete workflow: {e}")
            results["error"] = PipelineResult(
                pipeline_type=PipelineType.INTENT_CLASSIFICATION,
                success=False,
                error=str(e)
            )
            return results

    async def _execute_sql_workflow(
        self,
        query: str,
        language: str,
        contexts: List[str],
        project_id: str
    ) -> Dict[str, PipelineResult]:
        """Execute complete SQL workflow"""
        results = {}
        
        # Generate reasoning
        reasoning_request = PipelineRequest(
            pipeline_type=PipelineType.SQL_REASONING,
            query=query,
            language=language,
            contexts=contexts,
            project_id=project_id
        )
        
        reasoning_result = await self.execute_pipeline(reasoning_request)
        results["sql_reasoning"] = reasoning_result
        
        # Generate SQL
        sql_request = PipelineRequest(
            pipeline_type=PipelineType.SQL_GENERATION,
            query=query,
            language=language,
            contexts=contexts,
            project_id=project_id
        )
        
        sql_result = await self.execute_pipeline(sql_request)
        results["sql_generation"] = sql_result
        
        # If SQL generation was successful, break it down
        if sql_result.success and sql_result.data.get("sql"):
            breakdown_request = PipelineRequest(
                pipeline_type=PipelineType.SQL_BREAKDOWN,
                query=query,
                language=language,
                additional_params={"sql": sql_result.data["sql"]}
            )
            
            breakdown_result = await self.execute_pipeline(breakdown_request)
            results["sql_breakdown"] = breakdown_result
        
        return results


class PipelineFactory:
    """Factory for creating pipeline systems"""
    
    @staticmethod
    def create_unified_system(
        llm_provider: LLMProvider,
        engine: Engine,
        embedder_provider: EmbedderProvider = None,
        document_store_provider: DocumentStoreProvider = None,
        wren_ai_docs: List[dict] = None,
        use_rag: bool = True,
        **kwargs
    ) -> UnifiedPipelineSystem:
        """Create a unified pipeline system"""
        return UnifiedPipelineSystem(
            llm_provider=llm_provider,
            engine=engine,
            embedder_provider=embedder_provider,
            document_store_provider=document_store_provider,
            wren_ai_docs=wren_ai_docs,
            use_rag=use_rag,
            **kwargs
        )

    @staticmethod
    def create_sql_only_system(
        llm_provider: LLMProvider,
        engine: Engine,
        use_rag: bool = True,
        **kwargs
    ) -> SQLPipeline:
        """Create SQL-only pipeline system"""
        return SQLPipelineFactory.create_pipeline(
            llm_provider="custom",
            engine=engine,
            use_rag=use_rag,
            llm=llm_provider.get_llm(),
            **kwargs
        )


# Convenience functions
async def quick_sql_analysis(
    query: str,
    schema_documents: List[str],
    llm_provider: LLMProvider,
    engine: Engine,
    language: str = "English"
) -> Dict[str, Any]:
    """Quick SQL analysis with minimal setup"""
    system = PipelineFactory.create_sql_only_system(llm_provider, engine)
    system.initialize_knowledge_base(schema_documents=schema_documents)
    
    request = SQLRequest(query=query, language=language)
    result = await system.complete_sql_workflow(request)
    
    return {step: res.data if res.success else {"error": res.error} 
            for step, res in result.items()}


async def complete_data_analysis(
    query: str,
    schema_documents: List[str],
    llm_provider: LLMProvider,
    engine: Engine,
    embedder_provider: EmbedderProvider = None,
    document_store_provider: DocumentStoreProvider = None,
    language: str = "English"
) -> Dict[str, Any]:
    """Complete data analysis workflow"""
    system = PipelineFactory.create_unified_system(
        llm_provider=llm_provider,
        engine=engine,
        embedder_provider=embedder_provider,
        document_store_provider=document_store_provider,
        use_rag=True
    )
    
    system.initialize_knowledge_base(schema_documents=schema_documents)
    
    results = await system.execute_complete_workflow(
        query=query,
        language=language,
        contexts=schema_documents
    )
    
    return {step: res.data if res.success else {"error": res.error} 
            for step, res in results.items()}


if __name__ == "__main__":
    # Example usage
    async def example_usage():
        from src.core.provider import LLMProvider, EmbedderProvider, DocumentStoreProvider
        from src.core.engine import Engine
        
        # Initialize providers
        llm_provider = LLMProvider()  # Initialize with your config
        engine = Engine()  # Initialize with your config
        embedder_provider = EmbedderProvider()  # Initialize with your config
        document_store_provider = DocumentStoreProvider()  # Initialize with your config
        
        # Create unified system
        system = PipelineFactory.create_unified_system(
            llm_provider=llm_provider,
            engine=engine,
            embedder_provider=embedder_provider,
            document_store_provider=document_store_provider
        )
        
        # Initialize knowledge base
        schema_docs = [
            "CREATE TABLE customers (id INT, name VARCHAR, email VARCHAR)",
            "CREATE TABLE orders (id INT, customer_id INT, total DECIMAL)"
        ]
        system.initialize_knowledge_base(schema_documents=schema_docs)
        
        # Execute complete workflow
        results = await system.execute_complete_workflow(
            query="Show me the top customers by order value",
            language="English",
            contexts=schema_docs
        )
        
        print("Complete Workflow Results:")
        for step, result in results.items():
            print(f"\n{step.upper()}:")
            if result.success:
                print(orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode())
            else:
                print(f"Error: {result.error}")

    # asyncio.run(example_usage())