from typing import Any, Dict, Optional, List
from app.agents.pipelines.base import AgentPipeline
from app.core.engine import Engine
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.storage.documents import DocumentChromaStore
from langchain_openai import ChatOpenAI
from app.agents.nodes.sql.sql_pipeline import SQLRequest, SQLResult
from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
from app.agents.nodes.sql.sql_rag_agent import create_sql_rag_agent
from app.core.provider import DocumentStoreProvider
from app.agents.nodes.sql.scoring_sql_rag_agent import (
    create_scoring_integrated_sql_rag_agent
)
from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent
from app.agents.nodes.sql.followup_sql_generation import FollowUpSQLGeneration
from app.agents.nodes.sql.utils.sql_prompts import Configuration, AskHistory
from app.agents.nodes.sql.intent_classification import IntentClassification
from app.agents.nodes.sql.misleading_assistance import MisleadingAssistance
from app.agents.nodes.sql.relationship_recommendation import RelationshipRecommendation
from app.agents.nodes.sql.semantics_description import SemanticsDescription
from app.agents.nodes.sql.chart_generation import VegaLiteChartGenerationPipeline
from app.agents.nodes.sql.enhanced_chart_generation import EnhancedVegaLiteChartGenerationPipeline
from app.agents.nodes.sql.chart_adjustment import ChartAdjustment
from app.agents.nodes.sql.utils.chart_models import ChartAdjustmentOption
from app.agents.nodes.sql.powerbi_chart_generation import PowerBIChartGenerationPipeline
from app.agents.nodes.sql.plotly_chart_generation import PlotlyChartGenerationPipeline
from app.agents.nodes.sql.tableau_chart_generation import TableauChartGenerationPipeline
from app.agents.nodes.sql.plotly_chart_adjustment import PlotlyChartAdjustment, PlotlyChartAdjustmentOption
from app.agents.nodes.sql.data_assistance import DataAssistanceRequest, DataAssistanceResult
from app.agents.nodes.sql.data_assistance import DataAssistanceTool
from app.agents.nodes.sql.sql_suggestor import SQLQuestionSuggestionTool, SQLQuestionSuggestionRequest, SQLQuestionSuggestionResult
import logging

logger = logging.getLogger("lexy-ai-service")

class SQLGenerationPipeline(AgentPipeline):
    """Pipeline for SQL generation with scoring"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        relevance_scorer: Optional[SQLAdvancedRelevanceScorer] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Generation Pipeline",
            version="1.0",
            description="Generates SQL queries from natural language with quality scoring",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.relevance_scorer = relevance_scorer or SQLAdvancedRelevanceScorer()
        self.use_enhanced_agent = use_enhanced_agent
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                enable_scoring=True,
                relevance_scorer=self.relevance_scorer,
                document_store_provider=document_store_provider
            )
        else:
            self.agent =  create_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        self._initialized = True
 
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")  # Remove query from kwargs
        language = kwargs.get("language", "English")
        contexts = kwargs.get("contexts", [])
        project_id = kwargs.get("project_id")
        schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
        
        # Append project-specific instructions to the query
        from app.utils.project_instructions import project_instructions_manager
        enhanced_query = project_instructions_manager.append_instructions_to_query(
            query, project_id
        )
        
        logger.info(f"Starting SQL generation for query: {query}")
        logger.info(f"Enhanced query: {enhanced_query}")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Language: {language}")
        logger.info(f"Number of contexts: {len(contexts)}")
        
        # Generate SQL using the appropriate agent with enhanced query
        if self.use_enhanced_agent:
            logger.info("Using enhanced SQL generation agent")
            result = await self.agent.process_sql_request_enhanced(
                operation="GENERATION",
                query=enhanced_query,
                schema_context=schema_context,
                **kwargs
            )
        else:
            logger.info("Using standard SQL generation agent")
            result = await self.agent.process_sql_request(
                operation="GENERATION",
                query=enhanced_query,
                **kwargs
            )
        
        logger.info(f"SQL generation result: {result}")
        
        # Return the result directly since it already has the correct structure
        return result

class SQLBreakdownPipeline(AgentPipeline):
    """Pipeline for SQL query breakdown with explanation"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Breakdown Pipeline",
            version="1.0",
            description="Breaks down SQL queries into understandable explanations",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")  # Remove query from kwargs
        sql = kwargs.pop("sql", "")  # Remove sql from kwargs
        language = kwargs.get("language", "English")
        schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
        
        if self.use_enhanced_agent:
            result = await self.agent.process_sql_request_enhanced(
                operation="BREAKDOWN",
                query=query,
                sql=sql,
                schema_context=schema_context,
                **kwargs
            )
        else:
            result = await self.agent.process_sql_request(
                operation="BREAKDOWN",
                query=query,
                sql=sql,
                **kwargs
            )
        
        return {
            "success": result.get("success", False),
            "data": result.get("data", {}),
            "error": result.get("error")
        }

