import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import orjson
from datetime import datetime

# Import the original SQL RAG agent and the new scoring system
from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent, SQLOperationType, EnhancedSQLRAGAgent
from app.agents.nodes.sql.utils.sqlrelevance_score_util import SQLAdvancedRelevanceScorer
from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration


logger = logging.getLogger("lexy-ai-service")


class ScoringIntegratedSQLRAGAgent(SQLRAGAgent):
    """
    Enhanced SQL RAG Agent with integrated GRPO-based relevance scoring
    Extends the original SQLRAGAgent with advanced scoring capabilities
    """
    
    def __init__(self, 
                 llm, 
                 engine,
                 embeddings=None,
                 max_iterations=5,
                 document_store_provider=None,
                 scoring_config_path=None,
                 enable_scoring=True,
                 **kwargs):
        """
        Initialize enhanced SQL RAG agent with scoring capabilities
        
        Args:
            llm: Language model
            engine: Database engine
            embeddings: Embeddings for vector search
            max_iterations: Max agent iterations
            scoring_config_path: Path to scoring configuration
            enable_scoring: Whether to enable relevance scoring
            document_store_provider: Document store provider
            **kwargs: Additional arguments for base agent
        """
        # Initialize base agent
        super().__init__(llm, engine, embeddings, max_iterations, document_store_provider, **kwargs)
        
        # Initialize scoring system
        self.enable_scoring = enable_scoring
        if self.enable_scoring:
            self.relevance_scorer = SQLAdvancedRelevanceScorer(
                config_file_path=scoring_config_path
            )
        else:
            self.relevance_scorer = None
        self.document_store_provider = document_store_provider
        # Scoring history and analytics
        self.scoring_history = []
        self.performance_metrics = {
            "total_queries": 0,
            "high_quality_queries": 0,
            "correction_attempts": 0,
            "successful_corrections": 0
        }
        
        # Quality thresholds
        self.quality_thresholds = {
            "excellent": 0.8,
            "good": 0.6,
            "fair": 0.4,
            "poor": 0.0
        }
    
    def update_schema_context(self, schema_context: Dict[str, Any]):
        """Update schema context for scoring"""
        if self.enable_scoring and self.relevance_scorer:
            self.relevance_scorer.schema_context.update(schema_context)
            self.relevance_scorer._extract_schema_elements()
    
    async def _enhanced_sql_generation(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Enhanced SQL generation with integrated scoring and feedback loop
        """
        max_attempts = kwargs.get("max_correction_attempts", 1)
        current_attempt = 0
        best_result = None
        best_score = 0.0
        
        schema_context = kwargs.get("schema_context", {})
        if schema_context:
            self.update_schema_context(schema_context)
        
        while current_attempt < max_attempts:
            current_attempt += 1
            logger.info(f"SQL generation attempt {current_attempt}/{max_attempts}")
            
            # Generate SQL using base agent
            sql_result = await super()._handle_sql_generation(query, **kwargs)
            
            if not sql_result.get("success", False):
                continue
            
            # Add relevance scoring if enabled
            if self.enable_scoring:
               #TODO: Improve the Scoring algorithm, even though the results are accurate we are not getting the performance metrics as good but getting poor.
                scoring_result = await self._score_generation_result(
                    sql_result, query, schema_context
                )
                sql_result.update(scoring_result)
                
                current_score = scoring_result.get("final_relevance_score", 0.0)
                
                # Keep track of best result
                if current_score > best_score:
                    best_result = sql_result
                    best_score = current_score
                
                # If we have excellent quality, we can stop early
                if current_score >= self.quality_thresholds["excellent"]:
                    logger.info(f"Excellent quality achieved (score: {current_score:.3f})")
                    break
                
                # If quality is poor, try to improve with feedback
                if current_score < self.quality_thresholds["fair"] and current_attempt < max_attempts:
                    improvement_feedback = self._generate_improvement_feedback(scoring_result)
                    kwargs["additional_instructions"] = improvement_feedback
                    logger.info(f"Low quality score ({current_score:.3f}), attempting improvement")
                    continue
            else:
                best_result = sql_result
                break
       
        # Update performance metrics
        self.performance_metrics["total_queries"] += 1
        if best_score >= self.quality_thresholds["good"]:
            self.performance_metrics["high_quality_queries"] += 1
        
        return best_result or sql_result
    
    async def _score_generation_result(self, sql_result: Dict, query: str, schema_context: Dict) -> Dict:
        """Score the SQL generation result"""
        if not self.enable_scoring or not self.relevance_scorer:
            return {}
        
        # Construct model output for scoring
        model_output = f"""
        ### REASONING ###
        {sql_result.get('reasoning', 'No reasoning provided')}
        
        ### SQL ###
        {sql_result.get('sql', 'No SQL generated')}
        """
        
        # Get relevance scoring
        scoring_result = self.relevance_scorer.score_sql_reasoning(
            model_output, query, schema_context
        )
        
        # Add to scoring history
        self.scoring_history.append({
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "score": scoring_result["final_relevance_score"],
            "quality_level": scoring_result["quality_level"],
            "operation_type": scoring_result["detected_operation_type"],
            "sql_generated": sql_result.get('sql', '')[:100] + "..."  # First 100 chars
        })
        
        return {
            "relevance_scoring": scoring_result,
            "quality_level": scoring_result["quality_level"],
            "final_relevance_score": scoring_result["final_relevance_score"],
            "improvement_recommendations": self.relevance_scorer.get_improvement_recommendations(scoring_result)
        }
    
    def _generate_improvement_feedback(self, scoring_result: Dict) -> str:
        """Generate improvement feedback based on scoring results"""
        recommendations = scoring_result.get("improvement_recommendations", [])
        
        feedback_parts = [
            "Based on the analysis of your previous attempt, please improve the following:",
        ]
        
        for i, rec in enumerate(recommendations[:3], 1):  # Top 3 recommendations
            feedback_parts.append(f"{i}. {rec}")
        
        feedback_parts.append("Please provide more detailed reasoning and ensure SQL correctness.")
        
        return "\n".join(feedback_parts)
    
    async def _enhanced_sql_correction(self, sql: str, error_message: str, **kwargs) -> Dict[str, Any]:
        """Enhanced SQL correction with quality assessment"""
        self.performance_metrics["correction_attempts"] += 1
        
        # Get correction from base agent
        correction_result = await super()._handle_sql_correction("", sql=sql, error_message=error_message, **kwargs)
        
        if not correction_result.get("success", False):
            return correction_result
        
        # Add correction quality scoring if enabled
        if self.enable_scoring and self.relevance_scorer:
            original_sql = sql
            corrected_sql = correction_result.get("sql", "")
            reasoning = correction_result.get("reasoning", "")
            
            correction_scoring = self.relevance_scorer.score_sql_correction_quality(
                original_sql, corrected_sql, error_message, reasoning
            )
            
            correction_result.update({
                "correction_scoring": correction_scoring,
                "correction_quality_score": correction_scoring["total_correction_score"],
                "improvement_achieved": correction_scoring["improvement_score"]
            })
            
            # Update metrics
            if correction_scoring["total_correction_score"] >= 0.6:
                self.performance_metrics["successful_corrections"] += 1
        
        return correction_result
    
    async def process_sql_request_enhanced(self,
                                         operation: Union[SQLOperationType, str],
                                         query: str,
                                         **kwargs) -> Dict[str, Any]:
        """
        Enhanced SQL request processing with scoring integration
        """
        start_time = datetime.now()
        
        try:
            # Convert operation to enum if it's a string
            if isinstance(operation, str):
                try:
                    operation = SQLOperationType(operation.lower())
                except ValueError:
                    raise ValueError(f"Invalid operation type: {operation}")
           
            # Route to enhanced methods for generation and correction
            if operation == SQLOperationType.GENERATION:
                result = await self._enhanced_sql_generation(query, **kwargs)
            elif operation == SQLOperationType.CORRECTION:
                result = await self._enhanced_sql_correction(query, **kwargs)
            else:
                # Use base agent for other operations
                result = await super().process_sql_request(operation, query, **kwargs)
            
            # Add timing information
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            result.update({
                "processing_time_seconds": processing_time,
                "timestamp": end_time.isoformat(),
                "operation_type": operation.value
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced SQL processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation_type": operation.value if isinstance(operation, SQLOperationType) else operation,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_performance_analytics(self) -> Dict[str, Any]:
        """Get comprehensive performance analytics"""
        if not self.scoring_history:
            return {
                "message": "No scoring history available",
                "performance_metrics": self.performance_metrics
            }
        
        # Calculate score statistics
        scores = [entry["score"] for entry in self.scoring_history]
        quality_levels = [entry["quality_level"] for entry in self.scoring_history]
        
        # Quality distribution
        quality_distribution = {
            "excellent": quality_levels.count("excellent"),
            "good": quality_levels.count("good"),
            "fair": quality_levels.count("fair"), 
            "poor": quality_levels.count("poor")
        }
        
        # Operation type distribution
        operation_types = [entry["operation_type"] for entry in self.scoring_history]
        operation_distribution = {}
        for op_type in set(operation_types):
            operation_distribution[op_type] = operation_types.count(op_type)
        
        # Recent trend (last 10 queries)
        recent_scores = scores[-10:] if len(scores) > 10 else scores
        trend_direction = "improving" if len(recent_scores) > 1 and recent_scores[-1] > recent_scores[0] else "stable"
        
        return {
            "total_queries_scored": len(self.scoring_history),
            "average_score": sum(scores) / len(scores) if scores else 0,
            "median_score": sorted(scores)[len(scores)//2] if scores else 0,
            "score_range": {
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0
            },
            "quality_distribution": quality_distribution,
            "operation_distribution": operation_distribution,
            "recent_trend": {
                "direction": trend_direction,
                "recent_scores": recent_scores
            },
            "performance_metrics": self.performance_metrics,
            "success_rates": {
                "overall_success_rate": self.performance_metrics["high_quality_queries"] / max(1, self.performance_metrics["total_queries"]),
                "correction_success_rate": self.performance_metrics["successful_corrections"] / max(1, self.performance_metrics["correction_attempts"])
            }
        }
    
    def get_quality_insights(self) -> Dict[str, Any]:
        """Get detailed quality insights and recommendations"""
        analytics = self.get_performance_analytics()
        
        insights = []
        recommendations = []
        
        # Analyze quality distribution
        quality_dist = analytics.get("quality_distribution", {})
        total_queries = sum(quality_dist.values())
        
        if total_queries == 0:
            return {"message": "No data available for quality insights"}
        
        excellent_rate = quality_dist.get("excellent", 0) / total_queries
        poor_rate = quality_dist.get("poor", 0) / total_queries
        
        if excellent_rate > 0.7:
            insights.append("System is performing excellently with high-quality SQL generation")
        elif excellent_rate < 0.3:
            insights.append("System needs improvement in SQL generation quality")
            recommendations.append("Review and enhance reasoning prompts")
            recommendations.append("Provide more comprehensive schema context")
        
        if poor_rate > 0.3:
            insights.append("High rate of poor-quality outputs detected")
            recommendations.extend([
                "Implement additional validation steps",
                "Enhance error handling and correction mechanisms",
                "Review training data quality"
            ])
        
        # Analyze correction success rate
        correction_rate = analytics["success_rates"]["correction_success_rate"]
        if correction_rate < 0.5:
            insights.append("SQL correction mechanism needs improvement")
            recommendations.append("Enhance error message interpretation and correction logic")
        
        return {
            "insights": insights,
            "recommendations": recommendations,
            "quality_metrics": {
                "excellent_rate": excellent_rate,
                "poor_rate": poor_rate,
                "correction_success_rate": correction_rate
            }
        }
    
    async def batch_evaluate_queries(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Batch evaluate multiple queries for performance testing
        
        Args:
            queries: List of dicts with 'query' and optional 'expected_sql', 'schema_context'
            
        Returns:
            Evaluation results and statistics
        """
        results = []
        total_score = 0.0
        
        for i, query_data in enumerate(queries):
            query = query_data["query"]
            schema_context = query_data.get("schema_context", {})
            
            logger.info(f"Evaluating query {i+1}/{len(queries)}: {query[:50]}...")
            
            # Generate SQL
            result = await self.process_sql_request_enhanced(
                SQLOperationType.GENERATION,
                query,
                schema_context=schema_context
            )
            
            evaluation = {
                "query_index": i,
                "query": query,
                "generated_sql": result.get("sql", ""),
                "success": result.get("success", False),
                "relevance_score": result.get("final_relevance_score", 0.0),
                "quality_level": result.get("quality_level", "unknown"),
                "processing_time": result.get("processing_time_seconds", 0.0)
            }
            
            # Compare with expected SQL if provided
            if "expected_sql" in query_data:
                similarity_score = self._calculate_sql_similarity(
                    result.get("sql", ""), 
                    query_data["expected_sql"]
                )
                evaluation["expected_sql_similarity"] = similarity_score
            
            results.append(evaluation)
            total_score += evaluation["relevance_score"]
        
        # Calculate aggregate statistics
        avg_score = total_score / len(queries) if queries else 0
        success_rate = sum(1 for r in results if r["success"]) / len(queries) if queries else 0
        avg_processing_time = sum(r["processing_time"] for r in results) / len(queries) if queries else 0
        
        return {
            "individual_results": results,
            "aggregate_stats": {
                "total_queries": len(queries),
                "average_relevance_score": avg_score,
                "success_rate": success_rate,
                "average_processing_time": avg_processing_time
            },
            "quality_distribution": {
                level: sum(1 for r in results if r["quality_level"] == level)
                for level in ["excellent", "good", "fair", "poor", "unknown"]
            }
        }
    
    def _calculate_sql_similarity(self, sql1: str, sql2: str) -> float:
        """
        Simple SQL similarity calculation
        In production, you might want to use more sophisticated SQL parsing
        """
        if not sql1 or not sql2:
            return 0.0
        
        # Normalize queries
        sql1_norm = " ".join(sql1.lower().split())
        sql2_norm = " ".join(sql2.lower().split())
        
        if sql1_norm == sql2_norm:
            return 1.0
        
        # Simple token-based similarity
        tokens1 = set(sql1_norm.split())
        tokens2 = set(sql2_norm.split())
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def export_scoring_history(self, filepath: str = None) -> str:
        """Export scoring history to JSON file"""
        if not filepath:
            filepath = f"sql_scoring_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "total_entries": len(self.scoring_history),
                "performance_metrics": self.performance_metrics
            },
            "scoring_history": self.scoring_history,
            "performance_analytics": self.get_performance_analytics()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Scoring history exported to {filepath}")
        return filepath


