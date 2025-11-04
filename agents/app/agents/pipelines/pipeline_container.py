from typing import Dict, Any, Optional, List
import logging
from langchain_openai import ChatOpenAI
import chromadb
from app.agents.pipelines.base import AgentPipeline
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_llm, get_doc_store_provider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent
from app.agents.pipelines.sql_execution import SQLExecutionPipeline, SQLValidationPipeline, UserGuideAssistancePipeline, QuestionRecommendationPipeline
from app.agents.pipelines.sql_pipelines import (
    SQLGenerationPipeline, SQLBreakdownPipeline, SQLReasoningPipeline,
    SQLCorrectionPipeline, SQLExpansionPipeline, ChartGenerationPipeline,
    ChartAdjustmentPipeline, FollowUpSQLReasoningPipeline, FollowUpSQLGenerationPipeline,
    IntentClassificationPipeline, MisleadingAssistancePipeline, RelationshipRecommendationPipeline,
    SemanticsDescriptionPipeline, DataAssistancePipeline, AnalysisAssistancePipeline,
    QuestionSuggestionPipeline, SQLSummaryPipeline, SQLAnswerPipeline
)
from app.agents.pipelines.retrieval_pipeline import RetrievalPipeline
from app.core.engine_provider import EngineProvider
from app.agents.pipelines.sql_execution import DataSummarizationPipeline

# Dashboard and Report pipeline imports removed to avoid circular imports
# These will be imported locally when needed
logger = logging.getLogger("lexy-ai-service")
settings = get_settings()

class CombinedSQLChartPipeline(AgentPipeline):
    """Pipeline that combines SQL generation, chart generation, and reasoning in one flow"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: DocumentChromaStore,
        engine: Engine
    ):
        super().__init__(
            name="combined_sql_chart",
            version="1.0",
            description="Combined SQL Generation, Chart Generation and Reasoning Pipeline",
            llm=llm
        )
        self._llm = llm
        self._retrieval_helper = retrieval_helper
        self._doc_store_provider = document_store_provider
        self._engine = engine
        
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the combined pipeline
        
        Args:
            input_data (Dict[str, Any]): Input data containing the query and context
            
        Returns:
            Dict[str, Any]: Combined results from SQL generation, chart generation and reasoning
        """
        # Note: This pipeline requires pipelines to be passed in or accessed differently
        # to avoid circular import issues. The current implementation is commented out.
        raise NotImplementedError(
            "CombinedSQLChartPipeline.run() is not implemented due to circular import constraints. "
            "Please use individual pipelines directly or restructure the pipeline architecture."
        )

