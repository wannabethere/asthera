import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import json

from langchain_openai import ChatOpenAI
from langfuse.decorators import observe

from app.pipelines.base import AgentPipeline
from app.agents.nodes.mlagents.analysis_intent_classification import (
    AnalysisIntentPlanner, 
    AnalysisIntentResult
)
from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator
from app.storage.documents import DocumentChromaStore
from app.core.engine import Engine
from app.core.provider import DocumentStoreProvider

logger = logging.getLogger("analysis-intent-pipeline")


class AnalysisIntentClassificationPipeline(AgentPipeline):
    """
    Pipeline for running analysis intent classification using the AnalysisIntentPlanner.
    
    This pipeline provides async flow capabilities for classifying user questions
    and determining the appropriate analysis approach based on available data and functions.
    """
    
    def __init__(
        self,
        llm: ChatOpenAI,
        function_collection: Optional[DocumentChromaStore] = None,
        example_collection: Optional[DocumentChromaStore] = None,
        insights_collection: Optional[DocumentChromaStore] = None,
        retrieval_helper=None,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        max_functions_to_retrieve: int = 10,
        pipeline_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the Analysis Intent Classification Pipeline
        
        Args:
            llm: Language model instance
            function_collection: ChromaDB collection for function definitions
            example_collection: ChromaDB collection for function examples
            insights_collection: ChromaDB collection for function insights
            retrieval_helper: Optional retrieval helper instance
            document_store_provider: Optional document store provider instance
            engine: Optional engine instance
            max_functions_to_retrieve: Maximum number of functions to retrieve
            pipeline_config: Optional pipeline configuration
        """
        super().__init__(
            name="analysis_intent_classification_pipeline",
            version="1.0.0",
            description="Pipeline for classifying user analysis intent and determining feasibility",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        
        # Initialize the analysis intent planner
        self.analysis_planner = AnalysisIntentPlanner(
            llm=llm,
            function_collection=function_collection,
            example_collection=example_collection,
            insights_collection=insights_collection,
            max_functions_to_retrieve=max_functions_to_retrieve
        )
        
        # Pipeline configuration
        self.pipeline_config = pipeline_config or {}
        self.max_functions_to_retrieve = max_functions_to_retrieve
        
        # Performance metrics
        self._metrics = {
            "total_requests": 0,
            "successful_classifications": 0,
            "failed_classifications": 0,
            "average_processing_time": 0.0,
            "total_processing_time": 0.0,
            "last_request_time": None
        }
        
        # Pipeline state
        self._current_config = {}
        
    async def initialize(self, **kwargs) -> None:
        """
        Initialize the pipeline with any required resources
        
        Args:
            **kwargs: Initialization parameters
        """
        await super().initialize()
        
        # Initialize configuration
        self._current_config.update(kwargs)
        
        # Validate required components
        if not self.analysis_planner:
            raise ValueError("AnalysisIntentPlanner not properly initialized")
            
        logger.info(f"Analysis Intent Classification Pipeline initialized successfully")
        
    async def cleanup(self) -> None:
        """Clean up any resources used by the pipeline"""
        await super().cleanup()
        
        # Clear any cached data
        if hasattr(self.analysis_planner, '_function_spec_cache'):
            self.analysis_planner._function_spec_cache.clear()
            
        logger.info("Analysis Intent Classification Pipeline cleaned up successfully")
        
    @observe(name="Analysis Intent Classification Pipeline")
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Run the analysis intent classification pipeline
        
        Args:
            **kwargs: Pipeline parameters including:
                - question: User's natural language question (required)
                - dataframe_description: Description of the dataframe (optional)
                - dataframe_summary: Summary of the dataframe (optional)
                - available_columns: List of available columns (optional)
                - enable_quick_check: Whether to enable quick feasibility check (default: True)
                - enable_llm_feasibility: Whether to enable LLM-based feasibility assessment (default: True)
                
        Returns:
            Dict containing pipeline results with classification and metadata
        """
        start_time = datetime.now()
        self._metrics["total_requests"] += 1
        self._metrics["last_request_time"] = start_time
        
        try:
            # Extract parameters
            question = kwargs.get("question")
            if not question:
                raise ValueError("'question' parameter is required")
                
            dataframe_description = kwargs.get("dataframe_description", "")
            dataframe_summary = kwargs.get("dataframe_summary", "")
            available_columns = kwargs.get("available_columns", [])
            enable_quick_check = kwargs.get("enable_quick_check", True)
            enable_llm_feasibility = kwargs.get("enable_llm_feasibility", True)
            
            # Validate inputs
            if not isinstance(question, str) or not question.strip():
                raise ValueError("Question must be a non-empty string")
                
            if available_columns and not isinstance(available_columns, list):
                raise ValueError("Available columns must be a list")
                
            # Step 1: Quick feasibility check (optional)
            quick_check_result = None
            if enable_quick_check and available_columns:
                try:
                    quick_check_result = await self.analysis_planner.quick_feasibility_check(
                        question=question,
                        available_columns=available_columns,
                        dataframe_description=dataframe_description
                    )
                    logger.info(f"Quick feasibility check completed: {quick_check_result.get('feasible', False)}")
                except Exception as e:
                    logger.warning(f"Quick feasibility check failed: {e}")
                    quick_check_result = {"error": str(e)}
            
            # Step 2: Full intent classification
            classification_result = await self.analysis_planner.classify_intent(
                question=question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns
            )
            
            # Step 3: Enhanced feasibility assessment (optional)
            enhanced_feasibility = None
            if enable_llm_feasibility and classification_result.required_data_columns and available_columns:
                try:
                    enhanced_feasibility = await self.analysis_planner._assess_data_feasibility_with_llm(
                        required_columns=classification_result.required_data_columns,
                        available_columns=available_columns,
                        question=question,
                        dataframe_description=dataframe_description,
                        dataframe_summary=dataframe_summary
                    )
                    logger.info("Enhanced feasibility assessment completed")
                except Exception as e:
                    logger.warning(f"Enhanced feasibility assessment failed: {e}")
                    enhanced_feasibility = {"error": str(e)}
            
            # Step 4: Prepare results
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Update metrics
            self._metrics["successful_classifications"] += 1
            self._metrics["total_processing_time"] += processing_time
            self._metrics["average_processing_time"] = (
                self._metrics["total_processing_time"] / self._metrics["successful_classifications"]
            )
            
            # Prepare response
            result = {
                "pipeline_info": {
                    "name": self.name,
                    "version": self.version,
                    "processing_time_seconds": processing_time,
                    "timestamp": end_time.isoformat()
                },
                "input": {
                    "question": question,
                    "dataframe_description": dataframe_description,
                    "dataframe_summary": dataframe_summary,
                    "available_columns": available_columns,
                    "enable_quick_check": enable_quick_check,
                    "enable_llm_feasibility": enable_llm_feasibility
                },
                "classification": {
                    "intent_type": classification_result.intent_type,
                    "confidence_score": classification_result.confidence_score,
                    "rephrased_question": classification_result.rephrased_question,
                    "suggested_functions": classification_result.suggested_functions,
                    "reasoning": classification_result.reasoning,
                    "required_data_columns": classification_result.required_data_columns,
                    "clarification_needed": classification_result.clarification_needed,
                    "specific_function_matches": classification_result.specific_function_matches,
                    "can_be_answered": classification_result.can_be_answered,
                    "feasibility_score": classification_result.feasibility_score,
                    "missing_columns": classification_result.missing_columns,
                    "available_alternatives": classification_result.available_alternatives,
                    "data_suggestions": classification_result.data_suggestions
                },
                "quick_check": quick_check_result,
                "enhanced_feasibility": enhanced_feasibility,
                "retrieved_functions": classification_result.retrieved_functions,
                "status": "success"
            }
            
            logger.info(f"Analysis intent classification completed successfully in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            # Update metrics for failed requests
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            self._metrics["failed_classifications"] += 1
            
            logger.error(f"Analysis intent classification failed: {e}")
            
            return {
                "pipeline_info": {
                    "name": self.name,
                    "version": self.version,
                    "processing_time_seconds": processing_time,
                    "timestamp": end_time.isoformat()
                },
                "input": kwargs,
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                },
                "status": "error"
            }
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        return {
            "pipeline_name": self.name,
            "pipeline_version": self.version,
            "max_functions_to_retrieve": self.max_functions_to_retrieve,
            "pipeline_config": self.pipeline_config,
            "current_config": self._current_config,
            "is_initialized": self.is_initialized
        }
    
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """
        Update the pipeline configuration
        
        Args:
            config: New configuration parameters
        """
        if "max_functions_to_retrieve" in config:
            self.max_functions_to_retrieve = config["max_functions_to_retrieve"]
            if hasattr(self.analysis_planner, 'max_functions_to_retrieve'):
                self.analysis_planner.max_functions_to_retrieve = self.max_functions_to_retrieve
                
        if "pipeline_config" in config:
            self.pipeline_config.update(config["pipeline_config"])
            
        self._current_config.update(config)
        logger.info(f"Pipeline configuration updated: {list(config.keys())}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the pipeline"""
        return {
            "pipeline_name": self.name,
            "total_requests": self._metrics["total_requests"],
            "successful_classifications": self._metrics["successful_classifications"],
            "failed_classifications": self._metrics["failed_classifications"],
            "success_rate": (
                self._metrics["successful_classifications"] / max(self._metrics["total_requests"], 1)
            ),
            "average_processing_time": self._metrics["average_processing_time"],
            "total_processing_time": self._metrics["total_processing_time"],
            "last_request_time": self._metrics["last_request_time"].isoformat() if self._metrics["last_request_time"] else None
        }
    
    def reset_metrics(self) -> None:
        """Reset the pipeline's performance metrics"""
        self._metrics = {
            "total_requests": 0,
            "successful_classifications": 0,
            "failed_classifications": 0,
            "average_processing_time": 0.0,
            "total_processing_time": 0.0,
            "last_request_time": None
        }
        logger.info("Pipeline metrics reset")
    
    async def batch_classify_intents(
        self, 
        questions: List[Dict[str, Any]], 
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process multiple questions in batches for efficiency
        
        Args:
            questions: List of question dictionaries with parameters
            batch_size: Number of questions to process concurrently
            
        Returns:
            List of classification results
        """
        results = []
        
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [self.run(**question_params) for question_params in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle any exceptions in batch results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error for question {i + j}: {result}")
                    results.append({
                        "pipeline_info": {
                            "name": self.name,
                            "version": self.version,
                            "timestamp": datetime.now().isoformat()
                        },
                        "input": batch[j],
                        "error": {
                            "message": str(result),
                            "type": type(result).__name__
                        },
                        "status": "error"
                    })
                else:
                    results.append(result)
        
        return results
    
    async def classify_with_retry(
        self, 
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run classification with retry logic for resilience
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            **kwargs: Pipeline parameters
            
        Returns:
            Classification result
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await self.run(**kwargs)
                
                # Check if the result indicates an error
                if result.get("status") == "error":
                    raise Exception(result.get("error", {}).get("message", "Unknown error"))
                    
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Classification attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"All {max_retries + 1} classification attempts failed")
                    break
        
        # Return error result if all retries failed
        return {
            "pipeline_info": {
                "name": self.name,
                "version": self.version,
                "timestamp": datetime.now().isoformat(),
                "retry_attempts": max_retries + 1
            },
            "input": kwargs,
            "error": {
                "message": f"All retry attempts failed. Last error: {str(last_exception)}",
                "type": type(last_exception).__name__ if last_exception else "UnknownError"
            },
            "status": "error"
        }
    
    def get_available_analyses(self) -> Dict[str, str]:
        """Get available analysis types and their descriptions"""
        return self.analysis_planner.get_available_analyses()
    
    async def validate_input(self, **kwargs) -> Dict[str, Any]:
        """
        Validate input parameters before processing
        
        Args:
            **kwargs: Input parameters to validate
            
        Returns:
            Validation result
        """
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required parameters
        if "question" not in kwargs:
            validation_result["is_valid"] = False
            validation_result["errors"].append("'question' parameter is required")
        elif not isinstance(kwargs["question"], str) or not kwargs["question"].strip():
            validation_result["is_valid"] = False
            validation_result["errors"].append("'question' must be a non-empty string")
        
        # Check optional parameters
        if "available_columns" in kwargs and not isinstance(kwargs["available_columns"], list):
            validation_result["is_valid"] = False
            validation_result["errors"].append("'available_columns' must be a list")
        
        if "dataframe_description" in kwargs and not isinstance(kwargs["dataframe_description"], str):
            validation_result["warnings"].append("'dataframe_description' should be a string")
            
        if "dataframe_summary" in kwargs and not isinstance(kwargs["dataframe_summary"], str):
            validation_result["warnings"].append("'dataframe_summary' should be a string")
        
        # Check configuration parameters
        if "enable_quick_check" in kwargs and not isinstance(kwargs["enable_quick_check"], bool):
            validation_result["warnings"].append("'enable_quick_check' should be a boolean")
            
        if "enable_llm_feasibility" in kwargs and not isinstance(kwargs["enable_llm_feasibility"], bool):
            validation_result["warnings"].append("'enable_llm_feasibility' should be a boolean")
        
        return validation_result


class SelfCorrectingPipelineCodeGenPipeline(AgentPipeline):
    """
    Pipeline for generating self-correcting pipeline code using SelfCorrectingPipelineCodeGenerator.
    Provides async flow for code generation with self-correction and RAG.
    """
    def __init__(
        self,
        llm: ChatOpenAI,
        usage_examples_store: DocumentChromaStore,
        code_examples_store: DocumentChromaStore,
        function_definition_store: DocumentChromaStore,
        logical_reasoning_store: Optional[DocumentChromaStore] = None,
        max_iterations: int = 3,
        relevance_threshold: float = 0.7,
        pipeline_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            name="self_correcting_pipeline_codegen_pipeline",
            version="1.0.0",
            description="Pipeline for self-correcting pipeline code generation",
            llm=llm,
            **kwargs
        )
        self.generator = SelfCorrectingPipelineCodeGenerator(
            llm=llm,
            usage_examples_store=usage_examples_store,
            code_examples_store=code_examples_store,
            function_definition_store=function_definition_store,
            logical_reasoning_store=logical_reasoning_store,
            max_iterations=max_iterations,
            relevance_threshold=relevance_threshold
        )
        self.pipeline_config = pipeline_config or {}
        self._metrics = {
            "total_requests": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "average_processing_time": 0.0,
            "total_processing_time": 0.0,
            "last_request_time": None
        }

    async def initialize(self, **kwargs) -> None:
        await super().initialize()
        # No-op for now

    async def cleanup(self) -> None:
        await super().cleanup()
        # No-op for now

    @observe(name="SelfCorrectingPipelineCodeGenPipeline")
    async def run(self, **kwargs) -> Dict[str, Any]:
        start_time = datetime.now()
        self._metrics["total_requests"] += 1
        self._metrics["last_request_time"] = start_time
        try:
            context = kwargs["context"]
            function_name = kwargs["function_name"]
            function_inputs = kwargs.get("function_inputs", {})
            dataframe_name = kwargs.get("dataframe_name", "df")
            classification = kwargs.get("classification")
            dataset_description = kwargs.get("dataset_description")
            columns_description = kwargs.get("columns_description")
            result = await self.generator.generate_pipeline_code(
                context=context,
                function_name=function_name,
                function_inputs=function_inputs,
                dataframe_name=dataframe_name,
                classification=classification,
                dataset_description=dataset_description,
                columns_description=columns_description
            )
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            self._metrics["successful_generations"] += 1
            self._metrics["total_processing_time"] += processing_time
            self._metrics["average_processing_time"] = (
                self._metrics["total_processing_time"] / self._metrics["successful_generations"]
            )
            return {
                "pipeline_info": {
                    "name": self.name,
                    "version": self.version,
                    "processing_time_seconds": processing_time,
                    "timestamp": end_time.isoformat()
                },
                "input": kwargs,
                "result": result,
                "status": "success"
            }
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            self._metrics["failed_generations"] += 1
            return {
                "pipeline_info": {
                    "name": self.name,
                    "version": self.version,
                    "processing_time_seconds": processing_time,
                    "timestamp": end_time.isoformat()
                },
                "input": kwargs,
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                },
                "status": "error"
            }

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "pipeline_name": self.name,
            "total_requests": self._metrics["total_requests"],
            "successful_generations": self._metrics["successful_generations"],
            "failed_generations": self._metrics["failed_generations"],
            "success_rate": (
                self._metrics["successful_generations"] / max(self._metrics["total_requests"], 1)
            ),
            "average_processing_time": self._metrics["average_processing_time"],
            "total_processing_time": self._metrics["total_processing_time"],
            "last_request_time": self._metrics["last_request_time"].isoformat() if self._metrics["last_request_time"] else None
        }

    def reset_metrics(self) -> None:
        self._metrics = {
            "total_requests": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "average_processing_time": 0.0,
            "total_processing_time": 0.0,
            "last_request_time": None
        }


# Factory function for creating pipeline instances
def create_analysis_intent_pipeline(
    llm: ChatOpenAI,
    function_collection: Optional[DocumentChromaStore] = None,
    example_collection: Optional[DocumentChromaStore] = None,
    insights_collection: Optional[DocumentChromaStore] = None,
    pipeline_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> AnalysisIntentClassificationPipeline:
    """
    Factory function to create an AnalysisIntentClassificationPipeline instance
    
    Args:
        llm: Language model instance
        function_collection: ChromaDB collection for function definitions
        example_collection: ChromaDB collection for function examples
        insights_collection: ChromaDB collection for function insights
        pipeline_config: Optional pipeline configuration
        **kwargs: Additional arguments for the pipeline
        
    Returns:
        Configured AnalysisIntentClassificationPipeline instance
    """
    return AnalysisIntentClassificationPipeline(
        llm=llm,
        function_collection=function_collection,
        example_collection=example_collection,
        insights_collection=insights_collection,
        pipeline_config=pipeline_config,
        **kwargs
    )


def create_self_correcting_pipeline_codegen_pipeline(
    llm: ChatOpenAI,
    usage_examples_store: DocumentChromaStore,
    code_examples_store: DocumentChromaStore,
    function_definition_store: DocumentChromaStore,
    logical_reasoning_store: Optional[DocumentChromaStore] = None,
    max_iterations: int = 3,
    relevance_threshold: float = 0.7,
    pipeline_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> SelfCorrectingPipelineCodeGenPipeline:
    """
    Factory function to create a SelfCorrectingPipelineCodeGenPipeline instance
    """
    return SelfCorrectingPipelineCodeGenPipeline(
        llm=llm,
        usage_examples_store=usage_examples_store,
        code_examples_store=code_examples_store,
        function_definition_store=function_definition_store,
        logical_reasoning_store=logical_reasoning_store,
        max_iterations=max_iterations,
        relevance_threshold=relevance_threshold,
        pipeline_config=pipeline_config,
        **kwargs
    )




# Example usage and testing
if __name__ == "__main__":
    import asyncio
    from unittest.mock import Mock
    
    async def test_pipeline():
        """Test the analysis intent classification pipeline"""
        
        # Mock LLM for testing
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time",
            "suggested_functions": ["variance_analysis"],
            "reasoning": "Question specifically asks for rolling variance analysis with time grouping",
            "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
            "clarification_needed": null,
            "can_be_answered": true,
            "feasibility_score": 0.9,
            "missing_columns": [],
            "available_alternatives": [],
            "data_suggestions": null
        }
        '''
        mock_llm.ainvoke = Mock(return_value=mock_response)
        
        # Create pipeline
        pipeline = create_analysis_intent_pipeline(
            llm=mock_llm,
            pipeline_config={"test_mode": True}
        )
        
        # Initialize pipeline
        await pipeline.initialize()
        
        # Test single classification
        result = await pipeline.run(
            question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            dataframe_description="Financial metrics dataset with project performance data",
            dataframe_summary="Contains 10,000 rows with daily metrics from 2023-2024",
            available_columns=["flux", "timestamp", "projects", "cost_centers", "departments"]
        )
        
        print("Single classification result:")
        print(f"Status: {result['status']}")
        print(f"Intent: {result['classification']['intent_type']}")
        print(f"Confidence: {result['classification']['confidence_score']}")
        print(f"Can be answered: {result['classification']['can_be_answered']}")
        
        # Test batch classification
        questions = [
            {
                "question": "What is the variance of my data?",
                "dataframe_description": "Test dataset",
                "available_columns": ["value", "timestamp"]
            },
            {
                "question": "Show me user retention over time",
                "dataframe_description": "User dataset",
                "available_columns": ["user_id", "timestamp"]
            }
        ]
        
        batch_results = await pipeline.batch_classify_intents(questions)
        print(f"\nBatch classification results: {len(batch_results)} processed")
        
        # Test metrics
        metrics = pipeline.get_metrics()
        print(f"\nPipeline metrics:")
        print(f"Total requests: {metrics['total_requests']}")
        print(f"Success rate: {metrics['success_rate']:.2%}")
        print(f"Average processing time: {metrics['average_processing_time']:.2f}s")
        
        # Test configuration
        config = pipeline.get_configuration()
        print(f"\nPipeline configuration:")
        print(f"Name: {config['pipeline_name']}")
        print(f"Version: {config['pipeline_version']}")
        print(f"Initialized: {config['is_initialized']}")
        
        # Cleanup
        await pipeline.cleanup()
        
        return "Pipeline test completed successfully!"
    
    # Run the test
    test_result = asyncio.run(test_pipeline())
    print(f"\nTest result: {test_result}")
