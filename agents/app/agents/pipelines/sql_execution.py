from typing import Dict, Any, Optional, List
import logging
import aiohttp
from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from langchain_openai import ChatOpenAI
from app.core.engine import Engine
from app.core.provider import DocumentStoreProvider
from app.agents.nodes.sql.user_guide_assistance import UserGuideAssistance
from app.agents.nodes.sql.question_recommendation import QuestionRecommendation
from app.core.dependencies import get_llm
import pandas as pd
from app.agents.nodes.sql.recursive_summarizer import RecursiveDataSummarizer

logger = logging.getLogger("lexy-ai-service")

class SQLExecutionPipeline(AgentPipeline):
    """Pipeline for executing SQL queries"""
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        dry_run: bool = True
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=get_llm(),
            retrieval_helper=retrieval_helper,
            engine=engine
        )
        self._configuration = {"timeout": 30, "dry_run": True}
        self._engine = engine
        self._metrics = {}

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

    async def run(self, sql: str, project_id: str, configuration: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        try:
            # Get configuration values
            dry_run = configuration.get("dry_run", True) if configuration else self._configuration["dry_run"]
            
            # Create aiohttp session
            async with aiohttp.ClientSession() as session:
                # Execute SQL using engine
                success, result = await self._engine.execute_sql(
                    sql=sql,
                    session=session,
                    dry_run=dry_run,
                    **kwargs
                )
                
                # Update metrics
                self._metrics.update({
                    "last_sql": sql,
                    "last_project_id": project_id,
                    "success": success
                })
                
                return {
                    "post_process": result if result else {},
                    "metadata": {
                        "project_id": project_id,
                        "sql": sql,
                        "dry_run": dry_run
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in SQL execution pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise 


class SQLValidationPipeline(AgentPipeline):
    """Pipeline for validating SQL queries"""
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=get_llm(),
            retrieval_helper=retrieval_helper
        )
        self._configuration = {"validation_mode": "syntax", "timeout": 10}
        self._metrics = {}

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

    async def run(self, sql: str, project_id: str, configuration: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        try:
            # Example: Use retrieval_helper or LLM to validate SQL
            result = await self._retrieval_helper.validate_sql(
                sql=sql,
                project_id=project_id,
                mode=configuration.get("validation_mode", "syntax") if configuration else self._configuration["validation_mode"],
                timeout=configuration.get("timeout", 10) if configuration else self._configuration["timeout"]
            )
            self._metrics.update({"last_sql": sql, "last_project_id": project_id, "success": result.get("is_valid", False)})
            return {"post_process": result, "metadata": {"project_id": project_id, "sql": sql}}
        except Exception as e:
            logger.error(f"Error in SQL validation pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise 

class UserGuideAssistancePipeline(AgentPipeline):
    """Pipeline for providing user guide assistance"""
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: DocumentStoreProvider
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=get_llm(),
            retrieval_helper=retrieval_helper
        )
        self._configuration = {
            "max_cache_size": 1_000_000,
            "cache_ttl": 120,
            "language": "English"
        }
        self._metrics = {}
        self._user_guide_assistance = UserGuideAssistance(
            doc_store_provider=document_store_provider,
            maxsize=self._configuration["max_cache_size"],
            ttl=self._configuration["cache_ttl"]
        )

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
        query: str,
        docs: List[Dict[str, str]],
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        try:
            # Get configuration values
            language = configuration.get("language", self._configuration["language"]) if configuration else self._configuration["language"]
            
            # Create input for user guide assistance
            input_data = UserGuideAssistance.Input(
                id=project_id,
                query=query,
                language=language,
                docs=docs,
                project_id=project_id,
                configuration=configuration
            )
            
            # Generate assistance
            response_chunks = []
            async for chunk in self._user_guide_assistance.assist(input_data, **kwargs):
                response_chunks.append(chunk)
            
            response = "".join(response_chunks)
            
            # Update metrics
            self._metrics.update({
                "last_query": query,
                "last_project_id": project_id,
                "success": True
            })
            
            return {
                "post_process": {"response": response},
                "metadata": {
                    "project_id": project_id,
                    "query": query,
                    "language": language
                }
            }
            
        except Exception as e:
            logger.error(f"Error in user guide assistance pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise 

class QuestionRecommendationPipeline(AgentPipeline):
    """Pipeline for generating question recommendations"""
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        document_store_provider: DocumentStoreProvider
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=get_llm(),
            retrieval_helper=retrieval_helper
        )
        self._configuration = {
            "max_questions": 5,
            "max_categories": 3,
            "language": "en"
        }
        self._metrics = {}
        self._question_recommendation = QuestionRecommendation(
            doc_store_provider=document_store_provider
        )
        self._initialized = True  # Set the initialized flag

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
        user_question: str,
        mdl: dict,
        project_id: Optional[str] = None,
        previous_questions: List[str] = [],
        categories: List[str] = [],
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        try:
            # Merge default configuration with provided configuration
            merged_config = {
                "max_questions": self._configuration["max_questions"],
                "max_categories": self._configuration["max_categories"],
                "language": self._configuration["language"]
            }
            if configuration:
                merged_config.update(configuration)
            
            # Generate question recommendations
            result = await self._question_recommendation.run(
                user_question=user_question,
                mdl=mdl,
                previous_questions=previous_questions,
                categories=categories,
                project_id=project_id,
                configuration=merged_config,
                **kwargs
            )
            print("result in question recommendation pipeline run:  ", result)
            # Update metrics
            self._metrics.update({
                "last_user_question": user_question,
                "last_project_id": project_id,
                "success": result.get("status") == "success"
            })
            
            return {
                "post_process": result.get("response", {}),
                "metadata": {
                    "project_id": project_id,
                    "user_question": user_question,
                    "max_questions": merged_config["max_questions"],
                    "max_categories": merged_config["max_categories"]
                }
            }
            
        except Exception as e:
            logger.error(f"Error in question recommendation pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise

class DataSummarizationPipeline(AgentPipeline):
    """Pipeline for generating data summaries using recursive summarization"""
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        engine: Engine,
        retrieval_helper: RetrievalHelper
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=get_llm(),
            retrieval_helper=retrieval_helper,
            engine=engine
        )
        self._configuration = {
            "chunk_size": 150,
            "language": "English"
        }
        self._engine = engine
        self._metrics = {}
        self._summarizer = RecursiveDataSummarizer(
            chunk_size=self._configuration["chunk_size"],
            language=self._configuration["language"],
            llm=get_llm()
        )

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def get_configuration(self) -> Dict[str, Any]:
        return self._configuration.copy()

    def update_configuration(self, config: Dict[str, Any]) -> None:
        self._configuration.update(config)
        # Update summarizer configuration if needed
        if "chunk_size" in config:
            self._summarizer = RecursiveDataSummarizer(
                chunk_size=config["chunk_size"],
                language=self._configuration["language"] or "English",
                llm=get_llm()
            )

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        self._metrics.clear()

    async def run(
        self,
        query: str,
        sql: str,
        data_description: str,
        project_id: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        try:
            # Update configuration if provided
            if configuration:
                self.update_configuration(configuration)

            # Define progress callback
            async def progress_callback(message: str):
                logger.info(f"Summarization progress: {message}")

           
            # Generate summary
            result = self._summarizer.summarize_dataframe(
                df=df,
                data_description=data_description,
                progress_callback=progress_callback
            )

            # Update metrics
            self._metrics.update({
                "last_project_id": project_id,
                "rows_processed": len(df),
                "success": True,
                "total_tokens": result["metadata"]["total_tokens"],
                "estimated_cost": result["metadata"]["estimated_cost"]
            })

            return {
                "post_process": {
                    "executive_summary": result["executive_summary"],
                    "data_overview": result["data_overview"]
                },
                "metadata": {
                    "project_id": project_id,
                    "data_description": data_description,
                    "processing_stats": result["metadata"]
                }
            }

        except Exception as e:
            logger.error(f"Error in data summarization pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise


