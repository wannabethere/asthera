from typing import Dict, Any, Optional, List, Callable
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
from app.agents.nodes.sql.chart_generation import create_chart_generation_pipeline
from app.agents.nodes.sql.plotly_chart_generation import create_plotly_chart_generation_pipeline
from app.agents.nodes.sql.powerbi_chart_generation import create_powerbi_chart_generation_pipeline
from datetime import datetime

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
                    dry_run=False,
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
        llm: Any,
        engine: Engine,
        retrieval_helper: RetrievalHelper,
        chart_generation_pipeline: Optional[Any] = None,
        plotly_chart_generation_pipeline: Optional[Any] = None,
        powerbi_chart_generation_pipeline: Optional[Any] = None
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
            "chunk_size": 150,
            "language": "English",
            "batch_size": 1000,
            "enable_chart_generation": True,
            "chart_batch_index": 0,  # Which batch to use for chart generation (0 = first batch)
            "chart_language": "English",
            "chart_format": "vega_lite",  # Default chart format: vega_lite, plotly, powerbi
            "include_other_formats": False,  # Whether to include other format conversions
            "use_multi_format": True  # Whether to use multi-format chart generation
        }
        self._engine = engine
        self._metrics = {}
        self._llm = llm
        # Debug LLM type
        print(f"LLM type in DataSummarizationPipeline: {type(llm)}")
        print(f"LLM value: {llm}")
        
        self._summarizer = RecursiveDataSummarizer(
            chunk_size=self._configuration["chunk_size"],
            language=self._configuration["language"],
            llm=llm
        )
        
        # Initialize chart generation pipelines from input parameters
        self._chart_generator = chart_generation_pipeline or create_chart_generation_pipeline()
        self._plotly_chart_generator = plotly_chart_generation_pipeline or create_plotly_chart_generation_pipeline(self._llm)
        self._powerbi_chart_generator = powerbi_chart_generation_pipeline or create_powerbi_chart_generation_pipeline(self._llm)
        
        self._batch_summaries = {}  # In-memory cache for batch summaries
        self._batch_data = {}  # In-memory cache for batch data for chart generation
        self._initialized = True  # Set the initialized flag

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

    def set_chart_generation_batch(self, batch_index: int) -> None:
        """Set which batch to use for chart generation"""
        self._configuration["chart_batch_index"] = max(0, batch_index)
        logger.info(f"Chart generation batch set to: {self._configuration['chart_batch_index']}")

    def enable_chart_generation(self, enabled: bool = True) -> None:
        """Enable or disable chart generation"""
        self._configuration["enable_chart_generation"] = enabled
        logger.info(f"Chart generation {'enabled' if enabled else 'disabled'}")

    def set_chart_format(self, format: str) -> None:
        """Set the chart format (vega_lite, plotly, powerbi)"""
        supported_formats = ["vega_lite", "plotly", "powerbi"]
        if format not in supported_formats:
            raise ValueError(f"Unsupported format: {format}. Supported formats: {supported_formats}")
        self._configuration["chart_format"] = format
        logger.info(f"Chart format set to: {format}")

    def set_include_other_formats(self, include: bool = True) -> None:
        """Set whether to include other format conversions"""
        self._configuration["include_other_formats"] = include
        logger.info(f"Include other formats: {include}")

    def set_use_multi_format(self, use_multi: bool = True) -> None:
        """Set whether to use multi-format chart generation"""
        self._configuration["use_multi_format"] = use_multi
        logger.info(f"Use multi-format chart generation: {use_multi}")

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        self._metrics.clear()
        self._batch_summaries.clear()  # Clear batch summaries cache
        self._batch_data.clear()  # Clear batch data cache

    def _prepare_data_for_chart(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Convert DataFrame to the format expected by chart generator"""
        try:
            # Convert DataFrame to list of lists format
            data = df.values.tolist()
            columns = df.columns.tolist()
            
            return {
                "columns": columns,
                "data": data
            }
        except Exception as e:
            logger.error(f"Error preparing data for chart: {str(e)}")
            return {"columns": [], "data": []}

    async def _generate_chart_for_batch(
        self,
        batch_df: pd.DataFrame,
        query: str,
        sql: str,
        data_description: str,
        language: str = "English"
    ) -> Dict[str, Any]:
        """Generate chart for a specific batch of data"""
        try:
            # Prepare data for chart generation
            chart_data = self._prepare_data_for_chart(batch_df)
            
            if not chart_data["data"] or not chart_data["columns"]:
                logger.warning("No data available for chart generation")
                return {"success": False, "error": "No data available"}
            
            # Get chart format configuration
            chart_format = self._configuration.get("chart_format", "vega_lite")
            include_other_formats = self._configuration.get("include_other_formats", False)
            use_multi_format = self._configuration.get("use_multi_format", True)
            #chart_format = "vega_lite"
            # Generate chart using appropriate generator
            if use_multi_format:
                # Use existing chart generation pipelines
                chart_result = None
                
                if chart_format == "vega_lite":
                    # Use the chart generation pipeline passed to constructor
                    try:
                        # Use the chart generator directly
                        chart_result = await self._chart_generator.run(
                            query=query,
                            sql=sql,
                            data=chart_data,
                            language=language,
                            remove_data_from_chart_schema=True
                        )
                        
                        # Extract the chart data from the pipeline result
                        if chart_result.get("results"):
                            chart_result = {
                                "success": True,
                                "chart_data": {
                                    "chart_schema": chart_result.get("results", {}).get("chart_schema", {}),
                                    "chart_type": chart_result.get("results", {}).get("chart_type", ""),
                                    "reasoning": chart_result.get("results", {}).get("reasoning", ""),
                                    "format": "vega_lite"
                                },
                                "data_sample": chart_data
                            }
                        else:
                            chart_result = {
                                "success": False,
                                "error": "Failed to generate chart"
                            }
                            
                    except Exception as e:
                        logger.error(f"Error using chart generation pipeline: {e}")
                        chart_result = {
                            "success": False,
                            "error": f"Chart generation failed: {str(e)}"
                        }
                
                elif chart_format == "plotly":
                    # Use Plotly chart generation pipeline
                    chart_result = await self._plotly_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=chart_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if chart_result.get("success", False):
                        chart_result = {
                            "success": True,
                            "chart_data": {
                                "chart_schema": chart_result.get("chart_config", {}),
                                "chart_type": chart_result.get("chart_type", ""),
                                "reasoning": chart_result.get("reasoning", ""),
                                "format": "plotly"
                            },
                            "data_sample": chart_data
                        }
                    else:
                        chart_result = {
                            "success": False,
                            "error": chart_result.get("error", "Unknown chart generation error")
                        }
                
                elif chart_format == "powerbi":
                    # Use PowerBI chart generation pipeline
                    chart_result = await self._powerbi_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=chart_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if chart_result.get("success", False):
                        chart_result = {
                            "success": True,
                            "chart_data": {
                                "chart_schema": chart_result.get("chart_config", {}),
                                "chart_type": chart_result.get("chart_type", ""),
                                "reasoning": chart_result.get("reasoning", ""),
                                "format": "powerbi"
                            },
                            "data_sample": chart_data
                        }
                    else:
                        chart_result = {
                            "success": False,
                            "error": chart_result.get("error", "Unknown chart generation error")
                        }
                
                # Add other format conversions if requested
                if include_other_formats and chart_result.get("success", False):
                    # Add query and SQL info to chart_result for format conversion
                    chart_result["query"] = query
                    chart_result["sql"] = sql
                    chart_result["language"] = language
                    await self._add_format_conversions(chart_result, chart_data)
                
                return chart_result
                
            else:
                # Use original chart generator (Vega-Lite only)
                chart_result = await self._chart_generator.run(
                    query=query,
                    sql=sql,
                    data=chart_data,
                    language=language,
                    remove_data_from_chart_schema=True
                )
                
                return {
                    "success": True,
                    "chart_data": chart_result.get("results", {}),
                    "data_sample": chart_data
                }
            
        except Exception as e:
            logger.error(f"Error generating chart: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _add_format_conversions(self, chart_result: Dict[str, Any], chart_data: Dict[str, Any]) -> None:
        """Add conversions to other formats using existing pipelines"""
        try:
            if not chart_result.get("success", False):
                return
            
            chart_data_obj = chart_result.get("chart_data", {})
            current_format = chart_data_obj.get("format", "vega_lite")
            
            # Generate other formats if not already present
            if current_format == "vega_lite":
                # Generate Plotly version
                try:
                    plotly_result = await self._plotly_chart_generator.run(
                        query=chart_result.get("query", ""),
                        sql=chart_result.get("sql", ""),
                        data=chart_data,
                        language=chart_result.get("language", "English"),
                        remove_data_from_chart_config=True
                    )
                    
                    if plotly_result.get("success", False):
                        chart_data_obj["plotly_schema"] = plotly_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Plotly conversion: {e}")
                
                # Generate PowerBI version
                try:
                    powerbi_result = await self._powerbi_chart_generator.run(
                        query=chart_result.get("query", ""),
                        sql=chart_result.get("sql", ""),
                        data=chart_data,
                        language=chart_result.get("language", "English"),
                        remove_data_from_chart_config=True
                    )
                    
                    if powerbi_result.get("success", False):
                        chart_data_obj["powerbi_schema"] = powerbi_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate PowerBI conversion: {e}")
            
            elif current_format == "plotly":
                # Generate Vega-Lite version
                try:
                    vega_result = await self._chart_generator.run(
                        query=chart_result.get("query", ""),
                        sql=chart_result.get("sql", ""),
                        data=chart_data,
                        language=chart_result.get("language", "English"),
                        remove_data_from_chart_schema=True
                    )
                    
                    if vega_result.get("results"):
                        chart_data_obj["vega_lite_schema"] = vega_result.get("results", {}).get("chart_schema", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Vega-Lite conversion: {e}")
                
                # Generate PowerBI version
                try:
                    powerbi_result = await self._powerbi_chart_generator.run(
                        query=chart_result.get("query", ""),
                        sql=chart_result.get("sql", ""),
                        data=chart_data,
                        language=chart_result.get("language", "English"),
                        remove_data_from_chart_config=True
                    )
                    
                    if powerbi_result.get("success", False):
                        chart_data_obj["powerbi_schema"] = powerbi_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate PowerBI conversion: {e}")
            
            elif current_format == "powerbi":
                # Generate Vega-Lite version
                try:
                    vega_result = await self._chart_generator.run(
                        query=chart_result.get("query", ""),
                        sql=chart_result.get("sql", ""),
                        data=chart_data,
                        language=chart_result.get("language", "English"),
                        remove_data_from_chart_schema=True
                    )
                    
                    if vega_result.get("results"):
                        chart_data_obj["vega_lite_schema"] = vega_result.get("results", {}).get("chart_schema", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Vega-Lite conversion: {e}")
                
                # Generate Plotly version
                try:
                    plotly_result = await self._plotly_chart_generator.run(
                        query=chart_result.get("query", ""),
                        sql=chart_result.get("sql", ""),
                        data=chart_data,
                        language=chart_result.get("language", "English"),
                        remove_data_from_chart_config=True
                    )
                    
                    if plotly_result.get("success", False):
                        chart_data_obj["plotly_schema"] = plotly_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Plotly conversion: {e}")
            
        except Exception as e:
            logger.error(f"Error adding format conversions: {e}")

    async def run(
        self,
        query: str,
        sql: str,
        data_description: str,
        project_id: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        try:
            # Update configuration if provided
            if configuration:
                self.update_configuration(configuration)

            # Define progress callback
            def progress_callback(message: str):
                logger.info(f"Summarization progress: {message}")

            # Define local status update function
            def send_status_update(status: str, details: Dict[str, Any] = None):
                """Send status update via callback if available"""
                if status_callback:
                    try:
                        status_callback(status, details or {})
                    except Exception as e:
                        logger.error(f"Error in status callback: {str(e)}")
                logger.info(f"Status Update - {status}: {details}")

            # Clear previous batch summaries and data
            self._batch_summaries.clear()
            self._batch_data.clear()
            
            async with aiohttp.ClientSession() as session:
                # First get total count to determine number of batches
                count_sql = f"SELECT COUNT(*) as total_count FROM ({sql}) as count_query"
                success, count_result = await self._engine.execute_sql(
                    count_sql,
                    session,
                    dry_run=False,
                    **kwargs
                )
                print(f"Count result in data summarization pipeline: {count_result}")
                if not success or not count_result.get("data"):
                    raise Exception("Failed to get total count for batch processing")

                total_count = int(count_result["data"][0]["total_count"])
                batch_size = int(self._configuration["batch_size"]) or 2000
                total_batches = (total_count + batch_size - 1) // batch_size
                print(f"Total batches: {total_batches}")
                
                # Send status update for data fetch completion
                send_status_update("fetch_data_complete", {
                    "total_count": total_count,
                    "total_batches": total_batches,
                    "batch_size": batch_size,
                    "project_id": project_id
                })
                
                # Process all batches
                for current_batch in range(total_batches):
                    # Execute SQL using engine with batch processing
                    
                    success, result = await self._engine.execute_sql_in_batches(
                        sql=sql,
                        session=session,
                        batch_size=batch_size,
                        batch_num=current_batch,
                        dry_run=False,
                        **kwargs
                    )
                    
                    if not success:
                        raise Exception(f"Failed to execute batch {current_batch + 1}: {result.get('error', 'Unknown error')}")

                    # Get batch info from result
                    batch_info = result.get("batch_info", {})
                    is_last_batch = batch_info.get("is_last_batch", False)

                    # Process current batch
                    if result.get("data"):
                        batch_df = pd.DataFrame(result["data"])
                        
                        # Send status update for summarization begin
                        send_status_update("summarization_begin", {
                            "batch_number": current_batch + 1,
                            "total_batches": total_batches,
                            "batch_size": len(batch_df),
                            "project_id": project_id
                        })
                        
                        # Ensure data_description is a string
                        data_description_str = str(data_description) if data_description is not None else "Unknown data"
                        batch_summary = self._summarizer._recursive_summarize(
                            data=batch_df,
                            data_description=f"{data_description_str} (Batch {current_batch + 1}/{total_batches})",
                            progress_callback=progress_callback
                        )
                        print("batch_summary for data summarization pipeline", batch_summary)
                        # Cache batch summary
                        self._batch_summaries[current_batch] = batch_summary

                        # Cache batch data for chart generation
                        self._batch_data[current_batch] = batch_df

                        # Send status update for summarization complete
                        send_status_update("summarization_complete", {
                            "batch_number": current_batch + 1,
                            "total_batches": total_batches,
                            "batch_size": len(batch_df),
                            "project_id": project_id,
                            "is_last_batch": is_last_batch
                        })

                        # Log progress
                        logger.info(f"Processed batch {current_batch + 1}/{total_batches}")

                        # If this is the last batch, combine all summaries
                        if is_last_batch or current_batch == total_batches - 1:
                            # Get all batch summaries in order
                            batch_summaries = [self._batch_summaries[i] for i in range(total_batches)]
                            print(f"Batch summaries: {batch_summaries} {total_batches} {data_description}")
                            
                            # Extract just the summary text for combining
                            summary_texts = []
                            total_tokens = 0
                            total_cost = 0.0
                            total_rows = 0
                            
                            for summary in batch_summaries:
                                if isinstance(summary, str):
                                    summary_texts.append(summary)
                                    # For string summaries, we can't extract metadata, so use defaults
                                    total_tokens += 0
                                    total_cost += 0.0
                                    total_rows += 0
                                elif isinstance(summary, dict):
                                    summary_texts.append(summary.get("executive_summary", str(summary)))
                                    total_tokens += summary.get("metadata", {}).get("total_tokens", 0)
                                    total_cost += summary.get("metadata", {}).get("estimated_cost", 0.0)
                                    total_rows += len(summary.get("data", []))
                                else:
                                    summary_texts.append(str(summary))
                            
                            # Combine all batch summaries
                            combined_summary = self._summarizer._combine_summaries(
                                summary_texts,
                                data_description,
                                is_final=True
                            )
                            print(f"Combined summary: {combined_summary}")

                            # Generate chart if enabled
                            chart_result = None
                            if self._configuration.get("enable_chart_generation", True):
                                try:
                                    # Send status update for chart generation begin
                                    send_status_update("chart_generation_begin", {
                                        "project_id": project_id,
                                        "chart_format": self._configuration.get("chart_format", "vega_lite"),
                                        "total_batches": total_batches
                                    })
                                    
                                    # Get the batch to use for chart generation
                                    chart_batch_df = batch_df
                                    
                                    if chart_batch_df is not None:
                                        chart_language = self._configuration.get("chart_language", "English")
                                        chart_result = await self._generate_chart_for_batch(
                                            batch_df=chart_batch_df,
                                            query=query,
                                            sql=sql,
                                            data_description=data_description_str,
                                            language=chart_language
                                        )
                                        
                                        # Send status update for chart generation complete
                                        send_status_update("chart_generation_complete", {
                                            "project_id": project_id,
                                            "success": chart_result.get("success", False),
                                            "chart_format": self._configuration.get("chart_format", "vega_lite"),
                                            "error": chart_result.get("error") if not chart_result.get("success") else None
                                        })
                                        
                                        logger.info(f"Chart generation completed for batch")
                                    else:
                                        logger.warning(f"Could not retrieve data for chart generation batch ")
                                        
                                except Exception as e:
                                    logger.error(f"Error generating chart: {str(e)}")
                                    chart_result = {"success": False, "error": str(e)}
                                    
                                    # Send status update for chart generation error
                                    send_status_update("chart_generation_error", {
                                        "project_id": project_id,
                                        "error": str(e),
                                        "chart_format": self._configuration.get("chart_format", "vega_lite")
                                    })

                            # Prepare final result
                            final_result = {
                                "executive_summary": combined_summary,
                                "data_overview": {
                                    "total_rows": total_rows,
                                    "total_batches": total_batches,
                                    "batches_processed": len(batch_summaries)
                                },
                                "metadata": {
                                    "total_tokens": total_tokens,
                                    "estimated_cost": total_cost,
                                    "timestamp": datetime.now().isoformat()
                                }
                            }

                            # Add chart data to final result if available
                            if chart_result and chart_result.get("success"):
                                chart_data = chart_result.get("chart_data", {})
                                visualization = {
                                    "chart_schema": chart_data.get("chart_schema", {}),
                                    "chart_type": chart_data.get("chart_type", ""),
                                    "reasoning": chart_data.get("reasoning", ""),
                                    "data_sample": chart_result.get("data_sample", {}),
                                    "batch_used": self._configuration.get("chart_batch_index", 0),
                                    "format": chart_data.get("format", self._configuration.get("chart_format", "vega_lite"))
                                }
                                
                            
                                # Add other format schemas if available
                                if "plotly_schema" in chart_data:
                                    visualization["plotly_schema"] = chart_data["plotly_schema"]
                                if "powerbi_schema" in chart_data:
                                    visualization["powerbi_schema"] = chart_data["powerbi_schema"]
                                
                                final_result["visualization"] = visualization
                            elif chart_result:
                                final_result["visualization"] = {
                                    "error": chart_result.get("error", "Unknown chart generation error"),
                                    "batch_used": self._configuration.get("chart_batch_index", 0),
                                    "format": self._configuration.get("chart_format", "vega_lite")
                                }

                            # Update metrics
                            self._metrics.update({
                                "last_project_id": project_id,
                                "rows_processed": total_rows,
                                "success": True,
                                "total_tokens": total_tokens,
                                "estimated_cost": total_cost,
                                "batches_processed": len(batch_summaries),
                                "chart_generated": chart_result.get("success", False) if chart_result else False
                            })
                            post_process_result = {
                                "post_process": {
                                    "executive_summary": final_result["executive_summary"],
                                    "data_overview": final_result["data_overview"],
                                    "visualization": final_result.get("visualization", {})
                                },
                                "metadata": {
                                    "project_id": project_id,
                                    "data_description": data_description_str,
                                    "processing_stats": final_result["metadata"]
                                }
                            }
                            print("final_result for data summarization pipeline", post_process_result)
                            return post_process_result
                        else:
                            continue
                            
                

        except Exception as e:
            logger.error(f"Error in data summarization pipeline: {str(e)}")
            self._metrics.update({"last_error": str(e), "success": False})
            raise


# Example usage of the enhanced DataSummarizationPipeline with chart generation
async def example_data_summarization_with_charts():
    """
    Example demonstrating how to use the DataSummarizationPipeline with multi-format chart generation
    """
    import os
    from app.core.engine import Engine
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    # Setup (you would normally get these from your application context)
    llm = get_llm()
    engine = Engine()  # Your database engine
    retrieval_helper = RetrievalHelper()  # Your retrieval helper
    
    # Create chart generation pipelines (to avoid circular dependency)
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Create the pipeline with chart generation pipelines passed as parameters
    pipeline = DataSummarizationPipeline(
        name="Enhanced Data Summarization",
        version="1.0",
        description="Data summarization with multi-format chart generation",
        llm=llm,
        engine=engine,
        retrieval_helper=retrieval_helper,
        chart_generation_pipeline=chart_generation_pipeline,
        plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
        powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
    )
    
    # Configure chart generation
    pipeline.enable_chart_generation(True)
    pipeline.set_chart_generation_batch(0)  # Use first batch for chart generation
    pipeline.set_chart_format("vega_lite")  # Set chart format
    pipeline.set_include_other_formats(True)  # Include other format conversions
    pipeline.set_use_multi_format(True)  # Use multi-format chart generation
    
    # Example configuration
    configuration = {
        "batch_size": 500,  # Smaller batches for better chart generation
        "chunk_size": 100,
        "language": "English",
        "chart_language": "English",
        "chart_format": "vega_lite",
        "include_other_formats": True,
        "use_multi_format": True
    }
    
    # Example usage
    try:
        result = await pipeline.run(
            query="Analyze sales performance trends",
            sql="SELECT date, region, sales_amount, product_category FROM sales_data ORDER BY date",
            data_description="Sales performance data across regions and product categories",
            project_id="example_project_123",
            configuration=configuration
        )
        
        print("=== Data Summarization with Multi-Format Charts Result ===")
        print(f"Executive Summary: {result['post_process']['executive_summary'][:200]}...")
        print(f"Data Overview: {result['post_process']['data_overview']}")
        
        # Check if visualization was generated
        if 'visualization' in result['post_process']:
            viz = result['post_process']['visualization']
            if 'chart_schema' in viz:
                print(f"Chart Type: {viz.get('chart_type', 'Unknown')}")
                print(f"Chart Format: {viz.get('format', 'Unknown')}")
                print(f"Chart Schema: {viz.get('chart_schema', {})}")
                print(f"Chart Reasoning: {viz.get('reasoning', '')[:100]}...")
                print(f"Batch Used: {viz.get('batch_used', 'Unknown')}")
                
                # Check for other format schemas
                if 'plotly_schema' in viz:
                    print(f"Plotly Schema Available: {list(viz['plotly_schema'].keys())}")
                if 'powerbi_schema' in viz:
                    print(f"PowerBI Schema Available: {list(viz['powerbi_schema'].keys())}")
            else:
                print(f"Chart Generation Error: {viz.get('error', 'Unknown error')}")
        else:
            print("No visualization generated")
        
        # Print metrics
        metrics = pipeline.get_metrics()
        print(f"Processing Metrics: {metrics}")
        
    except Exception as e:
        print(f"Error in example: {str(e)}")


async def example_data_summarization_with_status_callback():
    """
    Example demonstrating how to use the DataSummarizationPipeline with status callback
    """
    import os
    from app.core.engine import Engine
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    # Setup
    llm = get_llm()
    engine = Engine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Define status callback function
    def status_callback(status: str, details: Dict[str, Any]):
        """Example status callback function"""
        print(f"🔄 STATUS UPDATE: {status}")
        print(f"   Details: {details}")
        
        # You can implement different logic based on status
        if status == "fetch_data_complete":
            print(f"   ✅ Data fetch completed - {details.get('total_count', 0)} records, {details.get('total_batches', 0)} batches")
        elif status == "summarization_begin":
            print(f"   📊 Starting summarization for batch {details.get('batch_number', 0)}/{details.get('total_batches', 0)}")
        elif status == "summarization_complete":
            print(f"   ✅ Summarization completed for batch {details.get('batch_number', 0)}")
            if details.get('is_last_batch', False):
                print(f"   🎉 All batches processed!")
        elif status == "chart_generation_begin":
            print(f"   📈 Starting chart generation with format: {details.get('chart_format', 'unknown')}")
        elif status == "chart_generation_complete":
            if details.get('success', False):
                print(f"   ✅ Chart generation completed successfully")
            else:
                print(f"   ❌ Chart generation failed: {details.get('error', 'Unknown error')}")
        elif status == "chart_generation_error":
            print(f"   ❌ Chart generation error: {details.get('error', 'Unknown error')}")
    
    # Create the pipeline (without status callback in constructor)
    pipeline = DataSummarizationPipeline(
        name="Data Summarization with Status Callback",
        version="1.0",
        description="Data summarization with status updates",
        llm=llm,
        engine=engine,
        retrieval_helper=retrieval_helper,
        chart_generation_pipeline=chart_generation_pipeline,
        plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
        powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
    )
    
    # Configure pipeline
    pipeline.enable_chart_generation(True)
    pipeline.set_chart_format("vega_lite")
    
    # Example configuration
    configuration = {
        "batch_size": 100,  # Small batches to see more status updates
        "chunk_size": 50,
        "language": "English",
        "chart_language": "English"
    }
    
    print("🚀 Starting Data Summarization with Status Callback Example")
    print("=" * 60)
    
    try:
        result = await pipeline.run(
            query="Analyze customer purchase patterns",
            sql="SELECT customer_id, purchase_date, amount, product_category FROM customer_purchases ORDER BY purchase_date",
            data_description="Customer purchase data with product categories",
            project_id="status_callback_example",
            configuration=configuration,
            status_callback=status_callback  # Pass callback to run method
        )
        
        print("\n" + "=" * 60)
        print("🎯 FINAL RESULT")
        print("=" * 60)
        print(f"Executive Summary: {result['post_process']['executive_summary'][:200]}...")
        print(f"Data Overview: {result['post_process']['data_overview']}")
        
        if 'visualization' in result['post_process']:
            viz = result['post_process']['visualization']
            if 'chart_schema' in viz:
                print(f"Chart Generated: {viz.get('chart_type', 'Unknown')} ({viz.get('format', 'Unknown')})")
            else:
                print(f"Chart Generation Error: {viz.get('error', 'Unknown error')}")
        
        # Print final metrics
        metrics = pipeline.get_metrics()
        print(f"Final Metrics: {metrics}")
        
    except Exception as e:
        print(f"❌ Error in example: {str(e)}")


async def example_different_chart_formats():
    """
    Example demonstrating different chart formats
    """
    import os
    from app.core.engine import Engine
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    # Setup
    llm = get_llm()
    engine = Engine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Test different formats
    formats = ["vega_lite", "plotly", "powerbi"]
    
    for chart_format in formats:
        print(f"\n=== Testing {chart_format.upper()} Format ===")
        
        # Create pipeline with chart generation pipelines
        pipeline = DataSummarizationPipeline(
            name=f"Data Summarization - {chart_format}",
            version="1.0",
            description=f"Data summarization with {chart_format} chart generation",
            llm=llm,
            engine=engine,
            retrieval_helper=retrieval_helper,
            chart_generation_pipeline=chart_generation_pipeline,
            plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
            powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
        )
        
        # Configure for specific format
        pipeline.enable_chart_generation(True)
        pipeline.set_chart_format(chart_format)
        pipeline.set_include_other_formats(False)  # Don't include other formats for this test
        pipeline.set_use_multi_format(True)
        
        try:
            result = await pipeline.run(
                query="Show sales trends by region",
                sql="SELECT date, region, sales_amount FROM sales_data ORDER BY date",
                data_description="Sales data with regional breakdown",
                project_id=f"test_project_{chart_format}",
                configuration={
                    "batch_size": 100,
                    "chunk_size": 50,
                    "language": "English",
                    "chart_format": chart_format
                }
            )
            
            if 'visualization' in result['post_process']:
                viz = result['post_process']['visualization']
                if 'chart_schema' in viz:
                    print(f"✅ {chart_format.upper()} chart generated successfully")
                    print(f"   Chart Type: {viz.get('chart_type', 'Unknown')}")
                    print(f"   Format: {viz.get('format', 'Unknown')}")
                else:
                    print(f"❌ {chart_format.upper()} chart generation failed: {viz.get('error', 'Unknown error')}")
            else:
                print(f"❌ No {chart_format.upper()} visualization generated")
                
        except Exception as e:
            print(f"❌ Error testing {chart_format}: {str(e)}")


if __name__ == "__main__":
    # Run the examples if this file is executed directly
    import asyncio
    
    async def run_examples():
        print("Running Multi-Format Chart Generation Examples...")
        
        print("\n1. Testing with all formats included:")
        await example_data_summarization_with_charts()
        
        print("\n2. Testing individual formats:")
        await example_different_chart_formats()
        
        print("\n3. Testing with status callback:")
        await example_data_summarization_with_status_callback()
        
        print("\n✅ All examples completed!")
    
    asyncio.run(run_examples())


