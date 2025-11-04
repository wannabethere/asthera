"""
LLM-Powered Field Type Classifier

This module uses Large Language Models to intelligently classify table columns
as dimensions vs facts and generate optimized query suggestions.

Features:
- LLM-based field type classification
- Intelligent query generation
- Context-aware suggestions
- Performance optimization recommendations
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("genieml-agents")


class FieldType(Enum):
    """Enumeration of field types for better query building."""
    DIMENSION = "dimension"
    FACT = "fact"
    IDENTIFIER = "identifier"
    TIMESTAMP = "timestamp"
    CALCULATED = "calculated"


@dataclass
class LLMClassificationResult:
    """Result from LLM field type classification."""
    field_type: str
    confidence: float
    reasoning: str
    query_suggestions: List[str]
    performance_notes: List[str]
    business_context: str


class LLMFieldClassifier:
    """
    LLM-powered field type classifier for intelligent query building.
    
    This class uses LLMs to:
    1. Classify columns as dimensions vs facts
    2. Generate intelligent query suggestions
    3. Provide context-aware recommendations
    4. Optimize query performance
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize the LLM field classifier.
        
        Args:
            llm_client: Optional LLM client for classification
        """
        self.llm_client = llm_client
        self.classification_cache = {}
        logger.info("LLM Field Classifier initialized")
    
    async def classify_column_with_llm(
        self,
        column: Dict[str, Any],
        table_context: Dict[str, Any],
        project_context: Optional[Dict[str, Any]] = None
    ) -> LLMClassificationResult:
        """
        Use LLM to classify a column's field type and generate suggestions.
        
        Args:
            column: Column definition
            table_context: Table context information
            project_context: Optional project context
            
        Returns:
            LLMClassificationResult with classification and suggestions
        """
        logger.info(f"Classifying column '{column.get('name', '')}' with LLM")
        
        try:
            # Create classification prompt
            prompt = self._create_classification_prompt(column, table_context, project_context)
            
            # Get LLM response
            if self.llm_client:
                response = await self._get_llm_response(prompt)
            else:
                # Fallback to rule-based classification
                response = await self._fallback_classification(column, table_context)
            
            # Parse LLM response
            result = self._parse_llm_response(response, column)
            
            # Cache result
            cache_key = f"{column.get('name', '')}_{table_context.get('table_name', '')}"
            self.classification_cache[cache_key] = result
            
            logger.info(f"Successfully classified column '{column.get('name', '')}' as {result.field_type}")
            return result
            
        except Exception as e:
            logger.error(f"Error classifying column with LLM: {str(e)}")
            # Return fallback classification
            return await self._fallback_classification(column, table_context)
    
    async def classify_table_columns_with_llm(
        self,
        table_document: Dict[str, Any],
        project_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, LLMClassificationResult]:
        """
        Classify all columns in a table using LLM.
        
        Args:
            table_document: TABLE_DOCUMENT with columns
            project_context: Optional project context
            
        Returns:
            Dictionary mapping column names to classification results
        """
        logger.info(f"Classifying all columns in table '{table_document.get('table_name', '')}' with LLM")
        
        try:
            table_context = {
                "table_name": table_document.get("table_name", ""),
                "description": table_document.get("description", ""),
                "business_purpose": table_document.get("business_purpose", ""),
                "domain": table_document.get("domain", ""),
                "classification": table_document.get("classification", "")
            }
            
            columns = table_document.get("columns", [])
            results = {}
            
            # Classify each column
            for column in columns:
                column_name = column.get("name", "")
                if not column_name:
                    continue
                
                result = await self.classify_column_with_llm(
                    column, table_context, project_context
                )
                results[column_name] = result
            
            logger.info(f"Successfully classified {len(results)} columns with LLM")
            return results
            
        except Exception as e:
            logger.error(f"Error classifying table columns with LLM: {str(e)}")
            return {}
    
    async def generate_query_with_llm(
        self,
        table_document: Dict[str, Any],
        query_requirements: Dict[str, Any],
        project_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to generate optimized queries based on requirements.
        
        Args:
            table_document: TABLE_DOCUMENT with field type classifications
            query_requirements: Query requirements and constraints
            project_context: Optional project context
            
        Returns:
            Dictionary with generated query and metadata
        """
        logger.info(f"Generating query with LLM for table '{table_document.get('table_name', '')}'")
        
        try:
            # Create query generation prompt
            prompt = self._create_query_generation_prompt(
                table_document, query_requirements, project_context
            )
            
            # Get LLM response
            if self.llm_client:
                response = await self._get_llm_response(prompt)
            else:
                # Fallback to rule-based query generation
                response = await self._fallback_query_generation(table_document, query_requirements)
            
            # Parse LLM response
            result = self._parse_query_response(response, table_document, query_requirements)
            
            logger.info(f"Successfully generated query with LLM")
            return result
            
        except Exception as e:
            logger.error(f"Error generating query with LLM: {str(e)}")
            # Return fallback query
            return await self._fallback_query_generation(table_document, query_requirements)
    
    def _create_classification_prompt(
        self,
        column: Dict[str, Any],
        table_context: Dict[str, Any],
        project_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a prompt for LLM field type classification."""
        
        column_name = column.get("name", "")
        data_type = column.get("type", "")
        description = column.get("business_description", "")
        business_purpose = column.get("business_purpose", "")
        usage_type = column.get("usage_type", "")
        example_values = column.get("example_values", [])
        
        table_name = table_context.get("table_name", "")
        table_description = table_context.get("description", "")
        table_business_purpose = table_context.get("business_purpose", "")
        table_domain = table_context.get("domain", "")
        
        prompt = f"""
You are a data analyst expert. Classify the following database column and provide intelligent query suggestions.

COLUMN INFORMATION:
- Name: {column_name}
- Data Type: {data_type}
- Description: {description}
- Business Purpose: {business_purpose}
- Usage Type: {usage_type}
- Example Values: {example_values}

TABLE CONTEXT:
- Table Name: {table_name}
- Table Description: {table_description}
- Business Purpose: {table_business_purpose}
- Domain: {table_domain}

CLASSIFICATION TASK:
Classify this column as one of: dimension, fact, identifier, timestamp, calculated

FIELD TYPE DEFINITIONS:
- dimension: Descriptive attributes (names, categories, statuses, classifications)
- fact: Measurable metrics (counts, amounts, prices, quantities, KPIs)
- identifier: Primary/foreign keys for joins and unique identification
- timestamp: Date/time fields for temporal analysis
- calculated: Computed fields and expressions

Please respond with a JSON object containing:
{{
    "field_type": "one of the field types above",
    "confidence": "confidence score 0.0-1.0",
    "reasoning": "explanation of classification decision",
    "performance_notes": ["list of performance optimization notes"],
    "business_context": "business context and usage recommendations"
}}
"""
        
        if project_context:
            prompt += f"\nPROJECT CONTEXT:\n{json.dumps(project_context, indent=2)}"
        
        return prompt
    
    def _create_query_generation_prompt(
        self,
        table_document: Dict[str, Any],
        query_requirements: Dict[str, Any],
        project_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a prompt for LLM query generation."""
        
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
                "business_purpose": column.get("business_purpose", "")
            })
        
        query_type = query_requirements.get("query_type", "analytical")
        filters = query_requirements.get("filters", {})
        aggregations = query_requirements.get("aggregations", [])
        group_by = query_requirements.get("group_by", [])
        order_by = query_requirements.get("order_by", [])
        limit = query_requirements.get("limit")
        
        prompt = f"""
You are a SQL expert. Generate an optimized query based on the following requirements.

TABLE INFORMATION:
- Table Name: {table_name}
- Description: {table_description}
- Business Purpose: {business_purpose}
- Domain: {domain}

COLUMNS WITH FIELD TYPES:
{json.dumps(column_info, indent=2)}

QUERY REQUIREMENTS:
- Query Type: {query_type}
- Filters: {filters}
- Aggregations: {aggregations}
- Group By: {group_by}
- Order By: {order_by}
- Limit: {limit}

QUERY TYPE GUIDELINES:
- analytical: Focus on aggregations, GROUP BY, and analytical functions
- transactional: Focus on exact lookups, filtering, and OLTP operations
- reporting: Focus on comprehensive aggregations and reporting metrics

FIELD TYPE USAGE:
- facts: Use for aggregations (SUM, COUNT, AVG, MAX, MIN)
- dimensions: Use for GROUP BY, WHERE clauses, and descriptive information
- identifiers: Use for JOIN conditions and exact lookups
- timestamps: Use for date range filtering and time-based analysis
- calculated: Use for computed fields and expressions

Please respond with a JSON object containing:
{{
    "query": "optimized SQL query",
    "query_type": "{query_type}",
    "field_type_usage": {{
        "facts_used": ["list of fact columns used"],
        "dimensions_used": ["list of dimension columns used"],
        "identifiers_used": ["list of identifier columns used"],
        "timestamps_used": ["list of timestamp columns used"]
    }},
    "optimization_notes": ["list of optimization recommendations"],
    "performance_considerations": ["list of performance considerations"],
    "business_value": "explanation of business value and use cases"
}}
"""
        
        if project_context:
            prompt += f"\nPROJECT CONTEXT:\n{json.dumps(project_context, indent=2)}"
        
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
    
    async def _fallback_classification(
        self,
        column: Dict[str, Any],
        table_context: Dict[str, Any]
    ) -> LLMClassificationResult:
        """Fallback to rule-based classification if LLM is not available."""
        
        column_name = column.get("name", "").lower()
        data_type = column.get("type", "").upper()
        is_primary_key = column.get("is_primary_key", False)
        is_calculated = column.get("is_calculated", False)
        
        # Rule-based classification
        if is_primary_key:
            field_type = "identifier"
            confidence = 0.9
            reasoning = "Primary key column"
        elif is_calculated:
            field_type = "fact"
            confidence = 0.8
            reasoning = "Calculated field"
        elif any(pattern in column_name for pattern in ["_id", "_key", "id_", "key_"]):
            field_type = "identifier"
            confidence = 0.7
            reasoning = "Column name suggests identifier"
        elif any(pattern in column_name for pattern in ["_date", "_time", "created_", "updated_"]):
            field_type = "timestamp"
            confidence = 0.7
            reasoning = "Column name suggests timestamp"
        elif any(pattern in column_name for pattern in ["_count", "_total", "_sum", "_amount", "_price"]):
            field_type = "fact"
            confidence = 0.7
            reasoning = "Column name suggests fact/measure"
        elif data_type in ["DATE", "DATETIME", "TIMESTAMP"]:
            field_type = "timestamp"
            confidence = 0.8
            reasoning = "Date/time data type"
        elif data_type in ["INTEGER", "BIGINT", "DECIMAL", "FLOAT", "DOUBLE"]:
            field_type = "fact"
            confidence = 0.6
            reasoning = "Numeric data type"
        else:
            field_type = "dimension"
            confidence = 0.5
            reasoning = "Default classification"
        
        # Generate basic suggestions
        query_suggestions = self._generate_basic_suggestions(field_type, column)
        performance_notes = self._generate_basic_performance_notes(field_type, column)
        
        return LLMClassificationResult(
            field_type=field_type,
            confidence=confidence,
            reasoning=reasoning,
            query_suggestions=[],  # Not needed - using SQL pairs and instructions
            performance_notes=performance_notes,
            business_context=f"Column '{column.get('name', '')}' classified as {field_type}"
        )
    
    async def _fallback_query_generation(
        self,
        table_document: Dict[str, Any],
        query_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback to rule-based query generation if LLM is not available."""
        
        table_name = table_document.get("table_name", "")
        query_type = query_requirements.get("query_type", "analytical")
        
        # Basic query generation
        if query_type == "analytical":
            query = f"SELECT * FROM {table_name} WHERE 1=1"
        elif query_type == "transactional":
            query = f"SELECT * FROM {table_name} WHERE id = ?"
        else:
            query = f"SELECT * FROM {table_name}"
        
        return {
            "query": query,
            "query_type": query_type,
            "field_type_usage": {},
            "optimization_notes": ["Basic query generated"],
            "performance_considerations": ["Consider adding indexes"],
            "business_value": "Basic query for data access"
        }
    
    def _parse_llm_response(self, response: str, column: Dict[str, Any]) -> LLMClassificationResult:
        """Parse LLM response into classification result."""
        try:
            # Try to parse as JSON
            data = json.loads(response)
            
            return LLMClassificationResult(
                field_type=data.get("field_type", "dimension"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                query_suggestions=[],  # Not needed - using SQL pairs and instructions
                performance_notes=data.get("performance_notes", []),
                business_context=data.get("business_context", "")
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            # Return fallback classification
            return self._fallback_classification(column, {})
    
    def _parse_query_response(self, response: str, table_document: Dict[str, Any], query_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM query response."""
        try:
            # Try to parse as JSON
            data = json.loads(response)
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing query response: {str(e)}")
            # Return fallback query
            return {
                "query": f"SELECT * FROM {table_document.get('table_name', '')}",
                "query_type": query_requirements.get("query_type", "analytical"),
                "field_type_usage": {},
                "optimization_notes": ["Fallback query generated"],
                "performance_considerations": ["Consider optimization"],
                "business_value": "Basic query for data access"
            }
    
    def _generate_basic_suggestions(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Generate basic query suggestions based on field type."""
        # Not needed - using SQL pairs and instructions
        return []
    
    def _generate_basic_performance_notes(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Generate basic performance notes based on field type."""
        column_name = column.get("name", "")
        notes = []
        
        if field_type == "fact":
            notes.extend([
                f"Consider indexes on {column_name} for aggregation performance",
                "Use appropriate aggregation functions"
            ])
        elif field_type == "dimension":
            notes.extend([
                f"Consider index on {column_name} for filtering",
                "Use appropriate data types"
            ])
        elif field_type == "identifier":
            notes.extend([
                f"Create primary key index on {column_name}",
                "Use integer types for better performance"
            ])
        elif field_type == "timestamp":
            notes.extend([
                f"Create index on {column_name} for date range queries",
                "Consider partitioning by date"
            ])
        
        return notes
    
    async def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        return {
            "cache_size": len(self.classification_cache),
            "llm_available": self.llm_client is not None,
            "classification_method": "LLM" if self.llm_client else "Rule-based"
        }
