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
        """Complete SQL workflow: reasoning -> generation -> breakdown -> answer"""
        results = {}
        
        # Step 1: Generate reasoning
        logger.info("Step 1: Generating reasoning plan")
        reasoning_result = await self.generate_reasoning(request)
        results["reasoning"] = reasoning_result
        
        if not reasoning_result.success:
            return results
        
        # Step 2: Generate SQL using reasoning
        logger.info("Step 2: Generating SQL")
        # Add reasoning to the request context
        if reasoning_result.data and "reasoning" in reasoning_result.data:
            enhanced_request = SQLRequest(
                query=request.query,
                language=request.language,
                contexts=request.contexts,
                sql_samples=request.sql_samples,
                configuration=request.configuration,
                project_id=request.project_id,
                timeout=request.timeout
            )
            
            sql_result = await self.generate_sql(enhanced_request)
            results["generation"] = sql_result
            
            if not sql_result.success:
                return results
            
            sql = sql_result.data.get("sql", "")
            
            # Step 3: Break down SQL
            logger.info("Step 3: Breaking down SQL")
            breakdown_result = await self.breakdown_sql(request, sql)
            results["breakdown"] = breakdown_result
            
            # Step 4: Generate sample answer (if SQL data is available)
            # Note: In a real scenario, you would execute the SQL to get actual data
            logger.info("Step 4: Generating answer (with sample data)")
            sample_data = {"message": "Execute SQL to get actual data"}
            answer_result = await self.generate_answer(request, sql, sample_data)
            results["answer"] = answer_result
        
        return results


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