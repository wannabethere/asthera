from typing import Dict, Any, Optional, List
import logging
from langchain_openai import ChatOpenAI
import chromadb
from enum import Enum
from app.pipelines.base import AgentPipeline
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_llm, get_doc_store_provider
from app.core.engine import Engine
from app.core.engine_provider import EngineProvider
from app.pipelines.mlpipelines.stats_pipelines import (
    AnalysisIntentClassificationPipeline,
    SelfCorrectingPipelineCodeGenPipeline,
    create_analysis_intent_pipeline,
    create_self_correcting_pipeline_codegen_pipeline
)


logger = logging.getLogger("lexy-ai-service")
settings = get_settings()


class PipelineType(Enum):
    """Supported pipeline types"""
    ANALYSIS_INTENT_CLASSIFICATION = "analysis_intent_classification_pipeline"
    SELF_CORRECTING_PIPELINE_CODEGEN = "self_correcting_pipeline_codegen_pipeline"


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
        self._doc_store_provider = get_doc_store_provider()
        self._engine = EngineProvider.get_engine()
        
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
    
    @classmethod
    async def initialize_async(cls) -> 'PipelineContainer':
        """Static async initialization method to create and configure the pipeline container
        
        Returns:
            PipelineContainer: The initialized pipeline container instance
        """
        if not cls._initialized:
            instance = cls()
            instance._initialize_pipelines()
            await instance._initialize_pipeline_async()
            return instance
        return cls._instance
    
    def _initialize_pipelines(self):
        """Initialize all required pipelines"""
        try:
            logger.info("Initializing pipeline container...")
            
            # Get document stores from provider
            function_collection = self._doc_store_provider.get_collection("function_definitions")
            example_collection = self._doc_store_provider.get_collection("function_examples")
            insights_collection = self._doc_store_provider.get_collection("function_insights")
            usage_examples_store = self._doc_store_provider.get_collection("usage_examples")
            code_examples_store = self._doc_store_provider.get_collection("code_examples")
            function_definition_store = self._doc_store_provider.get_collection("function_definitions")
            logical_reasoning_store = self._doc_store_provider.get_collection("logical_reasoning")
            
            # Initialize Analysis Intent Classification Pipeline
            logger.info("Initializing Analysis Intent Classification Pipeline...")
            analysis_intent_pipeline = create_analysis_intent_pipeline(
                llm=self._llm,
                function_collection=function_collection,
                example_collection=example_collection,
                insights_collection=insights_collection,
                retrieval_helper=None,  # Will be set if needed
                document_store_provider=self._doc_store_provider,
                engine=self._engine,
                pipeline_config={
                    "max_functions_to_retrieve": 10,
                    "enable_quick_check": True,
                    "enable_llm_feasibility": True
                }
            )
            
            # Initialize Self-Correcting Pipeline Code Generation Pipeline
            logger.info("Initializing Self-Correcting Pipeline Code Generation Pipeline...")
            self_correcting_pipeline = create_self_correcting_pipeline_codegen_pipeline(
                llm=self._llm,
                usage_examples_store=usage_examples_store,
                code_examples_store=code_examples_store,
                function_definition_store=function_definition_store,
                logical_reasoning_store=logical_reasoning_store,
                max_iterations=3,
                relevance_threshold=0.7,
                pipeline_config={
                    "enable_self_correction": True,
                    "enable_rag_enhancement": True,
                    "max_code_generation_attempts": 3
                }
            )
            
            # Register pipelines
            self._pipelines[PipelineType.ANALYSIS_INTENT_CLASSIFICATION.value] = analysis_intent_pipeline
            self._pipelines[PipelineType.SELF_CORRECTING_PIPELINE_CODEGEN.value] = self_correcting_pipeline
            
            logger.info(f"Pipeline container initialized successfully with {len(self._pipelines)} pipelines")
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline container: {e}")
            raise
    
    async def _initialize_pipeline_async(self):
        """Initialize all pipelines asynchronously"""
        try:
            # Initialize all pipelines
            for name, pipeline in self._pipelines.items():
                logger.info(f"Initializing pipeline: {name}")
                await pipeline.initialize()
            
            logger.info("All pipelines initialized asynchronously")
            
        except Exception as e:
            logger.error(f"Failed to initialize pipelines asynchronously: {e}")
            raise
    
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
    
    def get_pipeline_names(self) -> List[str]:
        """Get list of all available pipeline names
        
        Returns:
            List[str]: List of pipeline names
        """
        return list(self._pipelines.keys())
    
    def get_pipeline_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all pipelines
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary with pipeline information
        """
        pipeline_info = {}
        for name, pipeline in self._pipelines.items():
            pipeline_info[name] = {
                "name": pipeline.name,
                "version": pipeline.version,
                "description": pipeline.description,
                "is_initialized": pipeline.is_initialized,
                "metrics": pipeline.get_metrics() if hasattr(pipeline, 'get_metrics') else {}
            }
        return pipeline_info
    
    async def cleanup_all_pipelines(self):
        """Clean up all pipelines"""
        logger.info("Cleaning up all pipelines...")
        for name, pipeline in self._pipelines.items():
            try:
                logger.info(f"Cleaning up pipeline: {name}")
                await pipeline.cleanup()
            except Exception as e:
                logger.error(f"Failed to cleanup pipeline {name}: {e}")
        logger.info("All pipelines cleaned up")
    
    def get_analysis_intent_pipeline(self) -> AnalysisIntentClassificationPipeline:
        """Get the analysis intent classification pipeline
        
        Returns:
            AnalysisIntentClassificationPipeline: The analysis intent pipeline
        """
        return self.get_pipeline(PipelineType.ANALYSIS_INTENT_CLASSIFICATION.value)
    
    def get_self_correcting_pipeline_codegen(self) -> SelfCorrectingPipelineCodeGenPipeline:
        """Get the self-correcting pipeline code generation pipeline
        
        Returns:
            SelfCorrectingPipelineCodeGenPipeline: The self-correcting pipeline codegen
        """
        return self.get_pipeline(PipelineType.SELF_CORRECTING_PIPELINE_CODEGEN.value)
    
   