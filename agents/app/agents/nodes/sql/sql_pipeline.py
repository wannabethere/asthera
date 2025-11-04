import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

import orjson
from langchain_openai import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings

from app.agents.nodes.sql.sql_rag_agent import (
    SQLRAGAgent,
    SQLOperationType,
    create_sql_rag_agent,
    generate_sql_with_rag,
    breakdown_sql_with_rag,
    answer_with_sql_rag,
)
from app.agents.nodes.sql.utils.sql_rag_tools import (
    SQLGenerationTool,
    SQLBreakdownTool,
    SQLReasoningTool,
    SQLAnswerTool,
    SQLCorrectionTool,
    SQLExpansionTool,
    SQLQuestionTool,
    SQLSummaryTool,
)
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration

from app.agents.nodes.sql.scoring_sql_rag_agent import (
    ScoringIntegratedSQLRAGAgent,
    create_scoring_integrated_sql_rag_agent,
)

logger = logging.getLogger("lexy-ai-service")


@dataclass
class SQLRequest:
    """Standard SQL request structure"""
    query: str
    language: str = "English"
    contexts: List[str] = None
    sql_samples: List[Dict[str, str]] = None
    configuration: Configuration = None
    project_id: str = None
    timeout: float = 30.0


@dataclass
class SQLResult:
    """Standard SQL result structure"""
    success: bool
    data: Dict[str, Any] = None
    error: str = None
    metadata: Dict[str, Any] = None


