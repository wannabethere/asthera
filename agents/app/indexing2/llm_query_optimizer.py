"""
LLM-Powered Query Optimizer

This module uses Large Language Models to optimize SQL queries based on
field type classifications and business context.

Features:
- LLM-based query optimization
- Performance analysis and recommendations
- Business context-aware optimization
- Intelligent indexing suggestions
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("genieml-agents")


class OptimizationLevel(Enum):
    """Query optimization levels."""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class OptimizationResult:
    """Result from LLM query optimization."""
    optimized_query: str
    optimization_level: str
    performance_improvements: List[str]
    indexing_suggestions: List[str]
    business_impact: str
    confidence: float
    reasoning: str


class LLMQueryOptimizer:
    """
    LLM-powered query optimizer for intelligent SQL optimization.
    
    This class uses LLMs to:
    1. Analyze and optimize SQL queries
    2. Provide performance recommendations
    3. Suggest indexing strategies
    4. Evaluate business impact
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize the LLM query optimizer.
        
        Args:
            llm_client: Optional LLM client for optimization
        """
        self.llm_client = llm_client
        self.optimization_cache = {}
        logger.info("LLM Query Optimizer initialized")
    
    async def optimize_query_with_llm(
        self,
        original_query: str,
        table_document: Dict[str, Any],
        query_context: Optional[Dict[str, Any]] = None,
        optimization_level: OptimizationLevel = OptimizationLevel.INTERMEDIATE
    ) -> OptimizationResult:
        """
        Use LLM to optimize a SQL query.
        
        Args:
            original_query: Original SQL query to optimize
            table_document: TABLE_DOCUMENT with field type information
            query_context: Optional query context and requirements
            optimization_level: Level of optimization to apply
            
        Returns:
            OptimizationResult with optimized query and recommendations
        """
        logger.info(f"Optimizing query with LLM (level: {optimization_level.value})")
        
        try:
            # Create optimization prompt
            prompt = self._create_optimization_prompt(
                original_query, table_document, query_context, optimization_level
            )
            
            # Get LLM response
            if self.llm_client:
                response = await self._get_llm_response(prompt)
                # Parse LLM response
                result = self._parse_optimization_response(response, original_query, table_document)
            else:
                # Fallback to rule-based optimization
                result = await self._fallback_optimization(original_query, table_document)
            
            # Cache result
            cache_key = f"{hash(original_query)}_{optimization_level.value}"
            self.optimization_cache[cache_key] = result
            
            logger.info(f"Successfully optimized query with LLM")
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing query with LLM: {str(e)}")
            # Return fallback optimization
            return await self._fallback_optimization(original_query, table_document)
    
    async def analyze_query_performance_with_llm(
        self,
        query: str,
        table_document: Dict[str, Any],
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze query performance and provide recommendations.
        
        Args:
            query: SQL query to analyze
            table_document: TABLE_DOCUMENT with field type information
            performance_metrics: Optional performance metrics
            
        Returns:
            Dictionary with performance analysis and recommendations
        """
        logger.info("Analyzing query performance with LLM")
        
        try:
            # Create performance analysis prompt
            prompt = self._create_performance_analysis_prompt(
                query, table_document, performance_metrics
            )
            
            # Get LLM response
            if self.llm_client:
                response = await self._get_llm_response(prompt)
                # Parse LLM response
                result = self._parse_performance_response(response, query, table_document)
            else:
                # Fallback to rule-based analysis
                result = await self._fallback_performance_analysis(query, table_document)
            
            logger.info("Successfully analyzed query performance with LLM")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing query performance with LLM: {str(e)}")
            # Return fallback analysis
            return await self._fallback_performance_analysis(query, table_document)
    
    async def suggest_indexing_strategy_with_llm(
        self,
        table_document: Dict[str, Any],
        query_patterns: List[str],
        performance_requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to suggest indexing strategies.
        
        Args:
            table_document: TABLE_DOCUMENT with field type information
            query_patterns: List of common query patterns
            performance_requirements: Optional performance requirements
            
        Returns:
            Dictionary with indexing strategy recommendations
        """
        logger.info("Suggesting indexing strategy with LLM")
        
        try:
            # Create indexing strategy prompt
            prompt = self._create_indexing_strategy_prompt(
                table_document, query_patterns, performance_requirements
            )
            
            # Get LLM response
            if self.llm_client:
                response = await self._get_llm_response(prompt)
                # Parse LLM response
                result = self._parse_indexing_response(response, table_document)
            else:
                # Fallback to rule-based indexing
                result = await self._fallback_indexing_strategy(table_document, query_patterns)
            
            logger.info("Successfully suggested indexing strategy with LLM")
            return result
            
        except Exception as e:
            logger.error(f"Error suggesting indexing strategy with LLM: {str(e)}")
            # Return fallback indexing strategy
            return await self._fallback_indexing_strategy(table_document, query_patterns)
    
    def _create_optimization_prompt(
        self,
        original_query: str,
        table_document: Dict[str, Any],
        query_context: Optional[Dict[str, Any]],
        optimization_level: OptimizationLevel
    ) -> str:
        """Create a prompt for LLM query optimization."""
        
        table_name = table_document.get("table_name", "")
        table_description = table_document.get("description", "")
        business_purpose = table_document.get("business_purpose", "")
        domain = table_document.get("domain", "")
        
        columns = table_document.get("columns", [])
        column_info = []
        
        for column in columns:
            field_type = column.get("field_type", "dimension")
            column_info.append({
                "name": column.get("name", ""),
                "type": column.get("type", ""),
                "field_type": field_type,
                "description": column.get("business_description", ""),
                "business_purpose": column.get("business_purpose", ""),
                "usage_type": column.get("usage_type", "")
            })
        
        optimization_guidelines = {
            OptimizationLevel.BASIC: "Basic optimizations: proper indexing, simple query structure",
            OptimizationLevel.INTERMEDIATE: "Intermediate optimizations: join optimization, subquery improvements, aggregation optimization",
            OptimizationLevel.ADVANCED: "Advanced optimizations: query rewriting, advanced indexing, partitioning strategies",
            OptimizationLevel.EXPERT: "Expert optimizations: complex query transformations, advanced performance tuning, custom optimization strategies"
        }
        
        prompt = f"""
You are a SQL performance expert. Optimize the following query for maximum performance.

ORIGINAL QUERY:
{original_query}

TABLE INFORMATION:
- Table Name: {table_name}
- Description: {table_description}
- Business Purpose: {business_purpose}
- Domain: {domain}

COLUMNS WITH FIELD TYPES:
{json.dumps(column_info, indent=2)}

OPTIMIZATION LEVEL: {optimization_level.value}
GUIDELINES: {optimization_guidelines[optimization_level]}

FIELD TYPE OPTIMIZATION RULES:
- facts: Optimize aggregations, use appropriate functions, consider materialized views
- dimensions: Optimize filtering, use appropriate indexes, consider denormalization
- identifiers: Optimize joins, use integer types, ensure proper indexing
- timestamps: Optimize date functions, consider partitioning, use appropriate data types
- calculated: Optimize expressions, consider pre-computation, use efficient algorithms

Please respond with a JSON object containing:
{{
    "optimized_query": "optimized SQL query",
    "optimization_level": "{optimization_level.value}",
    "performance_improvements": ["list of specific performance improvements"],
    "indexing_suggestions": ["list of indexing recommendations"],
    "business_impact": "explanation of business value and impact",
    "confidence": "confidence score 0.0-1.0",
    "reasoning": "detailed explanation of optimization decisions"
}}
"""
        
        if query_context:
            prompt += f"\nQUERY CONTEXT:\n{json.dumps(query_context, indent=2)}"
        
        return prompt
    
    def _create_performance_analysis_prompt(
        self,
        query: str,
        table_document: Dict[str, Any],
        performance_metrics: Optional[Dict[str, Any]]
    ) -> str:
        """Create a prompt for LLM performance analysis."""
        
        table_name = table_document.get("table_name", "")
        columns = table_document.get("columns", [])
        
        # Analyze query for field type usage
        fact_columns = [col for col in columns if col.get("field_type") == "fact"]
        dimension_columns = [col for col in columns if col.get("field_type") == "dimension"]
        identifier_columns = [col for col in columns if col.get("field_type") == "identifier"]
        timestamp_columns = [col for col in columns if col.get("field_type") == "timestamp"]
        
        prompt = f"""
You are a database performance analyst. Analyze the following query for performance characteristics and bottlenecks.

QUERY TO ANALYZE:
{query}

TABLE INFORMATION:
- Table Name: {table_name}
- Fact Columns: {[col.get('name') for col in fact_columns]}
- Dimension Columns: {[col.get('name') for col in dimension_columns]}
- Identifier Columns: {[col.get('name') for col in identifier_columns]}
- Timestamp Columns: {[col.get('name') for col in timestamp_columns]}

PERFORMANCE ANALYSIS AREAS:
1. Query Structure Analysis
2. Field Type Usage Optimization
3. Indexing Requirements
4. Join Optimization
5. Aggregation Efficiency
6. Filtering Performance
7. Business Impact Assessment

Please respond with a JSON object containing:
{{
    "performance_score": "overall performance score 0-100",
    "bottlenecks": ["list of identified performance bottlenecks"],
    "optimization_opportunities": ["list of optimization opportunities"],
    "indexing_recommendations": ["list of specific indexing recommendations"],
    "query_structure_analysis": "analysis of query structure efficiency",
    "field_type_optimization": "analysis of field type usage optimization",
    "business_impact": "assessment of business impact and value",
    "confidence": "confidence score 0.0-1.0"
}}
"""
        
        if performance_metrics:
            prompt += f"\nPERFORMANCE METRICS:\n{json.dumps(performance_metrics, indent=2)}"
        
        return prompt
    
    def _create_indexing_strategy_prompt(
        self,
        table_document: Dict[str, Any],
        query_patterns: List[str],
        performance_requirements: Optional[Dict[str, Any]]
    ) -> str:
        """Create a prompt for LLM indexing strategy."""
        
        table_name = table_document.get("table_name", "")
        columns = table_document.get("columns", [])
        
        # Categorize columns by field type
        fact_columns = [col for col in columns if col.get("field_type") == "fact"]
        dimension_columns = [col for col in columns if col.get("field_type") == "dimension"]
        identifier_columns = [col for col in columns if col.get("field_type") == "identifier"]
        timestamp_columns = [col for col in columns if col.get("field_type") == "timestamp"]
        
        prompt = f"""
You are a database indexing expert. Design an optimal indexing strategy for the following table and query patterns.

TABLE INFORMATION:
- Table Name: {table_name}
- Fact Columns: {[col.get('name') for col in fact_columns]}
- Dimension Columns: {[col.get('name') for col in dimension_columns]}
- Identifier Columns: {[col.get('name') for col in identifier_columns]}
- Timestamp Columns: {[col.get('name') for col in timestamp_columns]}

QUERY PATTERNS:
{json.dumps(query_patterns, indent=2)}

INDEXING STRATEGY CONSIDERATIONS:
1. Primary Key Indexes
2. Foreign Key Indexes
3. Dimension Filtering Indexes
4. Fact Aggregation Indexes
5. Timestamp Range Indexes
6. Composite Indexes
7. Covering Indexes
8. Partial Indexes
9. Bitmap Indexes (for low-cardinality dimensions)
10. Columnar Storage (for analytical workloads)

Please respond with a JSON object containing:
{{
    "indexing_strategy": "overall indexing strategy description",
    "primary_indexes": ["list of primary key indexes"],
    "secondary_indexes": ["list of secondary indexes"],
    "composite_indexes": ["list of composite indexes"],
    "specialized_indexes": ["list of specialized indexes (bitmap, partial, etc.)"],
    "storage_recommendations": ["list of storage recommendations"],
    "performance_impact": "expected performance impact",
    "maintenance_considerations": ["list of maintenance considerations"],
    "confidence": "confidence score 0.0-1.0"
}}
"""
        
        if performance_requirements:
            prompt += f"\nPERFORMANCE REQUIREMENTS:\n{json.dumps(performance_requirements, indent=2)}"
        
        return prompt
    
    async def _get_llm_response(self, prompt: str) -> str:
        """Get response from LLM client."""
        if not self.llm_client:
            raise ValueError("LLM client not available")
        
        try:
            # This would be implemented based on your specific LLM client
            # For now, return a mock response
            response = await self.llm_client.generate(prompt)
            return response
        except Exception as e:
            logger.error(f"Error getting LLM response: {str(e)}")
            raise
    
    async def _fallback_optimization(
        self,
        original_query: str,
        table_document: Dict[str, Any]
    ) -> OptimizationResult:
        """Fallback to rule-based optimization if LLM is not available."""
        
        # Basic rule-based optimizations
        optimized_query = original_query
        
        # Add basic optimizations
        if "SELECT *" in optimized_query.upper():
            optimized_query = optimized_query.replace("SELECT *", "SELECT specific_columns")
        
        if "WHERE 1=1" in optimized_query:
            optimized_query = optimized_query.replace("WHERE 1=1", "WHERE actual_conditions")
        
        return OptimizationResult(
            optimized_query=optimized_query,
            optimization_level="basic",
            performance_improvements=["Basic query structure optimization"],
            indexing_suggestions=["Consider adding indexes on frequently queried columns"],
            business_impact="Basic performance improvement",
            confidence=0.6,
            reasoning="Rule-based optimization applied"
        )
    
    async def _fallback_performance_analysis(
        self,
        query: str,
        table_document: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback to rule-based performance analysis."""
        
        return {
            "performance_score": 70,
            "bottlenecks": ["Potential missing indexes", "Suboptimal query structure"],
            "optimization_opportunities": ["Add indexes", "Optimize joins", "Improve filtering"],
            "indexing_recommendations": ["Create indexes on WHERE clause columns"],
            "query_structure_analysis": "Basic query structure analysis",
            "field_type_optimization": "Consider field type-specific optimizations",
            "business_impact": "Moderate performance improvement potential",
            "confidence": 0.6
        }
    
    async def _fallback_indexing_strategy(
        self,
        table_document: Dict[str, Any],
        query_patterns: List[str]
    ) -> Dict[str, Any]:
        """Fallback to rule-based indexing strategy."""
        
        table_name = table_document.get("table_name", "")
        columns = table_document.get("columns", [])
        
        # Basic indexing recommendations
        primary_indexes = []
        secondary_indexes = []
        
        for column in columns:
            if column.get("is_primary_key"):
                primary_indexes.append(f"PRIMARY KEY on {column.get('name')}")
            elif column.get("field_type") == "identifier":
                secondary_indexes.append(f"INDEX on {column.get('name')}")
            elif column.get("field_type") == "dimension":
                secondary_indexes.append(f"INDEX on {column.get('name')} for filtering")
            elif column.get("field_type") == "timestamp":
                secondary_indexes.append(f"INDEX on {column.get('name')} for date ranges")
        
        return {
            "indexing_strategy": "Basic indexing strategy based on field types",
            "primary_indexes": primary_indexes,
            "secondary_indexes": secondary_indexes,
            "composite_indexes": [],
            "specialized_indexes": [],
            "storage_recommendations": ["Consider columnar storage for analytical workloads"],
            "performance_impact": "Moderate performance improvement",
            "maintenance_considerations": ["Regular index maintenance", "Monitor index usage"],
            "confidence": 0.6
        }
    
    def _parse_optimization_response(
        self,
        response: str,
        original_query: str,
        table_document: Dict[str, Any]
    ) -> OptimizationResult:
        """Parse LLM optimization response."""
        try:
            # Try to parse as JSON
            data = json.loads(response)
            
            return OptimizationResult(
                optimized_query=data.get("optimized_query", original_query),
                optimization_level=data.get("optimization_level", "basic"),
                performance_improvements=data.get("performance_improvements", []),
                indexing_suggestions=data.get("indexing_suggestions", []),
                business_impact=data.get("business_impact", ""),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "")
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing optimization response: {str(e)}")
            # Return fallback optimization
            return self._fallback_optimization(original_query, table_document)
    
    def _parse_performance_response(
        self,
        response: str,
        query: str,
        table_document: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse LLM performance response."""
        try:
            # Try to parse as JSON
            data = json.loads(response)
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing performance response: {str(e)}")
            # Return fallback analysis
            return self._fallback_performance_analysis(query, table_document)
    
    def _parse_indexing_response(
        self,
        response: str,
        table_document: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse LLM indexing response."""
        try:
            # Try to parse as JSON
            data = json.loads(response)
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing indexing response: {str(e)}")
            # Return fallback indexing strategy
            return self._fallback_indexing_strategy(table_document, [])
    
    async def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            "cache_size": len(self.optimization_cache),
            "llm_available": self.llm_client is not None,
            "optimization_method": "LLM" if self.llm_client else "Rule-based"
        }