# Factory function for creating enhanced agents
def create_enhanced_sql_rag_agent(llm, engine, document_store_provider, scoring_config_path=None, **kwargs):
    """
    Factory function to create an enhanced SQL RAG agent with scoring
    
    Args:
        llm: Language model instance
        engine: Database engine instance
        scoring_config_path: Path to scoring configuration file
        **kwargs: Additional arguments for agent initialization
        
    Returns:
        EnhancedSQLRAGAgent instance
    """
    # Create base SQL RAG agent
    base_agent = SQLRAGAgent(llm=llm, engine=engine, document_store_provider=document_store_provider, **kwargs)
    
    # Create relevance scorer
    relevance_scorer = SQLAdvancedRelevanceScorer(
        config_file_path=scoring_config_path
    )
    
    # Create enhanced agent
    enhanced_agent = EnhancedSQLRAGAgent(
        base_agent=base_agent,
        relevance_scorer=relevance_scorer
    )
    
    return enhanced_agent


def create_scoring_integrated_sql_rag_agent(llm, engine, document_store_provider, scoring_config_path=None, **kwargs):
    """
    Factory function to create a scoring-integrated SQL RAG agent (alternative approach)
    
    Args:
        llm: Language model instance
        engine: Database engine instance
        scoring_config_path: Path to scoring configuration file
        **kwargs: Additional arguments for agent initialization
        
    Returns:
        ScoringIntegratedSQLRAGAgent instance
    """
    return ScoringIntegratedSQLRAGAgent(
        llm=llm,
        engine=engine,
        document_store_provider=document_store_provider,
        scoring_config_path=scoring_config_path,
        **kwargs
    )