class SQLReasoningPipeline(AgentPipeline):
    """Pipeline for SQL reasoning generation"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Reasoning Pipeline",
            version="1.0",
            description="Generates reasoning for SQL queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")  # Remove query from kwargs
        language = kwargs.get("language", "English")
        contexts = kwargs.get("contexts", [])
        project_id = kwargs.get("project_id")
        schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
        # Append project-specific instructions to the query
        from app.utils.project_instructions import project_instructions_manager
        enhanced_query = project_instructions_manager.append_instructions_to_query(
            query, project_id
        )

        if self.use_enhanced_agent:
            result = await self.agent.process_sql_request_enhanced(
                operation="REASONING",
                query=enhanced_query,
                schema_context=schema_context,
                **kwargs
            )
        else:
            result = await self.agent.process_sql_request(
                operation="REASONING",
                query=enhanced_query,
                **kwargs
            )
        
        return {
            "success": result.get("success", True),
            "data": {
                "reasoning": result.get("reasoning", ""),
                "processing_time_seconds": result.get("processing_time_seconds", 0.0),
                "timestamp": result.get("timestamp", ""),
                "operation_type": result.get("operation_type", "")
            },
            "error": result.get("error",{})
        }

class SQLCorrectionPipeline(AgentPipeline):
    """Pipeline for SQL query correction"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Correction Pipeline",
            version="1.0",
            description="Corrects SQL queries based on error messages",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        sql = kwargs.pop("sql", "")  # Remove sql from kwargs
        error_message = kwargs.pop("error_message", "")  # Remove error_message from kwargs
        query = kwargs.pop("query", "")  # Remove query from kwargs
        contexts = kwargs.get("contexts", [])
        schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
        
        if self.use_enhanced_agent:
            result = await self.agent.process_sql_request_enhanced(
                operation="CORRECTION",
                query=query,  # Use the query from kwargs, which might be empty
                sql=sql,
                error_message=error_message,
                schema_context=schema_context,
                **kwargs
            )
        else:
            result = await self.agent.process_sql_request(
                operation="CORRECTION",
                query=query,  # Use the query from kwargs, which might be empty
                sql=sql,
                error_message=error_message,
                **kwargs
            )
        logger.info("result in sql correction pipeline", result)
        return {
            "success": result.get("success", False),
            "valid_generation_results": [
                {
                    "sql": result.get("sql", ""),
                    "correlation_id": result.get("correlation_id", "")
                }
            ] if result.get("success", False) and result.get("sql") else [],
            "invalid_generation_results": [],
            "error": result.get("error")
        }

