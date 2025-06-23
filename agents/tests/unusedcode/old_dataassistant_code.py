class DataAssistancePipeline:
    """Data assistance pipeline for answering questions about database schema"""
    
    def __init__(
        self,
        doc_store_provider: DocumentStoreProvider,
        **kwargs
    ):
        self.llm = get_llm()
        self.doc_store_provider = doc_store_provider
        self._user_queues = {}
        
        # Initialize components with LangChain PromptTemplate
        self.prompt_template = PromptTemplate(
            template=data_assistance_user_prompt_template,
            input_variables=["query", "db_schemas", "language"]
        )
        
        # Initialize generator with system prompt
        self.generator = self.llm.bind(
            system_prompt=data_assistance_system_prompt,
            streaming_callback=self._streaming_callback
        )
    
    def _streaming_callback(self, chunk, query_id):
        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()
        asyncio.create_task(self._user_queues[query_id].put(chunk.content))
        if chunk.meta.get("finish_reason"):
            asyncio.create_task(self._user_queues[query_id].put("<DONE>"))
    
    async def get_streaming_results(self, query_id):
        async def _get_streaming_results(query_id):
            return await self._user_queues[query_id].get()

        if query_id not in self._user_queues:
            self._user_queues[query_id] = asyncio.Queue()
            
        while True:
            try:
                self._streaming_results = await asyncio.wait_for(
                    _get_streaming_results(query_id), timeout=120
                )
                if self._streaming_results == "<DONE>":
                    del self._user_queues[query_id]
                    break
                if self._streaming_results:
                    yield self._streaming_results
                    self._streaming_results = ""
            except TimeoutError:
                break
    
    @observe(name="Data Assistance")
    async def run(
        self,
        request: DataAssistanceRequest
    ) -> DataAssistanceResult:
        """Run the data assistance pipeline"""
        logger.info("Data Assistance pipeline is running...")
        
        try:
            # Prepare query with history
            query = request.query
            if request.histories:
                previous_queries = [history.question for history in request.histories]
                query = "\n".join(previous_queries) + "\n" + query
            
            
            # Build prompt using LangChain PromptTemplate
            prompt = self.prompt_template.format(
                query=query,
                db_schemas=request.db_schemas,
                language=request.language
            )
            
            # Concatenate system and user prompts directly
            full_prompt = f"{data_assistance_system_prompt}\n\n{prompt}"
            
            result = await self.llm.ainvoke(full_prompt)
            
            # Update metrics
            self.doc_store_provider.update_metrics("sql_queries", "query")
            logger.info(f"data assistance result I am here {result}")
            return DataAssistanceResult(
                success=True,
                data=result.content,
                metadata={
                    "operation": "data_assistance",
                    "language": request.language
                }
            )
            
        except Exception as e:
            logger.error(f"Error in data assistance: {e}")
            return DataAssistanceResult(
                success=False,
                error=str(e),
                metadata={
                    "operation": "data_assistance",
                    "language": request.language
                }
            )


class DataAssistanceFactory:
    """Factory class for creating data assistance pipelines"""
    
    @staticmethod
    def create_pipeline(
        doc_store_provider: DocumentStoreProvider,
        **kwargs
    ) -> DataAssistancePipeline:
        """Create data assistance pipeline with specified configuration"""
        return DataAssistancePipeline(
            doc_store_provider=doc_store_provider,
            **kwargs
        )
    
    @staticmethod
    def create_simple_pipeline(doc_store_provider: DocumentStoreProvider) -> DataAssistancePipeline:
        """Create simple pipeline with default settings"""
        return DataAssistanceFactory.create_pipeline(
            doc_store_provider=doc_store_provider
        )


# Convenience functions for common operations
async def quick_data_assistance(
    query: str,
    db_schemas: List[str],
    doc_store_provider: DocumentStoreProvider,
    language: str = "English"
) -> Dict[str, Any]:
    """Quick data assistance with minimal setup"""
    pipeline = DataAssistanceFactory.create_pipeline(
        doc_store_provider=doc_store_provider
    )
    
    request = DataAssistanceRequest(
        query=query,
        db_schemas=db_schemas,
        language=language
    )
    
    result = await pipeline.run(request)
    return result.data if result.success else {"error": result.error}


# Example usage and testing
async def example_usage():
    """Example of how to use the data assistance pipeline"""
    from app.core.dependencies import get_doc_store_provider
    
    # Get document store provider
    doc_store_provider = get_doc_store_provider()
    
    # Schema documents
    schema_docs = [
        "CREATE TABLE customers (id INT, name VARCHAR, email VARCHAR, created_at TIMESTAMP)",
        "CREATE TABLE orders (id INT, customer_id INT, total DECIMAL, order_date TIMESTAMP)",
        "CREATE TABLE order_items (order_id INT, product_id INT, quantity INT, price DECIMAL)"
    ]
    
    # Example: Quick data assistance
    print("=== Quick Data Assistance ===")
    result = await quick_data_assistance(
        query="What tables are available in the database?",
        db_schemas=schema_docs,
        doc_store_provider=doc_store_provider,
        language="English"
    )
    print(result)