# Example usage and testing
async def demonstrate_enhanced_sql_rag():
    """Demonstrate both enhanced SQL RAG agent approaches"""
    
    # Mock objects for demonstration
    class MockLLM:
        async def agenerate(self, prompts):
            # Mock response
            return "Mock LLM response"
    
    class MockEngine:
        pass
    
    # Create enhanced agent (wrapper approach)
    llm = MockLLM()
    engine = MockEngine()
    
    print("=== Creating EnhancedSQLRAGAgent (Wrapper Approach) ===")
    enhanced_agent = create_enhanced_sql_rag_agent(
        llm=llm,
        engine=engine,
        scoring_config_path=None,  # Use default config
        max_iterations=3
    )
    
    # Set up schema context
    schema_context = {
        "schema": {
            "customers": ["customer_id", "name", "email", "signup_date"],
            "orders": ["order_id", "customer_id", "order_date", "total_amount", "status"],
            "products": ["product_id", "name", "category", "price", "stock_quantity"]
        }
    }
    
    enhanced_agent.update_schema_context(schema_context)
    
    print("Enhanced SQL RAG Agent created successfully!")
    print("Available methods:")
    print("- generate_sql_with_scoring()")
    print("- correct_sql_with_scoring()")
    print("- breakdown_sql_with_scoring()")
    print("- answer_with_scoring()")
    print("- get_performance_analytics()")
    print("- get_quality_insights()")
    
    # Create scoring-integrated agent (inheritance approach)
    print("\n=== Creating ScoringIntegratedSQLRAGAgent (Inheritance Approach) ===")
    integrated_agent = create_scoring_integrated_sql_rag_agent(
        llm=llm,
        engine=engine,
        enable_scoring=True,
        max_iterations=3
    )
    
    integrated_agent.update_schema_context(schema_context)
    
    print("Scoring-Integrated SQL RAG Agent created successfully!")
    print("Available methods:")
    print("- process_sql_request_enhanced()")
    print("- get_performance_analytics()")
    print("- get_quality_insights()")
    print("- batch_evaluate_queries()")
    print("- export_scoring_history()")
    
    # Test queries for batch evaluation
    test_queries = [
        {
            "query": "Find all customers who placed orders in the last 30 days",
            "schema_context": schema_context,
            "expected_sql": "SELECT DISTINCT c.* FROM customers c JOIN orders o ON c.customer_id = o.customer_id WHERE o.order_date >= CURRENT_DATE - INTERVAL '30 days'"
        },
        {
            "query": "What are the top 5 best-selling products?",
            "schema_context": schema_context
        },
        {
            "query": "Calculate total revenue by month for the current year",
            "schema_context": schema_context
        }
    ]
    
    print(f"\nTest queries prepared ({len(test_queries)} queries):")
    for i, query_data in enumerate(test_queries, 1):
        print(f"{i}. {query_data['query']}")
    
    # Show analytics structure for both approaches
    print("\n=== Performance Analytics Comparison ===")
    
    # Enhanced agent analytics
    enhanced_analytics = enhanced_agent.get_performance_analytics()
    print(f"EnhancedSQLRAGAgent - Total Queries: {enhanced_analytics.get('total_queries', 0)}")
    
    # Integrated agent analytics  
    integrated_analytics = integrated_agent.get_performance_analytics()
    print(f"ScoringIntegratedSQLRAGAgent - Total Queries: {integrated_analytics['performance_metrics']['total_queries']}")
    
    return enhanced_agent, integrated_agent