class SQLExpansionPipeline(AgentPipeline):
    """Pipeline for SQL query expansion"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Expansion Pipeline",
            version="1.0",
            description="Expands SQL queries with additional functionality",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")  # Remove query from kwargs
        original_sql = kwargs.pop("original_sql", "")  # Remove original_sql from kwargs
        contexts = kwargs.get("contexts", [])
       
        if self.use_enhanced_agent:
            result = await self.agent.process_sql_request_enhanced(
                operation="EXPANSION",
                query=query,
                **kwargs
            )
        else:
            result = await self.agent.process_sql_request(
                operation="EXPANSION",
                query=query,
                **kwargs
            )
        
        # The agent returns a structure with sql, success, correlation_id directly
        # We need to convert this to the expected format with valid_generation_results
        if result.get("success", False):
            # Convert the agent result to the expected pipeline format
            return {
                "success": True,
                "valid_generation_results": [
                    {
                        "sql": result.get("sql", ""),
                        "correlation_id": result.get("correlation_id", "")
                    }
                ],
                "invalid_generation_results": [],
                "error": None
            }
        else:
            # If the agent failed, return empty results
            return {
                "success": False,
                "valid_generation_results": [],
                "invalid_generation_results": [],
                "error": result.get("error", "Unknown error")
            }

class SQLTransformPipeline(AgentPipeline):
    """Pipeline for SQL transform generation (dynamic column transformations)"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Transform Pipeline",
            version="1.0",
            description="Generates SQL queries with dynamic column transformations",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Import and initialize transform agent
        from app.agents.nodes.sql.transform_sql_rag_agent import create_transform_sql_rag_agent
        
        self.agent = create_transform_sql_rag_agent(
            llm=llm,
            engine=engine,
            document_store_provider=document_store_provider
        )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the SQL transform pipeline
        
        Args:
            **kwargs: Input parameters including:
                - query: The natural language question
                - knowledge: Additional knowledge context (List[str])
                - contexts: Schema contexts
                - project_id: The project ID
                - language: Language for generation (default: "English")
                - schema_context: Optional schema context
                
        Returns:
            Dict[str, Any]: Transform results containing:
                - success: Whether the transform was generated successfully
                - data: The generated SQL and metadata
                - error: Any error that occurred
        """
        try:
            query = kwargs.pop("query", "")  # Remove query from kwargs
            knowledge = kwargs.pop("knowledge", [])  # Remove knowledge from kwargs
            contexts = kwargs.get("contexts", [])
            project_id = kwargs.get("project_id")
            language = kwargs.get("language", "English")
            schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
            
            # Append project-specific instructions to the query
            from app.utils.project_instructions import project_instructions_manager
            enhanced_query = project_instructions_manager.append_instructions_to_query(
                query, project_id
            )
            
            logger.info(f"Starting SQL transform generation for query: {query}")
            logger.info(f"Enhanced query: {enhanced_query}")
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Knowledge items: {len(knowledge)}")
            logger.info(f"Number of contexts: {len(contexts)}")
            
            # Process transform request using transform agent
            result = await self.agent.process_transform_request(
                query=enhanced_query,
                knowledge=knowledge,
                contexts=contexts,
                language=language,
                project_id=project_id,
                schema_context=schema_context,
                **kwargs
            )
            
            logger.info(f"SQL transform result: {result}")
            
            # Return the result in the expected format
            return {
                "success": result.get("success", False),
                "data": result.get("data", {}),
                "error": result.get("error"),
                "metadata": {
                    "transform_type": result.get("data", {}).get("transform_type"),
                    "reasoning_plan": result.get("data", {}).get("reasoning_plan", {})
                }
            }
            
        except Exception as e:
            logger.error(f"Error in SQL transform pipeline: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

class ChartGenerationPipeline(AgentPipeline):
    """Pipeline for chart generation with support for multiple chart types including enhanced Vega-Lite"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True,
        chart_config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            name="Chart Generation Pipeline",
            version="1.0",
            description="Generates charts from SQL query results with enhanced Vega-Lite support",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        self.chart_config = chart_config or {"type": "enhanced_vega_lite"}  # Default to enhanced Vega-Lite for KPI support
        
        # Initialize appropriate chart generator based on config
        if self.chart_config.get("type") == "powerbi":
            self.chart_generator = PowerBIChartGenerationPipeline(llm=llm)
        elif self.chart_config.get("type") == "plotly":
            self.chart_generator = PlotlyChartGenerationPipeline(llm=llm)
        elif self.chart_config.get("type") == "tableau":
            self.chart_generator = TableauChartGenerationPipeline(llm=llm)
        elif self.chart_config.get("type") in ["vega_lite", "enhanced_vega_lite"]:
            # Use enhanced Vega-Lite pipeline with KPI support
            self.chart_generator = EnhancedVegaLiteChartGenerationPipeline()
        else:  # Default to enhanced Vega-Lite for better chart type support
            self.chart_generator = EnhancedVegaLiteChartGenerationPipeline()
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.get("query", "")
        sql = kwargs.get("sql", "")
        data = kwargs.get("data", {})
        language = kwargs.get("language", "English")
        export_format = kwargs.get("export_format")
        
        # Run chart generation with the selected generator
        result = await self.chart_generator.run(
            query=query,
            sql=sql,
            data=data,
            language=language,
            export_format=export_format
        )
        
        # Format response based on chart type
        if self.chart_config.get("type") == "powerbi":
            return {
                "success": result.get("success", False),
                "data": {
                    "chart_config": result.get("chart_config", {}),
                    "reasoning": result.get("reasoning", ""),
                    "chart_type": result.get("chart_type", ""),
                    "exported_json": result.get("exported_json"),
                    "dax_measures": result.get("dax_measures"),
                    "visual_settings": result.get("visual_settings")
                },
                "error": result.get("error")
            }
        elif self.chart_config.get("type") == "plotly":
            return {
                "success": result.get("success", False),
                "data": {
                    "chart_config": result.get("chart_config", {}),
                    "reasoning": result.get("reasoning", ""),
                    "chart_type": result.get("chart_type", ""),
                    "exported_json": result.get("exported_json"),
                    "python_code": result.get("python_code"),
                    "express_code": result.get("express_code"),
                    "javascript_code": result.get("javascript_code"),
                    "chart_summary": result.get("chart_summary")
                },
                "error": result.get("error")
            }
        elif self.chart_config.get("type") in ["vega_lite", "enhanced_vega_lite"]:
            # Enhanced Vega-Lite response format
            return {
                "success": result.get("success", False),
                "data": {
                    "chart_schema": result.get("chart_schema", {}),
                    "reasoning": result.get("reasoning", ""),
                    "chart_type": result.get("chart_type", ""),
                    "exported_json": result.get("exported_json"),
                    "observable_code": result.get("observable_code"),
                    "altair_code": result.get("altair_code"),
                    "chart_summary": result.get("chart_summary"),
                    "enhanced_metadata": result.get("enhanced_metadata", {}),
                    "kpi_metadata": result.get("chart_schema", {}).get("kpi_metadata", {})
                },
                "error": result.get("error")
            }
        else:  # Fallback to basic Vega-Lite
            return {
                "success": result.get("success", False),
                "data": {
                    "chart_schema": result.get("chart_schema", {}),
                    "reasoning": result.get("reasoning", ""),
                    "chart_type": result.get("chart_type", ""),
                    "exported_json": result.get("exported_json"),
                    "observable_code": result.get("observable_code"),
                    "altair_code": result.get("altair_code"),
                    "chart_summary": result.get("chart_summary")
                },
                "error": result.get("error")
            }