class SQLPipeline:
    """Unified SQL pipeline with all operations"""
    
    def __init__(
        self,
        llm,
        engine: Engine,
        doc_store: DocumentStoreProvider,
        embeddings=None,
        use_rag: bool = True,
        **kwargs
    ):
        self.llm = llm
        self.engine = engine
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.use_rag = use_rag
        
        # Initialize RAG agent if enabled
        if use_rag:
            self.rag_agent = create_sql_rag_agent(llm, engine, doc_store, embeddings=embeddings, **kwargs)
        else:
            self.rag_agent = None
        
        # Initialize individual tools
        self.sql_generation = SQLGenerationTool(llm, engine)
        self.sql_breakdown = SQLBreakdownTool(llm, engine)
        self.sql_reasoning = SQLReasoningTool(llm)
        self.sql_answer = SQLAnswerTool(llm)
        self.sql_correction = SQLCorrectionTool(llm, engine)
        self.sql_expansion = SQLExpansionTool(llm, engine)
        self.sql_question = SQLQuestionTool(llm)
        self.sql_summary = SQLSummaryTool(llm)
    
    
    async def generate_sql(self, request: SQLRequest) -> SQLResult:
        """Generate SQL from natural language"""
        try:
            if self.use_rag and self.rag_agent:
                result = await generate_sql_with_rag(
                    self.rag_agent,
                    request.query,
                    language=request.language,
                    configuration=request.configuration.__dict__ if request.configuration else {},
                    project_id=request.project_id,
                    timeout=request.timeout
                )
            else:
                result = await self.sql_generation.run(
                    query=request.query,
                    contexts=request.contexts or [],
                    configuration=request.configuration or Configuration(),
                    project_id=request.project_id,
                    timeout=request.timeout
                )
            print("result in enhanced sql pipeline", result)
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "generation", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL generation: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "generation", "rag_enabled": self.use_rag}
            )
    
    async def breakdown_sql(self, request: SQLRequest, sql: str) -> SQLResult:
        """Break down SQL into understandable steps"""
        try:
            if self.use_rag and self.rag_agent:
                result = await breakdown_sql_with_rag(
                    self.rag_agent,
                    request.query,
                    sql,
                    language=request.language,
                    project_id=request.project_id,
                    timeout=request.timeout
                )
            else:
                result = await self.sql_breakdown.run(
                    query=request.query,
                    sql=sql,
                    language=request.language
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "breakdown", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL breakdown: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "breakdown", "rag_enabled": self.use_rag}
            )
    
    async def generate_reasoning(self, request: SQLRequest) -> SQLResult:
        """Generate reasoning plan for SQL"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.REASONING,
                    request.query,
                    contexts=request.contexts or [],
                    language=request.language
                )
            else:
                result = await self.sql_reasoning.run(
                    query=request.query,
                    contexts=request.contexts or [],
                    language=request.language,
                    sql_samples=request.sql_samples or []
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "reasoning", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL reasoning: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "reasoning", "rag_enabled": self.use_rag}
            )
    
    async def generate_answer(
        self, 
        request: SQLRequest, 
        sql: str, 
        sql_data: Dict
    ) -> SQLResult:
        """Generate natural language answer from SQL results"""
        try:
            if self.use_rag and self.rag_agent:
                result = await answer_with_sql_rag(
                    self.rag_agent,
                    request.query,
                    sql,
                    sql_data,
                    language=request.language
                )
            else:
                result = await self.sql_answer.run(
                    query=request.query,
                    sql=sql,
                    sql_data=sql_data,
                    language=request.language
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "answer", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL answer generation: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "answer", "rag_enabled": self.use_rag}
            )
    
    async def correct_sql(
        self, 
        sql: str, 
        error_message: str, 
        contexts: List[str] = None
    ) -> SQLResult:
        """Correct invalid SQL"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.CORRECTION,
                    "",
                    sql=sql,
                    error_message=error_message,
                    contexts=contexts or []
                )
            else:
                result = await self.sql_correction.run(
                    sql=sql,
                    error_message=error_message,
                    contexts=contexts or []
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "correction", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL correction: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "correction", "rag_enabled": self.use_rag}
            )
    
    async def expand_sql(
        self, 
        adjustment_request: str, 
        original_sql: str, 
        contexts: List[str] = None
    ) -> SQLResult:
        """Expand SQL based on user request"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.EXPANSION,
                    adjustment_request,
                    original_sql=original_sql,
                    contexts=contexts or []
                )
            else:
                result = await self.sql_expansion.run(
                    adjustment_request=adjustment_request,
                    original_sql=original_sql,
                    contexts=contexts or []
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "expansion", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL expansion: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "expansion", "rag_enabled": self.use_rag}
            )
    
    async def sql_to_questions(self, sqls: List[str], language: str = "English") -> SQLResult:
        """Convert SQL queries to natural language questions"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.QUESTION,
                    "",
                    sqls=sqls,
                    language=language
                )
            else:
                result = await self.sql_question.run(
                    sqls=sqls,
                    language=language
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "question", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL to question conversion: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "question", "rag_enabled": self.use_rag}
            )
    
    async def summarize_sqls(
        self, 
        query: str, 
        sqls: List[str], 
        language: str = "English"
    ) -> SQLResult:
        """Summarize SQL queries"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.SUMMARY,
                    query,
                    sqls=sqls,
                    language=language
                )
            else:
                result = await self.sql_summary.run(
                    query=query,
                    sqls=sqls,
                    language=language
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "summary", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL summary: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "summary", "rag_enabled": self.use_rag}
            )
    
    async def complete_sql_workflow(self, request: SQLRequest) -> Dict[str, SQLResult]:
        """Complete SQL workflow with unified context: reasoning -> generation -> breakdown -> answer"""
        results = {}
        
        # Step 1: Retrieve unified context once
        logger.info("Step 1: Retrieving unified context")
        unified_context = await self._retrieve_unified_context(request)
        
        if not unified_context.get("success", False):
            return {"error": "Failed to retrieve unified context", "success": False}
        
        # Step 2: Generate reasoning using unified context
        logger.info("Step 2: Generating reasoning plan with unified context")
        reasoning_result = await self._generate_reasoning_with_context(request, unified_context["data"])
        results["reasoning"] = reasoning_result
        
        if not reasoning_result.success:
            return results
        
        # Step 3: Generate SQL using unified context and reasoning
        logger.info("Step 3: Generating SQL with unified context")
        sql_result = await self._generate_sql_with_context(request, unified_context["data"], reasoning_result.data)
        results["generation"] = sql_result
        
        if not sql_result.success:
            return results
        
        sql = sql_result.data.get("sql", "")
        
        # Step 4: Break down SQL using unified context
        logger.info("Step 4: Breaking down SQL with unified context")
        breakdown_result = await self._breakdown_sql_with_context(request, sql, unified_context["data"])
        results["breakdown"] = breakdown_result
        
        # Step 5: Generate answer using unified context
        logger.info("Step 5: Generating answer with unified context")
        sample_data = {"message": "Execute SQL to get actual data"}
        answer_result = await self._generate_answer_with_context(request, sql, sample_data, unified_context["data"])
        results["answer"] = answer_result
        
        return results

    async def _retrieve_unified_context(self, request: SQLRequest) -> Dict[str, Any]:
        """Retrieve unified context for SQL operations"""
        try:
            if not request.project_id:
                return {"success": False, "error": "project_id is required"}
            
            # Use RAG agent to retrieve unified context
            if self.use_rag and self.rag_agent:
                # Get schema context
                schema_result = await self.rag_agent.retrieval_helper.get_database_schemas(
                    project_id=request.project_id,
                    table_retrieval={
                        "table_retrieval_size": 10,
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": False
                    },
                    query=request.query
                )
                
                # Get SQL pairs
                sql_pairs_result = await self.rag_agent.retrieval_helper.get_sql_pairs(
                    query=request.query,
                    project_id=request.project_id,
                    similarity_threshold=0.3,
                    max_retrieval_size=3
                )
                
                # Get instructions
                instructions_result = await self.rag_agent.retrieval_helper.get_instructions(
                    query=request.query,
                    project_id=request.project_id,
                    similarity_threshold=0.3,
                    top_k=3
                )
                
                # Extract schema contexts
                schema_contexts = []
                relationships = []
                for schema in schema_result.get("schemas", []):
                    if isinstance(schema, dict):
                        table_ddl = schema.get("table_ddl", "")
                        if table_ddl:
                            schema_contexts.append(table_ddl)
                        
                        table_relationships = schema.get("relationships", [])
                        if table_relationships:
                            relationships.extend(table_relationships)
                
                return {
                    "success": True,
                    "data": {
                        "schema_contexts": schema_contexts,
                        "relationships": relationships,
                        "sql_pairs": sql_pairs_result.get("sql_pairs", []),
                        "instructions": instructions_result.get("documents", []),
                        "table_names": [schema.get("table_name", "") for schema in schema_result.get("schemas", [])],
                        "has_calculated_field": schema_result.get("has_calculated_field", False),
                        "has_metric": schema_result.get("has_metric", False)
                    }
                }
            else:
                # Fallback for non-RAG mode
                return {
                    "success": True,
                    "data": {
                        "schema_contexts": request.contexts or [],
                        "relationships": [],
                        "sql_pairs": request.sql_samples or [],
                        "instructions": [],
                        "table_names": [],
                        "has_calculated_field": False,
                        "has_metric": False
                    }
                }
        except Exception as e:
            logger.error(f"Error retrieving unified context: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_reasoning_with_context(self, request: SQLRequest, unified_context: Dict[str, Any]) -> SQLResult:
        """Generate reasoning using unified context"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.REASONING,
                    request.query,
                    contexts=unified_context["schema_contexts"],
                    language=request.language,
                    project_id=request.project_id
                )
            else:
                result = await self.sql_reasoning.run(
                    query=request.query,
                    contexts=unified_context["schema_contexts"],
                    language=request.language,
                    sql_samples=unified_context["sql_pairs"]
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "reasoning", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in reasoning generation: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "reasoning", "rag_enabled": self.use_rag}
            )

    async def _generate_sql_with_context(self, request: SQLRequest, unified_context: Dict[str, Any], reasoning_data: Dict[str, Any]) -> SQLResult:
        """Generate SQL using unified context and reasoning"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.GENERATION,
                    request.query,
                    contexts=unified_context["schema_contexts"],
                    language=request.language,
                    configuration=request.configuration.__dict__ if request.configuration else {},
                    project_id=request.project_id,
                    timeout=request.timeout
                )
            else:
                result = await self.sql_generation.run(
                    query=request.query,
                    contexts=unified_context["schema_contexts"],
                    configuration=request.configuration or Configuration(),
                    project_id=request.project_id,
                    timeout=request.timeout
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "generation", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL generation: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "generation", "rag_enabled": self.use_rag}
            )

    async def _breakdown_sql_with_context(self, request: SQLRequest, sql: str, unified_context: Dict[str, Any]) -> SQLResult:
        """Break down SQL using unified context"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.BREAKDOWN,
                    request.query,
                    sql=sql,
                    language=request.language,
                    project_id=request.project_id,
                    timeout=request.timeout
                )
            else:
                result = await self.sql_breakdown.run(
                    query=request.query,
                    sql=sql,
                    language=request.language
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "breakdown", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in SQL breakdown: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "breakdown", "rag_enabled": self.use_rag}
            )

    async def _generate_answer_with_context(self, request: SQLRequest, sql: str, sql_data: Dict, unified_context: Dict[str, Any]) -> SQLResult:
        """Generate answer using unified context"""
        try:
            if self.use_rag and self.rag_agent:
                result = await self.rag_agent.process_sql_request(
                    SQLOperationType.ANSWER,
                    request.query,
                    sql=sql,
                    sql_data=sql_data,
                    language=request.language
                )
            else:
                result = await self.sql_answer.run(
                    query=request.query,
                    sql=sql,
                    sql_data=sql_data,
                    language=request.language
                )
            
            return SQLResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                metadata={"operation": "answer", "rag_enabled": self.use_rag}
            )
        except Exception as e:
            logger.error(f"Error in answer generation: {e}")
            return SQLResult(
                success=False,
                error=str(e),
                metadata={"operation": "answer", "rag_enabled": self.use_rag}
            )