# Example usage functions
async def example_enhanced_agent_usage():
    """Example of using EnhancedSQLRAGAgent"""
    
    # Setup (in real implementation, use actual LLM and engine)
    from langchain.llms import OpenAI
    # from your_engine import Engine
    
    # llm = OpenAI(temperature=0.1)
    # engine = Engine()
    
    # For demo purposes, use mock objects
    class MockLLM:
        pass
    class MockEngine:
        pass
    
    llm = MockLLM()
    engine = MockEngine()
    
    # Create enhanced agent
    agent = create_enhanced_sql_rag_agent(llm, engine)
    
    # Update schema
    schema_context = {
        "schema": {
            "customers": ["id", "name", "email"],
            "orders": ["id", "customer_id", "total", "date"]
        }
    }
    agent.update_schema_context(schema_context)
    
    # Example usage (commented out since we're using mock objects)
    """
    # Generate SQL with scoring
    result = await agent.generate_sql_with_scoring(
        "Find customers who spent more than $1000",
        schema_context=schema_context,
        max_improvement_attempts=3
    )
    
    print(f"Generated SQL: {result['sql']}")
    print(f"Quality Score: {result['final_score']:.3f}")
    print(f"Quality Level: {result['quality_level']}")
    
    # Get performance analytics
    analytics = agent.get_performance_analytics()
    print(f"Total queries processed: {analytics['total_queries']}")
    print(f"Average score: {analytics['average_score']:.3f}")
    
    # Get quality insights
    insights = agent.get_quality_insights()
    print("Quality insights:", insights)
    """
    
    return agent


if __name__ == "__main__":
    # Run demonstration
    print("Advanced SQL RAG Agent Integration with Relevance Scoring")
    print("=" * 70)
    
    async def main():
        # Demonstrate both approaches
        enhanced_agent, integrated_agent = await demonstrate_enhanced_sql_rag()
        
        # Show example usage
        print("\n=== Example Usage Patterns ===")
        example_agent = await example_enhanced_agent_usage()
        
        print("\nBoth enhanced agent types are now available:")
        print("1. EnhancedSQLRAGAgent - Wrapper approach around existing agent")
        print("2. ScoringIntegratedSQLRAGAgent - Inheritance approach with deep integration")
        
        return enhanced_agent, integrated_agent, example_agent
    
    asyncio.run(main())