class ChartAdjustmentPipeline(AgentPipeline):
    """Pipeline for chart adjustments with support for multiple chart types"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True,
        chart_config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            name="Chart Adjustment Pipeline",
            version="1.0",
            description="Adjusts chart visualizations based on data",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        self.chart_config = chart_config or {"type": "enhanced_vega_lite"}  # Default to enhanced Vega-Lite for KPI support
        
        # Initialize appropriate chart adjuster based on config
        if self.chart_config.get("type") == "powerbi":
            self.chart_adjuster = PowerBIChartGenerationPipeline(llm=llm)
        elif self.chart_config.get("type") == "plotly":
            self.chart_adjuster = PlotlyChartAdjustment()
        elif self.chart_config.get("type") in ["vega_lite", "enhanced_vega_lite"]:
            # Use enhanced chart adjustment for better support
            self.chart_adjuster = ChartAdjustment()
        else:  # Default to enhanced Vega-Lite
            self.chart_adjuster = ChartAdjustment()
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.get("query", "")
        sql = kwargs.get("sql", "")
        adjustment_option = kwargs.get("adjustment_option")
        chart_schema = kwargs.get("chart_schema", {})
        data = kwargs.get("data", {})
        language = kwargs.get("language", "English")
        
        chart_type = self.chart_config.get("type")
        if chart_type == "powerbi":
            # For PowerBI, use chart_config and adjustment_option as-is
            result = await self.chart_adjuster.run(
                query=query,
                sql=sql,
                data=data,
                language=language,
                chart_config=chart_schema,
                adjustment_option=adjustment_option
            )
            return {
                "success": result.get("success", False),
                "data": {
                    "chart_config": result.get("chart_config", {}),
                    "reasoning": result.get("reasoning", ""),
                    "chart_type": result.get("chart_type", ""),
                    "dax_measures": result.get("dax_measures"),
                    "visual_settings": result.get("visual_settings")
                },
                "error": result.get("error")
            }
        elif chart_type == "plotly":
            # For Plotly, convert adjustment_option if needed and map chart_schema to chart_config
            if isinstance(adjustment_option, dict):
                adjustment_option = PlotlyChartAdjustmentOption(**adjustment_option)
            result = await self.chart_adjuster.run(
                query=query,
                sql=sql,
                adjustment_option=adjustment_option,
                chart_config=chart_schema,
                data=data,
                language=language
            )
            return {
                "success": result.get("success", False),
                "data": {
                    "chart_config": result.get("chart_config", {}),
                    "reasoning": result.get("reasoning", ""),
                    "chart_type": result.get("chart_type", ""),
                    "python_code": result.get("python_code"),
                    "express_code": result.get("express_code"),
                    "javascript_code": result.get("javascript_code")
                },
                "error": result.get("error")
            }
        else:  # Default Vega-Lite
            # For Vega-Lite, use ChartAdjustmentOption if needed
            if isinstance(adjustment_option, dict):
                adjustment_option = ChartAdjustmentOption(**adjustment_option)
            print("adjustment_option",adjustment_option)
            result = await self.chart_adjuster.run(
                query=query,
                sql=sql,
                adjustment=adjustment_option,
                chart_schema=chart_schema,
                data=data,
                language=language
            )
            return {
                "success": result.get("success", False),
                "post_process": {
                    "results": {
                        "chart_schema": result.get("chart_schema", {}),
                        "reasoning": result.get("reasoning", ""),
                        "chart_type": result.get("chart_type", "")
                    }
                },
                "error": result.get("error")
            }

class FollowUpSQLReasoningPipeline(AgentPipeline):
    """Pipeline for follow-up SQL reasoning"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None
    ):
        super().__init__(
            name="Follow-up SQL Reasoning Pipeline",
            version="1.0",
            description="Generates reasoning for follow-up SQL queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.get("query", "")
        previous_context = kwargs.get("previous_context", {})
        
        # Implement follow-up reasoning logic
        return {
            "success": True,
            "data": {
                "reasoning": f"Follow-up reasoning for: {query}",
                "context": previous_context
            }
        }

class FollowUpSQLGenerationPipeline(AgentPipeline):
    """Pipeline for follow-up SQL generation"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Follow-up SQL Generation Pipeline",
            version="1.0",
            description="Generates follow-up SQL queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        # Use the provider directly
        self.followup_generator = FollowUpSQLGeneration(document_store_provider)
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")  # Remove query from kwargs
        contexts = kwargs.get("contexts", [])
        previous_sql = kwargs.pop("previous_sql", "")  # Remove previous_sql from kwargs
        project_id = kwargs.get("project_id")
        sql_generation_reasoning = kwargs.pop("sql_generation_reasoning", "")  # Remove sql_generation_reasoning from kwargs
        
        # Append project-specific instructions to the query
        from app.utils.project_instructions import project_instructions_manager
        enhanced_query = project_instructions_manager.append_instructions_to_query(
            query, project_id
        )
        
        # Create history from previous SQL
        histories = []
        if previous_sql:
            histories.append(AskHistory(
                question=query,
                sql=previous_sql
            ))
        
        # Run follow-up SQL generation with enhanced query
        result = await self.followup_generator.run(
            query=enhanced_query,
            contexts=contexts,
            sql_generation_reasoning=sql_generation_reasoning,
            histories=histories,
            configuration=Configuration(),
            project_id=project_id
        )
        
        return {
            "success": bool(result.get("valid_generation_results")),
            "data": result,
            "error": result.get("error")
        }

class IntentClassificationPipeline(AgentPipeline):
    """Pipeline for intent classification"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Intent Classification Pipeline",
            version="1.0",
            description="Classifies user intents for SQL queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        self._configuration = {}
        self._metrics = {}
        self._intent_classifier = None
        self._initialized = False
        
        # Initialize intent classifier
        self._intent_classifier = IntentClassification(
            doc_store_provider=document_store_provider
        )
        self._initialized = True
        logger.info(f"Pipeline {self.name} initialized successfully")
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )

    async def run(
        self,
        query: str,
        project_id: str,
        histories: Optional[List[Dict[str, Any]]] = None,
        sql_samples: Optional[List[Dict[str, Any]]] = None,
        instructions: Optional[List[Dict[str, Any]]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Run the intent classification pipeline
        
        Args:
            query: User query
            histories: Previous conversation history
            sql_samples: Retrieved SQL samples
            instructions: Retrieved instructions
            project_id: Project identifier
            configuration: Optional configuration parameters
            **kwargs: Additional arguments
            
        Returns:
            Pipeline results containing intent classification
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
            
        try:
            config = Configuration(**configuration) if configuration else Configuration()
            
            # Run intent classification
            result = await self._intent_classifier.run(
                query=query,
                project_id=project_id,
                histories=histories,
                sql_samples=sql_samples,
                instructions=instructions,
                configuration=config
            )
            print("intent classification result", result)
            # Update metrics
            self._metrics.update({
                "last_query": query,
                "last_project_id": project_id,
                "intent": result.get("intent"),
                "success": True
            })
            
            return {
                "success": True,
                "rephrased_question": result.get("rephrased_question"),
                "intent": result.get("intent"),
                "reasoning": result.get("reasoning"),
                "results": result.get("results") or None,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error in intent classification pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

class MisleadingAssistancePipeline(AgentPipeline):
    """Pipeline for handling misleading queries"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Misleading Assistance Pipeline",
            version="1.0",
            description="Handles potentially misleading queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        # Use the provider directly
        self.misleading_assistant = MisleadingAssistance(document_store_provider)
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")  # Remove query from kwargs
        db_schemas = kwargs.get("db_schemas", [])
        language = kwargs.get("language", "English")
        query_id = kwargs.get("query_id")
        histories = kwargs.get("histories", [])
        
        # Run misleading assistance
        result = await self.misleading_assistant.run(
            query=query,
            db_schemas=db_schemas,
            language=language,
            query_id=query_id,
            histories=histories
        )
        
        return {
            "success": bool(result.get("replies")),
            "data": {
                "assistance": result.get("replies", [""])[0]
            },
            "error": None
        }

class RelationshipRecommendationPipeline(AgentPipeline):
    """Pipeline for table relationship recommendations"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Relationship Recommendation Pipeline",
            version="1.0",
            description="Recommends relationships between tables",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        # Use the provider directly
        self.relationship_recommender = RelationshipRecommendation(document_store_provider)
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        mdl = kwargs.pop("mdl", "")  # Remove mdl from kwargs
        project_id = kwargs.get("project_id")
        configuration = kwargs.get("configuration", Configuration())
        
        # Create input for relationship recommendation
        if not project_id:
            raise ValueError("project_id is required")
            
        request = RelationshipRecommendation.Input(
            id=project_id,
            mdl=mdl,
            project_id=project_id,
            configuration=configuration
        )
        
        # Run relationship recommendation
        result = await self.relationship_recommender.recommend(request)
        
        if result.status == "failed":
            return {
                "success": False,
                "data": None,
                "error": result.error.message if result.error else "Unknown error"
            }
        
        return {
            "success": result.status == "finished",
            "data": result.response,
            "error": None
        }

class SemanticsDescriptionPipeline(AgentPipeline):
    """Pipeline for SQL semantics description"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Semantics Description Pipeline",
            version="1.0",
            description="Generates semantic descriptions of SQL queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        # Use the provider directly
        self.semantics_descriptor = SemanticsDescription(document_store_provider)
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = SQLRAGAgent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        mdl = kwargs.pop("mdl", "")  # Remove mdl from kwargs
        project_id = kwargs.get("project_id")
        configuration = kwargs.get("configuration", Configuration())
        
        if not project_id:
            raise ValueError("project_id is required")
            
        # Create input for semantics description
        request = SemanticsDescription.Input(
            id=project_id,
            mdl=mdl,
            project_id=project_id,
            configuration=configuration
        )
        
        # Run semantics description
        result = await self.semantics_descriptor.describe(request)
        
        if result.status == "failed":
            return {
                "success": False,
                "data": None,
                "error": result.error.message if result.error else "Unknown error"
            }
        
        return {
            "success": result.status == "finished",
            "data": result.response,
            "error": None
        }

class AnalysisAssistancePipeline(AgentPipeline):
    """Pipeline for analysis assistance (analytical guidance and metric recommendations)"""
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Analysis Assistance Pipeline",
            version="1.0",
            description="Provides analytical guidance and metric recommendations",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.analysis_assistance = DataAssistanceTool(doc_store_provider=document_store_provider, retrieval_helper=retrieval_helper)

    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")
        db_schemas = kwargs.get("db_schemas", [])
        language = kwargs.get("language", "English")
        histories = kwargs.get("histories")
        configuration = kwargs.get("configuration")
        project_id = kwargs.get("project_id")
        timeout = kwargs.get("timeout", 30.0)
        query_id = kwargs.get("query_id")
        
        # Prepare request dataclass
        request = DataAssistanceRequest(
            query=query,
            db_schemas=db_schemas,
            language=language,
            histories=histories,
            configuration=configuration,
            project_id=project_id,
            timeout=timeout,
            query_id=query_id
        )
        
        result: DataAssistanceResult = await self.analysis_assistance.run(request)
        logger.info(f"analysis assistance result: {result}")
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "metadata": result.metadata
        }


class QuestionSuggestionPipeline(AgentPipeline):
    """Pipeline for question suggestion (example queries and analysis questions)"""
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Question Suggestion Pipeline",
            version="1.0",
            description="Provides example queries and analysis questions",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.question_suggestion = SQLQuestionSuggestionTool(doc_store_provider=document_store_provider, retrieval_helper=retrieval_helper)

    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")
        db_schemas = kwargs.get("db_schemas", [])
        language = kwargs.get("language", "English")
        histories = kwargs.get("histories")
        configuration = kwargs.get("configuration")
        project_id = kwargs.get("project_id")
        timeout = kwargs.get("timeout", 30.0)
        query_id = kwargs.get("query_id")
        
        # Prepare request dataclass
        if not project_id:
            raise ValueError("project_id is required")
            
        request = SQLQuestionSuggestionRequest(
            query_id=query_id or "default",
            query=query,
            project_id=project_id,
            language=language,
            db_schemas=db_schemas,
            histories=histories,
            configuration=configuration,
            timeout=timeout
        )
        
        result: SQLQuestionSuggestionResult = await self.question_suggestion.run(request)
        logger.info(f"question suggestion result: {result}")
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "metadata": result.metadata,
            "suggestions": result.suggestions
        }


class DataAssistancePipeline(AgentPipeline):
    """Pipeline for data assistance (schema Q&A)"""
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="Data Assistance Pipeline",
            version="1.0",
            description="Provides data assistance based on user questions and schema",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.data_assistance = DataAssistanceTool(doc_store_provider=document_store_provider, retrieval_helper=retrieval_helper)
        
       

    async def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.pop("query", "")  # Remove query from kwargs
        db_schemas = kwargs.get("db_schemas", [])
        language = kwargs.get("language", "English")
        histories = kwargs.get("histories")
        configuration = kwargs.get("configuration")
        project_id = kwargs.get("project_id")
        timeout = kwargs.get("timeout", 30.0)
        query_id = kwargs.get("query_id")
        
        # Prepare request dataclass
        request = DataAssistanceRequest(
            query=query,
            db_schemas=db_schemas,
            language=language,
            histories=histories,
            configuration=configuration,
            project_id=project_id,
            timeout=timeout,
            query_id=query_id
        )
        
        result: DataAssistanceResult = await self.data_assistance.run(request)
        logger.info(f"data assistance result I am here {result}")
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "metadata": result.metadata
        }

class SQLSummaryPipeline(AgentPipeline):
    """Pipeline for generating summaries of SQL queries and their results"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Summary Pipeline",
            version="1.0",
            description="Generates summaries of SQL queries and their results",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = create_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the SQL summary pipeline
        
        Args:
            **kwargs: Input parameters including:
                - query: The original user query
                - sql: The SQL query to summarize
                - project_id: The project ID
                - schema_context: Optional schema context
                
        Returns:
            Dict[str, Any]: Summary results containing:
                - success: Whether the summary was generated successfully
                - data: The generated summary and metadata
                - error: Any error that occurred
        """
        try:
            query = kwargs.pop("query", "")  # Remove query from kwargs
            sql = kwargs.pop("sql", "")  # Remove sql from kwargs
            project_id = kwargs.get("project_id")
            schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
            
            # Generate summary using the appropriate agent
            if self.use_enhanced_agent:
                result = await self.agent.process_sql_request_enhanced(
                    operation="SUMMARY",
                    query=query,
                    sql=sql,
                    schema_context=schema_context,
                    **kwargs
                )
            else:
                result = await self.agent.process_sql_request(
                    operation="SUMMARY",
                    query=query,
                    sql=sql,
                    **kwargs
                )
            
            return {
                "success": result.get("success", False),
                "data": {
                    "summary": result.get("summary", ""),
                    "metadata": result.get("metadata", {})
                },
                "error": result.get("error")
            }
            
        except Exception as e:
            logger.error(f"Error in SQL summary pipeline: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            } 

class SQLAnswerPipeline(AgentPipeline):
    """Pipeline for generating natural language answers from SQL results"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Answer Pipeline",
            version="1.0",
            description="Generates natural language answers from SQL query results",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Initialize the appropriate agent
        if use_enhanced_agent:
            self.agent = create_scoring_integrated_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider,
                enable_scoring=True
            )
        else:
            self.agent = create_sql_rag_agent(
                llm=llm,
                engine=engine,
                document_store_provider=document_store_provider
            )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the SQL answer pipeline
        
        Args:
            **kwargs: Input parameters including:
                - query: The original user query
                - sql: The SQL query that was executed
                - sql_data: The results from executing the SQL query
                - language: The language for the answer (default: "English")
                - project_id: The project ID
                - schema_context: Optional schema context
                
        Returns:
            Dict[str, Any]: Answer results containing:
                - success: Whether the answer was generated successfully
                - data: The generated answer and metadata
                - error: Any error that occurred
        """
        try:
            query = kwargs.pop("query", "")  # Remove query from kwargs
            sql = kwargs.pop("sql", "")  # Remove sql from kwargs
            sql_data = kwargs.pop("sql_data", {})  # Remove sql_data from kwargs
            language = kwargs.get("language", "English")
            project_id = kwargs.get("project_id")
            schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
            print("sql_data in sql answer pipeline", len(sql_data))
            # Generate answer usin g the appropriate agent
            logger.info(f"Answer pipeline: query={query}, sql={sql[:100]}..., sql_data={sql_data}")
            if self.use_enhanced_agent:
                result = await self.agent.process_sql_request_enhanced(
                    operation="ANSWER",
                    query=query,
                    sql=sql,
                    sql_data=sql_data,
                    schema_context=schema_context,
                    **kwargs
                )
            else:
                result = await self.agent.process_sql_request(
                    operation="ANSWER",
                    query=query,
                    sql=sql,
                    sql_data=sql_data,
                    **kwargs
                )
            
            logger.info(f"Answer pipeline result: {result}")
            
            success = result.get("success", False)
            if not success:
                logger.error(f"Answer pipeline failed: {result.get('error', 'Unknown error')}")
                logger.error(f"Full result: {result}")
            
            return {
                "success": success,
                "data": {
                    "answer": result.get("answer", ""),
                    "reasoning": result.get("reasoning", ""),
                    "metadata": result.get("metadata", {})
                },
                "error": result.get("error")
            }
            
        except Exception as e:
            logger.error(f"Error in SQL answer pipeline: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

# Import vulnerability knowledge from separate module
from app.utils.vulnerability_knowledge import get_vulnerability_knowledge


class SQLVulnerabilityTransformPipeline(AgentPipeline):
    """Pipeline for SQL transform generation with automatic vulnerability knowledge loading based on project_id"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        use_enhanced_agent: bool = True
    ):
        super().__init__(
            name="SQL Vulnerability Transform Pipeline",
            version="1.0",
            description="Generates SQL queries with dynamic column transformations using vulnerability knowledge for CVE data projects",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        self.use_enhanced_agent = use_enhanced_agent
        
        # Import and initialize transform agent
        from app.agents.nodes.sql.transform_sql_rag_agent import create_transform_sql_rag_agent
        
        self.agent = create_transform_sql_rag_agent(
            llm=llm,
            engine=engine,
            document_store_provider=document_store_provider
        )
        
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the SQL vulnerability transform pipeline
        
        Args:
            **kwargs: Input parameters including:
                - query: The natural language question
                - project_id: The project ID (required, "cve_data" triggers vulnerability knowledge)
                - knowledge: Additional knowledge context (List[str], optional - will be merged with vulnerability knowledge if project_id is "cve_data")
                - contexts: Schema contexts
                - language: Language for generation (default: "English")
                - schema_context: Optional schema context
                
        Returns:
            Dict[str, Any]: Transform results containing:
                - success: Whether the transform was generated successfully
                - data: The generated SQL and metadata
                - error: Any error that occurred
        """
        try:
            query = kwargs.pop("query", "")  # Remove query from kwargs
            project_id = kwargs.get("project_id")
            
            if not project_id:
                raise ValueError("project_id is required for SQLVulnerabilityTransformPipeline")
            
            # Get knowledge from kwargs, defaulting to empty list
            provided_knowledge = kwargs.pop("knowledge", []) or []
            
            # Automatically load vulnerability knowledge if project_id is "cve_data"
            knowledge = list(provided_knowledge)  # Make a copy
            if project_id == "cve_data":
                vulnerability_knowledge = get_vulnerability_knowledge()
                # Merge provided knowledge with vulnerability knowledge
                knowledge.extend(vulnerability_knowledge)
                logger.info(f"Loaded {len(vulnerability_knowledge)} vulnerability knowledge items for project_id='cve_data'")
            
            contexts = kwargs.get("contexts", [])
            language = kwargs.get("language", "English")
            schema_context = kwargs.pop("schema_context", None)  # Remove schema_context from kwargs
            
            # Append project-specific instructions to the query
            from app.utils.project_instructions import project_instructions_manager
            enhanced_query = project_instructions_manager.append_instructions_to_query(
                query, project_id
            )
            
            logger.info(f"Starting SQL vulnerability transform generation for query: {query}")
            logger.info(f"Enhanced query: {enhanced_query}")
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Total knowledge items: {len(knowledge)}")
            logger.info(f"Number of contexts: {len(contexts)}")
            
            # Process transform request using transform agent
            result = await self.agent.process_transform_request(
                query=enhanced_query,
                knowledge=knowledge,
                contexts=contexts,
                language=language,
                project_id=project_id,
                schema_context=schema_context,
                **kwargs
            )
            
            logger.info(f"SQL vulnerability transform result: {result}")
            
            # Return the result in the expected format
            return {
                "success": result.get("success", False),
                "data": result.get("data", {}),
                "error": result.get("error"),
                "metadata": {
                    "transform_type": result.get("data", {}).get("transform_type"),
                    "reasoning_plan": result.get("data", {}).get("reasoning_plan", {}),
                    "project_id": project_id,
                    "vulnerability_knowledge_loaded": project_id == "cve_data"
                }
            }
            
        except Exception as e:
            logger.error(f"Error in SQL vulnerability transform pipeline: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }