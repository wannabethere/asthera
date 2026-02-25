"""
Async Query Pipeline
Handles user questions and returns data asynchronously
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI

from app.pipelines.base import ExtractionPipeline

logger = logging.getLogger(__name__)


class AsyncQueryPipeline(ExtractionPipeline):
    """
    General-purpose async pipeline for handling user queries
    
    This pipeline:
    1. Accepts user questions
    2. Processes them asynchronously
    3. Returns structured data
    4. Can be composed with other pipelines
    
    Usage:
        pipeline = AsyncQueryPipeline(
            name="user_query_pipeline",
            llm=llm,
            query_processor=custom_processor
        )
        
        result = await pipeline.run(
            inputs={
                "query": "What are the compliance requirements?",
                "context": {"project_id": "123"},
                "options": {"include_details": True}
            }
        )
    """
    
    def __init__(
        self,
        name: str = "async_query_pipeline",
        version: str = "1.0.0",
        description: str = "Async pipeline for processing user queries",
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        query_processor: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        result_formatter: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        max_retries: int = 3,
        timeout: Optional[float] = 30.0,
        **kwargs
    ):
        """
        Initialize async query pipeline
        
        Args:
            name: Pipeline name
            version: Pipeline version
            description: Pipeline description
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            query_processor: Custom query processing function
            result_formatter: Custom result formatting function
            max_retries: Maximum number of retries on failure
            timeout: Query timeout in seconds
            **kwargs: Additional pipeline parameters
        """
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.query_processor = query_processor
        self.result_formatter = result_formatter
        self.max_retries = max_retries
        self.timeout = timeout
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info(f"AsyncQueryPipeline '{self.name}' initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process user query asynchronously
        
        Args:
            inputs: Dictionary with keys:
                - query: User query string (required)
                - context: Optional context information
                - options: Optional processing options
                - filters: Optional data filters
                - metadata: Optional metadata
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with query results:
                - success: bool
                - data: Query results
                - metadata: Result metadata
                - processing_time: Time taken to process
        """
        if status_callback:
            status_callback("query_started", {"pipeline": self.name})
        
        query = inputs.get("query")
        if not query:
            return {
                "success": False,
                "error": "No query provided",
                "data": {}
            }
        
        context = inputs.get("context", {})
        options = inputs.get("options", {})
        filters = inputs.get("filters", {})
        metadata = inputs.get("metadata", {})
        
        try:
            import asyncio
            import time
            
            start_time = time.time()
            
            # Process query with timeout
            if self.timeout:
                if status_callback:
                    status_callback("processing", {"stage": "query_processing"})
                
                result = await asyncio.wait_for(
                    self._process_query(
                        query=query,
                        context=context,
                        options=options,
                        filters=filters,
                        metadata=metadata,
                        status_callback=status_callback
                    ),
                    timeout=self.timeout
                )
            else:
                result = await self._process_query(
                    query=query,
                    context=context,
                    options=options,
                    filters=filters,
                    metadata=metadata,
                    status_callback=status_callback
                )
            
            processing_time = time.time() - start_time
            
            # Format result if formatter provided
            if self.result_formatter:
                if status_callback:
                    status_callback("processing", {"stage": "formatting_result"})
                result = self.result_formatter(result)
            
            if status_callback:
                status_callback("completed", {
                    "stage": "query_complete",
                    "processing_time": processing_time
                })
            
            return {
                "success": True,
                "data": result,
                "metadata": {
                    "query": query,
                    "processing_time": processing_time,
                    "pipeline": self.name,
                    **metadata
                }
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Query processing timed out after {self.timeout}s")
            if status_callback:
                status_callback("error", {"stage": "timeout", "timeout": self.timeout})
            
            return {
                "success": False,
                "error": f"Query processing timed out after {self.timeout}s",
                "data": {}
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "processing_failed", "error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    async def _process_query(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any],
        filters: Dict[str, Any],
        metadata: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Internal method to process query
        
        Override this method in subclasses for custom query processing
        
        Args:
            query: User query
            context: Context information
            options: Processing options
            filters: Data filters
            metadata: Query metadata
            status_callback: Optional status callback
            
        Returns:
            Processed query results
        """
        # Use custom processor if provided
        if self.query_processor:
            return await self._call_query_processor(query, context, options, filters, metadata)
        
        # Default implementation: basic query processing
        return await self._default_query_processing(query, context, options, filters, metadata)
    
    async def _call_query_processor(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any],
        filters: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call custom query processor"""
        import asyncio
        import inspect
        
        # Check if query_processor is async or sync
        if inspect.iscoroutinefunction(self.query_processor):
            return await self.query_processor(query, {
                "context": context,
                "options": options,
                "filters": filters,
                "metadata": metadata
            })
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.query_processor,
                query,
                {
                    "context": context,
                    "options": options,
                    "filters": filters,
                    "metadata": metadata
                }
            )
    
    async def _default_query_processing(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any],
        filters: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Default query processing implementation
        
        This is a placeholder - override in subclasses or provide query_processor
        """
        logger.info(f"Processing query: {query[:100]}...")
        
        return {
            "query": query,
            "result": "Default processing - override _default_query_processing or provide query_processor",
            "context": context,
            "options": options,
            "filters": filters
        }
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info(f"AsyncQueryPipeline '{self.name}' cleaned up")


class AsyncDataRetrievalPipeline(AsyncQueryPipeline):
    """
    Specialized async pipeline for data retrieval operations
    
    This pipeline extends AsyncQueryPipeline with data-specific functionality:
    - Database query execution
    - Schema-aware data retrieval
    - Result aggregation and formatting
    - Pagination support
    
    Usage:
        pipeline = AsyncDataRetrievalPipeline(
            data_source=db_pool,
            schema_registry=schema_registry
        )
        
        result = await pipeline.run(
            inputs={
                "query": "Get all users",
                "context": {"project_id": "123"},
                "options": {
                    "limit": 100,
                    "offset": 0,
                    "include_metadata": True
                }
            }
        )
    """
    
    def __init__(
        self,
        data_source: Any = None,
        schema_registry: Optional[Any] = None,
        retrieval_helper: Optional[Any] = None,
        contextual_graph_service: Optional[Any] = None,
        name: str = "async_data_retrieval_pipeline",
        **kwargs
    ):
        """
        Initialize async data retrieval pipeline
        
        Args:
            data_source: Data source (e.g., db_pool, API client)
            schema_registry: Schema registry for metadata
            retrieval_helper: Optional retrieval helper for enhanced retrieval
            contextual_graph_service: Optional contextual graph service
            name: Pipeline name
            **kwargs: Additional pipeline parameters (description, llm, model_name, etc.)
        """
        description = kwargs.pop("description", "Async pipeline for data retrieval and querying")
        super().__init__(
            name=name,
            description=description,
            **kwargs
        )
        self.data_source = data_source
        self.schema_registry = schema_registry
        self.retrieval_helper = retrieval_helper
        self.contextual_graph_service = contextual_graph_service
    
    async def _default_query_processing(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any],
        filters: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process data retrieval query
        
        Args:
            query: User query (natural language or structured)
            context: Context including project_id, domain, etc.
            options: Retrieval options (limit, offset, include_metadata, etc.)
            filters: Data filters
            metadata: Query metadata
            
        Returns:
            Retrieved data with metadata
        """
        logger.info(f"Processing data retrieval query: {query[:100]}...")
        
        result = {
            "query": query,
            "data": [],
            "metadata": {
                "total_count": 0,
                "retrieved_count": 0,
                "has_more": False
            }
        }
        
        try:
            # Step 1: If retrieval_helper available, use it for schema retrieval
            if self.retrieval_helper and context.get("project_id"):
                schemas = await self._retrieve_schemas(
                    query=query,
                    project_id=context.get("project_id"),
                    options=options
                )
                result["schemas"] = schemas
                result["metadata"]["schema_count"] = len(schemas)
            
            # Step 2: If contextual_graph_service available, get contextual information
            if self.contextual_graph_service:
                contexts = await self._retrieve_contexts(
                    query=query,
                    context=context,
                    options=options
                )
                result["contexts"] = contexts
                result["metadata"]["context_count"] = len(contexts)
            
            # Step 3: Execute data retrieval based on available information
            if self.data_source:
                data = await self._execute_data_retrieval(
                    query=query,
                    context=context,
                    options=options,
                    filters=filters,
                    schemas=result.get("schemas", []),
                    contexts=result.get("contexts", [])
                )
                result["data"] = data
                result["metadata"]["retrieved_count"] = len(data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in data retrieval processing: {str(e)}", exc_info=True)
            result["error"] = str(e)
            return result
    
    async def _retrieve_schemas(
        self,
        query: str,
        project_id: str,
        options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant schemas for the query"""
        if not self.retrieval_helper:
            return []
        
        try:
            table_retrieval = {
                "table_retrieval_size": options.get("schema_limit", 10),
                "table_column_retrieval_size": options.get("column_limit", 50),
                "allow_using_db_schemas_without_pruning": False
            }
            
            db_schemas = await self.retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval=table_retrieval,
                query=query
            )
            
            return db_schemas.get("schemas", [])
            
        except Exception as e:
            logger.warning(f"Error retrieving schemas: {str(e)}")
            return []
    
    async def _retrieve_contexts(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant contextual information"""
        if not self.contextual_graph_service:
            return []
        
        try:
            # Use query_engine if available
            if hasattr(self.contextual_graph_service, 'query_engine'):
                # Search for relevant contexts
                search_results = await self.contextual_graph_service.query_engine.search_contexts(
                    query=query,
                    top_k=options.get("context_limit", 5),
                    filters=context.get("filters")
                )
                return search_results.get("contexts", [])
            
            return []
            
        except Exception as e:
            logger.warning(f"Error retrieving contexts: {str(e)}")
            return []
    
    async def _execute_data_retrieval(
        self,
        query: str,
        context: Dict[str, Any],
        options: Dict[str, Any],
        filters: Dict[str, Any],
        schemas: List[Dict[str, Any]],
        contexts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute the actual data retrieval
        
        This method should be overridden based on the data source type
        """
        logger.info(f"Executing data retrieval with {len(schemas)} schemas and {len(contexts)} contexts")
        
        # Placeholder implementation
        # In a real implementation, this would:
        # 1. Generate SQL/queries based on schemas and contexts
        # 2. Execute queries against data_source
        # 3. Aggregate and format results
        
        return [{
            "message": "Data retrieval placeholder - implement _execute_data_retrieval for your data source",
            "available_schemas": [s.get("table_name") for s in schemas[:5]],
            "available_contexts": [c.get("context_name") for c in contexts[:5]]
        }]