class PipelineContainer:
    """Container class for managing all pipelines used in the AskService"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Ensure only one instance of PipelineContainer exists"""
        if cls._instance is None:
            cls._instance = super(PipelineContainer, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the pipeline container with all required pipelines"""
        if PipelineContainer._initialized:
            return
            
        self._pipelines: Dict[str, AgentPipeline] = {}
        
        # Initialize core dependencies
        self._llm = get_llm(temperature=0.0, model="gpt-4")
        self._retrieval_helper = RetrievalHelper()
        self._doc_store_provider = get_doc_store_provider()
        self._engine = EngineProvider.get_engine()
        
        # Initialize SQL RAG Agent
        self._sql_rag_agent = SQLRAGAgent(
            llm=self._llm,
            engine=self._engine,
            document_store_provider=self._doc_store_provider,
            retrieval_helper=self._retrieval_helper
        )
        
        PipelineContainer._initialized = True
    
    @classmethod
    def initialize(cls) -> 'PipelineContainer':
        """Static initialization method to create and configure the pipeline container
        
        Returns:
            PipelineContainer: The initialized pipeline container instance
        """
        if not cls._initialized:
            instance = cls()
            instance._initialize_pipelines()
            return instance
        return cls._instance
    
    def _initialize_pipelines(self):
        """Initialize all required pipelines"""
        # Initialize SQL pipeline
        self._pipelines["sql_pipeline"] = SQLGenerationPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["sql_pipeline"]._initialized = True
        # Initialize combined SQL and Chart pipeline
        self._pipelines["combined_sql_chart"] = CombinedSQLChartPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["combined_sql_chart"]._initialized = True
        # Initialize intent classification pipeline
        self._pipelines["intent_classification"] = IntentClassificationPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider
        )
        self._pipelines["intent_classification"]._initialized = True
        # Initialize retrieval pipelines
        self._pipelines["historical_question"] = RetrievalPipeline(
            name="historical_question",
            version="1.0",
            description="Historical Question Retrieval Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper
        )
        self._pipelines["historical_question"]._initialized = True
        
        self._pipelines["sql_pairs"] = RetrievalPipeline(
            name="sql_pairs",
            version="1.0",
            description="SQL Pairs Retrieval Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper
        )
        self._pipelines["sql_pairs"]._initialized = True
        
        self._pipelines["instructions"] = RetrievalPipeline(
            name="instructions",
            version="1.0",
            description="Instructions Retrieval Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper
        )
        self._pipelines["instructions"]._initialized = True
        
        self._pipelines["database_schemas"] = RetrievalPipeline(
            name="db_schema",
            version="1.0",
            description="Database Schemas Retrieval Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper
        )
        
        self._pipelines["database_schemas"]._initialized = True
        
        self._pipelines["metrics"] = RetrievalPipeline(
            name="db_schema",
            version="1.0",
            description="Database Schemas Retrieval Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper
        )
        self._pipelines["metrics"]._initialized = True

        self._pipelines["views"] = RetrievalPipeline(
            name="db_schema",
            version="1.0",
            description="Database Schemas Retrieval Pipeline",  
            llm=self._llm,
            retrieval_helper=self._retrieval_helper
        )
        self._pipelines["views"]._initialized = True

        # Initialize SQL generation and reasoning pipelines
        self._pipelines["sql_generation"] = SQLGenerationPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["sql_generation"]._initialized = True
        # Initialize SQL execution and validation pipelines
        self._pipelines["sql_execution"] = SQLExecutionPipeline(
            name="sql_execution",
            version="1.0",
            description="SQL Execution Pipeline",
            llm=self._llm,
            engine=self._engine,
            retrieval_helper=self._retrieval_helper
        )
        
        self._pipelines["sql_execution"]._initialized = True
        self._pipelines["sql_validation"] = SQLValidationPipeline(
            name="sql_validation",
            version="1.0",
            description="SQL Validation Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper
        )
        self._pipelines["sql_validation"]._initialized = True
        # Initialize SQL summary pipeline
        self._pipelines["sql_summary"] = SQLSummaryPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine,
        )
        self._pipelines["sql_summary"]._initialized = True
        self._pipelines["sql_breakdown"] = SQLBreakdownPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine,
        )
        self._pipelines["sql_breakdown"]._initialized = True
        self._pipelines["sql_expansion"] = SQLExpansionPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["sql_expansion"]._initialized = True
        
        self._pipelines["relationship_recommendation"] = RelationshipRecommendationPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["relationship_recommendation"]._initialized = True
        
        self._pipelines["semantics_description"] = SemanticsDescriptionPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["semantics_description"]._initialized = True
        self._pipelines["sql_reasoning"] = SQLReasoningPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["sql_reasoning"]._initialized = True
        # Initialize SQL answer pipeline
        self._pipelines["sql_answer"] = SQLAnswerPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        
        self._pipelines["followup_sql_generation"] = FollowUpSQLGenerationPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["followup_sql_generation"]._initialized = True
        self._pipelines["sql_correction"] = SQLCorrectionPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["sql_correction"]._initialized = True
        self._pipelines["followup_sql_reasoning"] = FollowUpSQLReasoningPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["followup_sql_reasoning"]._initialized = True
        # Initialize chart generation and adjustment pipelines
        self._pipelines["chart_generation"] = ChartGenerationPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine,
            chart_config={"type": "enhanced_vega_lite"}  # Use enhanced Vega-Lite for KPI support
        )
        self._pipelines["chart_generation"]._initialized = True
        self._pipelines["chart_adjustment"] = ChartAdjustmentPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine,
            chart_config={"type": "enhanced_vega_lite"}  # Use enhanced Vega-Lite for KPI support
        )
        self._pipelines["chart_adjustment"]._initialized = True
        # Initialize assistance pipelines
        self._pipelines["misleading_assistance"] = MisleadingAssistancePipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["misleading_assistance"]._initialized = True
        self._pipelines["data_assistance"] = DataAssistancePipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["data_assistance"]._initialized = True
        # Initialize analysis assistance pipeline
        self._pipelines["analysis_assistance"] = AnalysisAssistancePipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["analysis_assistance"]._initialized = True
        # Initialize question suggestion pipeline
        self._pipelines["question_suggestion"] = QuestionSuggestionPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine
        )
        self._pipelines["question_suggestion"]._initialized = True
        # Initialize question recommendation pipeline
        self._pipelines["question_recommendation"] = QuestionRecommendationPipeline(
            name="question_recommendation",
            version="1.0",
            description="Question Recommendation Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider
        )
        self._pipelines["question_recommendation"]._initialized = True
        # Initialize user guide assistance pipeline
        self._pipelines["user_guide"] = UserGuideAssistancePipeline(
            name="user_guide",
            version="1.0",
            description="User Guide Assistance Pipeline",
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider
        )
        self._pipelines["user_guide"]._initialized = True
        # Initialize the data summarization pipeline
        self._pipelines["data_summarization"] = DataSummarizationPipeline(
            name="data_summarization",
            version="1.0",
            description="Pipeline for generating data summaries using recursive summarization",
            llm=self._llm,
            engine=self._engine,  # You'll need to configure this with your database connection
            retrieval_helper=self._retrieval_helper
        )
        
        self._pipelines["data_summarization"]._initialized = True
        
        # Initialize dashboard pipelines with local imports to avoid circular dependencies
        try:
            from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
            self._pipelines["dashboard_streaming"] = create_dashboard_streaming_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper
            )
            self._pipelines["dashboard_streaming"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import dashboard streaming pipeline: {e}")
            self._pipelines["dashboard_streaming"] = None
        
        try:
            from app.agents.pipelines.writers.conditional_formatting_generation_pipeline import create_conditional_formatting_generation_pipeline
            self._pipelines["conditional_formatting_generation"] = create_conditional_formatting_generation_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper,
                document_store_provider=self._doc_store_provider
            )
            self._pipelines["conditional_formatting_generation"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import conditional formatting pipeline: {e}")
            self._pipelines["conditional_formatting_generation"] = None
        
        try:
            from app.agents.pipelines.writers.enhanced_dashboard_streaming_pipeline import create_enhanced_dashboard_streaming_pipeline
            if self._pipelines.get("dashboard_streaming"):
                self._pipelines["enhanced_dashboard_streaming"] = create_enhanced_dashboard_streaming_pipeline(
                    engine=self._engine,
                    llm=self._llm,
                    retrieval_helper=self._retrieval_helper,
                    dashboard_streaming_pipeline=self._pipelines["dashboard_streaming"]
                )
                self._pipelines["enhanced_dashboard_streaming"]._initialized = True
            else:
                logger.warning("Enhanced dashboard streaming pipeline not created due to missing dashboard streaming pipeline")
                self._pipelines["enhanced_dashboard_streaming"] = None
        except ImportError as e:
            logger.warning(f"Failed to import enhanced dashboard streaming pipeline: {e}")
            self._pipelines["enhanced_dashboard_streaming"] = None
        
        # Initialize dashboard summary pipeline
        try:
            from app.agents.pipelines.writers.dashboard_summary_pipeline import create_dashboard_summary_pipeline
            self._pipelines["dashboard_summary"] = create_dashboard_summary_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper
            )
            self._pipelines["dashboard_summary"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import dashboard summary pipeline: {e}")
            self._pipelines["dashboard_summary"] = None
        
        # Initialize dashboard orchestrator pipeline
        try:
            from app.agents.pipelines.writers.dashboard_orchestrator_pipeline import create_dashboard_orchestrator_pipeline
            self._pipelines["dashboard_orchestrator"] = create_dashboard_orchestrator_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper,
                conditional_formatting_pipeline=self._pipelines.get("conditional_formatting_generation"),
                enhanced_streaming_pipeline=self._pipelines.get("enhanced_dashboard_streaming"),
                dashboard_summary_pipeline=self._pipelines.get("dashboard_summary")
            )
            self._pipelines["dashboard_orchestrator"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import dashboard orchestrator pipeline: {e}")
            self._pipelines["dashboard_orchestrator"] = None
        
        # Initialize report generation pipelines
        try:
            from app.agents.pipelines.writers.simple_report_generation_pipeline import create_simple_report_generation_pipeline
            self._pipelines["simple_report_generation"] = create_simple_report_generation_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper
            )
            self._pipelines["simple_report_generation"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import simple report generation pipeline: {e}")
            self._pipelines["simple_report_generation"] = None
        
        try:
            from app.agents.pipelines.writers.report_orchestrator_pipeline import create_report_orchestrator_pipeline
            self._pipelines["report_orchestrator"] = create_report_orchestrator_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper,
                conditional_formatting_pipeline=self._pipelines.get("conditional_formatting_generation"),
                simple_report_pipeline=self._pipelines.get("simple_report_generation"),
                report_summary_pipeline=self._pipelines.get("dashboard_summary")
            )
            self._pipelines["report_orchestrator"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import report orchestrator pipeline: {e}")
            self._pipelines["report_orchestrator"] = None
        
        # Initialize alert orchestrator pipeline
        try:
            from app.agents.pipelines.writers.alert_orchestrator_pipeline import create_alert_orchestrator_pipeline
            self._pipelines["alert_orchestrator"] = create_alert_orchestrator_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper,
                sql_execution_pipeline=self._pipelines.get("sql_execution")
            )
            self._pipelines["alert_orchestrator"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import alert orchestrator pipeline: {e}")
            self._pipelines["alert_orchestrator"] = None
        
        # Initialize feed management pipeline
        try:
            from app.agents.pipelines.writers.feed_management_pipeline import create_feed_management_pipeline
            self._pipelines["feed_management"] = create_feed_management_pipeline(
                engine=self._engine,
                llm=self._llm,
                retrieval_helper=self._retrieval_helper
            )
            self._pipelines["feed_management"]._initialized = True
        except ImportError as e:
            logger.warning(f"Failed to import feed management pipeline: {e}")
            self._pipelines["feed_management"] = None
    
    @classmethod
    def get_instance(cls) -> 'PipelineContainer':
        """Get the singleton instance of PipelineContainer
        
        Returns:
            PipelineContainer: The singleton instance
        """
        if cls._instance is None:
            raise RuntimeError("PipelineContainer not initialized. Call initialize() first.")
        return cls._instance
    
    def get_pipeline(self, name: str) -> AgentPipeline:
        """Get a pipeline by name
        
        Args:
            name (str): Name of the pipeline to get
            
        Returns:
            AgentPipeline: The requested pipeline
            
        Raises:
            KeyError: If pipeline with given name doesn't exist
        """
        # Handle both enum and string cases
        pipeline_name = name.value if hasattr(name, 'value') else name
        
        if pipeline_name not in self._pipelines:
            raise KeyError(f"Pipeline '{pipeline_name}' not found")
        return self._pipelines[pipeline_name]
    
    def get_all_pipelines(self) -> Dict[str, AgentPipeline]:
        """Get all pipelines
        
        Returns:
            Dict[str, AgentPipeline]: Dictionary of all pipelines
        """
        return self._pipelines.copy()
    
   