class SQLPipelineFactory:
    """Factory class for creating SQL pipelines"""
    
    @staticmethod
    def create_pipeline(
        engine: Engine = None,
        doc_store: DocumentStoreProvider = None,
        use_rag: bool = True,
        embeddings: Any = None,
        **kwargs
    ) -> SQLPipeline:
        """Create SQL pipeline with specified configuration"""
        
        llm = get_llm()
        
        return SQLPipeline(
            llm=llm,
            engine=engine,
            doc_store=doc_store,
            embeddings=embeddings if embeddings else get_embedder(),
            use_rag=use_rag,
            **kwargs
        )
    
    @staticmethod
    def create_simple_pipeline(engine: Engine) -> SQLPipeline:
        """Create simple pipeline with default settings"""
        return SQLPipelineFactory.create_pipeline(
            llm_provider="openai",
            engine=engine,
            use_rag=False
        )
    
    @staticmethod
    def create_rag_pipeline(engine: Engine, **kwargs) -> SQLPipeline:
        """Create RAG-enabled pipeline"""
        return SQLPipelineFactory.create_pipeline(
            llm_provider="openai",
            engine=engine,
            use_rag=True,
            **kwargs
        )


# Convenience functions for common operations
async def quick_sql_generation(
    query: str,
    schema_documents: List[str],
    engine: Engine,
    language: str = "English",
    use_rag: bool = True
) -> Dict[str, Any]:
    """Quick SQL generation with minimal setup"""
    pipeline = SQLPipelineFactory.create_pipeline(
        engine=engine,
        use_rag=use_rag
    )
    
    if use_rag:
        pipeline.initialize_knowledge_base(schema_documents=schema_documents)
    
    request = SQLRequest(
        query=query,
        language=language,
        contexts=schema_documents if not use_rag else None
    )
    
    result = await pipeline.generate_sql(request)
    return result.data if result.success else {"error": result.error}


async def complete_sql_analysis(
    query: str,
    schema_documents: List[str],
    engine: Engine,
    sql_samples: List[Dict[str, str]] = None,
    language: str = "English"
) -> Dict[str, Any]:
    """Complete SQL analysis workflow"""
    pipeline = SQLPipelineFactory.create_rag_pipeline(engine)
    pipeline.initialize_knowledge_base(
        schema_documents=schema_documents,
        sql_samples=sql_samples
    )
    
    request = SQLRequest(
        query=query,
        language=language,
        sql_samples=sql_samples
    )
    
    results = await pipeline.complete_sql_workflow(request)
    
    # Format results for easy consumption
    formatted_results = {}
    for step, result in results.items():
        if result.success:
            formatted_results[step] = result.data
        else:
            formatted_results[step] = {"error": result.error}
    
    return formatted_results


# Example usage and testing
async def example_usage():
    """Example of how to use the SQL pipeline"""
    
    # Mock engine for testing
    # engine = Engine()  # Initialize with your actual engine
    
    # Schema documents
    schema_docs = [
        "CREATE TABLE customers (id INT, name VARCHAR, email VARCHAR, created_at TIMESTAMP)",
        "CREATE TABLE orders (id INT, customer_id INT, total DECIMAL, order_date TIMESTAMP)",
        "CREATE TABLE order_items (order_id INT, product_id INT, quantity INT, price DECIMAL)"
    ]
    
    # SQL samples
    sql_samples = [
        {
            "question": "How many customers do we have?",
            "sql": "SELECT COUNT(*) FROM customers"
        },
        {
            "question": "What are the top selling products?",
            "sql": "SELECT product_id, SUM(quantity) as total_sold FROM order_items GROUP BY product_id ORDER BY total_sold DESC LIMIT 10"
        }
    ]
    
    # Example 1: Quick SQL generation
    print("=== Quick SQL Generation ===")
    # result = await quick_sql_generation(
    #     query="Show me all customers who placed orders in the last month",
    #     schema_documents=schema_docs,
    #     engine=engine,
    #     language="English",
    #     use_rag=True
    # )
    # print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
    
    # Example 2: Complete workflow
    print("\n=== Complete SQL Analysis ===")
    # results = await complete_sql_analysis(
    #     query="What is the total revenue by customer in the last quarter?",
    #     schema_documents=schema_docs,
    #     engine=engine,
    #     sql_samples=sql_samples,
    #     language="English"
    # )
    # print(orjson.dumps(results, option=orjson.OPT_INDENT_2).decode())
    
    # Example 3: Step-by-step usage
    print("\n=== Step-by-step Usage ===")
    # pipeline = SQLPipelineFactory.create_rag_pipeline(engine)
    # pipeline.initialize_knowledge_base(
    #     schema_documents=schema_docs,
    #     sql_samples=sql_samples
    # )
    
    # request = SQLRequest(
    #     query="Find customers with more than 5 orders",
    #     language="English"
    # )
    
    # # Generate SQL
    # sql_result = await pipeline.generate_sql(request)
    # if sql_result.success:
    #     print("Generated SQL:", sql_result.data.get("sql"))
    #     
    #     # Break down SQL
    #     breakdown_result = await pipeline.breakdown_sql(request, sql_result.data["sql"])
    #     if breakdown_result.success:
    #         print("SQL Breakdown:", breakdown_result.data)
    #     
    #     # Convert to question
    #     question_result = await pipeline.sql_to_questions([sql_result.data["sql"]])
    #     if question_result.success:
    #         print("Generated Question:", question_result.data.get("questions"))


if __name__ == "__main__":
    asyncio.run(example_usage())