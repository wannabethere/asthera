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
    SemanticsDescriptionPipeline, DataAssistancePipeline, SQLSummaryPipeline, SQLAnswerPipeline
)
from app.agents.pipelines.retrieval_pipeline import RetrievalPipeline
from app.core.engine_provider import EngineProvider
from app.agents.pipelines.sql_execution import DataSummarizationPipeline
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
        # Get the required pipelines
        sql_pipeline = PipelineContainer.get_instance().get_pipeline("sql_generation")
        chart_pipeline = PipelineContainer.get_instance().get_pipeline("chart_generation")
        reasoning_pipeline = PipelineContainer.get_instance().get_pipeline("sql_reasoning")
        
        # Generate SQL
        sql_result = await sql_pipeline.run(input_data)
        
        # Generate chart if SQL was successful
        chart_result = {}
        if sql_result.get("success", False):
            chart_input = {
                **input_data,
                "sql_query": sql_result.get("sql_query"),
                "sql_result": sql_result.get("result")
            }
            chart_result = await chart_pipeline.run(chart_input)
        
        # Perform reasoning
        reasoning_input = {
            **input_data,
            "sql_query": sql_result.get("sql_query"),
            "sql_result": sql_result.get("result"),
            "chart_result": chart_result
        }
        reasoning_result = await reasoning_pipeline.run(reasoning_input)
        
        return {
            "success": sql_result.get("success", False),
            "sql_result": sql_result,
            "chart_result": chart_result,
            "reasoning_result": reasoning_result
        }

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
            chart_config={"type": "vega_lite"}  # Default to Vega-Lite
        )
        self._pipelines["chart_generation"]._initialized = True
        self._pipelines["chart_adjustment"] = ChartAdjustmentPipeline(
            llm=self._llm,
            retrieval_helper=self._retrieval_helper,
            document_store_provider=self._doc_store_provider,
            engine=self._engine,
            chart_config={"type": "vega_lite"}  # Default to Vega-Lite
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
    
   