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
from app.agents.nodes.sql.chart_generation import create_chart_generation_pipeline,create_vega_lite_chart_generation_pipeline
from app.agents.nodes.sql.enhanced_chart_generation import create_enhanced_vega_lite_chart_generation_pipeline
from app.agents.nodes.sql.plotly_chart_generation import create_plotly_chart_generation_pipeline
from app.agents.nodes.sql.powerbi_chart_generation import create_powerbi_chart_generation_pipeline
from app.agents.nodes.sql.utils.chart import ChartExecutor, ChartExecutionConfig, execute_chart_with_sql
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
            
            # Extract pagination parameters from configuration
            page = configuration.get("page") if configuration else None
            page_size = configuration.get("page_size") if configuration else None
            enable_pagination = configuration.get("enable_pagination", False) if configuration else False
            
            # Create aiohttp session
            async with aiohttp.ClientSession() as session:
                # Execute SQL using engine with pagination if enabled
                if enable_pagination and page is not None and page_size is not None:
                    # Use batch execution for pagination
                    success, result = await self._engine.execute_sql_in_batches(
                        sql=sql,
                        session=session,
                        batch_size=page_size,
                        batch_num=page - 1,  # Convert to 0-based index
                        dry_run=False,
                        **kwargs
                    )
                else:
                    # Use regular execution
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
                    "success": success,
                    "pagination_used": enable_pagination and page is not None and page_size is not None
                })
                
                # Prepare response with pagination metadata if used
                response = {
                    "post_process": result if result else {},
                    "metadata": {
                        "project_id": project_id,
                        "sql": sql,
                        "dry_run": dry_run
                    }
                }
                
                # Add pagination info to response if pagination was used
                if enable_pagination and page is not None and page_size is not None and result:
                    if "batch_info" in result:
                        # Add pagination metadata from batch execution
                        response["post_process"]["pagination"] = {
                            "page": page,
                            "page_size": page_size,
                            "total_records": result["batch_info"].get("total_count", 0),
                            "total_pages": result["batch_info"].get("total_batches", 0),
                            "has_next": not result["batch_info"].get("is_last_batch", True),
                            "has_previous": page > 1
                        }
                    else:
                        # Add basic pagination info if not provided by engine
                        total_records = len(result.get("data", [])) if result else 0
                        response["post_process"]["pagination"] = {
                            "page": page,
                            "page_size": page_size,
                            "total_records": total_records,
                            "total_pages": (total_records + page_size - 1) // page_size if total_records > 0 else 0,
                            "has_next": page * page_size < total_records,
                            "has_previous": page > 1
                        }
                
                return response
                
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
            "use_multi_format": True,  # Whether to use multi-format chart generation
            # Chart execution configuration
            "page_size": 1000,
            "max_rows": 10000,
            "enable_pagination": True,
            "sort_by": None,
            "sort_order": "ASC",
            "timeout_seconds": 30,
            "cache_results": True,
            "cache_ttl_seconds": 300
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
        self._chart_generator = chart_generation_pipeline or create_enhanced_vega_lite_chart_generation_pipeline()
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

    def set_chart_execution_config(self, config: ChartExecutionConfig) -> None:
        """Set the chart execution configuration"""
        self._configuration.update({
            "page_size": config.page_size,
            "max_rows": config.max_rows,
            "enable_pagination": config.enable_pagination,
            "sort_by": config.sort_by,
            "sort_order": config.sort_order,
            "timeout_seconds": config.timeout_seconds,
            "cache_results": config.cache_results,
            "cache_ttl_seconds": config.cache_ttl_seconds
        })
        logger.info("Chart execution configuration updated")

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        self._metrics.clear()
        self._batch_summaries.clear()  # Clear batch summaries cache
        self._batch_data.clear()  # Clear batch data cache

    def _prepare_data_for_chart(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Convert DataFrame to the format expected by chart generator"""
        try:
            # Convert DataFrame to list of dictionaries format (not list of lists)
            # This is what the chart generation pipeline expects
            data = df.to_dict(orient='records')
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
            
            # Generate chart using appropriate generator
            if use_multi_format:
                # Use existing chart generation pipelines
                chart_result = None
                
                if chart_format == "vega_lite":
                    # Use the chart generation pipeline passed to constructor
                    try:
                        # Use the chart generator directly
                        pipeline_result = await self._chart_generator.run(
                            query=query,
                            sql=sql,
                            data=chart_data,
                            language=language,
                            remove_data_from_chart_schema=True
                        )
                        print("chart_result in data summarization pipeline in generate_chart_for_batch", pipeline_result)
                        
                        # Check if the pipeline result contains the expected structure
                        if pipeline_result.get("results") and pipeline_result["results"].get("chart_schema"):
                            chart_schema = pipeline_result["results"]["chart_schema"]
                            chart_type = pipeline_result["results"].get("chart_type", "")
                            reasoning = pipeline_result["results"].get("reasoning", "")
                        elif pipeline_result.get("chart_schema") and pipeline_result.get("success", False):
                            # If the pipeline result has chart_schema directly in root (like your output)
                            chart_schema = pipeline_result["chart_schema"]
                            chart_type = pipeline_result.get("chart_type", "")
                            reasoning = pipeline_result.get("reasoning", "")
                        else:
                            # Log the actual structure for debugging
                            logger.warning(f"Unexpected chart pipeline result structure: {pipeline_result}")
                            chart_result = {
                                "success": False,
                                "error": f"Failed to generate chart - unexpected result structure. Keys: {list(pipeline_result.keys()) if isinstance(pipeline_result, dict) else 'not a dict'}"
                            }
                            return chart_result
                        
                        # Execute the chart with actual data using ChartExecutor
                        try:
                            # Create ChartExecutor instance
                            chart_executor = ChartExecutor(db_engine=self._engine)
                            
                            # Create execution configuration
                            exec_config = ChartExecutionConfig(
                                page_size=self._configuration.get("page_size", 1000),
                                max_rows=self._configuration.get("max_rows", 10000),
                                enable_pagination=self._configuration.get("enable_pagination", True),
                                sort_by=self._configuration.get("sort_by"),
                                sort_order=self._configuration.get("sort_order", "ASC"),
                                timeout_seconds=self._configuration.get("timeout_seconds", 30),
                                cache_results=self._configuration.get("cache_results", True),
                                cache_ttl_seconds=self._configuration.get("cache_ttl_seconds", 300)
                            )
                            
                            # Execute the chart with the actual SQL data
                            execution_result = await chart_executor.execute_chart(
                                chart_schema=chart_schema,
                                sql_query=sql,
                                config=exec_config,
                                db_engine=self._engine
                            )
                            
                            if execution_result.get("success", False):
                                # Chart execution successful
                                executed_schema = execution_result.get("chart_schema", {})
                                data_count = execution_result.get("data_count", 0)
                                validation = execution_result.get("validation", {})
                                
                                chart_result = {
                                    "success": True,
                                    "chart_data": {
                                        "chart_schema": executed_schema,
                                        "chart_type": chart_type,
                                        "reasoning": reasoning,
                                        "format": "vega_lite",
                                        "data_count": data_count,
                                        "validation": validation
                                    },
                                    "data_sample": chart_data,
                                    "execution_info": {
                                        "data_count": data_count,
                                        "validation_success": validation.get("valid", False),
                                        "execution_config": execution_result.get("execution_config", {})
                                    }
                                }
                            else:
                                # Chart execution failed, but we still have the generated schema
                                logger.warning(f"Chart execution failed: {execution_result.get('error', 'Unknown error')}")
                                chart_result = {
                                    "success": True,  # Chart generation was successful
                                    "chart_data": {
                                        "chart_schema": chart_schema,
                                        "chart_type": chart_type,
                                        "reasoning": reasoning,
                                        "format": "vega_lite"
                                    },
                                    "data_sample": chart_data,
                                    "execution_error": execution_result.get("error", "Unknown execution error")
                                }
                                
                        except Exception as exec_error:
                            logger.error(f"Error executing chart: {str(exec_error)}")
                            # Chart execution failed, but we still have the generated schema
                            chart_result = {
                                "success": True,  # Chart generation was successful
                                "chart_data": {
                                    "chart_schema": chart_schema,
                                    "chart_type": chart_type,
                                    "reasoning": reasoning,
                                    "format": "vega_lite"
                                },
                                "data_sample": chart_data,
                                "execution_error": str(exec_error)
                            }
                        
                    except Exception as e:
                        logger.error(f"Error using chart generation pipeline: {e}")
                        chart_result = {
                            "success": False,
                            "error": f"Chart generation failed: {str(e)}"
                        }
                
                elif chart_format == "plotly":
                    # Use Plotly chart generation pipeline
                    pipeline_result = await self._plotly_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=chart_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if pipeline_result.get("success", False):
                        chart_result = {
                            "success": True,
                            "chart_data": {
                                "chart_schema": pipeline_result.get("chart_config", {}),
                                "chart_type": pipeline_result.get("chart_type", ""),
                                "reasoning": pipeline_result.get("reasoning", ""),
                                "format": "plotly"
                            },
                            "data_sample": chart_data
                        }
                    else:
                        chart_result = {
                            "success": False,
                            "error": pipeline_result.get("error", "Unknown chart generation error")
                        }
                
                elif chart_format == "powerbi":
                    # Use PowerBI chart generation pipeline
                    pipeline_result = await self._powerbi_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=chart_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if pipeline_result.get("success", False):
                        chart_result = {
                            "success": True,
                            "chart_data": {
                                "chart_schema": pipeline_result.get("chart_config", {}),
                                "chart_type": pipeline_result.get("chart_type", ""),
                                "reasoning": pipeline_result.get("reasoning", ""),
                                "format": "powerbi"
                            },
                            "data_sample": chart_data
                        }
                    else:
                        chart_result = {
                            "success": False,
                            "error": pipeline_result.get("error", "Unknown chart generation error")
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
                pipeline_result = await self._chart_generator.run(
                    query=query,
                    sql=sql,
                    data=chart_data,
                    language=language,
                    remove_data_from_chart_schema=True
                )
                
                return {
                    "success": True,
                    "chart_data": pipeline_result.get("results", {}),
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
                                        
                                        # Add debug logging to understand the chart_result structure
                                        logger.info(f"Chart generation result structure: {chart_result}")
                                        logger.info(f"Chart generation success status: {chart_result.get('success', False)}")
                                        logger.info(f"Chart generation success check: {chart_result.get('success')}")
                                        logger.info(f"Chart generation error: {chart_result.get('error')}")
                                        
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
                                
                                # Add execution information if available (for Vega-Lite charts)
                                if chart_data.get("data_count") is not None:
                                    visualization["data_count"] = chart_data.get("data_count")
                                if chart_result.get("execution_info"):
                                    visualization["execution_info"] = chart_result.get("execution_info")
                                if chart_result.get("execution_error"):
                                    visualization["execution_error"] = chart_result.get("execution_error")
                                if chart_result.get("warning"):
                                    visualization["warning"] = chart_result.get("warning")
                            
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





class ChartExecutionPipeline(AgentPipeline):
    """Pipeline for executing charts with SQL data using ChartExecutor"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        chart_generation_pipeline=None,
        plotly_chart_generation_pipeline=None,
        powerbi_chart_generation_pipeline=None
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
            "page_size": 1000,
            "max_rows": 10000,
            "enable_pagination": True,
            "sort_by": None,
            "sort_order": "ASC",
            "timeout_seconds": 30,
            "cache_results": True,
            "cache_ttl_seconds": 300,
            "chart_format": "vega_lite",  # vega_lite, plotly, powerbi
            "include_other_formats": False,
            "use_multi_format": True,
            "remove_data_from_chart_schema": True,
            "language": "English"
        }
        self._engine = engine
        self._metrics = {}
        
        # Initialize chart generation pipelines if not provided
        self._chart_generator = chart_generation_pipeline or create_enhanced_vega_lite_chart_generation_pipeline()
        self._plotly_chart_generator = plotly_chart_generation_pipeline or create_plotly_chart_generation_pipeline(self._llm)
        self._powerbi_chart_generator = powerbi_chart_generation_pipeline or create_powerbi_chart_generation_pipeline(self._llm)
        
        # Initialize chart executor
        self._chart_executor = ChartExecutor(db_engine=engine)
        
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
        self._chart_executor.clear_cache()

    def set_chart_format(self, format: str) -> None:
        """Set the chart format (vega_lite, plotly, powerbi)"""
        supported_formats = ["vega_lite", "plotly", "powerbi"]
        if format not in supported_formats:
            raise ValueError(f"Unsupported format: {format}. Supported formats: {supported_formats}")
        self._configuration["chart_format"] = format
        logger.info(f"Chart format set to: {format}")

    def set_execution_config(self, config: ChartExecutionConfig) -> None:
        """Set the chart execution configuration"""
        self._configuration.update({
            "page_size": config.page_size,
            "max_rows": config.max_rows,
            "enable_pagination": config.enable_pagination,
            "sort_by": config.sort_by,
            "sort_order": config.sort_order,
            "timeout_seconds": config.timeout_seconds,
            "cache_results": config.cache_results,
            "cache_ttl_seconds": config.cache_ttl_seconds
        })
        logger.info("Chart execution configuration updated")

    async def _generate_chart_schema(
        self,
        query: str,
        sql: str,
        sample_data: Dict[str, Any],
        language: str = "English"
    ) -> Dict[str, Any]:
        """Generate chart schema using the appropriate chart generation pipeline"""
        try:
            chart_format = self._configuration.get("chart_format", "vega_lite")
            
            if chart_format == "vega_lite":
                result = await self._chart_generator.run(
                    query=query,
                    sql=sql,
                    data=sample_data,
                    language=language,
                    remove_data_from_chart_schema=self._configuration.get("remove_data_from_chart_schema", True)
                )
                
                if result.get("results"):
                    return {
                        "success": True,
                        "chart_schema": result.get("results", {}).get("chart_schema", {}),
                        "chart_type": result.get("results", {}).get("chart_type", ""),
                        "reasoning": result.get("results", {}).get("reasoning", ""),
                        "format": "vega_lite"
                    }
                else:
                    return {"success": False, "error": "Failed to generate Vega-Lite chart schema"}
            
            elif chart_format == "plotly":
                result = await self._plotly_chart_generator.run(
                    query=query,
                    sql=sql,
                    data=sample_data,
                    language=language,
                    remove_data_from_chart_config=self._configuration.get("remove_data_from_chart_schema", True)
                )
                
                if result.get("success", False):
                    return {
                        "success": True,
                        "chart_schema": result.get("chart_config", {}),
                        "chart_type": result.get("chart_type", ""),
                        "reasoning": result.get("reasoning", ""),
                        "format": "plotly"
                    }
                else:
                    return {"success": False, "error": result.get("error", "Failed to generate Plotly chart schema")}
            
            elif chart_format == "powerbi":
                result = await self._powerbi_chart_generator.run(
                    query=query,
                    sql=sql,
                    data=sample_data,
                    language=language,
                    remove_data_from_chart_config=self._configuration.get("remove_data_from_chart_schema", True)
                )
                
                if result.get("success", False):
                    return {
                        "success": True,
                        "chart_schema": result.get("chart_config", {}),
                        "chart_type": result.get("chart_type", ""),
                        "reasoning": result.get("reasoning", ""),
                        "format": "powerbi"
                    }
                else:
                    return {"success": False, "error": result.get("error", "Failed to generate PowerBI chart schema")}
            
            else:
                return {"success": False, "error": f"Unsupported chart format: {chart_format}"}
                
        except Exception as e:
            logger.error(f"Error generating chart schema: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _get_sample_data(self, sql: str, **kwargs) -> Dict[str, Any]:
        """Get sample data for chart schema generation"""
        try:
            # Modify SQL to get sample data (first 10 rows)
            sample_sql = f"SELECT * FROM ({sql}) as sample_query LIMIT 10"
            
            async with aiohttp.ClientSession() as session:
                success, result = await self._engine.execute_sql(
                    sample_sql,
                    session,
                    dry_run=False,
                    **kwargs
                )
                
                if success and result.get("data"):
                    # Convert to the format expected by chart generators
                    data = result["data"]
                    if data:
                        columns = list(data[0].keys())
                        rows = [[row[col] for col in columns] for row in data]
                        return {
                            "columns": columns,
                            "data": rows
                        }
                
                return {"columns": [], "data": []}
                
        except Exception as e:
            logger.error(f"Error getting sample data: {str(e)}")
            return {"columns": [], "data": []}

    async def run(
        self,
        query: str,
        sql: str,
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute chart with SQL data using ChartExecutor"""
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        try:
            # Update configuration if provided
            if configuration:
                self.update_configuration(configuration)
            
            # Define status update function
            def send_status_update(status: str, details: Dict[str, Any] = None):
                if status_callback:
                    try:
                        status_callback(status, details or {})
                    except Exception as e:
                        logger.error(f"Error in status callback: {str(e)}")
                logger.info(f"Chart Execution Status - {status}: {details}")
            
            send_status_update("started", {
                "project_id": project_id,
                "query": query,
                "sql": sql,
                "chart_format": self._configuration.get("chart_format", "vega_lite")
            })
            
            # Step 1: Get sample data for chart schema generation
            send_status_update("getting_sample_data", {"project_id": project_id})
            sample_data = await self._get_sample_data(sql, **kwargs)
            
            if not sample_data.get("data"):
                error_msg = "No sample data available for chart schema generation"
                send_status_update("error", {"project_id": project_id, "error": error_msg})
                raise Exception(error_msg)
            
            send_status_update("sample_data_ready", {
                "project_id": project_id,
                "sample_size": len(sample_data.get("data", []))
            })
            
            # Step 2: Generate chart schema
            send_status_update("generating_chart_schema", {
                "project_id": project_id,
                "chart_format": self._configuration.get("chart_format", "vega_lite")
            })
            
            language = self._configuration.get("language", "English")
            schema_result = await self._generate_chart_schema(
                query=query,
                sql=sql,
                sample_data=sample_data,
                language=language
            )
            
            if not schema_result.get("success", False):
                error_msg = f"Failed to generate chart schema: {schema_result.get('error', 'Unknown error')}"
                send_status_update("error", {"project_id": project_id, "error": error_msg})
                raise Exception(error_msg)
            
            chart_schema = schema_result.get("chart_schema", {})
            chart_type = schema_result.get("chart_type", "")
            reasoning = schema_result.get("reasoning", "")
            chart_format = schema_result.get("format", "vega_lite")
            
            send_status_update("chart_schema_ready", {
                "project_id": project_id,
                "chart_type": chart_type,
                "chart_format": chart_format
            })
            
            # Step 3: Create execution configuration
            exec_config = ChartExecutionConfig(
                page_size=self._configuration.get("page_size", 1000),
                max_rows=self._configuration.get("max_rows", 10000),
                enable_pagination=self._configuration.get("enable_pagination", True),
                sort_by=self._configuration.get("sort_by"),
                sort_order=self._configuration.get("sort_order", "ASC"),
                timeout_seconds=self._configuration.get("timeout_seconds", 30),
                cache_results=self._configuration.get("cache_results", True),
                cache_ttl_seconds=self._configuration.get("cache_ttl_seconds", 300)
            )
            
            # Step 4: Execute chart with full data
            send_status_update("executing_chart", {
                "project_id": project_id,
                "execution_config": {
                    "page_size": exec_config.page_size,
                    "max_rows": exec_config.max_rows,
                    "enable_pagination": exec_config.enable_pagination
                }
            })
            
            execution_result = await self._chart_executor.execute_chart(
                chart_schema=chart_schema,
                sql_query=sql,
                config=exec_config,
                db_engine=self._engine
            )
            
            if not execution_result.get("success", False):
                error_msg = f"Chart execution failed: {execution_result.get('error', 'Unknown error')}"
                send_status_update("error", {"project_id": project_id, "error": error_msg})
                raise Exception(error_msg)
            
            # Step 5: Prepare final result
            executed_schema = execution_result.get("chart_schema", {})
            data_count = execution_result.get("data_count", 0)
            validation = execution_result.get("validation", {})
            execution_config = execution_result.get("execution_config", {})
            
            send_status_update("chart_execution_complete", {
                "project_id": project_id,
                "data_count": data_count,
                "validation_success": validation.get("valid", False)
            })
            
            # Prepare response
            result = {
                "post_process": {
                    "chart_schema": executed_schema,
                    "chart_type": chart_type,
                    "reasoning": reasoning,
                    "chart_format": chart_format,
                    "data_count": data_count,
                    "validation": validation,
                    "execution_config": execution_config,
                    "sample_data": sample_data
                },
                "metadata": {
                    "project_id": project_id,
                    "query": query,
                    "sql": sql,
                    "chart_format": chart_format,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Add other format conversions if requested
            if self._configuration.get("include_other_formats", False) and self._configuration.get("use_multi_format", True):
                send_status_update("generating_other_formats", {"project_id": project_id})
                await self._add_format_conversions(result, sample_data, query, sql, language)
                send_status_update("other_formats_ready", {"project_id": project_id})
            
            # Update metrics
            self._metrics.update({
                "last_project_id": project_id,
                "last_query": query,
                "data_count": data_count,
                "success": True,
                "chart_type": chart_type,
                "chart_format": chart_format,
                "validation_success": validation.get("valid", False)
            })
            
            send_status_update("completed", {
                "project_id": project_id,
                "data_count": data_count,
                "chart_type": chart_type,
                "chart_format": chart_format
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in chart execution pipeline: {str(e)}")
            self._metrics.update({
                "last_error": str(e),
                "success": False,
                "last_project_id": project_id
            })
            
            if status_callback:
                try:
                    status_callback("error", {"project_id": project_id, "error": str(e)})
                except Exception as callback_error:
                    logger.error(f"Error in status callback: {str(callback_error)}")
            
            raise

    async def _add_format_conversions(
        self,
        result: Dict[str, Any],
        sample_data: Dict[str, Any],
        query: str,
        sql: str,
        language: str
    ) -> None:
        """Add conversions to other chart formats"""
        try:
            current_format = result["post_process"]["chart_format"]
            
            # Generate other formats
            if current_format == "vega_lite":
                # Generate Plotly version
                try:
                    plotly_result = await self._plotly_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=sample_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if plotly_result.get("success", False):
                        result["post_process"]["plotly_schema"] = plotly_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Plotly conversion: {e}")
                
                # Generate PowerBI version
                try:
                    powerbi_result = await self._powerbi_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=sample_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if powerbi_result.get("success", False):
                        result["post_process"]["powerbi_schema"] = powerbi_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate PowerBI conversion: {e}")
            
            elif current_format == "plotly":
                # Generate Vega-Lite version
                try:
                    vega_result = await self._chart_generator.run(
                        query=query,
                        sql=sql,
                        data=sample_data,
                        language=language,
                        remove_data_from_chart_schema=True
                    )
                    
                    if vega_result.get("results"):
                        result["post_process"]["vega_lite_schema"] = vega_result.get("results", {}).get("chart_schema", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Vega-Lite conversion: {e}")
                
                # Generate PowerBI version
                try:
                    powerbi_result = await self._powerbi_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=sample_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if powerbi_result.get("success", False):
                        result["post_process"]["powerbi_schema"] = powerbi_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate PowerBI conversion: {e}")
            
            elif current_format == "powerbi":
                # Generate Vega-Lite version
                try:
                    vega_result = await self._chart_generator.run(
                        query=query,
                        sql=sql,
                        data=sample_data,
                        language=language,
                        remove_data_from_chart_schema=True
                    )
                    
                    if vega_result.get("results"):
                        result["post_process"]["vega_lite_schema"] = vega_result.get("results", {}).get("chart_schema", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Vega-Lite conversion: {e}")
                
                # Generate Plotly version
                try:
                    plotly_result = await self._plotly_chart_generator.run(
                        query=query,
                        sql=sql,
                        data=sample_data,
                        language=language,
                        remove_data_from_chart_config=True
                    )
                    
                    if plotly_result.get("success", False):
                        result["post_process"]["plotly_schema"] = plotly_result.get("chart_config", {})
                except Exception as e:
                    logger.warning(f"Failed to generate Plotly conversion: {e}")
                    
        except Exception as e:
            logger.error(f"Error adding format conversions: {e}")




# Example usage of the enhanced DataSummarizationPipeline with chart generation


